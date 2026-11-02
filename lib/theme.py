"""anumati's look: Vyom's visual language in the user's varna theme, but
only while every text stays readable. Pure Python (no GTK), for the
approval window (dialog.py), installed root-owned next to it and loaded by
path, never from the user's home. pramana (the polkit password prompt)
carries the same module, so the two windows look alike."""
import json
import os

# The look: Vyom's panels (github.com/Theyashsawarkar/vyom), so this window
# reads as part of the same desktop: a glass card, a mode pill in the top
# bar, rounded rows, key caps in the footer. Colours come from the user's
# varna theme only through theme() below, which accepts a palette only if
# every text stays clearly readable; anything else gets FALLBACK.
CSS = """
window.elevate {
  /* Glass like Vyom's panels, but never see-through enough to read what's
     behind (the compositor's blur does the rest): 0.84, where they're 0.55. */
  background-color: alpha(@base, 0.84);
  color: @text; font-family: "Inter", "Noto Sans", sans-serif; font-size: 13px;
}
.elevate .topbar { padding: 12px 16px; border-bottom: 1px solid alpha(@text, 0.06); }
.elevate .mode { padding: 5px 11px 5px 9px; border-radius: 10px; font-weight: 600; font-size: 12.5px;
  background-color: alpha(@error, 0.15); color: @error; }
.elevate .glyph { font-family: "JetBrainsMono Nerd Font", monospace; font-size: 15px; }
.elevate .title { font-size: 15px; font-weight: 600; color: @text; }
.elevate .requester { color: @accent; font-weight: 700; }
.elevate .body { padding: 14px 16px 6px 16px; }
.elevate .reason { color: @subtext; font-size: 13px; }
.elevate .section { color: @muted; font-size: 10.5px; font-weight: 700; letter-spacing: 1px; }
.elevate .cmd-card { background-color: alpha(@text, 0.05); border: 1px solid alpha(@accent, 0.18);
  border-radius: 12px; padding: 10px 12px; }
.elevate .cmd-card.root { border-color: alpha(@error, 0.45); }
.elevate .cmd-card.declined { opacity: 0.5; }
/* Who a command runs as: on every card, never only by position. */
.elevate .mode.user { background-color: alpha(@accent, 0.15); color: @accent; }
.elevate .badge { font-family: "JetBrainsMono Nerd Font", monospace; font-size: 11px; font-weight: 700;
  padding: 2px 8px; border-radius: 8px; }
.elevate .badge.root { background-color: alpha(@error, 0.18); color: @error; }
.elevate .badge.user { background-color: alpha(@accent, 0.18); color: @accent; }
.elevate .where { font-family: "JetBrainsMono Nerd Font", monospace; font-size: 11.5px; color: @subtext; }
.elevate .why { color: @text; font-weight: 600; font-size: 13.5px; }
.elevate .cmd { font-family: "JetBrainsMono Nerd Font", "JetBrains Mono", monospace; font-size: 12.5px;
  color: @code; background-color: alpha(@crust, 0.7); border-radius: 10px; padding: 7px 10px; }
.elevate .note { color: @muted; font-size: 12px; }
.elevate .error { color: @error; font-weight: 600; }
.elevate checkbutton check { border-color: @muted; background-color: alpha(@crust, 0.7); }
.elevate checkbutton check:checked { background-color: @accent; border-color: @accent; color: @on_accent; }
.elevate entry { background-color: alpha(@crust, 0.7); border-radius: 10px; min-height: 34px; }
.elevate button.btn { padding: 7px 14px; border-radius: 10px; font-weight: 600; font-size: 12.5px;
  background-color: alpha(@text, 0.06); border: 1px solid alpha(@text, 0.08); color: @text; box-shadow: none; }
.elevate button.btn.run { background-color: @accent; color: @on_accent; border-color: transparent; }
.elevate button.btn.run:disabled { background-color: alpha(@text, 0.08); color: @muted; }
.elevate button.btn.deny { background-color: alpha(@error, 0.16); color: @error; border-color: alpha(@error, 0.3); }
.elevate .foot { padding: 9px 16px; border-top: 1px solid alpha(@text, 0.06); background-color: alpha(@crust, 0.25); }
.elevate .hint { color: @muted; font-family: "JetBrainsMono Nerd Font", monospace; font-size: 11px; }
.elevate .countdown { color: @warn; font-size: 11.5px; }
"""

