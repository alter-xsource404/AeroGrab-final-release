"""v1.8.1: YouTube/yt-dlp environment (JS runtime, self-updating yt-dlp), routing of YouTube downloads to yt-dlp's own downloader,
fallback when AeroGrab's own engine fails, and plain-words error reporting. No network: every download is a fake."""
import hashlib, http.server, io, json, os, shutil, stat, sys, tempfile, threading, time, types, unittest, zipfile
from unittest import mock
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import aerograb

POSIX = os.name != "nt"


def make_exe(folder, name, text):
    p = os.path.join(folder, name)
    with open(p, "w") as f:
        f.write("#!/bin/sh\n" + text + "\n")
    os.chmod(p, os.stat(p).st_mode | stat.S_IEXEC)
    return p


class TestExplain(unittest.TestCase):
    def test_codes(self):
        cases = {
            "ERROR: [youtube] abc: Sign in to confirm you're not a bot": "bot",
            "No supported JavaScript runtime could be found": "js_runtime",
            "n challenge solving failed: Some formats may be missing": "js_runtime",
            "ERROR: Sign in to confirm your age. This video may be inappropriate for some users.": "age",
            "Private video. Sign in if you've been granted access": "login",
            "The uploader has not made this video available in your country": "geo",
            "This video is DRM protected": "drm",
            "Video unavailable. This video has been removed": "unavailable",
            "Requested format is not available. Use --list-formats": "format",
            "<urlopen error [Errno 11001] getaddrinfo failed>": "network",
            "Unable to extract uploader id": "outdated",
            "something nobody has seen before": "unknown",
        }
        for msg, code in cases.items():
            self.assertEqual(aerograb.explain_ytdlp_error(msg)[0], code, msg)
        self.assertTrue(aerograb.explain_ytdlp_error("No supported JavaScript runtime")[1])
        self.assertEqual(aerograb.explain_ytdlp_error(None), ("unknown", ""))


class TestRouting(unittest.TestCase):
    def test_which_streams_need_ytdlp_downloader(self):
        n = aerograb.needs_ytdlp_downloader
        self.assertTrue(n("https://www.youtube.com/watch?v=x", [{"url": "https://x.test/v.mp4"}]))
        self.assertTrue(n("https://youtu.be/x", []))
        self.assertTrue(n("https://vimeo.com/1", [{"url": "https://rr1---sn-abc.googlevideo.com/videoplayback?x=1"}]))
        self.assertTrue(n("https://x.test/p", [{"url": "https://cdn.test/v.mp4", "downloader_options": {"http_chunk_size": 10485760}}]))
        self.assertTrue(n("https://x.test/p", [{"url": "https://cdn.test/v.mp4", "cookies": "a=b"}]))
        self.assertTrue(n("https://x.test/p", [{"url": "https://cdn.test/v.mp4", "http_headers": {"User-Agent": "u", "X-Token": "t"}}]))
        self.assertFalse(n("https://vimeo.com/1", [{"url": "https://cdn.test/v.mp4", "http_headers": {"User-Agent": "u", "Referer": "r", "Accept": "*/*"}}]))
        self.assertFalse(n("https://vimeo.com/1", [{"url": "https://cdn.test/v.mp4"}]))

    def test_is_youtube_url(self):
        for u in ("https://www.youtube.com/watch?v=1", "https://m.youtube.com/shorts/1", "https://youtu.be/1", "https://www.youtube-nocookie.com/embed/1"):
            self.assertTrue(aerograb.is_youtube_url(u), u)
        for u in ("https://vimeo.com/1", "https://notyoutube.com/", "https://youtube.com.evil.test/", ""):
            self.assertFalse(aerograb.is_youtube_url(u), u)


class FakeYDL:
    """Stands in for yt_dlp.YoutubeDL: extract_info(download=True) reports two files (video, audio) through the hooks and writes the result."""
    infos, calls, opts_seen = {}, [], []

    def __init__(self, opts):
        self.opts = opts
        FakeYDL.opts_seen.append(opts)

    def __enter__(self): return self
    def __exit__(self, *a): return False

    def extract_info(self, url, download=False):
        FakeYDL.calls.append((url, download))
        info = FakeYDL.infos.get(url, {"title": "T", "id": "i"})
        if download:
            for h in self.opts["progress_hooks"]:
                h({"status": "downloading", "filename": "v.f137.mp4", "downloaded_bytes": 500, "total_bytes": 1000})
                h({"status": "finished", "filename": "v.f137.mp4", "downloaded_bytes": 1000, "total_bytes": 1000})
                h({"status": "downloading", "filename": "v.f140.m4a", "downloaded_bytes": 100, "total_bytes": 200})
            for h in self.opts.get("postprocessor_hooks", []):
                h({"status": "started"})
            path = self.opts["outtmpl"].replace("%(title).120B [%(id)s]", "T [i]") % {"ext": "mp4"}  # like yt-dlp: %% -> %, %(ext)s -> mp4
            with open(path, "wb") as f:
                f.write(b"x" * 1200)
            info = dict(info, requested_downloads=[{"filepath": path}])
        return info


