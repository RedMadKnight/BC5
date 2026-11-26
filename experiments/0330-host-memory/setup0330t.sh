#!/usr/bin/env bash
# BC5 experiment 0330: the maintainer's test shortcut "BC5 emulator (test 0330: pamięć)" (his choice "a", 2026-10-26), as
# exp 0328's: the private binary (a86787f1, the normal build with the 0330 switches) through a copy of today's play-pkg.sh
# (b10eac6d, with the integrated lazy list), with one log per start in ~/bc5-work/exp0330/play/. The copy differs in two
# places:
#   - the per-start log;
#   - after the lazy-list line: the import table at 1800 s (no data walk), the zero scan at 1810 s, and the journal's
#     page-cache drop (arm B: no frame-rate cost; the normal build's journal would otherwise go through the page cache
#     for the whole session).
# His live saves, his input.cfg (RT off) and the package mount are the normal shortcut's: this is his play, not a bench.
# The shared launchers and builds are not written. Nothing is started.
# usage: setup0330t.sh   (on the box)
set -u
W=$HOME/bc5-work; E=$W/exp0330; R=$E/raw; LOCK=$W/BOX-LOCK
SRC=$W/play-pkg.sh; DST=$E/play-pkg-0330t.sh; BIN=$E/kyty_emulator
DESK=$(xdg-user-dir DESKTOP 2> /dev/null); DESK=${DESK:-$HOME/Desktop}; LNK="$DESK/BC5 emulator (test 0330).desktop"
OLD_LOG='LOG=~/bc5-work/play-pkg-last.log'
ANCHOR_SUB='exp 0330 (F394)'
# shellcheck disable=SC2016
NEW_LOG='LOG=~/bc5-work/exp0330/play/play-$(date +%Y%m%d-%H%M%S).log  # exp 0330 (the maintainer'"'"'s test): one log per start, beside the test binary'
DIAG='export BC5_DIRECT_BREAKDOWN_AT=1800 BC5_DIRECT_BREAKDOWN_NODATA=1 BC5_DIRECT_ZEROSCAN_AT=1810 BC5_DIRECT_JOURNAL_DONTNEED=1  # exp 0330 (the maintainer'"'"'s test): the import table and the zero scan after 30 min, the journal out of the page cache'
md5() { md5sum < "$1" | cut -c1-8; }
pgrep '^kyty_emulator' > /dev/null && { echo "an emulator runs: stop"; exit 1; }
ps -eo args= | grep -qE '^(/[^ ]*/)?bash [^ ]*/play-pkg[^ ]*\.sh( |$)' && { echo "a launcher runs: stop"; exit 1; }
[ -s "$LOCK" ] && { echo "box locked: $(cat "$LOCK")"; exit 1; }
[ "$(md5 "$SRC")" = b10eac6d ] || { echo "$SRC is not b10eac6d: stop"; exit 1; }
[ "$(md5 "$BIN")" = a86787f1 ] || { echo "$BIN is not a86787f1: stop"; exit 1; }
[ "$(grep -cxF -- "$OLD_LOG" "$SRC")" = 1 ] || { echo "the LOG line is not there once: stop"; exit 1; }
[ "$(grep -cF -- "$ANCHOR_SUB" "$SRC")" = 1 ] || { echo "the lazy-list line is not there once: stop"; exit 1; }
[ -d "$DESK" ] || { echo "no desktop directory $DESK: stop"; exit 1; }
for f in "$DST" "$LNK"; do [ -e "$f" ] && { echo "$f exists: stop"; exit 1; }; done
echo "cloud exp 0330 | the test shortcut (files only, no emulator) | start $(date +%H:%M) | until ~$(date -d +3min +%H:%M)" > "$LOCK"
trap 'grep -q "^cloud exp 0330 | the test shortcut" "$LOCK" 2> /dev/null && rm -f "$LOCK"' EXIT
mkdir -p "$E/play" "$R" || exit 1
awk -v old="$OLD_LOG" -v nl="$NEW_LOG" -v sub_="$ANCHOR_SUB" -v d="$DIAG" '$0 == old {print nl; next} {print} index($0, sub_) {print d}' "$SRC" > "$DST" || exit 1
chmod 755 "$DST"
bash -n "$DST" || { echo "$DST does not parse"; rm -f "$DST"; exit 1; }
diff -u "$SRC" "$DST" > "$R/play-pkg-0330t.diff"
[ "$(grep -c '^+[^+]' "$R/play-pkg-0330t.diff")" = 2 ] && [ "$(grep -c '^-[^-]' "$R/play-pkg-0330t.diff")" = 1 ] || { echo "the diff is not two lines in, one out"; rm -f "$DST"; exit 1; }
n=$(grep -nF -- "BC5_DIRECT_ZEROSCAN_AT=1810" "$DST" | cut -d: -f1)
got=$(env -i HOME="$HOME" PATH="$PATH" bash -c 'source <(sed -n "1,$2p" "$1") > /dev/null 2>&1; echo "LOG=$LOG | LAZY=${BC5_DIRECT_LAZY_NAMES:-} | BD=${BC5_DIRECT_BREAKDOWN_AT:-} ND=${BC5_DIRECT_BREAKDOWN_NODATA:-} ZS=${BC5_DIRECT_ZEROSCAN_AT:-} DN=${BC5_DIRECT_JOURNAL_DONTNEED:-}"' _ "$DST" "$n")
echo "the copy's first $n lines give: $got"
case "$got" in *"/exp0330/play/play-"*"LAZY=orbis_user_malloc,Wwise,SoundAlloc,FileSystem,UIStringAlloc | BD=1800 ND=1 ZS=1810 DN=1") ;; *) echo "not the expected settings"; rm -f "$DST"; exit 1 ;; esac
cat > "$LNK" << EOF
[Desktop Entry]
Type=Application
Name=BC5 emulator (test 0330: pamięć)
Comment=BC5 exp 0330: the normal build with the 0330 memory switches (private binary a86787f1), the integrated lazy list, the zero scan after 30 min; a log per start in ~/bc5-work/exp0330/play/
Exec=/usr/bin/distrobox enter ubuntu -- /usr/bin/env BC5_EMU=$BIN $DST
Icon=applications-games
Terminal=false
EOF
chmod 755 "$LNK"
echo "launcher $DST md5 $(md5 "$DST"); shortcut \"$LNK\" md5 $(md5 "$LNK"); logs in $E/play/"
echo "undo: rm \"$LNK\" \"$DST\""
