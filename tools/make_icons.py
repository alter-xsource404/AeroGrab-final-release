#!/usr/bin/env python3
"""Regenerates every icon from code. Needs Pillow:  pip install pillow
Run from the repo root:  python tools/make_icons.py
Writes assets/icon.{png,ico,icns}, extension/icons/icon{16,32,48,128}.png and
refreshes the embedded app icon and header brand marks inside aerograb.py (the UI icons are Lucide: see tools/build_icons.py) and extension/content.js."""
import base64, io, re
from pathlib import Path
import math
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
S = 1024  # master canvas; everything is drawn big and scaled down for crisp edges


def _bez(p0, p1, p2, n=40):
    return [((1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t * t * p2[0], (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t * t * p2[1]) for t in [i / n for i in range(n + 1)]]


def _fill(canvas, poly, c1, c2, vertical=True, blur=0):
    """Paint polygon `poly` (already in canvas px) with a linear gradient c1 -> c2 on `canvas`."""
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).polygon(poly, fill=255)
    if blur:
        mask = mask.filter(ImageFilter.GaussianBlur(blur))
    g = Image.linear_gradient("L").resize((S, S))
    if not vertical:
        g = g.rotate(-90)
    layer = Image.composite(Image.new("RGB", (S, S), c2), Image.new("RGB", (S, S), c1), g).convert("RGBA")
    layer.putalpha(mask)
    canvas.alpha_composite(layer)


def master():
    """AeroGrab mark: a cyan 'A' with a swoosh orbiting it and a download arrow, on a deep navy tile."""
    top, bot = (16, 38, 112), (8, 14, 52)
    g = Image.linear_gradient("L").resize((S, S))
    bg = Image.composite(Image.new("RGB", (S, S), bot), Image.new("RGB", (S, S), top), g).convert("RGBA")
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).rounded_rectangle((40, 40, S - 40, S - 40), radius=210, fill=255)
    bg.putalpha(mask)

    k, ox, oy = 1.06, 410, 355
    T = lambda pts: [((x - ox) * k + 512, (y - oy) * k + 505) for x, y in pts]  # logo-space -> canvas

    # soft glow behind the mark
    glow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse((150, 150, 874, 874), fill=(40, 140, 255, 70))
    bg.alpha_composite(glow.filter(ImageFilter.GaussianBlur(90)))

    # the A: one solid with a triangular counter, left leg bright, right leg dark
    A = _bez((345, 95), (400, 40), (500, 55)) + [(560, 150), (770, 628), (650, 628), (480, 322), (420, 205), (140, 650), (15, 650), (345, 95)]
    A = _bez((345, 95), (385, 50), (465, 55), 20) + _bez((465, 55), (520, 52), (555, 110), 20) + [(770, 628), (650, 628), (480, 325), (420, 205), (140, 650), (15, 650)]
    _fill(bg, T(A), (110, 228, 255), (35, 125, 245))
    right = [(470, 40), (800, 40), (800, 700), (252, 700), (420, 205)]   # everything right of the apex split line
    rmask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(rmask).polygon(T(right), fill=255)
    amask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(amask).polygon(T(A), fill=255)
    from PIL import ImageChops
    dark = Image.composite(Image.new("RGB", (S, S), (14, 36, 150)), Image.new("RGB", (S, S), (45, 120, 240)), Image.linear_gradient("L").resize((S, S))).convert("RGBA")
    dark.putalpha(ImageChops.multiply(rmask, amask))
    bg.alpha_composite(dark)

    # swoosh (soft shadow, then body)
    swoosh = (_bez((48, 595), (150, 420), (420, 335), 50) + _bez((420, 335), (620, 270), (722, 222), 40)
              + _bez((722, 222), (752, 235), (738, 268), 12) + _bez((738, 268), (600, 385), (400, 455), 40)
              + _bez((400, 455), (250, 520), (222, 640), 40) + _bez((222, 640), (120, 665), (48, 595), 30))
    sh = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(sh).polygon(T([(x, y + 26) for x, y in swoosh]), fill=(4, 12, 70, 170))
    bg.alpha_composite(sh.filter(ImageFilter.GaussianBlur(14)))
    _fill(bg, T(swoosh), (130, 245, 255), (90, 115, 245), vertical=False)

    # download arrow
    arrow = [(540, 410), (620, 410), (620, 520), (680, 520), (580, 645), (475, 520), (540, 520)]
    _fill(bg, T(arrow), (110, 225, 255), (40, 150, 240))
    return bg


# ---------------- toolbar + tree icons (drawn on 256 px, shipped at 32 px / 16 px) ----------------
BLUE, GREEN, RED, ORANGE, GREY = ((96, 165, 250), (29, 78, 216)), ((74, 222, 128), (21, 128, 61)), ((248, 113, 113), (185, 28, 28)), ((251, 191, 36), (217, 119, 6)), ((156, 163, 175), (75, 85, 99))


def disc(colors):
    top, bot = colors
    g = Image.linear_gradient("L").resize((256, 256))
    im = Image.composite(Image.new("RGB", (256, 256), bot), Image.new("RGB", (256, 256), top), g).convert("RGBA")
    mask = Image.new("L", (256, 256), 0)
    ImageDraw.Draw(mask).ellipse((10, 10, 246, 246), fill=255)
    im.putalpha(mask)
    return im


