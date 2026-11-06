# -*- coding: utf-8 -*-
"""AeroGrab design system: colour tokens, the Dark / Light "Modern Premium" palettes, typography, the icon engine and the
ttk style engine. Standard library only (tkinter is imported lazily, so the CLI never needs it).

How it fits together
  * make_palette(mode, accent, skin) -> a dict of colour tokens (bg, sidebar, surface, elevated, fg, muted, border, accent ...).
    Everything the window draws reads these tokens; nothing in the GUI hard-codes a colour.
  * Theme(root).apply(palette) re-styles every ttk widget, the classic Tk widgets created later (option database), the named
    fonts and the image-based controls (rounded buttons, check boxes, scroll bars). It can be called any number of times, so
    switching Dark <-> Light happens live, without a restart and without touching the download engine.
  * Theme.icon(name, size, tone) returns a PhotoImage of a Lucide-style icon tinted with a palette colour. The glyphs are stored
    as alpha masks (aerograb_icons.py) and tinted at run time, so one data set serves both themes, accents and disabled states.
"""
import base64, math, platform, re, struct, zlib

try:
    from aerograb_icons import DATA as _ICON_DATA, MASK as _ICON_MASK
except ImportError:  # the pack is optional: without it the UI simply has no pictures
    _ICON_DATA, _ICON_MASK = {}, 64

# ============================================================ colour helpers
DEFAULT_ACCENT = "#2563eb"   # "the theme's own accent": Dark uses #3b82f6, Light uses #2563eb, unless the user picked a colour
ACCENTS = (("Blue", "#2563eb"), ("Teal", "#0d9488"), ("Green", "#16a34a"), ("Orange", "#ea580c"), ("Red", "#dc2626"),
           ("Purple", "#7c3aed"), ("Pink", "#db2777"))


def valid_hex(c):
    c = (c or "").strip()
    return c.lower() if re.fullmatch(r"#[0-9a-fA-F]{6}", c) else ""


def _rgb(c):
    return tuple(int(c[i:i + 2], 16) for i in (1, 3, 5))


def mix(a, b, t):
    """Colour a moved a fraction t of the way towards colour b ('#rrggbb')."""
    return "#%02x%02x%02x" % tuple(round(x + (y - x) * t) for x, y in zip(_rgb(a), _rgb(b)))


def luminance(c):
    def lin(v):
        v /= 255.0
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (lin(x) for x in _rgb(c))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(a, b):
    """WCAG contrast ratio between two colours (1.0 - 21.0)."""
    la, lb = luminance(a), luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def contrast_fg(bg):
    """Black or white, whichever is easier to read on `bg`."""
    return "#000000" if luminance(bg) > 0.179 else "#ffffff"


def _ensure_contrast(fg, bg, minimum=4.5):
    """Move fg away from bg (towards black or white) until it reads at least `minimum`:1 on it."""
    target = "#000000" if luminance(bg) > 0.4 else "#ffffff"
    for i in range(101):
        c = mix(fg, target, i * 0.01)
        if contrast_ratio(c, bg) >= minimum:
            return c
    return target


# ============================================================ palettes
# The two Modern Premium themes. Starting points were the brief's palette; muted text, status colours and the filled-accent
# colour were nudged so that every text / background pair used by the UI reaches WCAG AA (4.5:1) - see tests/test_theme.py.
_DARK = dict(mode="dark", bg="#111318", sidebar="#171b23", surface="#1b1f27", elevated="#222834", field="#1b1f27",
             fg="#f1f5f9", muted="#94a3b8", border="#303744", border_strong="#3c4658", grid="#232933",
             hover="#242b37", header_bg="#171b23", button="#222834", button_active="#2b3342",
             accent="#3b82f6", accent_hover="#60a5fa", accent_bg="#2563eb", accent_bg_hover="#3b82f6",
             success="#34d399", warning="#fbbf24", danger="#f87171", icon="#cbd5e1",
             map_bg="#171b23", seg_empty="#232933", seg_border="#3c4658")
_LIGHT = dict(mode="light", bg="#f5f7fa", sidebar="#eef1f5", surface="#ffffff", elevated="#ffffff", field="#ffffff",
              fg="#172033", muted="#586579", border="#e2e8f0", border_strong="#cbd5e1", grid="#edf1f6",
              hover="#eef2f8", header_bg="#f8fafc", button="#ffffff", button_active="#f1f5f9",
              accent="#2563eb", accent_hover="#1d4ed8", accent_bg="#2563eb", accent_bg_hover="#1d4ed8",
              success="#047857", warning="#b45309", danger="#dc2626", icon="#475569",
              map_bg="#eef1f5", seg_empty="#e2e8f0", seg_border="#94a3b8")

