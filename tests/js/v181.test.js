const assert = require("assert");
const C = require("../../extension/classify.js");
// octet-stream loaded by a media element, no extension -> media
let r = C.classifyResponse({ url: "https://cdn.test/stream/123", ct: "application/octet-stream", type: "media", total: 5e6 });
assert.strictEqual(r.category, "video");
// same bytes fetched by script (not a media element) stay unlisted
assert.strictEqual(C.classifyResponse({ url: "https://cdn.test/api/123", ct: "application/octet-stream", type: "xmlhttprequest", total: 5e6 }), null);
// mime-less media element response
assert.strictEqual(C.classifyResponse({ url: "https://cdn.test/s/9", ct: "", type: "media" }).category, "video");
// thresholds
assert.strictEqual(C.minSize("video", "video", false), 300 * 1024);
assert.ok(C.minSize("audio", "", false) <= 128 * 1024);
console.log("ok");
