#!/usr/bin/env bash
# BC5 exp 0433, the mechanism probe (top, 2026-11-19 06:4x): beside one fight run, per-thread context switches at two
# points and a 60 s perf count of futex calls and context switches. Read-only on the emulator (no ptrace).
#   probe0433.sh <out prefix> [t_a s] [t_b s]   t from the emulator's start (default 227 = G+120, 395 = G+288 at G 107)
# Waits up to 180 s for an emulator to appear (by process name, pgrep '^kyty_emulator', never a command-line pattern).
set -u
export LC_ALL=C
OUT=$1; TA=${2:-227}; TB=${3:-395}
for _ in $(seq 1 360); do P=$(pgrep -o '^kyty_emulator') && break; sleep 0.5; done
[ -n "${P:-}" ] || { echo "no emulator in 180 s" > "$OUT-probe.err"; exit 1; }
T0=$(awk '{print $22}' "/proc/$P/stat"); HZ=$(getconf CLK_TCK); UP0=$(awk '{print int($1)}' /proc/uptime)
age() { echo $(( $(awk '{print int($1)}' /proc/uptime) - T0 / HZ )); }
snap() {  # tid comm voluntary nonvoluntary
  for d in /proc/"$P"/task/*; do
    printf '%s %s %s %s\n' "${d##*/}" "$(tr ' ' '_' < "$d/comm" 2> /dev/null)" \
      "$(awk '/^voluntary_ctxt_switches/ {print $2}' "$d/status" 2> /dev/null)" \
      "$(awk '/^nonvoluntary_ctxt_switches/ {print $2}' "$d/status" 2> /dev/null)"
  done > "$1"
  echo "# pid $P age $(age) s at $(date +%T)" >> "$1"
}
waitage() { while [ -d "/proc/$P" ] && [ "$(age)" -lt "$1" ]; do sleep 1; done; [ -d "/proc/$P" ]; }
echo "pid $P, started at uptime $((T0 / HZ)) s (probe started at uptime $UP0 s)" > "$OUT-probe.txt"
waitage "$TA" || { echo "emulator gone before $TA s" >> "$OUT-probe.txt"; exit 1; }
snap "$OUT-ctx-a.txt"
distrobox enter ubuntu -- sudo -n perf stat -e 'syscalls:sys_enter_futex,context-switches,cpu-migrations' -p "$P" -- sleep 60 \
  > "$OUT-perf.txt" 2>&1 < /dev/null
echo "perf rc $? at age $(age) s" >> "$OUT-probe.txt"
waitage "$TB" || { echo "emulator gone before $TB s" >> "$OUT-probe.txt"; exit 1; }
snap "$OUT-ctx-b.txt"
echo "done at age $(age) s" >> "$OUT-probe.txt"
