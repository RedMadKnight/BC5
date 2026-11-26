#!/usr/bin/env bash
# BC5 (experiment 0189): the raw/ files from the run directories ~/bc5-work/exp0189/r-<tag> (run-0189.sh).
# Nothing from the title's binaries (no shader code or disassembly), register values and counts only.
# usage: summarize.sh <out dir>
OUT=$1; mkdir -p "$OUT"; cd ~/bc5-work/exp0189 || exit 1
{
for d in r-R*/ r-S*/; do
  t=${d#r-}; t=${t%/}
  echo "== $t: $(cat "$d/env.txt")"
  awk '/page fault/ {n++; if (!f) f = substr($0, 2, index($0, "]") - 2) + 0} /Faulty UTCL2 client ID/ {sub(/.*client ID: /, ""); c[$0]++}
       /in page starting at address/ {for (i = 1; i <= NF; i++) if ($i == "address") a[$(i + 1)]++}
       END {printf "kernel: %d page-fault records, %d pages", n, length(a); for (k in c) printf ", client %s x%d", k, c[k]; printf "\n"}' "$d/dmesg.txt"
  echo "kernel: $(grep -c -i "ring .*timeout" "$d/dmesg.txt") ring timeouts, $(grep -c -i "reset succeeded" "$d/dmesg.txt") ring resets"
  echo "journal: $(grep -c -a "TIMEOUT" "$d/journal-excerpt.txt") fence timeouts"
  grep -a "TIMEOUT" "$d/journal-excerpt.txt" | sed 's/ at 0x[0-9a-f]*//' | cut -c1-150
  echo -n "flips per 10 s: "; grep -a "^frame profile: t " "$d/journal-excerpt.txt" | awk '{t = $4 + 0; n[int(t / 10)]++} END {for (k in n) printf "%d:%d\n", k * 10, n[k]}' | sort -n | tr '\n' ' '; echo
  grep -a "/dev/gc TF ring\|/dev/gc HS offchip" "$d/emu.log" | head -2
  grep -a "^tf ring" "$d/journal-excerpt.txt" | head -1
  grep -a "timeout probe: TF ring" "$d/journal-excerpt.txt" | cut -c1-200 | head -1
  [ -f "$d/../r-$t-stall.out" ] && echo "wave dump at a 0.7-s journal stall: $(cat "$d/../r-$t-stall.out")"
  echo
done
} > "$OUT/runs.txt"
grep -a "^\[bc5-gc-trace\]" r-R0/emu.log > "$OUT/R0-ioctl-trace.txt"
grep -a "^reg census" r-R0/emu.log > "$OUT/R0-census.txt"
for t in R7 R8; do grep -a "^reg census" r-$t/emu.log | awk '/buffers,/ {b = NR} {l[NR] = $0} END {for (i = b; i <= NR; i++) print l[i]}' > "$OUT/$t-census-last.txt"; done
grep -a "page fault\|in page starting\|client ID" r-R0/dmesg.txt | head -60 > "$OUT/R0-dmesg-first.txt"
J=$(grep -o "/home[^ ]*direct.log" r-R3/launcher.out 2>/dev/null | head -1)
grep -a "timeout probe: TF ring\|timeout probe:   state before op 27\|timeout probe:   state before op 15.*11d04bb9" r-R3/journal-excerpt.txt ../../bc5-data/captures/play-20261021-1818/gc/direct.log 2>/dev/null | sed 's/^[^:]*direct.log://' | cut -c1-420 > "$OUT/R3-timeout-probe.txt"
grep -a "timeout probe:   state before op 15.*11d04bb9" ../../bc5-data/captures/play-20261021-1834/gc/direct.log | cut -c1-420 > "$OUT/R6-traversal-dispatch.txt"
sed -n '/^Ring timed out details/,/^num_mec/p' r-R3/devcoredump.txt | grep -v "^$" > "$OUT/R3-devcoredump-gfx.txt"
for spec in R6:0x11d04bb900 S1:0x11d040e200 S3:0x11d04a6000; do
  t=${spec%%:*}; base=${spec#*:}
  python3 -I - waves-$t.txt "$base" "$t" > "$OUT/$t-waves.txt" <<'PY'
import re, sys, collections
txt = open(sys.argv[1], errors="replace").read(); base = int(sys.argv[2], 16)
c = collections.Counter()
for w in re.split(r"-{20,}\n", txt):
    m = re.search(r"ixSQ_WAVE_PC_LO: ([0-9a-f]+) \|\s+ixSQ_WAVE_PC_HI: ([0-9a-f]+)", w)
    if not m: continue
    pc = int(m.group(2), 16) << 32 | int(m.group(1), 16)
    st = re.search(r"ixSQ_WAVE_STATUS: ([0-9a-f]+)", w).group(1)
    ex = re.search(r"ixSQ_WAVE_EXEC_LO: ([0-9a-f]+)", w).group(1)
    c[(hex(pc), "+0x%x of %s" % (pc - base, sys.argv[2]), "STATUS " + st, "EXEC_LO " + ex)] += 1
print("umr -O halt_waves -wa gfx_0.0.0, 0.7 s into the stall of run %s: waves by PC" % sys.argv[3])
for k, n in c.most_common(): print(n, *k)
print(sum(c.values()), "waves")
PY
done
grep -a "timeout probe:   state before op 16.*cs 0000000011d049aa" ../../bc5-data/captures/play-20261021-1947/gc/direct.log | cut -c1-420 > "$OUT/S2-traversal-dispatch.txt"
ls -la "$OUT"
