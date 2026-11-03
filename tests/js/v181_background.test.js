// v1.8.1 detection fixes, run against the real background.js with stubbed browser APIs
const assert = require("assert");
const mem = {}, listeners = {};
const store = () => ({ get: async (k) => (typeof k === "string" ? { [k]: mem[k] } : Object.fromEntries(Object.entries(k).map(([a, d]) => [a, mem[a] ?? d]))), set: async (o) => Object.assign(mem, o), remove: async (k) => { delete mem[k]; } });
const ev = (n) => ({ addListener: (f) => (listeners[n] = f) });
let queried = 0, rules = [];
globalThis.chrome = {
  storage: { local: store(), session: store(), onChanged: ev("sc") },
  webRequest: { onHeadersReceived: ev("hdr") }, downloads: { onCreated: ev("dl") },
  cookies: { getAll: async () => [] }, action: { setBadgeText() {}, setBadgeBackgroundColor() {} },
  tabs: { get: async () => ({ url: "https://site.test/p", title: "T" }), onUpdated: ev("upd"), onRemoved: ev("rem"), sendMessage: async () => {},
          query: async (q) => { queried++; return q.url === "https://site.test/*" ? [{ id: 7, active: true }] : []; } },
  windows: { getLastFocused: async () => ({ focused: true }) },
  runtime: { onMessage: ev("msg"), onInstalled: ev("inst"), getURL: (p) => p, id: "abc" },
  contextMenus: { create() {}, onClicked: ev("ctx") },
  declarativeNetRequest: { updateSessionRules: async (o) => { rules.push(o); } },
};
const MASTER = "#EXTM3U\n#EXT-X-STREAM-INF:BANDWIDTH=900000,RESOLUTION=640x360\nlow.m3u8\n";
globalThis.fetch = async (url) => ({ ok: true, url, text: async () => MASTER });
require(require("path").join(__dirname, "../../extension/background.js"));
const msg = (m, tab = 7) => new Promise((res) => { const r = listeners.msg(m, { tab: { id: tab } }, res); if (r !== true) res("(no reply)"); });
(async () => {
  const H = (o, ct, extra = []) => listeners.hdr({ tabId: 7, statusCode: 200, responseHeaders: [{ name: "Content-Type", value: ct }, ...extra], ...o });
  H({ url: "https://cdn.test/chunked.mp4", type: "media" }, "video/mp4");                       // no Content-Length at all
  H({ url: "https://cdn.test/s/881", type: "media" }, "application/octet-stream");             // media element, no extension, generic type
  H({ url: "https://cdn.test/api/x", type: "xmlhttprequest" }, "application/octet-stream");    // a script's binary payload: not media
  H({ url: "https://site.test/page", type: "main_frame" }, "text/html; charset=utf-8");        // a normal page
  H({ url: "https://cdn.test/direct.mp4", type: "main_frame" }, "video/mp4", [{ name: "Content-Length", value: "9000000" }]);  // a video opened in the tab
  H({ tabId: -1, url: "https://cdn.test/worker.mp4", type: "xmlhttprequest", initiator: "https://site.test" }, "video/mp4", [{ name: "Content-Length", value: "9000000" }]);   // fetched by a worker
  H({ tabId: -1, url: "https://cdn.test/nowhere.mp4", type: "xmlhttprequest", initiator: "https://other.test" }, "video/mp4", [{ name: "Content-Length", value: "9000000" }]);
  await new Promise((r) => setTimeout(r, 150));
  const urls = (await msg({ cmd: "list" })).map((m) => m.url).sort();
  assert.deepStrictEqual(urls, ["https://cdn.test/chunked.mp4", "https://cdn.test/direct.mp4", "https://cdn.test/s/881", "https://cdn.test/worker.mp4"]);
  console.log("PASS unknown-size, octet-stream media, direct video tab and worker-fetched media are detected; pages and script payloads are not");
  // a master playlist is read with the page's Referer through a one-address session rule that is removed again
  H({ url: "https://cdn.test/m/master.m3u8", type: "xmlhttprequest", documentUrl: "https://site.test/p" }, "application/vnd.apple.mpegurl");
  await msg({ cmd: "variants", url: "https://cdn.test/m/master.m3u8" });
  await new Promise((r) => setTimeout(r, 50));
  const add = rules.find((r) => r.addRules);
  assert(add, "a referer rule was installed");
  const hdrs = add.addRules[0].action.requestHeaders;
  assert.strictEqual(hdrs.find((h) => h.header === "referer").value, "https://site.test/p");
  assert.strictEqual(hdrs.find((h) => h.header === "origin").value, "https://site.test");
  assert(new RegExp(add.addRules[0].condition.regexFilter).test("https://cdn.test/m/master.m3u8"));
  assert(rules.some((r) => r.removeRuleIds && r.removeRuleIds[0] === add.addRules[0].id), "and removed");
  console.log("PASS manifest fetch carries Referer/Origin via a temporary per-address rule");
})().catch((e) => { console.error(e); process.exit(1); });
