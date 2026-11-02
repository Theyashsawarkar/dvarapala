# 9. The window closes on the answer; the agent does the waiting

**Status:** Accepted  
**Date:** 2026-11-02

## Context

The window stayed on screen until the approved commands finished, showing each one's state and output, and stayed open after a failure until it was closed. A slow command (a package install, a build) left a window in the way for minutes, with nothing for the user to do in it: a run can't be cancelled, and the agent gets the full output anyway. The user's part ends at the answer; only the agent needs the result.

## Decision

The window hides as soon as the request is answered: on Deny, Esc, close or expiry as before, and on approval right after the password check passes (at once when no password is needed). A wrong password keeps it open to retry, since that's still waiting on the user. The phone's request clears at the same moment (`{"t": "done", "status": "approved"}`, then the socket closes).

The same process keeps running the commands with no window, then writes `result.json` and exits. It stays the transient service the agent didn't start, so nothing about what runs or how changes ([ADR 4](0004-window-outside-the-agent.md)). The results view goes: per-card state and output, and the key that closed the window after a failure.

## Consequences

- Nothing on screen shows a run in progress or its result. Failures reach the user through the agent, which gets every command's output; `~/.local/state/anumati/requests.jsonl` and `/var/log/anumati.log` keep the record.
- A process with no window can't show that it's stuck, so an unexpected error in the run is reported to the agent as an `error` result. A command that hangs still ends at its 30-minute limit.
- `Ctrl+H` hides the window whenever the user wants it gone, such as during a slow password check. Hiding isn't an answer: an unanswered request can still be answered from the phone, otherwise it expires as denied after 10 minutes, with the agent waiting until then. Esc stays the way to say no.
- The window says it will close, so a window going away isn't mistaken for a cancelled request.
