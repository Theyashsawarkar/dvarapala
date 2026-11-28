# Changelog

Newest first. Releases are tags (`vX.Y.Z`) with `VERSION` in `bin/dvarapala`.

## Unreleased

- Website: pranali joins the family list in the footer; the site builder passes ruff.
- **One MCP server for every agent session** (ADR 12). With [pranali](https://github.com/Theyashsawarkar/pranali) on your PATH, `dvarapala --mcp` execs `pranali dvarapala --fallback dvarapala --mcp --in-process`: a ~0.3 MB pipe to one shared server, `dvarapala --serve`, socket-activated by `dvarapala-mcp.socket` (`$XDG_RUNTIME_DIR/dvarapala/mcp.sock`, 0600 in a 0700 folder; `install.sh` installs it and `dvarapala.service` root-owned in `/usr/local/lib/systemd/user` and enables the socket for you). Each session used to run a Python server of its own: about 11 MB each (PSS with swap); the shared one is about 11 MB whatever the number of sessions (measured with 4). Nothing changes in what runs or what you see: requests are validated and shown exactly as before, each with its own `requester`, in the window on the agent's display (from pranali's hello, used only if it's one of yours). The server serves only your own processes (SO_PEERCRED), starts its helpers (`systemd-run`, `notify-send`) from root-owned folders only, and wakes only when called. On stop it refuses new calls (-32002, "not run, retry it") and lets running ones finish for up to 20 s; a request still waiting for your answer then reaches its agent as "may or may not have happened" (its window stays and runs what you approve), so `install.sh` doesn't restart the server while one is waiting. Without pranali or the socket, `--mcp` serves in the agent's process as before; `--mcp --in-process` always does.
- A request whose agent went away no longer leaves its folder behind in `$XDG_RUNTIME_DIR/dvarapala` (the per-session server was killed before it could clean up).
- The website, closer to Vayu's own: the tool's screenshot blurred behind the page, a centred hero with the logo and the verse, the page you're on as the white pill, glass "On this page" and footer panels, releases as cards. No glow behind the logo, no coloured line beside the verse.
- **Spatial look**: the approval window's buttons, mode and badges are pills, its cards rounder; without varna, Vayu's Spatial colours (near-white for where you act).
- The website has Vayu's Spatial look: graphite glass, a floating navigation bar, near-white for links and the main button, and the tool's own colour only as its signature (the logo's glow, the shloka's line, the release dots). No more all-caps labels.

## v1.8.0 -- 2026-11-25

- **Secrets, typed into the window and never given to the agent** (ADR 11). A request may carry `"secrets"` (where to save each, what it is, why): the window shows a SECRET card with a hidden field, and saves what you type straight to that file (0600, as you, its new folders 0700) before any command runs. Only inside your home, never in a git repository or through a symbolic link. The agent's result says only whether each was saved (`saved`, `declined`, `failed`, `not_run`), and no log has the value. A request can be secrets alone; the one-off form is `dvarapala --secret PATH --what … --why …`. Agents are told (MCP tool, `--help`) never to ask for a secret in the chat. Requests with secrets are answered on the laptop only.
- The button says what it will do: "Save 1 secret", "Save 1 secret and run 2 selected".

## v1.7.0 -- 2026-11-09

- Every corner is rounded: the website's callouts.
- A logo and a shloka at the top of the README and the website: every Vayu tool has them now.

- Vim keys, modal like every Vayu tool but kept small (no Space leader): the
  window opens in **insert** mode in the password field when a command runs as
  root, otherwise in **normal** mode on the first command card. Normal: `j`/`k`
  move between the commands (`gg`/`G` first/last), `x` or `Space` ticks the
  one you're on, `a` / `n` tick all / none, `Enter` runs (or goes to the
  password first), `i` types the password, `q` or `Esc` denies. In the
  password field `Esc` goes back to the cards instead of denying at once;
  `Esc` again denies. Moving between cards no longer needs Tab.
- The card you're on has the accent border, and the footer shows the mode.
- Enter or Space on the Deny / Run buttons (reached with Tab) still presses
  that button. Tab and Shift+Tab still move the focus, and Ctrl chords that
  aren't the window's (Ctrl+C on a selected command) still reach GTK: NORMAL
  mode had swallowed every key it didn't know, so Tab went nowhere.
- `Ctrl+H` hides the window while the password is being checked too, as it did
  before the vim keys.
- The keys are data, resolved by Vyom's keys module (`lib/keys.py`, vendored,
  installed root-owned with the rest); `scripts/keybinds.py` writes the
  `# keybind:` lines and the README table, and CI checks them.

## v1.6.0 -- 2026-11-02

- **Renamed from anumati to dvarapala** (द्वारपाल, the guardian at the temple
  door; ADR 10). The command and MCP server are `dvarapala`;
  `/usr/local/bin/anumati` stays as a root-owned link to it, so agents and notes
  that still say anumati keep working. Reinstall with `./install.sh`.

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
