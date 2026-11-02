# 2. A consent gate, not a sandbox

**Status:** Accepted  
**Date:** 2026-10-16

## Context

AI agents need root for real work; copying sudo commands back and forth is slow and error-prone, and giving an agent passwordless sudo removes the human from the loop.

## Decision

dvarapala shows every command, with the agent's reason, in a window the user approves with their password. It defends against an agent running something unseen; it doesn't defend against malicious code already running as the user (which could fake any password prompt).

## Consequences

- The threat model is stated plainly in the README and SECURITY.md.
- Use it with agents you trust to ask honestly.