# Optional alternative colour schemes (Options > Appearance > Skin). A skin supplies the surfaces; the design system derives the rest.
SKINS = {
    "midnight": ("dark", dict(bg="#0d1117", panel="#161b22", field="#010409", fg="#c9d1d9", muted="#8b949e", border="#30363d", grid="#21262d", button="#21262d",
                              button_active="#30363d", map_bg="#161b22", seg_empty="#21262d", seg_border="#484f58"), "#58a6ff"),
    "nord": ("dark", dict(bg="#2e3440", panel="#3b4252", field="#252a33", fg="#eceff4", muted="#a3adbf", border="#4c566a", grid="#434c5e", button="#434c5e",
                          button_active="#4c566a", map_bg="#3b4252", seg_empty="#434c5e", seg_border="#6b7690"), "#88c0d0"),
    "solarized dark": ("dark", dict(bg="#002b36", panel="#073642", field="#00212b", fg="#93a1a1", muted="#8a9ea0", border="#18505c", grid="#0a3d4a", button="#0a3d4a",
                                    button_active="#14505e", map_bg="#073642", seg_empty="#0a3d4a", seg_border="#586e75"), "#268bd2"),
    "solarized light": ("light", dict(bg="#fdf6e3", panel="#eee8d5", field="#fffdf5", fg="#586e75", muted="#657b83", border="#d8d0b8", grid="#eee8d5", button="#eee8d5",
                                      button_active="#e3dcc2", map_bg="#f5eed8", seg_empty="#eee8d5", seg_border="#93a1a1"), "#268bd2"),
    "forest": ("light", dict(bg="#eef3ec", panel="#dde7d9", field="#fbfdfa", fg="#1f2d22", muted="#4f6657", border="#b9c9b2", grid="#dde7d9", button="#dde7d9",
                             button_active="#cbdbc5", map_bg="#e6eee2", seg_empty="#dde7d9", seg_border="#8aa08f"), "#2f7d4f"),
    "high contrast": ("dark", dict(bg="#000000", panel="#0a0a0a", field="#000000", fg="#ffffff", muted="#d0d0d0", border="#ffffff", grid="#555555", button="#1a1a1a",
                                   button_active="#333333", map_bg="#0a0a0a", seg_empty="#333333", seg_border="#ffffff"), "#ffd400"),
}


def skin_names():
    return ["default"] + list(SKINS)


def make_palette(mode="light", accent=DEFAULT_ACCENT, skin="default"):
    """Every colour the window uses, for 'light' or 'dark' and an accent colour. A skin (see SKINS) replaces the surfaces:
    it decides the mode itself, and supplies its own accent unless the user picked one."""
    accent = valid_hex(accent) or DEFAULT_ACCENT
    sk = SKINS.get(str(skin).lower())
    if sk:
        mode = sk[0]
        accent = sk[2] if accent == DEFAULT_ACCENT else accent
    p = dict(_DARK if mode == "dark" else _LIGHT)
    mode = p["mode"]
    custom_accent = accent != DEFAULT_ACCENT
    if sk:
        p.update(sk[1])
        bg, panel, field, fg = p["bg"], p["panel"], p["field"], p["fg"]
        # derive the tokens a skin does not spell out
        p.update(sidebar=panel, surface=field, elevated=mix(panel, fg, 0.06), header_bg=panel, hover=mix(field, fg, 0.07),
                 border_strong=mix(p["border"], fg, 0.25), icon=mix(fg, bg, 0.12))
        p["success"], p["warning"], p["danger"] = ((_DARK if mode == "dark" else _LIGHT)[k] for k in ("success", "warning", "danger"))
    p["panel"] = p["sidebar"]   # legacy name: the secondary surface
    if custom_accent or sk:
        if mode == "dark":
            p["accent"] = accent if contrast_ratio(accent, p["surface"]) >= 2.8 else mix(accent, "#ffffff", 0.35)
            p["accent_hover"] = mix(p["accent"], "#ffffff", 0.25)
        else:
            p["accent"] = accent if contrast_ratio(accent, p["surface"]) >= 2.8 else mix(accent, "#000000", 0.25)
            p["accent_hover"] = mix(p["accent"], "#000000", 0.2)
        p["accent_bg"] = accent
        for _ in range(12):   # a filled button / selection colour that white (or black) text can sit on
            if contrast_ratio(p["accent_bg"], contrast_fg(p["accent_bg"])) >= 4.5:
                break
            p["accent_bg"] = mix(p["accent_bg"], "#000000" if contrast_fg(p["accent_bg"]) == "#ffffff" else "#ffffff", 0.08)
        p["accent_bg_hover"] = mix(p["accent_bg"], "#ffffff" if mode == "dark" else "#000000", 0.14)
    p["accent_fg"] = contrast_fg(p["accent_bg"])
    # a hover colour for filled accent controls that is visibly different but keeps the label readable (>= 4.5:1)
    toward = "#ffffff" if mode == "dark" else "#000000"
    hov = p["accent_bg"]
    for i in range(1, 41 if mode == "dark" else 8):
        cand = mix(p["accent_bg"], toward, i * 0.015)
        if contrast_ratio(cand, p["accent_fg"]) < 4.5:
            break
        hov = cand
    p["accent_bg_hover"] = hov
    text = p["accent"]   # accent_text: the accent when it is used as text (tabs, links) - nudged until it reads 4.5:1 on every surface; the accent itself stays as chosen
    for surf in (p["surface"], p["sidebar"], p["bg"]):
        text = _ensure_contrast(text, surf, 4.5) if contrast_ratio(text, surf) < 4.5 else text
    p["accent_text"] = text
    # soft tints of the accent: the selected row, badges, progress troughs
    base = p["surface"]
    p["accent_soft"] = mix(base, p["accent"], 0.26 if mode == "dark" else 0.13)
    p["selected"] = p["accent_soft"]
    p["selected_fg"] = p["fg"]
    p["zebra"] = mix(base, p["fg"], 0.022 if mode == "dark" else 0.018)
    p["track"] = mix(p["surface"], p["fg"], 0.12 if mode == "dark" else 0.09)
    p["thumb"] = mix(p["surface"], p["fg"], 0.22 if mode == "dark" else 0.26)
    p["thumb_hover"] = mix(p["surface"], p["fg"], 0.38 if mode == "dark" else 0.42)
    p["focus"] = p["accent"]
    surfaces = (p["bg"], p["sidebar"], p["surface"], p["hover"], p["selected"])
    for k in ("muted", "success", "warning", "danger"):   # these are all used as text: keep them readable (>= 4.5:1) on every surface they can sit on
        for surf in surfaces:
            p[k] = _ensure_contrast(p[k], surf, 4.5)
    p["disabled"] = mix(p["muted"], p["bg"], 0.45)
    p["mode"] = mode
    p["accent_requested"] = accent
    return p


PAL = make_palette("dark")   # the live palette: Theme.apply() replaces its contents in place, so `from aerograb_theme import PAL` stays current


