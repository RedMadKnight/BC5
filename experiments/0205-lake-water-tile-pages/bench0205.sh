#!/usr/bin/env bash
# BC5 experiment 0205 (from exp 0201, 0197): one run of the exp 0194 bench (the maintainer's lake save, private copy) to the frozen
# Photo Mode view of the near lake, then screenshots and the patch share (patch0197.py). The switches in ENVX
# go over the launcher's defaults; the diagnostic binary of exp 0194 and its keyboard-off input config are used.
# Steps (exp 0194 README): title cross; slot list down, down (shot "slot"), cross; Continue Game: down, cross;
# about 60 s later at the Parry prompt (shot "game"): options, down x4, cross, triangle; then the camera moves
# (shots "ts00".."ts12", one every ~5 s for 60 s: the patches grow in the frozen view). The run stops after SECS.
# The run holds ~/bc5-work/BOX-LOCK (the top session's rule) until its emulator exits; SERIES/STEP set the shots.
# PAGES=1 adds pg0205.py's page sampler (r-<tag>/pages.txt); PAGES_RANGES="<hex base>:<hex size> ..." overrides its ranges.
# usage: ENVX="<switches>" [SERIES=13 STEP=5 PAGES=0] bench0205.sh <tag> [secs]
TAG=$1; SECS=${2:-280}
W=~/bc5-work/exp0194
cd ~/bc5-work
pgrep -x kyty_emulator >/dev/null && { echo busy; exit 1; }
# run directories of exps 0194-0205 share exp0194/r-<tag>: a reused tag mixes runs (S2 at 18:16 reused exp 0194's
# r-S2, and its stale input.cmd.done sent the slot keys early)
[ -e "$W/r-$TAG" ] && { echo "$W/r-$TAG exists: pick an unused tag"; exit 1; }
[ -s ~/bc5-work/BOX-LOCK ] && { echo "box locked: $(cat ~/bc5-work/BOX-LOCK)"; exit 1; }
SERIES=${SERIES:-13}; STEP=${STEP:-5}  # shots in the frozen view and seconds between them
echo "water session exp 0205 | bench $TAG | start $(date +%H:%M) | until ~$(date -d "+$(( (SECS + 120) / 60 )) min" +%H:%M)" > ~/bc5-work/BOX-LOCK
ENVX="BC5_0194_INPUT_CONFIG=$W/input-0194.cfg BC5_EMU=$W/kyty_emulator ${ENVX:-}"
( ROUTE=${ROUTE:-interactive.cmd} ENVX="$ENVX" SHOTS="50" setsid nohup timeout $((SECS + 120)) $W/run-0194b.sh "$TAG" "$SECS" > ~/bc5-work/exp0205/$TAG.out 2>&1 & )
R=$W/r-$TAG
for _ in $(seq 1 60); do pgrep -x kyty_emulator >/dev/null && break; sleep 1; done
EPID=$(pgrep -n -x kyty_emulator)
( while kill -0 "$EPID" 2>/dev/null; do sleep 5; done; grep -q "^water session exp 0205 | bench $TAG " ~/bc5-work/BOX-LOCK 2>/dev/null && rm -f ~/bc5-work/BOX-LOCK ) < /dev/null > /dev/null 2>&1 &
for _ in $(seq 1 60); do [ -f "$R/input.cmd" ] && break; sleep 1; done
# PAGES=1: the read-only page sampler of the water's streamed textures (pg0205.py) for the whole run, every 5 s
[ "${PAGES:-0}" = 1 ] && PG0205_PID=$EPID setsid nohup nice -n 10 python3 -I ~/bc5-work/exp0205/pg0205.py "$R/pages.txt" 5 6 ${PAGES_RANGES:-} < /dev/null > /dev/null 2>&1 &
gone() { # the run's emulator died (B1 at 16 s): stop here, so no step or shot runs while another session has the box
  kill -0 "$EPID" 2>/dev/null && return 1
  echo "== $TAG: the emulator ended early, at $(date +%T); bench stopped"; exit 2
}
step() { # append lines, wait until all are done
  gone
  local n; n=$(cat "$R/input.cmd.done" 2>/dev/null || echo 0)
  printf "$1" >> "$R/input.cmd"
  local add; add=$(printf "$1" | grep -c "")
  for _ in $(seq 1 120); do [ "$(cat "$R/input.cmd.done" 2>/dev/null || echo 0)" -ge $((n + add)) ] && return 0; gone; sleep 0.5; done
  echo "step timed out: $1"; return 1
}
for _ in $(seq 1 90); do [ "$(cat "$R/input.cmd.done" 2>/dev/null || echo 0)" -ge 2 ] && break; gone; sleep 2; done
for _ in $(seq 1 ${SLOTWAIT:-5}); do gone; sleep 1; done  # SLOTWAIT: seconds from the title press to the slot list (longer with the old APR paths)
step "press down\nwait 700\npress down\nwait 900\n"
$W/snap0194.sh "r-$TAG" slot > /dev/null
step "press cross\nwait 3500\n"
step "press down\nwait 800\npress cross\nwait 1500\n"
for _ in $(seq 1 ${LOADWAIT:-60}); do gone; sleep 1; done  # LOADWAIT: seconds from the load to the Parry prompt (longer with heavy journals)
$W/snap0194.sh "r-$TAG" game > /dev/null
step "press options\nwait 1300\npress down\nwait 400\npress down\nwait 400\npress down\nwait 400\npress down\nwait 600\npress cross\nwait 3000\npress triangle\nwait 1500\n"
step "stick r 0 128 1600\nwait 300\ntrigger r2 255 1500\nwait 300\nstick r 128 255 350\nwait 900\n"
for k in $(seq -w 0 $((SERIES - 1))); do gone; $W/snap0194.sh "r-$TAG" "ts$k" > /dev/null; sleep $((STEP - 1)); done  # SERIES shots, one every ~STEP s
echo "== $TAG ($ENVX) $(date +%T)"
distrobox enter ubuntu -- python3 ~/bc5-work/exp0197/patch0197.py "$R"/shots/*-ts*.png 2>/dev/null | sed "s|$R/shots/||"
grep -a "fps counter" ~/bc5-work/play-pkg-last.log | tail -1 | cut -c1-90