def fake_module(infos=None, version="2024.01.01"):
    m = types.ModuleType("yt_dlp")
    m.YoutubeDL = FakeYDL
    m.version = types.SimpleNamespace(__version__=version)
    FakeYDL.infos, FakeYDL.calls, FakeYDL.opts_seen = infos or {}, [], []
    return mock.patch.dict(sys.modules, {"yt_dlp": m})


def finish(d, timeout=30):
    d.start()
    end = time.time() + timeout
    while d.status not in ("Completed", "Error", "Paused") and time.time() < end:
        time.sleep(0.05)
    return d


class TestYoutubeNative(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def test_youtube_goes_straight_to_ytdlp_downloader_without_a_second_lookup(self):
        url = "https://www.youtube.com/watch?v=abc"
        with fake_module():
            d = finish(aerograb.ExtractDownload(url, self.tmp, 4, quality=720, hint="Great Video 720p"))
            calls = list(FakeYDL.calls)
        self.assertEqual((d.status, type(d.inner).__name__), ("Completed", "NativeYt"), d.error)
        self.assertEqual(calls, [(url, True)])  # one yt-dlp run, which also downloads: no separate "resolve" extraction first
        self.assertEqual(os.path.basename(d.path), "Great Video 720p.mp4")

    def test_progress_covers_video_and_audio_and_joining_is_noted(self):
        with fake_module():
            d = aerograb.NativeYt("https://www.youtube.com/watch?v=abc", self.tmp, 2, hint="Clip")
            seen = []
            real = FakeYDL.extract_info

            def spy(self_, url, download=False):
                seen.append(None)
                return real(self_, url, download)
            with mock.patch.object(FakeYDL, "extract_info", spy):
                finish(d)
        self.assertEqual(d.status, "Completed", d.error)
        self.assertEqual(d.size, 1200)  # the finished file's real size replaces the estimate

    def test_percent_sign_in_a_title_is_not_a_template_field(self):
        with fake_module():
            d = finish(aerograb.NativeYt("https://www.youtube.com/watch?v=abc", self.tmp, 2, hint="100% real 1080p"))
        self.assertEqual((d.status, os.path.basename(d.path)), ("Completed", "100% real 1080p.mp4"), d.error)
        self.assertIn("100%% real 1080p", FakeYDL.opts_seen[0]["outtmpl"])

    def test_no_name_known_uses_ytdlp_title_template(self):
        with fake_module():
            d = finish(aerograb.NativeYt("https://www.youtube.com/watch?v=abc", self.tmp, 2))
        self.assertEqual((d.status, os.path.basename(d.path)), ("Completed", "T [i].mp4"), d.error)

    def test_speed_limit_reaches_ytdlp(self):
        with fake_module():
            d = aerograb.NativeYt("https://www.youtube.com/watch?v=abc", self.tmp, 2, hint="x")
            d.set_limit(500)
            finish(d)
        self.assertEqual(FakeYDL.opts_seen[0].get("ratelimit"), 500 * 1024)

    def test_ytdlp_failure_is_explained(self):
        class Boom(FakeYDL):
            def extract_info(self, url, download=False):
                raise RuntimeError("ERROR: [youtube] abc: Sign in to confirm you're not a bot")
        with fake_module():
            sys.modules["yt_dlp"].YoutubeDL = Boom
            d = finish(aerograb.NativeYt("https://www.youtube.com/watch?v=abc", self.tmp, 2, hint="x"))
        self.assertEqual(d.status, "Error")
        self.assertIn("proof that you are a person", d.error)
        self.assertIn("not a bot", d.error)  # the original message is kept, too


class Always403(http.server.BaseHTTPRequestHandler):
    def do_GET(self): self.send_error(403)
    do_HEAD = do_GET
    def log_message(self, *a): pass


class TestFallback(unittest.TestCase):
    def test_own_engine_failure_falls_back_to_ytdlp_downloader(self):
        srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Always403)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(srv.shutdown)
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        page = "https://vimeo.com/42"
        info = {"title": "Clip", "ext": "mp4", "protocol": "https", "url": f"http://127.0.0.1:{srv.server_address[1]}/v.mp4"}
        with fake_module({page: info}):
            d = finish(aerograb.ExtractDownload(page, tmp, 2), timeout=60)
            downloads = [c for c in FakeYDL.calls if c[1]]
        self.assertEqual((d.status, type(d.inner).__name__), ("Completed", "NativeYt"), d.error)
        self.assertEqual(len(downloads), 1)


