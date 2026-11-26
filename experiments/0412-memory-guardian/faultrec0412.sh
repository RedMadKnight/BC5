#!/usr/bin/env bash
# BC5 exp 0412 (tag fr412, README sections 64-65): the launcher's step after a run. The emulator's fault record
# (BC5_FAULT_RECORD: ~/bc5-data/captures/faults/<date-time>/, exit code 86) lacks what the emulator cannot read:
# the kernel's own lines, the devcoredump, the binary's sum. This adds them to every record written since the run
# began that is not complete yet:
#   dmesg.txt    the kernel log since the run began (whole), and dmesg-gpu.txt: its amdgpu, drm and fault lines
#   build.txt    the binary's path, md5 and time; the kernel, Mesa and libdrm versions; the devcoredump's path
#                (the maintainer's udev rule copies it to ~/bc5-data/captures/devcoredump within seconds: waited
#                for, 20 s at most); the kernel's verdict in one line (page fault, timeout, reset succeeded/failed)
# Reads only; writes only into the record directories. Nothing here is read by a later run. No waiter is left:
# the script ends by itself after 20 s at most.
# usage: faultrec0412.sh <run's start, epoch seconds> <the emulator binary> [<dmesg's line count at the start>]
set -u
export LC_ALL=C LANGUAGE=C
T0=${1:?start}; BIN=${2:?binary}; ND0=${3:-}
case "$T0" in *[!0-9]* | "") echo "the start is epoch seconds"; exit 1 ;; esac
F=$HOME/bc5-data/captures/faults; DC=$HOME/bc5-data/captures/devcoredump
[ -d "$F" ] || { echo "no fault record directory: no record was written"; exit 0; }
n=0
for d in "$F"/*/; do
  d=${d%/}; [ -f "$d/record.txt" ] && [ ! -e "$d/build.txt" ] || continue
  [ "$(stat -c %Y "$d/record.txt")" -ge "$T0" ] || continue
  n=$((n + 1))
  if [ -n "$ND0" ]; then sudo -n dmesg 2> /dev/null | tail -n +"$((ND0 + 1))" > "$d/dmesg.txt"
  else sudo -n dmesg --since "@$T0" > "$d/dmesg.txt" 2> /dev/null || sudo -n dmesg 2> /dev/null | tail -n 400 > "$d/dmesg.txt"; fi
  # the reset and the devcoredump come some seconds after the fault: wait for a copied dump, 20 s at most
  dump=""
  for _ in $(seq 1 20); do
    dump=$(find "$DC" -maxdepth 1 -type f -newermt "@$T0" 2> /dev/null | sort | tail -1)
    [ -n "$dump" ] && break
    sleep 1
  done
  if [ -n "$ND0" ]; then sudo -n dmesg 2> /dev/null | tail -n +"$((ND0 + 1))" > "$d/dmesg.txt"
  else sudo -n dmesg --since "@$T0" > "$d/dmesg.txt" 2> /dev/null || true; fi
  grep -iE "amdgpu|\[drm|page fault|GCVM|PERMISSION_FAULTS|ring .* timeout|reset|bc5-gpu-watch|devcoredump|Out of memory|oom" "$d/dmesg.txt" > "$d/dmesg-gpu.txt"
  v=""
  grep -qi "page fault" "$d/dmesg-gpu.txt" && v="a page fault"
  grep -qiE "ring .* timeout" "$d/dmesg-gpu.txt" && v="$v, a ring timeout"
  grep -qiE "reset.*succeeded" "$d/dmesg-gpu.txt" && v="$v, reset succeeded"
  grep -qiE "reset failed|reset.*fail" "$d/dmesg-gpu.txt" && v="$v, RESET FAILED"
  v=${v#, }; [ -n "$v" ] || v="no amdgpu fault or timeout line in the kernel log"
  {
    echo "added by faultrec0412.sh at $(date '+%F %T') (the launcher's step; the emulator cannot read these)"
    echo "binary: $BIN"
    echo "binary md5: $(md5sum < "$BIN" 2> /dev/null | cut -d' ' -f1)"
    echo "binary time: $(stat -c %y "$BIN" 2> /dev/null)"
    echo "kernel: $(uname -r)"
    echo "mesa: $(rpm -q --qf '%{VERSION}-%{RELEASE}' mesa-vulkan-drivers 2> /dev/null || echo unknown)"
    echo "libdrm: $(rpm -q --qf '%{VERSION}-%{RELEASE}' libdrm 2> /dev/null || echo unknown)"
    echo "the kernel's words (dmesg-gpu.txt, $(grep -c . "$d/dmesg-gpu.txt") lines): $v"
    grep -iE "page fault|in page starting at|GCVM_L2_PROTECTION_FAULT_STATUS|MORE_FAULTS|PERMISSION_FAULTS|RW:|Faulty UTCL2 client" "$d/dmesg-gpu.txt" | head -12 | sed 's/^/  /'
    echo "devcoredump: ${dump:-none copied within 20 s of this step}"
  } > "$d/build.txt"
  echo "completed $d: $v; devcoredump ${dump:-none}"
done
[ "$n" != 0 ] || echo "no fault record since the run began"
