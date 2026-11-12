#!/usr/bin/env bash
# BC5 exp 0412 (README section 40): the proof runs of BC5_GUARD_ZSKIP_POLL_SUBMIT (build g412u): arm fast5 (fast2 + the zero
# skip + the poll before every submission) on the scripted load, nine times, with the zero skip's catcher on; RT on;
# measuring watchdog 220 MiB; the fuse as always. The old zero skip timed out the gfx ring in 3 of 9 runs.
# THE CHAIN STOPS after a run with a kernel line. A file night/STOP ends the chain between runs.
# usage (on the box, under setsid nohup): ab0412u.sh [first] [last]
set -u
X=$HOME/bc5-work/exp0412; N=$X/night
calm() { for _ in $(seq 1 60); do pgrep '^kyty_emulator' > /dev/null || [ -s "$HOME/bc5-work/BOX-LOCK" ] || return 0; sleep 5; done; return 1; }
one() { # tag
  [ -e "$N/STOP" ] && { echo "$(date +%T) chain: STOP before $1"; exit 0; }
  calm || { echo "$(date +%T) chain: the box is not calm before $1"; exit 1; }
  pgrep steamwebhelper > /dev/null && { echo "$(date +%T) chain: Steam runs: stopped before $1"; exit 1; }
  sleep 10
  N_WD_MIB=220 bash "$X/run0412n.sh" "$1" fast5 60 BC5_GUARD_ZSKIP_STAT=1 > "$N/run-$1.log" 2>&1
  J=$(ls -td "$HOME"/bc5-data/captures/play-*/gc 2> /dev/null | head -1)/direct.log
  grep -a 'zero skip\|zp412\|zc412\|^guard: t\|^guard heaps\|learned: fault\|FAILED\|TIMEOUT\|timed out' "$J" | cut -c1-500 > "$N/raw/$1-zpoll.txt"
  echo "$(date +%T) chain: $1: $(cut -c1-190 "$N/raw/$1-summary.txt" 2> /dev/null)"
  echo "$(date +%T) chain: $1: $(grep -a 'zp412' "$N/raw/$1-zpoll.txt" | grep -a 'looks' | tail -1 | cut -c40-260)"
  if [ -s "$N/raw/$1-dmesg-after.txt" ]; then echo "$(date +%T) chain: kernel lines after $1: stopped"; exit 0; fi
}
for i in $(seq "${1:-1}" "${2:-9}"); do one "v${i}zp"; done
echo "$(date +%T) chain: end"
