#!/usr/bin/env bash
# BC5 exp 0412 (README section 48): does BC5_GUARD_ZSKIP_SCAN end the canary hits and the hangs of the zero skip?
# Build g412w BESIDE the one in place (bin-w/kyty_emulator, N_EMU); the scripted route, 120 s after G, fuse 13,000,
# watchdog 220 MiB; arm lw7 is the word set that hung 3 of 7 on g412v (section 47).
#   s1 = lw7 + BC5_GUARD_ZSKIP_SCAN=1 (the whole run of a find); s2 = lw7 + BC5_GUARD_ZSKIP_SCAN=2 (an 8 MiB window);
#   s0 = lw7 on g412w without the scan (control); f1 = fast7 + scan mode 1.
# Before every arm: the lock empty and no emulator for 60 s in a row. Starts no arm after LAST (HH:MM).
# usage (on the box): LAST=19:20 bash ab0412x.sh > ab0412x.out 2>&1
set -u
export LC_ALL=C
W=$HOME/bc5-work; X=$W/exp0412; LOCK=$W/BOX-LOCK; R=$X/night/raw; EMU=$X/bin-w/kyty_emulator
LAST=${LAST:-23:59}
now() { date +%H:%M; }
free_box() { [ ! -s "$LOCK" ] && ! pgrep '^kyty_emulator' > /dev/null; }
arm() {   # <tag> <arm> [KEY=VALUE ...]
  local tag=$1 a=$2; shift 2
  [ -e "$R/$tag-start.txt" ] && { echo "$(date +%T) $tag already run: skipped"; return 0; }
  local ok=0
  while [ "$ok" -lt 6 ]; do if free_box; then ok=$((ok + 1)); else ok=0; fi; sleep 10; [[ "$(now)" > "$LAST" ]] && { echo "$(date +%T) $tag not started: past $LAST"; return 1; }; done
  echo "$(date +%T) $tag: rsync processes $(pgrep -c rsync), steamwebhelper $(pgrep -c steamwebhelper)"
  N_EMU=$EMU N_FUSE="13000 2048" N_WD_MIB=220 bash "$X/run0412n.sh" "$tag" "$a" 120 "$@" 2>&1 | tail -1
  local j; j=$(sed -n 's/^journal \([^ ]*\) .*/\1/p' "$R/$tag-journal.txt" 2> /dev/null)
  echo "$(date +%T) $tag ended: rsync processes $(pgrep -c rsync); canary hits $(grep -c 'canary hit' "$j" 2> /dev/null)"
  grep 'zero skip scan (exp 0412, tag zs412): t [0-9]* s: mode' "$j" 2> /dev/null | tail -1 | cut -c1-400
  grep 'zero skip: .*still skipped of' "$j" 2> /dev/null | tail -1 | cut -c1-240
}
arm c1s1 lw7 BC5_GUARD_ZSKIP_SCAN=1 || exit 0
arm c2s2 lw7 BC5_GUARD_ZSKIP_SCAN=2 || exit 0
arm c3s0 lw7 || exit 0
arm c4s1 lw7 BC5_GUARD_ZSKIP_SCAN=1 || exit 0
arm c5s2 lw7 BC5_GUARD_ZSKIP_SCAN=2 || exit 0
arm c6s0 lw7 || exit 0
arm c7s1 lw7 BC5_GUARD_ZSKIP_SCAN=1 || exit 0
arm c8s2 lw7 BC5_GUARD_ZSKIP_SCAN=2 || exit 0
arm c9f1 fast7 BC5_GUARD_ZSKIP_SCAN=1 || exit 0
arm d1s1 lw7 BC5_GUARD_ZSKIP_SCAN=1 || exit 0
arm d2s2 lw7 BC5_GUARD_ZSKIP_SCAN=2 || exit 0
arm d3s0 lw7 || exit 0
echo "$(date '+%F %T') series done"
