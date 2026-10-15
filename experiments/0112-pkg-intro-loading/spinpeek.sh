#!/usr/bin/env bash
# BC5 run 413 helper: during the logo, the code around the render thread spin and the registers of
# every thread, from the live process (private, stdout only). usage: spinpeek.sh START COUNT GAP OUT
START=$1; COUNT=$2; GAP=$3; OUT=$4
: > "$OUT"
for _ in $(seq 1 300); do PID=$(pgrep -x kyty_emulator | head -1); [ -n "$PID" ] && break; sleep 1; done
sleep "$START"
for i in $(seq 1 "$COUNT"); do
  echo "== peek $i up $(cut -d" " -f1 /proc/uptime)" >> "$OUT"
  gdb -q -batch -p "$PID" -ex "set pagination off" -ex "set debuginfod enabled off" \
    -ex "x/70i 0x903f37900" \
    -ex "thread apply all info registers rip rax rbx rcx rdx rsi rdi rbp rsp r8 r9 r10 r11 r12 r13 r14 r15" 2>/dev/null \
    | grep -E "^=> |^   0x|^Thread |^r[a-z0-9]+ +0x" >> "$OUT"
  sleep "$GAP"
done
