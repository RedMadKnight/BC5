#!/usr/bin/env bash
# BC5 experiment 0401: the maintainer's test shortcut "BC5 emulator (test 0401)" on his desktop (his words, 2026-11-03:
# "przygotuj skrót do kolejnego testu z przełącznikami bez ARGS_WB=all"). It runs the private launcher play-pkg-0401.sh
# (c6b2d7fd) with the private build 174e768e and both of this experiment's switches on, ARGS_WB set off explicitly. No
# menu: the launcher starts game.pkg. RT on comes from the shared settings, which this script only prints.
# Writes only the one .desktop file (made as a temporary file in the series' directory, then moved). Nothing else is
# written, except that mode cpacb also removes the cp shortcut it replaces; the build, the launcher and the settings are only read.
# Mode cp (the top session's GO, 2026-11-03, after "Nie da się grać" on both): "BC5 emulator (test 0401 CP)", CP_COHER_START_DELAY alone.
# Mode cpacb (the top session's GO, 2026-11-03 09:10 and 09:24): "BC5 emulator (test 0401 CP+acb)", series c's build
# (exp0401c) with CP_COHER_START_DELAY, the acb CS prefix and exp 0381's acb state restore on; it replaces the cp shortcut.
# Mode cpacb-b puts the same shortcut back on series b's build (exp0401b, no restore): the rollback.
# Since the top session's GO of 2026-11-03 13:52 (his "Tak, przebuduj"), mode cpacb runs series d (exp0401d): series c's
# three switches on exp 0379's zero skip, with the skip on as exp 0388's play0389z.sh on sets it (its list, pinned). Mode
# cpacb-c puts the same shortcut back on series c's 505b3ae3, without the skip: the rollback.
# Since the top session's GO of 2026-11-03 16:4x (his "Buduj"), mode cpacb runs series e (exp0401e): series c's binary plus
# the table catcher, the NpCppWebApi SessionManager V2 exports and the param.json memory sizing, all three on, with the acb CS
# prefix off (the top's hand edit of 2026-11-03, after the prefix-on crashes). Mode cpacb-c0 is that hand edit (series c's
# 505b3ae3, prefix off): the rollback. Mode cpacb-d is series d as mode cpacb was until then.
# Since the top session's addition of 2026-11-03 17:0x, mode cpacb runs series e2 (exp0401e2): series e plus exp 0403's
# BC5_DIRECT_ACB_INHERIT, set to journal (the catcher; wave and skip are built, not set). Mode cpacb-e is series e as it was.
# usage: shortcut0401.sh [both|cp|cpacb|cpacb-e|cpacb-c0|cpacb-c|cpacb-d|cpacb-b]   (on the box; both is the default)
set -u
DESK=$(xdg-user-dir DESKTOP 2> /dev/null); DESK=${DESK:-$HOME/Pulpit}
OLD=""; ZL=""; WANT_LIST=""
case ${1:-both} in
both)  S=""; WANT_BIN=174e768ec3a68c34be879ad57067819c; WANT_LAUNCHER=c6b2d7fdba882a1817224c9bf6d07ff2
       NAME="BC5 emulator (test 0401)"; WHAT="CP_COHER_START_DELAY 0x20 and SPI_SHADER_REQ_CTRL_PS 0x7 (Mesa's preamble values)"
       ENVS="BC5_DIRECT_CP_COHER_START_DELAY=1 BC5_DIRECT_SPI_REQ_CTRL_PS=1 BC5_DIRECT_ARGS_WB=0" ;;
cp)    S=""; WANT_BIN=174e768ec3a68c34be879ad57067819c; WANT_LAUNCHER=c6b2d7fdba882a1817224c9bf6d07ff2
       NAME="BC5 emulator (test 0401 CP)"; WHAT="CP_COHER_START_DELAY 0x20 only (Mesa's preamble value)"
       ENVS="BC5_DIRECT_CP_COHER_START_DELAY=1 BC5_DIRECT_SPI_REQ_CTRL_PS=0 BC5_DIRECT_ARGS_WB=0" ;;
cpacb) S=e2; WANT_BIN=35ff82ebc8530e4bcc4ea66ccf43accf; WANT_LAUNCHER=fbac41eef200b36c440ddc1ef5322783
       NAME="BC5 emulator (test 0401 CP+acb)"; WHAT="CP_COHER_START_DELAY 0x20, exp 0381's acb state restore, exp 0403's ACB_INHERIT journal (acb CS prefix off), the table catcher, NpCppWebApi SessionManager V2 and the param.json memory sizing"
       ENVS="BC5_DIRECT_CP_COHER_START_DELAY=1 BC5_DIRECT_ACB_CS_PREFIX=0 BC5_DIRECT_ACB_INHERIT=journal BC5_DIRECT_ACB_STATE_RESTORE=1 BC5_DIRECT_SPI_REQ_CTRL_PS=0 BC5_DIRECT_ARGS_WB=0 BC5_DIRECT_TABLE_CATCHER=1 KYTY_BC5_NP_SESSION_V2=1 KYTY_BC5_MEMORY_FROM_PARAM=1"
       OLD="BC5 emulator (test 0401 CP)" ;;