def set_palette(p):
    PAL.clear()
    PAL.update(p)


# ============================================================ typography
FONT_FAMILIES = ("Inter", "Segoe UI Variable Text", "Segoe UI Variable", "Segoe UI", "SF Pro Text", "Helvetica Neue", "Noto Sans", "Ubuntu", "Cantarell", "DejaVu Sans")
MONO_FAMILIES = ("Cascadia Mono", "Cascadia Code", "Consolas", "SF Mono", "Menlo", "DejaVu Sans Mono", "Liberation Mono")


def pick_family(available, wanted=FONT_FAMILIES, fallback="TkDefaultFont"):
    """The first wanted font that is installed (case-insensitive)."""
    have = {a.lower(): a for a in available}
    for w in wanted:
        if w.lower() in have:
            return have[w.lower()]
    return fallback


def semibold_of(family, available):
    """A semibold face when the family ships one as its own family name (Segoe UI Semibold, Inter SemiBold), else None."""
    have = {a.lower(): a for a in available}
    for suffix in (" Semibold", " SemiBold", " Semi Bold"):
        if (family + suffix).lower() in have:
            return have[(family + suffix).lower()]
    return None


# ============================================================ raster engine (pure Python, no Pillow)
def png_rgba(w, h, rgba):
    """Encode raw RGBA bytes as a PNG."""
    stride = w * 4
    raw = b"".join(b"\x00" + bytes(rgba[y * stride:(y + 1) * stride]) for y in range(h))

    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b"")


def _weights(n_src, n_dst):
    scale, out = n_src / n_dst, []
    for i in range(n_dst):
        a, b, j, ws = i * scale, (i + 1) * scale, int(i * scale), []
        while j < b and j < n_src:
            ws.append((j, (min(b, j + 1) - max(a, j)) / scale))
            j += 1
        out.append(ws)
    return out


def resample_alpha(src, n_src, n_dst):
    """Area-average an n_src x n_src alpha mask down (or bilinearly up) to n_dst x n_dst."""
    if n_src == n_dst:
        return bytes(src)
    if n_dst > n_src:   # rare (very high DPI): nearest-neighbour keeps it simple and still looks fine at these sizes
        return bytes(src[min(n_src - 1, y * n_src // n_dst) * n_src + min(n_src - 1, x * n_src // n_dst)] for y in range(n_dst) for x in range(n_dst))
    ws = _weights(n_src, n_dst)
    rows = [[sum(src[r * n_src + j] * w for j, w in col) for col in ws] for r in range(n_src)]
    out = bytearray(n_dst * n_dst)
    for y, col in enumerate(ws):
        for x in range(n_dst):
            out[y * n_dst + x] = min(255, round(sum(rows[j][x] * w for j, w in col)))
    return bytes(out)


def tint_alpha(alpha, color, opacity=1.0):
    """RGBA bytes: `color` everywhere, with the given alpha mask (scaled by opacity)."""
    n = len(alpha)
    r, g, b = _rgb(color)
    buf = bytearray(n * 4)
    buf[0::4], buf[1::4], buf[2::4] = bytes([r]) * n, bytes([g]) * n, bytes([b]) * n
    buf[3::4] = alpha if opacity >= 1 else bytes(round(a * opacity) for a in alpha)
    return buf


class Canvas2D:
    """A tiny anti-aliased RGBA drawing surface (signed-distance shapes), for the few controls that are pictures:
    rounded button backgrounds, check boxes, radio buttons, chevrons."""

    def __init__(self, w, h, bg=None):
        self.w, self.h = w, h
        c = (0, 0, 0, 0) if bg is None else _rgb(bg) + (255,)
        self.px = [list(c) for _ in range(w * h)]

    def _blend(self, i, color, a):
        if a <= 0:
            return
        r, g, b = _rgb(color)
        p = self.px[i]
        oa = p[3] / 255.0
        na = a + oa * (1 - a)
        if na <= 0:
            return
        p[0] = round((r * a + p[0] * oa * (1 - a)) / na)
        p[1] = round((g * a + p[1] * oa * (1 - a)) / na)
        p[2] = round((b * a + p[2] * oa * (1 - a)) / na)
        p[3] = round(na * 255)

    def rrect(self, x0, y0, x1, y1, r, fill=None, outline=None, ow=1.0):
        cx, cy, hx, hy = (x0 + x1) / 2, (y0 + y1) / 2, (x1 - x0) / 2, (y1 - y0) / 2
        r = max(0.0, min(r, hx, hy))
        for y in range(self.h):
            for x in range(self.w):
                qx, qy = abs(x + 0.5 - cx) - (hx - r), abs(y + 0.5 - cy) - (hy - r)
                d = math.hypot(max(qx, 0), max(qy, 0)) + min(max(qx, qy), 0) - r
                outer = min(1.0, max(0.0, 0.5 - d))
                if outer <= 0:
                    continue
                i = y * self.w + x
                if outline:
                    self._blend(i, outline, outer)
                    inner = min(1.0, max(0.0, 0.5 - (d + ow)))
                    if fill and inner > 0:
                        self._blend(i, fill, inner)
                elif fill:
                    self._blend(i, fill, outer)

    def circle(self, cx, cy, r, fill=None, outline=None, ow=1.0):
        self.rrect(cx - r, cy - r, cx + r, cy + r, r, fill, outline, ow)

    def polyline(self, pts, width, color):
        for y in range(self.h):
            for x in range(self.w):
                px, py, best = x + 0.5, y + 0.5, 1e9
                for (ax, ay), (bx, by) in zip(pts, pts[1:]):
                    dx, dy = bx - ax, by - ay
                    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy or 1)))
                    best = min(best, math.hypot(px - (ax + t * dx), py - (ay + t * dy)))
                self._blend(y * self.w + x, color, min(1.0, max(0.0, width / 2 + 0.5 - best)))

    def png(self):
        return png_rgba(self.w, self.h, bytes(v for p in self.px for v in p))


