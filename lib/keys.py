# Vendored from Vyom's vyom/keys.py v1.0.2 (sha256 b526d8ac6d1703f4) by scripts/vendor-keys.sh: don't edit here, change it in Vyom and vendor it again.
"""keys: vim keys as data. Normal and Insert modes, counts, sequences, and
Space as the leader, the same in every tool.

KEYS_VERSION = see below. Pure Python, no GTK or curses: Vyom's panel uses it,
and the Python tools (vesha, vishvakarma, nada, drishya, vinyasa, dvarapala,
pramana) carry a vendored copy (scripts/vendor-keys.sh in the Vyom repo writes
it, with a header that says which version and hash it is; `--check` finds a
stale copy). Grown from ganit's vim.py (ganit ADR 0005); Vyom ADR 0008.

A sequence is a string of tokens: one character each ("g", "G", "5", "/"),
or a name in angle brackets: <CR> <Esc> <BS> <Tab> <S-Tab> <Del> <Up>
<Down> <Left> <Right> <PgUp> <PgDn> <Home> <End> <F1>..<F12>, and chords
<C-d> (Ctrl+d), <A-1> (Alt+1), <C-CR>, <S-CR>. " " is Space, the leader.

    from keys import Bind, Keymap, Machine
    km = Keymap([Bind("j", "down", "Move down"), Bind(" yy", "copy", "Copy the name")])
    m = Machine()
    m.feed(km, "5"); m.feed(km, "j")     # -> Result("run", bind, count=5)

An action is whatever the host wants: a string ("down", "tab:+1": verb and
argument) or a callable. The host runs it; this module only resolves keys.
"""
import re
from dataclasses import dataclass, field
from typing import Any

KEYS_VERSION = "1.0.2"
LEADER = " "

# The reserved Space groups: the same letter means the same thing in every
# tool. A tool may leave a group empty but never use its letter for anything
# else (keybind-search.py --check enforces it). Free letters for a tool's own
# nouns: b c h i j l n p v w x z.
GROUPS = {
    " ": "leader",
    "  ": "palette",
    " ?": "keys",
    " q": "close",
    " t": "tabs",
    " u": "toggles",
    " y": "copy",
    " f": "find",
    " s": "sort",
    " r": "refresh",
    " a": "add",
    " d": "delete",
    " e": "edit",
    " o": "open",
    " g": "go to",
    " m": "mark",
    " ,": "settings",
    " k": "ask AI",
}
RESERVED = {k[1] for k in GROUPS if len(k) == 2}
FREE = set("bchijlnpvwxz")

# Prefixes that aren't the leader but still open a which-key strip.
PREFIX_NAMES = {"g": "go", "d": "delete", "y": "copy", "c": "change", "z": "view"}

# Gdk key names (also what most toolkits call them) for one-character tokens.
CHAR_NAMES = {
    "space": " ", "slash": "/", "question": "?", "equal": "=", "dollar": "$", "asciicircum": "^",
    "bracketleft": "[", "bracketright": "]", "braceleft": "{", "braceright": "}",
    "asterisk": "*", "plus": "+", "minus": "-", "period": ".", "comma": ",", "semicolon": ";",
    "colon": ":", "underscore": "_", "numbersign": "#", "percent": "%", "ampersand": "&",
    "exclam": "!", "at": "@", "less": "<", "greater": ">", "bar": "|", "backslash": "\\",
    "apostrophe": "'", "quotedbl": '"', "grave": "`", "asciitilde": "~", "parenleft": "(",
    "parenright": ")",
}
SPECIAL = {
    "Return": "CR", "KP_Enter": "CR", "Escape": "Esc", "BackSpace": "BS", "Tab": "Tab",
    "ISO_Left_Tab": "S-Tab", "Delete": "Del", "Up": "Up", "Down": "Down", "Left": "Left",
    "Right": "Right", "Page_Up": "PgUp", "Page_Down": "PgDn", "Home": "Home", "End": "End",
}
SPELL = {
    "CR": "Enter", "Esc": "Esc", "BS": "Backspace", "Tab": "Tab", "S-Tab": "Shift+Tab", "Del": "Delete",
    "Up": "Up", "Down": "Down", "Left": "Left", "Right": "Right", "PgUp": "Page Up", "PgDn": "Page Down",
    "Home": "Home", "End": "End",
}
MODIFIER_NAMES = ("Shift", "Control", "Alt", "Super", "Meta", "Hyper", "ISO_Level", "Caps_Lock", "Num_Lock")


def is_modifier(name):
    """A modifier key on its own (Shift_L, Control_R...)."""
    return name.startswith(MODIFIER_NAMES)


