#!/usr/bin/env bash
# BC5 experiment 0301: MangoHud in every build, hidden at the start, shown and hidden by Emulation > MangoHud
# (patch_0301.diff), as private binaries. On the box, from SSH, attended; ~/bc5-work/exp0301 holds this script,
# build0301.py, launchers0301.py and patch_0301.diff.
#   prep      the private tree (the shared tree's four files, md5-checked, patched into exp0301/tree/src), the
#             launchers (launchers0301.py: the proposal and the private play-pkg-0301.sh), the S6N route's save copy
#             (exp0196/saves-before-152617, the state exp 0264 used) and the input configuration copy
#             (exp0194/input-0194.cfg). Reads only; writes only under exp0301.
#   build     exp0301/normal/kyty_emulator and exp0301/lean/kyty_emulator from the shared builds' other objects
#             (build0301.py, nice 19), under our lock line. No emulator, no GPU.
#   run <tag> <normal|lean> <secs> [VAR=value ...]
#             one run of the second title through play-pkg-0301.sh in exp0301/wd: the save copy reset into
#             wd/_SaveData before the run, the S6N route (exp0203/o2-continue.cmd: Continue at 85 s), ray tracing
#             off (KYTY_BC5_RT=0), the private input configuration (reset to its base copy unless KEEPCFG=1).
#             Samples at SAMPLES seconds (default 30 150 250): the process's VmRSS/VmHWM, threads, MangoHud's
#             threads, whether libMangoHud.so is mapped, MangoHud's control socket, GTT in use, MemAvailable; the
#             process's CPU time at the end. dmesg is polled every 3 s and the run stopped at a new amdgpu
#             fault/timeout/reset line. Only the emulator this script started is stopped. Kept: the emulator log's
#             host-menu and MangoHud lines, the journal's frame-profile lines (gzipped), the input configuration.
# The maintainer's saves (~/bc5-work/_SaveData), input.cfg and route-record.txt are never read or written: the
# launcher runs in exp0301/wd with its own copies. Their checksum is printed before and after each run.
set -u
W=$HOME/bc5-work; E=$W/exp0301; K=$HOME/src/KytyPlus; LOCK=$W/BOX-LOCK
LOCKTAG="mangohud exp 0301"
saves() { (cd "$W/_SaveData" && find PPSA03671 -type f -exec md5sum {} + | sort -k2 | md5sum | cut -c1-16); }
guard() {  # no emulator, no lock line but ours
  pgrep '^kyty_emulator' > /dev/null && { echo "an emulator runs: stop"; exit 1; }
  local other; other=$(grep -v "^$LOCKTAG" "$LOCK" 2> /dev/null)
  [ -n "$other" ] && { echo "box locked: $other"; exit 1; }
  return 0
}
lock() { echo "$LOCKTAG | $1 | start $(date +%H:%M) | until ~$(date -d "+$2 min" +%H:%M)" >> "$LOCK"; }
unlock() { sed -i "/^$LOCKTAG | /d" "$LOCK" 2> /dev/null; [ -s "$LOCK" ] || rm -f "$LOCK"; }
FILES="src/graphics/presentation/hostMenu.cpp src/graphics/presentation/hostMenu.h src/graphics/presentation/settingsOverlay.cpp src/graphics/presentation/window/hostInput.cpp"
BASE="afb5ae7e 1fc6fe2a e302a5f7 8a578f90"  # their md5s in patch 0001 on main 36a68b0 (= the shared builds e62a97c6 / 753889c9)
case "${1:-}" in
prep)
  guard
  mkdir -p "$E/raw" "$E/tree" "$E/wd/_SaveData"
  rm -rf "$E/tree/src"; set -- $BASE
  for f in $FILES; do
    m=$(md5sum < "$K/$f" | cut -c1-8)
    [ "$m" = "$1" ] || { echo "$f is $m, not $1: the diff's base differs"; exit 1; }
    mkdir -p "$(dirname "$E/tree/$f")"; cp "$K/$f" "$E/tree/$f"; shift
  done
  (cd "$E/tree" && git apply --check "$E/patch_0301.diff" && git apply "$E/patch_0301.diff") || { echo "patch failed"; exit 1; }  # no patch(1) on the host
  for f in $FILES; do echo "patched $f $(md5sum < "$E/tree/$f" | cut -c1-8)"; done | tee "$E/raw/tree-md5.txt"
  python3 -I "$E/launchers0301.py" "$W" "$E/launch" || exit 1
  cp "$E/launch/play-pkg-0301.sh" "$E/play-pkg-0301.sh"
  echo "launchers: play-pkg.sh $(md5sum < "$W/play-pkg.sh" | cut -c1-8), play-astro.sh $(md5sum < "$W/play-astro.sh" | cut -c1-8) -> proposal $(md5sum < "$E/launch/play-pkg.sh" | cut -c1-8) / $(md5sum < "$E/launch/play-astro.sh" | cut -c1-8)" | tee -a "$E/raw/tree-md5.txt"
  [ -d "$E/saves-s6n" ] || cp -a "$W/exp0196/saves-before-152617" "$E/saves-s6n"
  cp "$W/exp0194/input-0194.cfg" "$E/input-0301.base.cfg"
  cp "$W/exp0203/o2-continue.cmd" "$E/route.cmd"
  echo "prep done: saves-s6n $(du -sh "$E/saves-s6n" | cut -f1), input base $(md5sum < "$E/input-0301.base.cfg" | cut -c1-8), route $(md5sum < "$E/route.cmd" | cut -c1-8)"
  ;;
