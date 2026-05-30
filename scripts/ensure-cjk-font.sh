#!/usr/bin/env bash
# Ensure a CJK (Chinese/Japanese/Korean) font is available so build-pptx renders
# CJK glyphs in headless QA / notes-PDF (e.g. a 魏晉祺 byline on a Thank-You slide).
#
# - No-op if any CJK font is already present (the common case: macOS/Windows ship
#   one; most Linux desktops have Noto CJK).
# - Otherwise downloads ONE Noto Sans CJK TC weight (~15 MB, SIL OFL — freely
#   redistributable) into the user font dir, so the repo stays lean (no 100 MB
#   font committed). Matches the font name build-pptx emits ("Noto Sans CJK TC").
# - Fully graceful: any failure (no network, no curl/wget) just warns and exits 0,
#   never breaks install/update. The .pptx itself is unaffected either way —
#   PowerPoint/Keynote substitute a system CJK font on the user's machine.
set -u

FONT_NAME="Noto Sans CJK TC"
URLS=(
    "https://cdn.jsdelivr.net/gh/notofonts/noto-cjk/Sans/OTF/TraditionalChinese/NotoSansCJKtc-Regular.otf"
    "https://github.com/notofonts/noto-cjk/raw/main/Sans/OTF/TraditionalChinese/NotoSansCJKtc-Regular.otf"
)

# 1) Already have a CJK-capable font? (fontconfig query covers Linux + macOS)
if command -v fc-list >/dev/null 2>&1; then
    if [ -n "$(fc-list :lang=zh 2>/dev/null)" ]; then
        echo "  CJK font already present — skipping."
        exit 0
    fi
fi

# 2) Destination per OS
case "$(uname -s)" in
    Darwin) DST="$HOME/Library/Fonts" ;;
    Linux)  DST="$HOME/.local/share/fonts/superstack-cjk" ;;
    *)      echo "  Unsupported OS for auto-install; install a CJK font manually."; exit 0 ;;
esac
mkdir -p "$DST"
OUT="$DST/NotoSansCJKtc-Regular.otf"
if [ -f "$OUT" ]; then
    echo "  $FONT_NAME already installed at $OUT."
    exit 0
fi

echo "  No CJK font found — downloading $FONT_NAME (~15 MB, OFL)..."
ok=""
for url in "${URLS[@]}"; do
    if command -v curl >/dev/null 2>&1; then
        curl -fsSL --max-time 120 "$url" -o "$OUT" && ok=1 && break
    elif command -v wget >/dev/null 2>&1; then
        wget -q --timeout=120 -O "$OUT" "$url" && ok=1 && break
    else
        echo "  Neither curl nor wget available; skipping (install a CJK font manually)."
        exit 0
    fi
done

# Validate it's a real OpenType file (magic 'OTTO' or 0x00010000), else discard.
if [ -z "$ok" ] || [ ! -s "$OUT" ]; then
    echo "  Download failed; skipping. CJK decks may show boxes in headless render."
    rm -f "$OUT"
    exit 0
fi
magic="$(head -c4 "$OUT" | tr -d '\0')"
if [ "$magic" != "OTTO" ] && [ "$(head -c2 "$OUT" | xxd -p 2>/dev/null)" != "0001" ]; then
    echo "  Downloaded file is not a valid font; discarding."
    rm -f "$OUT"
    exit 0
fi

command -v fc-cache >/dev/null 2>&1 && fc-cache -f "$DST" >/dev/null 2>&1
echo "  Installed $FONT_NAME -> $OUT"
exit 0
