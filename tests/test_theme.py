"""Tests for the design system (aerograb_theme.py / aerograb_icons.py) and the live Dark / Light switch.

The logic tests run anywhere. The GUI tests start the real window in a child process (one process per scenario, with its own settings folder) and
skip themselves when there is no display or no tkinter - the same way CI treats gui_smoke.py."""
import base64, json, os, shutil, struct, subprocess, sys, tempfile, textwrap, unittest, zlib

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import aerograb_icons
import aerograb_theme as T

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")

# every (text colour, background) pair the interface actually draws
TEXT_PAIRS = (("fg", "bg"), ("fg", "sidebar"), ("fg", "surface"), ("fg", "selected"), ("fg", "hover"), ("fg", "button"), ("muted", "bg"), ("muted", "sidebar"),
              ("muted", "surface"), ("muted", "hover"), ("accent_fg", "accent_bg"), ("accent_fg", "accent_bg_hover"), ("accent_text", "bg"),
              ("accent_text", "surface"), ("success", "surface"), ("success", "bg"), ("warning", "surface"), ("danger", "surface"), ("danger", "bg"), ("danger", "selected"))


class TestPalettes(unittest.TestCase):
    def test_both_premium_themes_meet_wcag_aa(self):
        for mode in ("dark", "light"):
            p = T.make_palette(mode)
            for a, b in TEXT_PAIRS:
                self.assertGreaterEqual(T.contrast_ratio(p[a], p[b]), 4.5, f"{mode}: {a} on {b} = {T.contrast_ratio(p[a], p[b]):.2f}")

    def test_the_specified_colours_are_used(self):
        d, l = T.make_palette("dark"), T.make_palette("light")
        self.assertEqual((d["bg"], d["sidebar"], d["surface"], d["elevated"], d["accent"], d["fg"], d["border"]),
                         ("#111318", "#171b23", "#1b1f27", "#222834", "#3b82f6", "#f1f5f9", "#303744"))
        self.assertEqual((l["bg"], l["sidebar"], l["surface"], l["accent"], l["accent_hover"], l["border"]),
                         ("#f5f7fa", "#eef1f5", "#ffffff", "#2563eb", "#1d4ed8", "#e2e8f0"))

    def test_light_is_not_an_inverted_dark(self):
        d, l = T.make_palette("dark"), T.make_palette("light")
        for k in ("success", "warning", "danger", "accent_bg_hover", "muted"):
            self.assertNotEqual(d[k], l[k], k)   # hand-tuned per theme, not computed by inverting
        self.assertGreater(T.luminance(l["bg"]), 0.85)
        self.assertLess(T.luminance(d["bg"]), 0.02)

    def test_every_skin_and_accent_has_the_full_token_set_and_readable_text(self):
        full = set(T.make_palette("light"))
        for sk in T.SKINS:
            p = T.make_palette("light", skin=sk)
            self.assertEqual(set(p), full, sk)
            for a, b in (("fg", "bg"), ("fg", "surface"), ("muted", "surface"), ("accent_fg", "accent_bg")):
                self.assertGreaterEqual(T.contrast_ratio(p[a], p[b]), 4.5, f"{sk}: {a} on {b}")
        for _, hexv in T.ACCENTS:
            for mode in ("dark", "light"):
                p = T.make_palette(mode, hexv)
                self.assertGreaterEqual(T.contrast_ratio(p["accent_fg"], p["accent_bg"]), 4.5, hexv)

    def test_garbage_input_falls_back_safely(self):
        self.assertEqual(T.make_palette("nonsense", "not a colour", "no such skin")["mode"], "light")
        self.assertEqual(T.valid_hex("#ABCDEF"), "#abcdef")
        self.assertEqual(T.valid_hex("red"), "")