build)
  guard
  lock "build of exp0301/normal and exp0301/lean kyty_emulator (three units + link each, nice 19, no emulator)" 20
  trap unlock EXIT
  {
    for b in kytyplus-build kytyplus-build-lean; do echo "shared $b $(md5sum < "$W/$b/src/kyty_emulator" | cut -c1-8) $(stat -c '%y' "$W/$b/src/kyty_emulator" | cut -c1-16)"; done
  } | tee "$E/raw/build-inputs.txt"
  rc=0
  for fl in normal lean; do
    case $fl in normal) B=$W/kytyplus-build ;; lean) B=$W/kytyplus-build-lean ;; esac
    echo "== $(date +%T) compdb $fl"
    distrobox enter ubuntu -- sh -c "cd '$B' && ninja -t compdb -x" > "$E/compdb-$fl.json" 2> "$E/raw/compdb-$fl.err" || { echo "compdb failed"; exit 1; }
    grep -q '"output": "src/kyty_emulator"' "$E/compdb-$fl.json" || { echo "no link command in the $fl compdb"; exit 1; }
    echo "== $(date +%T) build $fl"
    ( cd "$E" && distrobox enter ubuntu -- python3 -I "$E/build0301.py" "$fl" "$E/compdb-$fl.json" ) > "$E/raw/build-$fl.out" 2>&1
    r=$?; [ $r = 0 ] || rc=$r
    echo "== $(date +%T) build $fl rc $r, warnings $(grep -c "warning:" "$E/raw/build-$fl.out")"
    grep -A3 "exp0301/tree/src/.*:[0-9]*:[0-9]*: .*\(warning\|error\)" "$E/raw/build-$fl.out" | grep -v "^--" | sed 's/\x1b\[[0-9;]*m//g' | head -30
    BIN=$E/$fl/kyty_emulator
    [ -x "$BIN" ] && echo "$fl: $(stat -c %s "$BIN") bytes md5 $(md5sum < "$BIN" | cut -c1-8); strings: $(strings "$BIN" | grep -c "bc5-mangohud-%d\|MangoHud control socket\|MangoHud takes on or off")/3" | tee -a "$E/raw/build-inputs.txt"
  done
  for b in kytyplus-build kytyplus-build-lean; do echo "shared $b after: $(md5sum < "$W/$b/src/kyty_emulator" | cut -c1-8)"; done | tee -a "$E/raw/build-inputs.txt"
  exit $rc
  ;;
