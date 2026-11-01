# Changelog

## 1.8.0
Focus: a modular media-detection engine in the extension, YouTube detection that no longer depends on a lucky URL, an instant capture tip, and a leaner browser-to-OpenDM path. (Versions: app 1.8.0, extension 1.8.0, installer 1.8.0, Windows file version 1.8.0.0.)

**Read this first - what was and was not tested.** This build was developed in a sandbox with no browser, no network, no tkinter and no yt-dlp. Everything below marked *tested* was verified by automated tests against the real extension/host code with stubbed browser APIs (Node), a fake DOM, and a real loopback HTTP server + real native-messaging framing over pipes (Python). **None of it has been run in real Chrome / Edge / Brave, on the real YouTube / Facebook / Instagram / ... sites, or with the Tk dialog.** See "Remaining limitations" and the checklist in `docs/REAL_BROWSER_CHECKLIST.md`.

### Why YouTube was missed (traced in the v1.7 code)
1. The only network-level source was a 2 MB size floor on response headers. YouTube's player fetches a stream in ~0.5-2 MB ranged pieces (`&range=a-b`). Pieces under 2 MB were thrown away (nothing detected); pieces over it were each listed as a separate "stream" (8 pieces -> 8 entries, none a whole file). See the benchmark below.
2. The itag / mime / total size / duration YouTube puts in every `videoplayback` address were never read, so even a kept entry had no resolution and no pairing with its audio.
3. The quality menu depended entirely on yt-dlp finishing (seconds), and when yt-dlp was missing or blocked there was no second source.
4. Single-page navigation (clicking another video) was not seen by the tab-level reset, so the previous video's streams stayed in the list; the content script polled the address every 300 ms to compensate.
5. The look-ahead started on Play and the menu opened a moment later each started their own yt-dlp run (two identical extractions).

