#!/usr/bin/env bash
# Clip Hunter - one-line installer for macOS and Linux. Paste this into Terminal:
#
#   curl -fsSL https://raw.githubusercontent.com/paudelbaibhav/clip-hunter/main/install.sh | bash
#
# It installs Python if needed, downloads Clip Hunter into ~/clip-hunter and runs install.py
# (Python packages, ffmpeg, TwitchDownloaderCLI, caption model, final check). Running it again updates the code and
# keeps your clips, settings and downloads.
# Options:  CLIP_HUNTER_DIR=~/somewhere   CLIP_HUNTER_DEMO=<twitch channel>   (put them before "bash")
set -euo pipefail

REPO="${CLIP_HUNTER_REPO:-paudelbaibhav/clip-hunter}"
DIR="${CLIP_HUNTER_DIR:-$HOME/clip-hunter}"
TARBALL="${CLIP_HUNTER_TARBALL:-https://github.com/$REPO/archive/refs/heads/main.tar.gz}"
say() { printf '\n==> %s\n' "$*"; }

find_python() {
  for c in python3 python; do
    if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
      echo "$c"; return 0
    fi
  done
  return 1
}

say "Clip Hunter installer"
PY="$(find_python || true)"
if [ -z "$PY" ]; then
  say "Installing Python 3.12"
  if [ "$(uname)" = "Darwin" ]; then
    command -v brew >/dev/null || { echo "Homebrew is needed: install it from https://brew.sh, then run this line again."; exit 1; }
    brew install python@3.12
  elif command -v apt-get >/dev/null; then
    sudo apt-get update -y && sudo apt-get install -y python3 python3-venv python3-pip
  elif command -v dnf >/dev/null; then
    sudo dnf install -y python3 python3-pip
  else
    echo "Please install Python 3.10+ with your package manager, then run this line again."; exit 1
  fi
  PY="$(find_python)" || { echo "Python 3.10+ still not found. Open a new terminal and run this line again."; exit 1; }
fi
# Debian/Ubuntu ship Python without venv support
if ! "$PY" -c 'import ensurepip' 2>/dev/null && command -v apt-get >/dev/null; then
  sudo apt-get install -y python3-venv
fi
echo "    Python: $PY"

say "Downloading Clip Hunter into $DIR"
TMP="$(mktemp -d)"
if [ -f "$TARBALL" ]; then tar xzf "$TARBALL" -C "$TMP"; else curl -fsSL "$TARBALL" | tar xz -C "$TMP"; fi
SRC="$(dirname "$(find "$TMP" -maxdepth 2 -name install.py | head -1)")"
mkdir -p "$DIR"
cp -R "$SRC"/. "$DIR"/        # code only; runs/, tools/, .venv/, channels.json are kept
rm -rf "$TMP"

say "Running install.py"
cd "$DIR"
"$PY" install.py ${CLIP_HUNTER_DEMO:+--demo "$CLIP_HUNTER_DEMO"} ${CLIP_HUNTER_ARGS:-}
say "Done. Clip Hunter is in $DIR"