run)
  TAG=$2; FL=$3; SECS=$4; shift 4
  guard
  [ "$SECS" -le 600 ] || { echo "at most 600 s"; exit 1; }
  O=$E/r-$TAG; [ -e "$O" ] && { echo "tag $TAG used"; exit 1; }
  BIN=$E/$FL/kyty_emulator; [ -x "$BIN" ] || { echo "no $BIN"; exit 1; }
  use=$(df --output=pcent /var/home | tail -1 | tr -dc 0-9); [ "$use" -ge 80 ] && { echo "/var/home at $use %"; exit 1; }
  mkdir -p "$O"
  S0=$(saves); echo "$(date '+%F %T') $TAG: live saves $S0 (not used by the run)" | tee "$O/saves.txt"
  lock "run $TAG ($FL, $SECS s, second title S6N route, RT off, private wd and saves; $*)" $(( SECS / 60 + 3 ))
  EPID=""
  trap '[ -n "$EPID" ] && kill "$EPID" 2> /dev/null; unlock' EXIT
  trap 'exit 1' HUP INT TERM
  rm -rf "$E/wd/_SaveData/PPSA03671" && cp -a "$E/saves-s6n" "$E/wd/_SaveData/PPSA03671" || { echo "save copy failed"; exit 1; }
  [ "${KEEPCFG:-0}" = 1 ] && [ -f "$E/input-0301.cfg" ] || cp "$E/input-0301.base.cfg" "$E/input-0301.cfg"
  cp "$E/input-0301.cfg" "$O/input-before.cfg"; cp "$E/route.cmd" "$O/input.cmd"; sync
  { echo "$(date '+%F %T') run $TAG: $FL binary $(md5sum < "$BIN" | cut -c1-8), $SECS s, switches: KYTY_BC5_RT=0 $*"
    echo "kernel $(uname -r), boot $(cut -c1-8 /proc/sys/kernel/random/boot_id), up since $(uptime -s), /var/home $use %"; } > "$O/start.txt"
  before=$(sudo -n dmesg | wc -l); UP0=$(cut -d" " -f1 /proc/uptime)
  setsid nohup distrobox enter ubuntu -- env BC5_EMU="$BIN" KYTY_BC5_RT=0 KYTY_BC5_INPUT_CMD="$O/input.cmd" \
    BC5_0301_INPUT_CONFIG="$E/input-0301.cfg" "$@" "$E/play-pkg-0301.sh" < /dev/null > "$O/launcher.out" 2>&1 &
  for _ in $(seq 1 90); do EPID=$(pgrep -n -x kyty_emulator) && break; sleep 1; done
  [ -n "$EPID" ] || { echo "no emulator started"; cat "$O/launcher.out"; exit 1; }
  T0=$(date +%s)
  echo "emulator pid $EPID exe $(readlink "/proc/$EPID/exe") md5 $(md5sum < "/proc/$EPID/exe" | cut -c1-8)" >> "$O/start.txt"
  sleep 2
  tr '\0' '\n' < "/proc/$EPID/environ" | grep -E '^(MANGOHUD|KYTY_BC5_MANGOHUD|KYTY_BC5_OSD_FPS|KYTY_BC5_RT|KYTY_BC5_INPUT_CONFIG|DISABLE_MANGOHUD)' >> "$O/start.txt"
  sample() {  # <label>
    local p=$EPID gtt
    gtt=$(cat /sys/class/drm/card*/device/mem_info_gtt_used 2> /dev/null | head -1)
    echo "t $(( $(date +%s) - T0 )) $1: $(grep -E '^(VmRSS|VmHWM|Threads)' "/proc/$p/status" | tr -s ' \t' ' ' | tr '\n' ' ')" \
      "mangohud_threads $(cat /proc/$p/task/*/comm 2> /dev/null | grep -ci mango) [$(cat /proc/$p/task/*/comm 2> /dev/null | grep -i mango | sort | uniq -c | tr -s ' ' | tr '\n' ',')]" \
      "libMangoHud_mapped $(grep -c libMangoHud "/proc/$p/maps")" \
      "socket $(grep -c "@bc5-mangohud-$p" /proc/net/unix)" \
      "gtt_used_mib $(( ${gtt:-0} / 1048576 )) avail_mib $(awk '/^MemAvailable:/ {print int($2 / 1024)}' /proc/meminfo)"
  }
  set -- ${SAMPLES:-30 150 250}
  ENDED=""
  while [ $(( $(date +%s) - T0 )) -lt "$SECS" ]; do
    kill -0 "$EPID" 2> /dev/null || { ENDED="ended by itself at $(( $(date +%s) - T0 )) s"; break; }
    bad=$(sudo -n dmesg | tail -n +$((before + 1)) | grep -iE "amdgpu.*(fault|timeout|reset)|gpu reset|ring .* timeout")
    [ -n "$bad" ] && { ENDED="kernel line at $(( $(date +%s) - T0 )) s: $(echo "$bad" | head -1)"; break; }
    if [ $# -gt 0 ] && [ $(( $(date +%s) - T0 )) -ge "$1" ]; then sample "s$1" | tee -a "$O/samples.txt"; shift; fi
    sleep 3
  done
  sample end >> "$O/samples.txt" 2> /dev/null
  echo "cpu: utime+stime $(awk '{printf "%.1f s", ($14 + $15) / 100}' "/proc/$EPID/stat" 2> /dev/null) over $(( $(date +%s) - T0 )) s" >> "$O/samples.txt"
  J=$(ls -td ~/bc5-data/captures/play-*/gc 2> /dev/null | head -1)
  kill "$EPID" 2> /dev/null; sleep 4; kill -9 "$EPID" 2> /dev/null; EPID=""; sleep 3
  echo "$TAG ${ENDED:-stopped at $SECS s}" | tee "$O/end.txt"
  cp "$E/play-last.log" "$O/emu.log" 2> /dev/null
  grep -a -E "host menu:|MangoHud|mangohud|MANGOHUD" "$O/emu.log" | head -50 > "$O/menu-lines.txt"
  grep -a -m5 "Access violation\|Segmentation\|Aborted\|terminate called" "$O/emu.log" > "$O/crash.txt"
  cp "$E/input-0301.cfg" "$O/input-after.cfg"
  if [ "$FL" = normal ] && [ -n "$J" ] && [ "$(stat -c %Y "$J/direct.log" 2> /dev/null || echo 0)" -ge "$T0" ]; then
    echo "$J" > "$O/journal-dir.txt"
    LC_ALL=C nice -n 19 grep -a "^frame profile: t " "$J/direct.log" | gzip > "$O/frameprof.gz"
    echo "journal $J: $(stat -c %s "$J/direct.log") bytes, $(zcat "$O/frameprof.gz" | wc -l) frame-profile lines, $(grep -a -c TIMEOUT "$J/direct.log") TIMEOUT"
  fi
  sudo -n dmesg | awk -v up0="$UP0" '{ts = substr($0, 2, index($0, "]") - 2) + 0; if (ts >= up0) print}' > "$O/dmesg.txt"
  echo "kernel: $(grep -ci "amdgpu" "$O/dmesg.txt") amdgpu lines; crash lines $(grep -c . "$O/crash.txt")"
  cat "$O/samples.txt"; echo "== menu lines"; cat "$O/menu-lines.txt"
  S1=$(saves); echo "$(date '+%F %T') $TAG: live saves $S1" | tee -a "$O/saves.txt"
  [ "$S1" = "$S0" ] || echo "THE LIVE SAVES CHANGED: tell the top session"
  ;;
*) echo "usage: run0301.sh prep | build | run <tag> <normal|lean> <secs> [VAR=value ...]"; exit 2 ;;
esac
