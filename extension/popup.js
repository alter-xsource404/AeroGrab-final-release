// OpenDM toolbar popup (v1.8): switches, connection state, and a list of everything the extension detected in the current tab.
const api = globalThis.browser ?? globalThis.chrome;
const $ = (id) => document.getElementById(id);
const fmtSize = (n) => (n >= 1073741824 ? (n / 1073741824).toFixed(2) + " GB" : n >= 1048576 ? (n / 1048576).toFixed(1) + " MB" : n > 0 ? Math.ceil(n / 1024) + " KB" : "");
const LABEL = { video: "Video", audio: "Audio", stream: "Stream", image: "Image", document: "Document", archive: "Archive", app: "Program", other: "File" };
const nameOf = (m) => {
  if (m.filename) return m.filename;
  try { const p = decodeURIComponent(new URL(m.url).pathname.split("/").pop() || ""); if (p && /\.\w{1,6}$/.test(p)) return p; } catch {}
  return (m.title || m.site || "download") + (m.ext && m.kind === "file" ? "." + m.ext : "");
};
const safe = (s) => String(s).replace(/[\\/:*?"<>|\u0000-\u001f]+/g, " ").replace(/\s+/g, " ").trim().slice(0, 120);

(async () => {
  const c = await api.storage.local.get({ intercept: true, overlay: true, toast: true, detectImages: true });
  $("on").checked = c.intercept; $("ovr").checked = c.overlay; $("tip").checked = c.toast; $("img").checked = c.detectImages;
  $("on").onchange = (e) => api.storage.local.set({ intercept: e.target.checked });
  $("ovr").onchange = (e) => api.storage.local.set({ overlay: e.target.checked });
  $("tip").onchange = (e) => api.storage.local.set({ toast: e.target.checked });
  $("img").onchange = (e) => api.storage.local.set({ detectImages: e.target.checked });
  api.runtime.sendMessage({ cmd: "status" }).then((s) => {
    $("conn").textContent = s?.mode === "native" || s?.mode === "manual"
      ? "OpenDM: connected \u2714" + (s.mode === "native" && !s.running ? " (starts when needed)" : "")
      : "OpenDM: not connected. Open OpenDM once to set it up.";
  }).catch(() => {});
  api.runtime.sendMessage({ cmd: "stats" }).then((s) => {
    const last = (s?.sends || []).filter((x) => x.ok).pop();
    if (last) $("perf").textContent = "Last hand-over to OpenDM: " + last.ms + " ms (browser \u2192 OpenDM's reply).";
  }).catch(() => {});
  $("opt").onclick = () => { api.runtime.openOptionsPage(); window.close(); };

  const [tab] = await api.tabs.query({ active: true, currentWindow: true });
  const list = $("list");
  if (!tab || tab.id == null) { list.innerHTML = ""; return; }
  let items = [];
  try { items = (await api.runtime.sendMessage({ cmd: "list", tabId: tab.id })) || []; } catch {}
  // one row per resource: audio halves belong to their video, per-quality HLS playlists are hidden when their master is listed
  items = items.filter((m) => m.role !== "audio" || m.category === "audio").reverse();
  list.replaceChildren();
  if (!items.length) { const d = document.createElement("div"); d.className = "none"; d.textContent = "Nothing detected yet. Press play on a video, or reload the page."; list.append(d); return; }
  for (const m of items.slice(0, 60)) {
    const row = document.createElement("div"); row.className = "it"; row.title = m.url;
    const t = document.createElement("span"); t.className = "t"; t.textContent = m.drm ? "\uD83D\uDD12 " + nameOf(m) + " (DRM-protected)" : nameOf(m);
    const chip = document.createElement("span"); chip.className = "chip"; chip.textContent = (LABEL[m.category] || "File") + (m.height ? " " + m.height + "p" : "") + (m.kind === "hls" ? " HLS" : m.kind === "dash" ? " DASH" : "");
    const s = document.createElement("span"); s.className = "s"; s.textContent = [fmtSize(m.size), m.expired ? "expired" : ""].filter(Boolean).join(" ");
    row.append(chip, t, s);
    if (!m.drm && !m.expired) row.onclick = async () => {
      row.classList.add("busy");
      const base = m.kind === "file" ? nameOf(m) : safe(m.title || m.site || "video");
      const job = { url: m.url, referer: m.page || tab.url || "", filename: base, kind: m.kind === "file" ? undefined : m.kind, audioUrl: m.audioUrl || undefined, meta: { site: m.site || "", title: safe(m.title || ""), ext: m.ext || "", height: m.height || 0, size: m.size || 0, source: "stream" } };
      const r = await api.runtime.sendMessage({ cmd: "send", job });
      row.classList.remove("busy");
      $("msg").textContent = r?.ok ? "Sent to OpenDM \u2714" : (r?.error || "Could not reach OpenDM");
    };
    list.append(row);
  }
})();
