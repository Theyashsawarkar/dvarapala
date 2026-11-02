# Contributing to dvarapala

Thanks for helping. Bug reports, ideas and pull requests are welcome.
Because this code decides what runs as root, changes are reviewed for
security first: keep them small and explain the reasoning.

## Development setup

```sh
git clone https://github.com/Theyashsawarkar/dvarapala ~/code/dvarapala
cd ~/code/dvarapala
python -m py_compile bin/dvarapala lib/*.py
python -m unittest discover -s tests -v
shellcheck install.sh
```

The installed copy is root-owned in `/usr/local`; test a change by running
`./install.sh` from your clone (it shows what it replaces), then a harmless
request: `dvarapala --why "Test" --cmd "id"`.

## How it fits together

- `bin/dvarapala`: what agents call. Validates the request, starts the window
  as a transient systemd user service, waits, prints the result. `--mcp`
  serves the same over MCP.
- `lib/dialog.py`: the approval window (GTK 4 / libadwaita). Checks the
  password and hands the approved commands to the runner.
- `lib/runner.py`: runs as root via `sudo -k`; runs the commands and writes
  the audit log.
- `install.sh`: installs all three root-owned.

## Rules

- **What the user sees is what runs.** Never transform a command between
  display and execution; never add a way to run something that isn't shown.
- **No new trust in the agent.** The agent's process must never see the
  password or be able to edit what the window or runner do.
- **Keys are discoverable**: a `# keybind: Dvarapala/<scope> | <keys> | <Verb> <object>`
  line in `lib/dialog.py`'s header and a row in the README (CI checks).
- Every change gets a `CHANGELOG.md` entry; releases are tags `vX.Y.Z` with
  `VERSION` in `bin/dvarapala` bumped.

## Pull requests

Describe what and why, and tick the template's checklist. By contributing
you agree your work is released under the [MIT License](LICENSE).
