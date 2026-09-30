#!/usr/bin/env bash
# BC5: run ASTRO BOT in KytyPlus (LLE libSceAgc, soft CP) under gdb, interrupt after $RUN_SECONDS and
# dump every thread's backtrace. Run inside the ubuntu distrobox.
set -u
C=~/bc5-data/games/"PPSA21567 - ASTRO BOT_4xx.ffpfsc"
M=~/bc5-data/mnt/PPSA21567
CAP=~/bc5-data/captures/kytyplus-gdb-$(date +%Y%m%d-%H%M)
RUN=${RUN_SECONDS:-40}
mkdir -p "$M" "$CAP/gc"
BM=~/bc5-work/bc5-tools-ubuntu/release/bc5-mount
mountpoint -q "$M" || { "$BM" mount "$C" "$M" > "$CAP/bc5-mount.log" 2>&1 & MP=$!; trap "fusermount3 -u \"$M\" 2>/dev/null; wait $MP 2>/dev/null" EXIT; }
for _ in $(seq 1 100); do mountpoint -q "$M" && break; sleep 0.2; done
mountpoint -q "$M" || { echo "mount failed"; exit 1; }
export XDG_RUNTIME_DIR=/run/user/$(id -u) WAYLAND_DISPLAY=wayland-0 SDL_VIDEODRIVER=wayland
export SHADPS4_SYSMODULES_PACK_DIR="$M/fakelib" KYTY_GUEST_MEMORY_MB=13824 BC5_GC_DUMP_DIR="$CAP/gc"
cd "$CAP"
timeout -s INT --kill-after=30 "$RUN" gdb -q -batch \
  -ex "set pagination off" -ex "set confirm off" -ex "handle SIGSEGV nostop noprint pass" -ex "handle SIGUSR1 nostop noprint pass" -ex "handle SIGUSR2 nostop noprint pass" \
  -ex run -ex "info threads" -ex "thread apply all bt 14" \
  --args ~/bc5-work/kytyplus-build/src/kyty_emulator --game "$M" --printf-direction File --printf-output-file "$CAP/guest-printf.txt" > "$CAP/gdb.log" 2>&1
echo "gdb exit $?; log lines $(wc -l < "$CAP/gdb.log")"
echo "$CAP" > ~/bc5-work/last-gdb
