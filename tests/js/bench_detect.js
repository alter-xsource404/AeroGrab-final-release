// Detection benchmark:  node bench_detect.js [path/to/extension_folder]
// Feeds the REAL background.js of that folder with (a) a YouTube playback as the browser reports it, (b) a plain 20 MB MP4, using identical stubbed browser APIs.
// Reports: was the video detected at all; how many awaited browser-API round trips (storage / tabs) happen BEFORE the page is told; wall-clock from the event to the push.
// The stubs answer instantly, so times are pure extension-logic time. Real chrome.storage / tabs calls add their own latency per round trip - that is why the round trips are counted.
const path = require("path");
const dir = path.resolve(process.argv[2] || path.join(__dirname, "../../extension"));
const mem = {}, L = {}; let apiCalls = 0, firstPushAt = null, callsAtPush = 0;
const store = () => ({ get: async (k) => { apiCalls++; return typeof k === "string" ? { [k]: mem[k] } : Object.fromEntries(Object.entries(k).map(([a, d]) => [a, mem[a] ?? d])); }, set: async (o) => { apiCalls++; Object.assign(mem, o); }, remove: async (k) => { delete mem[k]; } });
const ev = (n) => ({ addListener: (f) => (L[n] = f) });
globalThis.chrome = { storage: { local: store(), session: store(), onChanged: ev("sc") }, webRequest: { onHeadersReceived: ev("h"), onBeforeRequest: ev("b") }, downloads: { onCreated: ev("d") }, cookies: { getAll: async () => [] },
  action: { setBadgeText() {}, setBadgeBackgroundColor() {} },
  tabs: { get: async () => { apiCalls++; return { url: "https://www.youtube.com/watch?v=abc", title: "t" }; }, onUpdated: ev("u"), onRemoved: ev("r"),
          sendMessage: async (id, m) => { if (firstPushAt === null && /media-(updated|found)/.test(m.cmd)) { firstPushAt = performance.now(); callsAtPush = apiCalls; } } },
  runtime: { onMessage: ev("m"), onInstalled: ev("i"), getURL: (p) => p }, contextMenus: { create() {}, onClicked: ev("c") } };
globalThis.fetch = async () => ({ ok: true, url: "", text: async () => "" });
require(path.join(dir, "background.js"));
const msg = (m) => new Promise((res) => { const r = L.m(m, { tab: { id: 1 } }, res); if (r !== true) res([]); });
const gv = (itag, mime, r) => `https://rr1---sn-x.googlevideo.com/videoplayback?expire=2000000000&id=o-ID&itag=${itag}&mime=${encodeURIComponent(mime)}&clen=50000000&dur=212&sig=S&range=${r}-${r + 1500000}`;
const H = (n, v) => ({ name: n, value: String(v) });
const wait = (ms) => new Promise((r) => setTimeout(r, ms));
(async () => {
  console.log(`[${dir}]`);
  // (a) YouTube: ~1.5 MB ranged pieces, the way YouTube's player requests them. Two variants of what the browser reports:
  //     A: responses carry Content-Range (total 50 MB)   B: no Content-Range, Content-Length = the piece (what a &range= query parameter produces)
  for (const [tab, label, withRange] of [[1, "A (Content-Range present)", true], [3, "B (piece size only)       ", false]]) {
    firstPushAt = null; apiCalls = 0; callsAtPush = 0;
    const t0 = performance.now();
    for (let i = 0; i < 8; i++) {
      const u = gv(137, "video/mp4", i * 1500000);
      L.b && L.b({ tabId: tab, url: u, frameId: 0, type: "xmlhttprequest" });
      L.h({ tabId: tab, statusCode: 206, type: "xmlhttprequest", url: u, frameId: 0, responseHeaders: [H("Content-Type", "video/mp4"), H("Content-Length", 1500001), ...(withRange ? [H("Content-Range", "bytes 0-1500000/50000000")] : [])] });
    }
    await wait(60);
    const yt = (await new Promise((res) => { const r = L.m({ cmd: "list" }, { tab: { id: tab } }, res); if (r !== true) res([]); }));
    console.log(`  YouTube 1080p, 8 ranged pieces, variant ${label}: entries listed = ${yt.length}` + (yt.length ? ` (${yt[0].height ? yt[0].height + "p, one per stream" : "each is a piece of the same stream, none is a whole file"})` : "  <- NOT DETECTED") +
      (firstPushAt !== null ? `; page told after ${callsAtPush} awaited storage/tabs round trips` : "; page never told"));
  }
  // (b) plain MP4
  firstPushAt = null; apiCalls = 0; callsAtPush = 0;
  const t1 = performance.now();
  L.h({ tabId: 2, statusCode: 200, type: "media", url: "https://cdn.example/clip.mp4", frameId: 0, responseHeaders: [H("Content-Type", "video/mp4"), H("Content-Length", 20e6)] });
  await wait(60);
  console.log(`  plain 20 MB MP4 (response headers arrive):           ` + (firstPushAt !== null ? `page told ${(firstPushAt - t1).toFixed(2)} ms after the headers, after ${callsAtPush} awaited storage/tabs round trips` : "page never told"));
  process.exit(0);
})();
