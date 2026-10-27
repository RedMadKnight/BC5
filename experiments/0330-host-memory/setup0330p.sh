#!/usr/bin/env bash
# BC5 experiment 0330: the test shortcut, second form (the maintainer's choice "a" after his session of 09:58, F395).
# - The import table and the zero scan come at 530 s and 540 s instead of 1800 s and 1810 s, before the ~642 s at which
#   his session froze. This is one line of exp0330/play-pkg-0330t.sh.
# - A host-side wrapper, exp0330/test0330p.sh, starts sample0330p.sh beside each session. The sampler writes
#   exp0330/play/mem-<time>.txt every 10 s: memory, reclaim, who reads (the emulator, bc5-mount, the NVMe), VRAM. It ends
#   with the emulator.
# - The shortcut runs the wrapper. Its name stays "BC5 emulator (test 0330: pamięć)".
# The previous launcher and shortcut are kept in exp0330/shortcut-1800/. Nothing is started.
# usage: setup0330p.sh   (on the box, with sample0330p.sh in ~/bc5-work/exp0330)
set -u
W=$HOME/bc5-work; E=$W/exp0330; R=$E/raw; B=$E/shortcut-1800; LOCK=$W/BOX-LOCK
L=$E/play-pkg-0330t.sh; S=$E/sample0330p.sh; WR=$E/test0330p.sh; BIN=$E/kyty_emulator
DESK=$(xdg-user-dir DESKTOP 2> /dev/null); DESK=${DESK:-$HOME/Desktop}; LNK="$DESK/BC5 emulator (test 0330).desktop"
OLD='export BC5_DIRECT_BREAKDOWN_AT=1800 BC5_DIRECT_BREAKDOWN_NODATA=1 BC5_DIRECT_ZEROSCAN_AT=1810 BC5_DIRECT_JOURNAL_DONTNEED=1  # exp 0330 (the maintainer'"'"'s test): the import table and the zero scan after 30 min, the journal out of the page cache'
NEW='export BC5_DIRECT_BREAKDOWN_AT=530 BC5_DIRECT_BREAKDOWN_NODATA=1 BC5_DIRECT_ZEROSCAN_AT=540 BC5_DIRECT_JOURNAL_DONTNEED=1  # exp 0330 (the maintainer'"'"'s test, F395): the import table and the zero scan at 530/540 s, before the ~642 s freeze; the journal out of the page cache'
md5() { md5sum < "$1" | cut -c1-8; }
pgrep '^kyty_emulator' > /dev/null && { echo "an emulator runs: stop"; exit 1; }
ps -eo args= | grep -qE '^(/[^ ]*/)?bash [^ ]*/(play-pkg[^ ]*|test0330p)\.sh( |$)' && { echo "a launcher runs: stop"; exit 1; }
[ -s "$LOCK" ] && { echo "box locked: $(cat "$LOCK")"; exit 1; }
[ "$(md5 "$L")" = 73845711 ] || { echo "$L is not 73845711: stop"; exit 1; }
[ "$(md5 "$LNK")" = ee3dd64d ] || { echo "the shortcut is not ee3dd64d: stop"; exit 1; }
[ "$(md5 "$BIN")" = a86787f1 ] || { echo "$BIN is not a86787f1: stop"; exit 1; }
[ "$(grep -cxF -- "$OLD" "$L")" = 1 ] || { echo "the switches line is not there once: stop"; exit 1; }
[ -x "$S" ] && bash -n "$S" || { echo "no runnable $S: stop"; exit 1; }
for f in "$B" "$WR"; do [ -e "$f" ] && { echo "$f exists: stop"; exit 1; }; done
echo "cloud exp 0330 | the test shortcut, second form (files only, no emulator) | start $(date +%H:%M) | until ~$(date -d +3min +%H:%M)" > "$LOCK"
trap 'grep -q "^cloud exp 0330 | the test shortcut" "$LOCK" 2> /dev/null && rm -f "$LOCK"' EXIT
mkdir -p "$B" "$R" "$E/play" || exit 1
cp -p "$L" "$B/play-pkg-0330t.sh" && cp -p "$LNK" "$B/BC5 emulator (test 0330).desktop" || exit 1
restore() { cat "$B/play-pkg-0330t.sh" > "$L"; cat "$B/BC5 emulator (test 0330).desktop" > "$LNK"; rm -f "$WR"; echo "RESTORED"; exit 1; }
awk -v o="$OLD" -v n="$NEW" '$0 == o {print n; next} {print}' "$B/play-pkg-0330t.sh" > "$L.new" && cat "$L.new" > "$L" && rm -f "$L.new" || restore
bash -n "$L" || { echo "$L does not parse"; restore; }
diff -u "$B/play-pkg-0330t.sh" "$L" > "$R/play-pkg-0330t-v2.diff"
[ "$(grep -c '^+[^+]' "$R/play-pkg-0330t-v2.diff")" = 1 ] && [ "$(grep -c '^-[^-]' "$R/play-pkg-0330t-v2.diff")" = 1 ] || { echo "the diff is not one line changed"; restore; }
n=$(grep -nF -- "BC5_DIRECT_ZEROSCAN_AT=540" "$L" | cut -d: -f1)
got=$(env -i HOME="$HOME" PATH="$PATH" bash -c 'source <(sed -n "1,$2p" "$1") > /dev/null 2>&1; echo "LAZY=${BC5_DIRECT_LAZY_NAMES:-} | BD=${BC5_DIRECT_BREAKDOWN_AT:-} ND=${BC5_DIRECT_BREAKDOWN_NODATA:-} ZS=${BC5_DIRECT_ZEROSCAN_AT:-} DN=${BC5_DIRECT_JOURNAL_DONTNEED:-}"' _ "$L" "$n")
echo "the launcher's first $n lines give: $got"
[ "$got" = "LAZY=orbis_user_malloc,Wwise,SoundAlloc,FileSystem,UIStringAlloc | BD=530 ND=1 ZS=540 DN=1" ] || { echo "not the expected settings"; restore; }
cat > "$WR" << 'EOF'
#!/usr/bin/env bash
# BC5 experiment 0330: the test shortcut's host side (2026-10-26, F395). It starts the sampler beside the session, then the
# test launcher in the distrobox, as the first form of the shortcut did.
E=$HOME/bc5-work/exp0330; T=$(date +%Y%m%d-%H%M%S)
mkdir -p "$E/play"
pgrep '^kyty_emulator' > /dev/null || setsid nohup "$E/sample0330p.sh" "$E/play/mem-$T.txt" 7200 < /dev/null > /dev/null 2>&1 &
exec /usr/bin/distrobox enter ubuntu -- /usr/bin/env BC5_EMU="$E/kyty_emulator" "$E/play-pkg-0330t.sh"
EOF
chmod 755 "$WR"; bash -n "$WR" || { echo "$WR does not parse"; restore; }
cat > "$LNK" << EOF
[Desktop Entry]
Type=Application
Name=BC5 emulator (test 0330: pamięć)
Comment=BC5 exp 0330: the normal build with the 0330 memory switches (private binary a86787f1), the integrated lazy list, the import table and the zero scan at 530/540 s, a memory sampler every 10 s; logs in ~/bc5-work/exp0330/play/
Exec=$WR
Icon=applications-games
Terminal=false
EOF
chmod 755 "$LNK"
echo "launcher $L md5 $(md5 "$L"); wrapper $WR md5 $(md5 "$WR"); sampler $S md5 $(md5 "$S"); shortcut md5 $(md5 "$LNK")"
echo "undo: cat \"$B/play-pkg-0330t.sh\" > \"$L\"; cat \"$B/BC5 emulator (test 0330).desktop\" > \"$LNK\"; rm \"$WR\""
