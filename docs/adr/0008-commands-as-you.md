# 8. Commands that run as you, in the same window, marked apart from root

**Status:** Accepted  
**Date:** 2026-10-28

## Context

Agents get stuck on more than root. A sandboxed agent can't reach the network or write outside its project; an agent the user set to "ask first" waits on commands it can't run alone. The fix was the same as for sudo before dvarapala: copy the command into a terminal, run it, paste the output back. Users asked for dvarapala to take these too, as long as root commands and the others can never be mistaken for each other.

## Decision

Each command in a request says how it runs: `"as": "root"` (the default, so every 1.x request means what it did) or `"as": "user"`, with an optional absolute `cwd` (default: the user's home). They share one window, one approval and one result format.

- **Marked on every card, never by position**: a numbered ROOT (red) or YOU badge, a red border on ROOT cards, and "as <user>, in <folder>" under YOU commands. The top bar counts each ("1 command as root and 2 as you") and its pill says "Root access" whenever anything runs as root.
- **The password only for root**: it's asked for when a ticked command is ROOT; a request with only YOU commands has no password field, and approving YOU commands from the phone needs none (`lib/remote.py`'s `root` indexes; a password sent along is dropped).
- **Run in request order**, stopping at the first failure of either kind: each run of consecutive ROOT commands goes to the root runner with one `sudo -k`, as before; each YOU command runs in the window's own process (`lib/userrun.py`).
- **Only what the window shows runs as you**: `bash -c`, no login shell (no rc files), no stdin, and an allowlisted environment built from the systemd user manager's, not the agent's. Nothing like `BASH_ENV`, `ENV`, `LD_PRELOAD`, `SHELLOPTS` or exported functions gets through; `PATH` keeps only absolute directories that aren't world-writable. `cwd` is refused on ROOT commands, which always run from `/`.
- **One tool**: the MCP tool is now `request_commands`; `request_root_commands` stays listed as the same tool so existing setups keep working.

## Consequences

- YOU commands are approved with a click, not a password: the window, which the agent didn't start, is the gate. A program already running as you that is actively malicious could run things as you anyway, so this stays within [ADR 2](0002-consent-gate-not-sandbox.md).
- YOU commands are logged in the user's `requests.jsonl` only; `/var/log/dvarapala.log` stays the record of what ran as root.
- A YOU command doesn't see the agent's environment (virtualenvs, tokens, exports): agents pass what they need on the command line.
- ekatva's phone app gets each command's `as` and `cwd`; until it shows them and lets you approve without a password, approve YOU-only requests in the window.
