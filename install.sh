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
#   /usr/local/lib/dvarapala/secretfile.py   saves a secret you typed, to its file
#   /usr/local/lib/dvarapala/keys.py         the window's vim keys (Vyom's keys module, vendored)
#   /usr/local/lib/dvarapala/{config,data}/  empty XDG dirs for the window, so
#                                          your GTK CSS can't restyle it
#   /usr/local/bin/{anumati,vayu-elevate}  -> dvarapala (its old names, kept working)
#   /usr/local/lib/systemd/user/dvarapala-mcp.socket, dvarapala.service
#                                          one MCP server for every agent session
#                                          (through pranali), started on demand;
#                                          the socket is enabled for you
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
lib=/usr/local/lib/dvarapala
units=/usr/local/lib/systemd/user
mode=${1:-install}
user_systemd() { [ -n "${XDG_RUNTIME_DIR:-}" ] && systemctl --user show-environment >/dev/null 2>&1; }

if [ "$mode" = "--uninstall" ]; then
  if user_systemd; then
    systemctl --user disable --now dvarapala-mcp.socket 2>/dev/null || true
    systemctl --user stop dvarapala.service 2>/dev/null || true
  fi
  sudo rm -f "$units/dvarapala-mcp.socket" "$units/dvarapala.service"
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
  "lib/secretfile.py:$lib/secretfile.py"
  "lib/keys.py:$lib/keys.py"
)
for pair in "${files[@]}"; do
  src=$here/${pair%%:*} dst=${pair#*:}
  if cmp -s "$src" "$dst" 2>/dev/null && [ "$(stat -c '%U %a' "$dst")" = "root 755" ]; then continue; fi
  differs "$dst"
  $check || sudo install -Dm755 -o root -g root "$src" "$dst"
done
for pair in "systemd/dvarapala-mcp.socket:$units/dvarapala-mcp.socket" \
            "systemd/dvarapala.service:$units/dvarapala.service"; do
  src=$here/${pair%%:*} dst=${pair#*:}
  if cmp -s "$src" "$dst" 2>/dev/null && [ "$(stat -c '%U %a' "$dst")" = "root 644" ]; then continue; fi
  differs "$dst"
  $check || { sudo install -Dm644 -o root -g root "$src" "$dst"; units_changed=1; }
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

# The shared MCP server's socket, for your user (agents' `dvarapala --mcp`
# reaches it through pranali; without either it serves in their process).
if user_systemd; then
  if ! systemctl --user is-enabled --quiet dvarapala-mcp.socket 2>/dev/null; then
    differs "dvarapala-mcp.socket (not enabled for you)"
    $check || { systemctl --user daemon-reload; systemctl --user enable --now dvarapala-mcp.socket; }
  elif [ -n "${units_changed:-}" ]; then
    systemctl --user daemon-reload
  fi
fi

if $check; then
  [ "$n" -eq 0 ] && echo "dvarapala is installed and matches this repo"
  [ "$n" -eq 0 ]
  exit
fi
[ "$n" -eq 0 ] && { echo "dvarapala already up to date"; exit 0; }
# A running shared server keeps the old code until it restarts; it isn't
# restarted under a request still waiting for your answer (each has its
# folder in $XDG_RUNTIME_DIR/dvarapala), whose agent would lose the result.
if user_systemd && systemctl --user is-active --quiet dvarapala.service; then
  if compgen -G "${XDG_RUNTIME_DIR}/dvarapala/2*" >/dev/null; then
    echo "dvarapala.service runs the old version until no request is waiting: then"
    echo "  systemctl --user restart dvarapala.service"
  else
    systemctl --user restart dvarapala.service
  fi
fi
echo "dvarapala installed: $n change(s). Try: dvarapala --why 'Test' --cmd 'id'"
