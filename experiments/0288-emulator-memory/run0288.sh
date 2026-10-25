#!/usr/bin/env bash
# BC5 experiment 0288: one scripted run of the second title on its play route, with the box's memory sampled every 10 s
# (sample0288.sh) and, in arm M, the per-heap breakdown near the end (BC5_DIRECT_BREAKDOWN_AT, patch0288.py in the private
# binary ~/bc5-work/exp0288/kyty_emulator). Exp 0264's ab0264.sh (the TCP session's catch0260.sh) reduced to one run:
#   - arm M: the private binary through play-pkg.sh (BC5_EMU), BC5_DIRECT_BREAKDOWN_AT=<at> (default 240 s); the run goes
#     on until the journal holds the breakdown of both memfds or <secs> + 120 s have passed;
#   - arm L: the shared lean build (BC5_LEAN=1), nothing else set: the lean build's memory over the same route;
#   - arm N: the shared normal build, nothing else set: the reference for L (same route, same length).
#   - MOUNT_ARENAS=<n>: before the run, if no emulator runs, the package mount is unmounted and mounted again by hand with
#     MALLOC_ARENA_MAX=<n> (bc5-mount only; the launcher then finds it mounted). After the run it is unmounted, so the next
#     launcher start mounts it as usual. Off by default.
# Route and saves as exp 0264: S6N's route (exp 0203's o2-continue.cmd, Continue at 85 s) from exp 0196's saves-before-152617,
# put in and taken back by exp 0196's ab-restore.sh; the live saves' checksum is taken at the start and must be the same at
# the end. The run stops at the first kernel amdgpu line (checked every second), a crash line, a TIMEOUT, the wrong binary.
# Only the emulator PID the run started is ever stopped. Attended: on the box supervisor's GO, the maintainer reachable.
# usage: run0288.sh <tag> <M|L|N> [secs] [at]   (on the box; default 300 s, breakdown at 240 s)
set -u
TAG=$1; ARM=$2; SECS=${3:-300}; AT=${4:-240}
E=$HOME/bc5-work/exp0288; R=$E/raw; W=$HOME/bc5-work; LOCK=$W/BOX-LOCK
SAVES=$W/exp0196/saves-before-152617; LAUNCH=$W/play-pkg.sh; SD=$W/_SaveData/PPSA03671
PKG=$HOME/bc5-data/pkg/game.pkg; MNT=$HOME/bc5-data/mnt/pkg-play; BM=$W/bc5-tools-ubuntu/release/bc5-mount
MOUNT_ARENAS=${MOUNT_ARENAS:-}
mkdir -p "$R"
[ "$SECS" -le 600 ] || { echo "at most 600 s"; exit 1; }
[ -e "$R/$TAG-start.txt" ] && { echo "tag $TAG already used"; exit 1; }
pgrep '^kyty_emulator' > /dev/null && { echo "an emulator is running: not started"; exit 1; }
if [ -s "$LOCK" ] && ! grep -q '^exp 0288 | chain' "$LOCK"; then echo "the box is locked: $(cat "$LOCK")"; exit 1; fi  # chain0288.sh holds one line across the runs
[ -d "$SAVES" ] && [ -x "$LAUNCH" ] && [ -x "$W/exp0196/ab-restore.sh" ] && [ -x "$E/sample0288.sh" ] || { echo "no $SAVES, $LAUNCH, ab-restore.sh or sample0288.sh"; exit 1; }
# Overnight condition (the top session, 2026-10-25): ray tracing off in every arm (KYTY_BC5_RT=0; the launcher's
# KYTY_BC5_RT_BUILD_PGM list drops the BVH build work) — S6N's route took the machine down at 17:47 with RT on and nobody can
# power-cycle before ~07:00. The heaps are allocated either way, so Q1, Q2 and Q4 measure the same.
RT=${RT:-KYTY_BC5_RT=0}
case $ARM in
  M) BIN=$E/kyty_emulator; LOG=$W/play-pkg-last.log; ENVS="$RT BC5_EMU=$BIN BC5_DIRECT_BREAKDOWN_AT=$AT BC5_DIRECT_BREAKDOWN_NODATA=1" ;;
  L) BIN=$W/kytyplus-build-lean/src/kyty_emulator; LOG=$W/play-pkg-lean-last.log; ENVS="$RT BC5_LEAN=1" ;;
  N) BIN=$W/kytyplus-build/src/kyty_emulator; LOG=$W/play-pkg-last.log; ENVS="$RT" ;;
  *) echo "arm M, L or N"; exit 1 ;;