def token(name, mods=frozenset()):
    """One key press as a token, or None (Super chords, unknown keys).
    name: a Gdk-style key name ("j", "G", "Return", "slash"); mods: a set of
    "shift" / "ctrl" / "alt". Shift is part of a character ("G", "?"), so it
    only shows in names (<S-CR>)."""
    mods = set(mods)
    if name.startswith("KP_") and len(name) == 4 and name[3].isdigit():
        name = name[3]
    base = CHAR_NAMES.get(name, name if len(name) == 1 else None)
    if base is not None and len(base) == 1 and base.isalpha() and "shift" in mods:
        base = base.upper()   # some keymaps (virtual keyboards) send "g" + Shift for G
    special = SPECIAL.get(name)
    if special is None and len(name) in (2, 3) and name[0] == "F" and name[1:].isdigit():
        special = name
    prefix = ("C-" if "ctrl" in mods else "") + ("A-" if "alt" in mods else "")
    if base is not None:
        if not prefix:
            return base
        return f"<{prefix}{'Space' if base == ' ' else base}>"
    if special is not None:
        if special == "S-Tab":
            return f"<{prefix}S-Tab>"
        shift = "S-" if "shift" in mods else ""
        return f"<{prefix}{shift}{special}>"
    return None


_SPECIAL = re.compile(
    r"<(?:[CAS]-)+(?:[^<>]+|[<>])>|<(?:CR|Esc|BS|Tab|S-Tab|Del|Up|Down|Left|Right|PgUp|PgDn|Home|End|F\d{1,2})>")


def tokens(seq):
    """A sequence split into tokens: " y<CR>" -> [" ", "y", "<CR>"]. Only a
    real key name in angle brackets is one token, so a bare "<" (or "<>") is
    a key of its own."""
    out, i = [], 0
    while i < len(seq):
        m = _SPECIAL.match(seq, i) if seq[i] == "<" else None
        j = m.end() if m else i + 1
        out.append(seq[i:j])
        i = j
    return out


def spell_token(tok):
    if tok == " ":
        return "Space"
    if len(tok) > 2 and tok[0] == "<" and tok[-1] == ">":
        inner = tok[1:-1]
        parts = []
        while len(inner) > 2 and inner[1] == "-" and inner[0] in "CAS":
            parts.append({"C": "Ctrl", "A": "Alt", "S": "Shift"}[inner[0]])
            inner = inner[2:]
        if inner == "S-Tab":
            parts.append("Shift"); inner = "Tab"
        parts.append(SPELL.get(inner, inner))
        return "+".join(parts)
    return tok


def spell(seq):
    """A sequence as the keys you press: " tc" -> "Space t c", "<C-d>" -> "Ctrl+d"."""
    return " ".join(spell_token(t) for t in tokens(seq))


@dataclass
class Bind:
    seq: str                     # the tokens, e.g. " yy", "gg", "<C-d>"
    action: Any                  # a string ("verb:arg") or a callable; the host runs it
    desc: str = ""               # verb-first ("Copy the name")
    group: str | None = None  # which-key group name for a prefix this bind opens (rarely needed)
    mode: str = "normal"         # "normal" | "insert" | "any"
    when: Any = None             # None, a tab key, a set of tab keys, or a callable() -> bool
    hidden: bool = False         # an alias: works, but not in help, palette or annotations

    def applies(self, mode, tab=None):
        if self.mode not in (mode, "any"):
            return False
        w = self.when
        if w is None:
            return True
        if callable(w):
            try:
                return bool(w())
            except Exception:
                return False
        if isinstance(w, (set, frozenset, list, tuple)):
            return tab in w
        return tab == w


def binds(rows, mode="normal", **kw):
    """Bind objects from (seq, action, desc) tuples (ganit's old table form)."""
    return [r if isinstance(r, Bind) else Bind(r[0], r[1], r[2] if len(r) > 2 else "", mode=mode, **kw)
            for r in rows]


@dataclass
class Keymap:
    """The binds that apply right now (one mode, one tab). A later bind with
    the same sequence replaces an earlier one, so a tool's binds override the
    core's."""
    binds_in: list = field(default_factory=list)
    groups: dict = field(default_factory=dict)

    def __post_init__(self):
        self.table = {}
        for b in self.binds_in:
            self.table[b.seq] = b
        self._toks = {seq: tokens(seq) for seq in self.table}
        self.names = dict(GROUPS)
        self.names.update(PREFIX_NAMES)
        self.names.update(self.groups or {})

    def lookup(self, pending):
        """(the bind for exactly this or None, whether a longer bind starts with it)."""
        exact = self.table.get(pending)
        pt = tokens(pending)
        longer = any(len(t) > len(pt) and t[:len(pt)] == pt for t in self._toks.values())
        return exact, longer

    def group_name(self, prefix):
        return self.names.get(prefix, "more")

    def next_keys(self, pending):
        """[(token, what, is_group)] after `pending`: a bind's description, or
        a group's name (with …)."""
        out, seen = [], {}
        for seq, b in self.table.items():
            pt, st = tokens(pending), self._toks.get(seq) or tokens(seq)
            if seq == pending or st[:len(pt)] != pt or b.hidden:
                continue
            rest = st[len(pt):]
            tok = rest[0]
            if tok in seen:
                continue
            seen[tok] = True
            if len(rest) == 1 and not self.lookup(seq)[1]:
                out.append((tok, b.desc, False))
            else:
                out.append((tok, self.group_name(pending + tok) + "…", True))
        return out

    def visible(self):
        return [b for b in self.table.values() if not b.hidden and b.desc]


