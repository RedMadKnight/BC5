#!/usr/bin/env bash
# BC5 experiment 0360 (exp 0358's shortcut0358.sh): the maintainer's test shortcut "BC5 emulator (test 0360)" on his
# desktop — the integrated play-pkg.sh derived by mktest0360.pl into ~/bc5-work/exp0360/play-pkg-0360t.sh (a log and a
# pad record per start in ~/bc5-work/exp0360/play/, nothing else changed), run with a private exp 0360 build through the
# shortcut's Exec. RT on comes from the shared input.cfg. Writes only under ~/bc5-work/exp0360 and the one .desktop file;
# the shared launcher and input.cfg are read.
# usage: shortcut0360.sh <variant>   (on the box, with mktest0360.pl beside it; no emulator started)
set -u
VAR=${1:?a variant}; E=$HOME/bc5-work/exp0360; HERE=$(cd "$(dirname "$0")" && pwd)
SRC=$HOME/bc5-work/play-pkg.sh; OUT=$E/play-pkg-0360t.sh; BIN=$E/$VAR/kyty_emulator
DESK=$(xdg-user-dir DESKTOP 2> /dev/null); DESK=${DESK:-$HOME/Pulpit}
WANT_LAUNCHER=${WANT_LAUNCHER:-55531ab6}; WANT_BIN=${WANT_BIN:-$(cat "$E/$VAR/binary.md5" 2> /dev/null)}
WHAT_DEFAULT="the CPU meter (one journal line a second: the CPU and run-queue wait of every thread, the CPUs of the box, bc5-mount) and the CPU sampler on the threads of the title"
WHAT=${SHORTCUT_WHAT:-$WHAT_DEFAULT}
m() { md5sum < "$1" | cut -c1-8; }
[ "$(m "$SRC")" = "$WANT_LAUNCHER" ] || { echo "$SRC is md5 $(m "$SRC"), not $WANT_LAUNCHER: stop"; exit 1; }
[ -x "$BIN" ] && [ -s "$E/$VAR/binary.md5" ] || { echo "no $BIN (build0360.sh first)"; exit 1; }
[ "$(m "$BIN")" = "$WANT_BIN" ] && [ "$(cat "$E/$VAR/binary.md5")" = "$WANT_BIN" ] || { echo "$BIN is md5 $(m "$BIN"), not $WANT_BIN: stop"; exit 1; }
[ -d "$DESK" ] || { echo "no desktop directory $DESK"; exit 1; }
mkdir -p "$E/play" "$E/raw"
perl "$HERE/mktest0360.pl" "$SRC" "$OUT" || exit 1
bash -n "$OUT" || { echo "$OUT does not parse"; exit 1; }
chmod +x "$OUT"
diff -u "$SRC" "$OUT" > "$E/raw/play-pkg-0360t.diff"
[ "$(grep -c '^[-+][^-+]' "$E/raw/play-pkg-0360t.diff")" = 4 ] || { echo "the test launcher's diff is not the LOG line replaced + a comment + the recorder line: stop"; cat "$E/raw/play-pkg-0360t.diff"; exit 1; }
grep -q "BC5_EMU" "$OUT" || { echo "the launcher does not take BC5_EMU: stop"; exit 1; }
D="$DESK/BC5 emulator (test 0360).desktop"
cat > "$D" <<EOF
[Desktop Entry]
Type=Application
Version=1.0
Name=BC5 emulator (test 0360)
Comment=BC5 test 0360 ($VAR, md5 $WANT_BIN): the integrated build (one ring, the 0341 guards, exps 0343, 0346, 0349) plus $WHAT; measurement only, no fix; RT on; a log per start in ~/bc5-work/exp0360/play/
Exec=/usr/bin/distrobox enter ubuntu -- /usr/bin/env BC5_EMU=$BIN $OUT
Icon=applications-games
Terminal=false
Categories=Game;
StartupNotify=false
EOF
chmod +x "$D"
echo "shortcut $D"; cat "$D"
echo "launcher $OUT md5 $(m "$OUT") (diff $E/raw/play-pkg-0360t.diff: $(grep -c '^[-+][^-+]' "$E/raw/play-pkg-0360t.diff") lines); emulator $BIN md5 $(m "$BIN") = $(cat "$E/$VAR/binary.md5")"
echo "== the diff"; cat "$E/raw/play-pkg-0360t.diff"
echo "== how the launcher picks the emulator"; grep -n "BC5_EMU" "$OUT" | head -3
