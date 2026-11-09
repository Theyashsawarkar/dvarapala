"""The approval window's keys: generated annotations, the vendored keys module."""
import importlib.util
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class Keys(unittest.TestCase):
    def test_annotations_and_readme_are_generated(self):
        r = subprocess.run([sys.executable, str(ROOT / "scripts" / "keybinds.py"), "--check"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_keys_module_is_vendored_from_vyom(self):
        self.assertTrue((ROOT / "lib" / "keys.py").read_text().startswith("# Vendored from Vyom's vyom/keys.py v"))

    def test_installed_with_the_window(self):
        self.assertIn('"lib/keys.py:$lib/keys.py"', (ROOT / "install.sh").read_text())

    def test_no_leader_and_few_keys(self):
        spec = importlib.util.spec_from_file_location("keybinds", ROOT / "scripts" / "keybinds.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        keys, ns = mod.load()
        seqs = [b.seq for b in ns["NORMAL_KEYS"]]
        self.assertFalse([s for s in seqs if s.startswith(" ") and len(s) > 1], "no Space leader in the security window")
        km = keys.Keymap(ns["NORMAL_KEYS"])
        m = keys.Machine()
        self.assertEqual(m.feed(km, "g", counts=False).kind, "pending")
        self.assertEqual(m.feed(km, "g", counts=False).bind.action, "first")
        self.assertEqual(m.feed(km, "<Esc>", counts=False).bind.action, "deny")

    def test_tab_and_ctrl_chords_left_to_gtk(self):
        # Tab reaches Deny / Run and Ctrl+C copies a command: NORMAL mode
        # swallowed both (every key it didn't know) in the first draft.
        import ast
        spec = importlib.util.spec_from_file_location("keybinds", ROOT / "scripts" / "keybinds.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        keys, ns = mod.load()
        tree = ast.parse((ROOT / "lib" / "dialog.py").read_text())
        fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "gtk_handles")
        exec(compile(ast.Module([fn], []), "dialog.py", "exec"), ns)
        km = keys.Keymap(ns["NORMAL_KEYS"])
        for tok in ("<Tab>", "<S-Tab>", "<C-c>", "<C-a>"):
            self.assertTrue(ns["gtk_handles"](tok, km), tok)
        for tok in ("<C-h>", "j", "x", " ", "<CR>", "<Esc>", "q", "z"):
            self.assertFalse(ns["gtk_handles"](tok, km), tok)


if __name__ == "__main__":
    unittest.main()
