#!/usr/bin/env bash
# BC5 experiment 0271 (exp 0266's driver, renamed): one lake-bench run (bench0271.sh; 26 frozen-view shots, no image
# dumps) on exp 0251's private binary (build0251.py, kept in ~/bc5-work/exp0251; BC5_EMU, the last value wins in the
# bench's env; not today's shared builds), with the draw-journal switches given as the second argument (the full-screen
# water draw alone, _EVERY, for the frame sizes over time). The depth and G-buffer reads are taken by capl0271.sh,
# started by hand while the run is attended. Conditions of the grant (top session, 2026-10-24 ~17:25, exp 0271): up to
# 3 runs, stopping at the first that shows both states or at any fault; before a run the queue (~/bc5-work/BOX-QUEUE) has
# reached us, no lock, no emulator, /var/home under 80 %; during it dmesg is polled every 3 s and the run is stopped on
# any new amdgpu fault/timeout/reset line. The live saves are never used by the bench (private copy); their checksum is
# taken before and after. After the run: the journal's summaries (jr0240.py, jr0245.py, db0250.py, cmp0245.py, wr0253.py).
# usage: ab0271.sh <tag> "<draw-journal switches>"   (on the box, from SSH; output in ~/bc5-work/exp0271/)
set -u
E=$HOME/bc5-work/exp0271
W=$HOME/bc5-work/exp0194
tag=$1
J=$2
export DUMPS=0 IMGS=0 SERIES=26
saves() { (cd ~/bc5-work/_SaveData && find PPSA03671 -type f -exec md5sum {} + | sort -k2 | md5sum | cut -c1-16); }
echo "$(date +%T) live saves checksum before: $(saves)"
L=$(cat ~/bc5-work/BOX-LOCK 2>/dev/null)
[ -n "$L" ] && { echo "$tag: box locked, stopping: $L"; exit 1; }
pgrep -x kyty_emulator > /dev/null && { echo "$tag: an emulator is running"; exit 1; }
use=$(df --output=pcent /var/home | tail -1 | tr -dc 0-9)
[ "$use" -ge 80 ] && { echo "$tag: /var/home at $use %, stopping"; exit 1; }
[ -e "$W/r-$tag" ] && { echo "$tag: tag used"; exit 1; }
before=$(sudo -n dmesg | wc -l)
echo "$(date +%T) $tag start: /var/home $use %, dmesg $before lines; journal switches: $J"
ENVX="KYTY_BC5_AMM_TRACE=1 $J BC5_EMU=$HOME/bc5-work/exp0251/kyty_emulator" "$E/bench0271.sh" "$tag" 360 > "$E/$tag.bench.txt" 2>&1 &
BP=$!
bad=""
while kill -0 "$BP" 2>/dev/null || pgrep -x kyty_emulator > /dev/null; do
  bad=$(sudo -n dmesg | tail -n +$((before + 1)) | grep -iE "amdgpu.*(fault|timeout|reset)|gpu reset|ring .* timeout")
  if [ -n "$bad" ]; then
    echo "$(date +%T) $tag: new kernel lines, stopping the run:"; echo "$bad" | head -5
    ep=$(pgrep -n -x kyty_emulator); [ -n "$ep" ] && kill "$ep"
    break
  fi
  sleep 3
done
wait "$BP" 2>/dev/null
for _ in $(seq 1 20); do [ -f "$W/r-$tag/journal-dir.txt" ] && break; sleep 3; done
for _ in $(seq 1 6); do grep -q "exp 0271 | bench $tag " ~/bc5-work/BOX-LOCK 2>/dev/null || break; sleep 5; done
grep -a "patch\|timed out\|ended early" "$E/$tag.bench.txt" | sed "s/^/  /"
jd=$(cat "$W/r-$tag/journal-dir.txt" 2>/dev/null)
if [ -n "$jd" ]; then
  echo "  journal: direct.log $(du -h "$jd/direct.log" | cut -f1), $(grep -ac '^draw journal buf' "$jd/direct.log") draw-journal lines ($(grep -a '^draw journal buf' "$jd/direct.log" | wc -c) bytes), $(grep -ac '^draw journal find' "$jd/direct.log") find lines"
  nice -n 10 python3 -I "$HOME/bc5-work/exp0240/jr0240.py" "$jd/direct.log" > "$E/$tag.jr.txt" 2>&1
  nice -n 10 python3 -I "$HOME/bc5-work/exp0245/jr0245.py" "$jd/direct.log" "$HOME/bc5-work/exp0245/gfx10.json" > "$E/$tag.db.txt" 2>&1
  nice -n 10 python3 -I "$HOME/bc5-work/exp0250/db0250.py" "$jd/direct.log" "$HOME/bc5-work/exp0245/gfx10.json" > "$E/$tag.surf.txt" 2>&1
  nice -n 10 python3 -I "$E/cmp0245.py" "$jd/direct.log" "$E/$tag.bench.txt" > "$E/$tag.cmp.txt" 2>&1
  nice -n 10 python3 -I "$E/wr0253.py" "$jd/direct.log" "$E/$tag.bench.txt" 11d01d7100 > "$E/$tag.wr.txt" 2>&1
  grep -a "^depth pool\|^draw journal window\|^draw journal find" "$jd/direct.log" | cut -c1-400 > "$E/$tag.pool.txt"
  echo "  depth pool: $(grep -ac '^depth pool dma_data' "$jd/direct.log") dma_data and $(grep -ac '^depth pool write_data' "$jd/direct.log") write_data lines into the depth memory, $(grep -ac '^draw journal find' "$jd/direct.log") find lines, $(grep -ac '^draw journal window' "$jd/direct.log") windows"
fi
echo "  written: run dir $(du -sh "$W/r-$tag" | cut -f1), journal dir $(du -sh "$jd" 2>/dev/null | cut -f1), emu.log $(du -sh "$W/r-$tag/emu.log" 2>/dev/null | cut -f1)"
echo "$(date +%T) live saves checksum after: $(saves); /var/home $(df --output=pcent /var/home | tail -1 | tr -d ' ')"
# On a fault, the newest GPU coredumps the maintainer's udev rule saved (CLAUDE.md, since 2026-10-24 17:15).
[ -n "$bad" ] && { echo "  devcoredumps (newest): $(ls -t ~/bc5-data/captures/devcoredump/ 2>/dev/null | head -3 | tr '
' ' ')"; exit 1; }
echo "$(date +%T) done"
