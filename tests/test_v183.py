"""v1.8.3: one version number everywhere (app, extension, Windows file info, installer) and it is shown in the window."""
import json, os, re, sys, unittest
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)
import aerograb


def read(*p):
    with open(os.path.join(ROOT, *p), encoding="utf-8") as f:
        return f.read()


class VersionConsistency(unittest.TestCase):
    V = aerograb.__version__

    def test_is_1_8_3(self):
        self.assertEqual(self.V, "1.8.3")

    def test_extension_manifests(self):
        for name in ("manifest.json", "manifest.firefox.json"):
            self.assertEqual(json.loads(read("extension", name))["version"], self.V, name)

    def test_windows_version_info(self):
        t = read("version_info.txt")
        four = tuple(int(x) for x in self.V.split(".")) + (0,)
        self.assertIn(f"filevers={four}", t)
        self.assertIn(f"prodvers={four}", t)
        self.assertIn(f"'FileVersion', '{self.V}'", t)
        self.assertIn(f"'ProductVersion', '{self.V}'", t)

    def test_installer(self):
        self.assertIn(f'#define AppVersion "{self.V}"', read("installer", "branding.iss"))

    def test_changelog_has_the_release(self):
        self.assertRegex(read("CHANGELOG.md"), rf"(?m)^## {re.escape(self.V)}\b")

    def test_window_title_and_header_show_name_and_version(self):
        self.assertTrue(aerograb.APP_TITLE.startswith(f"AeroGrab v{self.V}"), aerograb.APP_TITLE)
        self.assertEqual(aerograb.APP_NAME_VER, f"AeroGrab v{self.V}")
        src = read("aerograb.py")
        self.assertIn('text=f"v{__version__}", style="BrandVer.TLabel"', src)   # header label beside the name


if __name__ == "__main__":
    unittest.main()
