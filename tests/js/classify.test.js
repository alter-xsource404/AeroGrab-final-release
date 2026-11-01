// classify.js + adapters.js: pure-function tests (response classification, Content-Disposition, YouTube URLs, HLS/DASH manifests, DRM flags, site adapters)
const assert = require("assert"), path = require("path");
const C = require(path.join(__dirname, "../../extension/classify.js"));
const AD = require(path.join(__dirname, "../../extension/adapters.js"));
const ok = (m) => console.log("PASS", m);

// ---- response classification: not only by extension
let r = C.classifyResponse({ url: "https://x.test/dl?id=7", ct: "application/octet-stream", cd: "attachment; filename*=UTF-8''my%20file.zip", total: 9e6 });
assert.deepStrictEqual([r.category, r.ext, r.filename, r.attachment], ["archive", "zip", "my file.zip", true]);
r = C.classifyResponse({ url: "https://x.test/api/v1/stream?token=abc", ct: "video/mp4", total: 9e6 }); assert.deepStrictEqual([r.category, r.ext], ["video", "mp4"]);
r = C.classifyResponse({ url: "https://x.test/a", ct: "audio/mpeg" }); assert.strictEqual(r.ext, "mp3");
r = C.classifyResponse({ url: "https://x.test/doc", ct: "application/pdf" }); assert.deepStrictEqual([r.category, r.ext], ["document", "pdf"]);
r = C.classifyResponse({ url: "https://x.test/p.webp", ct: "image/webp", type: "image" }); assert.strictEqual(r.category, "image");
r = C.classifyResponse({ url: "https://x.test/setup", ct: "application/x-msdownload" }); assert.deepStrictEqual([r.category, r.ext], ["app", "exe"]);
r = C.classifyResponse({ url: "https://x.test/m", ct: "application/x-mpegURL" }); assert.deepStrictEqual([r.kind, r.category], ["hls", "stream"]);
r = C.classifyResponse({ url: "https://x.test/manifest?x=1", ct: "application/dash+xml" }); assert.strictEqual(r.kind, "dash");
for (const [u, ct] of [["https://x.test/s1.ts", "video/MP2T"], ["https://x.test/s1.m4s", "video/mp4"], ["https://x.test/a.vtt", "text/vtt"]]) assert.strictEqual(C.classifyResponse({ url: u, ct }).category, "segment", u);
assert.strictEqual(C.classifyResponse({ url: "https://x.test/api", ct: "application/json" }), null);
assert.strictEqual(C.classifyResponse({ url: "https://x.test/file", ct: "application/octet-stream" }), null);          // no name, no attachment: unknown binary blob is not offered
r = C.classifyResponse({ url: "https://x.test/file", ct: "application/octet-stream", cd: 'attachment; filename="r.bin"' }); assert.strictEqual(r.category, "other");
ok("responses classified by content-type / Content-Disposition, not only by URL extension; segments and JSON ignored");

assert.strictEqual(C.parseContentDisposition('attachment; filename="a\\"b.mp4"').filename, 'a"b.mp4');
assert.strictEqual(C.parseContentDisposition("attachment; filename=plain.pdf; size=3").filename, "plain.pdf");
assert.strictEqual(C.parseContentDisposition("attachment; filename=x.txt; filename*=utf-8''%E2%82%AC.txt").filename, "\u20ac.txt");
assert.strictEqual(C.parseContentDisposition('attachment; filename="../../evil.exe"').filename, ".._.._evil.exe");
ok("Content-Disposition: RFC 5987 beats plain, quotes unescaped, path separators neutralised");

// ---- YouTube
const gv = "https://rr1---sn-abc.googlevideo.com/videoplayback?expire=2000000000&id=o-XYZ&itag=";
let y = C.parseGoogleVideo(gv + "137&mime=video%2Fmp4&clen=52428800&dur=212.04&range=0-1048575&rn=5&rbuf=12000&sig=S");
assert.deepStrictEqual([y.itag, y.height, y.fps, y.isAudio, y.clen, y.ext], [137, 1080, 30, false, 52428800, "mp4"]);
assert(!/range=|rn=|rbuf=/.test(y.canonical) && /sig=S/.test(y.canonical));
assert.strictEqual(C.parseGoogleVideo(gv + "140&mime=audio%2Fmp4&clen=3000000").isAudio, true);
assert.strictEqual(C.parseGoogleVideo(gv + "22&mime=video%2Fmp4").muxed, true);
assert.strictEqual(C.parseGoogleVideo(gv + "251&mime=audio%2Fwebm").ext, "webm");
assert.strictEqual(C.parseGoogleVideo(gv + "299&mime=video%2Fmp4").fps, 60);
assert.strictEqual(C.parseGoogleVideo("https://rr1---sn-abc.googlevideo.com/videoplayback?sabr=1&id=1").sabr, true);
assert.strictEqual(C.parseGoogleVideo("https://example.com/videoplayback?itag=18"), null);
ok("YouTube videoplayback: itag -> resolution/fps/codec, audio/muxed, size, range pieces stripped, SABR flagged");
for (const [u, id] of [["https://youtu.be/dQw4w9WgXcQ?t=3", "dQw4w9WgXcQ"], ["https://m.youtube.com/shorts/abcDEF12345", "abcDEF12345"], ["https://www.youtube.com/watch?v=abcDEF12345&list=PL1", "abcDEF12345"], ["https://www.youtube.com/live/abcDEF12345", "abcDEF12345"]])
  assert.strictEqual(C.youtubeWatchUrl(u).id, id, u);
