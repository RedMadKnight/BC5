#!/usr/bin/env bash
# BC5 exp 0412: where the game's threads spend their time (the maintainer, 2026-11-11: "Czemu gra poswieca tyle czasu na
# obliczenia? Nasze biblioteki sa slabo napisane?"). A wall-clock stack sampler that needs no perf and no root: every
# <step> s it takes one eu-stack snapshot of each named thread of the emulator (eu-stack -1 -p <tid>: only that thread is
# attached and stopped, for some milliseconds; never bc5-ring or another bc5-* thread, see README section 10), and writes
# beside it that thread's user and system ticks, its context switches and its run-queue wait (/proc/<pid>/task/<tid>/stat,
# status, schedstat) and the process's I/O counters (/proc/<pid>/io: rchar, syscr, read_bytes, wchar, syscw).
# A sample of a blocked thread shows what it waits in, a sample of a running one what it computes: the share of samples
# per call path is the share of the thread's wall-clock time.
# Run INSIDE the ubuntu container (eu-stack is there): distrobox enter ubuntu -- bash prof0412.sh ...
# usage: prof0412.sh <out file> <step s, e.g. 0.5> <from s> <to s> <thread name> [<thread name> ...]
set -u
export LC_ALL=C
OUT=${1:?out}; STEP=${2:?step}; FROM=${3:?from}; TO=${4:?to}; shift 4
[ "$#" -ge 1 ] || { echo "thread names, please"; exit 1; }
for n in "$@"; do case "$n" in bc5-*) echo "not a bc5-* thread: $n"; exit 1 ;; esac; done
EP=""
for _ in $(seq 1 90); do EP=$(pgrep -o '^kyty_emulator') && break; sleep 2; done
[ -n "$EP" ] || { echo "# no emulator in 180 s" >> "$OUT"; exit 0; }
T0=$(stat -c %Y "/proc/$EP")
echo "# $(date '+%F %T') emulator $EP $(readlink "/proc/$EP/exe"); threads: $*; every $STEP s from $FROM to $TO s; HZ $(getconf CLK_TCK)" >> "$OUT"
# A thread is named as the sampler prints it: its comm with spaces as underscores ("Render_Thread" is comm "Render Thread").
tid_of() { local t c; for t in /proc/"$EP"/task/*; do c=$(cat "$t/comm" 2> /dev/null); [ "${c// /_}" = "$1" ] && { basename "$t"; return; }; done; }
while [ -d "/proc/$EP" ]; do
  now=$(($(date +%s) - T0))
  [ "$now" -ge "$TO" ] && break
  if [ "$now" -lt "$FROM" ]; then sleep 1; continue; fi
  io=$(tr '\n' ' ' < "/proc/$EP/io" 2> /dev/null)
  for n in "$@"; do
    tid=$(tid_of "$n"); [ -n "$tid" ] || continue
    st=$(awk '{ j = match($0, /\) [A-Za-z] /); split(substr($0, j + 2), a, " "); print a[1], a[12], a[13], a[8], a[10] }' "/proc/$EP/task/$tid/stat" 2> /dev/null)
    cs=$(awk '/ctxt_switches/ { printf "%s ", $2 }' "/proc/$EP/task/$tid/status" 2> /dev/null)
    ss=$(cat "/proc/$EP/task/$tid/schedstat" 2> /dev/null)
    echo "== t $(date +%s.%N | cut -c1-14) rel $now $n tid $tid | state utime stime minflt majflt: $st | ctxsw vol invol: $cs| schedstat run_ns wait_ns slices: $ss | io: $io" >> "$OUT"
    timeout 5 env -u DEBUGINFOD_URLS eu-stack -1 -p "$tid" 2> /dev/null | grep '^#' | head -24 | cut -c1-200 >> "$OUT"
  done
  sleep "$STEP"
done
echo "# $(date '+%F %T') end" >> "$OUT"
