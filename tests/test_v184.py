"""v1.8.4: single instance (mutex / lock + named pipe / unix socket IPC)."""
import os, subprocess, sys, tempfile, threading, time, unittest
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)
import aerograb


class SingleInstanceTests(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp(prefix="agsi")
        self.made = []

    def tearDown(self):
        for si in self.made:
            si.close()

    def si(self):
        s = aerograb.SingleInstance(self.home)
        self.made.append(s)
        return s

    def test_second_acquire_fails_then_succeeds_after_close(self):
        a, b = self.si(), self.si()
        self.assertTrue(a.acquire())
        self.assertFalse(b.acquire())
        a.close()
        self.assertTrue(b.acquire())

    def test_forward_reaches_owner(self):
        a = self.si()
        self.assertTrue(a.acquire() and a.serve())
        for _ in range(25):  # rapid repeated launches
            self.assertTrue(self.si().forward({"cmd": "show"}))
        got = []
        for _ in range(50):
            got += a.poll()
            if len(got) >= 25:
                break
            time.sleep(0.05)
        self.assertEqual(len(got), 25)
        self.assertTrue(all(m["cmd"] == "show" for m in got))

    def test_wrong_key_rejected_and_owner_survives(self):
        a = self.si()
        a.acquire(); a.serve()
        from multiprocessing.connection import Client
        with self.assertRaises(Exception):
            Client(a.address, a.family, authkey=b"wrong").send({"cmd": "show"})
        self.assertTrue(self.si().forward({"cmd": "show"}))

    def test_claim_or_forward(self):
        a = aerograb.claim_or_forward(False, wait=3, si=self.si())
        self.assertIsNotNone(a)
        self.assertIsNone(aerograb.claim_or_forward(True, wait=3, si=self.si()))
        self.assertEqual([m["cmd"] for m in a.poll()], ["ping"])

    def test_stale_socket_file_after_crash(self):
        if os.name == "nt":
            self.skipTest("unix sockets only")
        a = self.si()
        open(a.address, "w").close()  # leftover from a killed process
        self.assertTrue(a.acquire() and a.serve())
        self.assertTrue(self.si().forward({"cmd": "show"}))

    def test_owner_killed_lock_is_free(self):
        code = ("import sys;sys.path.insert(0,%r);import aerograb,time;s=aerograb.SingleInstance(%r);"
                "assert s.acquire();s.serve();print('up',flush=True);time.sleep(60)") % (ROOT, self.home)
        pr = subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE, text=True)
        try:
            self.assertEqual(pr.stdout.readline().strip(), "up")
            b = self.si()
            self.assertFalse(b.acquire())
            self.assertTrue(b.forward({"cmd": "show"}))
        finally:
            pr.kill(); pr.wait()
        b2 = self.si()
        self.assertTrue(b2.acquire())

    def test_entrypoint_gates_gui_launch(self):
        src = open(os.path.join(ROOT, "aerograb.py"), encoding="utf-8").read()
        self.assertLess(src.index("claim_or_forward(a.minimized)"), src.index("run_gui(a.port, a.minimized, inst)"))


if __name__ == "__main__":
    unittest.main()
