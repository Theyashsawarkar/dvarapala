# 12. One MCP server for every agent, through pranali

**Status:** Accepted
**Date:** 2026-11-28

## Context

Every agent session ran `dvarapala --mcp`, a Python MCP server of its own: about 11 MB each (PSS with swap), idle all day, one per Claude Code session (several at once is normal). Vayu's other tools (narada, darshan, sutradhar, ekatva) moved to one daemon each, reached through [pranali](https://github.com/Theyashsawarkar/pranali), a tiny stdio pipe with a shared hello and reconnect rules. dvarapala decides what runs as root, so moving it had to keep its model whole: what the window shows is what runs, the agent never sees the password, nothing is left with root access, and nobody new can ask.

## Decision

- `dvarapala --serve` is one MCP server for every session, on `$XDG_RUNTIME_DIR/dvarapala/mcp.sock`, started by systemd on the first connection (`dvarapala-mcp.socket`: `SocketMode=0600`, `DirectoryMode=0700`; `dvarapala.service` runs the root-owned `/usr/local/bin/dvarapala` with `python3 -I`). Both units are installed root-owned in `/usr/local/lib/systemd/user` by `install.sh`. Run by hand, it binds the socket itself only in a 0700 folder of the user's, and never removes one that answers.
- `dvarapala --mcp` execs `pranali dvarapala --fallback <python3 -I dvarapala> --mcp --in-process` when pranali is on the agent's PATH; without a server to reach, pranali runs that in-process server (the old behaviour). Without pranali, `--mcp` serves in process as before.
- Each connection is its own MCP session: pranali's hello first (refused without it), then MCP; each tool call runs in its own thread through the same `validate()` and `request()` as before. Connections from another uid are dropped (SO_PEERCRED), though the socket's mode already keeps them out.
- From the hello only the agent's `WAYLAND_DISPLAY` is used, so the window opens on its screen as it did when the server ran in the agent's environment, and only when that display is one of this user's (a socket in the server's runtime folder, a bare name). Nothing in the hello reaches a command: the requester is still the request's own field, YOU commands still get the user manager's environment (ADR 8), ROOT commands still run from `/`.
- On SIGTERM it takes no new connections, refuses new calls with `-32002` (not run, safe to retry), lets running calls finish for up to 20 s (`TimeoutStopSec=30`), then exits. Answers owed after an agent half-closes still go out, for up to 10 s.

## Consequences

- One ~11 MB server instead of one per session; each session costs a ~0.3 MB pipe. Idle, neither wakes. A session's first answer takes as long as before (~70 ms: Python starts, then execs pranali).
- **Who can ask is unchanged**: the socket admits only the user's own processes, which can already run `dvarapala` from a shell; a sandboxed agent that can run it does so today.
- **pranali runs from the user's PATH** (`~/.local/bin` with kosha), not a root-owned path. It sits on the agent's side of the gate, like the agent's own MCP config, which the agent could already point anywhere: it sees the requests the agent sends and the results it gets back, never the password, and can't change what the window shows (the server validates and the window displays what arrives). A malicious program running as the user stays out of scope, as before (ADR 2).
- A restart of the shared server (an update) while a request waits for the user loses that request's answer for its agent (pranali's `-32001`: "may or may not have happened"); the window stays and runs what's approved. `install.sh` therefore doesn't restart a running server while a request folder exists; the per-session servers had the same loss when their session ended.
- Requests whose agent went away now clean up their folder (the per-session server was killed first and left it).
