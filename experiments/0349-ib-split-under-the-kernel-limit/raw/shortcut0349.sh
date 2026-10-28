#!/usr/bin/env bash
# BC5 experiment 0349 (0343 + 0346 + 0349): the maintainer's test shortcut "BC5 emulator (test 0349)" on his desktop — the integrated
# play-pkg.sh (5b469087) derived by mktest0349.pl into ~/bc5-work/exp0349/play-pkg-0349t.sh (a log per start in
# ~/bc5-work/exp0349/play/, BC5_DIRECT_HOST_INDIRECT=learn:1100000000 after the settings loop), run with the private build
# ~/bc5-work/exp0349/kyty_emulator through the shortcut's Exec. RT on comes from the shared input.cfg (30dd586e, exp 0342).
# Writes only under ~/bc5-work/exp0349 and the one .desktop file; the shared launcher and input.cfg are read.
# usage: shortcut0349.sh   (on the box, with mktest0349.pl beside it)
set -u
E=$HOME/bc5-work/exp0349; HERE=$(cd "$(dirname "$0")" && pwd)
SRC=$HOME/bc5-work/play-pkg.sh; OUT=$E/play-pkg-0349t.sh; BIN=$E/kyty_emulator
DESK=$(xdg-user-dir DESKTOP 2> /dev/null); DESK=${DESK:-$HOME/Pulpit}
WANT_LAUNCHER=${WANT_LAUNCHER:-5b469087}
m() { md5sum < "$1" | cut -c1-8; }
[ "$(m "$SRC")" = "$WANT_LAUNCHER" ] || { echo "$SRC is md5 $(m "$SRC"), not $WANT_LAUNCHER (exp 0342's): stop"; exit 1; }
[ -x "$BIN" ] && [ -s "$E/binary.md5" ] || { echo "no $BIN (build0349.sh first)"; exit 1; }
[ -d "$DESK" ] || { echo "no desktop directory $DESK"; exit 1; }
mkdir -p "$E/play"
perl "$HERE/mktest0349.pl" "$SRC" "$OUT" || exit 1
bash -n "$OUT" || { echo "$OUT does not parse"; exit 1; }
chmod +x "$OUT"
diff -u "$SRC" "$OUT" > "$E/raw/play-pkg-0349t.diff"
[ "$(grep -c '^[-+][^-+]' "$E/raw/play-pkg-0349t.diff")" = 4 ] || { echo "the test launcher's diff is not 1 line changed + 2 added (plus the removed LOG line): stop"; cat "$E/raw/play-pkg-0349t.diff"; exit 1; }
D="$DESK/BC5 emulator (test 0349).desktop"
cat > "$D" <<EOF
[Desktop Entry]
Type=Application
Version=1.0
Name=BC5 emulator (test 0349)
Comment=BC5 test 0349: the integrated build with exp 0349 (a job over the kernel limit of 0xfffff dwords cut into up to four IBs instead of being refused, the carried base register committed only after a successful submit), exp 0343 (soft-CP replay polls bounded at 8 ms and journaled) and exp 0346 (a dispatch after the title zeroes its base register resolved by the host or NOP-ed); RT on; a log per start in ~/bc5-work/exp0349/play/
Exec=/usr/bin/distrobox enter ubuntu -- /usr/bin/env BC5_EMU=$BIN $OUT
Icon=applications-games
Terminal=false
Categories=Game;
StartupNotify=false
EOF
chmod +x "$D"
echo "shortcut $D"; cat "$D"
echo "launcher $OUT md5 $(m "$OUT") (diff $E/raw/play-pkg-0349t.diff); emulator $BIN md5 $(m "$BIN") = $(cat "$E/binary.md5")"