class TestOpts(unittest.TestCase):
    def test_solver_and_runtime_are_configured(self):
        with mock.patch.object(aerograb, "find_js_runtime", return_value={"name": "deno", "path": "/x/deno"}):
            o = aerograb.ytdlp_opts(720, limit_kb=100)
        self.assertEqual(o["js_runtimes"], {"deno": {"path": "/x/deno"}})
        self.assertEqual(o["remote_components"], ["ejs:github"])
        self.assertEqual(o["ratelimit"], 100 * 1024)
        self.assertIn("height<=720", o["format"])
        with mock.patch.object(aerograb, "find_js_runtime", return_value=None):
            o = aerograb.ytdlp_opts()
        self.assertNotIn("js_runtimes", o)
        self.assertNotIn("ratelimit", o)


@unittest.skipUnless(POSIX, "uses shell-script stand-ins for runtimes")
class TestRuntime(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.home, True)
        self.p = [mock.patch.object(aerograb, "CFG_DIR", self.home), mock.patch.dict(os.environ, {"PATH": "/nonexistent"}),
                  mock.patch.object(aerograb.os.path, "expanduser", lambda s: self.home if s == "~" else s)]
        for p in self.p:
            p.start()
            self.addCleanup(p.stop)

    def test_finds_deno_in_aerograb_folder_and_rejects_old_node(self):
        os.makedirs(os.path.join(self.home, "runtime"))
        deno = make_exe(os.path.join(self.home, "runtime"), "deno", 'echo "deno 2.1.4 (stable)"')
        rt = aerograb.find_js_runtime(refresh=True)
        self.assertEqual(rt, {"name": "deno", "path": deno})
        bin_ = os.path.join(self.home, "bin")
        os.makedirs(bin_)
        os.remove(deno)
        make_exe(bin_, "node", 'echo "v18.19.0"')
        with mock.patch.dict(os.environ, {"PATH": bin_}):
            self.assertIsNone(aerograb.find_js_runtime(refresh=True))  # Node < 22 is useless to yt-dlp
            make_exe(bin_, "node", 'echo "v22.3.0"')
            self.assertEqual(aerograb.find_js_runtime(refresh=True)["name"], "node")

    def test_install_deno_from_a_fake_release(self):
        script = b'#!/bin/sh\necho "deno 2.2.0"\n'
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("deno", script)
        data = buf.getvalue()
        asked = []

        def fetch(url, timeout=60, limit=0, accept=None):
            asked.append(url)
            if url.endswith(".sha256sum"):
                return (hashlib.sha256(data).hexdigest() + "  deno.zip\n").encode()
            return data
        path = aerograb.install_deno(fetch)
        self.assertEqual(path, os.path.join(self.home, "runtime", "deno"))
        self.assertTrue(asked[0].startswith("https://github.com/denoland/deno/releases/latest/download/deno-"))
        self.assertEqual(aerograb.find_js_runtime(refresh=True)["path"], path)

        def bad_sum(url, timeout=60, limit=0, accept=None):
            return b"0" * 64 + b"  x\n" if url.endswith(".sha256sum") else data
        with self.assertRaisesRegex(IOError, "checksum"):
            aerograb.install_deno(bad_sum)
        with self.assertRaisesRegex(IOError, "damaged"):
            aerograb.install_deno(lambda url, *a, **k: b"not a zip" if not url.endswith(".sha256sum") else b"")

    def test_deno_asset_names(self):
        self.assertEqual(aerograb.deno_asset("Windows", "AMD64"), "deno-x86_64-pc-windows-msvc.zip")
        self.assertEqual(aerograb.deno_asset("Darwin", "arm64"), "deno-aarch64-apple-darwin.zip")
        self.assertEqual(aerograb.deno_asset("Linux", "x86_64"), "deno-x86_64-unknown-linux-gnu.zip")


