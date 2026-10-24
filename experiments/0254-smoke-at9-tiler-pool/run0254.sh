#!/usr/bin/env bash
# BC5 experiment 0254: one smoke run of a shared build after 2026-10-23's two rebuilds (F301's ATRAC9 vibration decoder,
# 19:28/19:31; F311's tiler scratch pool, 22:44) and the top session's integration of F312's held tail (exp 0226, on by
# default), through the shortcut's own launcher with its defaults: nothing is set but the route's input file (and
# BC5_LEAN=1 for the lean build). Titles:
#   astro  ASTRO BOT, the normal build (play-astro.sh), S4A's route (exp 0229's run0229a.sh): the route saves
#          (save-backup-astro), cross at 50 s on the title, cross 25 s later to load the save. The LIVE saves are kept
#          aside first and put back after (diff -rq).
#   astroc the same through ASTRO BOT's second shortcut, play-astro-compute.sh, which sets the compute ring, so the held
#          tail acts (untested before this run).
#   pkg    the second title, the lean build (play-pkg.sh, BC5_LEAN=1), S4L's route (exp 0203's O2: saves-before-152617,
#          o2-continue.cmd, Continue at 85 s), saves by exp 0196's ab-restore.sh.
# Recorded: the binary's md5 against the expected one, the switches that reached the emulator, the run's length, crash
# lines, new kernel lines, the play log's "bc5 tiler scratch" lines (F311, one per 1024 requests) and "bc5 ajm: ATRAC9"
# lines (F301), AJM CODEC_ERROR lines, the box's memory state, the live saves back. For ASTRO BOT also its GPU journal
# (PLAY_CAPTURE=1 in bc5-run.env), in one awk pass: exp 0226's ab0226.py counts (cpu-wait GIVEN UP, two rings NOT served,
# hold tail ... GIVEN UP, TIMEOUT), the holds and the last "hold tail: N holds" summary. Writes <tag>-verdict.txt: "pass"
# when the run had its full time, the expected binary, no crash or kernel line and the live saves back identical.
# Only the emulator PID this run started is stopped.
# The expected md5s (first 8 hex digits) come from the integration's int.out: WANT_N (normal), WANT_L (lean).
# usage: WANT_N=... WANT_L=... run0254.sh <astro|astroc|pkg> <tag> <secs>   (on the box; inside chain0254.sh the chain's lock
#        line is reused)
set -u
TITLE=${1:?astro, astroc or pkg}; TAG=${2:?tag}; SECS=${3:-150}
: "${WANT_N:?expected md5 of the normal build}" "${WANT_L:?expected md5 of the lean build}"
E=$HOME/bc5-work/exp0254; R=$E/raw; W=$HOME/bc5-work
LOCK=$W/BOX-LOCK
mkdir -p "$R"
[ "$SECS" -le 400 ] || { echo "at most 400 s"; exit 1; }
[ -e "$R/$TAG-start.txt" ] && { echo "tag $TAG already used in $R"; exit 1; }
pgrep '^kyty_emulator' > /dev/null && { echo "an emulator is running: not started"; exit 1; }
if [ -s "$LOCK" ] && ! grep -q "^exp 0254 |" "$LOCK"; then echo "the box is locked: $(cat "$LOCK")"; exit 1; fi
boxstate() {  # <label>: one line of the box's memory state and its cumulative pressure counters (exp 0229)
  echo "box $1 uptime $(cut -d' ' -f1 /proc/uptime) avail_mib $(awk '/^MemAvailable:/ {print int($2 / 1024)}' /proc/meminfo)" \
    "swapfree_mib $(awk '/^SwapFree:/ {print int($2 / 1024)}' /proc/meminfo)" \
    "$(awk '$1 ~ /^(compact_stall|compact_fail|pswpin|pswpout|pgmajfault)$/ {printf "%s %s ", $1, $2}' /proc/vmstat)" \
    "psi_mem_full_us $(awk '/^full/ {sub("total=", "", $5); print $5}' /proc/pressure/memory)" \
    "psi_io_full_us $(awk '/^full/ {sub("total=", "", $5); print $5}' /proc/pressure/io)"
}
put() {  # <from> <to>: make <to> a copy of <from>, as astro-route.sh's restore does; true when identical
  mkdir -p "$2" && cp -a "$1/." "$2/" || return 1
  local d
  for d in "$2"/*/; do d=${d%/}; [ -e "$d" ] || continue; [ -e "$1/$(basename "$d")" ] || rm -r -- "$d"; done
  diff -rq "$1" "$2" > /dev/null
}
case $TITLE in
  astro|astroc)
    SD=$W/_SaveData/PPSA21564; BK=$W/save-backup-astro; KEEP=$E/astro-live-$TAG
    LAUNCH=$W/play-astro.sh; [ "$TITLE" = astroc ] && LAUNCH=$W/play-astro-compute.sh
    LOG=$W/play-last.log; BIN=$W/kytyplus-build/src/kyty_emulator; WANT=$WANT_N; LENV=""
    [ -d "$BK" ] && [ -d "$SD" ] && [ -x "$LAUNCH" ] || { echo "no $BK, $SD or $LAUNCH"; exit 1; }
    cp -a "$SD" "$KEEP" && diff -rq "$SD" "$KEEP" > /dev/null || { echo "the live saves were not kept: stop"; exit 1; }
    put "$BK" "$SD" && echo "route saves from $BK in $SD (live saves kept in $KEEP)" | tee "$R/$TAG-restore.txt" \
      || { put "$KEEP" "$SD"; echo "route saves did not go in; live saves put back: stop"; exit 1; }
    printf 'wait 50000\npress cross\nwait 25000\npress cross\n' > "$E/in-$TAG.cmd" ;;
  pkg)
    SD=$W/_SaveData/PPSA03671; SAVES=$W/exp0196/saves-before-152617
    LAUNCH=$W/play-pkg.sh; LOG=$W/play-pkg-lean-last.log; BIN=$W/kytyplus-build-lean/src/kyty_emulator; WANT=$WANT_L
    LENV="BC5_LEAN=1"
    [ -d "$SAVES" ] && [ -x "$LAUNCH" ] || { echo "no $SAVES or $LAUNCH"; exit 1; }
    sleep 2  # ab-restore.sh names its copies by time
    OUT=$("$W/exp0196/ab-restore.sh" "$SAVES") || { echo "$OUT"; exit 1; }
    echo "$OUT" | tee "$R/$TAG-restore.txt"
    KEEP=$(echo "$OUT" | sed -n 's/.*(previous saves in \(.*\))$/\1/p')
    [ -d "$KEEP" ] || { echo "the live saves were not kept: stop"; exit 1; }
    cp "$W/exp0203/o2-continue.cmd" "$E/in-$TAG.cmd" ;;
  *) echo "title astro, astroc or pkg"; exit 1 ;;
esac
OWN=0
[ -s "$LOCK" ] || { OWN=1; echo "exp 0254 | smoke run $TAG ($TITLE, $SECS s) | start $(date +%H:%M) | until ~$(date -d "+$((SECS / 60 + 3)) min" +%H:%M)" > "$LOCK"; }
sudo -n dmesg 2> /dev/null | wc -l > "$R/$TAG-dmesg-before.txt"
MD5=$(md5sum < "$BIN" | cut -c1-32)
{ date '+%F %T'; echo "title $TITLE, $SECS s, launcher $LAUNCH md5 $(md5sum < "$LAUNCH" | cut -c1-32) ($(stat -c %y "$LAUNCH" | cut -c1-16)), extra env '$LENV'"
  echo "binary $BIN md5 $MD5 ($(stat -c %y "$BIN" | cut -c1-16)), expected $WANT"
  echo "boot $(cut -c1-8 /proc/sys/kernel/random/boot_id), up since $(uptime -s)"
  boxstate start; } > "$R/$TAG-start.txt"
# shellcheck disable=SC2086
setsid nohup distrobox enter ubuntu -- env -u BC5_EMU $LENV KYTY_BC5_INPUT_CMD="$E/in-$TAG.cmd" "$LAUNCH" \
  < /dev/null > "$R/$TAG-launch.out" 2>&1 &
# No emulator ran before the launch (checked above), so the first one now is this run's; only that PID is ever stopped.
EP=""
for _ in $(seq 1 120); do EP=$(pgrep -o '^kyty_emulator') && break; sleep 0.5; done
echo "emulator pid ${EP:-none}: $(ps -o args= -p "${EP:-1}" 2> /dev/null | cut -c1-100)" >> "$R/$TAG-start.txt"
[ -n "$EP" ] && echo "environ: $(tr '\0' '\n' < "/proc/$EP/environ" 2> /dev/null | grep -E '^(KYTY_BC5_TILER_POOL|KYTY_BC5_AT9_VIBRATION|KYTY_BC5_APR_READAHEAD|BC5_LEAN|PLAY_CAPTURE|BC5_DIRECT_HOLD_TAIL|BC5_DIRECT_CHAIN|BC5_DIRECT_COMPUTE_RING|BC5_DIRECT_CROSS_RING_WAITS)=' | tr '\n' ' ')" >> "$R/$TAG-start.txt"
T0=$(date +%s); ENDED=""
[ -n "$EP" ] || ENDED="no emulator started"
while [ -z "$ENDED" ] && [ $(($(date +%s) - T0)) -lt "$SECS" ]; do
  [ -d "/proc/$EP" ] || { ENDED="ended by itself at $(($(date +%s) - T0)) s"; break; }
  sleep 1
done
boxstate end > "$R/$TAG-box-end.txt"
if [ -n "$EP" ] && [ -d "/proc/$EP" ]; then kill "$EP"; sleep 4; [ -d "/proc/$EP" ] && kill -9 "$EP" 2> /dev/null; fi
sleep 3
echo "$TAG ${ENDED:-stopped at $SECS s}" | tee "$R/$TAG-end.txt"
cp -p "$LOG" "$R/$TAG-play.log"
grep -a -m5 "Access violation\|Segmentation\|Aborted\|terminate called" "$R/$TAG-play.log" > "$R/$TAG-crash.txt"
grep -a "bc5 tiler scratch:" "$R/$TAG-play.log" > "$R/$TAG-tiler.txt"
grep -a "bc5 ajm: ATRAC9\|CODEC_ERROR" "$R/$TAG-play.log" > "$R/$TAG-ajm.txt"
if [ "$TITLE" != pkg ]; then  # this run's GPU journal: exp 0226's counts in one pass (the box is ours until the chain ends)
  J=$(cat "$W/last-play-capture" 2> /dev/null)/gc/direct.log
  if [ -f "$J" ] && [ "$(stat -c %Y "$J")" -ge "$T0" ]; then
    { echo "journal $J $(stat -c '%y %s' "$J")"
      nice -n 19 awk '/^cpu-wait / && /GIVEN UP/ {cg++} /^two rings/ && /NOT served/ {ns++}
        /^hold tail: the wait on / && /GIVEN UP/ {hg++} /TIMEOUT/ && !/^hold tail/ {to++}
        /^hold tail: the game thread.s chain is held/ {hl++} /^hold tail: [0-9]+ holds;/ {sum = $0}
        END {printf "journal: cpu-wait GIVEN UP %d, two rings NOT served %d, hold tail GIVEN UP %d, TIMEOUT %d, hold lines %d
", cg, ns, hg, to, hl
             print "journal last summary: " (sum == "" ? "none" : sum)}' "$J"; } > "$R/$TAG-journal.txt"
  else echo "no journal of this run ($J)" > "$R/$TAG-journal.txt"; fi
fi
N=$(cat "$R/$TAG-dmesg-before.txt")
sudo -n dmesg 2> /dev/null | tail -n +"$((N + 1))" | grep -i "amdgpu\|gpu\|oom\|hung" > "$R/$TAG-dmesg-after.txt"
sleep 2
if [ "$TITLE" = astro ]; then
  if put "$KEEP" "$SD"; then echo "live saves back and identical to $KEEP" | tee "$R/$TAG-restore-back.txt"
  else echo "LIVE SAVES DIFFER from $KEEP" | tee "$R/$TAG-restore-back.txt"; fi
else
  "$W/exp0196/ab-restore.sh" "$KEEP" | tee "$R/$TAG-restore-back.txt"
  if [ -e "$KEEP/PPSA03671" ] || [ -e "$SD/PPSA03671" ]; then
    echo "NESTED SAVE COPY in $KEEP or $SD: the live saves need checking by hand" | tee -a "$R/$TAG-restore-back.txt"
  elif diff -rq "$KEEP" "$SD" > /dev/null; then echo "live saves back and identical to $KEEP" | tee -a "$R/$TAG-restore-back.txt"
  else echo "LIVE SAVES DIFFER from $KEEP" | tee -a "$R/$TAG-restore-back.txt"; fi
fi
[ "$OWN" = 1 ] && grep -q "^exp 0254 | smoke run $TAG " "$LOCK" 2> /dev/null && rm -f "$LOCK" && echo "BOX-LOCK released"
NC=$(grep -c . "$R/$TAG-crash.txt"); NK=$(grep -c . "$R/$TAG-dmesg-after.txt")
{ echo "$TAG: ${ENDED:-stopped at $SECS s}; binary md5 ${MD5:0:8} (expected $WANT); crash lines $NC, kernel lines $NK"
  echo "  tiler lines $(grep -c . "$R/$TAG-tiler.txt"); last: $(tail -1 "$R/$TAG-tiler.txt" | sed 's/.*bc5 tiler scratch: //')"
  echo "  stderr hold tail lines $(grep -ac "hold tail" "$R/$TAG-play.log")"
  [ -s "$R/$TAG-journal.txt" ] && sed 's/^/  /' "$R/$TAG-journal.txt"
  echo "  AT9 lines $(grep -c "bc5 ajm: ATRAC9" "$R/$TAG-ajm.txt"): $(grep -m2 "bc5 ajm: ATRAC9" "$R/$TAG-ajm.txt" | sed 's/.*bc5 ajm: //' | tr '\n' ';'); CODEC_ERROR lines $(grep -c CODEC_ERROR "$R/$TAG-ajm.txt")"
  { grep "^box start" "$R/$TAG-start.txt"; cat "$R/$TAG-box-end.txt"; } | awk '
    {for (i = 3; i < NF; i += 2) v[NR, $i] = $(i + 1)}
    END {printf "  box: avail %s -> %s MiB; compact_stall +%d (fail +%d), pswpin +%d, pswpout +%d, majfault +%d; PSI full mem %.1f s, io %.1f s\n",
         v[1, "avail_mib"], v[2, "avail_mib"], v[2, "compact_stall"] - v[1, "compact_stall"], v[2, "compact_fail"] - v[1, "compact_fail"],
         v[2, "pswpin"] - v[1, "pswpin"], v[2, "pswpout"] - v[1, "pswpout"], v[2, "pgmajfault"] - v[1, "pgmajfault"],
         (v[2, "psi_mem_full_us"] - v[1, "psi_mem_full_us"]) / 1e6, (v[2, "psi_io_full_us"] - v[1, "psi_io_full_us"]) / 1e6}'
} | tee "$R/$TAG-summary.txt"
FAIL=""
[ -z "$ENDED" ] || FAIL="$FAIL $ENDED;"
[ "${MD5:0:8}" = "$WANT" ] || FAIL="$FAIL binary md5 ${MD5:0:8} not $WANT;"
[ "$NC" = 0 ] || FAIL="$FAIL $NC crash lines;"
[ "$NK" = 0 ] || FAIL="$FAIL $NK kernel lines;"
grep -q "live saves back and identical" "$R/$TAG-restore-back.txt" || FAIL="$FAIL THE LIVE SAVES NEED CHECKING;"
if [ -z "$FAIL" ]; then echo pass; else echo "FAIL:$FAIL"; fi | tee "$R/$TAG-verdict.txt"
