// content.js in a hand-made fake DOM (no browser or jsdom is available in CI here): the script loads, a play event + the YouTube data from page_hook.js
// produce the capture tip and a quality list, and the Download action sends the right job. This is a smoke test of the logic, NOT a browser test.
const assert = require("assert"), fs = require("fs"), path = require("path"), vm = require("vm");
const ext = (f) => fs.readFileSync(path.join(__dirname, "../../extension", f), "utf8");

class El {
  constructor(tag) { this.tagName = String(tag).toUpperCase(); this.children = []; this.style = {}; this.className = ""; this._l = {}; this.isConnected = true; this.parentElement = null; this.dataset = {}; this.offsetWidth = 150; this.offsetHeight = 30; }
  append(...k) { for (const x of k) { if (x && typeof x === "object") x.parentElement = this; this.children.push(x); } }
  replaceChildren(...k) { this.children = []; this.append(...k); }
  remove() { this.isConnected = false; }
  get firstChild() { return this.children[0]; }
  get classList() { const s = this; const t = () => s.className.split(/\s+/).filter(Boolean); const w = (a) => { s.className = a.join(" "); };
    return { contains: (c) => t().includes(c), add: (c) => { const a = t(); if (!a.includes(c)) { a.push(c); w(a); } }, remove: (c) => w(t().filter((x) => x !== c)), toggle: (c, f) => { const a = t().filter((x) => x !== c); if (f === undefined ? !t().includes(c) : f) a.push(c); w(a); } }; }
  addEventListener(t, f) { (this._l[t] ||= []).push(f); }
  removeEventListener() {}
  attachShadow() { return (this.shadow = new El("shadow")); }
  querySelector() { return null; } querySelectorAll() { return []; } getElementsByTagName() { return []; }
  closest() { return null; } getAttribute() { return null; } setPointerCapture() {}
  getBoundingClientRect() { return { left: 0, top: 0, right: 640, bottom: 360, width: 640, height: 360 }; }
}
const video = new El("video");
Object.assign(video, { paused: true, ended: false, currentSrc: "blob:https://www.youtube.com/abc", src: "", duration: 212 });
const WL = {}, DL = {}, sent = [];
const docEl = new El("html");
const doc = { documentElement: docEl, createElement: (t) => new El(t), querySelectorAll: (s) => (s === "video" ? [video] : []), querySelector: () => null, addEventListener: (t, f) => (DL[t] ||= []).push(f), title: "Some Title - YouTube" };
const store = { overlay: true, ovCompact: false, ovOff: null, toast: true };
const sandbox = {
  document: doc, location: { href: "https://www.youtube.com/watch?v=abcDEF12345", hostname: "www.youtube.com", pathname: "/watch", search: "?v=abcDEF12345" },
  navigator: { userAgent: "UA" }, innerWidth: 1280, innerHeight: 720, performance, URL, console, setTimeout, clearTimeout, setInterval, clearInterval, Promise, CSSStyleSheet: undefined,
  MutationObserver: class { observe() {} }, ResizeObserver: class { observe() {} disconnect() {} }, requestAnimationFrame: (f) => setTimeout(f, 1), queueMicrotask,
  addEventListener: (t, f) => (WL[t] ||= []).push(f), postMessage() {},
  chrome: { runtime: { sendMessage: async (m) => { sent.push(m); if (m.cmd === "cfg") return { video_button: true }; if (m.cmd === "list") return []; if (m.cmd === "send") return { ok: true }; if (m.cmd === "formats") return { ok: false, error: "yt-dlp is not installed", missing: true }; return undefined; }, onMessage: { addListener: (f) => (sandbox._bg = f) } },
    storage: { local: { get: async () => ({ ...store }), set: async () => {} }, onChanged: { addListener() {} } } },
};
sandbox.window = sandbox; sandbox.globalThis = sandbox; sandbox.self = sandbox;
vm.createContext(sandbox);
for (const f of ["names.js", "classify.js", "adapters.js", "content.js"]) vm.runInContext(ext(f), sandbox, { filename: f });
const WIN = vm.runInContext("window", sandbox);
const fire = (target, type, e = {}) => { for (const f of (target[type] || [])) f({ type, isTrusted: true, target: video, composedPath: () => [], ...e }); };
const wait = (ms) => new Promise((r) => setTimeout(r, ms));
const overlayEl = () => { const root = docEl.children[0].shadow; return root.children.find((c) => /\bov\b/.test(c.className)); };

