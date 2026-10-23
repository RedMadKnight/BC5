#!/usr/bin/env bash
# BC5 experiment 0228: the load-time A/B for one title as one detached chain under one BOX-LOCK line: a warm-up run
# (RA0, not scored: the caches come to the same state for every scored run), then RA0, RA4, FIX, OLD, OLD, FIX, RA4, RA0
# (each arm early and late), SECS s each (default 150), 15 s apart. Stops on saves that differ, a new amdgpu line or a
# new boot. Only on the boot of 2026-10-23 00:05 or later (BOOT_AFTER, the reboot after the box thrashed).
# Start it only after the maintainer has stopped (no emulator, no lock) and on the top session's Go.
# usage: setsid nohup chain0228.sh <astro|pkg> > raw/chain-<title>.out 2>&1 < /dev/null &   (on the box)
set -u
TITLE=${1:?astro or pkg}; SECS=${SECS:-150}
E=$HOME/bc5-work/exp0228; R=$E/raw; LOCK=$HOME/bc5-work/BOX-LOCK
BOOT=$(cut -c1-8 /proc/sys/kernel/random/boot_id)
N0=$(sudo -n dmesg 2> /dev/null | wc -l)
P=A; [ "$TITLE" = pkg ] && P=P; P=${TAGP:-$P}
RUNS=${RUNS:-W-RA0 1-RA0 2-RA4 3-FIX 4-OLD 5-OLD 6-FIX 7-RA4 8-RA0}  # the mini A/B of 2026-10-23: TAGP=AM RUNS="1-OLD 2-CUR 3-OLD 4-CUR"
NRUN=$(echo $RUNS | wc -w)
mkdir -p "$R"
checks() {
  [ "$(cut -c1-8 /proc/sys/kernel/random/boot_id)" = "$BOOT" ] || { echo "boot id changed: stop"; return 1; }
  local k
  k=$(sudo -n dmesg 2> /dev/null | tail -n +"$((N0 + 1))" | grep -ci "amdgpu.*\(fault\|timeout\|reset\|error\)")
  [ "$k" = 0 ] || { echo "$k new amdgpu lines: stop"; return 1; }
}
release() { grep -q "^exp 0228 | chain $TITLE: " "$LOCK" 2> /dev/null && rm -f "$LOCK" && echo "== $(date +%T) BOX-LOCK released"; }
[ ! -s "$LOCK" ] && ! pgrep '^kyty_emulator' > /dev/null || { echo "box not free at $(date +%T): $(cat "$LOCK" 2> /dev/null): stop"; exit 1; }
checks || exit 1
BOOT_AFTER=${BOOT_AFTER:-2026-10-23 00:05:00}
[ "$(date -d "$(uptime -s)" +%s)" -ge "$(date -d "$BOOT_AFTER" +%s)" ] || { echo "the box has not booted since $BOOT_AFTER: stop"; exit 1; }
echo "exp 0228 | chain $TITLE: load-time A/B, $NRUN runs ($RUNS) x $SECS s (Go from the top session) | start $(date +%H:%M) | until ~$(date -d "+$((NRUN * (SECS + 45) / 60 + 2)) min" +%H:%M)" > "$LOCK"
if [[ " $RUNS" == *-FIX* ]] && [ ! -x "$E/kyty_emulator" ]; then  # the fixed binary: a one-file build against the shared objects (exp 0222's build)
  echo "== $(date +%T) build"
  cp -p "$E/src/libAmpr.fix.cpp" "$E/src/libAmpr.cpp"
  distrobox enter ubuntu -- nice -n 10 python3 -I "$E/build0228.py" "$HOME/bc5-work/exp0203/compdb.json" > "$R/build.log" 2>&1
  RC=$?
  sed 's/\x1b\[[0-9;]*m//g' "$R/build.log" | grep -E "warning:|error:" | cut -c1-200
  echo "== $(date +%T) build rc $RC"
  [ $RC = 0 ] && grep -q "bc5-apr-r%zu-%zu" <(strings "$E/kyty_emulator") || { echo "no fixed binary: stop"; release; exit 1; }
  md5sum "$E/kyty_emulator" "$E/src/libAmpr.cpp" "$HOME/bc5-work/kytyplus-build/src/kyty_emulator"
fi
for T in $RUNS; do
  TAG=$P$T
  echo "== $(date +%T) run $TAG"
  "$E/run0228.sh" "$TITLE" "$TAG" "${T#*-}" "$SECS" > "$R/$TAG-run.out" 2>&1
  cat "$R/$TAG-run.out"
  grep -q "live saves back and identical" "$R/$TAG-restore-back.txt" 2> /dev/null || { echo "== $TAG: THE LIVE SAVES NEED CHECKING: stop"; release; exit 1; }
  grep -q "no emulator started" "$R/$TAG-end.txt" 2> /dev/null && { echo "== $TAG: no emulator seen: stop"; release; exit 1; }
  pgrep '^kyty_emulator' > /dev/null && { echo "== $TAG: an emulator is still running after the run: stop"; release; exit 1; }
  checks || { release; exit 1; }
  sleep 15
done
release
echo "== $(date +%T) chain $TITLE done"