class TestFontsAndRaster(unittest.TestCase):
    def test_font_choice_prefers_inter_then_segoe(self):
        self.assertEqual(T.pick_family(["Arial", "Segoe UI", "Inter"]), "Inter")
        self.assertEqual(T.pick_family(["Arial", "Segoe UI Variable Text", "Segoe UI"]), "Segoe UI Variable Text")
        self.assertEqual(T.pick_family(["arial"], fallback="X"), "X")
        self.assertEqual(T.semibold_of("Segoe UI", ["Segoe UI", "Segoe UI Semibold"]), "Segoe UI Semibold")
        self.assertIsNone(T.semibold_of("Inter", ["Inter"]))

    def test_every_icon_is_a_complete_64px_mask(self):
        self.assertGreaterEqual(len(aerograb_icons.DATA), 80)
        pack = T.IconPack()
        for name in aerograb_icons.DATA:
            m = pack.mask(name, 64)
            self.assertEqual(len(m), 64 * 64, name)
            self.assertGreater(sum(1 for b in m if b > 128), 30, name + " is empty")

    def test_icons_scale_and_tint_to_valid_pngs(self):
        pack = T.IconPack()
        for size in (12, 16, 18, 20, 24, 32, 48):
            png = pack.png("add", size, "#3b82f6")
            self.assertEqual(png[:8], b"\x89PNG\r\n\x1a\n")
            w, h = struct.unpack(">II", png[16:24])
            self.assertEqual((w, h), (size, size))
            raw = zlib.decompress(png[png.index(b"IDAT") + 4:png.index(b"IEND") - 8])
            px = [raw[1 + y * (1 + size * 4) + x * 4: 1 + y * (1 + size * 4) + x * 4 + 4] for y in range(size) for x in range(size)]
            opaque = [p for p in px if p[3] > 200]
            self.assertTrue(opaque and all(p[:3] == bytes((0x3b, 0x82, 0xf6)) for p in opaque), size)   # tinted with exactly the requested colour

    def test_every_toolbar_and_sidebar_icon_exists(self):
        import aerograb
        for bid, (icon, _, _) in aerograb.TOOLBAR_ACTIONS.items():
            self.assertIn(icon, aerograb_icons.DATA, bid)
        for icon in ("t_all", "t_folder", "t_unfinished", "t_finished", "t_grabber", "t_queue", "t_queue_item", "st_done", "st_active", "st_paused", "st_error", "st_queued",
                     "sun", "moon", "search", "info", "warning", "error", "question", *aerograb.App.CAT_ICONS.values()):
            self.assertIn(icon, aerograb_icons.DATA, icon)

    def test_shapes_render_antialiased(self):
        c = T.Canvas2D(20, 20)
        c.rrect(0, 0, 20, 20, 6, fill="#ffffff")
        alphas = {p[3] for p in c.px}
        self.assertIn(0, alphas)      # transparent corner
        self.assertIn(255, alphas)    # solid centre
        self.assertTrue(any(0 < a < 255 for a in alphas))   # soft edge


# ---------------------------------------------------------------- the real window
def _display_ok():
    if sys.platform.startswith("linux") and not os.environ.get("DISPLAY"):
        return False
    try:
        import tkinter  # noqa: F401
    except ImportError:
        return False
    return True


PRELUDE = textwrap.dedent('''
    import json, os, sys, threading, time
    sys.path.insert(0, %r)
    import aerograb
    out = {}
    def walk(w):
        yield w
        for c in w.winfo_children():
            yield from walk(c)
''') % os.path.abspath(ROOT)


def run_gui(body, home, port):
    script = PRELUDE + f"\napp = aerograb.App({port})\nroot = app.root\n" + textwrap.dedent(body) + "\nprint('RESULT' + json.dumps(out))\nos._exit(0)\n"
    env = dict(os.environ, AEROGRAB_HOME=home)
    r = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, timeout=120, env=env)
    for line in r.stdout.splitlines():
        if line.startswith("RESULT"):
            return json.loads(line[6:])
    raise AssertionError("GUI child failed:\n" + r.stdout[-1500:] + r.stderr[-2500:])


