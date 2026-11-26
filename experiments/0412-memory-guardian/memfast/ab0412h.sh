#!/usr/bin/env bash
# BC5 exp 0412: the runs for build g412h (KYTY_BC5_PHYSMAP_SORTED), one after another on the box under setsid nohup.
# l1verify: the sorted table in verify mode (the old search runs beside the new one in Unmap), with the whole-box
# snapshot at 60, 130 and 165 s. Then ABBA, l2off l3on l4on l5off: the scripted load of the copy of his save, ledger arm,
# KYTY_BC5_RANGES_FAST=1 in all four, the sorted table on in two; the stack sampler on game-main and Render_Thread.
# Every run has the sampler, the fuse and the watchdog (run0412n.sh). A file night/STOP ends the chain between runs.
set -u
X=$HOME/bc5-work/exp0412; N=$X/night
calm() { for _ in $(seq 1 36); do pgrep '^kyty_emulator' > /dev/null || pgrep -f prof0412.sh > /dev/null || [ -s "$HOME/bc5-work/BOX-LOCK" ] || return 0; sleep 5; done; return 1; }
one() { # tag, then the extra words
  local tag=$1; shift
  [ -e "$N/STOP" ] && { echo "$(date +%T) chain: STOP before $tag"; exit 0; }
  calm || { echo "$(date +%T) chain: the box is not calm before $tag"; exit 1; }
  sleep 10
  (setsid nohup distrobox enter ubuntu -- bash "$X/prof0412.sh" "$N/raw/$tag-prof-game.txt" 0 25 200 game-main > /dev/null 2>&1 < /dev/null &)
  (setsid nohup distrobox enter ubuntu -- bash "$X/prof0412.sh" "$N/raw/$tag-prof-render.txt" 0 25 200 Render_Thread > /dev/null 2>&1 < /dev/null &)
  bash "$X/run0412n.sh" "$tag" ledger 60 KYTY_BC5_RANGES_FAST=1 "$@" > "$N/run-$tag.log" 2>&1
}
[ -e "$N/STOP" ] && { echo "$(date +%T) chain: STOP file"; exit 0; }
calm || { echo "$(date +%T) chain: the box is not calm"; exit 1; }
(setsid nohup bash "$X/snap0412.sh" "$N/raw/l1verify-snap.txt" 60 130 165 > /dev/null 2>&1 < /dev/null &)
bash "$X/run0412n.sh" l1verify ledger 60 KYTY_BC5_RANGES_FAST=1 KYTY_BC5_PHYSMAP_SORTED=verify > "$N/run-l1verify.log" 2>&1
one l2off
one l3on KYTY_BC5_PHYSMAP_SORTED=1
one l4on KYTY_BC5_PHYSMAP_SORTED=1
one l5off
echo "$(date +%T) chain: end"
