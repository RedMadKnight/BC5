#!/usr/bin/env bash
# exp 0446 (tag thr446, 2026-11-26): per-thread CPU time of the running emulator, read from /proc every THR_S seconds
# (default 5) without touching the process (no ptrace, no signal): one line per sample per thread,
#   <seconds since the emulator's start> <tid> <comm> <utime ticks> <stime ticks>
# Waits up to 10 min for a kyty_emulator to appear, then samples until it exits.   thr446.sh <out file>
set -u
OUT=${1:?out}; S=${THR_S:-5}; TCK=$(getconf CLK_TCK)
t0=$(date +%s); pid=""
while [ -z "$pid" ] && [ $(( $(date +%s) - t0 )) -lt 600 ]; do pid=$(pgrep -x kyty_emulator | head -1); [ -z "$pid" ] && sleep 1; done
[ -n "$pid" ] || { echo "no emulator in 10 min" > "$OUT"; exit 1; }
start=$(date +%s.%N)
echo "# pid $pid, clock ticks $TCK/s, sample every $S s; el tid comm utime stime" > "$OUT"
while [ -d "/proc/$pid" ]; do
    el=$(echo "$(date +%s.%N) - $start" | bc)
    for t in /proc/$pid/task/*; do
        [ -r "$t/stat" ] || continue
        # comm may hold spaces: take the fields after the closing parenthesis
        s=$(cat "$t/stat" 2> /dev/null) || continue
        c=${s#*(}; c=${c%)*}; r=${s##*) }
        set -- $r
        echo "${el%.*} ${t##*/} ${c// /_} ${12} ${13}"
    done >> "$OUT"
    sleep "$S"
done
