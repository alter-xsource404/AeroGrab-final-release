"""Update-check tests (GitHub Releases): version compare, asset choice, download checks, helper scripts.
Run with:  python -m unittest discover -s tests -v   (no internet: a local server plays GitHub)"""
import hashlib, http.server, json, os, sys, tempfile, threading, unittest, urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import aerograb

OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))  # talk to 127.0.0.1 directly, whatever the machine's proxy says
ANY = lambda url: True
EXE = b"MZ" + os.urandom(5000)


def asset(name, size=0, digest=""):
    return {"name": name, "size": size, "digest": digest, "browser_download_url": f"https://github.com/o/r/releases/download/v9/{name}"}


ASSETS = [asset("aerograb-Setup-9.0.0.exe"), asset("aerograb-portable-9.0.0.exe"), asset("aerograb-linux"), asset("aerograb-macos.zip"), asset("source.zip")]


class TestVersions(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(aerograb.parse_version("v1.6.10"), (1, 6, 10))
        self.assertEqual(aerograb.parse_version("1.7-beta"), (1, 7))
        self.assertIsNone(aerograb.parse_version("latest"))
        self.assertIsNone(aerograb.parse_version(None))

    def test_newer(self):
        self.assertTrue(aerograb.is_newer("v1.6.1", "1.6.0"))
        self.assertTrue(aerograb.is_newer("1.10.0", "1.9.9"))   # numbers, not text
        self.assertTrue(aerograb.is_newer("2.0", "1.9.9"))
        self.assertFalse(aerograb.is_newer("1.6", "1.6.0"))      # same version
        self.assertFalse(aerograb.is_newer("1.5.9", "1.6.0"))
        self.assertFalse(aerograb.is_newer("nonsense", "1.6.0"))


class TestKind(unittest.TestCase):
    def kind(self, files, frozen=True, system="Windows", env=None):
        return aerograb.install_kind(frozen=frozen, system=system, exe="C:/x/aerograb.exe", listdir=lambda p: files, env=env or {})

    def test_installed_has_uninstaller(self):
        self.assertEqual(self.kind(["aerograb.exe", "unins000.exe", "unins000.dat"]), "installed")

    def test_portable_has_none(self):
        self.assertEqual(self.kind(["aerograb.exe", "notes.txt"]), "portable")

    def test_source_and_other_systems_are_manual(self):
        self.assertEqual(self.kind(["unins000.exe"], frozen=False), "manual")
        self.assertEqual(self.kind([], system="Linux"), "manual")

    def test_unreadable_folder_is_portable(self):
        def boom(p):
            raise OSError
        self.assertEqual(aerograb.install_kind(frozen=True, system="Windows", exe="C:/x/aerograb.exe", listdir=boom, env={}), "portable")

    def test_override(self):
        self.assertEqual(self.kind([], frozen=False, env={"AEROGRAB_UPDATE_KIND": "Installed"}), "installed")


class TestPickAsset(unittest.TestCase):
    def test_installed_takes_setup(self):
        self.assertEqual(aerograb.pick_asset(ASSETS, "installed")["name"], "aerograb-Setup-9.0.0.exe")
        self.assertEqual(aerograb.pick_asset([asset("AeroGrab-installer.exe"), asset("aerograb-portable.exe")], "installed")["name"], "AeroGrab-installer.exe")

    def test_portable_takes_portable(self):
        self.assertEqual(aerograb.pick_asset(ASSETS, "portable")["name"], "aerograb-portable-9.0.0.exe")

    def test_portable_falls_back_to_the_non_installer_exe(self):  # build.py's own name is aerograb-windows.exe
        self.assertEqual(aerograb.pick_asset([asset("aerograb-Setup-9.exe"), asset("aerograb-windows.exe")], "portable")["name"], "aerograb-windows.exe")

    def test_never_the_wrong_kind(self):
        self.assertIsNone(aerograb.pick_asset([asset("aerograb-portable.exe")], "installed"))
        self.assertIsNone(aerograb.pick_asset([asset("aerograb-Setup.exe")], "portable"))
        self.assertIsNone(aerograb.pick_asset(ASSETS, "manual"))
        self.assertIsNone(aerograb.pick_asset(None, "portable"))

    def test_ignores_uninstallers_and_assets_without_a_link(self):
        broken = {"name": "aerograb-portable.exe"}
        self.assertIsNone(aerograb.pick_asset([broken, asset("unins000.exe")], "portable"))


class TestParseRelease(unittest.TestCase):
    def rel(self, **kw):
        d = {"tag_name": "v9.0.0", "body": "## What's new\n- **Fast** thing\n- see [docs](https://x.io)", "html_url": "https://github.com/o/r/releases/tag/v9.0.0", "assets": ASSETS}
        d.update(kw)
        return d

    def test_newer_release(self):
        i = aerograb.parse_release(self.rel(), current="1.6.0", kind="portable")
        self.assertTrue(i["newer"])
        self.assertEqual((i["version"], i["asset"]["name"]), ("9.0.0", "aerograb-portable-9.0.0.exe"))

    def test_same_version_is_not_newer(self):
        self.assertFalse(aerograb.parse_release(self.rel(tag_name="v1.6.0"), current="1.6.0", kind="portable")["newer"])

    def test_drafts_and_prereleases_are_skipped(self):
        self.assertIsNone(aerograb.parse_release(self.rel(prerelease=True), "1.6.0", "portable"))
        self.assertIsNone(aerograb.parse_release(self.rel(draft=True), "1.6.0", "portable"))

    def test_bad_tag(self):
        with self.assertRaises(aerograb.UpdateError):
            aerograb.parse_release(self.rel(tag_name="nightly"), "1.6.0", "portable")

    def test_foreign_page_link_is_replaced(self):
        self.assertEqual(aerograb.parse_release(self.rel(html_url="https://evil.example/x"), "1.6.0", "portable")["page"], aerograb.UPDATE_PAGE)

    def test_notes_are_plain_text(self):
        n = aerograb.parse_release(self.rel(), "1.6.0", "portable")["notes"]
        self.assertIn("\u2022 Fast thing", n)
        self.assertIn("docs (https://x.io)", n)
        self.assertNotIn("**", n)
        self.assertNotIn("##", n)
        self.assertEqual(aerograb.plain_notes(""), "No release notes were provided.")
        self.assertTrue(aerograb.plain_notes("x" * 9000).endswith("\u2026"))


class TestTrust(unittest.TestCase):
    def test_hosts(self):
        t = aerograb.trusted_update_url
        self.assertTrue(t("https://github.com/o/r/releases/download/v1/a.exe"))
        self.assertTrue(t("https://objects.githubusercontent.com/x"))
        self.assertFalse(t("http://github.com/a.exe"))                 # not https
        self.assertFalse(t("https://github.com.evil.example/a.exe"))   # look-alike
        self.assertFalse(t("https://evilgithub.com/a.exe"))
        self.assertFalse(t(""))


class Server(unittest.TestCase):
    """A local stand-in for GitHub: /api returns release JSON, /file.exe returns a file, /bad.exe is not a program."""
    body = EXE

    @classmethod
    def setUpClass(cls):
        outer = cls

        class H(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                if self.path == "/api":
                    data = json.dumps({"tag_name": "v9.0.0", "body": "notes", "assets": [asset("aerograb-portable.exe", len(EXE))]}).encode()
                elif self.path == "/missing":
                    return self.send_error(404)
                elif self.path == "/limited":
                    return self.send_error(403)
                elif self.path == "/bad.exe":
                    data = b"<html>not a program</html>" * 50
                elif self.path == "/short.exe":
                    data = outer.body
                    self.send_response(200)
                    self.send_header("Content-Length", str(len(data) + 100))  # promises more than it sends
                    self.end_headers()
                    self.wfile.write(data)
                    return
                else:
                    data = outer.body
                self.send_response(200)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
        cls.srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
        cls.base = f"http://127.0.0.1:{cls.srv.server_address[1]}"
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.dest = os.path.join(self.dir, "new.exe")


class TestFetch(Server):
    def test_check_finds_the_update(self):
        i = aerograb.check_for_update(OPENER, current="1.6.0", kind="portable", url=self.base + "/api")
        self.assertTrue(i["newer"])
        self.assertEqual(i["asset"]["name"], "aerograb-portable.exe")

    def test_friendly_http_errors(self):
        for path, word in (("/missing", "No release"), ("/limited", "limiting")):
            with self.assertRaises(aerograb.UpdateError) as c:
                aerograb.fetch_latest_release(OPENER, self.base + path)
            self.assertIn(word, str(c.exception))

    def test_no_server(self):
        with self.assertRaises(aerograb.UpdateError):
            aerograb.fetch_latest_release(OPENER, "http://127.0.0.1:9/api", timeout=2)


class TestDownload(Server):
    def a(self, path="/file.exe", **kw):
        return {"name": "aerograb-portable.exe", "size": len(EXE), "browser_download_url": self.base + path, **kw}

    def get(self, a, **kw):
        return aerograb.download_update(a, self.dest, opener=OPENER, trusted=ANY, **kw)

    def test_good_download_with_checksum_and_progress(self):
        seen = []
        out = self.get(self.a(digest="sha256:" + hashlib.sha256(EXE).hexdigest()), progress=lambda d, t: seen.append((d, t)))
        with open(out, "rb") as f:
            self.assertEqual(f.read(), EXE)
        self.assertEqual(seen[-1], (len(EXE), len(EXE)))
        self.assertFalse(os.path.exists(self.dest + ".part"))

    def test_wrong_checksum_is_discarded(self):
        with self.assertRaises(aerograb.UpdateError) as c:
            self.get(self.a(digest="sha256:" + "0" * 64))
        self.assertIn("checksum", str(c.exception))
        self.assertFalse(os.path.exists(self.dest))
        self.assertFalse(os.path.exists(self.dest + ".part"))

    def test_wrong_size_and_truncated(self):
        with self.assertRaises(aerograb.UpdateError):
            self.get(self.a(size=len(EXE) + 1))
        with self.assertRaises(aerograb.UpdateError):
            self.get(self.a("/short.exe"))
        self.assertFalse(os.path.exists(self.dest))

    def test_not_a_program(self):
        with self.assertRaises(aerograb.UpdateError) as c:
            self.get(self.a("/bad.exe", size=0))
        self.assertIn("not a Windows program", str(c.exception))
        self.assertFalse(os.path.exists(self.dest + ".part"))

    def test_cancel(self):
        stop = threading.Event()
        stop.set()
        with self.assertRaises(aerograb.UpdateError):
            self.get(self.a(), stop=stop)
        self.assertFalse(os.path.exists(self.dest + ".part"))

    def test_untrusted_host_refused_before_connecting(self):
        with self.assertRaises(aerograb.UpdateError):
            aerograb.download_update(self.a(), self.dest, opener=OPENER)  # real trust check: 127.0.0.1 over http is not GitHub


class TestScripts(unittest.TestCase):
    def test_portable_script(self):
        s = aerograb.portable_script(r"C:\Apps\100%\aerograb.exe", r"C:\Apps\100%\aerograb.exe.new")
        self.assertIn(r'set "TARGET=C:\Apps\100%%\aerograb.exe"', s)   # % doubled for cmd
        self.assertIn('move /y "%NEW%" "%TARGET%"', s)
        self.assertLess(s.index("goto swap"), s.index('start "" "%TARGET%"'))
        self.assertIn("\r\n", s)

    def test_installer_script(self):
        s = aerograb.installer_script(r"C:\Temp\aerograb-Setup.exe", r"C:\Apps\aerograb.exe")
        self.assertIn('start "" /wait "%SETUP%" /SILENT', s)
        self.assertIn("/SUPPRESSMSGBOXES", s)
        self.assertLess(s.index('/wait "%SETUP%"'), s.index('start "" "%TARGET%"'))  # install first, then restart
        self.assertIn("/VERYSILENT", aerograb.installer_script("a.exe", "b.exe", ["/VERYSILENT"]))

    def test_apply_writes_and_launches_the_script(self):
        launched = []
        with mock_frozen():
            path = aerograb.apply_update("portable", "C:/x/aerograb.exe.new", exe="C:/x/aerograb.exe", launcher=launched.append)
        self.assertEqual(launched, [path])
        with open(path, encoding="utf-8") as f:
            self.assertIn("aerograb.exe.new", f.read())

    def test_source_copy_refuses_to_replace_python(self):
        with self.assertRaises(aerograb.UpdateError):
            aerograb.apply_update("portable", "new.exe", launcher=lambda s: None)

    def test_stage_path(self):
        d = tempfile.mkdtemp()
        exe = os.path.join(d, "aerograb.exe")
        self.assertEqual(aerograb.stage_path("portable", {}, exe), exe + ".new")   # next to the exe: the swap is one rename on one drive
        p = aerograb.stage_path("installed", asset("../../evil name?.exe"))
        self.assertEqual(os.path.dirname(p), os.path.join(tempfile.gettempdir(), "aerograb-update"))
        self.assertNotIn("?", p)


class mock_frozen:
    def __enter__(self):
        self.had = hasattr(sys, "frozen")
        sys.frozen = True

    def __exit__(self, *a):
        if not self.had:
            del sys.frozen


if __name__ == "__main__":
    unittest.main()
