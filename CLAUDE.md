# dvarapala -- notes for agents

Commands for AI agents, as root or as the user (`"as"`), approved by the
user in a window that marks the two apart (ADR 8). Its own repo,
pulled into Vayu (github.com/Theyashsawarkar/vayu, whose CLAUDE.md
"Plugins" rules apply); it must work on any Linux desktop on its own. It was
called vayu-elevate until v1.1.0 (`/usr/local/bin/vayu-elevate` is a link).

- `bin/dvarapala` (what agents call), `lib/dialog.py` (the window), `lib/remote.py`
  (answering from the phone through ekatva; the same module as pramana's,
  keep in step), `lib/runner.py`
  (runs as root), `lib/userrun.py` (runs the user's commands: allowlisted
  environment, never the agent's). `install.sh` installs them root-owned into `/usr/local`:
  never make the installed copies user-writable or load code from the user's
  home at runtime.
- Security first: what the window shows is exactly what runs; the agent never
  sees the password; nothing is left with root access afterwards. Read
  SECURITY.md before changing the flow.
- Keys: `# keybind: Dvarapala/root approval | <keys> | <Verb> ...` in
  `lib/dialog.py`'s header, and a README row (CI checks).
- Every change: a CHANGELOG.md entry; releases are tags with `VERSION` in
  `bin/dvarapala` bumped. `python -m py_compile bin/dvarapala lib/*.py`,
  `python -m unittest discover -s tests` and `shellcheck install.sh` must pass.
- Test with harmless requests only (`--cmd id`), through the real window; the
  user approves each.
- The website (docs/, GitHub Pages) is generated: after changing README.md, CHANGELOG.md or docs/adr/, run `python3 scripts/build-site.py` and commit docs/ (CI checks it). A significant design decision gets a new ADR in docs/adr/ (next number; supersede, never rewrite).
