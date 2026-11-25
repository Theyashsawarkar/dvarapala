# 11. Secrets are typed into the window and saved for the agent, never given to it

**Status:** Accepted
**Date:** 2026-11-25

## Context

Agents need secrets: an API token to set up a service, a password for a tool's config. The ways open to them were bad. The user pastes it into the chat, and it lands in the conversation's log (and the model provider's). Or the agent asks the user to run a command in a terminal (`read -s t && printf … > file`), which needs a terminal with a keyboard: an agent's `! command` has none, so it saved nothing, and the user pasted the token into the chat after all.

## Decision

A request may carry `"secrets"`: for each, the file to save it to, what it is and why. The same approval window shows a SECRET card (in the theme's warning colour) per secret, with a hidden field, where it will be saved, and that the agent never sees it.

- **Saved by the window, as you**, before any command runs (`lib/secretfile.py`): its new folders 0700, the file 0600, written to a temporary file and renamed over the old one.
- **Only to a safe place**: inside your home (from the passwd database, not the environment), never inside a git working tree (a `.git` in its folder or any above; git itself isn't run, since a folder's config could run code), never through a symbolic link, never over something that isn't a regular file of yours.
- **Never back to the agent**: the field is cleared once read, the result says only `saved`, `declined`, `failed` (with why) or `not_run`, and `requests.jsonl` keeps the path and the state, not the value.
- **Empty is no**: a secret left empty is declined. If one can't be saved, no command runs: the commands may need it.
- **Laptop only**: a request with secrets isn't sent to the phone, since the secret is typed into this window.

## Consequences

- Agents get a secret they need without it ever passing through them: their commands read it from the file.
- A request may be secrets alone: its pill says "A secret", its button "Save 1 secret".
- The secret is in the window's memory until it's written; the window is already protected against being read (`PR_SET_DUMPABLE=0`, ADR 4).