### Detection engine (modular)
- `extension/classify.js` (pure functions): response classification by **content-type, Content-Disposition (RFC 6266/5987) and URL** - video, audio, HLS/DASH, image, document, archive, program (EXE/MSI/APK ...), other; segments (.ts/.m4s/.vtt) ignored; per-category minimum sizes; YouTube `videoplayback` parser (itag table -> resolution/fps/codec/container, audio vs video vs muxed, `clen`, `dur`, expiry, range-free stream address, SABR/live flags); HLS master + DASH MPD parsers (qualities, audio renditions, live, **DRM flag**).
- `extension/adapters.js`: one small object per site (YouTube, Facebook, Instagram, TikTok, X/Twitter, Vimeo, Reddit, Dailymotion + generic). Each can describe a stream from its address (role/height/group), map a page to its canonical video address, and read the site's own title/caption from the DOM. Adding a site = adding one object (`OpenDMAdapters.register`).
- `extension/page_hook.js` (Chrome/Edge/Brave, runs in the page's own world): reports single-page navigation (no polling), YouTube's own description of the current video (title, length, quality ladder, live/DRM/playability status) and MediaSource use. It does **not** wrap fetch/XHR and never touches playback.
- Service worker: YouTube streams are recognised at `webRequest.onBeforeRequest` (before any response header), one entry per stream (not per piece), refreshed addresses update the entry, mp4 video is paired with m4a audio / webm with opus; HLS/DASH manifests are fetched once in the background on detection (qualities, audio, DRM); SPA navigation clears stale entries but keeps a stream that loaded at that instant; tab state is in memory and persisted write-behind (no storage round trip before the page is told); per-class list caps so thumbnails can't evict videos.
- Popup lists **everything detected in the tab** (video/audio/stream/image/document/archive/program) with one-click send, shows the last measured hand-over time, and has switches for the capture tip and image listing.

### Instant capture
- Capture tip: when a video that is playing has a known downloadable resource, a small tip appears under the OpenDM button ("Video detected - up to 1080p - <title>" with Download / Qualities). Once per resource, 7 s, never steals focus; switch in the popup. *Download* sends the best quality straight to OpenDM's dialog.
- The button also appears while the pointer is over a video (before Play).
- YouTube quality list appears **immediately** from the player's own data, with sizes marked as estimates, and is refined when yt-dlp answers; downloads from it still go through yt-dlp at download time (always fresh addresses, merging by ffmpeg).
- Removed timers: the 300 ms address poll and the 600 ms wake interval are gone; the position loop runs only for ~450 ms after something moved; the DOM observer only reacts to added `<video>` subtrees.
- Push messages from the service worker (coalesced within 40 ms), look-ahead starts at Play (was +400 ms).

### Browser -> OpenDM
- Local server: HTTP/1.1 keep-alive, TCP_NODELAY and one buffered write per response (headers and body used to leave as two small segments - a classic delayed-ACK stall on Windows). Unknown paths now answer 404 (they used to be silently dropped).
- Native host: token and port are cached (re-read only when the file changes), one keep-alive connection per thread with one retry if it went stale.
- `/formats` is single-flight: concurrent identical lookups share one yt-dlp run (including shared failures).
- GUI hand-over poll 100 ms -> 25 ms.
- The dialog shows what the browser already knows (quality - format - length - size estimate - site) instead of "Checking...".
- Extension measures every hand-over (`stats`), shown in the popup and in the menu footer ("Sent to OpenDM (1080p) - 38 ms").

### Names, metadata, DRM
- Title priority: yt-dlp title -> YouTube player title -> site adapter (Instagram caption from `og:description`, tweet text, Reddit post title, TikTok description ...) -> v1.7 chain -> "<Site> video <id>". `Content-Disposition` names are kept for files.
- New `meta` object on every job (site, title, container, height, duration, size, source) - validated and size-limited by `sanitize_meta()`.
- **DRM:** Widevine/PlayReady/FairPlay-protected HLS/DASH manifests and YouTube videos reporting DRM are flagged, shown as protected, and refused by the extension and (second line) by OpenDM's server. No bypass of any kind.

### Compatibility
- Settings, history, installer `AppId`, native-host name and extension ID unchanged. Existing 290 Python tests and 5 JS suites pass unchanged. Reload the extension after upgrading.
- Manifest: no new permissions. One extra content script with `"world": "MAIN"` (Chrome/Edge/Brave 111+, `minimum_chrome_version` set). Firefox build: shared scripts listed in `background.scripts`; no page hook there (falls back to network sniffing + yt-dlp).

### Measured (loopback / stubbed, see `tools/bench_capture.py` and `tests/js/bench_detect.js`; same harness on v1.7.0 and v1.8.0, this sandbox)
| | v1.7.0 | v1.8.0 |
|---|---|---|
| host message -> job reaches OpenDM, 300 sequential adds (median / p95) | 0.47 / 0.64 ms | 0.20 / 0.36 ms |
| host message -> reply back to browser (median / p95) | 0.66 / 0.87 ms | 0.33 / 0.60 ms |
| burst of 20 adds, all acknowledged | 13.7 ms | 5.5 ms |
| two simultaneous /formats for one video: yt-dlp runs started | 2 | 1 |
| YouTube 1080p, 8 ranged pieces, headers carry Content-Range: entries listed | 8 (pieces, no height) | 1 (1080p) |
| same, headers carry only the piece size (<2 MB): entries listed | **0 - not detected** | 1 (1080p) |
| awaited storage/tabs round trips before the page is told (YouTube) | 4 | 1 (state restore after a service-worker wake; not awaited on the early path) |
| awaited round trips before the page is told (plain MP4) | 3 | 1 |

These are loopback numbers: they show the overhead the code itself adds, which was already small. They are **not** end-to-end "click Play -> dialog" times. The big end-to-end costs are yt-dlp extraction (seconds, unchanged, now run once and hidden behind the instant list on YouTube), process start-up when OpenDM is not running (unchanged: the installer's folder build avoids unpacking), and Tk window creation (not measurable here). The Windows delayed-ACK fix cannot show up on Linux loopback; its effect on Windows is unmeasured.

### Tests added
`tests/js/classify.test.js`, `youtube.test.js`, `contentload.test.js` (fake DOM), `bench_detect.js`; `tests/test_v180.py`; `tools/bench_capture.py`.

### Remaining limitations
- Nothing was run in a real browser or on real sites (see top). Supported-site list below is what the code is written to handle, not a tested compatibility claim.
- YouTube: since SABR, many players request streams with a POST and no per-stream address; those cannot be listed from the network and are served from the player's quality ladder + yt-dlp. Direct googlevideo addresses that *are* seen expire and can be throttled or refused outside the page; the dependable path is yt-dlp (needs yt-dlp installed). Live streams, premieres, members-only, age-gated and DRM videos depend on yt-dlp/login and are not guaranteed.
- Facebook / Instagram / TikTok / X / Reddit / Vimeo / Dailymotion: addresses and page markup change often; adapters are best-effort, with yt-dlp as the backstop. Private content needs the browser's cookies (sent) and may still fail.
- Blob/MSE players with encrypted segments, and any DRM, are not downloadable by design.
- HLS: master playlists with separate audio renditions are parsed, but the download engine's handling of separate audio groups is unchanged from v1.7 and was not re-tested here. Live HLS is flagged, not specially handled.
- Images are listed in the popup only (never auto-captured). The popup HLS/DASH send uses the best quality, not a chosen one.
- No `declarativeNetRequest` is used (nothing is blocked or redirected, so it would add nothing); no fetch/XHR wrapping (not needed, and it would risk breaking pages).
- `web_accessible_resources`, auto-update and store packaging unchanged.

## 1.7.0
Focus: faster browser capture, faster download dialog, real file names, a leaner build. (Versions: app 1.7.0, extension 1.7.0, installer 1.7.0, Windows file version 1.7.0.0.)

### Browser capture
- **One persistent native-messaging connection** (`connectNative`) replaces a new host process for every message. With the packaged one-file exe, every `ping` / `config` / `add` / `formats` used to unpack and start the whole program (seconds). The connection is opened when the browser starts, so the first capture finds a running host. Replies are matched by id and a slow yt-dlp `formats` lookup runs on its own thread, so a download hand-over is never queued behind it. If the host dies, the next call reconnects once.
- The host now tries `/add` first and starts OpenDM only if nothing answers (was: ping, then add).
- The content script runs at `document_start` (was `document_idle`), so players created early are seen immediately.
- When a video starts playing on a yt-dlp-supported site, the extension asks OpenDM for the qualities in the background (only if OpenDM is already running; it never launches OpenDM), so the "Download this video" menu is filled when opened.
- Duplicate sniffed streams (e.g. Facebook byte-range pieces) are dropped in memory before any storage or tab lookup.

### Download dialog
- The capture dialog is polled every 100 ms (was 500 ms with the main tick); yt-dlp and ffmpeg lookup are warmed up in the background at start-up.
- *Start Download* starts the transfer immediately (`Manager.kick()`), not at the next tick.

### File names
- New `extension/names.js` + `pick_title()` in OpenDM: site title -> post caption -> structured data / Open Graph / page metadata -> `Content-Disposition` / URL name -> `<Site> video <id>`. Titles that only name the site ("Facebook", "Reels", "(3) Facebook", "Reel by ...") are rejected, which fixes names like `facebook 1920p.mp4`. The tab title is used only when it is not generic.
- The page caption is read from the post around the video (Facebook/Instagram etc.) on a best-effort basis; when a site exposes nothing usable the descriptive fallback is used.
- `clean_name()` now also strips zero-width/bidi characters, avoids Windows reserved names (CON, NUL, COM1 ...), limits the stem to 120 characters at a word boundary and keeps the extension. Existing duplicate handling still adds `(1)`, `(2)`.

### Size / packaging
- The old build bundled **two ffmpegs** (imageio-ffmpeg's ~80 MB inside the exe, plus the installer's separate 107 MB `ffmpeg.exe`). ffmpeg now ships once, beside `OpenDM.exe`.
- The installer packs a program **folder** (`--onedir`) instead of a one-file exe: no unpacking on every start, and the native host starts quickly. `python build.py --portable` still produces the single exe.
- Unused stdlib modules excluded (pydoc, idle, turtle, ...). Generated `build/`, stale `dist/*.exe` and `opendm.py.patch` are no longer in the source ZIP.

### Compatibility
- Settings, history and the installer `AppId` are unchanged, so upgrading in place keeps them. The native-host name and extension ID are unchanged. The extension must be reloaded after upgrading (it is updated together with the app).
