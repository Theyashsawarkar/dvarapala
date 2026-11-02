"""Request validation: a bad request must fail fast (exit 2, status error)
without opening a window. Runs bin/dvarapala as a subprocess."""
import json
import os
import subprocess
import sys
import unittest

BIN = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bin", "dvarapala")


def run(request):
    env = {k: v for k, v in os.environ.items() if k not in ("WAYLAND_DISPLAY", "DISPLAY")}
    r = subprocess.run([sys.executable, BIN], input=json.dumps(request) if not isinstance(request, str) else request,
                       capture_output=True, text=True, timeout=20, env=env)
    return r.returncode, json.loads(r.stdout)


class Validation(unittest.TestCase):
    def assertRejected(self, request, words):
        code, out = run(request)
        self.assertEqual(code, 2, out)
        self.assertEqual(out["status"], "error")
        self.assertIn(words, out["message"])

    def test_needs_why(self):
        self.assertRejected({"commands": [{"cmd": "id"}]}, "needs a 'why'")

    def test_no_commands(self):
        self.assertRejected({"commands": []}, "command")

    def test_hidden_characters(self):
        self.assertRejected({"commands": [{"cmd": "echo ‮ hi", "why": "x"}]}, "invisible")
        self.assertRejected({"commands": [{"cmd": "echo hi", "why": "zero​width"}]}, "invisible")

    def test_too_many(self):
        self.assertRejected({"commands": [{"cmd": "true", "why": "x"}] * 51}, "50")

    def test_as_must_be_root_or_user(self):
        self.assertRejected({"commands": [{"cmd": "id", "why": "x", "as": "admin"}]}, "'root' or 'user'")

    def test_cwd_only_for_user_commands(self):
        self.assertRejected({"commands": [{"cmd": "id", "why": "x", "cwd": "/tmp"}]}, "run from /")
        self.assertRejected({"commands": [{"cmd": "id", "why": "x", "as": "user", "cwd": "rel/dir"}]}, "absolute")
        self.assertRejected({"commands": [{"cmd": "id", "why": "x", "as": "user", "cwd": "/tmp/\u202e"}]},
                            "invisible")

    def test_not_json(self):
        code, out = run("not json")
        self.assertEqual(code, 2)
        self.assertEqual(out["status"], "error")


class Validated(unittest.TestCase):
    """validate() itself: what reaches the window."""
    def setUp(self):
        import importlib.machinery
        import importlib.util
        loader = importlib.machinery.SourceFileLoader("dvarapala_bin", BIN)
        spec = importlib.util.spec_from_loader("dvarapala_bin", loader)
        self.m = importlib.util.module_from_spec(spec)
        loader.exec_module(self.m)

    def test_root_is_the_default(self):
        out = self.m.validate({"commands": [{"cmd": "id", "why": "x"}]})
        self.assertEqual(out["commands"][0]["as"], "root")
        self.assertNotIn("cwd", out["commands"][0])

    def test_user_cwd_is_normalised(self):
        out = self.m.validate({"commands": [{"cmd": "id", "why": "x", "as": "user", "cwd": "/home/x/../y/"}]})
        self.assertEqual(out["commands"][0], {"cmd": "id", "why": "x", "as": "user", "cwd": "/home/y"})

    def test_summary(self):
        c = lambda *who: [{"as": w} for w in who]  # noqa: E731
        self.assertEqual(self.m.summary(c("root")), "1 command as root")
        self.assertEqual(self.m.summary(c("user", "user")), "2 commands as you")
        self.assertEqual(self.m.summary(c("root", "root", "user")), "2 commands as root and 1 as you")


class Interface(unittest.TestCase):
    def test_schema(self):
        r = subprocess.run([sys.executable, BIN, "--schema"], capture_output=True, text=True, timeout=20)
        self.assertEqual(r.returncode, 0)
        schema = json.loads(r.stdout)
        self.assertEqual(schema["request"]["properties"]["commands"]["items"]["properties"]["as"]["enum"],
                         ["root", "user"])

    def test_mcp_lists_both_names(self):
        msgs = [{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
                {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}]
        r = subprocess.run([sys.executable, BIN, "--mcp"], input="".join(json.dumps(m) + "\n" for m in msgs),
                           capture_output=True, text=True, timeout=20)
        tools = json.loads(r.stdout.splitlines()[1])["result"]["tools"]
        self.assertEqual([t["name"] for t in tools], ["request_commands", "request_root_commands"])

    def test_version(self):
        r = subprocess.run([sys.executable, BIN, "--version"], capture_output=True, text=True, timeout=20)
        self.assertRegex(r.stdout.strip(), r"^\d+\.\d+\.\d+$")


if __name__ == "__main__":
    unittest.main()