# Vayu's own colours (Catppuccin Mocha): used when there's no varna theme,
# or the theme fails a check.
FALLBACK = {"base": "#1e1e2e", "crust": "#11111b", "text": "#cdd6f4", "subtext": "#a6adc8",
            "muted": "#7f849c", "accent": "#cba6f7", "code": "#a6e3a1", "ok": "#a6e3a1",
            "error": "#f38ba8", "warn": "#fab387", "on_accent": "#11111b", "dark": True}


def _luminance(h):
    def ch(c):
        c = c / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (int(h[i:i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def contrast(a, b):
    la, lb = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def theme(home):
    """The user's varna colours, if they keep this window unmistakable.

    palette.json is the user's file, so an agent running as the user could
    write it too: it must never be able to make a command hard to read or
    a button easy to miss. So every colour must be plain #rrggbb, the text
    must be readable on everything it's drawn on (else the whole palette is
    ignored), and any other colour that isn't readable enough is replaced by
    the text colour."""
    path = os.path.join(home, ".local/state/varna/palette.json")
    try:
        if os.path.getsize(path) > 65536:
            return FALLBACK
        with open(path) as f:
            data = json.load(f)
        c = data["colors"]
        pick = lambda *names: next(c[n] for n in names if n in c)  # noqa: E731
        t = {"base": pick("base"), "crust": pick("crust"), "text": pick("text"), "subtext": pick("subtext1", "subtext0"),
             "muted": pick("overlay2", "subtext0"), "accent": pick("accent"), "code": pick("green", "ok"),
             "ok": pick("ok", "green"), "error": pick("error", "red"), "warn": pick("warn", "yellow"),
             "dark": data.get("variant") != "light"}
    except (OSError, ValueError, KeyError, TypeError, StopIteration):
        return FALLBACK
    if not all(isinstance(v, str) and len(v) == 7 and v[0] == "#" and all(x in "0123456789abcdefABCDEF" for x in v[1:])
               for k, v in t.items() if k != "dark"):
        return FALLBACK
    t = {k: (v.lower() if k != "dark" else v) for k, v in t.items()}
    # Must hold, or the whole palette is ignored: the body text and the
    # command blocks readable (4.5:1, WCAG AA) on what they're drawn on.
    if contrast(t["text"], t["base"]) < 4.5 or contrast(t["text"], t["crust"]) < 4.5:
        return FALLBACK
    # Every other colour that isn't readable enough is replaced by the text
    # colour (always readable, see above): a faint theme colour, or one an
    # agent made faint, never makes anything hard to see.
    if contrast(t["code"], t["crust"]) < 7:          # the command itself: AAA, else plain text
        t["code"] = t["text"]
    for role, need in (("subtext", 4.5), ("error", 4.5), ("warn", 4.5), ("ok", 4.5)):
        if contrast(t[role], t["base"]) < need:
            t[role] = t["text"]
    if contrast(t["muted"], t["base"]) < 3:
        t["muted"] = t["subtext"]
    # The Run button: the accent, labelled in whichever reads better on it.
    # (the theme's own ink first, like Vyom's buttons; black or white only if needed)
    t["on_accent"] = next((c for c in (t["crust"], t["text"], "#000000", "#ffffff")
                           if contrast(c, t["accent"]) >= 4.5), t["crust"])
    if contrast(t["accent"], t["base"]) < 3 or contrast(t["on_accent"], t["accent"]) < 4.5:
        return FALLBACK
    return t


def theme_css(t):
    # libadwaita's own accent (focus rings, the selected text) is the theme's too.
    adw = f"@define-color accent_color {t['accent']};\n@define-color accent_bg_color {t['accent']};\n" \
          f"@define-color accent_fg_color {t['on_accent']};\n"
    return "".join(f"@define-color {k} {v};\n" for k, v in t.items() if k != "dark") + adw + CSS
