#!/usr/bin/env bash
# BC5 exp 0412: which mappings of the emulator grow (the ASTRO BOT host leak, 217 MiB/min of anonymous memory; the top
# session's order of 2026-11-11 01:10). Read-only: every <step> s it reads /proc/<pid>/smaps, /proc/<pid>/status and the
# fd directory of the first emulator process and writes, per sample, the totals by class and every mapping whose
# resident + swapped memory is 8 MiB or more (address range, permissions, name, size, Rss, Swap, Anonymous, all in MiB).
# Classes: heap ([heap]), anon (no name, private), memfd (a /memfd: name), stack, file (a path), other.
# It waits up to 120 s for the emulator and ends with it. No ptrace, nothing written outside <out file>.
# usage (host): smaps0412.sh <out file> [step s, default 30]
set -u
export LC_ALL=C
OUT=${1:?the out file}; STEP=${2:-30}
EP=""
for _ in $(seq 1 60); do EP=$(pgrep -o '^kyty_emulator') && break; sleep 2; done
[ -n "$EP" ] || { echo "# no emulator in 120 s" >> "$OUT"; exit 0; }
T0=$(date +%s)
echo "# $(date '+%F %T') emulator $EP $(readlink "/proc/$EP/exe"); every $STEP s" >> "$OUT"
while [ -d "/proc/$EP" ]; do
  t=$(($(date +%s) - T0))
  th=$(awk '/^Threads:/ { print $2 }' "/proc/$EP/status" 2> /dev/null); fds=$(ls "/proc/$EP/fd" 2> /dev/null | wc -l)
  an=$(awk '/^RssAnon:/ { a = $2 } /^VmSwap:/ { s = $2 } /^VmData:/ { d = $2 } END { printf "rssanon %d swap %d vmdata %d", a / 1024, s / 1024, d / 1024 }' "/proc/$EP/status" 2> /dev/null)
  echo "== t $t s: threads ${th:-?}, fds $fds, $an MiB, maps $(wc -l < "/proc/$EP/maps" 2> /dev/null)" >> "$OUT"
  awk '
    function flush() {
      if (range == "") return
      cls = "other"
      if (name == "[heap]") cls = "heap"; else if (name ~ /^\[stack/) cls = "stack"; else if (name ~ /memfd:/) cls = "memfd"
      else if (name == "" ) cls = "anon"; else if (name ~ /^\//) cls = "file"
      n[cls]++; sz[cls] += size; rs[cls] += rss; sw[cls] += swap; an[cls] += anon
      if (rss + swap >= 8192) printf "map %s %s %s size %d rss %d swap %d anon %d\n", range, perms, (name == "" ? "-" : name), size / 1024, rss / 1024, swap / 1024, anon / 1024
    }
    /^[0-9a-f]+-[0-9a-f]+ / { flush(); range = $1; perms = $2; name = ""; for (i = 6; i <= NF; i++) name = name (i > 6 ? " " : "") $i; size = rss = swap = anon = 0; next }
    /^Size:/ { size = $2 } /^Rss:/ { rss = $2 } /^Swap:/ { swap = $2 } /^Anonymous:/ { anon = $2 }
    END { flush(); for (c in n) printf "class %s: %d maps, size %d rss %d swap %d anon %d\n", c, n[c], sz[c] / 1024, rs[c] / 1024, sw[c] / 1024, an[c] / 1024 }
  ' "/proc/$EP/smaps" 2> /dev/null >> "$OUT"
  sleep "$STEP"
done
echo "# $(date '+%F %T') emulator $EP ended" >> "$OUT"
