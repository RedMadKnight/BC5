#!/usr/bin/env bash
# BC5 experiment 0401: the maintainer's test shortcut "BC5 emulator (test 0401)" on his desktop (his words, 2026-11-03:
# "przygotuj skrót do kolejnego testu z przełącznikami bez ARGS_WB=all"). It runs the private launcher play-pkg-0401.sh
# (c6b2d7fd) with the private build 174e768e and both of this experiment's switches on, ARGS_WB set off explicitly. No
# menu: the launcher starts game.pkg. RT on comes from the shared settings, which this script only prints.
# Writes only the one .desktop file. Nothing else is written; the build, the launcher and the settings are only read.
# usage: shortcut0401.sh   (on the box)
set -u
E=$HOME/bc5-work/exp0401; BIN=$E/bin/kyty_emulator; L=$E/play-pkg-0401.sh
DESK=$(xdg-user-dir DESKTOP 2> /dev/null); DESK=${DESK:-$HOME/Pulpit}
WANT_BIN=174e768ec3a68c34be879ad57067819c; WANT_LAUNCHER=c6b2d7fdba882a1817224c9bf6d07ff2
ENVS="BC5_DIRECT_CP_COHER_START_DELAY=1 BC5_DIRECT_SPI_REQ_CTRL_PS=1 BC5_DIRECT_ARGS_WB=0"
m() { md5sum < "$1" 2> /dev/null | cut -d' ' -f1; }
pgrep '^kyty_emulator' > /dev/null && { echo "an emulator runs: stop"; exit 1; }
[ "$(m "$BIN")" = "$WANT_BIN" ] || { echo "$BIN is not $WANT_BIN: stop"; exit 1; }
[ "$(m "$L")" = "$WANT_LAUNCHER" ] || { echo "$L is not $WANT_LAUNCHER: stop"; exit 1; }
[ -d "$DESK" ] && [ ! -L "$DESK" ] || { echo "no desktop directory $DESK: stop"; exit 1; }
D="$DESK/BC5 emulator (test 0401).desktop"
[ ! -e "$D" ] || grep -qF 'Name=BC5 emulator (test 0401)' "$D" || { echo "$D exists and is not ours: stop"; exit 1; }
t=$D.tmp.$$
cat > "$t" << EOF
[Desktop Entry]
Type=Application
Version=1.0
Name=BC5 emulator (test 0401)
Comment=BC5 test 0401: private build $WANT_BIN with CP_COHER_START_DELAY 0x20 and SPI_SHADER_REQ_CTRL_PS 0x7 (Mesa's preamble values), without ARGS_WB; starts the game directly; log ~/bc5-work/exp0401/play-last.log
Exec=/usr/bin/distrobox enter ubuntu -- /usr/bin/env $ENVS $L
Icon=applications-games
Terminal=false
Categories=Game;
StartupNotify=false
EOF
[ "$(grep -c "^Exec=/usr/bin/distrobox enter ubuntu -- /usr/bin/env $ENVS $L$" "$t")" = 1 ] || { rm -f "$t"; echo "the Exec line is not as meant: stop"; exit 1; }
if command -v desktop-file-validate > /dev/null; then desktop-file-validate "$t" || { rm -f "$t"; echo "the .desktop file is not valid: stop"; exit 1; }; fi
chmod +x "$t" && mv -fT "$t" "$D" || { rm -f "$t"; echo "cannot write $D"; exit 1; }
echo "shortcut $D, md5 $(m "$D")"; grep -E '^(Name|Exec)=' "$D"
echo "RT in the shared settings: $(grep -h 'RayTracing.PPSA03671' "$HOME"/bc5-work/input*.cfg 2> /dev/null | sort -u | tr '\n' ' ')"
