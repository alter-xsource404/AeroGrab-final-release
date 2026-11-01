// OpenDM v1.8 - website adapters. One entry per site; adding a site = adding one object to ADAPTERS (nothing else changes).
//
//   id / name       short id, display name
//   page            RegExp tested against the PAGE hostname
//   cdn             RegExp tested against the hostname of a media REQUEST (lets the service worker label a stream before any header arrives)
//   videoPage(url)  the address OpenDM (yt-dlp) should read for a page/post URL: { id, url } or null
//   request(u, ct)  a request's URL -> extra facts about that stream { role, height, group, ... } (or null = nothing special)
//   dom(doc, video) the page's own title / caption / extra facts for the <video>, read from the DOM (content script only)
//
// request() runs in the service worker for EVERY media response, so it must be cheap and must not throw.
(function (g) {
  "use strict";
  const C = () => g.OpenDMClassify;
  const txt = (e) => (e && (e.innerText || e.textContent) || "").replace(/\s+/g, " ").trim();
  const meta = (doc, sel) => doc.querySelector(sel)?.content || "";
  const b64json = (s) => { try { return JSON.parse(atob(s.replace(/-/g, "+").replace(/_/g, "/"))); } catch { return null; } };
  const idFrom = (u, re) => { try { const m = re.exec(new URL(u).pathname + new URL(u).search); return m ? m[1] : ""; } catch { return ""; } };

  const ADAPTERS = [
    {
      id: "youtube", name: "YouTube",
      page: /(^|\.)(youtube\.com|youtu\.be|youtube-nocookie\.com)$/i, cdn: /(^|\.)googlevideo\.com$/i,
      videoPage: (u) => C().youtubeWatchUrl(u),
      request(u) {
        const r = C().parseGoogleVideo(u.href);
        if (!r) return null;
        // YouTube serves picture and sound as separate adaptive streams, in many small ranged pieces; the range-free address is the whole stream.
        return { site: "youtube", url: r.canonical, role: r.muxed ? "both" : r.isAudio ? "audio" : "video", height: r.height, fps: r.fps, codec: r.codec, itag: r.itag, ext: r.ext,
                 size: r.clen, duration: r.dur, live: r.live, sabr: r.sabr, group: "yt", expire: r.expire };
      },
      dom(doc) {
        return { titles: [meta(doc, "meta[name='title']"), txt(doc.querySelector("h1.ytd-watch-metadata, ytd-watch-metadata h1, h1.title")), meta(doc, "meta[property='og:title']")],
                 author: txt(doc.querySelector("ytd-channel-name a, #owner #channel-name a")) };
      },
    },
    {
      id: "facebook", name: "Facebook", page: /(^|\.)(facebook\.com|fb\.watch|fb\.com)$/i, cdn: /(^|\.)(fbcdn\.net|facebook\.com)$/i,
      videoPage(u) { const id = idFrom(u, /(?:\/reel\/|\/videos\/(?:[^/]+\/)?|[?&]v=|\/watch\/\?v=)(\d{6,})/); return id ? { id, url: u } : null; },
      request(u) {
        const efg = u.searchParams.get("efg"), tag = efg ? String(b64json(efg)?.vencode_tag || "") : "";
        if (!tag) return null;
        const h = /(\d{3,4})p/.exec(tag);
        return { site: "facebook", role: /audio|heaac|aac|opus/i.test(tag) ? "audio" : "video", height: h ? +h[1] : 0, group: "fb" };
      },
      dom: (doc) => ({ titles: [meta(doc, "meta[property='og:title']"), meta(doc, "meta[property='og:description']")] }),
    },
    {
      id: "instagram", name: "Instagram", page: /(^|\.)instagram\.com$/i, cdn: /(^|\.)(cdninstagram\.com|fbcdn\.net)$/i,
      videoPage(u) { const m = /\/(reels?|p|tv)\/([\w-]+)/.exec(new URL(u).pathname); return m ? { id: m[2], url: u } : null; },
      request(u) {
        const efg = u.searchParams.get("efg"), tag = efg ? String(b64json(efg)?.vencode_tag || "") : "";
        if (!tag) return null;
        const h = /(\d{3,4})p/.exec(tag);
        return { site: "instagram", role: /audio|heaac|aac|opus/i.test(tag) ? "audio" : "video", height: h ? +h[1] : 0, group: "ig" };
      },
      // og:description is "123 likes, 4 comments - user on March 3, 2025: "the caption"."
      dom(doc) {
        const d = meta(doc, "meta[property='og:description']"), q = /:\s*["\u201c](.+?)["\u201d]\.?\s*$/s.exec(d);
        return { titles: [q ? q[1] : "", meta(doc, "meta[property='og:title']")] };
      },
    },
    {
      id: "tiktok", name: "TikTok", page: /(^|\.)tiktok\.com$/i, cdn: /(^|\.)(tiktokcdn[\w-]*\.com|tiktokv\.com|ttwstatic\.com|byteoversea\.com|muscdn\.com)$/i,
      videoPage(u) { const id = idFrom(u, /\/video\/(\d+)/); return id ? { id, url: u } : null; },
      request: () => ({ site: "tiktok", group: "tt" }),
      dom: (doc) => ({ titles: [txt(doc.querySelector("[data-e2e='browse-video-desc'], [data-e2e='video-desc']")), meta(doc, "meta[property='og:title']"), meta(doc, "meta[property='og:description']")] }),
    },
    {
      id: "twitter", name: "X (Twitter)", page: /(^|\.)(twitter\.com|x\.com)$/i, cdn: /(^|\.)twimg\.com$/i,
      videoPage(u) { const id = idFrom(u, /\/status\/(\d+)/); return id ? { id, url: u } : null; },
      // video.twimg.com/ext_tw_video/<id>/pu/vid/avc1/1280x720/<name>.mp4  - the size is in the path
      request(u) { const m = /\/(\d{3,4})x(\d{3,4})\//.exec(u.pathname); return { site: "twitter", group: "tw", height: m ? Math.min(+m[1], +m[2]) : 0 }; },
      dom(doc, v) { const art = v?.closest?.("article"); return { titles: [txt(art?.querySelector("[data-testid='tweetText']")), meta(doc, "meta[property='og:description']")] }; },
    },
    {
      id: "vimeo", name: "Vimeo", page: /(^|\.)vimeo\.com$/i, cdn: /(^|\.)(vimeocdn\.com|akamaized\.net)$/i,
      videoPage(u) { const id = idFrom(u, /\/(?:video\/)?(\d{5,})/); return id ? { id, url: u } : null; },
      request: () => ({ site: "vimeo", group: "vm" }),
      dom: (doc) => ({ titles: [meta(doc, "meta[property='og:title']"), txt(doc.querySelector("h1"))] }),
    },
    {
      id: "reddit", name: "Reddit", page: /(^|\.)reddit\.com$/i, cdn: /(^|\.)(redd\.it|redditmedia\.com)$/i,
      videoPage(u) { const m = /\/comments\/(\w+)/.exec(new URL(u).pathname); return m ? { id: m[1], url: u } : null; },
      // v.redd.it/<id>/DASH_720.mp4 (picture only) + DASH_audio.mp4 / DASH_AUDIO_128.mp4 (sound)
      request(u) {
        const m = /\/([\w]+)\/DASH_(\w+)\.mp4/i.exec(u.pathname);
        if (!m) return /\.m3u8$/i.test(u.pathname) ? { site: "reddit", group: "rd" } : null;
        const audio = /^audio/i.test(m[2]);
        return { site: "reddit", role: audio ? "audio" : "video", height: audio ? 0 : +m[2] || 0, group: "rd:" + m[1] };
      },
      dom(doc, v) { const post = v?.closest?.("shreddit-post, article, [data-testid='post-container']"); return { titles: [post?.getAttribute?.("post-title") || "", txt(post?.querySelector("h1, h2, h3, [slot='title']")), meta(doc, "meta[property='og:title']")] }; },
    },
    {
      id: "dailymotion", name: "Dailymotion", page: /(^|\.)(dailymotion\.com|dai\.ly)$/i, cdn: /(^|\.)(dmcdn\.net|dailymotion\.com)$/i,
      videoPage(u) { const id = idFrom(u, /\/video\/(\w+)/); return id ? { id, url: u } : null; },
      request: () => ({ site: "dailymotion", group: "dm" }),
      dom: (doc) => ({ titles: [meta(doc, "meta[property='og:title']"), txt(doc.querySelector("h1"))] }),
    },
  ];

  const hostOf = (u) => { try { return new URL(u).hostname.toLowerCase(); } catch { return ""; } };
  const GENERIC = { id: "generic", name: "", page: /./, cdn: null, videoPage: () => null, request: () => null, dom: (doc) => ({ titles: [meta(doc, "meta[property='og:title']"), meta(doc, "meta[name='twitter:title']"), txt(doc.querySelector("h1"))] }) };

  const forPage = (url) => { const h = hostOf(url); return ADAPTERS.find((a) => a.page.test(h)) || GENERIC; };
  const forRequest = (url) => { const h = hostOf(url); return ADAPTERS.find((a) => a.cdn && a.cdn.test(h)) || null; };
  function describeRequest(url) {
    const a = forRequest(url);
    if (!a) return null;
    try { return a.request(new URL(url)) || null; } catch { return null; }
  }
  const register = (a) => { ADAPTERS.unshift(a); };   // a site can be added at run time (tests, future adapters)

  g.OpenDMAdapters = { ADAPTERS, GENERIC, forPage, forRequest, describeRequest, register };
  if (typeof module !== "undefined" && module.exports) module.exports = g.OpenDMAdapters;
})(typeof globalThis !== "undefined" ? globalThis : this);
