// AeroGrab browser integration (Chrome / Edge / Brave / Firefox, Manifest V3) - v1.8: modular detection (classify.js + adapters.js), early YouTube detection, instant push notifications, in-memory tab state; v1.7: one persistent native-messaging connection; v1.6: capture rules from AeroGrab's Configuration; v1.5: audio/video stream pairing
const api = globalThis.browser ?? globalThis.chrome;
// Shared modules. Chrome/Edge/Brave service worker: importScripts. Firefox: listed in manifest "background.scripts" (already loaded). Node tests: require.
if (typeof importScripts === "function") { try { importScripts("names.js", "classify.js", "adapters.js"); } catch (e) { console.warn("AeroGrab: could not load detection modules", e); } }
else if (typeof require === "function" && !globalThis.AeroGrabClassify) { require("./names.js"); require("./classify.js"); require("./adapters.js"); }
const CL = globalThis.AeroGrabClassify, AD = globalThis.AeroGrabAdapters;
const DEFAULTS = { port: 6800, token: "", intercept: true, minSizeKB: 0 };

const getCfg = async () => ({ ...DEFAULTS, ...(await api.storage.local.get(DEFAULTS)) });

async function cookieHeader(url) {
  try {
    const cs = await api.cookies.getAll({ url });
    return cs.map((c) => `${c.name}=${c.value}`).join("; ");
  } catch { return ""; }
}

// ---- talking to AeroGrab -------------------------------------------------------------------
// Preferred: the native-messaging host that AeroGrab registers with the browser by itself. It needs no port and no
// pairing token, only trusts this extension's ID, and starts AeroGrab if it isn't running.
// Fallback: the local server on 127.0.0.1 with a pairing token pasted into the options page.
const NATIVE_HOST = "org.aerograb.nativehost";
const withTimeout = (p, ms) => Promise.race([p, new Promise((_, rej) => setTimeout(() => rej(new Error("timed out")), ms))]);
// v1.7: sendNativeMessage starts a NEW host process for every message (for a packaged AeroGrab that means unpacking and starting the whole
// program each time: seconds). connectNative keeps one host process alive; messages carry an id, the host echoes it, so calls can overlap
// (a slow "formats" lookup never blocks a download hand-over). Falls back to sendNativeMessage where connectNative doesn't exist.
let nPort = null, nSeq = 0;
const nPending = new Map();
function nativePort() {
  if (nPort) return nPort;
  const p = api.runtime.connectNative(NATIVE_HOST);
  p.onMessage.addListener((m) => {
    const w = m && nPending.get(m.id);
    if (!w) return;
    nPending.delete(m.id); clearTimeout(w.t);
    const { id, ...reply } = m; w.res(reply);
  });
  p.onDisconnect.addListener(() => {
    const err = new Error((api.runtime.lastError && api.runtime.lastError.message) || "Native host has exited.");
    if (nPort === p) nPort = null;
    for (const [id, w] of nPending) { clearTimeout(w.t); w.rej(err); nPending.delete(id); }
  });
  return (nPort = p);
}
function viaPort(msg, ms) {
  return new Promise((res, rej) => {
    const id = ++nSeq, t = setTimeout(() => { nPending.delete(id); rej(new Error("timed out")); }, ms);
    nPending.set(id, { res, rej, t });
    const post = () => nativePort().postMessage({ ...msg, id });
    try { post(); } catch { nPort = null; try { post(); } catch (e) { nPending.delete(id); clearTimeout(t); rej(e); } }   // a stale port: reconnect once
  });
}
const nativeCall = (msg, ms = 30000) =>   // 30 s: AeroGrab may need time to start
  typeof api.runtime.connectNative === "function" ? viaPort(msg, ms) : withTimeout(Promise.resolve(api.runtime.sendNativeMessage(NATIVE_HOST, msg)), ms);

// Latency of the last hand-overs (browser -> AeroGrab's reply), kept for the popup and for measuring: nothing here is estimated.
const perf = { sends: [], formats: [] };
const sendFlight = new Map();   // url|quality|kind -> promise: a double click while the first hand-over is still running is the same download
async function sendToAeroGrab(job) {
  if (job.drm || drmUrls.has(job.url)) throw new Error("This stream is DRM-protected. AeroGrab does not download protected content.");
  const key = [job.url, job.quality || 0, job.kind || "", job.audioUrl || ""].join("|");
  const running = sendFlight.get(key);
  if (running) return running;
  const p = sendNow(job).finally(() => sendFlight.delete(key));
  sendFlight.set(key, p);
  return p;
}
async function sendNow(job) {
  const t0 = performance.now(), rec = { t: Date.now(), kind: job.kind || "file", ok: false, ms: 0 };
  try {
    const full = { ...job, ts: Date.now(), cookie: await cookieHeader(job.url), userAgent: navigator.userAgent };
    let reply = null, nativeError = "";
    try { reply = await nativeCall({ cmd: "add", job: full }); } catch (e) { nativeError = e?.message || String(e); }  // host not registered / not allowed
    if (reply) {
      if (reply.ok) { rec.ok = true; return; }
      throw new Error(reply.error || "AeroGrab refused the download");  // AeroGrab answered: don't retry another way
    }
    const cfg = await getCfg();
    if (!cfg.token) throw new Error("not paired: AeroGrab's browser integration isn't registered yet" + (nativeError ? ` (${nativeError})` : ""));
    const r = await fetch(`http://127.0.0.1:${cfg.port}/add`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-AeroGrab-Token": cfg.token },
      body: JSON.stringify(full),
    });
    if (!r.ok) throw new Error("AeroGrab replied " + r.status);
    rec.ok = true;
  } finally {
    rec.ms = Math.round(performance.now() - t0);
    perf.sends.push(rec); if (perf.sends.length > 20) perf.sends.shift();
  }
}

