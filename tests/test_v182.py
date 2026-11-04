"""v1.8.2: browser -> AeroGrab hand-over latency. A slow 'config' / 'ping' must never delay an 'add'."""
import io, json, os, struct, sys, tempfile, threading, time, unittest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import aerograb


def frame(o):
    b = json.dumps(o).encode()
    return struct.pack("<I", len(b)) + b


def unframe(data):
    out, i = [], 0
    while i < len(data):
        n = struct.unpack("<I", data[i:i + 4])[0]
        out.append(json.loads(data[i + 4:i + 4 + n]))
        i += 4 + n
    return out


class TestHandOverLatency(unittest.TestCase):
    def test_slow_config_does_not_block_add(self):
        host = aerograb.NativeHost(state_dir=tempfile.mkdtemp())
        order = []
        release = threading.Event()

        def handle(m):
            if m["cmd"] == "config":
                release.wait(5)          # a slow settings refresh
            order.append(m["cmd"])
            if m["cmd"] == "add":
                release.set()            # only now may the config answer finish
            return {"ok": True}

        host.handle = handle
        data = frame({"cmd": "config", "id": 1}) + frame({"cmd": "add", "id": 2, "job": {"url": "https://x.test/a.zip"}})
        out = io.BytesIO()
        t0 = time.time()
        host.serve(["--native-host"], stdin=io.BytesIO(data), stdout=out)
        self.assertLess(time.time() - t0, 3, "add waited for the slow config")
        self.assertEqual(order, ["add", "config"])
        self.assertEqual(sorted(r["id"] for r in unframe(out.getvalue())), [1, 2])

    def test_messages_without_id_keep_their_order(self):
        host = aerograb.NativeHost(state_dir=tempfile.mkdtemp())
        seen = []
        host.handle = lambda m: (seen.append(m["cmd"]), {"ok": True})[1]
        host.serve(["--native-host"], stdin=io.BytesIO(frame({"cmd": "ping"}) + frame({"cmd": "config"}) + frame({"cmd": "add", "job": {}})), stdout=io.BytesIO())
        self.assertEqual(seen, ["ping", "config", "add"])

    def test_cold_start_polls_quickly(self):
        sleeps = []
        calls = {"n": 0}
        host = aerograb.NativeHost(state_dir=tempfile.mkdtemp(), launch=lambda: None, sleep=sleeps.append, wait_seconds=5)

        def alive():
            calls["n"] += 1
            return calls["n"] > 3
        host.alive = alive
        host.settings = lambda: {"autostart_from_browser": True}
        host.ensure_running()
        self.assertTrue(sleeps and max(sleeps) <= 0.05)


if __name__ == "__main__":
    unittest.main()
