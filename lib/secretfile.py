"""Secrets an agent asks you for (`"secrets"` in a request): you type or paste
each one into the approval window, and it is saved straight to the file the
request names, as you, readable only by you. The agent never gets the value:
its result says only whether each one was saved.

Installed root-owned next to dialog.py and loaded by path. Pure Python (no
GTK), so CI tests it.

Where a secret may go: a file in your home, never inside a git working tree
(so it can't be committed by accident), never through a symlink, and never
over something that isn't a regular file of yours.
"""
import os
import stat
import tempfile

MAX_VALUE = 64 * 1024


def _git_tree(path):
    """Whether `path` is inside a git working tree: a `.git` (a folder, or the
    file a worktree has) in its folder or any folder above. Git itself isn't
    run: in a folder the agent picked, its config could run code."""
    probe = os.path.dirname(path)
    while True:
        if os.path.lexists(os.path.join(probe, ".git")):
            return True
        up = os.path.dirname(probe)
        if up == probe:
            return False
        probe = up


def check_path(path, home):
    """None if a secret may be saved at `path`, else why not (in words)."""
    if not isinstance(path, str) or not os.path.isabs(path):
        return "the path must be absolute"
    norm = os.path.normpath(path)
    home = os.path.normpath(home)
    if not norm.startswith(home + os.sep):
        return "a secret is saved only inside your home"
    # Every part of the way must be a real folder, never a link somewhere else.
    part = home
    for name in os.path.relpath(norm, home).split(os.sep)[:-1]:
        part = os.path.join(part, name)
        if os.path.islink(part):
            return f"{part} is a symbolic link"
        if os.path.exists(part) and not os.path.isdir(part):
            return f"{part} isn't a folder"
    if os.path.islink(norm):
        return f"{norm} is a symbolic link"
    if os.path.exists(norm):
        st = os.lstat(norm)
        if not stat.S_ISREG(st.st_mode) or st.st_uid != os.getuid():
            return f"{norm} isn't a regular file of yours"
    if _git_tree(norm):
        return f"{norm} is inside a git repository: keep secrets outside them (~/.config/<tool>/)"
    return None


def clean(value):
    """What was pasted, without the newline or spaces a paste brings along."""
    return value.replace("\r", "").strip("\n").strip()


def save(path, value, home):
    """Writes the secret (0600, its new folders 0700), replacing the file whole."""
    why = check_path(path, home)
    if why:
        raise ValueError(why)
    value = clean(value)
    if not value:
        raise ValueError("nothing was entered")
    if len(value.encode()) > MAX_VALUE:
        raise ValueError("that's over 64 KB")
    norm = os.path.normpath(path)
    folder = os.path.dirname(norm)
    made = []
    d = folder
    while not os.path.isdir(d):
        made.append(d)
        d = os.path.dirname(d)
    for d in reversed(made):
        os.mkdir(d, 0o700)
    fd, tmp = tempfile.mkstemp(prefix=".dvarapala-", dir=folder)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(value)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, norm)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
