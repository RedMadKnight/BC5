#!/usr/bin/env bash
# BC5 experiment 0356: the maintainer's test shortcut "BC5 emulator (test 0358)" on his desktop — the integrated
# play-pkg.sh (55531ab6) derived by mktest0358.pl into ~/bc5-work/exp0358/play-pkg-0358t.sh (a log per start in
# ~/bc5-work/exp0358/play/, nothing else changed), run with the private build ~/bc5-work/exp0358/kyty_emulator (the AMM
# fault ledger, 187910d8) through the shortcut's Exec. RT on comes from the shared input.cfg. Writes only under
# ~/bc5-work/exp0358 and the one .desktop file; the shared launcher and input.cfg are read.
# usage: shortcut0358.sh   (on the box, with mktest0358.pl beside it; no emulator started)
set -u
E=$HOME/bc5-work/exp0358; HERE=$(cd "$(dirname "$0")" && pwd)
SRC=$HOME/bc5-work/play-pkg.sh; OUT=$E/play-pkg-0358t.sh; BIN=$E/kyty_emulator
DESK=$(xdg-user-dir DESKTOP 2> /dev/null); DESK=${DESK:-$HOME/Pulpit}
WANT_LAUNCHER=${WANT_LAUNCHER:-55531ab6}; WANT_BIN=${WANT_BIN:-$(cat "$E/binary.md5" 2> /dev/null)}   # the last build0358*.sh writes it; override to pin
m() { md5sum < "$1" | cut -c1-8; }
[ "$(m "$SRC")" = "$WANT_LAUNCHER" ] || { echo "$SRC is md5 $(m "$SRC"), not $WANT_LAUNCHER (exp 0350's): stop"; exit 1; }
[ -x "$BIN" ] && [ -s "$E/binary.md5" ] || { echo "no $BIN (build0358.sh first)"; exit 1; }
[ "$(m "$BIN")" = "$WANT_BIN" ] && [ "$(cat "$E/binary.md5")" = "$WANT_BIN" ] || { echo "$BIN is md5 $(m "$BIN"), not $WANT_BIN: stop"; exit 1; }
[ -d "$DESK" ] || { echo "no desktop directory $DESK"; exit 1; }
mkdir -p "$E/play"
perl "$HERE/mktest0358.pl" "$SRC" "$OUT" || exit 1
bash -n "$OUT" || { echo "$OUT does not parse"; exit 1; }
chmod +x "$OUT"
diff -u "$SRC" "$OUT" > "$E/raw/play-pkg-0358t.diff"
[ "$(grep -c '^[-+][^-+]' "$E/raw/play-pkg-0358t.diff")" = 4 ] || { echo "the test launcher's diff is not the LOG line replaced + a comment + the recorder line: stop"; cat "$E/raw/play-pkg-0358t.diff"; exit 1; }
grep -q "^BC5_EMU=\|BC5_EMU" "$OUT" || { echo "the launcher does not take BC5_EMU: stop"; exit 1; }
D="$DESK/BC5 emulator (test 0358).desktop"
cat > "$D" <<EOF
[Desktop Entry]
Type=Application
Version=1.0
Name=BC5 emulator (test 0358)
Comment=BC5 test 0358: the integrated build (one ring, the 0341 guards, exps 0343, 0346, 0349) plus the thread trap v2: a crash in the title prints the faulting thread, every thread's worker slots and the frame-block pool's state; a pool sample once a second (for the null-object crash at eboot.bin+0x3d7eca0); RT on; a log per start in ~/bc5-work/exp0358/play/
Exec=/usr/bin/distrobox enter ubuntu -- /usr/bin/env BC5_EMU=$BIN $OUT
Icon=applications-games
Terminal=false
Categories=Game;
StartupNotify=false
EOF
chmod +x "$D"
echo "shortcut $D"; cat "$D"
echo "launcher $OUT md5 $(m "$OUT") (diff $E/raw/play-pkg-0358t.diff: $(grep -c '^[-+][^-+]' "$E/raw/play-pkg-0358t.diff") lines); emulator $BIN md5 $(m "$BIN") = $(cat "$E/binary.md5")"
echo "== the diff"; cat "$E/raw/play-pkg-0358t.diff"
echo "== how the launcher picks the emulator"; grep -n "BC5_EMU" "$OUT" | head -3
