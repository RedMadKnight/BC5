#!/usr/bin/env bash
# exp 0413: one ASTRO BOT start of the private build with the given audit groups' defaults set to 0. Prints PASS or the end line.
# usage: bisect.sh <tag> <group>...
S=C:/Users/kjani/AppData/Local/Temp/claude/7e70d624f1bff3f5/43cd6eac-dc2c-49c1-b603-e5283be4d569/scratchpad/int
TAG=$1; shift; ASECS=${ASECS:-60}
OFF=$(awk -v gs=" $* " 'index(gs, " " $1 " ") {printf "%s=0 ", $2}' "$S/sw.txt")
timeout 200 ssh -n -o ConnectTimeout=10 bc250 "pgrep '^kyty_emulator' && { echo EMU; exit 1; }; [ -s ~/bc5-work/BOX-LOCK ] && { echo LOCKED; exit 1; }; cd ~/bc5-work/exp0413/n && P_BIN=\$HOME/bc5-work/exp0413/p/build-normal/src/kyty_emulator P_WANT=a76f86abffed99a3423ce5c9a394d5f4 bash ./start0413.sh $TAG astro $ASECS $OFF 2>&1 | tail -1"