class IconPack:
    """The Lucide glyphs of aerograb_icons.py: scaled on demand, tinted with any colour, returned as PNG bytes."""

    def __init__(self):
        self._raw, self._scaled, self._png = {}, {}, {}

    def has(self, name):
        return name in _ICON_DATA

    def mask(self, name, size):
        key = (name, size)
        if key not in self._scaled:
            if name not in self._raw:
                self._raw[name] = zlib.decompress(base64.b64decode("".join(_ICON_DATA[name])))
            self._scaled[key] = resample_alpha(self._raw[name], _ICON_MASK, size)
        return self._scaled[key]

    def png(self, name, size, color, opacity=1.0):
        key = (name, size, color, round(opacity, 2))
        if key not in self._png:
            self._png[key] = png_rgba(size, size, tint_alpha(self.mask(name, size), color, opacity))
        return self._png[key]


# ============================================================ the ttk style engine
# icon name -> palette token it is tinted with ("icon" = the neutral icon colour). Colour is used selectively.
TONES = {"add": "accent", "resume": "success", "delete": "danger", "startq": "success", "t_all": "accent", "t_unfinished": "accent",
         "t_finished": "success", "st_done": "success", "st_active": "accent", "st_paused": "warning", "st_error": "danger",
         "st_queued": "muted", "st_wait": "muted", "success": "success", "warning": "warning", "error": "danger", "info": "accent",
         "question": "accent", "scan": "success", "stopall": "icon", "close": "muted", "chevron_right": "muted", "chevron_down": "muted"}