esac
REF_SAVES=${REF_SAVES:-c0ee58b92c0cadc2}  # the live saves' reference checksum named by the top session (2026-10-25)
[ -x "$BIN" ] || { echo "no binary $BIN"; exit 1; }
WANT=$(md5sum < "$BIN" | cut -c1-8)
saves() { (cd "$W/_SaveData" && find PPSA03671 -type f -exec md5sum {} + | sort -k2 | md5sum | cut -c1-16); }  # exp 0253's ab0253.sh
S0=$(saves); echo "$(date '+%F %T') $TAG live saves $S0 (reference $REF_SAVES); binary $BIN md5 $WANT ($(stat -c %y "$BIN" | cut -c1-16))" | tee -a "$R/saves.txt"
[ "$S0" = "$REF_SAVES" ] || { echo "the live saves are $S0, not the reference $REF_SAVES: not started (REF_SAVES=<md5> to accept another state)"; exit 1; }
echo "exp 0288 | run $TAG arm $ARM: the second title's S6N route, $SECS s, memory sampled, ${ENVS:-launcher defaults}${MOUNT_ARENAS:+, mount MALLOC_ARENA_MAX=$MOUNT_ARENAS}, maintainer reachable | start $(date +%H:%M) | until ~$(date -d "+$(((SECS + 180) / 60 + 2)) min" +%H:%M)" > "$LOCK"
trap 'grep -q "^exp 0288 | run $TAG " "$LOCK" 2> /dev/null && rm -f "$LOCK"' EXIT
boxstate() {  # <label>: the box's memory state and pressure counters (exp 0229, as run0254b.sh)
  echo "box $1 uptime $(cut -d' ' -f1 /proc/uptime) avail_mib $(awk '/^MemAvailable:/ {print int($2 / 1024)}' /proc/meminfo)" \
    "swapfree_mib $(awk '/^SwapFree:/ {print int($2 / 1024)}' /proc/meminfo)" \
    "$(awk '$1 ~ /^(compact_stall|compact_fail|pswpin|pswpout|pgmajfault)$/ {printf "%s %s ", $1, $2}' /proc/vmstat)" \
    "psi_mem_full_us $(awk '/^full/ {sub("total=", "", $5); print $5}' /proc/pressure/memory)"
}
mountstate() {  # <label>: bc5-mount's pid, uptime and memory
  local p; p=$(pgrep -o -x bc5-mount || echo "")
  if [ -n "$p" ]; then echo "mount $1 pid $p etimes $(ps -o etimes= -p "$p" | tr -d ' ') $(awk '/^Rss:/ {r=$2} /^Swap:/ {w=$2} END {printf "rss_mib %d swap_mib %d", r/1024, w/1024}' "/proc/$p/smaps_rollup") arenas $(tr '\0' '\n' < "/proc/$p/environ" | grep -c '^MALLOC_ARENA_MAX=')"
  else echo "mount $1 none"; fi
}
# The launcher runs inside the ubuntu distrobox, so its bc5-mount lives in that container's mount namespace: the host's
# `mountpoint` does not see it (the N1 attempt of 01:22 saw "not a mountpoint" with the mount alive). Every mount step
# here goes through the distrobox too. unmount_wait: fusermount, then wait for the process to leave; never a kill.
inbox() { distrobox enter ubuntu -- "$@"; }
unmount_wait() {
  if inbox mountpoint -q "$MNT"; then inbox fusermount3 -u "$MNT" || { echo "cannot unmount $MNT"; return 1; }; fi
  for _ in $(seq 1 60); do pgrep -x bc5-mount > /dev/null || return 0; sleep 1; done
  echo "bc5-mount $(pgrep -x bc5-mount | tr '\n' ' ')still runs 60 s after the unmount; left alone"; return 1
}
mount_wait() {  # [MALLOC_ARENA_MAX=<n>]: the launcher's own mount command (play-pkg.sh), inside the distrobox
  # The N1 attempt of 01:54 started this with `inbox env ... setsid nohup ... &` from the host side and the mount never came
  # up (an empty log); the form that works is the launcher's own, a background job inside the container's shell.
  inbox bash -c "$1 BC5_MOUNT_DISK_CACHE=\$HOME/bc5-data/cache/bc5-mount nohup $BM mount $PKG $MNT > $R/$TAG-mount-${2:-hand}.log 2>&1 &"
  for _ in $(seq 1 150); do inbox mountpoint -q "$MNT" && return 0; sleep 0.2; done
  echo "the mount did not come up (see $R/$TAG-mount-${2:-hand}.log)"; return 1
}
REMOUNTED=""
if [ -n "$MOUNT_ARENAS" ]; then
  mountstate before-remount | tee -a "$R/$TAG-mount.txt"
  unmount_wait | tee -a "$R/$TAG-mount.txt" || exit 1
  mount_wait "MALLOC_ARENA_MAX=$MOUNT_ARENAS" arenas || exit 1
  REMOUNTED=1; mountstate after-remount | tee -a "$R/$TAG-mount.txt"