class TestUpdater(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.home, True)
        for p in (mock.patch.object(aerograb, "CFG_DIR", self.home), mock.patch.object(sys, "path", list(sys.path)),
                  mock.patch.dict(sys.modules), mock.patch.dict(os.environ, {"AEROGRAB_NO_YTDLP_UPDATE": ""})):
            p.start()
            self.addCleanup(p.stop)
        os.environ.pop("AEROGRAB_NO_YTDLP_UPDATE", None)
        self.addCleanup(sys.path_importer_cache.pop, os.path.join(self.home, "ytdlp", "yt-dlp.zip"), None)

    def release(self, tag, tamper=False, claim=None):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("yt_dlp/__init__.py", "")
            z.writestr("yt_dlp/version.py", f"__version__ = '{claim or tag}'\n")
        data = buf.getvalue()
        sums = f"{hashlib.sha256(data + (b'x' if tamper else b'')).hexdigest()}  yt-dlp\n{'0' * 64}  yt-dlp.exe\n".encode()
        asked = []

        def fetch(url, timeout=60, limit=0, accept=None):
            asked.append(url)
            if "api.github.com" in url:
                return json.dumps({"tag_name": tag}).encode()
            return sums if url.endswith("SHA2-256SUMS") else data
        fetch.asked = asked
        return fetch

    def test_newer_release_is_installed_and_used(self):
        with fake_module(version="2024.01.01"):
            f = self.release("2099.01.02")
            r = aerograb.ytdlp_update(fetch=f)
            self.assertEqual((r["updated"], r["version"], r["error"]), (True, "2099.01.02", ""), r)
            self.assertEqual(aerograb.ytdlp_version(), "2099.01.02")  # the running program switched to the downloaded copy
            self.assertTrue(os.path.isfile(os.path.join(self.home, "ytdlp", "yt-dlp.zip")))
            n = len(f.asked)
            r2 = aerograb.ytdlp_update(fetch=f)  # checked a moment ago: no network at all
            self.assertTrue(r2["skipped"])
            self.assertEqual(len(f.asked), n)

    def test_up_to_date_downloads_nothing(self):
        with fake_module(version="2099.05.05"):
            f = self.release("2099.01.02")
            r = aerograb.ytdlp_update(fetch=f)
            self.assertEqual((r["updated"], r["error"]), (False, ""))
            self.assertEqual([u for u in f.asked if u.endswith("/yt-dlp")], [])

    def test_bad_checksum_and_lying_release_are_refused(self):
        with fake_module(version="2024.01.01"):
            r = aerograb.ytdlp_update(force=True, fetch=self.release("2099.01.02", tamper=True))
            self.assertFalse(r["updated"])
            self.assertIn("checksum", r["error"])
            r = aerograb.ytdlp_update(force=True, fetch=self.release("2099.01.03", claim="2000.01.01"))
            self.assertIn("not the release", r["error"])
            self.assertFalse(os.path.exists(os.path.join(self.home, "ytdlp", "yt-dlp.zip")))
            self.assertEqual(aerograb.ytdlp_version(), "2024.01.01")

    def test_odd_release_names_are_refused_and_network_errors_reported(self):
        with fake_module():
            r = aerograb.ytdlp_update(force=True, fetch=self.release("evil; rm -rf"))
            self.assertIn("unexpected release name", r["error"])

            def down(*a, **k): raise OSError("no route to host")
            self.assertIn("no route", aerograb.ytdlp_update(force=True, fetch=down)["error"])

    def test_downloaded_copy_wins_at_start_only_when_newer(self):
        z = os.path.join(self.home, "ytdlp", "yt-dlp.zip")
        os.makedirs(os.path.dirname(z))
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("yt_dlp/version.py", "__version__ = '2030.01.01'\n")
        open(z, "wb").write(buf.getvalue())
        with mock.patch.object(aerograb, "_installed_ytdlp_version", return_value="2029.12.31"):
            self.assertTrue(aerograb._prefer_downloaded_ytdlp())
        sys.path.remove(z)
        with mock.patch.object(aerograb, "_installed_ytdlp_version", return_value="2030.01.01"):
            self.assertFalse(aerograb._prefer_downloaded_ytdlp())
        with mock.patch.dict(os.environ, {"AEROGRAB_NO_YTDLP_UPDATE": "1"}), mock.patch.object(aerograb, "_installed_ytdlp_version", return_value=""):
            self.assertFalse(aerograb._prefer_downloaded_ytdlp())

    def test_version_ordering(self):
        k = aerograb._vkey
        self.assertLess(k("2025.11.12"), k("2026.03.02"))
        self.assertLess(k("2026.03.02"), k("2026.03.02.232212"))  # a nightly of that day is newer than the stable release
        self.assertLess(k("2026.03.02.100000"), k("2026.03.02.232212"))
        self.assertEqual(k(""), ())