@unittest.skipUnless(_display_ok(), "needs a display (use xvfb-run)")
class TestLiveTheme(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp()
        self.port = 21000 + (os.getpid() * 7 + id(self)) % 3000

    def tearDown(self):
        shutil.rmtree(self.home, ignore_errors=True)

    def test_default_is_dark_and_switching_is_live_complete_and_persistent(self):
        r = run_gui('''
            out["start"] = [aerograb.PAL["mode"], root.cget("bg")]
            d = app.mgr.add("http://example.test/a.bin", app.folder.get(), 4, later=True)
            d.name = "\\u09ac\\u09be\\u0982\\u09b2\\u09be-\\u09ab\\u09be\\u0987\\u09b2.mp4"; app.draw_list(); root.update()
            out["bangla"] = [app.tree.item(i, "values")[0] for i in app.tree.get_children()]
            mgr, nthreads, items = id(app.mgr), threading.active_count(), len(app.mgr.items)
            app.set_theme("light"); root.update()
            out["light"] = [aerograb.PAL["mode"], root.cget("bg"), app.style.lookup("Treeview", "background"), str(app.menubar_frame.cget("bg"))]
            sizes = []
            for i in range(12):
                app.toggle_theme(); root.update(); sizes.append(len(app.theme._img_cache))
            out["cache_growth"] = sizes[-1] - sizes[1]
            out["engine_untouched"] = [id(app.mgr) == mgr, threading.active_count() - nthreads, len(app.mgr.items) - items]
            app.set_theme("dark"); root.update()
            bright = []
            for w in walk(root):
                c = w.winfo_class()
                if c in ("Frame", "Label", "Canvas", "Text", "Listbox", "Menu", "Entry", "Toplevel", "Tk"):
                    try:
                        bg = str(w.cget("bg")).lower()
                    except Exception:
                        continue
                    if bg in ("white", "#ffffff", "#fff", "systembuttonface", "#d9d9d9"):
                        bright.append([c, str(w), bg])
            out["bright_widgets_in_dark"] = bright
            out["saved"] = json.load(open(aerograb.SETTINGS_FILE))["theme"]
        ''', self.home, self.port)
        self.assertEqual(r["start"], ["dark", "#111318"])
        self.assertEqual(r["bangla"][-1], "\u09ac\u09be\u0982\u09b2\u09be-\u09ab\u09be\u0987\u09b2.mp4")
        self.assertEqual(r["light"], ["light", "#f5f7fa", "#ffffff", "#f5f7fa"])
        self.assertLessEqual(r["cache_growth"], 0, "icons are being re-created on every switch (memory leak)")
        self.assertEqual(r["engine_untouched"], [True, 0, 0])   # same Manager, no new threads, no lost downloads
        self.assertEqual(r["bright_widgets_in_dark"], [], "unthemed white widgets remain in Dark")
        self.assertEqual(r["saved"], "dark")

    def test_theme_choice_survives_a_restart(self):
        run_gui('app.set_theme("light"); root.update()', self.home, self.port)
        r = run_gui('root.update(); out["mode"] = aerograb.PAL["mode"]; out["bg"] = root.cget("bg")', self.home, self.port + 1)
        self.assertEqual((r["mode"], r["bg"]), ("light", "#f5f7fa"))

    def test_navigation_toolbar_and_table_keep_everything(self):
        r = run_gui('''
            root.update()
            out["side"] = [[app.side.item(i, "text").strip(), app.side.set(i, "n")] for i in app.side.get_children("")]
            out["cats"] = [app.side.item(i, "text").strip() for i in app.side.get_children("all")]
            out["tool"] = sorted(app.tbtn)
            out["cols"] = [app.tree.heading(c, "text") for c in app.tree["columns"]]
            out["hbar_hidden"] = not app.hsb.winfo_ismapped()
            out["menus"] = [b.cget("text") for b, m in app.menu_labels]
            out["speed_graph"] = [hasattr(app, n) for n in ("gcv", "redraw_graph")]
        ''', self.home, self.port)
        self.assertEqual([x[0] for x in r["side"]], ["All Downloads", "Unfinished", "Finished", "Grabber projects", "Queues"])
        self.assertEqual(r["cats"], ["General", "Compressed", "Documents", "Music", "Video", "Images", "Programs"])
        self.assertEqual(set(r["tool"]), {"add", "resume", "stop", "stopall", "delete", "delc", "options", "scheduler", "startq", "stopq", "grabber", "browser"})
        self.assertEqual(r["menus"], ["Tasks", "File", "Downloads", "View", "Help", "Registration"])
        self.assertEqual(r["cols"], ["File Name", "Q", "Size", "Status", "Time left", "Transfer rate", "Last Try", "Description"])
        self.assertEqual(r["speed_graph"], [False, False])


if __name__ == "__main__":
    unittest.main()
