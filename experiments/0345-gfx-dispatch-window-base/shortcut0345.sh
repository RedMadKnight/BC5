#!/usr/bin/env bash
# BC5 experiment 0345: the maintainer's test shortcut "BC5 emulator (test 0345)" on his desktop — the integrated
# play-pkg.sh (5b469087) derived by mktest0345.pl into ~/bc5-work/exp0345/play-pkg-0345t.sh (a log per start in
# ~/bc5-work/exp0345/play/, BC5_DIRECT_GFX_BASE1=learn:1100000000 after the settings loop), run with the private build
# ~/bc5-work/exp0345/kyty_emulator through the shortcut's Exec. RT on comes from the shared input.cfg (30dd586e, exp 0342).
# Writes only under ~/bc5-work/exp0345 and the one .desktop file; the shared launcher and input.cfg are read.
# usage: shortcut0345.sh   (on the box, with mktest0345.pl beside it)
set -u
E=$HOME/bc5-work/exp0345; HERE=$(cd "$(dirname "$0")" && pwd)
SRC=$HOME/bc5-work/play-pkg.sh; OUT=$E/play-pkg-0345t.sh; BIN=$E/kyty_emulator
DESK=$(xdg-user-dir DESKTOP 2> /dev/null); DESK=${DESK:-$HOME/Pulpit}
WANT_LAUNCHER=${WANT_LAUNCHER:-5b469087}
m() { md5sum < "$1" | cut -c1-8; }
[ "$(m "$SRC")" = "$WANT_LAUNCHER" ] || { echo "$SRC is md5 $(m "$SRC"), not $WANT_LAUNCHER (exp 0342's): stop"; exit 1; }
[ -x "$BIN" ] && [ -s "$E/binary.md5" ] || { echo "no $BIN (build0345.sh first)"; exit 1; }
[ -d "$DESK" ] || { echo "no desktop directory $DESK"; exit 1; }
mkdir -p "$E/play"
perl "$HERE/mktest0345.pl" "$SRC" "$OUT" || exit 1
bash -n "$OUT" || { echo "$OUT does not parse"; exit 1; }
chmod +x "$OUT"
diff -u "$SRC" "$OUT" > "$E/raw/play-pkg-0345t.diff"
[ "$(grep -c '^[-+][^-+]' "$E/raw/play-pkg-0345t.diff")" = 4 ] || { echo "the test launcher's diff is not 1 line changed + 2 added (plus the removed LOG line): stop"; cat "$E/raw/play-pkg-0345t.diff"; exit 1; }
D="$DESK/BC5 emulator (test 0345).desktop"
cat > "$D" <<EOF
[Desktop Entry]
Type=Application
Version=1.0
Name=BC5 emulator (test 0345)
Comment=BC5 test 0345: the integrated build's objects with the experiment's backend (a dispatch with base-1 0 gets the title's window, or a NOP); RT on; a log per start in ~/bc5-work/exp0345/play/
Exec=/usr/bin/distrobox enter ubuntu -- /usr/bin/env BC5_EMU=$BIN $OUT
Icon=applications-games
Terminal=false
Categories=Game;
StartupNotify=false
EOF
chmod +x "$D"
echo "shortcut $D"; cat "$D"
echo "launcher $OUT md5 $(m "$OUT") (diff $E/raw/play-pkg-0345t.diff); emulator $BIN md5 $(m "$BIN") = $(cat "$E/binary.md5")"