class Theme:
    """Binds the design system to a Tk root: fonts, ttk styles, image-based controls, icons. Create once, then apply(palette)."""

    def __init__(self, root, scale=1.0):
        import tkinter as tk
        from tkinter import font as tkfont, ttk
        self.tk, self.tkfont, self.ttk, self.root = tk, tkfont, ttk, root
        self.style = ttk.Style(root)
        self.scale = max(0.75, float(scale))
        self.p = dict(PAL)
        self.icons = IconPack()
        self._img_cache = {}      # (name, size, colour, opacity) -> PhotoImage (kept alive here: Tk drops an image when its Python object dies)
        self._ctl = {}            # image-based control pictures: name -> PhotoImage, re-filled on every apply()
        self._elements = set()    # ttk element names already created (Tk cannot redefine one)
        self._layouts_done = False
        avail = set(tkfont.families(root))
        self.family = pick_family(avail)
        self.semibold = semibold_of(self.family, avail)
        self.mono = pick_family(avail, MONO_FAMILIES, "TkFixedFont")
        self.fonts = {}
        self.build_fonts()

    # ---------------------------------------------------------------- sizes
    def px(self, n):
        """A length in 96-dpi pixels -> real pixels on this display."""
        return max(1, int(round(n * self.scale)))

    # ---------------------------------------------------------------- fonts
    def build_fonts(self):
        f = self.tkfont
        fam = self.family if self.family != "TkDefaultFont" else f.nametofont("TkDefaultFont").actual("family")
        defs = {"body": (fam, 10, "normal"), "small": (fam, 9, "normal"), "bold": ((self.semibold or fam), 10, "normal" if self.semibold else "bold"),
                "heading": ((self.semibold or fam), 11, "normal" if self.semibold else "bold"), "title": ((self.semibold or fam), 15, "normal" if self.semibold else "bold"),
                "brand": ((self.semibold or fam), 14, "normal" if self.semibold else "bold"), "small_bold": ((self.semibold or fam), 9, "normal" if self.semibold else "bold"),
                "mono": (self.mono if self.mono != "TkFixedFont" else f.nametofont("TkFixedFont").actual("family"), 10, "normal")}
        for key, (family, size, weight) in defs.items():
            name = "Aero" + key.title().replace("_", "")
            try:
                font = f.nametofont(name)
                font.configure(family=family, size=size, weight=weight)
            except self.tk.TclError:
                font = f.Font(root=self.root, name=name, family=family, size=size, weight=weight)
            self.fonts[key] = font
        # Tk's own named fonts: every widget that does not name a font follows the design system
        for tkname, key in (("TkDefaultFont", "body"), ("TkTextFont", "body"), ("TkMenuFont", "body"), ("TkHeadingFont", "small_bold"), ("TkCaptionFont", "bold"),
                            ("TkSmallCaptionFont", "small"), ("TkIconFont", "body"), ("TkTooltipFont", "small")):
            try:
                src = self.fonts[key]
                f.nametofont(tkname).configure(family=src.cget("family"), size=src.cget("size"), weight=src.cget("weight"))
            except self.tk.TclError:
                pass
        try:
            f.nametofont("TkFixedFont").configure(family=self.fonts["mono"].cget("family"), size=10)
        except self.tk.TclError:
            pass

    # ---------------------------------------------------------------- icons
    def color_of(self, tone):
        return self.p.get(tone) or self.p["icon"]

    def icon(self, name, size=20, tone=None, opacity=1.0, color=None):
        """A PhotoImage of the icon, `size` 96-dpi pixels square, tinted with a palette token (default: the icon's own tone)."""
        if not self.icons.has(name):
            return self.blank(size)
        col = color or self.color_of(tone or TONES.get(name, "icon"))
        px = self.px(size)
        key = (name, px, col, round(opacity, 2))
        im = self._img_cache.get(key)
        if im is None:
            im = self._img_cache[key] = self.tk.PhotoImage(master=self.root, data=base64.b64encode(self.icons.png(name, px, col, opacity)).decode())
        return im

    def padded_icon(self, name, size=16, tone=None, color=None, left=6, right=8, vert=5):
        """An icon centred on a larger transparent canvas. Tk menus have no padding option, so this is how menu entries get breathing room."""
        col = color or self.color_of(tone or "icon")
        px, l, r, v = self.px(size), self.px(left), self.px(right), self.px(vert)
        key = ("pad", name, px, col, l, r, v)
        im = self._img_cache.get(key)
        if im is None:
            W, H = px + l + r, px + 2 * v
            alpha = bytearray(W * H)
            if self.icons.has(name):
                m = self.icons.mask(name, px)
                for y in range(px):
                    alpha[(y + v) * W + l:(y + v) * W + l + px] = m[y * px:(y + 1) * px]
            im = self._img_cache[key] = self.tk.PhotoImage(master=self.root, data=base64.b64encode(png_rgba(W, H, tint_alpha(bytes(alpha), col))).decode())
        return im

    def blank(self, size=20):
        px = self.px(size)
        key = ("", px, "", 0)
        if key not in self._img_cache:
            self._img_cache[key] = self.tk.PhotoImage(master=self.root, width=px, height=px)
        return self._img_cache[key]

    def image_from_png(self, png):
        return self.tk.PhotoImage(master=self.root, data=base64.b64encode(png).decode())

    # ---------------------------------------------------------------- control pictures
    def _picture(self, name, canvas):
        """Create or refresh the named control picture (a PhotoImage the ttk image elements point at)."""
        data = base64.b64encode(canvas.png()).decode()
        im = self._ctl.get(name)
        if im is None:
            self._ctl[name] = self.tk.PhotoImage(master=self.root, data=data)
        else:
            im.configure(data=data)
        return self._ctl[name]

    def _button_pictures(self, p):
        R, S = self.px(7), self.px(7) * 2 + self.px(4)
        bg = p["bg"]

        def pic(name, fill, outline=None, ring=None):
            c = Canvas2D(S, S, bg)
            if ring:
                c.rrect(0, 0, S, S, R, fill=None, outline=ring, ow=self.px(2))
                c.rrect(self.px(2), self.px(2), S - self.px(2), S - self.px(2), R - self.px(1), fill=fill, outline=outline)
            else:
                c.rrect(0, 0, S, S, R, fill=fill, outline=outline)
            self._picture(name, c)
        # toolbar (flat until hovered)
        pic("tool.normal", bg)
        pic("tool.hover", p["hover"])
        pic("tool.pressed", mix(p["hover"], p["fg"], 0.08))
        pic("tool.focus", bg, ring=p["focus"])
        # secondary buttons
        pic("btn.normal", p["button"], p["border_strong"])
        pic("btn.hover", p["button_active"], p["border_strong"])
        pic("btn.pressed", mix(p["button_active"], p["fg"], 0.06), p["border_strong"])
        pic("btn.disabled", bg, p["border"])
        pic("btn.focus", p["button"], p["border_strong"], ring=p["focus"])
        # primary (filled accent) buttons
        pic("pri.normal", p["accent_bg"], p["accent_bg"])
        pic("pri.hover", p["accent_bg_hover"], p["accent_bg_hover"])
        pic("pri.pressed", mix(p["accent_bg"], "#000000", 0.18), mix(p["accent_bg"], "#000000", 0.18))
        pic("pri.disabled", p["track"], p["track"])
        pic("pri.focus", p["accent_bg"], p["accent_bg"], ring=mix(p["accent"], p["fg"], 0.35))
        self._border_btn = (R, S)

    def _check_pictures(self, p):
        n = self.px(18)

        def box(name, fill, outline, mark=None, dis=False):
            c = Canvas2D(n, n)
            c.rrect(1, 1, n - 1, n - 1, self.px(5), fill=fill, outline=outline, ow=max(1.0, self.scale * 1.2))
            if mark:
                c.polyline([(n * 0.28, n * 0.52), (n * 0.43, n * 0.67), (n * 0.73, n * 0.34)], max(1.6, self.scale * 2.0), mark)
            self._picture(name, c)

        def radio(name, fill, outline, dot=None):
            c = Canvas2D(n, n)
            c.circle(n / 2, n / 2, n / 2 - 1, fill=fill, outline=outline, ow=max(1.0, self.scale * 1.2))
            if dot:
                c.circle(n / 2, n / 2, n * 0.2, fill=dot)
            self._picture(name, c)
        fg_on = p["accent_fg"]
        box("chk.off", p["field"], p["border_strong"])
        box("chk.off.hover", p["field"], p["accent"])
        box("chk.on", p["accent_bg"], p["accent_bg"], fg_on)
        box("chk.on.hover", p["accent_bg_hover"], p["accent_bg_hover"], fg_on)
        box("chk.off.dis", p["bg"], p["border"])
        box("chk.on.dis", p["track"], p["track"], p["muted"])
        radio("rad.off", p["field"], p["border_strong"])
        radio("rad.off.hover", p["field"], p["accent"])
        radio("rad.on", p["field"], p["accent_bg"], p["accent_bg"])
        radio("rad.on.hover", p["field"], p["accent_bg_hover"], p["accent_bg_hover"])
        radio("rad.off.dis", p["bg"], p["border"])
        radio("rad.on.dis", p["bg"], p["border"], p["muted"])

    def _chevron_pictures(self, p):
        n = self.px(14)
        for name, pts in (("chev.right", [(n * 0.38, n * 0.24), (n * 0.64, n * 0.5), (n * 0.38, n * 0.76)]),
                          ("chev.down", [(n * 0.24, n * 0.38), (n * 0.5, n * 0.64), (n * 0.76, n * 0.38)])):
            c = Canvas2D(n, n)
            c.polyline(pts, max(1.4, self.scale * 1.6), p["muted"])
            self._picture(name, c)

    # ---------------------------------------------------------------- apply
    def apply(self, palette):
        """(Re)style everything for this palette. Cheap enough to call on every theme switch."""
        self.p = p = dict(palette)
        set_palette(p)
        self.style.theme_use("clam")   # the one built-in ttk theme every colour can be set on; identical on Windows, macOS and Linux
        self._button_pictures(p)
        self._check_pictures(p)
        self._chevron_pictures(p)
        self._make_elements()
        self._configure(p)
        self._option_database(p)
        self._layouts_done = True

    def _element(self, name, *args, **kw):
        if name not in self._elements:
            self.style.element_create(name, "image", *args, **kw)
            self._elements.add(name)

    def _make_elements(self):
        c, st = self._ctl, self.style
        R, S = self._border_btn
        for key, base in (("tool", "Tool"), ("btn", "Btn"), ("pri", "Pri")):
            normal = c[key + ".normal"]
            self._element(f"{base}.bg", normal, ("disabled", c.get(key + ".disabled", normal)), ("pressed", c[key + ".pressed"]),
                          ("focus", c[key + ".focus"]), ("active", c[key + ".hover"]), border=R, sticky="nswe")
        for key, base in (("chk", "Check"), ("rad", "Radio")):
            self._element(f"Aero{base}.indicator", c[key + ".off"], ("disabled", "selected", c[key + ".on.dis"]), ("disabled", c[key + ".off.dis"]),
                          ("selected", "active", c[key + ".on.hover"]), ("selected", c[key + ".on"]), ("active", c[key + ".off.hover"]), sticky="w")
        blank = self._picture("chev.blank", Canvas2D(self.px(14), self.px(14)))
        self._element("Aero.chev.indicator", c["chev.right"], ("user2", blank), ("user1", c["chev.down"]), sticky="w", width=self.px(18))
        if self._layouts_done:
            return
        pad = self.px
        for style_name, el in (("Tool.TButton", "Tool.bg"), ("TButton", "Btn.bg"), ("Accent.TButton", "Pri.bg")):
            st.layout(style_name, [(el, {"sticky": "nswe", "children": [("Button.padding", {"sticky": "nswe", "children": [("Button.label", {"sticky": "nswe"})]})]})])
        for style_name, base in (("TCheckbutton", "Check"), ("TRadiobutton", "Radio")):
            kind = style_name[1:]
            st.layout(style_name, [(f"{kind}.padding", {"sticky": "nswe", "children": [(f"Aero{base}.indicator", {"side": "left", "sticky": ""}),
                                    (f"{kind}.focus", {"side": "left", "sticky": "w", "children": [(f"{kind}.label", {"sticky": "nswe"})]})]})])
        # slim scroll bars: no arrow buttons, just the thumb
        for orient in ("Vertical", "Horizontal"):
            side = "ns" if orient == "Vertical" else "ew"
            st.layout(f"{orient}.TScrollbar", [(f"{orient}.Scrollbar.trough", {"sticky": side, "children": [(f"{orient}.Scrollbar.thumb", {"expand": "1", "sticky": "nswe"})]})])
        st.layout("Side.Treeview.Item", [("Treeitem.padding", {"sticky": "nswe", "children": [
            ("Aero.chev.indicator", {"side": "left", "sticky": ""}), ("Treeitem.image", {"side": "left", "sticky": ""}),
            ("Treeitem.focus", {"side": "left", "sticky": "", "children": [("Treeitem.text", {"side": "left", "sticky": ""})]})]})])

    def _configure(self, p):
        s, px, F = self.style, self.px, self.fonts
        body, small = F["body"], F["small"]
        s.configure(".", background=p["bg"], foreground=p["fg"], fieldbackground=p["field"], bordercolor=p["border"], darkcolor=p["border"],
                    lightcolor=p["border"], troughcolor=p["surface"], focuscolor=p["focus"], insertcolor=p["fg"], font=body,
                    selectbackground=p["accent_bg"], selectforeground=p["accent_fg"], relief="flat", borderwidth=0)
        s.map(".", foreground=[("disabled", p["disabled"])])
        # ---- labels: one family, a few roles
        for name, kw in (("TLabel", {}), ("Title.TLabel", dict(font=F["title"])), ("Heading.TLabel", dict(font=F["heading"])), ("Bold.TLabel", dict(font=F["bold"])),
                         ("Muted.TLabel", dict(foreground=p["muted"])), ("Small.TLabel", dict(font=small, foreground=p["muted"])),
                         ("Success.TLabel", dict(foreground=p["success"])), ("Danger.TLabel", dict(foreground=p["danger"])),
                         ("Warning.TLabel", dict(foreground=p["warning"])), ("Accent.TLabel", dict(foreground=p["accent_text"])),
                         ("Brand.TLabel", dict(font=F["brand"], foreground=p["fg"])), ("BrandVer.TLabel", dict(font=small, foreground=p["muted"])),
                         ("Tagline.TLabel", dict(font=small, foreground=p["muted"]))):
            s.configure(name, background=p["bg"], **{"foreground": p["fg"], **kw})
        s.configure("Surface.TFrame", background=p["surface"])
        s.configure("Side.TFrame", background=p["sidebar"])
        s.configure("Status.TFrame", background=p["sidebar"])
        s.configure("Status.TLabel", background=p["sidebar"], foreground=p["muted"], font=small)
        s.configure("Card.TFrame", background=p["surface"], bordercolor=p["border"], relief="solid", borderwidth=1)
        s.configure("Surface.TLabel", background=p["surface"])
        s.configure("SurfaceMuted.TLabel", background=p["surface"], foreground=p["muted"])
        # ---- buttons
        for name, fg, fgmap in (("TButton", p["fg"], [("disabled", p["disabled"])]), ("Tool.TButton", p["fg"], [("disabled", p["disabled"])]),
                                ("Accent.TButton", p["accent_fg"], [("disabled", p["muted"])])):
            s.configure(name, foreground=fg, background=p["bg"], padding=(px(14), px(6)), anchor="center", width=-1, font=F["bold"] if name != "Tool.TButton" else small)
            s.map(name, foreground=fgmap)
        s.configure("Tool.TButton", padding=(px(10), px(6)), font=small)
        s.configure("Toolbutton", background=p["bg"])
        s.configure("TMenubutton", background=p["button"], foreground=p["fg"], bordercolor=p["border_strong"], padding=(px(10), px(5)), arrowcolor=p["muted"])
        s.map("TMenubutton", background=[("active", p["button_active"])])
        # ---- text fields
        for name in ("TEntry", "TCombobox", "TSpinbox"):
            s.configure(name, fieldbackground=p["field"], foreground=p["fg"], insertcolor=p["fg"], bordercolor=p["border_strong"], lightcolor=p["field"],
                        darkcolor=p["field"], padding=(px(8), px(5)), selectbackground=p["accent_soft"], selectforeground=p["fg"], borderwidth=1)
            s.map(name, fieldbackground=[("readonly", p["surface"]), ("disabled", p["bg"])], foreground=[("disabled", p["disabled"])],
                  bordercolor=[("focus", p["accent"]), ("hover", p["muted"]), ("disabled", p["border"])],
                  lightcolor=[("focus", p["accent"])], darkcolor=[("focus", p["accent"])])
        for name in ("TCombobox", "TSpinbox"):
            s.configure(name, arrowcolor=p["muted"], background=p["field"], arrowsize=px(14))
            s.map(name, arrowcolor=[("hover", p["fg"]), ("disabled", p["disabled"])], background=[("active", p["field"]), ("readonly", p["surface"])])
        # ---- check / radio
        for name in ("TCheckbutton", "TRadiobutton"):
            s.configure(name, background=p["bg"], foreground=p["fg"], padding=(px(2), px(3)))
            s.map(name, background=[("active", p["bg"])], foreground=[("disabled", p["disabled"])])
        # ---- tabs
        s.configure("TNotebook", background=p["bg"], bordercolor=p["border"], lightcolor=p["bg"], darkcolor=p["bg"], tabmargins=(0, 0, 0, 0))
        s.configure("TNotebook.Tab", background=p["bg"], foreground=p["muted"], padding=(px(16), px(8)), bordercolor=p["bg"], lightcolor=p["bg"], darkcolor=p["bg"], font=F["bold"])
        s.map("TNotebook.Tab", background=[("selected", p["bg"]), ("active", p["hover"])], foreground=[("selected", p["accent_text"]), ("active", p["fg"])],
              lightcolor=[("selected", p["accent"])], bordercolor=[("selected", p["bg"])])
        s.configure("TFrame", background=p["bg"])
        s.configure("TPanedwindow", background=p["bg"])
        s.configure("Sash", sashthickness=px(5), gripcount=0, background=p["bg"], bordercolor=p["bg"], lightcolor=p["bg"], darkcolor=p["bg"])
        s.configure("TLabelframe", background=p["bg"], bordercolor=p["border"], lightcolor=p["border"], darkcolor=p["border"], relief="solid", borderwidth=1)
        s.configure("TLabelframe.Label", background=p["bg"], foreground=p["fg"], font=F["bold"])
        s.configure("TSeparator", background=p["border"])
        s.configure("Horizontal.TProgressbar", background=p["accent"], troughcolor=p["track"], bordercolor=p["track"], lightcolor=p["accent"], darkcolor=p["accent"], thickness=px(8))
        s.configure("TScale", background=p["bg"], troughcolor=p["track"], bordercolor=p["bg"])
        # ---- scroll bars
        for orient in ("Vertical", "Horizontal"):
            n = f"{orient}.TScrollbar"
            s.configure(n, background=p["thumb"], troughcolor=p["surface"], bordercolor=p["surface"], lightcolor=p["thumb"], darkcolor=p["thumb"],
                        gripcount=0, arrowsize=px(11), relief="flat", borderwidth=0)
            s.map(n, background=[("pressed", p["accent"]), ("active", p["thumb_hover"])], lightcolor=[("pressed", p["accent"]), ("active", p["thumb_hover"])],
                  darkcolor=[("pressed", p["accent"]), ("active", p["thumb_hover"])])
        # ---- trees and tables
        s.configure("Treeview", background=p["surface"], fieldbackground=p["surface"], foreground=p["fg"], rowheight=px(26), borderwidth=0, bordercolor=p["surface"],
                    lightcolor=p["surface"], darkcolor=p["surface"], font=body, indent=px(16))
        s.map("Treeview", background=[("selected", p["selected"])], foreground=[("selected", p["selected_fg"])])
        s.configure("Treeview.Heading", background=p["header_bg"], foreground=p["muted"], font=F["small_bold"], relief="flat", padding=(px(10), px(7)), borderwidth=1,
                    bordercolor=p["header_bg"], lightcolor=p["header_bg"], darkcolor=p["border"])
        s.map("Treeview.Heading", background=[("active", p["hover"])], foreground=[("active", p["fg"])])
        s.configure("Main.Treeview", rowheight=px(32))
        s.configure("Side.Treeview", background=p["sidebar"], fieldbackground=p["sidebar"], rowheight=px(32), indent=px(14), bordercolor=p["sidebar"],
                    lightcolor=p["sidebar"], darkcolor=p["sidebar"], font=body)
        s.map("Side.Treeview", background=[("selected", p["selected"])], foreground=[("selected", p["fg"])])
        if self.tk.TkVersion < 8.7 and self.tk.Tcl().eval("info patchlevel").startswith("8.6.9"):   # Tk 8.6.9: tag colours ignore the style map unless it is filtered
            for opt in ("foreground", "background"):
                s.map("Treeview", **{opt: [e for e in s.map("Treeview", query_opt=opt) if e[:2] != ("!disabled", "!selected")]})

    def _option_database(self, p):
        """Colours and fonts for the classic (non-ttk) widgets - menus, text boxes, list boxes, canvases - created from now on."""
        root = self.root
        for pat, val in (("*Toplevel.background", p["bg"]), ("*Toplevel.borderWidth", self.px(10)), ("*Toplevel.relief", "flat"), ("*Frame.background", p["bg"]), ("*Label.background", p["bg"]), ("*Label.foreground", p["fg"]),
                         ("*Text.background", p["field"]), ("*Text.foreground", p["fg"]), ("*Text.insertBackground", p["fg"]),
                         ("*Text.selectBackground", p["accent_soft"]), ("*Text.selectForeground", p["fg"]), ("*Text.relief", "flat"),
                         ("*Text.highlightThickness", 1), ("*Text.highlightBackground", p["border_strong"]), ("*Text.highlightColor", p["accent"]),
                         ("*Text.borderWidth", 0), ("*Text.padX", self.px(8)), ("*Text.padY", self.px(6)), ("*Text.font", self.fonts["body"]),
                         ("*Listbox.background", p["field"]), ("*Listbox.foreground", p["fg"]), ("*Listbox.selectBackground", p["selected"]),
                         ("*Listbox.selectForeground", p["fg"]), ("*Listbox.relief", "flat"), ("*Listbox.highlightThickness", 1),
                         ("*Listbox.highlightBackground", p["border_strong"]), ("*Listbox.highlightColor", p["accent"]), ("*Listbox.borderWidth", 0),
                         ("*Listbox.activestyle", "none"), ("*Listbox.font", self.fonts["body"]),
                         ("*TCombobox*Listbox.background", p["elevated"]), ("*TCombobox*Listbox.foreground", p["fg"]),
                         ("*TCombobox*Listbox.selectBackground", p["selected"]), ("*TCombobox*Listbox.selectForeground", p["fg"]),
                         ("*TCombobox*Listbox.font", self.fonts["body"]), ("*TCombobox*Listbox.relief", "flat"), ("*TCombobox*Listbox.borderWidth", 0),
                         ("*Menu.background", p["elevated"]), ("*Menu.foreground", p["fg"]), ("*Menu.activeBackground", p["selected"]),
                         ("*Menu.activeForeground", p["fg"]), ("*Menu.disabledForeground", p["disabled"]), ("*Menu.relief", "flat"),
                         ("*Menu.borderWidth", 1), ("*Menu.activeBorderWidth", 0), ("*Menu.font", self.fonts["body"]), ("*Menu.selectColor", p["accent"]),
                         ("*Canvas.background", p["surface"]), ("*Canvas.highlightThickness", 0), ("*Spinbox.background", p["field"]),
                         ("*Scale.background", p["bg"]), ("*Scale.troughColor", p["track"])):
            root.option_add(pat, val)

    # ---------------------------------------------------------------- re-colouring widgets that already exist
    def repaint(self, w):
        """Recolour classic Tk widgets that were created before the palette changed (the ttk ones follow their style by themselves)."""
        p, cls = self.p, w.winfo_class()
        try:
            if cls in ("Tk", "Toplevel"):
                w.configure(bg=p["bg"])
            elif cls == "Frame" and not getattr(w, "_keep_bg", False):
                w.configure(bg=p["bg"])
            elif cls == "Label" and not getattr(w, "_keep_bg", False):
                w.configure(bg=p["bg"], fg=p["fg"])
            elif cls == "Canvas" and not getattr(w, "_keep_bg", False):
                w.configure(bg=p["surface"])
            elif cls in ("Text", "Listbox"):
                w.configure(bg=p["field"], fg=p["fg"], highlightbackground=p["border_strong"], highlightcolor=p["accent"])
                if cls == "Text":
                    w.configure(insertbackground=p["fg"], selectbackground=p["accent_soft"], selectforeground=p["fg"])
                else:
                    w.configure(selectbackground=p["selected"], selectforeground=p["fg"])
            elif cls == "Menu":
                w.configure(bg=p["elevated"], fg=p["fg"], activebackground=p["selected"], activeforeground=p["fg"], disabledforeground=p["disabled"], selectcolor=p["accent"])
        except self.tk.TclError:
            pass
        for c in w.winfo_children():
            self.repaint(c)


