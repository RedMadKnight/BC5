#!/usr/bin/env bash
# BC5 (experiment 0037): a poor man's profiler for the emulator's named threads. From START
# seconds after the emulator appears, every GAP seconds, attaches gdb for a moment and records the
# backtrace of each thread in NAMES. Run inside the ubuntu distrobox. Output: $OUT.
# usage: pc-sampler.sh START COUNT GAP OUT NAME[,NAME...]
set -u
START=$1; COUNT=$2; GAP=$3; OUT=$4; shift 4
: > "$OUT"
for _ in $(seq 1 300); do PID=$(pgrep -x kyty_emulator | head -1); [ -n "$PID" ] && break; sleep 1; done
[ -z "${PID:-}" ] && { echo "no emulator" >> "$OUT"; exit 1; }
sleep "$START"
PY="import gdb
names = set('$*'.split(','))
for t in gdb.selected_inferior().threads():
    if t.name in names:
        t.switch()
        f = gdb.newest_frame()
        out = []
        i = 0
        while f is not None and i < 8:
            out.append('%x %s' % (f.pc(), f.name() or '?'))
            f = f.older(); i += 1
        print('T', t.name, ' | '.join(out))
"
for i in $(seq 1 "$COUNT"); do
  kill -0 "$PID" 2>/dev/null || break
  echo "== sample $i $(date +%T)" >> "$OUT"
  gdb -q -batch -p "$PID" -ex "set pagination off" -ex "python
$PY" >> "$OUT" 2>/dev/null
  sleep "$GAP"
done
