# 3. Install root-owned in /usr/local

**Status:** Accepted  
**Date:** 2026-10-16

## Context

If the window or the runner were user-writable, the agent the window guards against could edit them.

## Decision

`install.sh` installs `dvarapala`, the window and the runner root-owned in `/usr/local`; the window runs with Python's isolated mode and root-owned XDG directories, so nothing in the user's home changes it.

## Consequences

- Updating needs sudo.
- What runs is what the user approved.
