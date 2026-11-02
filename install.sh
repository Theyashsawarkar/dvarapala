#!/usr/bin/env bash
# Installs dvarapala root-owned, so an AI agent running as your user can't
# edit what the approval window shows or what runs as root. Run it as your
# user from a clone of this repo; it calls sudo.
#
#   ./install.sh            install whatever differs
#   ./install.sh --check    list what differs, exit 1 if anything does
#   ./install.sh --uninstall
#
# Installs:
#   /usr/local/bin/dvarapala                 the CLI / MCP server agents call
#   /usr/local/lib/dvarapala/dialog.py       the approval window (GTK 4)
#   /usr/local/lib/dvarapala/theme.py        its look and the theme readability check
#   /usr/local/lib/dvarapala/remote.py       answering from the phone, through ekatva
#   /usr/local/lib/dvarapala/runner.py       runs the approved commands as root
#   /usr/local/lib/dvarapala/userrun.py      runs the approved commands as you
#   /usr/local/lib/dvarapala/{config,data}/  empty XDG dirs for the window, so
#                                          your GTK CSS can't restyle it
#   /usr/local/bin/{anumati,vayu-elevate}  -> dvarapala (its old names, kept working)
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
lib=/usr/local/lib/dvarapala
mode=${1:-install}

if [ "$mode" = "--uninstall" ]; then
  sudo rm -rf /usr/local/bin/dvarapala "$lib"
  for old in anumati vayu-elevate; do [ -L "/usr/local/bin/$old" ] && sudo rm -f "/usr/local/bin/$old"; done
  echo "dvarapala removed (the audit log /var/log/dvarapala.log is kept)"
  exit 0
fi
check=false
[ "$mode" = "--check" ] && check=true

n=0
differs() { n=$((n + 1)); if $check; then echo "differs: $1"; fi; }

# Dependencies: Arch package names; other distributions, see the README.
if command -v pacman >/dev/null; then
  missing=()
  for p in python python-gobject gtk4 libadwaita libnotify sudo; do
    pacman -Q "$p" >/dev/null 2>&1 || missing+=("$p")
  done
  if [ "${#missing[@]}" -gt 0 ]; then
    differs "packages not installed: ${missing[*]}"
    $check || sudo pacman -S --needed --noconfirm "${missing[@]}"
  fi
fi

files=(
  "bin/dvarapala:/usr/local/bin/dvarapala"
  "lib/dialog.py:$lib/dialog.py"
  "lib/theme.py:$lib/theme.py"
  "lib/remote.py:$lib/remote.py"
  "lib/runner.py:$lib/runner.py"
  "lib/userrun.py:$lib/userrun.py"
)
for pair in "${files[@]}"; do
  src=$here/${pair%%:*} dst=${pair#*:}
  if cmp -s "$src" "$dst" 2>/dev/null && [ "$(stat -c '%U %a' "$dst")" = "root 755" ]; then continue; fi
  differs "$dst"
  $check || sudo install -Dm755 -o root -g root "$src" "$dst"
done
for d in "$lib" "$lib/config" "$lib/data"; do
  if [ -d "$d" ] && [ "$(stat -c '%U %a' "$d")" = "root 755" ]; then continue; fi
  differs "$d (root-owned directory)"
  $check || sudo install -d -m755 -o root -g root "$d"
done

# The old names: root-owned links, so agents and notes that still say
# anumati or vayu-elevate keep working. The old installs' files go.
for old in anumati vayu-elevate; do
  if [ "$(readlink "/usr/local/bin/$old" 2>/dev/null)" != /usr/local/bin/dvarapala ]; then
    differs "/usr/local/bin/$old (link to dvarapala)"
    $check || sudo ln -sfn /usr/local/bin/dvarapala "/usr/local/bin/$old"
  fi
  if [ -e "/usr/local/lib/$old" ]; then
    differs "/usr/local/lib/$old (old install, to remove)"
    $check || sudo rm -rf "/usr/local/lib/$old"
  fi
done

if $check; then
  [ "$n" -eq 0 ] && echo "dvarapala is installed and matches this repo"
  [ "$n" -eq 0 ]
  exit
fi
[ "$n" -eq 0 ] && { echo "dvarapala already up to date"; exit 0; }
echo "dvarapala installed: $n change(s). Try: dvarapala --why 'Test' --cmd 'id'"
