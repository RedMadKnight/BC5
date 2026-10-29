#!/usr/bin/env bash
# BC5 experiment 0379, test shortcut (exp 0372's shortcut0372.sh): the maintainer's test shortcut
# "BC5 emulator (test 0379+0380)" on the desktop — play-pkg.sh (55531ab6) derived by mkplay0379t.pl into
# ~/bc5-work/exp0379t/play-pkg-0379t.sh (the private build, FORCE_START_AT_000 on, the zero skip SCAN/SKIP by itself, a log
# and a memory record per start in ~/bc5-work/exp0379t/play/). RT on comes from the shared input.cfg. Writes only under
# ~/bc5-work/exp0379t and the one .desktop file; the shared launcher and input.cfg are read.
# usage: shortcut0379t.sh   (on the box, with mkplay0379t.pl and play-sample0379t.sh beside it; no emulator started)
set -u
E=$HOME/bc5-work/exp0379t; HERE=$(cd "$(dirname "$0")" && pwd)
SRC=$HOME/bc5-work/play-pkg.sh; OUT=$E/play-pkg-0379t.sh; BIN=$E/kyty_emulator
DESK=$(xdg-user-dir DESKTOP 2> /dev/null); DESK=${DESK:-$HOME/Pulpit}
WANT_LAUNCHER=${WANT_LAUNCHER:-55531ab6}; WANT_BIN=${WANT_BIN:-$(cat "$E/binary.md5" 2> /dev/null)}
m() { md5sum < "$1" | cut -c1-8; }
[ "$(m "$SRC")" = "$WANT_LAUNCHER" ] || { echo "$SRC is md5 $(m "$SRC"), not $WANT_LAUNCHER: stop"; exit 1; }
[ -x "$BIN" ] && [ -n "$WANT_BIN" ] && [ "$(m "$BIN")" = "$WANT_BIN" ] || { echo "$BIN is not the build0379t.sh binary $WANT_BIN: stop"; exit 1; }
[ -d "$DESK" ] || { echo "no desktop directory $DESK"; exit 1; }
mkdir -p "$E/play" "$E/play-lists" "$E/raw"
cp "$HERE/play-sample0379t.sh" "$E/play-sample0379t.sh" || exit 1
perl "$HERE/mkplay0379t.pl" "$SRC" "$OUT" || exit 1
bash -n "$OUT" || { echo "$OUT does not parse"; exit 1; }
diff -u "$SRC" "$OUT" > "$E/raw/play-pkg-0379t.diff"
D="$DESK/BC5 emulator (test 0379+0380).desktop"
cat > "$D" <<EOF
[Desktop Entry]
Type=Application
Version=1.0
Name=BC5 emulator (test 0379+0380)
Comment=BC5 test 0379+0380: the shared normal build plus the zero skip of the render heaps (first start: SCAN, later starts: SKIP on the list from that play) and FORCE_START_AT_000 on indirect dispatches; RT on; a log and a memory record per start in ~/bc5-work/exp0379t/play/
Exec=/usr/bin/distrobox enter ubuntu -- $OUT
Icon=applications-games
Terminal=false
Categories=Game;
StartupNotify=false
EOF
chmod +x "$D"
echo "shortcut $D"; cat "$D"
echo "launcher $OUT md5 $(m "$OUT") (diff: $(grep -c '^[-+][^-+]' "$E/raw/play-pkg-0379t.diff") lines); sampler $(m "$E/play-sample0379t.sh"); emulator $BIN md5 $(m "$BIN")"
