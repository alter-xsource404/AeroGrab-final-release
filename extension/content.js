// AeroGrab content script - v1.8 (instant capture tip, hover button, YouTube quality list from the player's own data, no polling timers; v1.7: file names via names.js + page caption)
// ONLY the IDM-style "Download this video" button on playing <video> elements (drag it, double-click resets, x hides it for that video).
// FIX (#2): the "AeroGrab Video Sniffer" floating panel/bubble was removed completely.
// FIX (no sound): the menu now lists yt-dlp's formats (video+audio merged by AeroGrab/ffmpeg) whenever the page is supported;
//   raw sniffed streams are only a fallback and are always sent together with their paired audio stream (job.audioUrl).
// Runs in every frame. Everything lives in a closed shadow root, so page styles can't touch it.
(() => {
  "use strict";
  if (window.__aerograbSniffer || !document.documentElement) return;
  window.__aerograbSniffer = true;

  const api = globalThis.browser ?? globalThis.chrome;

  // FIX (phantom downloads): tell the background script when the user really interacts with this page, so only downloads
  // that follow a real click/key/right-click are taken over. Scripts cannot fake these (isTrusted).
  // The held modifier keys ride along: they are the "prevent / force downloading with AeroGrab" keys from AeroGrab's Configuration.
  let lastGesture = 0;
  const gesture = (e) => {
    if (!e.isTrusted || (e.type !== "pointerdown" && Date.now() - lastGesture < 300)) return;
    lastGesture = Date.now();
    try { Promise.resolve(api.runtime.sendMessage({ cmd: "gesture", alt: e.altKey, ctrl: e.ctrlKey, shift: e.shiftKey })).catch(() => {}); } catch {}
  };
  for (const t of ["pointerdown", "keydown", "contextmenu", "touchstart"]) addEventListener(t, gesture, { capture: true, passive: true });
  /* ICON-BEGIN */ const ICON = "data:image/png;base64,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"; /* ICON-END */

  const CSS = `
    :host{all:initial;--bg:#fff;--fg:#111827;--bd:#e5e7eb;--chip:#e5e7eb;--hov:#f3f4f6;--sub:#6b7280}
    @media (prefers-color-scheme:dark){:host{--bg:#1f2937;--fg:#f3f4f6;--bd:#374151;--chip:#374151;--hov:#2b3646;--sub:#9ca3af}}
    *{box-sizing:border-box;font:13px/1.35 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
    .chip{font-size:10px;font-weight:700;padding:1px 6px;border-radius:8px;background:var(--chip);color:var(--fg)}
    .ov{position:fixed;left:0;top:0;display:none;will-change:transform;color:var(--fg)}
    .pill{display:flex;align-items:center;gap:6px;height:30px;padding:0 4px 0 7px;border-radius:15px;cursor:grab;user-select:none;touch-action:none;
          background:linear-gradient(135deg,#2563eb,#1d4ed8);color:#fff;font-weight:600;font-size:12px;white-space:nowrap;
          box-shadow:0 2px 10px #0008,0 0 0 1px #ffffff40 inset;opacity:.88;transition:opacity .15s}
    .pill:hover,.ov.open .pill{opacity:1}
    .pill.drag{cursor:grabbing}
    .pill img{width:18px;height:18px;pointer-events:none;border-radius:4px}
    .pill .car{font-size:10px;opacity:.9;pointer-events:none}
    .pill .x{all:unset;cursor:pointer;width:20px;height:20px;border-radius:10px;text-align:center;line-height:20px;font-size:15px;opacity:.85}
    .pill .x:hover{background:#ffffff40;opacity:1}
    .ov.compact .lbl,.ov.compact .car{display:none}
    .ov.compact .pill{padding:0 4px 0 6px}
    .menu{position:absolute;right:0;top:36px;width:min(330px,calc(100vw - 16px));display:none;flex-direction:column;background:var(--bg);color:var(--fg);
          border:1px solid var(--bd);border-radius:12px;box-shadow:0 10px 30px #0007;overflow:hidden}
    .ov.open .menu{display:flex}
    .menu.up{top:auto;bottom:36px}
    .menu.left{right:auto;left:0}
    .mh{display:flex;align-items:center;gap:8px;padding:8px 10px;background:#2563eb;color:#fff}
    .mh img{width:18px;height:18px;border-radius:4px}.mh b{flex:1;font-size:13px}
    .mh button{all:unset;cursor:pointer;width:22px;height:22px;text-align:center;border-radius:5px;line-height:22px;font-size:16px}
    .mh button:hover{background:#fff3}
    .mn{padding:8px 10px 4px}
    .mn input{width:100%;padding:5px 7px;border-radius:6px;border:1px solid var(--bd);background:var(--bg);color:var(--fg);font-weight:600}
    .ml{overflow:auto;padding:2px 6px 6px}
    .q{display:flex;align-items:center;gap:8px;padding:8px 6px;border-radius:8px;cursor:pointer}
    .q:hover{background:var(--hov)}
    .q .ql{font-weight:700;min-width:62px}
    .q .qs{flex:1;min-width:0;color:var(--sub);font-size:12px;text-align:right}
    .q .go{color:#2563eb;font-weight:700}
    .q.busy{opacity:.55;pointer-events:none}
    .sep{padding:8px 6px 2px;font-size:11px;font-weight:700;color:var(--sub);text-transform:uppercase;letter-spacing:.04em}
    .note{padding:10px 8px;color:var(--sub);font-size:12px}
    .mf{padding:6px 10px;font-size:11px;color:var(--sub);border-top:1px solid var(--bd);min-height:26px}
    .mf.err{color:#ef4444}
    .mi{padding:0 10px 4px;font-size:11px;color:var(--sub);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
    .tip{position:absolute;right:0;top:36px;display:none;align-items:center;gap:8px;max-width:min(360px,calc(100vw - 16px));padding:7px 8px 7px 10px;border-radius:10px;
         background:var(--bg);color:var(--fg);border:1px solid var(--bd);box-shadow:0 6px 20px #0006;font-size:12px}
    .ov.tipon:not(.open) .tip{display:flex}
    .tip .tt{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
    .tip button{all:unset;cursor:pointer;padding:3px 9px;border-radius:7px;background:#2563eb;color:#fff;font-weight:700;font-size:12px;white-space:nowrap}
    .tip button.g{background:var(--chip);color:var(--fg)}
    .tip .tx{padding:2px 6px;background:none;color:var(--sub);font-size:15px}
    .pill.pulse{animation:odm 1.1s ease-out 2}
    @keyframes odm{0%{box-shadow:0 0 0 0 #2563eb99,0 2px 10px #0008}100%{box-shadow:0 0 0 12px #2563eb00,0 2px 10px #0008}}
  `;

  // ---------- helpers ----------
  const el = (tag, props = {}, ...kids) => { const e = document.createElement(tag); Object.assign(e, props); e.append(...kids); return e; };
  const send = async (msg) => { try { return await api.runtime.sendMessage(msg); } catch { return undefined; } };
  const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
  const fmtSize = (n) => (n >= 1073741824 ? (n / 1073741824).toFixed(2) + " GB" : n >= 1048576 ? (n / 1048576).toFixed(1) + " MB" : Math.ceil(n / 1024) + " KB");
  const fmtEta = (s) => (s < 5 ? "a few seconds" : s < 90 ? Math.round(s) + " s" : s < 5400 ? Math.round(s / 60) + " min" : Math.floor(s / 3600) + " h " + Math.round((s % 3600) / 60) + " min");
  const N = globalThis.AeroGrabNames, AD = globalThis.AeroGrabAdapters, CL = globalThis.AeroGrabClassify;
  const safeName = N.safeName;
  const fileExt = (u) => { try { const m = new URL(u).pathname.match(/\.([a-z0-9]{2,4})$/i); return m ? m[1].toLowerCase() : "mp4"; } catch { return "mp4"; } };
  const extOf = (u) => { try { return (new URL(u).pathname.match(/\.([a-z0-9]{2,4})$/i)?.[1] || "FILE").toUpperCase(); } catch { return "FILE"; } };
  const connected = (e = "") => /not paired|replied|token|fetch|network|refused|reach|isn't running|timed out/i.test(e) || !e;
  const errorHint = (e = "") =>
    /not paired/i.test(e) ? "AeroGrab isn't connected yet. Open AeroGrab once: it registers itself with your browser. (Or paste a token in this extension's options.)"
    : /replied 401|token/i.test(e) ? "AeroGrab and the extension disagree about the pairing token. Restart AeroGrab, or re-paste the token in the extension's options."
    : /fetch|network|refused/i.test(e) || !e ? "AeroGrab isn't running (or the port is wrong). Start it and try again." : e;

  // ---- what the page's own JavaScript told us (page_hook.js, Chrome / Edge / Brave): the YouTube player's description of the current video
  const hook = { yt: null };
  const int = (n) => (Number.isFinite(+n) ? Math.max(0, Math.min(1e12, Math.floor(+n))) : 0);
  const clip = (t, n = 300) => String(t == null ? "" : t).slice(0, n);
  function sanitizeYT(d) {
    return { id: clip(d.id, 20), title: clip(d.title), author: clip(d.author, 120), lengthSeconds: int(d.lengthSeconds), isLive: !!d.isLive, status: clip(d.status, 24), reason: clip(d.reason, 160), drm: !!d.drm, hls: !!d.hls,
             formats: (Array.isArray(d.formats) ? d.formats : []).slice(0, 80).map((f) => ({ itag: int(f.itag), mime: clip(f.mime, 120), height: int(f.height), fps: int(f.fps), label: clip(f.label, 16), bitrate: int(f.bitrate), size: int(f.size), audio: !!f.audio, hasUrl: !!f.hasUrl })) };
  }
  const ytId = () => (CL && CL.youtubeWatchUrl(location.href) || {}).id || "";
  const ytNow = () => (hook.yt && hook.yt.id && hook.yt.id === ytId() ? hook.yt : null);   // a stale answer for the previous video is never used

  // ---- the video's name (v1.7). Order: yt-dlp's real title -> the post's caption in the page -> metadata -> "<Site> video <id>".
  // The tab title is only used when it isn't generic; "Facebook", "Reels", "(3) Facebook" and the like are rejected by names.js.
  const BOILER = /^(follow|following|like|comment|share|reply|see more|more|sponsored|public|reels?|suggested for you|add friend|join|send message|watch more|see translation|original audio)$/i;
  const meta = (sel) => document.querySelector(sel)?.content;
  function jsonLdTexts() {
    const out = [];
    for (const n of document.querySelectorAll('script[type="application/ld+json"]')) {
      try {
        const walk = (o) => { if (!o || typeof o !== "object") return; if (Array.isArray(o)) return o.forEach(walk);
          if (/VideoObject|AudioObject|SocialMediaPosting/i.test([].concat(o["@type"] || []).join(" "))) out.push(o.name, o.headline, o.caption, o.description);
          walk(o["@graph"]); };
        walk(JSON.parse(n.textContent));
      } catch {}
      if (out.length > 12) break;
    }
    return out;
  }
  // The caption of the post this <video> sits in: nearest enclosing post, first real text block that isn't a button, a link (author name) or UI chrome.
  function postCaption(video) {
    const bad = (e) => e.closest('a[role="link"],a[href],button,[role="button"],[role="navigation"],nav,header,[role="tablist"],[aria-hidden="true"],[contenteditable="true"],form');
    for (let n = video?.parentElement, i = 0; n && i < 16; n = n.parentElement, i++) {
      if (n.querySelectorAll("video").length > 1) break;   // we climbed into a feed: a caption here would belong to another video
      const exact = n.querySelector('[data-ad-preview="message"],[data-ad-comet-preview="message"],[data-testid="post_message"],[itemprop="description"],figcaption');
      if (exact && (exact.innerText || "").trim().length >= 3) return exact.innerText;
      for (const e of n.querySelectorAll('div[dir="auto"],span[dir="auto"],h1,h2')) {
        if (bad(e)) continue;
        const t = (e.innerText || "").replace(/\s+/g, " ").trim();
        if (t.length >= 8 && t.length <= 600 && !BOILER.test(t) && !/^[\d.,\sKMB]+$/.test(t)) return t;
      }
    }
    return "";
  }
  function pickFor(video, yt) {
    const v = video || [...document.querySelectorAll("video")].find((x) => !x.paused && !x.ended) || document.querySelector("video");
    let site = []; try { site = AD?.forPage(location.href).dom?.(document, v)?.titles || []; } catch {}   // per-site hooks (adapters.js)
    return N.pickName({
      ytTitle: yt?.title || ytNow()?.title, ytFallback: yt?.fallback,
      dom: [v?.getAttribute("aria-label"), v?.title, postCaption(v), ...site, ...jsonLdTexts()],
      meta: [meta("meta[property='og:title']"), meta("meta[property='og:description']"), meta("meta[name='twitter:title']"), meta("meta[name='description']"), document.querySelector("h1")?.textContent, document.title],
      pageUrl: location.href,
    });
  }
  const captionGuess = (video) => pickFor(video, null);

  // The address yt-dlp should read: this page when it is a video page, else the permalink of the post the <video> sits in (feeds, reels).
  const VIDEO_PAGE = /(\/watch\?|\/watch\/\?|\/shorts\/|\/reels?\/[\w-]+|\/p\/[\w-]+|\/tv\/|\/videos?\/|\/status\/|\/clip\/|\/embed\/|youtu\.be\/|\/v\/)/i;
  const PERMALINK = 'a[href*="/reel/"],a[href*="/reels/"],a[href*="/p/"],a[href*="/tv/"],a[href*="/watch/"],a[href*="/videos/"],a[href*="/status/"],a[href*="/shorts/"],a[href*="/watch?"]';
  function pageUrlFor(v) {
    const ad = AD?.forPage(location.href), vp = ad && ad.videoPage ? ad.videoPage(location.href) : null;
    if (vp) return vp.url;                                       // the clean address for this site (YouTube: /watch?v=ID, also for /shorts/ID, youtu.be/ID ...)
    if (VIDEO_PAGE.test(location.pathname + location.search)) return location.href;
    for (let n = v.parentElement, i = 0; n && i < 14; n = n.parentElement, i++) {
      if (n.querySelectorAll("video").length > 1) break;
      const a = n.querySelector(PERMALINK);
      if (a && /^https?:/i.test(a.href)) return a.href;
    }
    return location.href;
  }

  // ---------- state ----------
  let cfg = { overlay: true, ovCompact: false, toast: true };
  const OV_HOME = { right: 10, top: 10 };
  const ovOff = { ...OV_HOME };   // where the button sits, measured from the video's top-right corner
  let items = [];                 // streams the background script sniffed for this tab (each may carry .audioUrl)
  const variants = new Map();     // HLS master url -> null (loading) | [{height,bandwidth,fps,url}]
  const probes = new Map();       // direct file url -> undefined | null (checking) | {width,height,duration,video,audio,segment,size,useUrl} | false
  const overlays = new Map();     // <video> -> its button
  let refreshTimer = 0;
  const toasted = new Set();      // capture tips already shown for this page (a resource is announced once)

  // ---------- shadow host ----------
  const host = el("div");
  host.style.cssText = "all:initial;position:fixed;top:0;left:0;width:0;height:0;z-index:2147483647;";
  const root = host.attachShadow({ mode: "closed" });
  try { const sh = new CSSStyleSheet(); sh.replaceSync(CSS); root.adoptedStyleSheets = [sh]; }
  catch { root.append(el("style", { textContent: CSS })); }
  document.documentElement.append(host);
  // our clicks must not reach the page (it would pause the video, close its menus ...)
  for (const t of ["pointerdown", "pointerup", "mousedown", "mouseup", "click", "dblclick", "contextmenu", "keydown", "keyup"]) root.addEventListener(t, (e) => e.stopPropagation());
  // a fullscreen <div> hides everything outside it: move our host inside while it is fullscreen
  document.addEventListener("fullscreenchange", () => {
    const fe = document.fullscreenElement;
    (fe && !["VIDEO", "IFRAME"].includes(fe.tagName) ? fe : document.documentElement).append(host);
    wake();
  });
  function applyVisibility() { host.style.display = cfg.overlay ? "" : "none"; if (!cfg.overlay) overlays.forEach(closeMenu); wake(); }

  // ---------- sniffed streams (fallback source) ----------
  async function loadItems() {
    const r = await send({ cmd: "list" });
    items = Array.isArray(r) ? r : [];
    for (const it of items) {
      if (it.kind === "hls" && !variants.has(it.url)) {
        variants.set(it.url, null);
        send({ cmd: "variants", url: it.url }).then((v) => { variants.set(it.url, Array.isArray(v) ? v : []); dataChanged(); });
      }
      if (it.kind === "file" && !probes.has(it.url)) {
        probes.set(it.url, null);
        send({ cmd: "probe", url: it.url }).then((p) => { probes.set(it.url, p || false); dataChanged(); });
      }
    }
    dataChanged();
  }
  function dataChanged() { overlays.forEach((ov) => ov.el.classList.contains("open") && renderList(ov)); tipSoon(); }
  const refreshSoon = () => { clearTimeout(refreshTimer); refreshTimer = setTimeout(loadItems, 300); };

  function shownItems() {
    const kids = new Set();  // hide the per-quality playlists of a master we already list
    for (const v of variants.values()) (v || []).forEach((x) => kids.add(x.url));
    const height = (it) => { const p = probes.get(it.url); return p && p.video ? Math.min(p.width, p.height) : 0; };
    const rank = (it) => (it.kind === "hls" ? 2 : it.kind === "dash" ? 1 : 0);
    return items.filter((it) => !kids.has(it.url) && !(probes.get(it.url) || {}).segment && it.role !== "audio")  // audio halves are attached to their video, not listed
      .reverse().sort((x, y) => rank(y) - rank(x) || height(y) - height(x));
  }

  // FIX (no sound): the audio stream that belongs to a silent video file. The background pairs them by role (efg/mime/content-type) and load time;
  // if it couldn't tell, fall back to "an audio-only file of the same length".
  function audioFor(it) {
    if (it.kind !== "file") return "";
    if (it.audioUrl) return it.audioUrl;
    const p = probes.get(it.url);
    if (!p || !p.video || p.audio) return "";
    const best = items.filter((x) => x.kind === "file" && x.url !== it.url)
      .map((x) => ({ x, q: probes.get(x.url) })).filter(({ q }) => q && q.audio && !q.video && !q.segment)
      .sort((a, b) => Math.abs((a.q.duration || 0) - (p.duration || 0)) - Math.abs((b.q.duration || 0) - (p.duration || 0)))[0];
    return best && (!p.duration || !best.q.duration || Math.abs(best.q.duration - p.duration) <= 2.5) ? (best.q.useUrl || best.x.url) : "";
  }

  // The job for a sniffed stream. Video+audio files are sent together (audioUrl) so AeroGrab downloads both and ffmpeg merges them.
  function jobFor(it, name, opts = {}) {
    const isHls = it.kind === "hls", isDash = it.kind === "dash";
    const vs = isHls ? variants.get(it.url) : undefined;
    const p = isHls || isDash ? undefined : probes.get(it.url);
    const v = opts.variant ?? null;
    const eff = v || (vs && vs.length ? vs[0] : null);
    const audioUrl = audioFor(it);
    const q = isHls ? (eff && eff.height ? eff.height + "p" : "") : isDash ? "" : (p && p.video ? Math.min(p.width, p.height) + "p" : "");
    const base = [safeName(name) || "video", q].filter(Boolean).join(" ");
    return {
      url: isHls || isDash ? it.url : (p && p.useUrl) || it.url, referer: it.page || location.href, kind: isHls ? "hls" : isDash ? "dash" : undefined,
      audioUrl: audioUrl || undefined,
      filename: isHls || isDash ? base : base + "." + (audioUrl ? "mp4" : p && p.audio && !p.video ? "m4a" : fileExt(it.url)),
      quality: v?.height || 0, bandwidth: v?.bandwidth || 0,
      meta: { site: it.site || siteName(), title: safeName(name) || "", ext: isHls || isDash ? "mp4" : fileExt(it.url), height: v?.height || (p && p.video ? Math.min(p.width, p.height) : 0), duration: (p && p.duration) || 0, size: (p && p.size) || it.size || 0, source: "stream" },
    };
  }

  const siteName = () => { const a = AD?.forPage(location.href); return a && a.name ? a.name : location.hostname.replace(/^(www|m)\./, ""); };
  // facts about the capture that AeroGrab shows in its dialog next to the name (all optional; AeroGrab sanitises them)
  const metaFor = (ov, extra) => ({ site: siteName(), title: ov.nameInput.value || "", duration: Math.round(ytNow()?.lengthSeconds || (Number.isFinite(ov.v.duration) ? ov.v.duration : 0) || ov.fmt?.duration || 0), source: ov.fmt && ov.fmt.ok ? "yt-dlp" : "page", ...extra });
  // The quality ladder YouTube's player reports for THIS video: one row per height (picture + the best audio, sizes added), nothing invented.
  function ytQuick() {
    const y = ytNow();
    if (!y || y.drm || (y.status && y.status !== "OK") || y.isLive) return null;
    const aud = y.formats.filter((f) => f.audio).sort((a, b) => (/mp4/.test(b.mime) - /mp4/.test(a.mime)) || b.bitrate - a.bitrate)[0] || null;
    const best = new Map();
    for (const f of y.formats) {
      if (f.audio || !f.height) continue;
      const cur = best.get(f.height), score = (f.fps || 0) * 1e3 + (/avc1|mp4/.test(f.mime) ? 1 : 0);
      if (!cur || score > cur.score) best.set(f.height, { ...f, score });
    }
    const rows = [...best.values()].sort((a, b) => b.height - a.height).map((f) => ({ height: f.height, fps: f.fps, size: (f.size || 0) + (f.size && aud ? aud.size || 0 : 0) }));
    return rows.length || aud ? { rows, audio: aud ? { size: aud.size || 0 } : null } : null;
  }

  // =====================================================================================================
  // "Download this video" button over every playing <video>
  // =====================================================================================================
  const MIN_W = 200, MIN_H = 110;
  const instKey = (v) => location.href + "|" + (v.currentSrc || v.src || "");  // new address or new source = new video "instance"

  let buttonOn = true;   // Configuration > General > "Show the Download this video button"
  Promise.resolve(api.runtime.sendMessage({ cmd: "cfg" })).then((c) => { if (c && c.video_button === false) { buttonOn = false; [...overlays.values()].forEach(destroy); } }).catch(() => {});
  function consider(v) {
    if (!buttonOn || !v || v.tagName !== "VIDEO" || overlays.has(v)) return;
    const ov = { v, played: !v.paused, closedKey: "", fmt: undefined, fmtMsg: "", nameDirty: false, w: 150, h: 30, key: instKey(v) };
    ov.nameInput = el("input", { type: "text", spellcheck: false, title: "File name - you can edit it" });
    ov.nameInput.oninput = () => { ov.nameDirty = true; };
    ov.list = el("div", { className: "ml" });
    ov.foot = el("div", { className: "mf" });
    ov.pill = el("div", { className: "pill", title: "Download this video with AeroGrab  (drag to move, double-click to reset)" },
      el("img", { src: ICON }), el("span", { className: "lbl", textContent: "Download this video" }), el("span", { className: "car", textContent: "▾" }),
      el("button", { className: "x", textContent: "×", title: "Hide this button for this video", onclick: (e) => { e.stopPropagation(); ov.closedKey = instKey(v); closeMenu(ov); layout(ov); } }));
    ov.tip = el("div", { className: "tip" }, el("span", { className: "tt" }), el("button", { textContent: "Download" }), el("button", { className: "g", textContent: "Qualities" }), el("button", { className: "tx", textContent: "×", title: "Dismiss" }));
    ov.tip.children[1].onclick = () => quickDownload(ov); ov.tip.children[2].onclick = () => { hideTip(ov); openMenu(ov); }; ov.tip.children[3].onclick = () => hideTip(ov);
    ov.info = el("div", { className: "mi" });
    ov.menu = el("div", { className: "menu" },
      el("div", { className: "mh" }, el("img", { src: ICON }), el("b", { textContent: "AeroGrab · Download this video" }),
        el("button", { textContent: "×", title: "Close", onclick: () => closeMenu(ov) })),
      el("div", { className: "mn" }, ov.nameInput), ov.info, ov.list, ov.foot);
    ov.el = el("div", { className: "ov" }, ov.pill, ov.tip, ov.menu);
    enableOverlayDrag(ov);
    root.append(ov.el);
    overlays.set(v, ov);
    if (typeof ResizeObserver === "function") { ov.ro = new ResizeObserver(wake); ov.ro.observe(v); }
    wake();
  }
  function destroy(ov) { ov.ro?.disconnect(); ov.el.remove(); overlays.delete(ov.v); }

  function shouldShow(ov, r) {
    const v = ov.v;
    if (!v.isConnected || !cfg.overlay) return false;
    if (!ov.played && v.paused && !ov.hover) return false;     // the button appears when the video has started playing - or while the pointer is over it
    if (ov.closedKey && ov.closedKey === instKey(v)) return false;
    if (r.width < MIN_W || r.height < MIN_H) return false;
    const vw = Math.min(r.right, innerWidth) - Math.max(r.left, 0), vh = Math.min(r.bottom, innerHeight) - Math.max(r.top, 0);
    return vw >= MIN_W * 0.8 && vh >= MIN_H * 0.8;
  }

  // Put the button on the video's top-right corner (or where the user dragged it); follows scrolling/resizing.
  function layout(ov) {
    const r = ov.v.getBoundingClientRect();
    if (!shouldShow(ov, r)) { ov.el.style.display = "none"; return false; }
    const k = instKey(ov.v);
    if (k !== ov.key) { ov.key = k; ov.fmt = undefined; ov.fmtMsg = ""; ov.nameDirty = false; if (ov.el.classList.contains("open")) closeMenu(ov); }
    ov.el.style.display = "block";
    ov.el.classList.toggle("compact", cfg.ovCompact);
    const w = ov.pill.offsetWidth || ov.w, h = ov.pill.offsetHeight || ov.h;
    ov.w = w; ov.h = h;
    const L = Math.max(r.left, 0), T = Math.max(r.top, 0), R = Math.min(r.right, innerWidth), B = Math.min(r.bottom, innerHeight);
    const left = clamp(R - ovOff.right - w, L + 2, Math.max(L + 2, R - w - 2));
    const top = clamp(T + ovOff.top, T + 2, Math.max(T + 2, B - h - 2));
    ov.el.style.transform = `translate(${Math.round(left)}px,${Math.round(top)}px)`;
    ov.vis = { L, T, R, B };
    if (ov.el.classList.contains("open")) {  // open the menu on the side with more room
      const below = innerHeight - (top + h) - 12, above = top - 12;
      const up = below < 240 && above > below;
      ov.menu.classList.toggle("up", up);
      ov.menu.classList.toggle("left", left + w - 330 < 4);
      ov.list.style.maxHeight = Math.max(120, Math.min(innerHeight * 0.6, (up ? above : below) - 110)) + "px";
    }
    return true;
  }

  // The position of the button is recomputed only while something moved: a short burst of frames after a scroll / resize / size change, then nothing.
  let looping = false, until = 0;
  function loop() {
    for (const ov of [...overlays.values()]) { if (!ov.v.isConnected) { destroy(ov); continue; } layout(ov); }
    if (performance.now() < until && overlays.size) requestAnimationFrame(loop); else looping = false;
  }
  function wake(ms = 450) { until = Math.max(until, performance.now() + ms); if (!looping && overlays.size) { looping = true; requestAnimationFrame(loop); } }

  function enableOverlayDrag(ov) {
    const pill = ov.pill;
    pill.addEventListener("pointerdown", (e) => {
      if (e.button !== 0 || e.target.closest(".x")) return;
      const sx = e.clientX, sy = e.clientY, r0 = ovOff.right, t0 = ovOff.top;
      let moved = false;
      try { pill.setPointerCapture(e.pointerId); } catch {}
      const move = (m) => {
        if (!moved && Math.abs(m.clientX - sx) + Math.abs(m.clientY - sy) < 5) return;
        moved = true; pill.classList.add("drag");
        const { L, T, R, B } = ov.vis || { L: 0, T: 0, R: innerWidth, B: innerHeight };
        ovOff.right = clamp(r0 - (m.clientX - sx), 0, Math.max(0, R - L - ov.w - 4));
        ovOff.top = clamp(t0 + (m.clientY - sy), 0, Math.max(0, B - T - ov.h - 4));
        layout(ov);
      };
      const up = () => {
        pill.removeEventListener("pointermove", move); pill.removeEventListener("pointerup", up); pill.classList.remove("drag");
        if (moved) api.storage.local.set({ ovOff: { right: ovOff.right, top: ovOff.top } });
        else toggleMenu(ov);
      };
      pill.addEventListener("pointermove", move); pill.addEventListener("pointerup", up);
    });
    pill.addEventListener("dblclick", (e) => {  // back to the top-right corner
      if (e.target.closest(".x")) return;
      Object.assign(ovOff, OV_HOME); api.storage.local.set({ ovOff: { ...OV_HOME } });
      closeMenu(ov); layout(ov);
    });
  }

  // ---- the quality menu
  function toggleMenu(ov) { ov.el.classList.contains("open") ? closeMenu(ov) : openMenu(ov); }
  function closeMenu(ov) { ov.el.classList.remove("open"); }
  async function openMenu(ov) {
    overlays.forEach((o) => o !== ov && closeMenu(o));
    ov.el.classList.add("open");
    hideTip(ov);
    try { window.postMessage({ source: "aerograb-content", type: "ask" }, "*"); } catch {}   // page_hook.js answers with the player's data (YouTube)
    if (!ov.nameDirty) ov.nameInput.value = pickFor(ov.v, ov.fmt || null);
    ov.foot.className = "mf"; ov.foot.textContent = "Pick a quality to send it to AeroGrab.";
    renderList(ov); layout(ov);
    const src = ov.v.currentSrc || ov.v.src || "";
    if (/^https?:/i.test(src)) await send({ cmd: "found", url: src });  // a plain <video src>: make sure it is in the list
    loadItems();
    if (ov.fmt === undefined) {  // ask AeroGrab (yt-dlp) what this page offers: video AND audio formats
      ov.fmt = null;
      const r = await send({ cmd: "formats", url: pageUrlFor(ov.v), referer: location.href });
      ov.fmt = r && r.ok ? r : false;
      ov.fmtMsg = r && !r.ok ? (r.error || "") : (r === undefined ? "no answer" : "");
      ov.speed = r?.speed || 0;
      ov.fmtHint = r && !r.ok ? (r.hint || "") : "";   // v1.8.1: WHY yt-dlp failed, in words (sign-in, outdated, no JavaScript runtime ...)
      if (ov.fmt && !ov.nameDirty) ov.nameInput.value = pickFor(ov.v, ov.fmt);
      if (ov.fmtMsg && !r?.missing && connected(ov.fmtMsg) && !/not a video page/i.test(ov.fmtMsg)) { ov.foot.className = "mf err"; ov.foot.textContent = errorHint(ov.fmtMsg); }
      renderList(ov);
    }
  }

  const etaFor = (ov, size) => {
    const bps = ov.speed || (navigator.connection?.downlink ? navigator.connection.downlink * 125000 : 0);
    return size > 0 && bps > 0 ? "~" + fmtEta(size / bps) : "";
  };

  // Choices for this video.
  //  1) yt-dlp formats (job kind "ytdlp"): AeroGrab downloads best video + best audio and merges them with ffmpeg. Always has sound.
  //  2) ONLY if yt-dlp can't read the page: the streams the browser really loaded, each sent together with its paired audio stream.
  function choicesFor(ov) {
    const name = () => ov.nameInput.value;
    const page = pageUrlFor(ov.v);
    const rows = [];
    const f = ov.fmt;
    if (f && f.ok && (f.formats?.length || f.audio)) {
      for (const x of f.formats || []) {
        rows.push({ label: x.height + "p" + (x.fps > 30 ? x.fps : ""), tag: String(x.ext || "mp4").toUpperCase(), size: x.size, approx: x.approx, sub: "video + sound",
                    job: () => ({ url: page, kind: "ytdlp", quality: x.height, filename: [safeName(name()) || "video", x.height + "p"].join(" "), referer: location.href, meta: metaFor(ov, { height: x.height, ext: String(x.ext || "mp4"), size: x.size }) }) });
      }
      if (f.audio) rows.push({ label: "Audio only", tag: String(f.audio.ext || "m4a").toUpperCase(), size: f.audio.size, approx: f.audio.approx,
                               job: () => ({ url: page, kind: "ytdlp", quality: -1, filename: safeName(name()) || "audio", referer: location.href, meta: metaFor(ov, { ext: String(f.audio.ext || "m4a"), size: f.audio.size, audio: true }) }) });
      return { rows, fallback: false, loading: 0 };
    }
    {   // still asking yt-dlp (or not asked yet): YouTube already told us its quality ladder (page_hook.js) - show that at once, sizes are refined when yt-dlp answers
      const q = ov.fmt === null || ov.fmt === undefined ? ytQuick() : null;
      if (q) {
        for (const x of q.rows) rows.push({ label: x.height + "p" + (x.fps > 30 ? x.fps : ""), tag: "MP4", size: x.size, approx: true, sub: "video + sound",
          job: () => ({ url: page, kind: "ytdlp", quality: x.height, filename: [safeName(name()) || "video", x.height + "p"].join(" "), referer: location.href, meta: metaFor(ov, { height: x.height, ext: "mp4", size: x.size }) }) });
        if (q.audio) rows.push({ label: "Audio only", tag: "M4A", size: q.audio.size, approx: true,
          job: () => ({ url: page, kind: "ytdlp", quality: -1, filename: safeName(name()) || "audio", referer: location.href, meta: metaFor(ov, { ext: "m4a", size: q.audio.size, audio: true }) }) });
        return { rows, fallback: false, loading: 0, quick: true };
      }
      if (ov.fmt === null) return { rows, fallback: false, loading: 0 };   // don't flash raw streams that vanish a second later
    }
    const all = shownItems(), src = ov.v.currentSrc || ov.v.src || "", dur = Number.isFinite(ov.v.duration) ? ov.v.duration : 0;
    const exact = all.filter((it) => src && (it.url === src || it.orig === src || (probes.get(it.url) || {}).useUrl === src));
    const sameLen = all.filter((it) => { const p = probes.get(it.url); return dur && p && p.duration && Math.abs(p.duration - dur) <= 1.5; });
    const mine = exact.length || sameLen.length ? [...new Set([...exact, ...sameLen])] : all.slice(0, 8);
    let loading = 0;
    for (const it of mine) {
      if (it.kind === "hls") {
        const vs = variants.get(it.url);
        if (vs == null) { loading++; continue; }
        if (!vs.length) rows.push({ label: "Original", tag: "HLS", size: 0, job: () => jobFor(it, name()) });
        for (const v of vs) rows.push({ label: v.height ? v.height + "p" + (v.fps > 30 ? v.fps : "") : "Audio / other", tag: "HLS", size: dur ? Math.round(v.bandwidth * dur / 8) : 0, approx: true,
                                       sub: dur ? "" : Math.round(v.bandwidth / 1000) + " kbps", job: () => jobFor(it, name(), { variant: v }) });
      } else if (it.kind === "dash") {
        rows.push({ label: "Best", tag: "DASH", size: 0, sub: "ffmpeg merges the streams", job: () => jobFor(it, name()) });
      } else {
        const p = probes.get(it.url);
        if (p === undefined || p === null) { loading++; continue; }
        if (p && p.segment) continue;
        const audio = audioFor(it);
        const apx = audio ? items.find((x) => x.url === audio) : null;
        const sz = ((p && p.size) || it.size || 0) + (apx ? ((probes.get(apx.url) || {}).size || apx.size || 0) : 0);
        const hasPic = p && p.video;
        rows.push({ label: hasPic ? Math.min(p.width, p.height) + "p" : p && p.audio ? "Audio only" : "Video", tag: audio ? "MP4" : extOf(it.url), size: sz,
                    sub: audio ? "video + sound" : hasPic && !p.audio ? "no sound" : "", job: () => jobFor(it, name()) });
      }
    }
    return { rows, fallback: true, loading };
  }

  function renderList(ov) {
    const { rows: choices, fallback, loading, quick } = choicesFor(ov);
    const out = [];
    const prot = protectedNote(ov);
    ov.info.textContent = [siteName(), CL && ytNow()?.lengthSeconds ? CL.fmtDuration(ytNow().lengthSeconds) : "", ytNow()?.author].filter(Boolean).join(" · ");
    if (prot) { ov.list.replaceChildren(el("div", { className: "note", textContent: prot })); return; }
    if (ov.fmt && ov.fmt.warning) out.push(el("div", { className: "note", textContent: ov.fmt.warning }));
    if (ov.fmt === false && ov.fmtHint) out.push(el("div", { className: "note", textContent: ov.fmtHint }));
    if (choices.length) out.push(el("div", { className: "sep", textContent: fallback ? "Detected on this page" : quick ? "Available qualities (sizes are estimates)" : "Available qualities" }));
    for (const c of choices) {
      const bits = [c.size ? (c.approx ? "≈ " : "") + fmtSize(c.size) : "", etaFor(ov, c.size), c.sub].filter(Boolean).join(" · ");
      const q = el("div", { className: "q", title: "Send to AeroGrab" }, el("span", { className: "ql", textContent: c.label }), el("span", { className: "chip", textContent: c.tag }),
                   el("span", { className: "qs", textContent: bits }), el("span", { className: "go", textContent: "⬇" }));
      q.onclick = async () => {
        q.classList.add("busy");
        const t0 = performance.now();
        const r = await send({ cmd: "send", job: c.job() });   // background adds cookies + user-agent, then hands it to AeroGrab (native messaging / local API)
        const ms = Math.round(performance.now() - t0);
        q.classList.remove("busy");
        if (r?.ok) { ov.foot.className = "mf"; ov.foot.textContent = "Sent to AeroGrab ✔ (" + c.label + ") · " + ms + " ms"; }
        else { ov.foot.className = "mf err"; ov.foot.textContent = errorHint(r?.error); }
      };
      out.push(q);
    }
    if (ov.fmt === null) out.push(el("div", { className: "note", textContent: "Reading the video's streams…" }));
    else if (loading) out.push(el("div", { className: "note", textContent: "Checking detected streams…" }));
    if (!choices.length && ov.fmt !== null && !loading && !(ov.fmt === false && ov.fmtHint)) {
      const missing = ov.fmt === false && /yt-dlp is not installed/i.test(ov.fmtMsg);
      out.push(el("div", { className: "note", textContent: missing
        ? "For every quality on YouTube, Facebook, Instagram and similar sites, install yt-dlp:  pip install yt-dlp  (then restart AeroGrab)."
        : "No stream detected yet. Let the video play for a moment (or switch its quality), then open this menu again." }));
    }
    ov.list.replaceChildren(...out);
  }

  // Protected streams are never offered: no DRM bypass, no workaround - the menu says why.
  function protectedNote(ov) {
    const y = ytNow();
    if (y && (y.drm || (y.status && y.status !== "OK" && y.status !== "LIVE_STREAM_OFFLINE"))) {
      return y.drm ? "This video is DRM-protected. AeroGrab does not download protected content."
        : "YouTube says this video can't be played here" + (y.reason ? " (" + y.reason + ")" : "") + ". It may need a login, or it isn't available to download.";
    }
    const mine = items.filter((it) => it.drm);
    return mine.length && !choicesFor(ov).rows.length ? "This stream is DRM-protected. AeroGrab does not download protected content." : "";
  }

  // ---- instant capture tip: appears under the button as soon as a downloadable resource is known for a video that is playing (once per resource)
  function hideTip(ov) { ov.el.classList.remove("tipon"); ov.pill.classList.remove("pulse"); clearTimeout(ov.tipT); }
  function showTip(ov, text) {
    if (!cfg.toast || ov.el.classList.contains("open") || !layout(ov)) return;
    ov.tip.firstChild.textContent = text;
    ov.el.classList.add("tipon"); ov.pill.classList.remove("pulse"); void ov.pill.offsetWidth; ov.pill.classList.add("pulse");
    clearTimeout(ov.tipT); ov.tipT = setTimeout(() => hideTip(ov), 7000);
  }
  async function quickDownload(ov) {   // the tip's Download: best quality, straight to AeroGrab's dialog
    if (!ov.nameDirty) ov.nameInput.value = pickFor(ov.v, ov.fmt || null);   // the menu may never have been opened: fill in the real name now
    const first = choicesFor(ov).rows[0];
    hideTip(ov);
    if (!first) return openMenu(ov);
    const t0 = performance.now(), r = await send({ cmd: "send", job: first.job() });
    openMenu(ov);
    ov.foot.className = r?.ok ? "mf" : "mf err";
    ov.foot.textContent = r?.ok ? "Sent to AeroGrab ✔ (" + first.label + ") · " + Math.round(performance.now() - t0) + " ms" : errorHint(r?.error);
  }
  function maybeTip(ov) {
    if (!cfg.toast || !ov || !ov.played || toasted.has(instKey(ov.v))) return;
    const { rows } = choicesFor(ov);
    if (!rows.length || protectedNote(ov)) return;
    toasted.add(instKey(ov.v));
    const nm = pickFor(ov.v, ov.fmt || null), r0 = rows[0];
    showTip(ov, "Video detected" + (r0.label && !/^(Original|Best|Video)$/.test(r0.label) ? " · up to " + r0.label : "") + " — " + (nm.length > 42 ? nm.slice(0, 41) + "…" : nm));
  }
  function tipSoon() { clearTimeout(tipSoon.t); tipSoon.t = setTimeout(() => { for (const ov of overlays.values()) if (ov.played) maybeTip(ov); }, 60); }

  // ---------- finding videos: now, and as the page changes ----------
  // Look-ahead: when a video starts playing on a site yt-dlp supports, ask AeroGrab for its qualities right away (only if AeroGrab is already
  // running - this never starts it), so the menu is filled the moment the user opens it.
  const PREFETCH_HOSTS = /(^|\.)(youtube\.com|youtu\.be|facebook\.com|fb\.watch|instagram\.com|tiktok\.com|twitter\.com|x\.com|vimeo\.com|dailymotion\.com|twitch\.tv|reddit\.com|bilibili\.com|rumble\.com)$/i;
  async function prefetch(ov) {
    if (ov.fmt !== undefined || ov.pre === location.href || !PREFETCH_HOSTS.test(location.hostname)) return;
    ov.pre = location.href;
    const r = await send({ cmd: "formats", url: pageUrlFor(ov.v), referer: location.href, prefetch: true });
    if (r && r.ok && ov.fmt === undefined) { ov.fmt = r; ov.speed = r.speed || 0; if (!ov.nameDirty) ov.nameInput.value = pickFor(ov.v, r); renderList(ov); }
  }
  const markPlayed = (v) => { consider(v); const ov = overlays.get(v); if (ov) { ov.played = true; wake(); checkNav(); prefetch(ov); loadItems(); tipSoon(); } };   // v1.8: the look-ahead starts at once, not 400 ms later
  window.addEventListener("playing", (e) => e.target?.tagName === "VIDEO" && markPlayed(e.target), true);
  window.addEventListener("play", (e) => e.target?.tagName === "VIDEO" && markPlayed(e.target), true);
  window.addEventListener("loadstart", (e) => { if (e.target?.tagName === "VIDEO") { consider(e.target); wake(); } }, true);  // reels / playlists swap the source
  let scanTimer = 0;
  function scan() {
    checkNav();
    document.querySelectorAll("video").forEach(consider);
    for (const ov of [...overlays.values()]) if (!ov.v.isConnected) destroy(ov);
    wake();
  }
  const scanSoon = () => { if (!scanTimer) scanTimer = setTimeout(() => { scanTimer = 0; scan(); }, 80); };
  // v1.8: a page like YouTube mutates thousands of nodes; only a newly added <video> (or a subtree that contains one) is worth a re-scan
  new MutationObserver((recs) => {
    for (const r of recs) for (const n of r.addedNodes) if (n.nodeType === 1 && (n.tagName === "VIDEO" || (n.getElementsByTagName && n.getElementsByTagName("video").length))) return scanSoon();
  }).observe(document.documentElement, { childList: true, subtree: true });

  // hover: IDM shows its button as soon as the pointer is over a video, even before it plays. Throttled; no per-frame work.
  let hoverT = 0;
  addEventListener("pointermove", (e) => {
    if (!overlays.size || hoverT || !e.isTrusted) return;
    hoverT = setTimeout(() => { hoverT = 0; }, 90);
    for (const ov of overlays.values()) {
      if (!ov.v.isConnected) continue;
      const r = ov.v.getBoundingClientRect(), inside = e.clientX >= r.left && e.clientX <= r.right && e.clientY >= r.top && e.clientY <= r.bottom;
      if (inside) { clearTimeout(ov.hoverOff); if (!ov.hover) { ov.hover = true; wake(); } ov.hoverOff = setTimeout(() => { ov.hover = false; wake(); }, 1800); }
    }
  }, { capture: true, passive: true });

  // Single-page sites change the address without reloading (YouTube, Instagram, Facebook reels): re-arm every button.
  let lastHref = location.href;
  const checkNav = () => {
    if (location.href === lastHref) return;
    lastHref = location.href;
    items = []; hook.yt = hook.yt && hook.yt.id === ytId() ? hook.yt : null;
    overlays.forEach((ov) => { ov.fmt = undefined; ov.fmtMsg = ""; ov.nameDirty = false; ov.pre = ""; hideTip(ov); closeMenu(ov); });
    scanSoon(); wake(); loadItems();
  };
  // v1.8: no timers. The address change comes from page_hook.js ("nav"), the Navigation API, popstate/hashchange, YouTube's own events, and every scan.
  window.addEventListener("popstate", checkNav); window.addEventListener("hashchange", checkNav);
  for (const t of ["yt-navigate-finish", "yt-page-data-updated"]) document.addEventListener(t, checkNav, true);
  try { window.navigation?.addEventListener("navigatesuccess", checkNav); } catch {}
  for (const t of ["scroll", "resize", "transitionend", "animationend"]) window.addEventListener(t, () => wake(), { capture: true, passive: true });
  window.addEventListener("message", (e) => {   // answers from page_hook.js (it runs in the page's own world)
    if (e.source !== window || !e.data || e.data.source !== "aerograb-hook") return;
    const { type, data } = e.data;
    if (type === "nav") checkNav();
    else if (type === "yt-player" && data && typeof data === "object") { hook.yt = sanitizeYT(data); for (const ov of overlays.values()) { if (ov.el.classList.contains("open")) renderList(ov); } tipSoon(); }
  });
  window.addEventListener("pointerdown", (e) => {  // a click anywhere else closes the menu
    const path = e.composedPath ? e.composedPath() : [];
    if (!path.includes(host)) overlays.forEach(closeMenu);
  }, true);
  window.addEventListener("keydown", (e) => { if (e.key === "Escape") overlays.forEach(closeMenu); }, true);

  // ---------- wiring ----------
  api.runtime.onMessage.addListener((m) => {
    if (m?.cmd === "media-updated") overlays.forEach((ov) => ov.el.classList.contains("open") && refreshSoon());
    if (m?.cmd === "media-found") { loadItems(); setTimeout(tipSoon, 120); }   // the service worker saw a stream: refresh the list, then announce it
  });
  api.storage.onChanged.addListener((ch) => {
    if (ch.overlay) cfg.overlay = ch.overlay.newValue ?? true;
    if (ch.ovCompact) cfg.ovCompact = !!ch.ovCompact.newValue;
    if (ch.toast) cfg.toast = ch.toast.newValue !== false;
    if (ch.ovOff?.newValue) Object.assign(ovOff, ch.ovOff.newValue);
    applyVisibility();
  });
  api.storage.local.get({ overlay: true, ovCompact: false, ovOff: null, toast: true }).then((c) => {
    cfg = { overlay: c.overlay, ovCompact: c.ovCompact, toast: c.toast !== false };
    if (c.ovOff && Number.isFinite(c.ovOff.right) && Number.isFinite(c.ovOff.top)) Object.assign(ovOff, { right: Math.max(0, c.ovOff.right), top: Math.max(0, c.ovOff.top) });
    applyVisibility(); scan();
  });
})();