def glyph(im, fn):
    """Draw white shapes (with a soft shadow) on top of `im`."""
    layer = Image.new("L", (256, 256), 0)
    fn(ImageDraw.Draw(layer))
    shadow = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    shadow.putalpha(layer.point(lambda v: v * 80 // 255).transform((256, 256), Image.AFFINE, (1, 0, 0, 0, 1, -8)).filter(ImageFilter.GaussianBlur(5)))
    white = Image.new("RGBA", (256, 256), (255, 255, 255, 255))
    white.putalpha(layer)
    return Image.alpha_composite(Image.alpha_composite(im, shadow), white)


def blank():
    return Image.new("RGBA", (256, 256), (0, 0, 0, 0))


def gear_points(cx, cy, r_out, r_in, teeth=8):
    pts, step = [], 360 / teeth
    for i in range(teeth):
        a = i * step
        for ang, r in ((a - 15, r_in), (a - 9, r_out), (a + 9, r_out), (a + 15, r_in)):
            pts.append((cx + r * math.cos(math.radians(ang)), cy + r * math.sin(math.radians(ang))))
    return pts


def tray_bin(d, fill="#f87171", dx=0, dy=0):
    d.rounded_rectangle((52 + dx, 62 + dy, 204 + dx, 88 + dy), radius=10, fill=fill)       # lid
    d.rounded_rectangle((100 + dx, 40 + dy, 156 + dx, 66 + dy), radius=10, fill=fill)       # handle
    d.polygon([(70 + dx, 96 + dy), (186 + dx, 96 + dy), (174 + dx, 216 + dy), (82 + dx, 216 + dy)], fill=fill)


def sized(img, n):
    return img.resize((n, n), Image.LANCZOS)


def main():
    m = master()
    (ROOT / "assets").mkdir(exist_ok=True)
    (ROOT / "extension" / "icons").mkdir(parents=True, exist_ok=True)
    sized(m, 512).save(ROOT / "assets" / "icon.png", optimize=True)
    m.save(ROOT / "assets" / "icon.ico", sizes=[(n, n) for n in (16, 24, 32, 48, 64, 128, 256)])
    sized(m, 512).save(ROOT / "assets" / "icon.icns")
    for n in (16, 32, 48, 128):
        sized(m, n).save(ROOT / "extension" / "icons" / f"icon{n}.png", optimize=True)

    buf = io.BytesIO()
    sized(m, 128).save(buf, "PNG", optimize=True)
    b64 = base64.b64encode(buf.getvalue()).decode()
    lines = "\n".join(f'    "{b64[i:i + 100]}"' for i in range(0, len(b64), 100))
    src = (ROOT / "aerograb.py").read_text(encoding="utf-8")
    new, n = re.subn(r"(# --- window icon.*?\n)ICON_B64 = \(.*?\n\)\n(# --- end window icon ---)",
                     lambda mo: f"{mo.group(1)}ICON_B64 = (\n{lines}\n)\n{mo.group(2)}", src, flags=re.S)
    if n != 1:
        raise SystemExit("icon markers not found in aerograb.py")
    (ROOT / "aerograb.py").write_text(new, encoding="utf-8")

    # floating panel icon (48 px, inlined so web pages can never request it)
    buf48 = io.BytesIO()
    sized(m, 48).save(buf48, "PNG", optimize=True)
    uri = "data:image/png;base64," + base64.b64encode(buf48.getvalue()).decode()
    # header brand mark, pre-scaled to 32 and 64 px so the window header stays sharp without Pillow at run time
    marks = {}
    for n in (32, 64):
        bb = io.BytesIO()
        sized(m, n).save(bb, "PNG", optimize=True)
        marks[n] = base64.b64encode(bb.getvalue()).decode()
    body = "".join(f"    {n}: (\n" + "".join(f'        "{v[i:i + 100]}"\n' for i in range(0, len(v), 100)) + "    ),\n" for n, v in marks.items())
    src2 = (ROOT / "aerograb.py").read_text(encoding="utf-8")
    new2, n3 = re.subn(r"(# --- brand marks ---\n)BRAND_B64 = \{.*?\n\}\n(# --- end brand marks ---)", lambda mo: f"{mo.group(1)}BRAND_B64 = {{\n{body}}}\n{mo.group(2)}", src2, flags=re.S)
    if n3 != 1:
        raise SystemExit("brand mark markers not found in aerograb.py")
    (ROOT / "aerograb.py").write_text(new2, encoding="utf-8")
    # the toolbar / menu / tree icons are Lucide glyphs now: tools/build_icons.py

    cp = ROOT / "extension" / "content.js"
    js, n2 = re.subn(r"/\* ICON-BEGIN \*/.*?/\* ICON-END \*/", lambda mo: f'/* ICON-BEGIN */ const ICON = "{uri}"; /* ICON-END */',
                     cp.read_text(encoding="utf-8"), flags=re.S)
    if n2 != 1:
        raise SystemExit("icon markers not found in extension/content.js")
    cp.write_text(js, encoding="utf-8")
    print("icons written; embedded window icon refreshed")


if __name__ == "__main__":
    main()