# ============================================================ Windows niceties
def enable_dpi_awareness():
    """Windows: draw crisp at 125 / 150 / 200 % scaling instead of letting the system stretch a blurry bitmap. Must run before Tk starts."""
    if platform.system() != "Windows":
        return
    import ctypes
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)   # system DPI aware (Tk 8.6 does not understand per-monitor awareness)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def style_titlebar(win, p):
    """Windows 10/11: dark or light title bar to match the theme; on Windows 11 also colour the caption like the window's background."""
    if platform.system() != "Windows":
        return
    try:
        import ctypes
        win.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(win.winfo_id()) or win.winfo_id()
        dwm = ctypes.windll.dwmapi

        def put(attr, value):
            v = ctypes.c_int(value)
            return dwm.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(v), ctypes.sizeof(v))
        dark = 1 if p["mode"] == "dark" else 0
        if put(20, dark) != 0:
            put(19, dark)
        bgr = lambda c: int(c[5:7], 16) << 16 | int(c[3:5], 16) << 8 | int(c[1:3], 16)   # COLORREF is 0x00BBGGRR
        put(35, bgr(p["bg"]))       # DWMWA_CAPTION_COLOR   (Windows 11 only; ignored elsewhere)
        put(36, bgr(p["fg"]))       # DWMWA_TEXT_COLOR
        put(34, bgr(p["border"]))   # DWMWA_BORDER_COLOR
    except Exception:
        pass