class Result:
    """What one key did: kind is "pending" (a sequence or count goes on),
    "run" (bind, count), "unknown" (seq: no such key), "cancel" (Esc dropped
    a pending sequence or count)."""
    __slots__ = ("bind", "count", "kind", "seq")

    def __init__(self, kind, bind=None, count=1, seq=""):
        self.kind, self.bind, self.count, self.seq = kind, bind, count, seq

    def __repr__(self):
        return f"Result({self.kind!r}, {self.bind and self.bind.seq!r}, count={self.count}, seq={self.seq!r})"


class Machine:
    """A count and a pending sequence between key presses."""

    def __init__(self):
        self.pending = ""
        self.count = ""

    def busy(self):
        return bool(self.pending or self.count)

    def reset(self):
        self.pending, self.count = "", ""

    def typed(self):
        """What's been typed so far, spelled ("5 Space y")."""
        return (self.count + (" " if self.count and self.pending else "") + spell(self.pending)).strip()

    def feed(self, km, tok, counts=True):
        """One token through the keymap. An exact bind on a digit beats the
        count (dvara's dock, doot's actions); "0" only counts after 1-9."""
        if tok == "<Esc>" and self.busy():
            self.reset()
            return Result("cancel")
        if (counts and not self.pending and len(tok) == 1 and tok.isdigit()
                and (tok != "0" or self.count)
                and (self.count or (tok not in km.table and not km.lookup(tok)[1]))):
            self.count += tok
            return Result("pending")
        seq = self.pending + tok
        exact, longer = km.lookup(seq)
        if longer:
            self.pending = seq
            return Result("pending", seq=seq)
        count = int(self.count or 1)
        self.reset()
        if exact is None:
            return Result("unknown", seq=seq, count=count)
        return Result("run", exact, count, seq)


# ------------------------------------------------------------- lists of keys
def help_rows(km, leader_groups=True):
    """[(section, [(keys, what)])] for a help screen: direct keys, then each
    Space group, in sequence order."""
    direct, lead = [], {}
    for b in km.visible():
        if b.seq.startswith(LEADER) and len(b.seq) > 1:
            t = tokens(b.seq)
            g = t[0] + t[1] if len(t) > 2 else LEADER
            lead.setdefault(g, []).append((spell(b.seq), b.desc))
        else:
            direct.append((spell(b.seq), b.desc))
    out = []
    if direct:
        out.append(("Keys", direct))
    if leader_groups:
        for g in sorted(lead, key=lambda g: (g != LEADER, g)):
            name = "Leader" if g == LEADER else f"Space {spell(g[1:])} · {km.group_name(g)}"
            out.append((name, sorted(lead[g])))
    return out


def palette_rows(km):
    """[(keys, what, bind)] for a palette: every visible bind, leader ones first."""
    rows = [(spell(b.seq), b.desc, b) for b in km.visible()]
    rows.sort(key=lambda r: (not r[2].seq.startswith(LEADER), r[0]))
    return rows


def fuzzy(query, text):
    """Each word of the query appears in text, in order (case-insensitive)."""
    text, pos = text.lower(), 0
    for w in query.lower().split():
        i = text.find(w, pos)
        if i < 0:
            return False
        pos = i + len(w)
    return True


def annotations(source, scoped):
    """`# keybind:` lines (Vayu's keybinding search reads them).
    scoped: [(scope, mode, [Bind])]. The mode goes after the scope as
    ":normal" / ":insert", so the search can show and filter it."""
    lines = []
    for scope, mode, bs in scoped:
        suffix = f":{mode}" if mode in ("normal", "insert") else ""
        for b in bs:
            if b.hidden or not b.desc:
                continue
            lines.append(f"# keybind: {source}/{scope}{suffix} | {spell(b.seq)} | {b.desc}")
    return lines


def misused_groups(binds_list, groups=None):
    """Binds that put a reserved letter's group to another use: a tool's own
    group name for a reserved prefix. [(prefix, their name, reserved name)]."""
    out = []
    for prefix, name in (groups or {}).items():
        if prefix in GROUPS and GROUPS[prefix] != name and len(prefix) == 2:
            out.append((prefix, name, GROUPS[prefix]))
    return out