cpacb-e) S=e; WANT_BIN=852d9b089558d4c845ba7005af888b96; WANT_LAUNCHER=b9774734b4ae9411afb768197d3f59c8   # series e as built first
       NAME="BC5 emulator (test 0401 CP+acb)"; WHAT="CP_COHER_START_DELAY 0x20, exp 0381's acb state restore (acb CS prefix off), the table catcher, NpCppWebApi SessionManager V2 and the param.json memory sizing"
       ENVS="BC5_DIRECT_CP_COHER_START_DELAY=1 BC5_DIRECT_ACB_CS_PREFIX=0 BC5_DIRECT_ACB_STATE_RESTORE=1 BC5_DIRECT_SPI_REQ_CTRL_PS=0 BC5_DIRECT_ARGS_WB=0 BC5_DIRECT_TABLE_CATCHER=1 KYTY_BC5_NP_SESSION_V2=1 KYTY_BC5_MEMORY_FROM_PARAM=1"
       OLD="BC5 emulator (test 0401 CP)" ;;
cpacb-c0) S=c; WANT_BIN=505b3ae35ac4510494e03e50fec6a43e; WANT_LAUNCHER=d17996d379eef31aab995fa9aa55600d   # the rollback: the top's hand edit
       NAME="BC5 emulator (test 0401 CP+acb)"; WHAT="CP_COHER_START_DELAY 0x20 and exp 0381's acb state restore (acb CS prefix off)"
       ENVS="BC5_DIRECT_CP_COHER_START_DELAY=1 BC5_DIRECT_ACB_CS_PREFIX=0 BC5_DIRECT_ACB_STATE_RESTORE=1 BC5_DIRECT_SPI_REQ_CTRL_PS=0 BC5_DIRECT_ARGS_WB=0"
       OLD="BC5 emulator (test 0401 CP)" ;;
cpacb-d) S=d; WANT_BIN=1545c4dee54528fc0480faf1b62df45e; WANT_LAUNCHER=7e4df66b96b3983b85733606895d2a01
       NAME="BC5 emulator (test 0401 CP+acb)"; WHAT="CP_COHER_START_DELAY 0x20, the acb CS prefix, exp 0381's acb state restore and exp 0379's zero skip"
       ZL=$HOME/bc5-work/exp0388/m/zero-list-moving.txt; WANT_LIST=843f9fbcde4d9c2d324e8cba78cdbae5   # play0389z.sh on's list
       ENVS="BC5_DIRECT_CP_COHER_START_DELAY=1 BC5_DIRECT_ACB_CS_PREFIX=1 BC5_DIRECT_ACB_STATE_RESTORE=1 BC5_DIRECT_SPI_REQ_CTRL_PS=0 BC5_DIRECT_ARGS_WB=0 BC5_DIRECT_ZERO_SKIP=$ZL"
       OLD="BC5 emulator (test 0401 CP)" ;;
cpacb-c) S=c; WANT_BIN=505b3ae35ac4510494e03e50fec6a43e; WANT_LAUNCHER=d17996d379eef31aab995fa9aa55600d   # the rollback: series c, no skip
       NAME="BC5 emulator (test 0401 CP+acb)"; WHAT="CP_COHER_START_DELAY 0x20, the acb CS prefix and exp 0381's acb state restore"
       ENVS="BC5_DIRECT_CP_COHER_START_DELAY=1 BC5_DIRECT_ACB_CS_PREFIX=1 BC5_DIRECT_ACB_STATE_RESTORE=1 BC5_DIRECT_SPI_REQ_CTRL_PS=0 BC5_DIRECT_ARGS_WB=0"
       OLD="BC5 emulator (test 0401 CP)" ;;
cpacb-b) S=b; WANT_BIN=5b05ce9be5e4a4bf6352e270d28358d7; WANT_LAUNCHER=01312b5b995d632177745273a5adcd93   # the rollback: series b, no restore
       NAME="BC5 emulator (test 0401 CP+acb)"; WHAT="CP_COHER_START_DELAY 0x20 and the acb CS prefix"
       ENVS="BC5_DIRECT_CP_COHER_START_DELAY=1 BC5_DIRECT_ACB_CS_PREFIX=1 BC5_DIRECT_SPI_REQ_CTRL_PS=0 BC5_DIRECT_ARGS_WB=0"
       OLD="BC5 emulator (test 0401 CP)" ;;
*)     echo "usage: shortcut0401.sh [both|cp|cpacb|cpacb-e|cpacb-c0|cpacb-c|cpacb-d|cpacb-b]"; exit 1 ;;
esac
E=$HOME/bc5-work/exp0401$S; BIN=$E/bin/kyty_emulator; L=$E/play-pkg-0401.sh
m() { md5sum < "$1" 2> /dev/null | cut -d' ' -f1; }
pgrep '^kyty_emulator' > /dev/null && { echo "an emulator runs: stop"; exit 1; }
[ "$(m "$BIN")" = "$WANT_BIN" ] || { echo "$BIN is not $WANT_BIN: stop"; exit 1; }
[ "$(m "$L")" = "$WANT_LAUNCHER" ] || { echo "$L is not $WANT_LAUNCHER: stop"; exit 1; }
[ -z "$ZL" ] || [ "$(m "$ZL")" = "$WANT_LIST" ] || { echo "the zero list $ZL is not $WANT_LIST: stop"; exit 1; }
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
