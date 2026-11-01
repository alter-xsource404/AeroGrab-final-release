// OpenDM v1.8 - media classification core (pure functions: no DOM, no chrome.* calls; unit-tested in tests/js/classify.test.js).
// Loaded by the service worker (importScripts / Firefox "scripts") and by tests (require). Everything hangs off globalThis.OpenDMClassify.
//
//  classifyResponse()   one HTTP response (url + headers)  -> what is it?  (video / audio / stream / image / document / archive / app / other)
//  parseContentDisposition()   RFC 6266 / 5987 file names
//  parseGoogleVideo()   a YouTube "videoplayback" URL        -> itag, mime, size, duration, canonical (range-free) URL
//  parseHlsMaster() / parseMpd()   manifests -> qualities, audio renditions, and a DRM flag (DRM-protected streams are never offered)
(function (g) {
  "use strict";

  const LIST = (s) => new Set(s.split(" "));
  const EXT = {
    video: LIST("mp4 m4v webm mkv mov avi flv wmv 3gp 3g2 ogv mpg mpeg m2ts mts f4v"),
    audio: LIST("mp3 m4a aac wav flac ogg oga opus wma weba mka aiff aif amr mp2"),
    image: LIST("jpg jpeg png webp gif avif bmp svg ico heic heif tif tiff jfif"),
    document: LIST("pdf doc docx xls xlsx ppt pptx odt ods odp rtf txt epub mobi azw3 csv djvu cbz cbr"),
    archive: LIST("zip rar 7z tar gz tgz bz2 xz zst iso cab lz lzma"),
    app: LIST("exe msi apk apks xapk aab dmg pkg deb rpm appimage msix msixbundle bat cmd jar"),
  };
  const SEGMENT_EXT = LIST("ts m4s cmfv cmfa cmft m2t webvtt vtt srt aac_seg");
  const MIME_EXT = {
    "video/mp4": "mp4", "video/webm": "webm", "video/x-matroska": "mkv", "video/quicktime": "mov", "video/x-flv": "flv", "video/3gpp": "3gp", "video/ogg": "ogv",
    "video/x-msvideo": "avi", "video/x-ms-wmv": "wmv", "video/mpeg": "mpg", "audio/mpeg": "mp3", "audio/mp3": "mp3", "audio/mp4": "m4a", "audio/x-m4a": "m4a", "audio/aac": "aac",
    "audio/ogg": "ogg", "audio/webm": "weba", "audio/flac": "flac", "audio/x-flac": "flac", "audio/wav": "wav", "audio/x-wav": "wav", "audio/opus": "opus",
    "image/jpeg": "jpg", "image/png": "png", "image/webp": "webp", "image/gif": "gif", "image/avif": "avif", "image/bmp": "bmp", "image/heic": "heic",
    "application/pdf": "pdf", "application/zip": "zip", "application/x-zip-compressed": "zip", "application/vnd.rar": "rar", "application/x-rar-compressed": "rar",
    "application/x-7z-compressed": "7z", "application/gzip": "gz", "application/x-tar": "tar", "application/vnd.android.package-archive": "apk",
    "application/x-msdownload": "exe", "application/x-msi": "msi", "application/epub+zip": "epub",
    "application/msword": "doc", "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "application/vnd.ms-excel": "xls", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
    "application/vnd.ms-powerpoint": "ppt", "application/vnd.openxmlformats-officedocument.presentationml.presentation": "pptx",
  };
  const HLS_CT = /mpegurl/i, DASH_CT = /dash\+xml/i;

  const catOfExt = (e) => { for (const k of Object.keys(EXT)) if (EXT[k].has(e)) return k; return ""; };
  const extOfPath = (s) => { const m = /\.([a-z0-9]{1,8})$/i.exec(String(s || "").split(/[?#]/)[0]); return m ? m[1].toLowerCase() : ""; };
  const lowerCt = (ct) => String(ct || "").split(";")[0].trim().toLowerCase();

  // ---- Content-Disposition: filename*=UTF-8''%e2%82%ac.mp4 beats filename="x.mp4"
  function parseContentDisposition(h) {
    h = String(h || "");
    if (!h) return { type: "", filename: "" };
    const type = (/^\s*([a-z]+)/i.exec(h) || [])[1]?.toLowerCase() || "";
    let name = "";
    const star = /filename\*\s*=\s*([^;]+)/i.exec(h);
    if (star) {
      const m = /^\s*([\w-]+)'[^']*'(.*)$/.exec(star[1].trim());
      try { name = decodeURIComponent((m ? m[2] : star[1]).replace(/^"|"$/g, "")); } catch { name = (m ? m[2] : star[1]).replace(/^"|"$/g, ""); }
    }
    if (!name) {
      const q = /filename\s*=\s*"((?:[^"\\]|\\.)*)"/i.exec(h) || /filename\s*=\s*([^;]+)/i.exec(h);
      if (q) { name = q[1].trim().replace(/\\(.)/g, "$1"); try { if (/%[0-9a-f]{2}/i.test(name)) name = decodeURIComponent(name); } catch {} }
    }
    return { type, filename: name.replace(/[\\/]+/g, "_").trim() };
  }

  // ---- one HTTP response -> media record skeleton (or null when it is not something to offer)
  // in: { url, ct, cd, total (bytes, 0 if unknown), type (webRequest resourceType) }
  function classifyResponse({ url, ct, cd, total = 0, type = "" }) {
    const mime = lowerCt(ct), disp = parseContentDisposition(cd), path = (() => { try { return new URL(url).pathname; } catch { return String(url).split(/[?#]/)[0]; } })();
    const pext = extOfPath(path);
    if (HLS_CT.test(mime) || pext === "m3u8") return { category: "stream", kind: "hls", ext: "m3u8", mime, size: 0 };
    if (DASH_CT.test(mime) || pext === "mpd") return { category: "stream", kind: "dash", ext: "mpd", mime, size: 0 };
    if (SEGMENT_EXT.has(pext) || /^(video\/(mp2t|iso\.segment)|audio\/(aac_seg)|text\/vtt)/.test(mime)) return { category: "segment", kind: "segment", ext: pext, mime, size: total };
    const dext = extOfPath(disp.filename);
    const mext = MIME_EXT[mime] || "";
    // what the server calls it wins over what the URL looks like
    const ext = dext || mext || (mime === "application/octet-stream" || mime === "binary/octet-stream" || !mime || mime.startsWith("application/") ? pext : "");
    let category = catOfExt(ext) || (mime.startsWith("video/") ? "video" : mime.startsWith("audio/") ? "audio" : mime.startsWith("image/") ? "image" : "");
    if (!category && disp.type === "attachment") category = "other";
    if (!category) return null;
    if (category === "image" && type && type !== "image" && type !== "media" && type !== "xmlhttprequest" && type !== "other") return null;
    return { category, kind: "file", ext: ext || (category === "video" ? "mp4" : category === "audio" ? "m4a" : ""), mime, filename: disp.filename, attachment: disp.type === "attachment", size: total };
  }

  // minimum size worth listing, per category (a 1x1 tracking pixel or a 40 KB "preview" clip is not a download)
  function minSize(category, role, piece) {
    if (piece) return 0;
    return { video: 2 * 1024 * 1024, audio: role === "audio" ? 16 * 1024 : 256 * 1024, image: 60 * 1024, document: 1024, archive: 1024, app: 1024, other: 1024 }[category] ?? 1024;
  }

  // ================= YouTube =================
  // itag -> what the stream is. Only values that are fixed by YouTube's format table; unknown itags fall back to the mime type.
  const V = (h, fps, codec, ext) => ({ video: true, height: h, fps, codec, ext });
  const A = (kbps, codec, ext) => ({ audio: true, kbps, codec, ext });
  const ITAG = {
    18: { ...V(360, 30, "avc1", "mp4"), muxed: true }, 22: { ...V(720, 30, "avc1", "mp4"), muxed: true },
    160: V(144, 30, "avc1", "mp4"), 133: V(240, 30, "avc1", "mp4"), 134: V(360, 30, "avc1", "mp4"), 135: V(480, 30, "avc1", "mp4"), 136: V(720, 30, "avc1", "mp4"),
    137: V(1080, 30, "avc1", "mp4"), 264: V(1440, 30, "avc1", "mp4"), 266: V(2160, 30, "avc1", "mp4"), 298: V(720, 60, "avc1", "mp4"), 299: V(1080, 60, "avc1", "mp4"),
    278: V(144, 30, "vp9", "webm"), 242: V(240, 30, "vp9", "webm"), 243: V(360, 30, "vp9", "webm"), 244: V(480, 30, "vp9", "webm"), 247: V(720, 30, "vp9", "webm"),
    248: V(1080, 30, "vp9", "webm"), 271: V(1440, 30, "vp9", "webm"), 313: V(2160, 30, "vp9", "webm"), 302: V(720, 60, "vp9", "webm"), 303: V(1080, 60, "vp9", "webm"),
    308: V(1440, 60, "vp9", "webm"), 315: V(2160, 60, "vp9", "webm"),
    394: V(144, 30, "av01", "mp4"), 395: V(240, 30, "av01", "mp4"), 396: V(360, 30, "av01", "mp4"), 397: V(480, 30, "av01", "mp4"), 398: V(720, 30, "av01", "mp4"),
    399: V(1080, 30, "av01", "mp4"), 400: V(1440, 30, "av01", "mp4"), 401: V(2160, 30, "av01", "mp4"), 402: V(4320, 30, "av01", "mp4"),
    139: A(48, "mp4a", "m4a"), 140: A(128, "mp4a", "m4a"), 141: A(256, "mp4a", "m4a"), 249: A(50, "opus", "webm"), 250: A(70, "opus", "webm"), 251: A(160, "opus", "webm"),
  };
  const GV_HOST = /(^|\.)googlevideo\.com$/i;

  function parseGoogleVideo(url) {
    let u; try { u = new URL(url); } catch { return null; }
    if (!GV_HOST.test(u.hostname) || !/\/videoplayback\b/.test(u.pathname)) return null;
    const p = u.searchParams, itag = +p.get("itag") || 0, mime = decodeURIComponent(p.get("mime") || ""), info = ITAG[itag] || null;
    const isAudio = /^audio\//i.test(mime) || !!(info && info.audio);
    const live = p.get("source") === "yt_live_broadcast" || p.has("sq") || p.get("live") === "1";
    const sabr = p.get("sabr") === "1" || p.get("ump") === "1";
    for (const k of ["range", "rn", "rbuf", "rbuf", "alr", "cmo", "ump", "srfvp", "sabr"]) p.delete(k);   // per-chunk parameters: dropping them names the whole stream
    return {
      itag, mime, isAudio, live, sabr, muxed: !!(info && info.muxed), canonical: u.href,
      clen: +p.get("clen") || 0, dur: +p.get("dur") || 0, height: info?.height || 0, fps: info?.fps || 0, codec: info?.codec || (/codecs/.test(mime) ? mime : ""),
      kbps: info?.kbps || 0, ext: info?.ext || (/webm/.test(mime) ? "webm" : isAudio ? "m4a" : "mp4"),
      key: p.get("id") || p.get("ei") || "", expire: +p.get("expire") || 0,
    };
  }

  // The watch-page address for any YouTube URL form (the address yt-dlp / OpenDM should be given), or "".
  function youtubeWatchUrl(u) {
    try {
      const x = new URL(u), h = x.hostname.replace(/^(www|m|music)\./, "");
      let id = "";
      if (h === "youtu.be") id = x.pathname.split("/")[1] || "";
      else if (/(^|\.)youtube(-nocookie)?\.com$/.test(h)) {
        if (x.pathname === "/watch") id = x.searchParams.get("v") || "";
        else { const m = /^\/(shorts|live|embed|v)\/([\w-]{6,})/.exec(x.pathname); if (m) id = m[2]; }
      }
      return /^[\w-]{6,20}$/.test(id) ? { id, url: "https://www.youtube.com/watch?v=" + id } : null;
    } catch { return null; }
  }

  // ================= manifests =================
  const iso8601 = (s) => { const m = /^P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:([\d.]+)S)?$/i.exec(String(s || "")); return m ? (+m[1] || 0) * 86400 + (+m[2] || 0) * 3600 + (+m[3] || 0) * 60 + (+m[4] || 0) : 0; };
  const attrs = (s) => { const o = {}; for (const m of String(s).matchAll(/([A-Za-z_:][\w:.-]*)\s*=\s*("([^"]*)"|'([^']*)')/g)) o[m[1]] = m[3] ?? m[4]; return o; };

  // HLS master playlist -> { variants:[{height,bandwidth,fps,codecs,url,audioGroup}], audios:[{group,name,lang,url}], drm, live }
  function parseHlsMaster(text, base) {
    const lines = String(text || "").split(/\r?\n/), out = { variants: [], audios: [], drm: false, master: false, live: false };
    const abs = (u) => { try { return new URL(u.trim(), base).href; } catch { return u.trim(); } };
    if (/#EXT-X-(SESSION-)?KEY:[^\n]*(METHOD=SAMPLE-AES[^\n]*KEYFORMAT="?(com\.apple\.streamingkeydelivery|urn:uuid:(edef8ba9|9a04f079)|com\.microsoft\.playready|com\.widevine)|KEYFORMAT="?(com\.apple\.streamingkeydelivery|urn:uuid:(edef8ba9|9a04f079)|com\.microsoft\.playready|com\.widevine))/i.test(text)) out.drm = true;
    lines.forEach((l, i) => {
      if (l.startsWith("#EXT-X-STREAM-INF:")) {
        out.master = true;
        const a = Object.fromEntries([...l.slice(18).matchAll(/([A-Z0-9-]+)=("[^"]*"|[^,]*)/g)].map((m) => [m[1], m[2].replace(/"/g, "")]));
        const uri = lines.slice(i + 1).find((x) => x.trim() && !x.startsWith("#"));
        if (uri) out.variants.push({ height: +(a.RESOLUTION?.split("x")[1] || 0), width: +(a.RESOLUTION?.split("x")[0] || 0), bandwidth: +(a.BANDWIDTH || 0), fps: a["FRAME-RATE"] ? Math.round(+a["FRAME-RATE"]) : 0, codecs: a.CODECS || "", audioGroup: a.AUDIO || "", url: abs(uri) });
      } else if (l.startsWith("#EXT-X-MEDIA:")) {
        const a = Object.fromEntries([...l.slice(13).matchAll(/([A-Z0-9-]+)=("[^"]*"|[^,]*)/g)].map((m) => [m[1], m[2].replace(/"/g, "")]));
        if (a.TYPE === "AUDIO" && a.URI) out.audios.push({ group: a["GROUP-ID"] || "", name: a.NAME || "", lang: a.LANGUAGE || "", url: abs(a.URI), def: a.DEFAULT === "YES" });
      }
    });
    if (!out.master && /#EXTINF/.test(text) && !/#EXT-X-ENDLIST/.test(text)) out.live = true;   // a media playlist that never ends = live stream
    const seen = new Set();
    out.variants = out.variants.filter((v) => { const k = v.height + "/" + v.bandwidth; return !seen.has(k) && seen.add(k); }).sort((x, y) => y.height - x.height || y.bandwidth - x.bandwidth);
    return out;
  }

  // MPEG-DASH manifest -> { drm, live, duration, videos:[{id,height,width,bandwidth,fps,codecs}], audios:[{id,bandwidth,codecs,lang}] }  (regex based: DOMParser doesn't exist in a service worker)
  function parseMpd(text) {
    text = String(text || "");
    const root = attrs((/<MPD\b([^>]*)>/i.exec(text) || [])[1] || "");
    const out = { drm: /<ContentProtection\b/i.test(text), live: root.type === "dynamic", duration: iso8601(root.mediaPresentationDuration), videos: [], audios: [] };
    for (const set of text.matchAll(/<AdaptationSet\b([^>]*)>([\s\S]*?)<\/AdaptationSet>/gi)) {
      const sa = attrs(set[1]);
      for (const rep of set[2].matchAll(/<Representation\b([^>]*?)\/?>/gi)) {
        const ra = attrs(rep[1]), mime = (ra.mimeType || sa.mimeType || "").toLowerCase(), ctype = (sa.contentType || (mime.split("/")[0]) || "").toLowerCase();
        const fr = ra.frameRate || sa.frameRate || "", fps = fr.includes("/") ? Math.round(fr.split("/")[0] / (fr.split("/")[1] || 1)) : Math.round(+fr || 0);
        const row = { id: ra.id || "", bandwidth: +ra.bandwidth || 0, codecs: ra.codecs || sa.codecs || "", height: +(ra.height || sa.height) || 0, width: +(ra.width || sa.width) || 0, fps, lang: sa.lang || "" };
        if (ctype === "video") out.videos.push(row); else if (ctype === "audio") out.audios.push(row);
      }
    }
    out.videos.sort((a, b) => b.height - a.height || b.bandwidth - a.bandwidth);
    return out;
  }

  const fmtDuration = (s) => { s = Math.round(+s || 0); if (!s) return ""; const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), x = s % 60; return (h ? h + ":" + String(m).padStart(2, "0") : m) + ":" + String(x).padStart(2, "0"); };

  g.OpenDMClassify = { classifyResponse, parseContentDisposition, minSize, parseGoogleVideo, youtubeWatchUrl, parseHlsMaster, parseMpd, extOfPath, catOfExt, fmtDuration, ITAG, MIME_EXT };
  if (typeof module !== "undefined" && module.exports) module.exports = g.OpenDMClassify;
})(typeof globalThis !== "undefined" ? globalThis : this);
