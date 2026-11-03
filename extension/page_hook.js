// AeroGrab v1.8 - page hook. Runs in the PAGE's own JavaScript world (manifest: "world": "MAIN"), at document_start, in every frame.
// Chrome / Edge / Brave only (Firefox MV3 has no MAIN-world content scripts before 128; there everything below is simply absent and the
// extension falls back to network sniffing + yt-dlp).
//
// What it does - and what it deliberately does NOT do:
//   + tells the content script when a single-page site changes address (history.pushState/replaceState + YouTube's own events), so no polling is needed
//   + reads the player's own description of the current YouTube video (title, length, the quality ladder it offers, live/DRM status)
//   + notes when a <video> is fed through MediaSource (blob: address), so the extension knows the file is not at the <video src>
//   - it does NOT wrap fetch / XMLHttpRequest, does not touch player state, never changes playback; webRequest already sees every network request
// It talks to content.js only through window.postMessage, and everything it sends is plain, size-limited data.
(() => {
  "use strict";
  if (window.__aerograbHook) return;
  window.__aerograbHook = true;
  const post = (type, data) => { try { window.postMessage({ source: "aerograb-hook", type, data }, "*"); } catch {} };
  const str = (s, n = 400) => String(s == null ? "" : s).slice(0, n);

  // ---- single-page navigation without polling
  let lastHref = location.href;
  const nav = () => { if (location.href !== lastHref) { lastHref = location.href; post("nav", { href: location.href }); } };
  for (const m of ["pushState", "replaceState"]) {
    const orig = history[m];
    if (typeof orig !== "function") continue;
    history[m] = function () { const r = orig.apply(this, arguments); queueMicrotask(nav); return r; };
  }
  addEventListener("popstate", nav); addEventListener("hashchange", nav);

  // ---- MediaSource: a <video> with a blob: address is fed by script; remember which codecs it was given
  try {
    const MS = window.MediaSource, add = MS && MS.prototype.addSourceBuffer;
    if (add) {
      MS.prototype.addSourceBuffer = function (mime) { post("mse", { mime: str(mime, 120) }); return add.apply(this, arguments); };
    }
  } catch {}

  // ---- YouTube: the player knows exactly which video this is and which qualities it offers
  const isYT = /(^|\.)(youtube\.com|youtube-nocookie\.com)$/i.test(location.hostname);
  let lastSent = "";
  function ytSummary() {
    const player = document.getElementById("movie_player") || document.querySelector(".html5-video-player");
    let pr = null;
    try { pr = (player && typeof player.getPlayerResponse === "function" && player.getPlayerResponse()) || null; } catch {}
    if (!pr) { try { pr = window.ytInitialPlayerResponse || null; } catch {} }
    if (!pr || !pr.videoDetails) return null;
    const vd = pr.videoDetails, sd = pr.streamingData || {}, ps = pr.playabilityStatus || {};
    const rows = [];
    for (const f of [].concat(sd.formats || [], sd.adaptiveFormats || [])) {
      if (!f || !f.itag) continue;
      rows.push({ itag: f.itag | 0, mime: str(f.mimeType, 120), height: f.height | 0, fps: f.fps | 0, label: str(f.qualityLabel, 16), bitrate: f.bitrate | 0, size: +f.contentLength || 0,
                  hasUrl: !!(f.url || f.signatureCipher || f.cipher), audio: /^audio\//.test(f.mimeType || ""), durMs: +f.approxDurationMs || 0 });
    }
    return {
      id: str(vd.videoId, 20), title: str(vd.title, 300), author: str(vd.author, 120), lengthSeconds: +vd.lengthSeconds || 0, isLive: !!vd.isLive,
      description: str(vd.shortDescription, 300), status: str(ps.status, 24), reason: str(ps.reason, 160),
      drm: !!(sd.drmFamilies && sd.drmFamilies.length),
      hls: !!sd.hlsManifestUrl, formats: rows.slice(0, 80),
    };
  }
  function sendYT(force) {
    if (!isYT) return;
    const s = ytSummary();
    if (!s) return;
    const key = s.id + "|" + s.formats.length + "|" + s.status;
    if (!force && key === lastSent) return;
    lastSent = key;
    post("yt-player", s);
  }
  if (isYT) {
    for (const ev of ["yt-navigate-finish", "yt-page-data-updated", "yt-player-updated"]) addEventListener(ev, () => { lastHref = location.href; post("nav", { href: location.href }); setTimeout(() => sendYT(false), 0); }, true);
    // the first frame of a video: its player response is certainly loaded now
    addEventListener("loadeddata", (e) => { if (e.target && e.target.tagName === "VIDEO") sendYT(false); }, true);
    addEventListener("playing", (e) => { if (e.target && e.target.tagName === "VIDEO") sendYT(false); }, true);
  }
  // the content script may ask at any time (e.g. when the user opens the menu)
  addEventListener("message", (e) => {
    if (e.source !== window || !e.data || e.data.source !== "aerograb-content") return;
    if (e.data.type === "ask") sendYT(true);
  });
})();
