#!/usr/bin/env bash
# BC5 exp 0401 e11: the maintainer's shortcut "BC5 emulator (e11 unpacked)" on his desktop (his "zrób mi skrót", 2026-11-10,
# after the e11 menu series). It runs ~/bc5-work/exp0411/play-e11-0411.sh (this directory's play-e11-0411.sh): e11's build
# 70df5cb1 through exp 0411's launcher, "e10 unpacked"'s switches plus e11's four, and the stall catcher beside it.
# Writes only the one .desktop file (made as a temporary file in ~/bc5-work/exp0411, validated, then moved); removes nothing.
# The other shortcuts stay as they are.
# Mode mem12800 (his "Tak", 2026-11-10 18:4x): a second shortcut, "BC5 emulator (e11 mem 12800)", running the wrapper's
# mode mem12800 (the launcher's settings with 12,800 MiB of guest memory instead of 13,824).
# usage (on the box): WANT_W=<md5 of play-e11-0411.sh> bash shortcut0411.sh [mem12800]
set -u
E=$HOME/bc5-work/exp0411; W=$E/play-e11-0411.sh; WANT_W=${WANT_W:?the md5 of play-e11-0411.sh}
case "${1:-}" in
  "") NAME="BC5 emulator (e11 unpacked)"; ARG=""; MEM="" ;;
  mem12800) NAME="BC5 emulator (e11 mem 12800)"; ARG=" mem12800"; MEM=" with 12800 MiB of guest memory (exp0401e8/run-mem12800.env)" ;;
  *) echo "usage: shortcut0411.sh [mem12800]"; exit 1 ;;
esac
DESK=$(xdg-user-dir DESKTOP 2> /dev/null); DESK=${DESK:-$HOME/Pulpit}
m() { md5sum < "$1" 2> /dev/null | cut -d' ' -f1; }
pgrep '^kyty_emulator' > /dev/null && { echo "an emulator runs: stop"; exit 1; }
[ "$(m "$W")" = "$WANT_W" ] || { echo "$W is not $WANT_W: stop"; exit 1; }
bash -n "$W" || { echo "$W does not parse: stop"; exit 1; }
[ -d "$DESK" ] && [ ! -L "$DESK" ] || { echo "no desktop directory $DESK: stop"; exit 1; }
D="$DESK/$NAME.desktop"
[ ! -e "$D" ] || grep -qxF "Name=$NAME" "$D" || { echo "$D exists and is not ours: stop"; exit 1; }
t=$E/shortcut-0411.tmp.$$.desktop
cat > "$t" << EOF
[Desktop Entry]
Type=Application
Version=1.0
Name=$NAME
Comment=BC5 exp 0401 e11 (2026-11-10): e10 unpacked's switches plus e11's four reset switches on (BC5_DIRECT_RESET_REPLAY_ACB, BC5_DIRECT_RESET_LABELS, BC5_DIRECT_LEARN_GUEST_ONLY, BC5_DIRECT_RESET_LABEL_JOURNAL)$MEM; private build 70df5cb1; starts the game directly; log ~/bc5-work/exp0411/play-last.log; stall dumps ~/bc5-work/exp0411/stall/
Exec=/usr/bin/bash $W$ARG
Icon=applications-games
Terminal=false
Categories=Game;
StartupNotify=false
EOF
if command -v desktop-file-validate > /dev/null; then desktop-file-validate "$t" || { rm -f "$t"; echo "the .desktop file is not valid: stop"; exit 1; }; fi
if [ -e "$D" ]; then k=$E/desktop-before-$(date +%Y%m%d-%H%M%S).bak; cp -p "$D" "$k" && echo "kept the old shortcut as $k"; fi
chmod +x "$t" && mv -fT "$t" "$D" || { rm -f "$t"; echo "cannot write $D"; exit 1; }
echo "shortcut $D, md5 $(m "$D")"; grep -E '^(Name|Exec)=' "$D"
echo "RT in the shared settings: $(grep -h 'RayTracing.PPSA03671' "$HOME"/bc5-work/input*.cfg 2> /dev/null | sort -u | tr '\n' ' ')"
