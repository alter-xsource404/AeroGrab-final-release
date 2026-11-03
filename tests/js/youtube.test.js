// The REAL background.js fed with a YouTube playback: ranged googlevideo pieces, SPA navigation, DRM manifests, push notifications.
const assert = require("assert"), path = require("path");
const mem = {}, L = {}, sent = [], badge = {};
const store = () => ({ get: async (k) => (typeof k === "string" ? { [k]: mem[k] } : Object.fromEntries(Object.entries(k).map(([a, d]) => [a, mem[a] ?? d]))), set: async (o) => Object.assign(mem, o), remove: async (k) => { delete mem[k]; } });
const ev = (n) => ({ addListener: (f) => (L[n] = f) });
globalThis.chrome = { storage: { local: store(), session: store(), onChanged: ev("sc") }, webRequest: { onHeadersReceived: ev("h"), onBeforeRequest: ev("b") }, downloads: { onCreated: ev("d") }, cookies: { getAll: async () => [] },
  action: { setBadgeText: (o) => (badge[o.tabId] = o.text), setBadgeBackgroundColor() {} }, tabs: { get: async () => ({ url: "https://www.youtube.com/watch?v=abc", title: "T" }), onUpdated: ev("u"), onRemoved: ev("r"), sendMessage: async (id, m) => { sent.push([id, m.cmd, m.item]); } },
  runtime: { onMessage: ev("m"), onInstalled: ev("i"), getURL: (p) => p }, contextMenus: { create() {}, onClicked: ev("c") } };
const MPD_DRM = `<MPD><Period><AdaptationSet contentType="video"><ContentProtection schemeIdUri="urn:uuid:edef8ba9-79d6-4ace-a3c8-27dcd51d21ed"/><Representation id="1" bandwidth="1" height="720"/></AdaptationSet></Period></MPD>`;
globalThis.fetch = async (u) => ({ ok: true, url: u, text: async () => (u.includes("drm") ? MPD_DRM : "#EXTM3U\n") });
require(path.join(__dirname, "../../extension/background.js"));
const msg = (m, tab = 5) => new Promise((res) => { const r = L.m(m, { tab: { id: tab } }, res); if (r !== true) res("(none)"); });
const wait = (ms) => new Promise((r) => setTimeout(r, ms));
const gv = (itag, mime, extra = "") => `https://rr1---sn-x.googlevideo.com/videoplayback?expire=${Math.floor(Date.now() / 1000) + 3600}&id=o-ID&itag=${itag}&mime=${encodeURIComponent(mime)}&clen=9000000&dur=212&sig=S${extra}`;

