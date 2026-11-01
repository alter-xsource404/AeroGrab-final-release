"""v1.8.0: capture metadata, keep-alive local server, single-flight /formats, DRM refusal, native-host connection reuse."""
import http.client, json, os, socket, struct, sys, tempfile, threading, time, unittest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import opendm


def free_port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


class Mgr:
    settings = {}
    speed_seen = 0.0
    def add(self, *a, **k): pass


class TestMeta(unittest.TestCase):
    def test_sanitize_meta(self):
        m = opendm.sanitize_meta({"site": " YouTube\x00 ", "title": "T" * 500, "ext": "mp4", "height": 1080, "duration": 212.6, "size": 5e7, "source": "page", "audio": True,
                                  "evil": "x", "width": -5})
        self.assertEqual((m["site"], len(m["title"]), m["ext"], m["height"], m["duration"], m["size"], m["source"], m["audio"]), ("YouTube", 200, "mp4", 1080, 212, 50000000, "page", True))
        self.assertNotIn("evil", m); self.assertNotIn("width", m)
        for bad in (None, "x", [], {"ext": "mp4;rm", "height": "1080", "size": 1 << 60, "source": "hacker", "audio": 1}):
            self.assertEqual(opendm.sanitize_meta(bad), {}, bad)

    def test_capture_summary(self):
        self.assertEqual(opendm.capture_summary({"height": 1080, "ext": "mp4", "duration": 754, "size": 85 * 1048576, "source": "page", "site": "YouTube"}), "1080p \u00b7 MP4 \u00b7 12:34 \u00b7 about 85.0 MB   (YouTube)")
        self.assertEqual(opendm.capture_summary({"audio": True, "ext": "m4a", "duration": 3725}), "Audio only \u00b7 M4A \u00b7 1:02:05")
        self.assertEqual(opendm.capture_summary({}), ""); self.assertEqual(opendm.capture_summary(None), "")


class Api(unittest.TestCase):
    def setUp(self):
        self.state = tempfile.mkdtemp(); self.port = free_port(); self.token = opendm.get_token(self.state); self.jobs = []
        self.srv = opendm.start_api(Mgr(), lambda: ("/tmp", 4), port=self.port, token=self.token, state_dir=self.state, confirm=self.jobs.append)
        self.addCleanup(self.srv.shutdown)

    def conn(self): return http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
    H = property(lambda s: {"X-OpenDM-Token": s.token, "Content-Type": "application/json"})

    def post(self, c, path, body):
        c.request("POST", path, json.dumps(body), self.H); r = c.getresponse(); return r.status, json.loads(r.read() or b"{}")

    def test_keep_alive_serves_many_requests_on_one_connection(self):
        c = self.conn()
        for i in range(5):
            st, _ = self.post(c, "/add", {"url": f"https://a.test/{i}.mp4", "ts": int(time.time() * 1000)}); self.assertEqual(st, 200)
        self.assertIsNotNone(c.sock, "connection stayed open"); self.assertEqual(len(self.jobs), 5)

    def test_unknown_paths_answer_404_instead_of_hanging(self):
        c = self.conn(); c.request("POST", "/nope", "{}", self.H); self.assertEqual(c.getresponse().status, 404)
        c = self.conn(); c.request("GET", "/nope", headers=self.H); self.assertEqual(c.getresponse().status, 404)

    def test_bad_token_closes_connection_and_does_not_poison_the_next_request(self):
        c = self.conn(); c.request("POST", "/add", json.dumps({"url": "https://a.test/x"}), {"X-OpenDM-Token": "bad"})
        r = c.getresponse(); r.read(); self.assertEqual(r.status, 401); self.assertTrue(r.will_close)

    def test_meta_reaches_the_dialog_cleaned_and_drm_is_refused(self):
        st, _ = self.post(self.conn(), "/add", {"url": "https://www.youtube.com/watch?v=x", "kind": "ytdlp", "quality": 1080, "filename": "T 1080p", "ts": int(time.time() * 1000),
                                               "meta": {"site": "YouTube", "height": 1080, "ext": "mp4", "junk": "x"}})
        self.assertEqual(st, 200); self.assertEqual(self.jobs[-1]["meta"], {"site": "YouTube", "height": 1080, "ext": "mp4"}); self.assertEqual(self.jobs[-1]["kind"], "ytdlp")
        n = len(self.jobs)
        st, body = self.post(self.conn(), "/add", {"url": "https://a.test/p.mpd", "kind": "dash", "drm": True}); self.assertEqual(st, 422); self.assertEqual(len(self.jobs), n)

    def test_simultaneous_formats_lookups_run_yt_dlp_once(self):
        runs = []
        def fake(url, *a, **k):
            runs.append(url); time.sleep(0.3)
            return {"title": "t", "fallback": "t", "duration": 1, "formats": [{"height": 720, "ext": "mp4", "size": 1, "approx": True, "fps": 30}], "audio": None}
        old = (opendm.ytdlp_formats, opendm.media_site); opendm.ytdlp_formats, opendm.media_site = fake, lambda u: True
        self.addCleanup(lambda: setattr(opendm, "ytdlp_formats", old[0])); self.addCleanup(lambda: setattr(opendm, "media_site", old[1]))
        out = []
        def go():
            st, b = self.post(self.conn(), "/formats", {"url": "https://www.youtube.com/watch?v=SF"}); out.append((st, b["ok"]))
        ts = [threading.Thread(target=go) for _ in range(3)]; [t.start() for t in ts]; [t.join() for t in ts]
        self.assertEqual(len(runs), 1); self.assertEqual(out, [(200, True)] * 3)
        go(); self.assertEqual(len(runs), 1, "a later call is served from the cache")

    def test_a_failed_lookup_is_shared_and_not_stuck(self):
        def boom(*a, **k): time.sleep(0.2); raise RuntimeError("bot check")
        old = (opendm.ytdlp_formats, opendm.media_site); opendm.ytdlp_formats, opendm.media_site = boom, lambda u: True
        self.addCleanup(lambda: setattr(opendm, "ytdlp_formats", old[0])); self.addCleanup(lambda: setattr(opendm, "media_site", old[1]))
        res = []
        ts = [threading.Thread(target=lambda: res.append(self.post(self.conn(), "/formats", {"url": "https://www.youtube.com/watch?v=F"})[1])) for _ in range(2)]
        [t.start() for t in ts]; [t.join() for t in ts]
        self.assertTrue(all(not r["ok"] and "bot check" in r["error"] for r in res))
        st, b = self.post(self.conn(), "/formats", {"url": "https://www.youtube.com/watch?v=F"}); self.assertFalse(b["ok"])   # a new call is not blocked forever


