# Changelog

## Rename: OpenDM -> AeroGrab
- App, extension ("AeroGrab Companion"), CLI/binaries (`aerograb`), native host (`org.aerograb.nativehost`), env vars (`AEROGRAB_HOME`, `AEROGRAB_FFMPEG`), repo URL (https://github.com/alter-xsource404/AeroGrab-final-release) and all docs renamed.
- Window title / header: "AeroGrab - The Download Manager You Need". New logo + all icon sizes regenerated.
- `~/.opendm` is moved to `~/.aerograb` on first start. Re-run Browser integration once so the browser finds the renamed native host.
- Firefox add-on id is now `aerograb@alter-xsource404.github.io`.

## 1.8.3 - quality menu closes on download, no floating banner, square button, version in the window
- The "Download this video" quality menu now dismisses the instant a quality is picked (or the tip's Download button is pressed), instead of staying open in the background.
- If the hand-over fails, the menu reopens with the error message so the reason is not lost.
- Removed the separate floating "Video detected - up to ... Download / Qualities / x" banner that popped up when a video was detected or started playing. Nothing is injected into the page apart from the "Download this video" button and its quality menu.
- The "Download this video" button is now a sharp rectangle: `border-radius: 0` on the button, its icon and its hide (x) control.
- Version bumped to **1.8.3** everywhere: app (`__version__`), browser extension (Chrome/Edge and Firefox manifests), Windows file/product version (`version_info.txt`) and installer (`branding.iss`).
- The main window now shows the version next to the app name: header "AeroGrab v1.8.1 - The Download Manager You Need" and the same in the title bar. It reads `__version__`, so it follows every future version bump.
- Removed the now-pointless "Announce detected videos when they start playing" switch from the toolbar popup. The button's quality list still refreshes live as streams are detected.

## 1.8.2 - instant download hand-over
Focus: remove the pause between a download command in the browser and AeroGrab's dialog.

Causes found (browser -> native host -> app path; the app's own server and dialog were already fast):
1. The extension ran its checks one after another before handing the link over: settings, capture rules, window focus, browser name, pause, cookies. Once the 60 s rules cache expired, the next download **waited for a full round trip to AeroGrab** just to re-read the rules.
2. The native host handled `config`/`ping` on its only reader thread, so a slow settings refresh could hold up the `add`.
3. Cold start (AeroGrab not running) polled for readiness every 250 ms.

Fixes:
- Capture rules are served from memory/storage immediately and refreshed in the background (stale-while-revalidate). Rules edited in AeroGrab apply from the next download after the refresh (<= 1 min); `capture-refresh` message forces it.
- Cookies, settings, rules, browser name and window focus are fetched in parallel; focus is tracked from events (no API call); the browser's own copy is paused alongside the hand-over, not in front of it.
- Native host: `config`/`ping`/`start` that carry an id run on worker threads; `add` is never queued behind them. Messages without an id keep their order.
- Cold start polls every 50 ms; the dialog's name/size probe result shows within 60 ms (was 300 ms).
- Tests: `tests/test_v182.py`; `native.test.js` updated for background refresh.

Not measured: no real browser here, so the actual milliseconds saved are unverified. The extension's popup still shows the measured hand-over time.

## 1.8.1
Focus: YouTube and "any site" downloads that actually work, and failures that explain themselves.

**What was and was not tested.** Python (324 tests) and the extension logic (JS suites, stubbed browser) pass. This build was made in a sandbox with no browser and no internet, so **nothing was run against real YouTube / Chrome / Deno / GitHub**. Please run `docs/REAL_BROWSER_CHECKLIST.md`.

### Why YouTube failed (root causes)
1. Since yt-dlp 2025.11 YouTube needs a **JavaScript runtime** (Deno, Node 22+, Bun, QuickJS) and the **yt-dlp-ejs solver**. AeroGrab configured neither, so yt-dlp returned nothing or only 360p.
2. yt-dlp was never updated (`>=2024.8.6`); YouTube changes break old copies within weeks.
3. YouTube's signed links were handed to AeroGrab's own 8-connection engine, which YouTube throttles/refuses. yt-dlp's downloader (10 MB pieces, retries) is what works.
4. The real error was swallowed: the menu said only "No stream detected yet".

### Fixes (app)
- Finds Deno/Node/Bun/QuickJS automatically; if none exists, downloads Deno (official release, checksum-checked when published) into `~/.aerograb/runtime`. Passes `js_runtimes` + `remote_components` to yt-dlp.
- Self-updating yt-dlp: official zipapp, SHA-256 verified, into `~/.aerograb/ytdlp` (checked every 12 h, and once immediately when a failure looks like "out of date"). Settings: `auto_ytdlp_update`, `auto_js_runtime`, `ytdlp_channel` ("stable"/"nightly"); env `AEROGRAB_NO_YTDLP_UPDATE`, `AEROGRAB_NO_RUNTIME_DOWNLOAD`, `AEROGRAB_JS_RUNTIME`.
- YouTube downloads go straight to yt-dlp's downloader (no second lookup). Other sites: AeroGrab's fast engine first, fresh links on expiry, then yt-dlp's downloader if it still fails. Streams needing cookies/odd headers use yt-dlp's downloader up front.
- yt-dlp errors are explained in words (sign-in, age, bot check, region, DRM, no runtime, outdated, network) and shown in the browser menu.
- Progress bar covers video + audio; speed limit applies; `%` in titles no longer breaks names; unnamed links get "Title [id]".
- `requirements.txt`: `yt-dlp[default]>=2025.11.12`; build bundles `yt_dlp_ejs`.

### Fixes (extension)
- Media with unknown size (chunked) was dropped; now kept. Video minimum 2 MB -> 300 KB.
- `application/octet-stream` media loaded by a media element is recognised; direct video tabs and requests from workers (no tab id) are detected.
- HLS/DASH manifests and file probes are fetched with the page's Referer/Origin (temporary per-address `declarativeNetRequest` rule; new permission `declarativeNetRequestWithHostAccess`, Chrome/Edge/Brave).

### Remaining limitations
- IDM is closed source; nothing here is reverse-engineered from it. DRM streams are not downloaded.
- YouTube can still require sign-in/PO tokens for some videos; that is up to yt-dlp and your browser login.
- In a PyInstaller build, whether the downloaded yt-dlp overrides the bundled one is verified at run time but unproven here.

## 1.8.0
Focus: a modular media-detection engine in the extension, YouTube detection that no longer depends on a lucky URL, an instant capture tip, and a leaner browser-to-AeroGrab path. (Versions: app 1.8.0, extension 1.8.0, installer 1.8.0, Windows file version 1.8.0.0.)

**Read this first - what was and was not tested.** This build was developed in a sandbox with no browser, no network, no tkinter and no yt-dlp. Everything below marked *tested* was verified by automated tests against the real extension/host code with stubbed browser APIs (Node), a fake DOM, and a real loopback HTTP server + real native-messaging framing over pipes (Python). **None of it has been run in real Chrome / Edge / Brave, on the real YouTube / Facebook / Instagram / ... sites, or with the Tk dialog.** See "Remaining limitations" and the checklist in `docs/REAL_BROWSER_CHECKLIST.md`.

### Why YouTube was missed (traced in the v1.7 code)
1. The only network-level source was a 2 MB size floor on response headers. YouTube's player fetches a stream in ~0.5-2 MB ranged pieces (`&range=a-b`). Pieces under 2 MB were thrown away (nothing detected); pieces over it were each listed as a separate "stream" (8 pieces -> 8 entries, none a whole file). See the benchmark below.
2. The itag / mime / total size / duration YouTube puts in every `videoplayback` address were never read, so even a kept entry had no resolution and no pairing with its audio.
3. The quality menu depended entirely on yt-dlp finishing (seconds), and when yt-dlp was missing or blocked there was no second source.
4. Single-page navigation (clicking another video) was not seen by the tab-level reset, so the previous video's streams stayed in the list; the content script polled the address every 300 ms to compensate.
5. The look-ahead started on Play and the menu opened a moment later each started their own yt-dlp run (two identical extractions).

### Detection engine (modular)
- `extension/classify.js` (pure functions): response classification by **content-type, Content-Disposition (RFC 6266/5987) and URL** - video, audio, HLS/DASH, image, document, archive, program (EXE/MSI/APK ...), other; segments (.ts/.m4s/.vtt) ignored; per-category minimum sizes; YouTube `videoplayback` parser (itag table -> resolution/fps/codec/container, audio vs video vs muxed, `clen`, `dur`, expiry, range-free stream address, SABR/live flags); HLS master + DASH MPD parsers (qualities, audio renditions, live, **DRM flag**).
- `extension/adapters.js`: one small object per site (YouTube, Facebook, Instagram, TikTok, X/Twitter, Vimeo, Reddit, Dailymotion + generic). Each can describe a stream from its address (role/height/group), map a page to its canonical video address, and read the site's own title/caption from the DOM. Adding a site = adding one object (`AeroGrabAdapters.register`).
- `extension/page_hook.js` (Chrome/Edge/Brave, runs in the page's own world): reports single-page navigation (no polling), YouTube's own description of the current video (title, length, quality ladder, live/DRM/playability status) and MediaSource use. It does **not** wrap fetch/XHR and never touches playback.
- Service worker: YouTube streams are recognised at `webRequest.onBeforeRequest` (before any response header), one entry per stream (not per piece), refreshed addresses update the entry, mp4 video is paired with m4a audio / webm with opus; HLS/DASH manifests are fetched once in the background on detection (qualities, audio, DRM); SPA navigation clears stale entries but keeps a stream that loaded at that instant; tab state is in memory and persisted write-behind (no storage round trip before the page is told); per-class list caps so thumbnails can't evict videos.
- Popup lists **everything detected in the tab** (video/audio/stream/image/document/archive/program) with one-click send, shows the last measured hand-over time, and has switches for the capture tip and image listing.

### Instant capture
- Capture tip: when a video that is playing has a known downloadable resource, a small tip appears under the AeroGrab button ("Video detected - up to 1080p - <title>" with Download / Qualities). Once per resource, 7 s, never steals focus; switch in the popup. *Download* sends the best quality straight to AeroGrab's dialog.
- The button also appears while the pointer is over a video (before Play).
- YouTube quality list appears **immediately** from the player's own data, with sizes marked as estimates, and is refined when yt-dlp answers; downloads from it still go through yt-dlp at download time (always fresh addresses, merging by ffmpeg).
- Removed timers: the 300 ms address poll and the 600 ms wake interval are gone; the position loop runs only for ~450 ms after something moved; the DOM observer only reacts to added `<video>` subtrees.
- Push messages from the service worker (coalesced within 40 ms), look-ahead starts at Play (was +400 ms).

### Browser -> AeroGrab
- Local server: HTTP/1.1 keep-alive, TCP_NODELAY and one buffered write per response (headers and body used to leave as two small segments - a classic delayed-ACK stall on Windows). Unknown paths now answer 404 (they used to be silently dropped).
- Native host: token and port are cached (re-read only when the file changes), one keep-alive connection per thread with one retry if it went stale.
- `/formats` is single-flight: concurrent identical lookups share one yt-dlp run (including shared failures).
- GUI hand-over poll 100 ms -> 25 ms.
- The dialog shows what the browser already knows (quality - format - length - size estimate - site) instead of "Checking...".
- Extension measures every hand-over (`stats`), shown in the popup and in the menu footer ("Sent to AeroGrab (1080p) - 38 ms").

### Names, metadata, DRM
- Title priority: yt-dlp title -> YouTube player title -> site adapter (Instagram caption from `og:description`, tweet text, Reddit post title, TikTok description ...) -> v1.7 chain -> "<Site> video <id>". `Content-Disposition` names are kept for files.
- New `meta` object on every job (site, title, container, height, duration, size, source) - validated and size-limited by `sanitize_meta()`.
- **DRM:** Widevine/PlayReady/FairPlay-protected HLS/DASH manifests and YouTube videos reporting DRM are flagged, shown as protected, and refused by the extension and (second line) by AeroGrab's server. No bypass of any kind.

### Compatibility
- Settings, history, installer `AppId`, native-host name and extension ID unchanged. Existing 290 Python tests and 5 JS suites pass unchanged. Reload the extension after upgrading.
- Manifest: no new permissions. One extra content script with `"world": "MAIN"` (Chrome/Edge/Brave 111+, `minimum_chrome_version` set). Firefox build: shared scripts listed in `background.scripts`; no page hook there (falls back to network sniffing + yt-dlp).

### Measured (loopback / stubbed, see `tools/bench_capture.py` and `tests/js/bench_detect.js`; same harness on v1.7.0 and v1.8.0, this sandbox)
| | v1.7.0 | v1.8.0 |
|---|---|---|
| host message -> job reaches AeroGrab, 300 sequential adds (median / p95) | 0.47 / 0.64 ms | 0.20 / 0.36 ms |
| host message -> reply back to browser (median / p95) | 0.66 / 0.87 ms | 0.33 / 0.60 ms |
| burst of 20 adds, all acknowledged | 13.7 ms | 5.5 ms |
| two simultaneous /formats for one video: yt-dlp runs started | 2 | 1 |
| YouTube 1080p, 8 ranged pieces, headers carry Content-Range: entries listed | 8 (pieces, no height) | 1 (1080p) |
| same, headers carry only the piece size (<2 MB): entries listed | **0 - not detected** | 1 (1080p) |
| awaited storage/tabs round trips before the page is told (YouTube) | 4 | 1 (state restore after a service-worker wake; not awaited on the early path) |
| awaited round trips before the page is told (plain MP4) | 3 | 1 |

These are loopback numbers: they show the overhead the code itself adds, which was already small. They are **not** end-to-end "click Play -> dialog" times. The big end-to-end costs are yt-dlp extraction (seconds, unchanged, now run once and hidden behind the instant list on YouTube), process start-up when AeroGrab is not running (unchanged: the installer's folder build avoids unpacking), and Tk window creation (not measurable here). The Windows delayed-ACK fix cannot show up on Linux loopback; its effect on Windows is unmeasured.

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
- The host now tries `/add` first and starts AeroGrab only if nothing answers (was: ping, then add).
- The content script runs at `document_start` (was `document_idle`), so players created early are seen immediately.
- When a video starts playing on a yt-dlp-supported site, the extension asks AeroGrab for the qualities in the background (only if AeroGrab is already running; it never launches AeroGrab), so the "Download this video" menu is filled when opened.
- Duplicate sniffed streams (e.g. Facebook byte-range pieces) are dropped in memory before any storage or tab lookup.

### Download dialog
- The capture dialog is polled every 100 ms (was 500 ms with the main tick); yt-dlp and ffmpeg lookup are warmed up in the background at start-up.
- *Start Download* starts the transfer immediately (`Manager.kick()`), not at the next tick.

### File names
- New `extension/names.js` + `pick_title()` in AeroGrab: site title -> post caption -> structured data / Open Graph / page metadata -> `Content-Disposition` / URL name -> `<Site> video <id>`. Titles that only name the site ("Facebook", "Reels", "(3) Facebook", "Reel by ...") are rejected, which fixes names like `facebook 1920p.mp4`. The tab title is used only when it is not generic.
- The page caption is read from the post around the video (Facebook/Instagram etc.) on a best-effort basis; when a site exposes nothing usable the descriptive fallback is used.
- `clean_name()` now also strips zero-width/bidi characters, avoids Windows reserved names (CON, NUL, COM1 ...), limits the stem to 120 characters at a word boundary and keeps the extension. Existing duplicate handling still adds `(1)`, `(2)`.

### Size / packaging
- The old build bundled **two ffmpegs** (imageio-ffmpeg's ~80 MB inside the exe, plus the installer's separate 107 MB `ffmpeg.exe`). ffmpeg now ships once, beside `aerograb.exe`.
- The installer packs a program **folder** (`--onedir`) instead of a one-file exe: no unpacking on every start, and the native host starts quickly. `python build.py --portable` still produces the single exe.
- Unused stdlib modules excluded (pydoc, idle, turtle, ...). Generated `build/`, stale `dist/*.exe` and `aerograb.py.patch` are no longer in the source ZIP.

### Compatibility
- Settings, history and the installer `AppId` are unchanged, so upgrading in place keeps them. The native-host name and extension ID are unchanged. The extension must be reloaded after upgrading (it is updated together with the app).
