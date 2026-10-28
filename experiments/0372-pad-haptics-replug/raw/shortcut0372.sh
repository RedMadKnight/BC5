#!/usr/bin/env bash
# BC5 experiment 0372 (exp 0359's shortcut0359.sh): the maintainer's test shortcut "BC5 emulator (test 0372)" on his
# desktop — play-pkg.sh (55531ab6) derived by mkplay0372.pl into ~/bc5-work/exp0372/play-pkg-0372t.sh (the private
# build ~/bc5-work/exp0372/kyty_emulator, the audio trace on, a log per start in ~/bc5-work/exp0372/play/). RT on comes
# from the shared input.cfg. Writes only under ~/bc5-work/exp0372 and the one .desktop file; the shared launcher and
# input.cfg are read.
# usage: shortcut0372.sh   (on the box, with mkplay0372.pl beside it; no emulator started)
set -u
E=$HOME/bc5-work/exp0372; HERE=$(cd "$(dirname "$0")" && pwd)
SRC=$HOME/bc5-work/play-pkg.sh; OUT=$E/play-pkg-0372t.sh; BIN=$E/kyty_emulator
DESK=$(xdg-user-dir DESKTOP 2> /dev/null); DESK=${DESK:-$HOME/Pulpit}
WANT_LAUNCHER=${WANT_LAUNCHER:-55531ab6}; WANT_BIN=${WANT_BIN:-$(cat "$E/binary.md5" 2> /dev/null)}
m() { md5sum < "$1" | cut -c1-8; }
[ "$(m "$SRC")" = "$WANT_LAUNCHER" ] || { echo "$SRC is md5 $(m "$SRC"), not $WANT_LAUNCHER: stop"; exit 1; }
[ -x "$BIN" ] && [ -n "$WANT_BIN" ] && [ "$(m "$BIN")" = "$WANT_BIN" ] || { echo "$BIN is not the build0372.sh binary $WANT_BIN: stop"; exit 1; }
[ -d "$DESK" ] || { echo "no desktop directory $DESK"; exit 1; }
mkdir -p "$E/play" "$E/raw"
perl "$HERE/mkplay0372.pl" "$SRC" "$OUT" || exit 1
bash -n "$OUT" || { echo "$OUT does not parse"; exit 1; }
diff -u "$SRC" "$OUT" > "$E/raw/play-pkg-0372t.diff"
D="$DESK/BC5 emulator (test 0372).desktop"
cat > "$D" <<EOF
[Desktop Entry]
Type=Application
Version=1.0
Name=BC5 emulator (test 0372)
Comment=BC5 test 0372: the shared normal build plus the DualSense haptics replug fix (the pad's streams follow the controller's audio device, never the speakers); RT on; a log per start in ~/bc5-work/exp0372/play/
Exec=/usr/bin/distrobox enter ubuntu -- $OUT
Icon=applications-games
Terminal=false
Categories=Game;
StartupNotify=false
EOF
chmod +x "$D"
echo "shortcut $D"; cat "$D"
echo "launcher $OUT md5 $(m "$OUT") (diff: $(grep -c '^[-+][^-+]' "$E/raw/play-pkg-0372t.diff") lines); emulator $BIN md5 $(m "$BIN")"
echo "== the diff"; cat "$E/raw/play-pkg-0372t.diff"
