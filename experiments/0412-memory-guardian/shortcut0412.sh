#!/usr/bin/env bash
# BC5 exp 0412: the maintainer's two desktop shortcuts for the guardian's arms (the top session's order, 2026-11-10 evening),
# on shortcut0411.sh's pattern: "BC5 emulator (0412 ledger)" and "BC5 emulator (0412 low)". Each runs
# ~/bc5-work/exp0412/play-guard-0412.sh <arm>: the guardian's build 70a3bbee through exp 0412's launcher (ulimit -c 0), the
# "e11 unpacked" shortcut's 70 words plus the arm's BC5_GUARD_* words, and the read-only sampler beside it.
# Writes only the one .desktop file (made as a temporary file in ~/bc5-work/exp0412, validated, then moved); removes nothing.
# The other shortcuts stay as they are.
# usage (on the box): WANT_W=<md5 of play-guard-0412.sh> bash shortcut0412.sh ledger|low
set -u
E=$HOME/bc5-work/exp0412; W=$E/play-guard-0412.sh; WANT_W=${WANT_W:?the md5 of play-guard-0412.sh}
case "${1:-}" in
  ledger) WHAT="the guardian's ledger only (BC5_GUARD_LEDGER=1: two journal lines every 10 s, no behaviour change)" ;;
  low)    WHAT="ledger + BC5_GUARD_FILE=random,dontneed (PSI 10) + BC5_GUARD_APPLY_MIN_MS=50 + BC5_GUARD_PIN_CAP=11600 (log only) + BC5_GUARD_MLOCK=pinned (inert while the memlock limit is 2 GiB)" ;;
  *) echo "usage: shortcut0412.sh ledger|low"; exit 1 ;;
esac
ARM=$1; NAME="BC5 emulator (0412 $ARM)"
DESK=$(xdg-user-dir DESKTOP 2> /dev/null); DESK=${DESK:-$HOME/Pulpit}
m() { md5sum < "$1" 2> /dev/null | cut -d' ' -f1; }
pgrep '^kyty_emulator' > /dev/null && { echo "an emulator runs: stop"; exit 1; }
[ "$(m "$W")" = "$WANT_W" ] || { echo "$W is not $WANT_W: stop"; exit 1; }
bash -n "$W" || { echo "$W does not parse: stop"; exit 1; }
[ -d "$DESK" ] && [ ! -L "$DESK" ] || { echo "no desktop directory $DESK: stop"; exit 1; }
D="$DESK/$NAME.desktop"
[ ! -e "$D" ] || grep -qxF "Name=$NAME" "$D" || { echo "$D exists and is not ours: stop"; exit 1; }
t=$E/shortcut-0412.tmp.$$.desktop
cat > "$t" << EOF
[Desktop Entry]
Type=Application
Version=1.0
Name=$NAME
Comment=BC5 exp 0412 (2026-11-10): e11 unpacked's switches plus $WHAT; private build 70a3bbee; starts the game directly; log ~/bc5-work/exp0412/play-last.log; sampler lines ~/bc5-work/exp0412/sampler/
Exec=/usr/bin/bash $W $ARM
Icon=applications-games
Terminal=false
Categories=Game;
StartupNotify=false
EOF
if command -v desktop-file-validate > /dev/null; then desktop-file-validate "$t" || { rm -f "$t"; echo "the .desktop file is not valid: stop"; exit 1; }; fi
if [ -e "$D" ]; then k=$E/desktop-before-$(date +%Y%m%d-%H%M%S)-$ARM.bak; cp -p "$D" "$k" && echo "kept the old shortcut as $k"; fi
chmod +x "$t" && mv -fT "$t" "$D" || { rm -f "$t"; echo "cannot write $D"; exit 1; }
echo "shortcut $D, md5 $(m "$D")"; grep -E '^(Name|Exec)=' "$D"
echo "RT in the shared settings: $(grep -h 'RayTracing.PPSA03671' "$HOME"/bc5-work/input*.cfg 2> /dev/null | sort -u | tr '\n' ' ')"
