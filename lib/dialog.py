#!/usr/bin/python3 -I
"""The anumati approval window: shows what an AI agent wants to run (as
root, or as you: each command is marked) and why, lets the user pick which
commands to allow, takes the sudo password once if any root command is
picked, and goes away the moment the user has answered. This process then
runs the picked ones in order, with no window, and writes the result for the
agent, which is the one that waits.

Installed root-owned as /usr/local/lib/anumati/dialog.py by
anumati's install.sh, and started only by anumati, as a transient user service
(not a child of the agent, so the agent can't ptrace it) with a cleared
environment and XDG dirs pointing at root-owned directories (so no user
GTK CSS can hide a row). See ai/README.md for the threat model.

    dialog.py <request-dir>     reads request.json, writes result.json

Keys:
# keybind: Anumati/root approval | Esc | Cancel the root request (deny everything)
# keybind: Anumati/root approval | Enter (password field or Run) | Run the selected commands (as root and as you)
# keybind: Anumati/root approval | Space | Toggle the focused command
# keybind: Anumati/root approval | Ctrl+H | Hide the approval window (unanswered, the request stays open on the phone until it expires)
"""
import ctypes
import json
import os
import pwd
import subprocess
import sys
import threading
import time

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk, Pango  # noqa: E402

APP_ID = "io.github.theyashsawarkar.Anumati"
RUNNER = "/usr/local/lib/anumati/runner.py"
SUDO = "/usr/bin/sudo"
EXPIRES_AFTER = 600          # seconds the request stays open (then: denied)
MAX_ATTEMPTS = 3             # wrong passwords before the request fails
STATE_LOG = os.path.join(pwd.getpwuid(os.getuid()).pw_dir, ".local/state/anumati/requests.jsonl")

