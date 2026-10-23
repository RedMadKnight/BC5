#!/usr/bin/env bash
# BC5 experiment 0242: the laptop side of the granted run (GRANTED by the top session, "after ~19:50 when the box is
# free with no lock"). It waits until it is NOT_BEFORE (default 19:50) and the box has had no BOX-LOCK and no
# process named kyty_emulator* for 120 s, checked every 10 s; it gives up at GIVE_UP (default 21:00).
# Then: claims ~/bc5-work/exp0242, copies the scripts, starts the kernel stream (kstream0242.sh, ends by itself),
# runs run0242.sh in this SSH session (attended) and scores it with ana0242.sh.
# usage: go0242.sh <tag> [secs]   (on the laptop, from the experiment directory)
set -u
TAG=${1:?tag}; SECS=${2:-600}
D="$(cd "$(dirname "$0")" && pwd)"
NOT_BEFORE=${NOT_BEFORE:-19:50}; GIVE_UP=${GIVE_UP:-21:00}
free_now() { ssh -o ConnectTimeout=20 bc250 '[ ! -s ~/bc5-work/BOX-LOCK ] && ! pgrep "^kyty_emulator" > /dev/null'; }
while :; do
  now=$(date +%H:%M)
  [[ "$now" > "$GIVE_UP" ]] && { echo "$(date +%T) gave up: the box was not free by $GIVE_UP"; exit 1; }
  if [[ ! "$now" < "$NOT_BEFORE" ]]; then
    ok=1
    for _ in $(seq 1 12); do free_now || { ok=0; break; }; sleep 10; done
    [ "$ok" = 1 ] && free_now && break
  fi
  sleep 20
done
echo "$(date +%T) box free for 120 s: starting"
ssh bc250 'pgrep "^kyty_emulator" > /dev/null && exit 3; [ -s ~/bc5-work/BOX-LOCK ] && exit 4
  if [ -e ~/bc5-work/exp0242 ] && [ ! -e ~/bc5-work/exp0242/CLAIMED ]; then exit 5; fi
  mkdir -p ~/bc5-work/exp0242/raw && [ -e ~/bc5-work/exp0242/CLAIMED ] || echo "exp 0242 claimed 2026-10-23 $(date +%H:%M) by the cutscene session: cutscene character-lag re-check on the defaults" > ~/bc5-work/exp0242/CLAIMED'
rc=$?; [ $rc = 0 ] || { echo "claim/guard failed (rc $rc: 3 emulator, 4 lock, 5 exp0242 is someone else's)"; exit 1; }
scp -q "$D/run0242.sh" "$D/ana0242.sh" "$D/long0242.py" bc250:bc5-work/exp0242/ || exit 1
ssh bc250 'chmod +x ~/bc5-work/exp0242/*.sh && python3 -I -m py_compile ~/bc5-work/exp0242/long0242.py && echo scripts ok' || exit 1
"$D/kstream0242.sh" &
KP=$!
sleep 3
ssh -o ServerAliveInterval=30 bc250 "~/bc5-work/exp0242/run0242.sh $TAG $SECS"
echo "$(date +%T) run finished; scoring"
ssh -o ServerAliveInterval=30 bc250 "~/bc5-work/exp0242/ana0242.sh $TAG"
wait "$KP"
echo "$(date +%T) done"
