#!/usr/bin/python3 -I
"""Root side of dvarapala: runs the commands the user approved.

Installed root-owned as /usr/local/lib/dvarapala/runner.py by
dvarapala's install.sh. Only ever started by dialog.py, as

    sudo -S -k -p '' -- /usr/bin/python3 -I /usr/local/lib/dvarapala/runner.py

with the password on the first line of stdin (sudo reads it) and one JSON
line after it (this script reads it):

    {"id": "...", "requester": "...", "commands": ["cmd", ...],
     "stop_on_failure": true, "timeout": 1800}

Each command runs as `bash -c <command>` from /, with no stdin (so nothing
can wait on a prompt: pacman needs --noconfirm) and a minimal environment.
Events go to stdout as JSON lines for the dialog to show live:

    {"event": "start", "index": 0}
    {"event": "done", "index": 0, "exit_code": 0, "stdout": "...", "stderr": "...",
     "duration": 1.2, "timed_out": false, "truncated": false}
    {"event": "skipped", "index": 1}
    {"event": "finished"}

Every run is appended to /var/log/dvarapala.log (root-only), so there is
a record of what ran as root that the requesting agent can't edit.
"""
import json
import os
import subprocess
import sys
import time

LOG = "/var/log/dvarapala.log"
MAX_OUTPUT = 512 * 1024  # per stream, per command
ENV = {
    "PATH": "/usr/local/sbin:/usr/local/bin:/usr/bin",
    "HOME": "/root",
    "LANG": "C.UTF-8",
    "TERM": "dumb",
}


def emit(obj):
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()


def clip(data):
    text = data.decode("utf-8", "replace")
    if len(text) > MAX_OUTPUT:
        return text[:MAX_OUTPUT], True
    return text, False


def audit(entry):
    try:
        fd = os.open(LOG, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
        with os.fdopen(fd, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except OSError as e:
        print(f"dvarapala runner: can't write {LOG}: {e}", file=sys.stderr)


def main():
    if os.geteuid() != 0:
        print("runner.py must run as root (via the dvarapala dialog)", file=sys.stderr)
        return 2
    # With NOPASSWD sudo doesn't consume the password line, so skip lines
    # until the request (a JSON object with "commands") arrives.
    req = None
    for line in sys.stdin:
        try:
            obj = json.loads(line)
        except ValueError:
            continue
        if isinstance(obj, dict) and isinstance(obj.get("commands"), list):
            req = obj
            break
    if req is None:
        print("runner.py: no request on stdin", file=sys.stderr)
        return 2
    commands = req["commands"]
    stop = bool(req.get("stop_on_failure", True))
    timeout = int(req.get("timeout", 1800))
    failed = False
    for i, cmd in enumerate(commands):
        if failed and stop:
            emit({"event": "skipped", "index": i})
            audit({"time": time.time(), "id": req.get("id"), "requester": req.get("requester"),
                   "command": cmd, "result": "skipped"})
            continue
        emit({"event": "start", "index": i})
        t0 = time.monotonic()
        timed_out = False
        try:
            p = subprocess.run(["/usr/bin/bash", "-c", cmd], cwd="/", env=ENV,
                               stdin=subprocess.DEVNULL, capture_output=True, timeout=timeout)
            code, out, err = p.returncode, p.stdout, p.stderr
        except subprocess.TimeoutExpired as e:
            timed_out = True
            code, out, err = 124, e.stdout or b"", (e.stderr or b"") + f"\n[timed out after {timeout}s]".encode()
        stdout, t1 = clip(out)
        stderr, t2 = clip(err)
        duration = round(time.monotonic() - t0, 3)
        emit({"event": "done", "index": i, "exit_code": code, "stdout": stdout, "stderr": stderr,
              "duration": duration, "timed_out": timed_out, "truncated": t1 or t2})
        audit({"time": time.time(), "id": req.get("id"), "requester": req.get("requester"),
               "command": cmd, "exit_code": code, "duration": duration})
        if code != 0:
            failed = True
    emit({"event": "finished"})
    return 0


if __name__ == "__main__":
    sys.exit(main())