fi
sleep 2  # ab-restore.sh names its copies by time
OUT=$("$W/exp0196/ab-restore.sh" "$SAVES") || { echo "FAIL: route saves not put in: $OUT" | tee "$R/$TAG-verdict.txt"; exit 1; }
echo "$OUT" > "$R/$TAG-restore.txt"
KEEP=$(echo "$OUT" | sed -n 's/.*(previous saves in \(.*\))$/\1/p')
[ -d "$KEEP" ] || { echo "FAIL: the live saves were not kept" | tee "$R/$TAG-verdict.txt"; exit 1; }
cp "$W/exp0203/o2-continue.cmd" "$E/in-$TAG.cmd"
N=$(sudo -n dmesg 2> /dev/null | wc -l)
{ date '+%F %T'; echo "run $TAG, arm $ARM ('${ENVS:-launcher default}'), $SECS s, breakdown at $AT s, launcher $LAUNCH md5 $(md5sum < "$LAUNCH" | cut -c1-8), binary $BIN md5 $WANT"
  echo "boot $(cut -c1-8 /proc/sys/kernel/random/boot_id), up since $(uptime -s)"; boxstate start; mountstate start; } > "$R/$TAG-start.txt"
setsid nohup "$E/sample0288.sh" "$R/$TAG-mem.txt" $((SECS + 150)) < /dev/null > /dev/null 2>&1 &
# shellcheck disable=SC2086
setsid nohup distrobox enter ubuntu -- env $ENVS KYTY_BC5_INPUT_CMD="$E/in-$TAG.cmd" "$LAUNCH" < /dev/null > "$R/$TAG-launch.out" 2>&1 &
EP=""
for _ in $(seq 1 120); do EP=$(pgrep -o '^kyty_emulator') && break; sleep 0.5; done
T0=$(date +%s); ENDED=""
if [ -z "$EP" ]; then ENDED="no emulator started"
else
  echo "emulator pid $EP exe $(readlink "/proc/$EP/exe")" >> "$R/$TAG-start.txt"
  sleep 2
  echo "environ: $(tr '\0' '\n' < "/proc/$EP/environ" 2> /dev/null | grep -E '^(BC5_EMU|BC5_LEAN|KYTY_BC5_RT|BC5_DIRECT_BREAKDOWN_AT|BC5_DIRECT_EAGER_NAMES|KYTY_GUEST_MEMORY_MB|BC5_DIRECT_SKIP_PGM|BC5_DIRECT_CS_PREFIX|KYTY_BC5_TILER_POOL|PLAY_CAPTURE)=' | tr '\n' ' ' | cut -c1-600)" >> "$R/$TAG-start.txt"
  [ "$(md5sum < "/proc/$EP/exe" | cut -c1-8)" = "$WANT" ] || ENDED="the emulator is not md5 $WANT"
fi
J=""
while [ -z "$ENDED" ]; do
  t=$(($(date +%s) - T0))
  [ -d "/proc/$EP" ] || { ENDED="ended by itself at $t s"; break; }
  sudo -n dmesg 2> /dev/null | tail -n +"$((N + 1))" | grep -qi "amdgpu" && { ENDED="kernel amdgpu line at $t s"; break; }
  if [ "$ARM" = M ]; then
    [ -n "$J" ] || J=$(ls -td ~/bc5-data/captures/play-*/gc 2> /dev/null | head -1)/direct.log
    if [ "$t" -ge "$SECS" ] && [ -f "$J" ] && [ "$(LC_ALL=C grep -a -c " by name (at)" "$J")" -ge 2 ]; then ENDED="stopped at $t s, both breakdowns in the journal"; break; fi
    [ "$t" -ge $((SECS + 120)) ] && { ENDED="stopped at $t s, breakdowns found: $(LC_ALL=C grep -a -c " by name (at)" "$J" 2> /dev/null)"; break; }
  else
    [ "$t" -ge "$SECS" ] && { ENDED="stopped at $t s"; break; }
  fi
  sleep 1
