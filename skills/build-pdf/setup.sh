#!/usr/bin/env bash
# build-pdf setup
#
# Idempotent. Safe to re-run.  Ensures:
#   1. Noto Sans CJK is installed (brew on macOS) so weasyprint has a
#      CJK font that renders reliably across PDF viewers.
#   2. fontconfig is configured to prefer Noto over the macOS-bundled
#      CJK fonts (PingFang, Heiti, Hiragino, Songti, ST*) which produce
#      CFF subsets that some viewers (e.g. PDFgear) can't render.
#
# Run:  bash skills/build-pdf/setup.sh

set -euo pipefail

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "==> build-pdf setup"

# 1. Noto Sans CJK
if ! fc-list 2>/dev/null | grep -qi "Noto Sans CJK TC"; then
    if [[ "$OSTYPE" == "darwin"* ]]; then
        if command -v brew >/dev/null 2>&1; then
            echo "    Installing font-noto-sans-cjk via brew..."
            brew install --cask font-noto-sans-cjk
        else
            echo "    ERROR: Noto Sans CJK not installed and brew not found."
            echo "    Install brew (https://brew.sh) or manually drop NotoSansCJK.ttc"
            echo "    into ~/Library/Fonts/ and re-run this script."
            exit 1
        fi
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        echo "    Noto Sans CJK not found.  On Debian/Ubuntu:"
        echo "      sudo apt install fonts-noto-cjk fonts-noto-cjk-extra"
        echo "    On Fedora: sudo dnf install google-noto-sans-cjk-fonts"
        exit 1
    fi
else
    echo "    Noto Sans CJK already installed ✓"
fi

# 2. fontconfig override (only on macOS — Linux usually doesn't need this)
if [[ "$OSTYPE" == "darwin"* ]]; then
    FC_USER_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/fontconfig"
    FC_USER_FILE="$FC_USER_DIR/fonts.conf"
    SKILL_FC_FILE="$SKILL_DIR/fontconfig.conf"

    if [[ -f "$FC_USER_FILE" ]] && cmp -s "$SKILL_FC_FILE" "$FC_USER_FILE"; then
        echo "    fontconfig override already in place ✓"
    elif [[ -f "$FC_USER_FILE" ]]; then
        # User has an existing fontconfig — back it up and warn them.
        cp "$FC_USER_FILE" "$FC_USER_FILE.bak.$(date +%s)"
        echo "    Backed up existing $FC_USER_FILE"
        cp "$SKILL_FC_FILE" "$FC_USER_FILE"
        echo "    Installed build-pdf fontconfig override"
    else
        mkdir -p "$FC_USER_DIR"
        cp "$SKILL_FC_FILE" "$FC_USER_FILE"
        echo "    Installed fontconfig override at $FC_USER_FILE"
    fi
    fc-cache -frv >/dev/null 2>&1 || true
fi

echo "==> build-pdf setup complete"