class TestFormatsErrors(unittest.TestCase):
    """The /formats endpoint reports WHY it failed, and updates yt-dlp once when the failure looks like 'out of date'."""

    def payload(self, fn):
        import http.client, socket
        s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
        state = tempfile.mkdtemp(); self.addCleanup(shutil.rmtree, state, True)
        token = aerograb.get_token(state)

        class M:
            settings = {}; speed_seen = 0.0
            def add(self, *a, **k): pass
        srv = aerograb.start_api(M(), lambda: ("/tmp", 4), port=port, token=token, state_dir=state, confirm=lambda j: None)
        self.addCleanup(srv.shutdown)
        c = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
        c.request("POST", "/formats", json.dumps({"url": "https://www.youtube.com/watch?v=abc"}), {"X-AeroGrab-Token": token, "Content-Type": "application/json"})
        return json.loads(c.getresponse().read())

    def test_failure_has_code_and_hint(self):
        with mock.patch.object(aerograb, "ytdlp_formats", side_effect=RuntimeError("Sign in to confirm you're not a bot")):
            r = self.payload(None)
        self.assertEqual((r["ok"], r["code"]), (False, "bot"))
        self.assertIn("proof", r["hint"])
        self.assertIn("could not read this video", r["error"])

    def test_outdated_ytdlp_is_updated_once_then_retried(self):
        ok = {"title": "T", "fallback": "T", "duration": 10, "formats": [{"height": 1080, "fps": 30, "ext": "mp4", "size": 1, "approx": True}], "audio": None}
        calls = []

        def formats(*a):
            calls.append(1)
            if len(calls) == 1:
                raise RuntimeError("Unable to extract player response")
            return dict(ok)
        with mock.patch.object(aerograb, "ytdlp_formats", formats), mock.patch.object(aerograb, "ytdlp_update", return_value={"updated": True}) as up, \
                mock.patch.object(aerograb, "ensure_js_runtime_async"):
            r = self.payload(None)
        self.assertTrue(r["ok"], r)
        self.assertEqual((len(calls), up.call_count), (2, 1))
        self.assertTrue(up.call_args.kwargs.get("force"))

    def test_no_retry_when_nothing_was_updated_or_error_is_not_about_versions(self):
        with mock.patch.object(aerograb, "ytdlp_formats", side_effect=RuntimeError("Unable to extract x")) as f, \
                mock.patch.object(aerograb, "ytdlp_update", return_value={"updated": False}), mock.patch.object(aerograb, "ensure_js_runtime_async"):
            r = self.payload(None)
            self.assertEqual((r["ok"], r["code"], f.call_count), (False, "outdated", 1))
        with mock.patch.object(aerograb, "ytdlp_formats", side_effect=RuntimeError("Private video")) as f, \
                mock.patch.object(aerograb, "ytdlp_update") as up:
            r = self.payload(None)
            self.assertEqual((r["code"], f.call_count, up.call_count), ("login", 1, 0))

    def test_low_quality_warning_when_no_runtime(self):
        info = {"title": "T", "duration": 10, "formats": [{"format_id": "18", "height": 360, "vcodec": "avc1", "acodec": "mp4a", "ext": "mp4", "tbr": 500}]}
        with fake_module({"https://www.youtube.com/watch?v=abc": info}), mock.patch.object(aerograb, "find_js_runtime", return_value=None):
            r = aerograb.ytdlp_formats("https://www.youtube.com/watch?v=abc")
        self.assertIn("no JavaScript runtime", r["warning"])
        with fake_module({"https://www.youtube.com/watch?v=abc": info}), mock.patch.object(aerograb, "find_js_runtime", return_value={"name": "deno", "path": "x"}):
            self.assertNotIn("warning", aerograb.ytdlp_formats("https://www.youtube.com/watch?v=abc"))


if __name__ == "__main__":
    unittest.main()
