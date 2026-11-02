"""Commands that run as you (`"as": "user"`), not root: approved in the same
window, no password, and run by the window itself, so they run outside the
agent's sandbox, from a process the agent didn't start.

Installed root-owned next to dialog.py and loaded by path. Pure Python (no
GTK), so CI tests it.

What the window shows must be what runs, so nothing the agent can set may
add code to a command: the environment is an allowlist (no BASH_ENV, no
LD_PRELOAD, no exported functions), built from the systemd user manager's
(not the agent's), and PATH keeps only directories that aren't writable by
everyone. No login shell, so no rc file runs either.
"""
import os
import pwd
import stat
import subprocess
import time

MAX_OUTPUT = 512 * 1024  # per stream, per command, as the root runner
TIMEOUT = 1800
KEEP = ("HOME", "USER", "LOGNAME", "SHELL", "LANG", "LANGUAGE", "XDG_RUNTIME_DIR", "XDG_SESSION_TYPE",
        "XDG_CURRENT_DESKTOP", "WAYLAND_DISPLAY", "DISPLAY", "DBUS_SESSION_BUS_ADDRESS",
        "SSH_AUTH_SOCK", "GNUPGHOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_STATE_HOME",
        "XDG_CACHE_HOME", "XDG_CONFIG_DIRS", "XDG_DATA_DIRS")
FALLBACK_PATH = "/usr/local/bin:/usr/bin"


def manager_env():
    """The user manager's environment (the session's, not the agent's)."""
    try:
        p = subprocess.run(["systemctl", "--user", "show-environment"], capture_output=True,
                           text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return {}
    env = {}
    for line in p.stdout.splitlines():
        k, sep, v = line.partition("=")
        if sep and k:
            env[k] = v
    return env


def safe_path(path, home):
    """PATH without relative, missing or world-writable directories."""
    keep = []
    for d in (path or "").split(":"):
        if not d.startswith("/") or d in keep:
            continue
        try:
            st = os.stat(d)
        except OSError:
            continue
        if stat.S_ISDIR(st.st_mode) and not st.st_mode & stat.S_IWOTH:
            keep.append(d)
    for d in (os.path.join(home, ".local/bin"), "/usr/local/bin", "/usr/bin"):
        if d not in keep and os.path.isdir(d):
            keep.append(d)
    return ":".join(keep) or FALLBACK_PATH


def build_env(source, home):
    env = {k: v for k, v in source.items() if k in KEEP or k.startswith("LC_")}
    me = pwd.getpwuid(os.getuid())
    env.update(HOME=home, USER=me.pw_name, LOGNAME=me.pw_name)
    env.setdefault("SHELL", me.pw_shell)
    env["PATH"] = safe_path(source.get("PATH"), home)
    env["TERM"] = "dumb"
    return env


def clip(data):
    text = data.decode("utf-8", "replace")
    if len(text) > MAX_OUTPUT:
        return text[:MAX_OUTPUT], True
    return text, False


def run(cmd, cwd, env, timeout=TIMEOUT):
    """One command, as `bash -c` in cwd with no stdin: the same result
    fields the root runner reports."""
    t0 = time.monotonic()
    timed_out = False
    if not os.path.isdir(cwd):
        code, out, err = 1, b"", f"dvarapala: no such directory: {cwd}".encode()
    else:
        try:
            p = subprocess.run(["/usr/bin/bash", "-c", cmd], cwd=cwd, env=env,
                               stdin=subprocess.DEVNULL, capture_output=True, timeout=timeout)
            code, out, err = p.returncode, p.stdout, p.stderr
        except subprocess.TimeoutExpired as e:
            timed_out = True
            code, out, err = 124, e.stdout or b"", (e.stderr or b"") + f"\n[timed out after {timeout}s]".encode()
        except OSError as e:
            code, out, err = 126, b"", str(e).encode()
    stdout, t1 = clip(out)
    stderr, t2 = clip(err)
    return {"exit_code": code, "stdout": stdout, "stderr": stderr,
            "duration": round(time.monotonic() - t0, 3), "timed_out": timed_out, "truncated": t1 or t2}
