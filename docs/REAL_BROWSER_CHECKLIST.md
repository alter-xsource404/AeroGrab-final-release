# Real-browser checklist for v1.8.0

v1.8.0 was verified with automated tests only (stubbed browser APIs, a fake DOM, a loopback server). Please run these once in real Chrome, Edge and Brave
(Windows, installed build) and report what differs. Reload the extension first (`chrome://extensions` -> reload) and restart AeroGrab.

## Setup
- [ ] AeroGrab running, **Browser setup** shows the host registered; extension popup says "AeroGrab: connected".
- [ ] `pip install yt-dlp` (or the bundled one) is available to AeroGrab; ffmpeg next to aerograb.exe.

## YouTube (the main fix)
- [ ] Open a normal video, press Play. Within ~0.5 s a tip "Video detected - up to <res>p - <title>" appears under the AeroGrab button.
- [ ] Open the menu: qualities appear at once (sizes marked as estimates); a second later sizes are refined (yt-dlp). Only heights that really exist are shown.
- [ ] Click a quality: AeroGrab's dialog opens with the real video title as file name, quality/format/length in the size line. Start Download -> mp4 with sound.
- [ ] Click another video in the sidebar (no page reload): old qualities disappear, the new video's tip appears.
- [ ] A Short (`/shorts/ID`), an embedded player (`youtube-nocookie.com/embed/ID`), a playlist item, a live stream, a members-only / age-gated video (logged in).
- [ ] DRM / rented movie: the menu says it is protected and offers nothing.
- [ ] Popup: the tab lists the googlevideo streams that were seen (if any) - note whether any appear in your browser at all (SABR).

## Other sites (note: detected? title right? quality list right? download works?)
- [ ] Facebook video + reel (caption used as file name)  - [ ] Instagram reel/post  - [ ] TikTok  - [ ] X/Twitter video  - [ ] Vimeo  - [ ] Reddit (v.redd.it, with sound)  - [ ] Dailymotion
- [ ] A site with a plain `<video src=file.mp4>`, an HLS site, a DASH site.
- [ ] A direct-download page (ZIP/EXE/PDF): browser download is taken over as before; popup lists them.

## Speed (the numbers that matter - please send them)
- [ ] Popup footer / menu footer: "Sent to AeroGrab ... N ms" for 5 captures with AeroGrab already running. (Expected: tens of ms or less.)
- [ ] Stopwatch: click the tip's Download -> AeroGrab dialog visible, with AeroGrab running; then with AeroGrab closed (it is started by the host).
- [ ] DevTools > Performance, YouTube playing 60 s: note CPU of the page and of the extension's service worker (chrome://extensions > service worker > inspect).
- [ ] Hover over a video before Play: the button appears; it does not appear on tiny videos/ads thumbnails.

## Regression
- [ ] Right-click "Download link with AeroGrab"; Alt-click prevents capture; excluded sites; the "Download this video" switch.
- [ ] Nothing breaks playback, the page layout, fullscreen (button moves into the fullscreen element).
