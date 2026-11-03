#!/usr/bin/env bash
# BC5 experiment 0401: the maintainer's test shortcut "BC5 emulator (test 0401)" on his desktop (his words, 2026-11-03:
# "przygotuj skrót do kolejnego testu z przełącznikami bez ARGS_WB=all"). It runs the private launcher play-pkg-0401.sh
# (c6b2d7fd) with the private build 174e768e and both of this experiment's switches on, ARGS_WB set off explicitly. No
# menu: the launcher starts game.pkg. RT on comes from the shared settings, which this script only prints.
# Writes only the one .desktop file (made as a temporary file in the series' directory, then moved). Nothing else is
# written, except that mode cpacb also removes the cp shortcut it replaces; the build, the launcher and the settings are only read.
# Mode cp (the top session's GO, 2026-11-03, after "Nie da się grać" on both): "BC5 emulator (test 0401 CP)", CP_COHER_START_DELAY alone.
# Mode cpacb (the top session's GO, 2026-11-03 09:10): "BC5 emulator (test 0401 CP+acb)", series b's build (exp0401b) with
# CP_COHER_START_DELAY and the acb CS prefix on; it replaces the cp shortcut.
# usage: shortcut0401.sh [both|cp|cpacb]   (on the box; both is the default)
set -u
DESK=$(xdg-user-dir DESKTOP 2> /dev/null); DESK=${DESK:-$HOME/Pulpit}
OLD=""
case ${1:-both} in
both)  S=""; WANT_BIN=174e768ec3a68c34be879ad57067819c; WANT_LAUNCHER=c6b2d7fdba882a1817224c9bf6d07ff2
       NAME="BC5 emulator (test 0401)"; WHAT="CP_COHER_START_DELAY 0x20 and SPI_SHADER_REQ_CTRL_PS 0x7 (Mesa's preamble values)"
       ENVS="BC5_DIRECT_CP_COHER_START_DELAY=1 BC5_DIRECT_SPI_REQ_CTRL_PS=1 BC5_DIRECT_ARGS_WB=0" ;;
cp)    S=""; WANT_BIN=174e768ec3a68c34be879ad57067819c; WANT_LAUNCHER=c6b2d7fdba882a1817224c9bf6d07ff2
       NAME="BC5 emulator (test 0401 CP)"; WHAT="CP_COHER_START_DELAY 0x20 only (Mesa's preamble value)"
       ENVS="BC5_DIRECT_CP_COHER_START_DELAY=1 BC5_DIRECT_SPI_REQ_CTRL_PS=0 BC5_DIRECT_ARGS_WB=0" ;;
cpacb) S=b; WANT_BIN=5b05ce9be5e4a4bf6352e270d28358d7; WANT_LAUNCHER=01312b5b995d632177745273a5adcd93
       NAME="BC5 emulator (test 0401 CP+acb)"; WHAT="CP_COHER_START_DELAY 0x20 and the acb CS prefix"
       ENVS="BC5_DIRECT_CP_COHER_START_DELAY=1 BC5_DIRECT_ACB_CS_PREFIX=1 BC5_DIRECT_SPI_REQ_CTRL_PS=0 BC5_DIRECT_ARGS_WB=0"
       OLD="BC5 emulator (test 0401 CP)" ;;
*)     echo "usage: shortcut0401.sh [both|cp|cpacb]"; exit 1 ;;
esac
E=$HOME/bc5-work/exp0401$S; BIN=$E/bin/kyty_emulator; L=$E/play-pkg-0401.sh
m() { md5sum < "$1" 2> /dev/null | cut -d' ' -f1; }
pgrep '^kyty_emulator' > /dev/null && { echo "an emulator runs: stop"; exit 1; }
[ "$(m "$BIN")" = "$WANT_BIN" ] || { echo "$BIN is not $WANT_BIN: stop"; exit 1; }
[ "$(m "$L")" = "$WANT_LAUNCHER" ] || { echo "$L is not $WANT_LAUNCHER: stop"; exit 1; }
[ -d "$DESK" ] && [ ! -L "$DESK" ] || { echo "no desktop directory $DESK: stop"; exit 1; }
D="$DESK/$NAME.desktop"
[ ! -e "$D" ] || grep -qxF "Name=$NAME" "$D" || { echo "$D exists and is not ours: stop"; exit 1; }
O=""; [ -z "$OLD" ] || O="$DESK/$OLD.desktop"
[ -z "$O" ] || [ ! -e "$O" ] || grep -qxF "Name=$OLD" "$O" || { echo "$O exists and is not ours: stop"; exit 1; }
t=$E/shortcut-0401.tmp.$$.desktop   # desktop-file-validate wants the extension; the same file system as the desktop
cat > "$t" << EOF
[Desktop Entry]
Type=Application
Version=1.0
Name=$NAME
Comment=BC5 test 0401: private build $WANT_BIN with $WHAT, without ARGS_WB; starts the game directly; log ~/bc5-work/exp0401$S/play-last.log
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
if [ -n "$O" ] && [ -e "$O" ]; then rm -f "$O" && echo "removed $O, which this one replaces"; fi
echo "RT in the shared settings: $(grep -h 'RayTracing.PPSA03671' "$HOME"/bc5-work/input*.cfg 2> /dev/null | sort -u | tr '\n' ' ')"
