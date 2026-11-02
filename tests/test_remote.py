"""Answering from the phone (lib/remote.py): only well-formed answers get
through, nothing secret goes out, and without ekatva nothing changes."""
import json
import os
import socket
import sys
import tempfile
import threading
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lib"))
import remote  # noqa: E402  (pure Python: no GTK needed, so CI runs it)


def answer(**kw):
    return json.dumps({"t": "answer", **kw})


class ParseAnswer(unittest.TestCase):
    def test_approval_with_password_and_commands(self):
        self.assertEqual(remote.parse_answer(answer(approve=True, allow=[1, 0, 1], password="pw"), 3),
                         {"approve": True, "allow": [0, 1], "password": "pw"})

    def test_denial_carries_nothing(self):
        self.assertEqual(remote.parse_answer(answer(approve=False, allow=[0], password="pw"), 2),
                         {"approve": False, "allow": [], "password": None})

    def test_rejects_malformed(self):
        for bad in ["not json", json.dumps([1]), json.dumps({"t": "other", "approve": True}),
                    answer(approve="yes", allow=[0], password="pw"),
                    answer(approve=True, allow="0", password="pw"),
                    answer(approve=True, allow=[True], password="pw"),
                    answer(approve=True, allow=[0], password=""),
                    answer(approve=True, allow=[0], password="a\nb"),
                    answer(approve=True, allow=[0], password="x" * 2000),
                    answer(approve=True, allow=[0]),
                    answer(approve=True, allow=[7], password="pw")]:  # no command in range
            self.assertIsNone(remote.parse_answer(bad, 2), bad)

    def test_user_commands_need_no_password(self):
        # commands 0 and 2 run as root, 1 as the user
        self.assertEqual(remote.parse_answer(answer(approve=True, allow=[1]), 3, root=[0, 2]),
                         {"approve": True, "allow": [1], "password": None})
        # a password sent along with them is dropped, never kept
        self.assertEqual(remote.parse_answer(answer(approve=True, allow=[1], password="pw"), 3, root=[0, 2]),
                         {"approve": True, "allow": [1], "password": None})
        # any root command in the answer still needs it
        self.assertIsNone(remote.parse_answer(answer(approve=True, allow=[0, 1]), 3, root=[0, 2]))
        self.assertEqual(remote.parse_answer(answer(approve=True, allow=[0, 1], password="pw"), 3, root=[0, 2]),
                         {"approve": True, "allow": [0, 1], "password": "pw"})

    def test_path_comes_from_the_uid_not_the_environment(self):
        os.environ["XDG_RUNTIME_DIR"] = "/tmp/evil"
        self.assertEqual(remote.socket_path(1000), "/run/user/1000/ekatva-root.sock")
        self.assertTrue(remote.socket_path().startswith(f"/run/user/{os.getuid()}/"))


class Bridge(unittest.TestCase):
    def test_without_ekatva_nothing_happens(self):
        r = remote.Remote.start({"commands": [{"cmd": "id", "why": ""}]}, lambda a: None, path="/nonexistent/x.sock")
        self.assertFalse(r.connected)
        r.send({"t": "done"})  # harmless
        r.close()

    def test_round_trip_with_a_fake_ekatva(self):
        d = tempfile.mkdtemp()
        path = os.path.join(d, "s.sock")
        srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        srv.bind(path)
        srv.listen(1)
        got, answers = [], []

        def ekatva():
            conn, _ = srv.accept()
            f = conn.makefile("rwb")
            got.append(json.loads(f.readline()))
            f.write((answer(approve=True, allow=[0], password="hunter2") + "\n").encode())
            f.write(b"garbage\n")
            f.flush()
            got.append(json.loads(f.readline()))
            conn.close()

        t = threading.Thread(target=ekatva, daemon=True)
        t.start()
        r = remote.Remote.start({"id": "r", "via": "anumati", "requester": "claude", "reason": "x",
                                 "commands": [{"cmd": "id", "why": "who"}]}, answers.append, path=path)
        self.assertTrue(r.connected)
        for _ in range(100):
            if answers:
                break
            time.sleep(0.01)
        self.assertEqual(answers, [{"approve": True, "allow": [0], "password": "hunter2"}])
        r.send({"t": "done", "status": "completed"})
        t.join(2)
        self.assertEqual(got[0]["t"], "request")
        self.assertEqual(got[0]["commands"], [{"cmd": "id", "why": "who"}])
        self.assertEqual(got[1], {"t": "done", "status": "completed"})
        # The window never sends a password out.
        self.assertNotIn("password", json.dumps(got))
        r.close()
        srv.close()


if __name__ == "__main__":
    unittest.main()