(async () => {
  try {
    // 1) ranged pieces of ~1.5 MB (under the old 2 MB floor), all from onBeforeRequest - before any response header exists
    for (let i = 0; i < 6; i++) L.b({ tabId: 5, url: gv(137, "video/mp4", `&range=${i * 1500000}-${(i + 1) * 1500000 - 1}&rn=${i}`), frameId: 0 });
    for (let i = 0; i < 3; i++) L.b({ tabId: 5, url: gv(140, "audio/mp4", `&range=${i * 500000}-${(i + 1) * 500000 - 1}`), frameId: 0 });
    L.b({ tabId: 5, url: gv(248, "video/webm", "&range=0-99"), frameId: 0 });
    let list = await msg({ cmd: "list" });
    assert.strictEqual(list.length, 3, "one entry per stream, not per piece: " + list.length);
    const v = list.find((x) => x.itag === 137);
    assert.deepStrictEqual([v.height, v.role, v.site, v.size, v.duration], [1080, "video", "youtube", 9000000, 212]);
    assert(v.audioUrl && /itag=140/.test(v.audioUrl), "mp4 video is paired with the m4a audio");
    assert(!/range=/.test(v.url));
    console.log("PASS YouTube: 10 ranged pieces collapse into 3 streams (1080p mp4 + 140 audio + 1080p webm), sizes/heights from the address, mp4 paired with m4a");
    // 2) the page is told at once
    assert(sent.some(([id, c, it]) => id === 5 && c === "media-found" && it.site === "youtube"), "media-found pushed");
    assert(sent.filter(([, c]) => c === "media-found").length <= 2, "notifications are coalesced");
    console.log("PASS content script is pushed 'media-found' immediately (" + sent.filter(([, c]) => c === "media-found").length + " messages for 10 requests)");
    // 3) same itag, refreshed address -> one entry, address updated
    L.b({ tabId: 5, url: gv(137, "video/mp4", "&range=0-9").replace("sig=S", "sig=NEW"), frameId: 0 });
    list = await msg({ cmd: "list" }); assert.strictEqual(list.length, 3); assert(list.find((x) => x.itag === 137).url.includes("sig=NEW"));
    console.log("PASS a refreshed address for the same itag updates the entry instead of adding one");
    // 4) SABR / live pieces carry no identity: not listed
    L.b({ tabId: 6, url: "https://rr1---sn-x.googlevideo.com/videoplayback?sabr=1&id=o-ID&c=WEB", frameId: 0 });
    L.h({ tabId: 6, statusCode: 200, type: "xmlhttprequest", url: "https://rr1---sn-x.googlevideo.com/videoplayback?sabr=1&id=o-ID", responseHeaders: [{ name: "Content-Type", value: "application/vnd.yt-ump" }] });
    await wait(30); assert.strictEqual((await msg({ cmd: "list" }, 6)).length, 0);
    console.log("PASS SABR requests (no stream identity) are not listed as bogus files");
    // 5) single-page navigation to another video clears the list; a fresh stream that already loaded survives
    L.u(5, { url: "https://www.youtube.com/watch?v=abc" }); await wait(1100);   // the old video's streams are now older than the 1 s grace period
    L.b({ tabId: 5, url: gv(18, "video/mp4"), frameId: 0 });                      // ...but a stream of the NEW video that loads right at the navigation must survive
    L.u(5, { url: "https://www.youtube.com/watch?v=xyz" }); await wait(20);
    const after = await msg({ cmd: "list" });
    assert.deepStrictEqual(after.map((x) => x.itag), [18]);
    console.log("PASS SPA navigation to a different video clears the previous video's streams (no stale list), a stream that loaded at that instant is kept");
    // 6) other categories
    L.h({ tabId: 7, statusCode: 200, type: "xmlhttprequest", url: "https://x.test/get?id=1", responseHeaders: [{ name: "Content-Type", value: "application/octet-stream" }, { name: "Content-Disposition", value: 'attachment; filename="setup.exe"' }, { name: "Content-Length", value: "5000000" }] });
    L.h({ tabId: 7, statusCode: 200, type: "image", url: "https://x.test/pic?i=2", responseHeaders: [{ name: "Content-Type", value: "image/jpeg" }, { name: "Content-Length", value: "300000" }] });
    L.h({ tabId: 7, statusCode: 200, type: "image", url: "https://x.test/pixel.gif", responseHeaders: [{ name: "Content-Type", value: "image/gif" }, { name: "Content-Length", value: "43" }] });
    L.h({ tabId: 7, statusCode: 200, type: "xmlhttprequest", url: "https://x.test/d/report", responseHeaders: [{ name: "Content-Type", value: "application/pdf" }, { name: "Content-Length", value: "800000" }] });
    await wait(20); const l7 = await msg({ cmd: "list" }, 7);
    assert.deepStrictEqual(l7.map((x) => x.category).sort(), ["app", "document", "image"]); assert.strictEqual(l7.find((x) => x.category === "app").filename, "setup.exe");
    console.log("PASS apps / documents / images detected from headers (tracking pixel ignored, original file name kept)");
    // 7) DRM manifest: flagged, and the hand-over is refused
    L.h({ tabId: 8, statusCode: 200, type: "xmlhttprequest", url: "https://cdn.test/drm/manifest.mpd", responseHeaders: [{ name: "Content-Type", value: "application/dash+xml" }] });
    await wait(40); const l8 = await msg({ cmd: "list" }, 8); assert.strictEqual(l8[0].drm, true);
    const r = await msg({ cmd: "send", job: { url: "https://cdn.test/drm/manifest.mpd", kind: "dash" } }, 8);
    assert.strictEqual(r.ok, false); assert(/DRM/.test(r.error));
    console.log("PASS Widevine-protected DASH manifest is flagged and AeroGrab refuses to hand it over");
    // 8) the popup (extension page, no sender.tab) can list a tab by id
    const lp = await new Promise((res) => { const rr = L.m({ cmd: "list", tabId: 7 }, {}, res); if (rr !== true) res("(none)"); }); assert.strictEqual(lp.length, 3);
    console.log("PASS popup can list the detected resources of a tab by id");
  } catch (e) { console.error("FAIL", e); process.exitCode = 1; }
  process.exit(process.exitCode || 0);
})();
