"""Secrets typed into the window (lib/secretfile.py): where they may go and
how they're kept. Pure Python: no window needed."""
import importlib.util
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("secretfile", os.path.join(ROOT, "lib", "secretfile.py"))
secretfile = importlib.util.module_from_spec(spec)
spec.loader.exec_module(secretfile)


class Saving(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = os.path.realpath(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_saved_for_you_alone_with_the_paste_trimmed(self):
        path = os.path.join(self.home, ".config", "made-up", "token")
        secretfile.save(path, "  made-up-token-123\r\n", self.home)
        with open(path) as f:
            self.assertEqual(f.read(), "made-up-token-123")
        self.assertEqual(stat.S_IMODE(os.stat(path).st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(os.stat(os.path.dirname(path)).st_mode), 0o700)
        # Replaced whole, never appended; no temporary file left behind.
        secretfile.save(path, "second", self.home)
        with open(path) as f:
            self.assertEqual(f.read(), "second")
        self.assertEqual(os.listdir(os.path.dirname(path)), ["token"])

    def test_refused_outside_home_in_a_repo_or_through_a_link(self):
        def why(p):
            return secretfile.check_path(p, self.home)
        self.assertIn("inside your home", why("/etc/made-up-token"))
        self.assertIn("absolute", why("relative/token"))
        os.makedirs(os.path.join(self.home, "repo", ".git"))
        self.assertIn("git repository", why(os.path.join(self.home, "repo", "deep", "token")))
        # A worktree's .git is a file.
        os.makedirs(os.path.join(self.home, "wt"))
        open(os.path.join(self.home, "wt", ".git"), "w").close()
        self.assertIn("git repository", why(os.path.join(self.home, "wt", "token")))
        os.makedirs(os.path.join(self.home, "elsewhere"))
        os.symlink(os.path.join(self.home, "elsewhere"), os.path.join(self.home, "link"))
        self.assertIn("symbolic link", why(os.path.join(self.home, "link", "token")))
        os.symlink("/etc/passwd", os.path.join(self.home, "file-link"))
        self.assertIn("symbolic link", why(os.path.join(self.home, "file-link")))
        os.makedirs(os.path.join(self.home, "a-folder"))
        self.assertIn("regular file", why(os.path.join(self.home, "a-folder")))
        self.assertIsNone(why(os.path.join(self.home, ".config", "ok", "token")))

    def test_nothing_typed_saves_nothing(self):
        path = os.path.join(self.home, "token")
        with self.assertRaises(ValueError):
            secretfile.save(path, " \n", self.home)
        self.assertFalse(os.path.exists(path))


def ask(request):
    env = {k: v for k, v in os.environ.items() if k not in ("WAYLAND_DISPLAY", "DISPLAY")}
    r = subprocess.run([sys.executable, os.path.join(ROOT, "bin", "dvarapala")], input=json.dumps(request),
                       capture_output=True, text=True, timeout=20, env=env)
    return r.returncode, json.loads(r.stdout)


class Requests(unittest.TestCase):
    """A request with secrets is checked before any window opens."""

    def rejected(self, request, words):
        code, out = ask(request)
        self.assertEqual(code, 2, out)
        self.assertIn(words, out["message"])

    def test_a_secret_needs_where_what_and_why(self):
        self.rejected({"secrets": [{"path": "~/.config/x/token", "what": "X token"}]}, "needs a 'why'")
        self.rejected({"secrets": [{"path": "/etc/x", "what": "X", "why": "y"}]}, "inside your home")
        self.rejected({"secrets": [{"path": "x/token", "what": "X", "why": "y"}]}, "absolute")
        self.rejected({"secrets": [{"path": "~/t", "what": "X‮", "why": "y"}]}, "invisible")
        two = {"path": "~/t", "what": "X", "why": "y"}
        self.rejected({"secrets": [two, two]}, "twice")
        self.rejected({"secrets": [two] * 6}, "at most 5")

    def test_nothing_to_ask(self):
        self.rejected({"commands": [], "secrets": []}, "at least one command")

    def test_a_secret_alone_is_a_request(self):
        # Valid: it gets as far as needing the desktop (none in tests).
        code, out = ask({"secrets": [{"path": "~/.config/x/token", "what": "X token", "why": "y"}]})
        self.assertEqual(code, 2)
        self.assertIn("Wayland", out["message"])


if __name__ == "__main__":
    unittest.main()
