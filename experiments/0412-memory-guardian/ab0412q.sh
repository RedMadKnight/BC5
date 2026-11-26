#!/usr/bin/env bash
# BC5 exp 0412 (README section 28): ABBA of arm fast2 against arm fast3 (the return-aware orphan release) on the
# scripted load, build g412o, RT on, 60 s of walking after the load. Measuring runs: the watchdog at 220 MiB
# (N_WD_MIB=220, the top session's decision of 2026-11-11), the fuse as always. Both arms run with
# BC5_GUARD_LOCK_STAT=1 (a line per hold of the device mutex of 30 ms or more), which changes no behaviour.
# After each run the journal's lock, release and return-aware lines go to raw/<tag>-holds.txt.
# A file night/STOP ends the chain between runs. usage (on the box, under setsid nohup): ab0412q.sh
set -u
X=$HOME/bc5-work/exp0412; N=$X/night
calm() { for _ in $(seq 1 60); do pgrep '^kyty_emulator' > /dev/null || [ -s "$HOME/bc5-work/BOX-LOCK" ] || return 0; sleep 5; done; return 1; }
one() { # tag arm
  [ -e "$N/STOP" ] && { echo "$(date +%T) chain: STOP before $1"; exit 0; }
  calm || { echo "$(date +%T) chain: the box is not calm before $1"; exit 1; }
  sleep 10
  N_WD_MIB=220 bash "$X/run0412n.sh" "$1" "$2" 60 BC5_GUARD_LOCK_STAT=1 > "$N/run-$1.log" 2>&1
  J=$(ls -td "$HOME"/bc5-data/captures/play-*/gc 2> /dev/null | head -1)/direct.log
  grep -a 'lock hold (exp 0412\|lock stat (exp 0412\|^lazy release (exp 0401 e7)\|^return-aware release\|^guard split\|^guard forget' "$J" | cut -c1-600 > "$N/raw/$1-holds.txt"
  echo "$(date +%T) chain: $1 ($2): $(cut -c1-150 "$N/raw/$1-summary.txt" 2> /dev/null)"
}
one a1f2 fast2
one a2f3 fast3
one a3f3 fast3
one a4f2 fast2
echo "$(date +%T) chain: end"