async function connectionStatus() {
  let nativeError = "";
  try { const r = await nativeCall({ cmd: "ping" }); if (r?.ok) return { mode: "native", running: !!r.running, version: r.version, autostart: r.autostart !== false }; }
  catch (e) { nativeError = e?.message || String(e); }
  const cfg = await getCfg();
  if (cfg.token) {
    try {
      const r = await fetch(`http://127.0.0.1:${cfg.port}/ping`, { headers: { "X-AeroGrab-Token": cfg.token } });
      return r.ok ? { mode: "manual", running: true } : { mode: "none", error: r.status === 401 ? "Wrong pairing token" : "AeroGrab replied " + r.status };
    } catch { /* not running */ }
  }
  return { mode: "none", error: nativeError || "AeroGrab's browser integration isn't registered yet" };
}

// ---------------- Which downloads does AeroGrab take over? (rules live in AeroGrab > Options > Configuration) ----------------
// AeroGrab hands its rules over on request (native host "config", or POST /config with the pairing token). The last answer is kept, so the rules
// still apply while AeroGrab isn't running. Until the first answer these built-in defaults apply: images and web files are never captured.
const DEFAULT_CAP = {
  intercept: true, capture_types: [], capture_unknown: true, exclude_sites: [], min_size_kb: 0, key_prevent: "alt", key_force: "none", browsers: {},
  skip_types: "jpg jpeg png gif webp bmp svg ico avif heic tif tiff css js mjs map html htm json xml woff woff2 ttf otf".split(" "),
  ctx_link: true, ctx_media: true, video_button: true,
};
let capCache = { t: 0, cfg: null };

async function buildMenus(cap) {
  try { await api.contextMenus.removeAll?.(); } catch {}
  if (cap.ctx_link !== false) api.contextMenus.create({ id: "dl-link", title: "Download link with AeroGrab", contexts: ["link"] });
  if (cap.ctx_media !== false) api.contextMenus.create({ id: "dl-media", title: "Download media with AeroGrab", contexts: ["video", "audio", "image"] });
}

async function getCapture(maxAge = 60e3) {
  if (capCache.cfg && Date.now() - capCache.t < maxAge) return capCache.cfg;
  let fresh = null;
  try { const r = await nativeCall({ cmd: "config" }); if (r?.ok && r.config) fresh = r.config; } catch {}
  if (!fresh) {
    try {
      const c = await getCfg();
      if (c.token) {
        const r = await fetch(`http://127.0.0.1:${c.port}/config`, { method: "POST", headers: { "Content-Type": "application/json", "X-AeroGrab-Token": c.token }, body: "{}" });
        if (r.ok) fresh = await r.json();
      }
    } catch {}
  }
  const stored = (await api.storage.local.get({ capture: null })).capture;
  if (fresh) {
    if (JSON.stringify(fresh) !== JSON.stringify(stored)) await api.storage.local.set({ capture: fresh });
    if (!stored || stored.ctx_link !== fresh.ctx_link || stored.ctx_media !== fresh.ctx_media) buildMenus({ ...DEFAULT_CAP, ...fresh });
  }
  const cfg = { ...DEFAULT_CAP, ...(fresh || stored || {}) };
  capCache = { t: Date.now(), cfg };
  return cfg;
}

