#!/usr/bin/env bash
# BC5 (experiment 0177): one 90-s start of the second title (intro and start screen, no input) with
# the normal (0) or the lean (1) emulator. From outside the emulator, read-only: the GPU's clock and
# activity every 2 s from t 50 s (sysfs gpu_metrics), one screenshot at ~74 s, the process's memory
# and thread count at the end. The normal run's frame counter is printed for t 55-82 s; the lean
# build has none. usage: lean-check.sh <tag> <0|1> [emulator binary]
TAG=$1; LEAN=$2
cd ~/bc5-work
pgrep -x kyty_emulator >/dev/null && { echo busy; exit 1; }
LOGF=play-pkg-last.log; [ "$LEAN" = 1 ] && LOGF=play-pkg-lean-last.log
setsid nohup distrobox enter ubuntu -- env BC5_LEAN="$LEAN" BC5_EMU="${3:-}" KYTY_BC5_INPUT_CMD=/dev/null ~/bc5-work/play-pkg.sh < /dev/null > ~/bc5-work/lc-$TAG.out 2>&1 &
for _ in $(seq 1 60); do pgrep -x kyty_emulator >/dev/null && break; sleep 1; done
PID=$(pgrep -x kyty_emulator | head -1)
sleep 50
: > lc-$TAG.clk
for i in $(seq 1 18); do
  python3 -I -c '
import struct
b = open("/sys/class/drm/card1/device/gpu_metrics", "rb").read()
u = struct.unpack_from("<62H", b, 4)
print(u[12], u[30], u[36])' >> lc-$TAG.clk
  [ "$i" = 12 ] && SHOTS=0177 ~/bc5-work/shot.sh lc-$TAG 0 > /dev/null 2>&1
  sleep 2
done
ALIVE=no; kill -0 "$PID" 2>/dev/null && ALIVE=yes
MEM=$(ps -o rss=,nlwp= -p "$PID" 2>/dev/null)
cp "$LOGF" lc-$TAG.log
pkill -x kyty_emulator; sleep 4; pkill -9 -x kyty_emulator; sleep 3
awk -v tag="$TAG" -v alive="$ALIVE" -v mem="$MEM" '{n++; a+=$1/100; if ($2 < 65535) {c+=$2; m++}} END {split(mem, x, " "); printf "%-14s alive at 86 s: %s; GPU activity %.0f %%, average clock %.0f MHz; RSS %.1f GB, %d threads\n", tag, alive, a/n, (m ? c/m : 0), x[1]/1048576, x[2]}' lc-$TAG.clk
grep -a "^fps counter" lc-$TAG.log | awk '{t=$4+0; if (t<55||t>=82) next; n++; s+=$6/$9; match($0,/longest gap ([0-9.]+)/,g); if (g[1]+0>mx) mx=g[1]+0} END{if (n) printf "               frame counter: %.1f flips/s over %d s, longest gap %.0f ms\n", s/n, n, mx}'
printf "               log: %s lines, %s bytes\n" "$(wc -l < lc-$TAG.log)" "$(wc -c < lc-$TAG.log)"
