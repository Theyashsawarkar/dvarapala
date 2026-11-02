# Changelog

Newest first. Releases are tags (`vX.Y.Z`) with `VERSION` in `bin/anumati`.

## v1.5.0 -- 2026-11-02

- **The window closes as soon as you answer** (ADR 9). It used to stay up
  until the commands finished, showing each one's result, and stayed open
  after a failure until you closed it. Now it goes the moment you approve
  (after a right password, if one was needed) or deny; a wrong password
  still keeps it open to retry. The commands run on in the same process with
  no window, and the agent waits for the results, as before. The phone's
  request clears at the same moment.
- Gone with the results view: the per-card state and output, and the
  `Enter (after a failed run)` key. A failure now reaches you through the
  agent, which gets the full output; the logs are as before.
- `Ctrl+H` hides the window at any time. Hiding isn't an answer: an
  unanswered request can still be answered from the phone, otherwise the
  agent waits until it expires and counts as denied. It can't be brought back.
- If the run breaks unexpectedly, the agent now gets an `error` result
  instead of waiting forever on a process with no window.

## v1.4.0 -- 2026-10-28

- **Commands as you, not just as root** (ADR 8). A command can say
  `"as": "user"` (with an optional absolute `cwd`, default: home): for
  anything an agent can't run itself, like a command its sandbox blocks.
  It shows in the same window with a YOU badge (ROOT ones get a red badge
  and border), numbered in run order, with "as <user>, in <folder>" under
  it; the top bar counts each kind. YOU commands run as you from the window
  with a click: the password is asked for only when a ROOT command is
  ticked, and a request with only YOU commands has no password field.
  Commands run in request order, stopping at the first failure of either
  kind; each run of ROOT commands is one `sudo -k`. Without `"as"` a
  command is ROOT, so 1.x requests are unchanged; `cwd` on a ROOT command
  is refused.
- YOU commands get an allowlisted environment from the systemd user
  manager, not the agent's (no `BASH_ENV`, `LD_PRELOAD`, exported
  functions; `PATH` without relative or world-writable folders), and no
  login shell. New `lib/userrun.py` (pure Python, tested), installed next
  to the window.
- MCP: the tool is now `request_commands`; `request_root_commands` is still
  listed, as the same tool. CLI: `--as user` and `--cwd` for the one-off
  form. Results and your `requests.jsonl` carry each command's `as` and
  `cwd`; notifications say "Approval requested" when nothing runs as root.
- Answering from the phone: approving only YOU commands needs no password
  (`lib/remote.py`'s `parse_answer` takes the ROOT indexes); the request
  sent to ekatva carries `as` and `cwd`.
- Enter on a command's checkbox runs the request (or moves to the password
  field when it's needed and empty).

## v1.3.0 -- 2026-10-26

- Answer from your phone: when [ekatva](https://github.com/Theyashsawarkar/ekatva)
  runs, the window also hands its request to ekatva
  (`/run/user/<uid>/ekatva-root.sock`), which shows it on your paired
  phone. Approving there (which commands, and your password) ticks those
  commands in the window and fills the password field, then goes through
  the same sudo check and runner as typing it here; a wrong password is
  reported back so you can retry from the phone; denying there denies.
  The window sends nothing secret out, finds the socket by uid (not the
  agent's environment), and validates every answer strictly. Without
  ekatva nothing changes. New `lib/remote.py` (pure Python, tested), ADR 7.
  The footer says "also on your phone" while it's linked.

## v1.2.1 -- 2026-10-24

- The look and the theme check moved into `lib/theme.py` (pure Python),
  loaded by path by the window: the tests that check a tampered theme can't
  hide anything now run in CI, which has no GTK (1.2.0's CI failed there).
  install.sh installs it next to dialog.py.

## v1.2.0 -- 2026-10-24

- **Looks like the rest of the desktop.** The window has Vyom's layout: a
  "Root access" pill and the request in the top bar, the commands as
  rounded cards, the password and buttons, then the keys (Space, Enter,
  Esc) and the time left in the footer; Vyom's type, buttons and a 20 px
  glass card (0.84, never see-through enough to read what's behind).
- **In your theme, safely** (ADR 6). The colours come from varna's
  `palette.json`, read as plain `#rrggbb` data only, never CSS. The body
  text and the commands must stay readable (4.5:1) or the palette is
  ignored; the command is the theme's green only at 7:1, else plain text;
  any other colour that isn't readable enough becomes the text colour; the
  Run button's label is picked to read on the accent. A light theme gets a
  light window. Without varna: anumati's own colours, as before.
- Focus rings and selected text use the theme's accent (not GTK's blue).

## v1.1.1 -- 2026-10-21

- A website (GitHub Pages, https://theyashsawarkar.github.io/anumati/): the README as a home page, the
  changelog, and architecture decision records (`docs/adr/`), built from these files by
  `scripts/build-site.py`; CI checks the site is up to date.

## v1.1.0 -- 2026-10-21

- Renamed from `vayu-elevate` to **anumati** (अनुमति, "permission") and
  moved into its own repository. Everything moves with the name:
  `/usr/local/bin/anumati`, `/usr/local/lib/anumati/`,
  `/var/log/anumati.log`, `~/.local/state/anumati/requests.jsonl`, the
  window's app id `io.github.theyashsawarkar.Anumati`, the MCP server name.
- `install.sh` (was Vayu's `ai/apply.sh`) installs it root-owned, keeps
  `/usr/local/bin/vayu-elevate` as a link so the old name still works,
  removes the old `/usr/local/lib/vayu-elevate`, and gains `--uninstall`.
- Tests for request validation, and CI.

## v1.0.0 -- 2026-10-16

- First version, as `vayu-elevate` inside Vayu: the approval window, the
  root runner, JSON in and out, the MCP server, the audit logs.