const extOf = (s) => { const m = /\.([a-z0-9]{1,10})$/i.exec(String(s || "").split(/[?#]/)[0]); return m ? m[1].toLowerCase() : ""; };
const hostMatch = (host, pats) => (pats || []).some((p) => {
  const q = p.replace(/^\*\./, "");
  return host === q || host.endsWith("." + q) || (p.includes("*") && new RegExp("^" + p.replace(/[.+?^${}()|[\]\\]/g, "\\$&").replace(/\*/g, ".*") + "$").test(host));
});
// Same rules as AeroGrab's capture_decision(): excluded site -> no; skip list -> no; capture list -> yes; anything else -> "unknown types" switch.
function captureAllowed(cap, url, filename, forced) {
  let u; try { u = new URL(url); } catch { return false; }
  if (!forced && hostMatch(u.hostname.toLowerCase(), cap.exclude_sites)) return false;
  if (forced) return true;
  const ext = extOf(filename) || extOf(u.pathname);
  if ((cap.skip_types || []).includes(ext)) return false;
  if ((cap.capture_types || []).includes(ext)) return true;
  return cap.capture_unknown !== false;
}
async function browserName() {
  const ua = navigator.userAgent;
  if (/Firefox\//.test(ua)) return "firefox";
  if (/Edg\//.test(ua)) return "edge";
  if (/OPR\/|Opera|Vivaldi/.test(ua)) return "other";
  try { if (navigator.brave && (await navigator.brave.isBrave())) return "brave"; } catch {}
  return "chrome";
}

// Take over browser downloads - but ONLY ones the user is starting right now.
// FIX (phantom downloads): the old code grabbed every download the browser reported (old/resumed items, page-script downloads,
// downloads from a window the user isn't using). Now a download must be fresh, in the focused window, follow a real user
// gesture (or a typed address), not be a duplicate, and not be part of a burst. Anything else is left to the browser, untouched.
const GESTURE_MS = 20e3, FRESH_MS = 15e3, DEDUPE_MS = 60e3, BURST_N = 3, BURST_MS = 10e3;
let lastGesture = 0, lastMods = {};
const recentUrls = new Map();   // url -> time AeroGrab was last offered it
const burstTimes = [];

async function windowFocused() {
  try { const w = await api.windows?.getLastFocused?.(); return !w || w.focused !== false; } catch { return true; }
}

async function shouldCapture(item, url) {
  const now = Date.now();
  if (item.byExtensionId) return false;                                   // started by another extension
  if (item.state && item.state !== "in_progress") return false;           // finished / interrupted old item
  const started = Date.parse(item.startTime || "");
  if (started && now - started > FRESH_MS) return false;                 // restored or old item, not a new click
  for (const [u, t] of recentUrls) if (now - t > DEDUPE_MS) recentUrls.delete(u);
  if (recentUrls.has(url)) return false;                                  // already offered a moment ago
  if (!(await windowFocused())) return false;                             // user is not in the browser
  const typed = !item.referrer;                                           // address bar / bookmark: no page involved
  if (!typed && now - lastGesture > GESTURE_MS) return false;             // page script started it without the user
  while (burstTimes.length && now - burstTimes[0] > BURST_MS) burstTimes.shift();
  if (burstTimes.length >= BURST_N) return false;                         // a page spraying downloads
  burstTimes.push(now); recentUrls.set(url, now);
  return true;
}

api.downloads.onCreated.addListener(async (item) => {
  const cfg = await getCfg();
  const url = item.finalUrl || item.url;
  if (!cfg.intercept || !/^https?:/i.test(url)) return;
  const cap = await getCapture();
  if (!cap.intercept) return;                                             // "Capture downloads from browsers" is off in AeroGrab
  if (cap.browsers && cap.browsers[await browserName()] === false) return; // this browser is switched off in AeroGrab
  const fresh = Date.now() - lastGesture < GESTURE_MS, held = (k) => fresh && k && k !== "none" && !!lastMods[k];
  if (held(cap.key_prevent)) return;                                      // the "let the browser do it" key was held
  if (!captureAllowed(cap, url, item.filename, held(cap.key_force))) return;   // file type / excluded site
  const minKB = Math.max(cfg.minSizeKB || 0, cap.min_size_kb || 0);
  if (minKB && item.fileSize > 0 && item.fileSize < minKB * 1024) return;
  if (!(await shouldCapture(item, url))) return;                          // not the user's download: leave it to the browser
  try { await api.downloads.pause(item.id); } catch {}  // keep the browser's copy from finishing while AeroGrab (maybe starting up) takes over
  try {
    const name = item.filename ? item.filename.split(/[\\/]/).pop() : "";
    await sendToAeroGrab({ url, referer: item.referrer || "", filename: name });
    await api.downloads.cancel(item.id);
    await api.downloads.erase({ id: item.id });
  } catch (e) {
    console.warn("AeroGrab unavailable, browser will download it:", e.message);
    try { await api.downloads.resume(item.id); } catch {}  // AeroGrab couldn't take it: let the browser carry on
  }
});

// Right-click menus (which ones exist is decided in AeroGrab's Configuration)
api.runtime.onInstalled.addListener(() => buildMenus(DEFAULT_CAP));
api.runtime.onStartup?.addListener(() => getCapture(0).catch(() => {}));   // also opens the native connection ahead of the first capture
getCapture(0).catch(() => {});   // service worker (re)started: warm the host process and the capture rules now, not at the first download
api.contextMenus.onClicked.addListener(async (info, tab) => {
  const url = info.linkUrl || info.srcUrl;
  if (!url) return;
  try { await sendToAeroGrab({ url, referer: info.pageUrl || tab?.url || "" }); }
  catch (e) { console.warn(e.message); api.tabs.create({ url: api.runtime.getURL("options.html") }); }
});

// ---------------- Detection: what did this tab load that can be downloaded? ----------------
// v1.8: classification lives in classify.js, per-site knowledge in adapters.js. Tab state is kept IN MEMORY and written to storage.session a moment
// later (write-behind), so a detection is announced to the page the instant it happens instead of after a storage round trip.
const sess = api.storage.session ?? api.storage.local;
const hdr = (d, n) => d.responseHeaders?.find((h) => h.name.toLowerCase() === n)?.value ?? "";
const kindOf = (url) => (/\.m3u8(\?|#|$)/i.test(url) ? "hls" : /\.mpd(\?|#|$)/i.test(url) ? "dash" : "file");
const CAPS = { media: 40, image: 20, other: 20 };   // per-tab list limits per class, so a page full of thumbnails can't push a video out
const classOf = (m) => (m.category === "image" ? "image" : m.category === "video" || m.category === "audio" || m.category === "stream" ? "media" : "other");
const flags = { images: true, push: true };
api.storage.local.get({ detectImages: true, toast: true }).then((c) => { flags.images = c.detectImages !== false; flags.push = c.toast !== false; }).catch(() => {});
api.storage.onChanged?.addListener((ch) => { if (ch.detectImages) flags.images = ch.detectImages.newValue !== false; if (ch.toast) flags.push = ch.toast.newValue !== false; });

// FIX (no sound): DASH sites (Facebook, Instagram, Reels, YouTube) serve picture and sound as two separate files.
// Fallback role detection for sites without an adapter:  1) content-type audio/*   2) ?mime=audio/..   3) ?efg=<base64 json>.vencode_tag
const b64json = (s) => { try { return JSON.parse(atob(s.replace(/-/g, "+").replace(/_/g, "/"))); } catch { return null; } };
function roleOf(url, ct) {
  if (/^audio\//i.test(ct)) return "audio";
  try {
    const u = new URL(url), mime = u.searchParams.get("mime"), efg = u.searchParams.get("efg");
    if (mime) return /^audio/i.test(mime) ? "audio" : "video";
    if (efg) { const tag = String(b64json(efg)?.vencode_tag || ""); if (tag) return /audio|heaac|aac|opus/i.test(tag) ? "audio" : "video"; }
  } catch {}
  return /^video\//i.test(ct) ? "video" : "unknown";
}

// Attach to every video the audio that belongs to it. YouTube: same container family, best bitrate. Sites that tag a group (Reddit id, ...): same group.
// Everything else: closest in time within the same frame.
function withPairs(list) {
  const audios = list.filter((m) => m.kind === "file" && m.role === "audio" && !m.expired);
  if (!audios.length) return list;
  return list.map((m) => {
    if (m.kind !== "file" || m.role !== "video") return m;
    let best = null;
    if (m.site === "youtube") {
      const want = m.ext === "webm" ? "webm" : "m4a";
      best = audios.filter((a) => a.site === "youtube").sort((x, y) => (y.ext === want) - (x.ext === want) || (x.itag === 140 ? -1 : 0) - (y.itag === 140 ? -1 : 0) || (y.kbps || 0) - (x.kbps || 0))[0];
    } else {
      const pool = m.group && audios.some((a) => a.group === m.group) ? audios.filter((a) => a.group === m.group) : audios;
      best = pool.map((a) => ({ a, d: Math.abs((a.t || 0) - (m.t || 0)) + (a.frameId === m.frameId ? 0 : 5000) })).sort((x, y) => x.d - y.d)[0]?.a;
    }
    return best ? { ...m, audioUrl: best.url } : m;
  });
}

// ---- per-tab state (memory first)
const TS = new Map();
function tabState(tabId) {
  let s = TS.get(tabId);
  if (s) return s;
  s = { list: [], keys: new Map(), page: "", title: "", pageKey: "", saveT: 0, pageAsked: false };
  TS.set(tabId, s);
  const k = "media:" + tabId;
  s.loaded = Promise.resolve(sess.get(k)).then((r) => {   // the service worker was asleep: bring back what it knew
    const saved = r && r[k];
    if (!Array.isArray(saved) || !saved.length) return;
    const have = new Set(s.list.map((m) => m.key));
    s.list = saved.filter((m) => !have.has(m.key)).concat(s.list);
    for (const m of s.list) s.keys.set(m.key, m);
  }).catch(() => {});
  return s;
}
function persist(tabId) {
  const s = TS.get(tabId);
  if (!s || s.saveT) return;
  s.saveT = setTimeout(() => { s.saveT = 0; Promise.resolve(sess.set({ ["media:" + tabId]: s.list.slice(-100) })).catch(() => {}); }, 150);
}
function setBadge(tabId) {
  const s = TS.get(tabId), n = s ? s.list.filter((m) => m.category !== "image" && m.role !== "audio" && m.category !== "other").length : 0;
  try { api.action.setBadgeText({ tabId, text: n ? String(Math.min(n, 30)) : "" }); if (n) api.action.setBadgeBackgroundColor({ tabId, color: "#2563eb" }); } catch {}
}
function resetTab(tabId, keepRecentMs = 0) {
  const s = TS.get(tabId);
  if (!s) { sess.remove("media:" + tabId); try { api.action.setBadgeText({ tabId, text: "" }); } catch {} return; }
  const keep = keepRecentMs ? s.list.filter((m) => Date.now() - (m.t || 0) < keepRecentMs) : [];
  s.list = keep; s.keys = new Map(keep.map((m) => [m.key, m]));
  if (keep.length) persist(tabId); else sess.remove("media:" + tabId);
  setBadge(tabId); notifyPanel(tabId);
}
// Saves run one at a time: two videos arriving together must not overwrite each other's list.
let addQueue = Promise.resolve();
const addMedia = (tabId, item) => (addQueue = addQueue.then(() => addMediaNow(tabId, item)).catch(() => {}));

// Sites like Facebook/Instagram serve one video as many ?bytestart=..&byteend=.. pieces.
// Dropping those two parameters gives the whole file, so all the pieces collapse into one entry.
function normalizeUrl(u) {
  try {
    const x = new URL(u);
    if (!x.searchParams.has("bytestart") && !x.searchParams.has("byteend")) return u;
    x.searchParams.delete("bytestart"); x.searchParams.delete("byteend");
    return x.href;
  } catch { return u; }
}

// Synchronous core: put the record in the tab's list and announce it. Returns the stored record, or null for a duplicate.
function ingest(tabId, item) {
  const s = tabState(tabId);
  const norm = normalizeUrl(item.url);
  if (norm !== item.url) item = { ...item, url: norm, orig: item.url, size: 0 };
  // one entry per stream: YouTube hands out a fresh address for the same itag now and then - that refreshes the entry instead of adding one
  const key = item.key || (item.site === "youtube" && item.itag ? "yt:" + item.itag + ":" + (item.sid || "") : norm);
  const prev = s.keys.get(key);
  if (prev) {
    if (item.site === "youtube" && item.url !== prev.url && (item.expire || 0) >= (prev.expire || 0)) { prev.url = item.url; prev.expire = item.expire; prev.expired = false; prev.t = Date.now(); persist(tabId); }
    return null;
  }
  item = { ...item, key, t: item.t || Date.now(), category: item.category || "video" };
  if (s.page && !item.page) item.page = s.page;
  if (s.title && !item.title) item.title = s.title;
  s.list.push(item); s.keys.set(key, item);
  const cls = classOf(item), cap = CAPS[cls];
  const same = s.list.filter((m) => classOf(m) === cls);
  if (same.length > cap) { const drop = same[0]; s.list.splice(s.list.indexOf(drop), 1); s.keys.delete(drop.key); }
  persist(tabId); setBadge(tabId);
  notifyPanel(tabId, item);
  if (!s.page && !s.pageAsked) {   // page address + title for the referer: asked once per tab, never on the hot path
    s.pageAsked = true;
    Promise.resolve(api.tabs.get(tabId)).then((t) => { if (t) { s.page = t.url || s.page; s.title = t.title || s.title; for (const m of s.list) { m.page = m.page || s.page; m.title = m.title || s.title; } persist(tabId); } }).catch(() => {});
  }
  if (item.kind === "hls" || item.kind === "dash") prefetchManifest(item.url, item.kind, tabId, key);
  return item;
}
async function addMediaNow(tabId, item) { await tabState(tabId).loaded; ingest(tabId, item); }

// ---- early detection: YouTube streams are recognised from the request address alone, before the response headers arrive
if (api.webRequest.onBeforeRequest) {
  api.webRequest.onBeforeRequest.addListener((d) => {
    if (d.tabId < 0) return;
    const r = AD.describeRequest(d.url);
    if (!r || r.site !== "youtube" || !r.itag || r.sabr || r.live) return;   // SABR / live pieces carry no stream identity: those videos are listed from the player's own data + yt-dlp
    ingest(d.tabId, { kind: "file", category: r.role === "audio" ? "audio" : "video", ...r, sid: parseSid(d.url), frameId: d.frameId, page: d.documentUrl || undefined });
  }, { urls: ["*://*.googlevideo.com/videoplayback*"], types: ["media", "xmlhttprequest", "other"] });
}
const parseSid = (u) => { try { return new URL(u).searchParams.get("id") || ""; } catch { return ""; } };

// v1.8.1: requests made by a worker / service worker of the page carry no tab id; find the tab by the page that started them
const originTab = new Map();
async function resolveTab(d) {
  if (!d.initiator || !/^https?:/i.test(d.initiator)) return -1;
  const hit = originTab.get(d.initiator);
  if (hit && Date.now() - hit.t < 30e3) return hit.id;
  let id = -1;
  try { const tabs = (await api.tabs.query({ url: d.initiator + "/*" })) || []; const t = tabs.find((x) => x.active) || tabs[0]; if (t) id = t.id; } catch {}
  originTab.set(d.initiator, { id, t: Date.now() }); if (originTab.size > 50) originTab.delete(originTab.keys().next().value);
  return id;
}
function onHeaders(d) {
  if (d.tabId < 0) { if (d.statusCode < 400) resolveTab(d).then((id) => { if (id >= 0) onHeaders({ ...d, tabId: id }); }).catch(() => {}); return; }
  if (d.statusCode >= 400) return;
  if (d.type === "image" && !flags.images) return;
  if ((d.type === "main_frame" || d.type === "sub_frame") && /^text\/html|^application\/xhtml/i.test(hdr(d, "content-type"))) return;   // a normal web page, not a file
  const ct = hdr(d, "content-type"), cd = hdr(d, "content-disposition");
  const total = +(hdr(d, "content-range").split("/")[1] || hdr(d, "content-length") || 0);
  const c = CL.classifyResponse({ url: d.url, ct, cd, total, type: d.type });
  if (!c || c.category === "segment") return;
  if (c.kind === "hls" || c.kind === "dash") return void addMedia(d.tabId, { url: d.url, kind: c.kind, category: "stream", size: 0, ext: c.ext, page: d.documentUrl || undefined, ...(AD.describeRequest(d.url) || {}) });
  const a = AD.describeRequest(d.url) || {};
  if (a.site === "youtube") { if (!a.itag || a.sabr || a.live) return; addMedia(d.tabId, { kind: "file", category: a.role === "audio" ? "audio" : "video", ...a, sid: parseSid(d.url), frameId: d.frameId, size: a.size || total }); return; }
  const role = a.role || (c.category === "video" || c.category === "audio" ? roleOf(d.url, ct) : "");
  const piece = /[?&](bytestart|byteend)=/.test(d.url);   // a ranged piece of a longer stream: size says nothing, keep it
  if (!piece && total > 0 && total < CL.minSize(c.category, role, false)) return;   // v1.8.1: an unknown size (chunked reply) is kept - it used to count as 0 bytes and was dropped
  if (c.category !== "video" && c.category !== "audio" && c.attachment === false && d.type !== "image" && !c.filename && total < 64 * 1024) return;   // a small API/XHR payload that happens to be a PDF/ZIP-typed blob
  addMedia(d.tabId, { url: d.url, kind: "file", category: c.category, ext: c.ext, size: total, role, filename: c.filename || "", mime: c.mime, t: Date.now(), frameId: d.frameId, page: d.documentUrl || undefined, ...a, site: a.site || undefined, height: a.height || 0 });
}
api.webRequest.onHeadersReceived.addListener(onHeaders, { urls: ["<all_urls>"], types: ["media", "xmlhttprequest", "other", "image", "main_frame", "sub_frame", "object"] }, ["responseHeaders"]);

// a hard navigation clears the list; a single-page navigation (YouTube, Instagram reels ...) clears it when the VIDEO changes, keeping anything that loaded in the last second
const pageKey = (u) => { try { const x = new URL(u); return x.origin + x.pathname + (x.searchParams.get("v") ? "?v=" + x.searchParams.get("v") : ""); } catch { return u || ""; } };
api.tabs.onUpdated.addListener((id, ci) => {
  if (!ci.url) return;
  const k = pageKey(ci.url), s = TS.get(id);
  if (ci.status === "loading") { if (s) { s.page = ci.url; s.title = ""; s.pageAsked = false; s.pageKey = k; } resetTab(id); return; }
  if (s && s.pageKey && s.pageKey !== k) { s.pageKey = k; s.page = ci.url; s.title = ""; s.pageAsked = false; resetTab(id, 1000); }
  else if (s) { s.pageKey = k; s.page = ci.url; }
  else tabState(id).pageKey = k;
});
api.tabs.onRemoved.addListener((id) => { const s = TS.get(id); if (s?.saveT) clearTimeout(s.saveT); TS.delete(id); sess.remove("media:" + id); });

// v1.8.1: many CDNs refuse a request without the page's Referer / Origin, and an extension's own fetch() cannot set them. A short-lived session rule
// (declarativeNetRequest, exactly this one address) adds them, so quality lists and file probes work on referer-protected hosts too.
let ruleSeq = 0;
async function withReferer(url, referer, fn) {
  const dnr = api.declarativeNetRequest;
  if (!dnr || !dnr.updateSessionRules || !/^https?:/i.test(referer || "") || url.length > 1500) return fn();
  const id = 1000 + (++ruleSeq % 50000);
  try {
    await dnr.updateSessionRules({ addRules: [{ id, priority: 1, action: { type: "modifyHeaders", requestHeaders: [
      { header: "referer", operation: "set", value: referer }, { header: "origin", operation: "set", value: new URL(referer).origin }] },
      condition: { regexFilter: "^" + url.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + "$", resourceTypes: ["xmlhttprequest", "other"], tabIds: [-1] } }] });
  } catch { return fn(); }
  try { return await fn(); } finally { try { await dnr.updateSessionRules({ removeRuleIds: [id] }); } catch {} }
}

// ---------------- Quality of direct files: read the MP4 header, not the whole file ----------------
const u32 = (b, o) => (((b[o] << 24) | (b[o + 1] << 16) | (b[o + 2] << 8) | b[o + 3]) >>> 0);
const u64 = (b, o) => u32(b, o) * 4294967296 + u32(b, o + 4);
const tag = (b, o) => String.fromCharCode(b[o], b[o + 1], b[o + 2], b[o + 3]);

function* boxes(b, start, end) {
  for (let o = start; o + 8 <= end;) {
    let size = u32(b, o), hdr = 8;
    const type = tag(b, o + 4);
    if (size === 1) { if (o + 16 > end) return; size = u64(b, o + 8); hdr = 16; }
    else if (size === 0) size = end - o;
    if (size < hdr) return;
    yield { type, off: o, size, hdr };
    o += size;
  }
}

function parseMoov(b, box) {
  const out = { width: 0, height: 0, duration: 0, video: false, audio: false, fragmented: false };
  const end = Math.min(box.off + box.size, b.length);
  for (const c of boxes(b, box.off + box.hdr, end)) {
    const p = c.off + c.hdr;
    if (c.type === "mvex") out.fragmented = true;
    if (c.type === "mvhd") {
      const v = b[p], ts = u32(b, p + (v ? 20 : 12)), du = v ? u64(b, p + 24) : u32(b, p + 16);
      if (ts && du < 0xffffffff) out.duration = du / ts;
    }
    if (c.type !== "trak") continue;
    let w = 0, h = 0, kind = "";
    for (const t of boxes(b, p, Math.min(c.off + c.size, b.length))) {
      if (t.type === "tkhd") { const o = t.off + t.hdr + (b[t.off + t.hdr] ? 88 : 76); w = u32(b, o) / 65536; h = u32(b, o + 4) / 65536; }
      if (t.type === "mdia") for (const m of boxes(b, t.off + t.hdr, Math.min(t.off + t.size, b.length))) if (m.type === "hdlr") kind = tag(b, m.off + m.hdr + 8);
    }
    if (kind === "vide") { out.video = true; if (w * h >= out.width * out.height) { out.width = Math.round(w); out.height = Math.round(h); } }
    else if (kind === "soun") out.audio = true;
  }
  return out;
}

async function rangeBytes(url, start, len) {
  const r = await fetch(url, { headers: { Range: `bytes=${start}-${start + len - 1}` }, credentials: "include" });
  if (!r.ok) throw new Error("http " + r.status);
  const cr = r.headers.get("content-range");
  const total = cr ? +cr.split("/")[1] || 0 : +(r.headers.get("content-length") || 0);
  if (r.status === 206) return { buf: new Uint8Array(await r.arrayBuffer()), total };
  if (start > 0) { r.body?.cancel(); throw new Error("server ignores Range"); }
  const rd = r.body.getReader(), parts = [];  // Range ignored: take only the first bytes, then hang up
  let n = 0;
  while (n < len) { const { done, value } = await rd.read(); if (done) break; parts.push(value); n += value.length; }
  rd.cancel().catch(() => {});
  const buf = new Uint8Array(Math.min(n, len)); let o = 0;
  for (const p of parts) { const take = Math.min(p.length, buf.length - o); buf.set(p.subarray(0, take), o); o += take; }
  return { buf, total };
}

async function probeMp4(url) {
  const WIN = 256 * 1024;
  let { buf, total } = await rangeBytes(url, 0, WIN), base = 0, off = 0;
  for (let guard = 0; guard < 40; guard++) {
    if (off < base || off + 16 > base + buf.length) {  // next box header isn't in our window: fetch from there
      if (total && off >= total) break;
      ({ buf } = await rangeBytes(url, off, WIN)); base = off;
      if (buf.length < 8) break;
    }
    const rel = off - base;
    let size = u32(buf, rel), hdr = 8;
    const type = tag(buf, rel + 4);
    if (size === 1) { size = u64(buf, rel + 8); hdr = 16; } else if (size === 0) size = (total || off + buf.length) - off;
    if (size < hdr) break;
    if (type === "moof" || type === "styp") return { segment: true, size: total, video: false, audio: false, width: 0, height: 0, duration: 0 };  // a piece of a stream, not a video
    if (type === "moov") {
      if (rel + size > buf.length) { if (size > 16 * 1024 * 1024) break; ({ buf } = await rangeBytes(url, off, size)); base = off; }
      const info = parseMoov(buf, { off: off - base, size, hdr });
      return { ...info, size: total, segment: info.fragmented && total > 0 && total < 20 * 1024 };  // tiny fMP4 = init segment only
    }
    off += size;
    if (total && off >= total) break;
  }
  return null;  // not an MP4 we can read (webm, mp3, ...): the panel just shows "Direct file"
}

const pcache = new Map();
async function probeMedia(url, orig, referer) {
  if (pcache.has(url)) return pcache.get(url);
  let out = null;
  for (const u of orig ? [url, orig] : [url]) {  // if the cleaned-up URL doesn't work, fall back to the original
    try { out = await withReferer(u, referer, () => probeMp4(u)); } catch { out = null; }
    if (out) { out.useUrl = u; break; }
  }
  pcache.set(url, out);
  return out;
}

// ---------------- Tell the page (instantly) when something new arrives ----------------
// The first notification for a tab goes out immediately; anything arriving within the next 40 ms is folded into one more message (YouTube lists ~10 streams at once).
const nStat = new Map();   // tabId -> { t: timer, dirty, item }
const brief = (m) => ({ key: m.key, kind: m.kind, category: m.category, role: m.role || "", height: m.height || 0, site: m.site || "", ext: m.ext || "", drm: !!m.drm });
function pushTo(tabId, item) {
  try { Promise.resolve(api.tabs.sendMessage(tabId, { cmd: "media-updated" }, { frameId: 0 })).catch(() => {}); } catch {}
  if (item && flags.push && item.category !== "image" && item.role !== "audio") {
    try { Promise.resolve(api.tabs.sendMessage(tabId, { cmd: "media-found", item: brief(item) }, { frameId: 0 })).catch(() => {}); } catch {}
  }
}
function notifyPanel(tabId, item) {
  let n = nStat.get(tabId);
  if (n) { n.dirty = true; if (item) n.item = item; return; }
  pushTo(tabId, item);
  n = { dirty: false, item: null, t: 0 };
  n.t = setTimeout(() => { nStat.delete(tabId); if (n.dirty) pushTo(tabId, n.item); }, 40);
  nStat.set(tabId, n);
}
async function listMedia(tabId) {
  const s = tabState(tabId);
  await s.loaded;
  const now = Date.now() / 1000;
  return withPairs(s.list.map((m) => (m.expire && m.expire < now ? { ...m, expired: true } : m)));
}

// ---------------- Manifests: HLS / DASH qualities, audio renditions, DRM check ----------------
// Fetched once, in the background, the moment a manifest is detected - so the quality list is ready before the user asks for it.
const mcache = new Map(), drmUrls = new Set();
function getManifest(url, kind, referer) {
  const hit = mcache.get(url);
  if (hit) return hit;
  const p = (async () => {
    try {
      const text = await withReferer(url, referer, async () => { const r = await fetch(url, { credentials: "include" }); return r.ok ? await r.text() : ""; });
      const r = { url };
      const m = kind === "dash" ? CL.parseMpd(text) : CL.parseHlsMaster(text, url);
      if (m.drm) drmUrls.add(url);
      return { kind, variants: [], audios: [], videos: [], ...m, failed: !text };
    } catch { return { kind, variants: [], audios: [], videos: [], drm: false, live: false, failed: true }; }
  })();
  mcache.set(url, p);
  p.then((m) => { if (m.failed && mcache.get(url) === p) mcache.delete(url); });   // a failed fetch is retried next time
  if (mcache.size > 60) mcache.delete(mcache.keys().next().value);
  return p;
}
function prefetchManifest(url, kind, tabId, key) {
  const rec0 = TS.get(tabId)?.keys.get(key);
  getManifest(url, kind, (rec0 && rec0.page) || TS.get(tabId)?.page).then((m) => {
    const rec = TS.get(tabId)?.keys.get(key);
    if (!rec || (!m.drm && !m.live)) return;
    rec.drm = !!m.drm; rec.live = !!m.live; persist(tabId); notifyPanel(tabId, rec);
  }).catch(() => {});
}
const getVariants = async (url, referer) => (await getManifest(url, "hls", referer)).variants;   // [{height,bandwidth,fps,url}] - empty = single-quality stream

// ---------------- Stream list from AeroGrab (yt-dlp): YouTube, Facebook, Instagram ... ----------------
// AeroGrab reads the page's qualities and sizes; the answer is cached for a few minutes. Nothing downloads until the user picks a row.
// v1.8: one lookup per address at a time. The look-ahead started when a video begins playing and the menu the user opens a second later used to run yt-dlp TWICE.
const fcache = new Map(), fflight = new Map();
async function getFormats(url, referer, prefetch) {
  const hit = fcache.get(url);
  if (hit && Date.now() - hit.t < 5 * 60e3) return hit.data;
  const running = fflight.get(url);
  if (running) { const d = await running.p; if (!(d && d.prefetch && !prefetch)) return d; }   // share the answer, unless the look-ahead was told "AeroGrab isn't running"
  const entry = { prefetch, p: null };
  entry.p = lookupFormats(url, referer, prefetch).finally(() => { if (fflight.get(url) === entry) fflight.delete(url); });
  fflight.set(url, entry);
  return entry.p;
}
async function lookupFormats(url, referer, prefetch) {
  const t0 = performance.now();
  const job = { url, referer: referer || "", cookie: await cookieHeader(url), userAgent: navigator.userAgent, ...(prefetch ? { prefetch: true } : {}) };
  let data = null, nativeError = "";
  try { data = await nativeCall({ cmd: "formats", job }, 90000); }  // yt-dlp can take a while
  catch (e) { nativeError = e?.message || String(e); }
  if (!data) {
    const cfg = await getCfg();
    if (!cfg.token) throw new Error("not paired: AeroGrab's browser integration isn't registered yet" + (nativeError ? ` (${nativeError})` : ""));
    if (prefetch) return { ok: false, error: "prefetch skipped", prefetch: true };
    const r = await fetch(`http://127.0.0.1:${cfg.port}/formats`, {
      method: "POST", headers: { "Content-Type": "application/json", "X-AeroGrab-Token": cfg.token }, body: JSON.stringify(job),
    });
    if (!r.ok) throw new Error("AeroGrab replied " + r.status);
    data = await r.json();
  }
  if (data?.prefetch) return data;   // AeroGrab isn't running: nothing to cache
  if (data?.ok && data.formats?.length) { fcache.set(url, { t: Date.now(), data }); perf.formats.push({ ms: Math.round(performance.now() - t0), t: Date.now() }); if (perf.formats.length > 20) perf.formats.shift(); }
  if (fcache.size > 40) fcache.delete(fcache.keys().next().value);
  return data;
}

api.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  // a tab's content script, or an extension page (popup) naming the tab it wants
  const tabId = sender.tab?.id ?? (sender.tab == null && Number.isInteger(msg?.tabId) ? msg.tabId : undefined);
  const reply = (p) => { p.then(sendResponse, (e) => sendResponse({ ok: false, error: e.message })); return true; };
  switch (msg?.cmd) {
    case "gesture": lastGesture = Date.now(); lastMods = { alt: !!msg.alt, ctrl: !!msg.ctrl, shift: !!msg.shift }; return false;   // real click/key in a page (content.js)
    case "cfg": return reply(getCapture(5 * 60e3));   // content.js: should the "Download this video" button show?
    case "send": return reply(sendToAeroGrab(msg.job).then(() => ({ ok: true })));
    case "status": return reply(connectionStatus().then((s) => ({ ok: true, ...s })));
    case "stats": return reply(Promise.resolve({ ok: true, sends: perf.sends.slice(-10), formats: perf.formats.slice(-10) }));
    case "formats":  // the overlay's menu; only for web addresses
      return /^https?:/i.test(msg.url || "") ? reply(getFormats(msg.url, msg.referer, !!msg.prefetch)) : false;
    case "list": return tabId == null ? false : reply(listMedia(tabId));
    case "variants":  // only for streams this tab actually loaded
      return tabId == null ? false : reply(listMedia(tabId).then((l) => (l.some((m) => m.url === msg.url) ? getVariants(msg.url, (l.find((m) => m.url === msg.url) || {}).page) : [])));
    case "manifest":  // full manifest facts (audio renditions, DRM flag, live) of a stream this tab loaded
      return tabId == null ? false : reply(listMedia(tabId).then((l) => { const m = l.find((x) => x.url === msg.url && (x.kind === "hls" || x.kind === "dash")); return m ? getManifest(m.url, m.kind, m.page) : null; }));
    case "probe":  // quality of a direct file, only for files this tab actually loaded
      return tabId == null ? false : reply(listMedia(tabId).then((l) => { const m = l.find((x) => x.url === msg.url); return m ? probeMedia(m.url, m.orig, m.page) : null; }));
    case "found":
      if (tabId == null || !/^https?:/i.test(msg.url || "")) return false;
      return reply(addMedia(tabId, { url: msg.url, kind: kindOf(msg.url), category: kindOf(msg.url) === "file" ? "video" : "stream", size: 0 }).then(() => ({ ok: true })));
  }
});