(async () => {
  try {
    await wait(30);
    assert(overlayEl(), "an overlay exists for the <video> after load");
    console.log("PASS content.js loads in a minimal DOM and attaches a button to the video");

    // the user presses Play; the page hook reports YouTube's quality ladder
    video.paused = false; fire(WL, "play", { target: video });
    sandbox.window.postMessage = () => {};
    for (const f of WL.message || []) f({ source: WIN, data: { source: "opendm-hook", type: "yt-player", data: { id: "abcDEF12345", title: "The Real Video Title", author: "Chan", lengthSeconds: 212, status: "OK", formats: [
      { itag: 137, mime: 'video/mp4; codecs="avc1"', height: 1080, fps: 30, size: 50e6, bitrate: 4e6 }, { itag: 136, mime: 'video/mp4; codecs="avc1"', height: 720, fps: 30, size: 30e6, bitrate: 2e6 },
      { itag: 248, mime: 'video/webm; codecs="vp9"', height: 1080, fps: 30, size: 40e6, bitrate: 3e6 }, { itag: 140, mime: 'audio/mp4; codecs="mp4a"', audio: true, size: 3e6, bitrate: 128e3 } ] } } });
    await wait(200);
    const ov = overlayEl();
    assert(/\btipon\b/.test(ov.className), "capture tip is visible after Play");
    assert(/up to 1080p/.test(ov.children[1].firstChild.textContent) && /The Real Video Title/.test(ov.children[1].firstChild.textContent), ov.children[1].firstChild.textContent);
    console.log("PASS Play + player data -> capture tip within 200 ms:", JSON.stringify(ov.children[1].firstChild.textContent));

    // one-click Download in the tip: best quality, handed to OpenDM through the yt-dlp path (it merges video + audio)
    sent.length = 0; ov.children[1].children[1].onclick(); await wait(20);
    const job = sent.find((m) => m.cmd === "send").job;
    assert.deepStrictEqual([job.url, job.kind, job.quality], ["https://www.youtube.com/watch?v=abcDEF12345", "ytdlp", 1080]);
    assert(/The Real Video Title 1080p/.test(job.filename), job.filename);
    assert.deepStrictEqual([job.meta.site, job.meta.title, job.meta.height, job.meta.duration, job.meta.ext], ["YouTube", "The Real Video Title", 1080, 212, "mp4"]);
    console.log("PASS tip's Download sends {watch URL, ytdlp, 1080p, real title, meta} to OpenDM");

    // the tip is announced once per video, not again for the same resource
    ov.className = ov.className.replace("tipon", ""); for (const f of WL.message) f({ source: WIN, data: { source: "opendm-hook", type: "yt-player", data: { id: "abcDEF12345", title: "The Real Video Title", status: "OK", formats: [{ itag: 137, mime: "video/mp4", height: 1080, size: 1 }] } } });
    await wait(150); assert(!/\btipon\b/.test(overlayEl().className), "no duplicate notification");
    console.log("PASS no duplicate capture notification for the same video");

    // DRM-flagged video: no rows, no tip
    sandbox.location.href = "https://www.youtube.com/watch?v=drmDRM12345";
    for (const f of WL.message) f({ source: WIN, data: { source: "opendm-hook", type: "yt-player", data: { id: "drmDRM12345", title: "Protected", status: "OK", drm: true, formats: [{ itag: 137, mime: "video/mp4", height: 1080, size: 1 }] } } });
    await wait(150); assert(!/\btipon\b/.test(overlayEl().className));
    console.log("PASS DRM-protected video: nothing is offered");
  } catch (e) { console.error("FAIL", e); process.exitCode = 1; }
  process.exit(process.exitCode || 0);
})();
