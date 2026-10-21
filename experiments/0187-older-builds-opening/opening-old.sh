#!/usr/bin/env bash
# BC5 (experiment 0187): the second title's New Game opening by script (start screen, slot list,
# down twice to the empty slot 3, challenge level; as exp 0180's opening-run.sh) for SECS seconds
# (default 190: start screen, menu and the daytime forest; the night jungle from ~195 s is left out,
# where builds before 2026-10-18 17:08 met the GPU fault of F207). Any build: BIN=<binary> runs a
# kept one through emu-ts.sh (exp 0186) with KYTY_BC5_AJM_TRACE, timing its decoder jobs into the
# same index as KYTY_BC5_AJM_DUMP; without BIN the current build with KYTY_BC5_AJM_DUMP.
# The saves are put back to ~/bc5-work/save-backup-0180-0953 before and after (the run writes slot 3).
# Prints the clock voice's passes (F242), the flips per 10 s from the direct journal's frame profile,
# and whether the emulator ended by itself. usage: [BIN=<binary>] opening-old.sh <tag> [secs] ["<env>"]
TAG=$1; SECS=${2:-190}; ENVS=${3:-}
cd ~/bc5-work
BK=save-backup-0180-0953; SD=_SaveData/PPSA03671
restore() {
  cp -a "$BK/." "$SD/"
  for d in "$SD"/*/; do d=${d%/}; [ -e "$BK/$(basename "$d")" ] || rm -r -- "$d"; done
  diff -rq "$BK" "$SD" > /dev/null && echo "saves as in $BK" || echo "SAVES DIFFER from $BK"
}
pgrep -x kyty_emulator >/dev/null && { echo busy; exit 1; }
restore
D=~/bc5-work/dump-$TAG; rm -rf "$D"; mkdir -p "$D"
if [ -n "${BIN:-}" ]; then
  mkdir -p ~/bc5-work/old-$TAG; cp -p "$BIN" ~/bc5-work/old-$TAG/kyty_emulator
  RUNENV="BC5_EMU=$HOME/bc5-work/emu-ts.sh EMU_TS_BIN=$HOME/bc5-work/old-$TAG/kyty_emulator AJM_TS_OUT=$D/ajm-index.txt KYTY_BC5_AJM_TRACE=1"
else
  RUNENV="KYTY_BC5_AJM_DUMP=$D"
fi
printf 'wait 85000\npress cross\nwait 20000\npress down\nwait 800\npress down\nwait 800\npress cross\nwait 30000\npress cross\nwait 8000\npress cross\n' > op-$TAG.cmd
setsid nohup distrobox enter ubuntu -- env KYTY_BC5_INPUT_CMD=$HOME/bc5-work/op-$TAG.cmd $RUNENV $ENVS ~/bc5-work/play-pkg.sh < /dev/null > op-$TAG.out 2>&1 &
for _ in $(seq 1 60); do pgrep -x kyty_emulator >/dev/null && break; sleep 1; done
T0=$(date +%s); ENDED=""
while [ $(( $(date +%s) - T0 )) -lt "$SECS" ]; do
  pgrep -x kyty_emulator >/dev/null || { ENDED="ended by itself at $(( $(date +%s) - T0 )) s"; break; }
  sleep 1
done
J=$(ls -td ~/bc5-data/captures/play-*/gc | head -1)/direct.log
cp play-pkg-last.log op-$TAG.log
pkill -x kyty_emulator; sleep 4; pkill -9 -x kyty_emulator; sleep 3
restore
echo "$TAG ${ENDED:-stopped at $SECS s}; journal $J"
tail -n 3 op-$TAG.log | cut -c1-160
echo "clock voice passes (start-end s, speed):"
awk '{t=$1+0; i=$2; s=$5+0; if (NF<5) next; if ((i in prev) && s < prev[i]) {if (prev[i]-s0[i] == 479352) printf "%.0f-%.0f %.2fx\n", seg0[i], t, 479352/48000/(t-seg0[i]); seg0[i]=t; s0[i]=s} if (!(i in prev)) {seg0[i]=t; s0[i]=s} prev[i]=s}' "$D/ajm-index.txt" | tr '\n' ' '; echo
echo "flips per 10 s (direct journal frame profile):"
grep -a "^frame profile: t " "$J" | awk '{t=$4+0; w=int(t/10); n[w]++} END {for (k in n) printf "%d:%d\n", k*10, n[k]}' | sort -n | tr '\n' ' '; echo