done
boxstate end > "$R/$TAG-box-end.txt"; mountstate end >> "$R/$TAG-box-end.txt"
if [ -n "$EP" ] && [ -d "/proc/$EP" ]; then kill "$EP"; sleep 4; [ -d "/proc/$EP" ] && kill -9 "$EP" 2> /dev/null; fi
sleep 3
echo "$TAG $ENDED" > "$R/$TAG-end.txt"
cp -p "$LOG" "$R/$TAG-play.log" 2> /dev/null
grep -a -m5 "Access violation\|Segmentation\|Aborted\|terminate called" "$R/$TAG-play.log" > "$R/$TAG-crash.txt" 2> /dev/null
if [ "$ARM" != L ]; then
  [ -n "$J" ] || J=$(ls -td ~/bc5-data/captures/play-*/gc 2> /dev/null | head -1)/direct.log
  if [ -f "$J" ] && [ "$(stat -c %Y "$J")" -ge "$T0" ]; then
    echo "journal $J $(stat -c '%y %s' "$J")" > "$R/$TAG-journal.txt"
    LC_ALL=C nice -n 19 ionice -c3 grep -a -E "^frame profile: t |^(direct|private)[ :]|^  [A-Za-z(].* views: |^hint |^learned|^scratch|^aliases|TIMEOUT|GIVEN UP|ENOMEM|EAGAIN|MAPS FAILED|^timing split" "$J" | gzip > "$R/$TAG-x.gz"
    zcat "$R/$TAG-x.gz" | grep -a "TIMEOUT" > "$R/$TAG-probe.txt"
    zcat "$R/$TAG-x.gz" | grep -a -A 40 " by name " > "$R/$TAG-breakdown.txt"
  else echo "no journal of this run ($J)" > "$R/$TAG-journal.txt"; : > "$R/$TAG-probe.txt"; fi
else echo "lean build: no journal" > "$R/$TAG-journal.txt"; : > "$R/$TAG-probe.txt"; fi
sudo -n dmesg 2> /dev/null | tail -n +"$((N + 1))" | grep -i "amdgpu\|gpu\|oom\|hung\|SQC" > "$R/$TAG-dmesg-after.txt"
sleep 2
"$W/exp0196/ab-restore.sh" "$KEEP" > "$R/$TAG-restore-back.txt" 2>&1
if [ -e "$KEEP/PPSA03671" ] || [ -e "$SD/PPSA03671" ]; then echo "NESTED SAVE COPY in $KEEP or $SD" >> "$R/$TAG-restore-back.txt"
elif diff -rq "$KEEP" "$SD" > /dev/null; then echo "live saves back and identical to $KEEP" >> "$R/$TAG-restore-back.txt"
else echo "LIVE SAVES DIFFER from $KEEP" >> "$R/$TAG-restore-back.txt"; fi
if [ -n "$REMOUNTED" ]; then  # the arena mount goes, and the launcher's normal mount comes back in its place (default arenas)
  mountstate before-unmount >> "$R/$TAG-mount.txt"
  unmount_wait >> "$R/$TAG-mount.txt" 2>&1 && mount_wait "" normal >> "$R/$TAG-mount.txt" 2>&1 && echo "the launcher's normal mount is back" >> "$R/$TAG-mount.txt"
  mountstate after-normal-remount >> "$R/$TAG-mount.txt"
fi
S1=$(saves); echo "$(date '+%F %T') $TAG live saves $S1 (were $S0)" | tee -a "$R/saves.txt"
NC=$(grep -c . "$R/$TAG-crash.txt"); NK=$(grep -c . "$R/$TAG-dmesg-after.txt"); NT=$(grep -c "TIMEOUT" "$R/$TAG-probe.txt")
FAIL=""
case "$ENDED" in stopped*) ;; *) FAIL="$FAIL $ENDED;" ;; esac
[ "$NC" = 0 ] || FAIL="$FAIL $NC crash lines;"
[ "$NK" = 0 ] || FAIL="$FAIL $NK kernel lines;"
[ "$NT" = 0 ] || FAIL="$FAIL $NT TIMEOUT lines;"
[ "$S1" = "$S0" ] || FAIL="$FAIL THE LIVE SAVES CHANGED ($S0 -> $S1);"
grep -q "live saves back and identical" "$R/$TAG-restore-back.txt" || FAIL="$FAIL THE LIVE SAVES NEED CHECKING;"
echo "$TAG (arm $ARM): $ENDED; crash lines $NC, kernel lines $NK, TIMEOUT lines $NT; samples $(grep -vc '^#' "$R/$TAG-mem.txt" 2> /dev/null)" > "$R/$TAG-summary.txt"
if [ -z "$FAIL" ]; then echo pass; else echo "FAIL:$FAIL"; fi > "$R/$TAG-verdict.txt"
cat "$R/$TAG-summary.txt" "$R/$TAG-verdict.txt"
grep -q "^exp 0288 | run $TAG " "$LOCK" 2> /dev/null && rm -f "$LOCK" && echo "BOX-LOCK released"
