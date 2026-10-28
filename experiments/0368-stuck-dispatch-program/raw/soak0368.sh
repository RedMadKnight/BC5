#!/usr/bin/env bash
# BC5 experiment 0368: the soak that F492 calls for — repeated S6N RT-on runs on the SHARED normal build with
# BC5_DIRECT_UMR_ON_TIMEOUT=1 (exp 0058: the halted waves dumped 0.9 s into a stalled wait, before the kernel's reset),
# until the first event (a hang, a reset, a machine-down) or the deadline. Each run is s6n0368.sh (exp 0364's S6N
# script on the shared build: the S6N route save, RT on, a private working directory, the live saves compared only,
# the kernel log polled). This loop owns the box lock line for the whole soak (its expected end in it), streams the
# kernel log beside the runs, and stops after a run that did not pass. usage: soak0368.sh <live-saves sum> [deadline HH:MM] [secs]
set -u
EXPECT_SAVES=${1:?the live saves sum}; DEADLINE=${2:-22:45}; SECS=${3:-600}
W=$HOME/bc5-work; E=$W/exp0368; R=$E/raw; LOCK=$W/BOX-LOCK
mkdir -p "$R"
pgrep -x kyty_emulator > /dev/null && { echo "an emulator runs: not started"; exit 1; }
[ -e "$LOCK" ] || touch "$LOCK"
[ -s "$LOCK" ] && { echo "box locked: $(cat "$LOCK")"; exit 1; }
[ -x "$E/s6n0368.sh" ] || { echo "no $E/s6n0368.sh"; exit 1; }
BIN=$W/kytyplus-build/src/kyty_emulator; M=$(md5sum < "$BIN" | cut -c1-8)
lockline() { echo "bvh exp 0368 | SOAK: S6N RT on 600 s repeated on the shared normal build $M, BC5_DIRECT_UMR_ON_TIMEOUT=1, run $1 | start $(date +%H:%M) | until $DEADLINE (the first event stops it)" > "$LOCK"; }
lockline 0
trap 'grep -q "^bvh exp 0368 | SOAK" "$LOCK" 2> /dev/null && : > "$LOCK"; [ -n "${SP:-}" ] && kill "$SP" 2> /dev/null' EXIT
DL=$(date -d "today $DEADLINE" +%s)
timeout $((DL - $(date +%s) + 120)) sudo -n dmesg -w > "$R/soak-kernel-stream.txt" 2>&1 &
SP=$!
echo "$(date '+%F %T') soak start: build $M, deadline $DEADLINE, $SECS s a run, umr on timeout" | tee -a "$R/soak.log"
n=0
while :; do
  now=$(date +%s)
  if [ $((now + SECS + 180)) -gt "$DL" ]; then echo "$(date '+%F %T') deadline $DEADLINE: no more runs (a full run would end past it)" | tee -a "$R/soak.log"; break; fi
  n=$((n + 1)); TAG=S$n
  lockline "$n"
  echo "$(date '+%F %T') run $TAG starting" | tee -a "$R/soak.log"
  SOAK=1 BC5_0368_SWITCHES="BC5_DIRECT_UMR_ON_TIMEOUT=1" PLAY_PKG_MD5=55531ab6 bash "$E/s6n0368.sh" "$EXPECT_SAVES" "$TAG" "$SECS" on > "$R/$TAG.console" 2>&1
  rc=$?
  V=$(grep -a "^$TAG:" "$R/$TAG.console" | tail -1 | cut -c1-230)
  echo "$(date '+%F %T') run $TAG rc $rc: $V" | tee -a "$R/soak.log"
  grep -a "^fps\|flips/s" "$R/$TAG.console" | tail -1 | cut -c1-120 | tee -a "$R/soak.log"
  if ! grep -a -q "^pass" "$R/$TAG.console"; then
    echo "$(date '+%F %T') run $TAG did not pass: the soak stops (the event's dumps: $(ls -t ~/bc5-data/captures/play-*/gc/umr-waves-*.txt 2> /dev/null | head -2 | tr '\n' ' '))" | tee -a "$R/soak.log"
    break
  fi
  if grep -a -q "not started" "$R/$TAG.console"; then echo "$(date '+%F %T') run $TAG not started: the soak stops" | tee -a "$R/soak.log"; break; fi
  sleep 20
done
echo "$(date '+%F %T') soak end after $n runs" | tee -a "$R/soak.log"
