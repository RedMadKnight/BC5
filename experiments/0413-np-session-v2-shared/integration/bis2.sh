#!/usr/bin/env bash
# exp 0413: one ASTRO BOT start of the skip-file diagnostic build (126fd308). The audit groups given are skipped in the
# table, and each skipped row is replaced by a dummy row (+BC5_X_<name>=1), so the number of setenv calls and the
# starting environment are the same in every run. usage: bis2.sh <tag> [group ...]   (ALL = every group)
S=C:/Users/kjani/AppData/Local/Temp/claude/7e70d624f1bff3f5/43cd6eac-dc2c-49c1-b603-e5283be4d569/scratchpad/int
TAG=$1; shift
if [ "${1:-}" = ALL ]; then NAMES=$(awk '{print $2}' "$S/sw36.txt"); else NAMES=$(awk -v gs=" $* " 'index(gs, " " $1 " ") {print $2}' "$S/sw36.txt"); fi
{ for n in $NAMES; do echo "$n"; done; for n in $NAMES; do echo "+BC5_X_$n=1"; done; } | timeout 200 ssh -o ConnectTimeout=10 bc250 "pgrep '^kyty_emulator' >/dev/null && { cat > /dev/null; echo EMU; exit 1; }; [ -s ~/bc5-work/BOX-LOCK ] && { cat > /dev/null; echo LOCKED; exit 1; }; cd ~/bc5-work/exp0413/n && cat > skip.txt && P_BIN=\$HOME/bc5-work/exp0413/p/build-normal/src/kyty_emulator P_WANT=126fd308dfeb920823cde80ed3e7e805 bash ./start0413.sh $TAG astro 60 2>&1 | tail -1 | cut -c1-60; cp skip.txt raw/$TAG-skip.txt"
