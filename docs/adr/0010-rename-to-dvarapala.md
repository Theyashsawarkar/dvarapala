# 10. Rename anumati to dvarapala

**Status:** Accepted  
**Date:** 2026-11-02

## Context

Vayu's tools take their names from Hindu mythology, history and culture, and a plain word ("permission") said less than the tool does: it stands at the door between an agent and root, and nothing passes it without the user.

## Decision

It became dvarapala (द्वारपाल, the guardian at the temple door). `/usr/local/bin/anumati` stays as a root-owned link to it, as `vayu-elevate` did before, so existing agents and notes keep working. The repository moved to github.com/Theyashsawarkar/dvarapala; GitHub redirects the old address.

## Consequences

- New paths (`/usr/local/lib/dvarapala`, `/var/log/dvarapala.log`, its state and app id); the old audit log stays where it was.
- The MCP server is named dvarapala, so agents see its tools under the new name after a restart.