# The look and the theme check (lib/theme.py), loaded by path from this
# root-owned directory: python -I puts no script directory on sys.path.
def _load_theme_module():
    import importlib.util
    spec = importlib.util.spec_from_file_location("anumati_theme", os.path.join(os.path.dirname(os.path.realpath(__file__)), "theme.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_theme = _load_theme_module()


def _load_remote_module():
    import importlib.util
    spec = importlib.util.spec_from_file_location("anumati_remote", os.path.join(os.path.dirname(os.path.realpath(__file__)), "remote.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


remote = _load_remote_module()


def _load_userrun_module():
    import importlib.util
    spec = importlib.util.spec_from_file_location("anumati_userrun", os.path.join(os.path.dirname(os.path.realpath(__file__)), "userrun.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


userrun = _load_userrun_module()
CSS, FALLBACK, contrast, theme, theme_css = _theme.CSS, _theme.FALLBACK, _theme.contrast, _theme.theme, _theme.theme_css


def harden():
    # Not dumpable: other processes of this user can't ptrace this one or
    # read /proc/<pid>/mem, where the password lives while it's typed.
    try:
        ctypes.CDLL("libc.so.6", use_errno=True).prctl(4, 0, 0, 0, 0)  # PR_SET_DUMPABLE
    except OSError:
        pass


def write_json_atomic(path, obj):
    tmp = path + ".tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(obj, f)
    os.replace(tmp, path)


class Request:
    def __init__(self, path):
        with open(path) as f:
            data = json.load(f)
        self.id = str(data["id"])[:64]
        self.requester = str(data.get("requester") or "an AI agent")[:80]
        self.reason = str(data.get("reason") or "")[:2000]
        home = pwd.getpwuid(os.getuid()).pw_dir
        # (cmd, why, "root"|"user", cwd): anything but "user" runs as root.
        self.commands = [(str(c["cmd"]), str(c.get("why") or ""), "user" if c.get("as") == "user" else "root",
                          str(c.get("cwd") or home) if c.get("as") == "user" else "/")
                         for c in data["commands"]][:50]
        self.root = [i for i, c in enumerate(self.commands) if c[2] == "root"]


def summary(commands):
    """'2 commands as root and 1 as you' (anumati's notification says the same)."""
    root = sum(c[2] == "root" for c in commands)
    user = len(commands) - root
    first = root or user
    text = f"{first} command{'s' * (first != 1)} as {'root' if root else 'you'}"
    return text + (f" and {user} as you" if root and user else "")


def short_home(path):
    home = pwd.getpwuid(os.getuid()).pw_dir
    return "~" + path[len(home):] if path == home or path.startswith(home + "/") else path


def keycap(keys, t):
    """'Esc' as a key cap (Pango), like Vyom's footer hints."""
    return (f"<span background='{t['crust']}' foreground='{t['subtext']}' font_family='JetBrainsMono Nerd Font'> "
            + GLib.markup_escape_text(keys) + " </span>")


class ElevateWindow(Adw.ApplicationWindow):
    def __init__(self, app, req, outdir, t=FALLBACK):
        super().__init__(application=app, title="Root access requested" if req.root else "Approval requested")
        self.req, self.outdir = req, outdir
        self.started = time.monotonic()
        self.attempts = 0
        self.done = False          # result written
        self.running = False
        self.results = [{"index": i, "command": c, "why": w, "as": who, "cwd": cwd,
                         "decision": "approved", "state": "not_run"}
                        for i, (c, w, who, cwd) in enumerate(req.commands)]
        self.user = pwd.getpwuid(os.getuid()).pw_name
        self.add_css_class("elevate")
        self.set_default_size(820, -1)
        self.connect("close-request", self.on_close)

        # Capture phase: the window sees Esc/Enter before any child, so a
        # widget that was disabled while focused can't swallow them.
        keys = Gtk.EventControllerKey()
        keys.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        keys.connect("key-pressed", self.on_key)
        self.add_controller(keys)

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        # Top bar, like a Vyom panel's: the mode pill, then what's asked.
        top = Gtk.Box(spacing=12)
        top.add_css_class("topbar")
        pill = Gtk.Box(spacing=7, valign=Gtk.Align.CENTER)
        pill.add_css_class("mode")
        if not req.root:
            pill.add_css_class("user")
        # nf-md-shield_alert for root, nf-md-account when everything runs as you
        glyph = Gtk.Label(label="\U000f0483" if req.root else "\U000f0004")
        glyph.add_css_class("glyph")
        pill.append(glyph)
        pill.append(Gtk.Label(label="Root access" if req.root else "As you"))
        top.append(pill)
        who = Gtk.Label(label=req.requester, xalign=0)
        who.add_css_class("requester")
        top.append(who)
        t_ = Gtk.Label(label=f"wants to run {summary(req.commands)}", xalign=0, hexpand=True, wrap=True)
        t_.add_css_class("title")
        top.append(t_)
        outer.append(top)

        body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        body.add_css_class("body")
        if req.reason:
            r = Gtk.Label(label=req.reason, xalign=0, wrap=True, selectable=True)
            r.add_css_class("reason")
            body.append(r)

        sec = Gtk.Label(label="COMMANDS", xalign=0)
        sec.add_css_class("section")
        body.append(sec)
        cards = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.checks, self.card_boxes = [], []
        for i, (cmd, why, as_, cwd) in enumerate(req.commands):
            card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
            card.add_css_class("cmd-card")
            card.add_css_class(as_)
            row = Gtk.Box(spacing=10)
            check = Gtk.CheckButton(active=True)
            check.connect("toggled", self.on_toggle, i)
            row.append(check)
            # Who it runs as, on every card, in its own colour: never implied
            # by position. The number is the order they run in.
            badge = Gtk.Label(label=f"{i + 1} · {'ROOT' if as_ == 'root' else 'YOU'}", valign=Gtk.Align.CENTER)
            badge.add_css_class("badge")
            badge.add_css_class(as_)
            row.append(badge)
            wl = Gtk.Label(label=why or "(no reason given)", xalign=0, wrap=True, hexpand=True)
            wl.add_css_class("why")
            row.append(wl)
            card.append(row)
            # The exact text that will run: selectable, wrapped by character
            # so nothing can hide past the edge.
            cl = Gtk.Label(label=cmd, xalign=0, wrap=True, selectable=True)
            cl.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
            cl.add_css_class("cmd")
            card.append(cl)
            if as_ == "user":
                where = Gtk.Label(label=f"as {self.user}, in {short_home(cwd)}", xalign=0, wrap=True, selectable=True)
                where.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
                where.add_css_class("where")
                card.append(where)
            cards.append(card)
            self.checks.append(check)
            self.card_boxes.append(card)
        scroller = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER,
                                      propagate_natural_height=True, max_content_height=520)
        scroller.set_child(cards)
        body.append(scroller)

        how = []
        if req.root:
            how.append("ROOT commands run as root, from /, after your password.")
        if len(req.root) < len(req.commands):
            how.append(f"YOU commands run as {self.user}, in the folder shown, outside the agent's sandbox, "
                       "without a password.")
        note = Gtk.Label(xalign=0, wrap=True,
                         label=" ".join(how) + " Each runs with bash -c and no input, in order, stopping at the "
                               "first that fails. Untick anything you don't want run. This window closes as "
                               "soon as you answer; the agent waits for the results.")
        note.add_css_class("note")
        body.append(note)

        self.error = Gtk.Label(xalign=0, visible=False, wrap=True)
        self.error.add_css_class("error")
        body.append(self.error)

        bottom = Gtk.Box(spacing=8, margin_bottom=8)
        self.password = Gtk.PasswordEntry(show_peek_icon=True, hexpand=True,
                                          placeholder_text="Your password (for the ROOT commands)")
        self.password.connect("activate", lambda *_: self.on_run())
        # Only asked for when something would run as root.
        self.password.set_visible(bool(req.root))
        bottom.append(self.password)
        if not req.root:
            bottom.append(Gtk.Box(hexpand=True))
        self.deny_btn = Gtk.Button(label="Deny")
        self.deny_btn.add_css_class("btn")
        self.deny_btn.add_css_class("deny")
        self.deny_btn.connect("clicked", lambda *_: self.finish_denied("denied", "The user denied the request."))
        bottom.append(self.deny_btn)
        self.run_btn = Gtk.Button()
        self.run_btn.add_css_class("btn")
        self.run_btn.add_css_class("run")
        self.run_btn.connect("clicked", lambda *_: self.on_run())
        bottom.append(self.run_btn)
        body.append(bottom)
        outer.append(body)

        # Footer, like Vyom's: the keys, then the time left.
        foot = Gtk.Box(spacing=16)
        foot.add_css_class("foot")
        for keys, what in (("Space", "toggle"), ("Enter", "run"), ("Esc", "deny"), ("Ctrl+H", "hide")):
            h = Gtk.Label(use_markup=True)
            h.set_markup(f"{keycap(keys, t)} {GLib.markup_escape_text(what)}")
            h.add_css_class("hint")
            foot.append(h)
        # Answerable from the phone too, when ekatva runs (lib/remote.py).
        self.remote = remote.Remote.start(
            {"id": req.id, "via": "anumati", "requester": req.requester, "reason": req.reason,
             "commands": [{"cmd": c, "why": w, "as": who, **({"cwd": cwd} if who == "user" else {})}
                          for c, w, who, cwd in req.commands]},
            lambda answer: GLib.idle_add(self.remote_answer, answer), root=req.root)
        if self.remote.connected:
            h = Gtk.Label(label="also on your phone")
            h.add_css_class("hint")
            foot.append(h)
        self.countdown = Gtk.Label(xalign=1, hexpand=True)
        self.countdown.add_css_class("countdown")
        foot.append(self.countdown)
        outer.append(foot)

        self.set_content(outer)
        self.update_run_label()
        self.tick()
        GLib.timeout_add_seconds(1, self.tick)
        (self.password if req.root else self.run_btn).grab_focus()

    # ---- selection -------------------------------------------------------
    def selected(self):
        return [i for i, c in enumerate(self.checks) if c.get_active()]

    def needs_password(self):
        return any(i in self.req.root for i in self.selected())

    def on_toggle(self, check, i):
        self.results[i]["decision"] = "approved" if check.get_active() else "declined"
        if check.get_active():
            self.card_boxes[i].remove_css_class("declined")
        else:
            self.card_boxes[i].add_css_class("declined")
        self.update_run_label()

    def update_run_label(self):
        n = len(self.selected())
        self.run_btn.set_label(f"Run {n} selected" if n else "Nothing selected")
        self.run_btn.set_sensitive(n > 0 and not self.running and not self.done)
        if not self.running and not self.done:
            self.password.set_sensitive(self.needs_password())

    def on_key(self, _ctrl, keyval, _code, state):
        if keyval in (Gdk.KEY_h, Gdk.KEY_H) and state & Gdk.ModifierType.CONTROL_MASK:
            self.set_visible(False)
            return True
        if keyval == Gdk.KEY_Escape:
            if not self.running:
                self.finish_denied("denied", "The user denied the request.")
            return True
        if keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter) and isinstance(self.get_focus(), Gtk.CheckButton):
            # On a card: run, or go to the password when it's needed.
            if self.needs_password() and not self.password.get_text():
                self.password.grab_focus()
            else:
                self.on_run()
            return True
        return False  # Enter in the password field: activate = Run; on a button: that button

    def quit(self):
        self.get_application().quit()

    def tick(self):
        if self.done or self.running:
            self.countdown.set_label("")
            return not self.done
        left = EXPIRES_AFTER - int(time.monotonic() - self.started)
        if left <= 0:
            self.finish_denied("timeout", f"No answer within {EXPIRES_AFTER // 60} minutes.")
            return False
        self.countdown.set_label(f"expires in {left // 60}:{left % 60:02d}, then counts as denied")
        return True

    # ---- an answer from the phone ------------------------------------------
    def remote_answer(self, answer):
        """The same as answering here: the ticks you see are what runs, and
        the password goes through the same sudo check."""
        if self.done or self.running:
            return False
        if not answer["approve"]:
            self.finish_denied("denied", "Denied on the phone.")
            return False
        for i, check in enumerate(self.checks):
            check.set_active(i in answer["allow"])
        if answer["password"] is not None:
            self.password.set_text(answer["password"])
        answer["password"] = None
        self.on_run()
        return False

    # ---- running ---------------------------------------------------------
    def on_run(self):
        if self.running or self.done or not self.selected():
            return
        pw = self.password.get_text()
        self.running = True
        # Move focus off the password field before disabling it: disabling the
        # focused widget left GTK's focus broken and the keys stopped working.
        self.set_focus(None)
        for w in (*self.checks, self.password, self.deny_btn):
            w.set_sensitive(False)
        self.update_run_label()
        self.error.set_visible(False)
        if not self.needs_password():
            self.password.set_text("")
            self.start_run(None)
            return
        threading.Thread(target=self.check_password, args=(pw,), daemon=True).start()

    def check_password(self, pw):
        try:
            p = subprocess.run([SUDO, "-S", "-k", "-p", "", "--", "/usr/bin/true"],
                               input=(pw + "\n").encode(), capture_output=True, timeout=30)
            ok = p.returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            ok = False
        GLib.idle_add(self.after_password, ok, pw if ok else None)

    def after_password(self, ok, pw):
        if not ok:
            self.attempts += 1
            self.running = False
            if self.attempts >= MAX_ATTEMPTS:
                self.finish_denied("auth_failed", f"Wrong password {MAX_ATTEMPTS} times.")
                return False
            self.remote.send({"t": "wrong", "attempts": self.attempts})
            self.error.set_label(f"Wrong password (attempt {self.attempts} of {MAX_ATTEMPTS}).")
            self.error.set_visible(True)
            for w in (*self.checks, self.password, self.deny_btn):
                w.set_sensitive(True)
            self.password.set_text("")
            self.password.grab_focus()
            self.update_run_label()
            return False
        self.password.set_text("")
        self.start_run(pw)
        return False

    def start_run(self, pw):
        """Answered: the window and the phone's request go now, the commands
        run on without them, and the agent waits for the result."""
        chosen = self.selected()
        for i, r in enumerate(self.results):
            if i not in chosen:
                r["state"] = "declined"
        self.set_visible(False)
        self.remote.send({"t": "done", "status": "approved"})
        self.remote.close()
        threading.Thread(target=self.run_all, args=(pw, chosen), daemon=True).start()

    def run_all(self, pw, chosen):
        """The chosen commands in request order: each run of consecutive
        ROOT commands goes to the root runner (one sudo), each YOU command
        runs here; the first failure skips the rest. With no window left to
        show a crash, anything unexpected still has to reach the agent."""
        try:
            self.run_groups(pw, chosen)
        except Exception as e:
            GLib.idle_add(self.finish, "error", f"The run stopped unexpectedly: {e}")

    def run_groups(self, pw, chosen):
        groups = []
        for i in chosen:
            who = self.req.commands[i][2]
            if groups and groups[-1][0] == who:
                groups[-1][1].append(i)
            else:
                groups.append((who, [i]))
        env = userrun.build_env(userrun.manager_env(), pwd.getpwuid(os.getuid()).pw_dir) \
            if any(who == "user" for who, _ in groups) else None
        failed = False
        for who, idxs in groups:
            if failed:
                for i in idxs:
                    GLib.idle_add(self.on_event, {"event": "skipped"}, i)
                continue
            if who == "root":
                ok, err = self.run_root(pw, idxs)
                if err is not None:
                    GLib.idle_add(self.finish, "error", err)
                    return
                failed = not ok
                continue
            for i in idxs:
                if failed:
                    GLib.idle_add(self.on_event, {"event": "skipped"}, i)
                    continue
                cmd, _, _, cwd = self.req.commands[i]
                GLib.idle_add(self.on_event, {"event": "start"}, i)
                res = userrun.run(cmd, cwd, env)
                GLib.idle_add(self.on_event, {"event": "done", **res}, i)
                failed = res["exit_code"] != 0
        del pw
        GLib.idle_add(self.finish, "completed", "Ran the approved commands.")

    def run_root(self, pw, idxs):
        """(all succeeded, error message if the runner itself broke)"""
        payload = {"id": self.req.id, "requester": self.req.requester,
                   "commands": [self.req.commands[i][0] for i in idxs],
                   "stop_on_failure": True, "timeout": 1800}
        ok, finished = True, False
        try:
            p = subprocess.Popen([SUDO, "-S", "-k", "-p", "", "--", "/usr/bin/python3", "-I", RUNNER],
                                 stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            p.stdin.write((pw + "\n" + json.dumps(payload) + "\n").encode())
            p.stdin.close()
            for line in p.stdout:
                try:
                    ev = json.loads(line)
                except ValueError:
                    continue
                if ev.get("event") == "finished":
                    finished = True
                elif ev.get("event") in ("start", "done", "skipped"):
                    if ev.get("event") == "done" and ev.get("exit_code") != 0:
                        ok = False
                    GLib.idle_add(self.on_event, ev, idxs[ev["index"]])
            p.wait()
            err = p.stderr.read().decode("utf-8", "replace").strip()
        except OSError as e:
            return False, f"The root runner couldn't start: {e}"
        if not finished:
            # The runner died before "finished" (sudo refused, python error...)
            return False, f"The root runner exited with {p.returncode}: {err[-500:]}"
        return ok, None

    def on_event(self, ev, i):
        kind = ev.get("event")
        r = self.results[i]
        if kind == "start":
            r["state"] = "running"
        elif kind == "skipped":
            r["state"] = "skipped"
        elif kind == "done":
            code = ev["exit_code"]
            r.update(state="ok" if code == 0 else "failed", exit_code=code, stdout=ev["stdout"],
                     stderr=ev["stderr"], duration=ev["duration"], timed_out=ev["timed_out"],
                     truncated=ev.get("truncated", False))
        return False

    # ---- result ----------------------------------------------------------
    def finish_denied(self, status, message):
        for r in self.results:
            r["decision"] = "declined" if status == "denied" else r["decision"]
            r["state"] = "not_run"
        self.finish(status, message)

    def finish(self, status, message):
        if self.done:
            return
        self.done = True
        self.running = False
        self.remote.send({"t": "done", "status": status})
        self.remote.close()
        result = {"id": self.req.id, "status": status, "message": message,
                  "approved": [r["index"] for r in self.results if r["decision"] == "approved" and status == "completed"],
                  "declined": [r["index"] for r in self.results if r["decision"] == "declined"],
                  "results": self.results}
        try:
            write_json_atomic(os.path.join(self.outdir, "result.json"), result)
        except OSError as e:
            print(f"anumati dialog: can't write the result: {e}", file=sys.stderr)
        self.log(result)
        self.quit()

    def log(self, result):
        try:
            os.makedirs(os.path.dirname(STATE_LOG), exist_ok=True)
            entry = {"time": time.time(), "id": self.req.id, "requester": self.req.requester,
                     "reason": self.req.reason, "status": result["status"],
                     "commands": [{"cmd": r["command"], "as": r["as"], "cwd": r["cwd"], "decision": r["decision"],
                                   "state": r["state"], "exit_code": r.get("exit_code")} for r in self.results]}
            with open(STATE_LOG, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except OSError:
            pass

    def on_close(self, *_):
        if not self.done:
            if self.running:
                return True  # the password is being checked; a right one hides the window
            self.finish_denied("denied", "The user closed the window.")
        return False


def main():
    harden()
    if len(sys.argv) != 2:
        print("usage: dialog.py <request-dir>", file=sys.stderr)
        return 2
    outdir = sys.argv[1]
    try:
        req = Request(os.path.join(outdir, "request.json"))
    except (OSError, ValueError, KeyError, TypeError) as e:
        write_json_atomic(os.path.join(outdir, "result.json"),
                          {"status": "error", "message": f"bad request: {e}", "results": []})
        return 2
    Adw.init()
    t = theme(pwd.getpwuid(os.getuid()).pw_dir)
    Adw.StyleManager.get_default().set_color_scheme(
        Adw.ColorScheme.FORCE_DARK if t["dark"] else Adw.ColorScheme.FORCE_LIGHT)
    provider = Gtk.CssProvider()
    provider.load_from_string(theme_css(t))
    Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), provider,
                                              Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 1)
    app = Adw.Application(application_id=APP_ID, flags=Gio.ApplicationFlags.NON_UNIQUE)
    app.connect("activate", lambda a: ElevateWindow(a, req, outdir, t).present())
    app.run([])
    return 0


if __name__ == "__main__":
    sys.exit(main())
