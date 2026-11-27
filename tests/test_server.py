"""The shared MCP server (`--serve`) and `--mcp` through pranali. Only
requests that never open a window (bad ones, lists), in a private
directory; nothing reaches the user's desktop."""
import json
import os
import shutil
import signal
import socket
import stat
import subprocess
import sys
import tempfile
import time
import unittest

BIN = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bin", "dvarapala")
INIT = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "test", "version": "0"}}}
LIST = {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}
BAD = {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
       "params": {"name": "request_commands", "arguments": {"commands": [{"cmd": "id"}]}}}   # no why: no window
HELLO = {"pranali": 1, "tool": "dvarapala", "agent": "test", "pid": os.getpid(), "cwd": "/", "env": {}}


def wait_for(pred, secs=10):
    end = time.monotonic() + secs
    while time.monotonic() < end:
        if pred():
            return True
        time.sleep(0.02)
    return False


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="dv")
        self.dir = os.path.join(self.tmp, "dvarapala")
        self.sock = os.path.join(self.dir, "mcp.sock")
        self.env = {k: v for k, v in os.environ.items() if k not in ("WAYLAND_DISPLAY", "DISPLAY")}
        self.env.update(XDG_RUNTIME_DIR=self.tmp, PRANALI_SOCKET=self.sock)
        self.procs = []

    def tearDown(self):
        for p in self.procs:
            if p.poll() is None:
                p.kill()
            p.wait()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def server(self, *pre):
        p = subprocess.Popen([*pre, sys.executable, BIN, "--serve"], env=self.env,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.procs.append(p)
        self.assertTrue(wait_for(lambda: os.path.exists(self.sock)), "no socket")
        return p

    def connect(self, hello=HELLO):
        c = socket.socket(socket.AF_UNIX)
        c.settimeout(10)
        c.connect(self.sock)
        f = c.makefile("rwb", buffering=0)
        if hello is not None:
            f.write((json.dumps(hello) + "\n").encode())
        return c, f

    @staticmethod
    def ask(f, *msgs):
        for m in msgs:
            f.write((json.dumps(m) + "\n").encode())
        return [json.loads(f.readline()) for _ in msgs]


class Shared(Base):
    def test_hello_then_mcp(self):
        self.server()
        st = os.stat(self.sock)
        self.assertEqual(stat.S_IMODE(st.st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(os.stat(self.dir).st_mode), 0o700)
        c, f = self.connect()
        self.assertEqual(json.loads(f.readline()), {"pranali": 1, "ok": True})
        init, tools, bad = self.ask(f, INIT, LIST, BAD)
        self.assertEqual(init["result"]["serverInfo"]["name"], "dvarapala")
        self.assertEqual([t["name"] for t in tools["result"]["tools"]], ["request_commands", "request_root_commands"])
        self.assertTrue(bad["result"]["isError"])
        self.assertIn("needs a 'why'", bad["result"]["content"][0]["text"])
        c.close()

    def test_sessions_are_apart(self):
        self.server()
        a, fa = self.connect()
        b, fb = self.connect()
        fa.readline(), fb.readline()
        fa.write((json.dumps({**LIST, "id": "a"}) + "\n").encode())
        fb.write((json.dumps({**LIST, "id": "b"}) + "\n").encode())
        self.assertEqual(json.loads(fb.readline())["id"], "b")
        self.assertEqual(json.loads(fa.readline())["id"], "a")
        a.close(), b.close()

    def test_needs_the_hello(self):
        self.server()
        c, f = self.connect(hello={"agent": "old"})
        self.assertFalse(json.loads(f.readline())["ok"])
        self.assertEqual(f.readline(), b"")   # and nothing more on that connection
        c.close()

    def test_answers_after_half_close(self):
        self.server()
        c, f = self.connect()
        f.readline()
        f.write((json.dumps(BAD) + "\n").encode())
        c.shutdown(socket.SHUT_WR)
        self.assertEqual(json.loads(f.readline())["id"], 3)
        c.close()

    def test_refuses_a_directory_others_can_enter(self):
        os.makedirs(self.dir, mode=0o755)
        os.chmod(self.dir, 0o755)
        p = subprocess.run([sys.executable, BIN, "--serve"], env=self.env, capture_output=True, text=True, timeout=20)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("0700", p.stderr)

    def test_leaves_a_live_server_alone(self):
        self.server()
        p = subprocess.run([sys.executable, BIN, "--serve"], env=self.env, capture_output=True, text=True, timeout=20)
        self.assertIn("already answers", p.stderr)
        c, f = self.connect()
        self.assertTrue(json.loads(f.readline())["ok"])   # the first one still serves
        c.close()

    def test_sigterm_stops_and_removes_its_socket(self):
        p = self.server()
        c, f = self.connect()
        f.readline()
        p.send_signal(signal.SIGTERM)
        self.assertEqual(p.wait(10), 0)
        self.assertFalse(os.path.exists(self.sock))
        c.close()

    def test_socket_activated(self):
        if not shutil.which("systemd-socket-activate"):
            self.skipTest("no systemd-socket-activate")
        os.makedirs(self.dir, mode=0o700)
        p = subprocess.Popen(["systemd-socket-activate", "-l", self.sock, sys.executable, BIN, "--serve"],
                             env=self.env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.procs.append(p)
        self.assertTrue(wait_for(lambda: os.path.exists(self.sock)))
        c, f = self.connect()
        self.assertTrue(json.loads(f.readline())["ok"])
        self.assertEqual(self.ask(f, LIST)[0]["id"], 2)
        c.close()


class Draining(unittest.TestCase):
    """Stopping: calls running finish and are answered; new ones are refused
    with -32002 before anything is shown (request() is a stand-in here)."""

    def test_refuses_new_calls_and_waits_for_running_ones(self):
        import importlib.machinery
        import importlib.util
        import threading
        loader = importlib.machinery.SourceFileLoader("dvarapala_srv", BIN)
        mod = importlib.util.module_from_spec(importlib.util.spec_from_loader("dvarapala_srv", loader))
        loader.exec_module(mod)
        gate, shown = threading.Event(), []

        def fake_request(req, wayland=None):
            shown.append((req["requester"], wayland))
            gate.wait(5)
            return {"status": "completed", "results": []}
        mod.request = fake_request
        out = []
        server = mod.Server()
        sess = mod.Session(out.append, wayland="wayland-7", server=server)
        call = {"jsonrpc": "2.0", "id": 9, "method": "tools/call", "params": {"name": "request_commands",
                "arguments": {"requester": "Agent A", "commands": [{"cmd": "id", "why": "x"}]}}}
        sess.handle(json.dumps(call))
        self.assertTrue(wait_for(lambda: shown))
        self.assertEqual(shown, [("Agent A", "wayland-7")])   # its own requester and display
        done = []
        t = threading.Thread(target=lambda: done.append(server.drain(5)))
        t.start()
        self.assertTrue(wait_for(lambda: server.stopping))
        sess.handle(json.dumps({**call, "id": 10}))
        self.assertEqual(json.loads(out[-1])["error"]["code"], -32002)
        self.assertEqual(len(shown), 1)                         # the refused one was never shown
        gate.set()
        t.join(10)
        self.assertEqual(done, [0])
        self.assertEqual({json.loads(x)["id"] for x in out}, {9, 10})


@unittest.skipUnless(shutil.which("pranali"), "pranali isn't installed")
class ThroughPranali(Base):
    def mcp(self, *msgs, args=("--mcp",)):
        r = subprocess.run([sys.executable, BIN, *args], input="".join(json.dumps(m) + "\n" for m in msgs),
                           env=self.env, capture_output=True, text=True, timeout=30)
        return [json.loads(x) for x in r.stdout.splitlines()]

    def test_mcp_reaches_the_shared_server(self):
        self.server()
        p = subprocess.Popen([sys.executable, BIN, "--mcp"], env=self.env, stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        self.procs.append(p)
        p.stdin.write((json.dumps(INIT) + "\n").encode())
        p.stdin.flush()
        self.assertEqual(json.loads(p.stdout.readline())["id"], 1)
        # the agent's process is now pranali (exec'd), not a Python server of its own
        self.assertEqual(os.path.basename(os.readlink(f"/proc/{p.pid}/exe")), "pranali")
        p.stdin.write((json.dumps(BAD) + "\n").encode())
        p.stdin.flush()
        self.assertIn("needs a 'why'", json.loads(p.stdout.readline())["result"]["content"][0]["text"])
        p.stdin.close()
        self.assertEqual(p.wait(10), 0)
        p.stdout.close()

    def test_mcp_without_a_server_serves_in_process(self):
        out = self.mcp(INIT, LIST)
        self.assertEqual(out[1]["result"]["tools"][0]["name"], "request_commands")


if __name__ == "__main__":
    unittest.main()