class Host(unittest.TestCase):
    def test_host_reuses_one_connection_and_caches_state_files(self):
        state = tempfile.mkdtemp(); port = free_port(); token = opendm.get_token(state); seen = []
        srv = opendm.start_api(Mgr(), lambda: ("/tmp", 4), port=port, token=token, state_dir=state, confirm=seen.append); self.addCleanup(srv.shutdown)
        host = opendm.NativeHost(state_dir=state, launch=lambda: self.fail("no launch"), sleep=lambda s: None)
        accepted = []
        orig = srv.get_request
        def counting():
            r = orig(); accepted.append(1); return r
        srv.get_request = counting
        reads = []
        orig_read = opendm.read_json
        opendm.read_json = lambda *a, **k: (reads.append(1), orig_read(*a, **k))[1]; self.addCleanup(lambda: setattr(opendm, "read_json", orig_read))
        for i in range(10):
            self.assertEqual(host.handle({"cmd": "add", "job": {"url": f"https://a.test/{i}.zip", "ts": int(time.time() * 1000)}}), {"ok": True})
        self.assertEqual(len(seen), 10); self.assertEqual(len(accepted), 1, "one TCP connection for ten hand-overs"); self.assertLessEqual(len(reads), 1, "api.json is read once, not per message")

    def test_host_recovers_when_the_server_restarts(self):
        state = tempfile.mkdtemp(); port = free_port(); token = opendm.get_token(state); seen = []
        srv = opendm.start_api(Mgr(), lambda: ("/tmp", 4), port=port, token=token, state_dir=state, confirm=seen.append)
        host = opendm.NativeHost(state_dir=state, launch=lambda: None, sleep=lambda s: None)
        job = lambda n: {"cmd": "add", "job": {"url": f"https://a.test/{n}.zip", "ts": int(time.time() * 1000)}}
        self.assertEqual(host.handle(job(1)), {"ok": True})
        srv.shutdown(); srv.server_close()
        srv = opendm.start_api(Mgr(), lambda: ("/tmp", 4), port=port, token=token, state_dir=state, confirm=seen.append); self.addCleanup(srv.shutdown)
        self.assertEqual(host.handle(job(2)), {"ok": True}); self.assertEqual(len(seen), 2)


if __name__ == "__main__":
    unittest.main()
