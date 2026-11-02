"""Answering from the phone, through ekatva (github.com/Theyashsawarkar/ekatva).

When ekatva runs, its socket is /run/user/<uid>/ekatva-root.sock. The
window hands it the request (what it shows, nothing more); ekatva shows it
on your paired phone, and your answer there (which commands, and your
password) comes back here, where it goes through exactly the same steps as
typing it in the window: the sudo check, then the runner.

Only answers flow in; nothing secret flows out. The path comes from the
uid, never from the environment, which the agent asking controls. Pure
Python, no GTK, so CI tests it.
"""
import json
import os
import socket
import threading

MAX_PASSWORD = 1024
MAX_LINE = 64 * 1024


def socket_path(uid=None):
    return f"/run/user/{os.getuid() if uid is None else uid}/ekatva-root.sock"


def parse_answer(line, n_commands, root=None):
    """A validated answer, or None for anything malformed.

    {"approve": bool, "allow": [indexes], "password": str|None}

    `root`: the indexes of the commands that need the password (dvarapala's
    "as": "root"; None means all of them). Approving only the others needs
    no password, and any password sent with them is dropped.
    """
    try:
        msg = json.loads(line)
    except ValueError:
        return None
    if not isinstance(msg, dict) or msg.get("t") != "answer" or not isinstance(msg.get("approve"), bool):
        return None
    allow = msg.get("allow")
    if not isinstance(allow, list) or not all(isinstance(i, int) and not isinstance(i, bool) for i in allow):
        return None
    allow = sorted({i for i in allow if 0 <= i < n_commands})
    if not msg["approve"]:
        return {"approve": False, "allow": [], "password": None}
    if not allow:
        return None
    if root is not None and not set(allow) & set(root):
        return {"approve": True, "allow": allow, "password": None}
    pw = msg.get("password")
    if not isinstance(pw, str) or not pw or len(pw) > MAX_PASSWORD or "\n" in pw or "\0" in pw:
        return None
    return {"approve": True, "allow": allow, "password": pw}


class Remote:
    """One request's line to ekatva, if it's running; harmless if not."""

    def __init__(self, sock=None):
        self.sock = sock
        self.lock = threading.Lock()

    @property
    def connected(self):
        return self.sock is not None

    @classmethod
    def start(cls, request, on_answer, path=None, root=None):
        """Connects and sends the request; `on_answer(answer)` is called from
        a background thread for each valid answer (`root`: see
        parse_answer). Never raises."""
        try:
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            s.settimeout(2)
            s.connect(path or socket_path())
            s.settimeout(None)
        except OSError:
            return cls(None)
        r = cls(s)
        r.send({"t": "request", "v": 1, **request})
        n = len(request.get("commands") or []) or 1
        threading.Thread(target=r._read, args=(on_answer, n, root), daemon=True).start()
        return r

    def _read(self, on_answer, n, root=None):
        buf = b""
        try:
            while True:
                chunk = self.sock.recv(4096)
                if not chunk:
                    return
                buf += chunk
                if len(buf) > MAX_LINE:
                    return self.close()
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    answer = parse_answer(line.decode("utf-8", "replace"), n, root)
                    if answer:
                        on_answer(answer)
        except (OSError, AttributeError):
            return

    def send(self, msg):
        if not self.sock:
            return
        with self.lock:
            try:
                self.sock.sendall((json.dumps(msg) + "\n").encode())
            except OSError:
                self.close()

    def close(self):
        s, self.sock = self.sock, None
        if s:
            try:
                s.close()
            except OSError:
                pass
