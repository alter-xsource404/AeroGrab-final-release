#!/usr/bin/env python3
"""Capture-pipeline latency benchmark (native host -> OpenDM's local server -> the GUI hand-over callback).

    python tools/bench_capture.py [path/to/OpenDM_folder]      # default: this checkout

Runs the REAL code: opendm.start_api() (HTTP server), opendm.NativeHost.serve() (the program the browser starts) over real OS pipes, with the
native-messaging framing the browser uses. The GUI is replaced by a callback that records the time the job arrived (where the Tk thread would
pick it up). It therefore measures everything between "the extension wrote the message" and "OpenDM has the job", on loopback.

It does NOT measure: browser/extension JavaScript, Tk dialog construction, or process start-up. Those are reported separately (see CHANGELOG).
Run it against two folders to compare versions:  python tools/bench_capture.py /path/old  &&  python tools/bench_capture.py /path/new
"""
import importlib.util, json, os, socket, statistics, struct, sys, tempfile, threading, time

root = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), ".."))
spec = importlib.util.spec_from_file_location("opendm_bench", os.path.join(root, "opendm.py"))
opendm = importlib.util.module_from_spec(spec)
sys.modules["opendm_bench"] = opendm
spec.loader.exec_module(opendm)


def free_port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


class Mgr:
    settings = {}
    speed_seen = 0.0
    def add(self, *a, **k): pass


def frame(o):
    d = json.dumps(o).encode()
    return struct.pack("=I", len(d)) + d


def read_frame(f):
    raw = f.read(4)
    (n,) = struct.unpack("=I", raw)
    return json.loads(f.read(n))


def pct(v, p):
    v = sorted(v); return v[min(len(v) - 1, int(len(v) * p / 100))]


def main():
    state = tempfile.mkdtemp(); port = free_port()
    arrived = {}
    def confirm(job):
        arrived[job["url"]] = time.perf_counter()
    token = opendm.get_token(state)
    srv = opendm.start_api(Mgr(), lambda: ("/tmp", 8), port=port, token=token, state_dir=state, confirm=confirm)
    host = opendm.NativeHost(state_dir=state, launch=lambda: None, sleep=lambda s: None)
    in_r, in_w = os.pipe(); out_r, out_w = os.pipe()
    t = threading.Thread(target=host.serve, args=([ "--native-host" ],), kwargs=dict(stdin=os.fdopen(in_r, "rb", 0), stdout=os.fdopen(out_w, "wb", 0)), daemon=True)
    t.start()
    to_host, from_host = os.fdopen(in_w, "wb", 0), os.fdopen(out_r, "rb", 0)

    def add(i, tag="a"):
        url = f"https://cdn.example/{tag}/{i}.mp4"
        t0 = time.perf_counter()
        to_host.write(frame({"cmd": "add", "id": i, "job": {"url": url, "filename": f"clip {i}.mp4", "ts": int(time.time() * 1000), "meta": {"site": "Bench", "height": 1080}}}))
        r = read_frame(from_host); t1 = time.perf_counter()
        assert r.get("ok"), r
        return (arrived[url] - t0) * 1000, (t1 - t0) * 1000

    for i in range(20): add(i, "warm")                      # connection set-up, imports, caches
    N = 300
    rows = [add(i) for i in range(N)]
    to_srv = [r[0] for r in rows]; rt = [r[1] for r in rows]
    print(f"[{root}]  version {opendm.__version__}")
    print(f"  sequential 'add' x{N}:  message written -> job reaches OpenDM   median {statistics.median(to_srv):.2f} ms   p95 {pct(to_srv, 95):.2f} ms   max {max(to_srv):.2f} ms")
    print(f"                          message written -> browser gets reply   median {statistics.median(rt):.2f} ms   p95 {pct(rt, 95):.2f} ms")

    # burst: 20 messages written back-to-back
    t0 = time.perf_counter()
    urls = []
    for i in range(20):
        urls.append(f"https://cdn.example/burst/{i}.mp4")
        to_host.write(frame({"cmd": "add", "id": 1000 + i, "job": {"url": urls[-1], "ts": int(time.time() * 1000)}}))
    for _ in range(20): read_frame(from_host)
    print(f"  burst of 20 'add':      all 20 acknowledged after {(time.perf_counter() - t0) * 1000:.1f} ms; last job reached OpenDM {(max(arrived[u] for u in urls) - t0) * 1000:.1f} ms after the first write")

    # two identical /formats lookups at once (look-ahead + menu): how many extractions run?
    runs = []
    def fake_formats(url, *a, **k):
        runs.append(url); time.sleep(0.4)
        return {"title": "x", "fallback": "x", "duration": 1, "formats": [{"height": 720, "ext": "mp4", "size": 1, "approx": True, "fps": 30}], "audio": None}
    opendm.ytdlp_formats = fake_formats; opendm.media_site = lambda u: True
    out = []
    def fcall(i):
        to_host_local = None
    results = []
    def post(i):
        import urllib.request
        req = urllib.request.Request(f"http://127.0.0.1:{port}/formats", method="POST", data=json.dumps({"url": "https://www.youtube.com/watch?v=BENCH"}).encode(),
                                     headers={"X-OpenDM-Token": token, "Content-Type": "application/json"})
        t = time.perf_counter()
        with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req, timeout=10) as r: results.append((json.loads(r.read())["ok"], time.perf_counter() - t))
    ths = [threading.Thread(target=post, args=(i,)) for i in range(2)]
    t0 = time.perf_counter(); [x.start() for x in ths]; [x.join() for x in ths]
    print(f"  2 simultaneous /formats for one video (each lookup takes 400 ms here): extractions started = {len(runs)}, both answered after {(time.perf_counter() - t0) * 1000:.0f} ms")
    srv.shutdown()


main()