assert.strictEqual(C.youtubeWatchUrl("https://www.youtube.com/feed/subscriptions"), null);
ok("every YouTube address form maps to one canonical watch URL");

// ---- manifests
const master = `#EXTM3U\n#EXT-X-MEDIA:TYPE=AUDIO,GROUP-ID="a",NAME="English",LANGUAGE="en",DEFAULT=YES,URI="aud/en.m3u8"\n#EXT-X-STREAM-INF:BANDWIDTH=800000,RESOLUTION=640x360,AUDIO="a"\nv/360.m3u8\n#EXT-X-STREAM-INF:BANDWIDTH=2800000,RESOLUTION=1280x720,FRAME-RATE=60.000,AUDIO="a"\nv/720.m3u8\n`;
let h = C.parseHlsMaster(master, "https://cdn.test/p/master.m3u8");
assert.deepStrictEqual(h.variants.map((v) => [v.height, v.fps, v.url]), [[720, 60, "https://cdn.test/p/v/720.m3u8"], [360, 0, "https://cdn.test/p/v/360.m3u8"]]);
assert.strictEqual(h.audios[0].url, "https://cdn.test/p/aud/en.m3u8"); assert.strictEqual(h.drm, false);
h = C.parseHlsMaster(master + '#EXT-X-SESSION-KEY:METHOD=SAMPLE-AES,URI="skd://x",KEYFORMAT="com.apple.streamingkeydelivery"\n', "https://cdn.test/m.m3u8"); assert.strictEqual(h.drm, true);
h = C.parseHlsMaster('#EXTM3U\n#EXT-X-KEY:METHOD=AES-128,URI="k.key"\n#EXTINF:4,\ns1.ts\n#EXT-X-ENDLIST\n', "https://cdn.test/m.m3u8"); assert.deepStrictEqual([h.drm, h.live], [false, false]);   // plain AES-128 is NOT DRM
h = C.parseHlsMaster("#EXTM3U\n#EXTINF:4,\ns1.ts\n", "https://cdn.test/m.m3u8"); assert.strictEqual(h.live, true);
ok("HLS: variants sorted/resolved, audio renditions, SAMPLE-AES/FairPlay flagged as DRM, plain AES-128 is not, live detected");
const mpd = `<MPD type="static" mediaPresentationDuration="PT1H2M3.5S"><Period><AdaptationSet contentType="video" mimeType="video/mp4"><Representation id="v1" bandwidth="900000" width="640" height="360" codecs="avc1.4d401e" frameRate="30"/><Representation id="v2" bandwidth="3000000" width="1280" height="720" codecs="avc1.64001f" frameRate="60000/1001"/></AdaptationSet><AdaptationSet mimeType="audio/mp4" lang="en"><Representation id="a1" bandwidth="128000" codecs="mp4a.40.2"/></AdaptationSet></Period></MPD>`;
let m = C.parseMpd(mpd);
assert.deepStrictEqual([m.videos.map((v) => v.height), m.audios.length, m.drm, m.live, m.duration, m.videos[0].fps], [[720, 360], 1, false, false, 3723.5, 60]);
m = C.parseMpd(mpd.replace("<Period>", '<Period><ContentProtection schemeIdUri="urn:uuid:edef8ba9-79d6-4ace-a3c8-27dcd51d21ed"/>')); assert.strictEqual(m.drm, true);
ok("DASH: representations, audio sets, duration, frame-rate fractions; Widevine ContentProtection flagged as DRM");

// ---- adapters
assert.deepStrictEqual(AD.describeRequest("https://v.redd.it/abc/DASH_480.mp4?source=fallback"), { site: "reddit", role: "video", height: 480, group: "rd:abc" });
assert.strictEqual(AD.describeRequest("https://v.redd.it/abc/DASH_audio.mp4").role, "audio");
assert.strictEqual(AD.describeRequest("https://video.twimg.com/ext_tw_video/1/pu/vid/avc1/1280x720/x.mp4").height, 720);
const efg = Buffer.from(JSON.stringify({ vencode_tag: "dash_ln_heaac_vbr3_audio" })).toString("base64");
assert.strictEqual(AD.describeRequest("https://video.xx.fbcdn.net/o1/v/t2/f2/x.mp4?efg=" + encodeURIComponent(efg)).role, "audio");
assert.strictEqual(AD.forPage("https://www.youtube.com/watch?v=1").id, "youtube"); assert.strictEqual(AD.forPage("https://unknown.example/").id, "generic");
assert.strictEqual(AD.forPage("https://x.com/u/status/1").videoPage("https://x.com/u/status/12345").id, "12345");
AD.register({ id: "demo", name: "Demo", page: /(^|\.)demo\.test$/, cdn: /(^|\.)democdn\.test$/, videoPage: () => null, request: () => ({ site: "demo", role: "video" }), dom: () => ({ titles: [] }) });
assert.strictEqual(AD.describeRequest("https://a.democdn.test/x.mp4").site, "demo");
ok("adapters: Reddit/Twitter/Facebook request facts, page routing, a new site registers without touching anything else");
