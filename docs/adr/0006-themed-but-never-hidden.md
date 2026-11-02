# 6. Themed like the desktop, but nothing can be made hard to read

**Status:** Accepted  
**Date:** 2026-10-24

## Context

The approval window used fixed colours on a near-opaque card, deliberately: it runs with a cleared environment and root-owned XDG directories so that no user GTK CSS (which any process of the user, an agent included, can write) can restyle it, for example to hide a command. Next to Vayu's other popups (Vyom's glass panels, in whatever theme varna applies) it looked like a different program, and users asked for one look across the desktop.

## Decision

The window takes Vyom's layout (a mode pill in the top bar, rounded command cards, key caps in the footer, the same type and buttons) and the user's varna colours, read from `~/.local/state/varna/palette.json` as data, never as CSS, and only through checks that make tampering useless:

- every colour must be a plain `#rrggbb` (no CSS can be smuggled in);
- the body text and the commands must be readable on what they're drawn on (WCAG AA, 4.5:1), or the whole palette is ignored for dvarapala's built-in colours;
- the command's colour is the theme's green only at 7:1 (AAA), else the plain text colour; any other colour (errors, warnings, status, secondary text) that isn't readable enough is replaced by the text colour;
- the Run button's label is whichever of the theme's ink, its text, black or white reads at 4.5:1 on the accent, or the palette is ignored;
- a palette file over 64 KB, or one that doesn't parse, is ignored.

The card stays at 0.84 opacity (Vyom's panels: 0.55), so what's behind the window never reads as part of it even without the compositor's blur.

## Consequences

- The window looks like the rest of the desktop in all ten varna themes, light ones included (FORCE_LIGHT for a light palette).
- The worst a tampered palette can do is change tints: every text stays at least AA-readable, and nothing but colours is read from the file. Tests (`tests/test_theme.py`) cover invisible text, faint status colours, unreadable buttons and CSS injection attempts.
