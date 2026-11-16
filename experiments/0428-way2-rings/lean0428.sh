#!/usr/bin/env bash
# BC5 exp 0428: the freeze re-run on the shared lean build, the second title 300 s, the route by time (smoke0425's: a cross at
# 90, 100, 108 s, exp 0379's walk from 170 s), RT on, JobArenaFix as the shared input.cfg has it (start0428l.sh). No fuse,
# no watchdog. usage (on the box, detached, in ~/bc5-work/exp0413/n): bash ~/bc5-work/exp0428/lean0428.sh <tag>
set -u
ulimit -c 0
export LC_ALL=C
W=$HOME/bc5-work; N=$W/exp0413/n; T=${1:?a tag}
LB=$W/kytyplus-build-lean/src/kyty_emulator; ML=$(md5sum < "$LB" | cut -d' ' -f1)
cd "$N" || exit 1
CMD=$N/cmd-$T.txt
{ printf 'wait 90000\npress cross\nwait 10000\npress cross\nwait 8000\npress cross\nwait 62000\n'
  c=0; while [ $c -lt 8 ]; do s=255; [ $(((c / 4) % 2)) = 1 ] && s=0; printf 'stick l 128 0 15000\nstick r %d 128 1200\nwait 300\n' "$s"; c=$((c + 1)); done
  printf 'stick l 128 128\nstick r 128 128\n'; } > "$CMD"
echo "lean0428 $(date +%T): lean ${ML:0:8}, tag $T"
P_BIN=$LB P_WANT=$ML P_WORDS=$N/words0413nz.txt bash "$W/exp0428/start0428l.sh" "$T" lean 300 KYTY_BC5_INPUT_CMD="$CMD" | grep "^$T "
echo "lean0428 $(date +%T): ended; JobArenaFix in its config: $(grep -i '^JobArenaFix' "$N/input-$T.cfg" 2> /dev/null || echo 'no line (the default)')"
