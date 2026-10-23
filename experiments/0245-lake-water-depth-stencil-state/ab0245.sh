#!/usr/bin/env bash
# BC5 experiment 0245 (exp 0244's driver, renamed): one lake-bench run (bench0245.sh, exp 0235's bench renamed;
# one series of 26 frozen-view shots, no image dumps) with the title's AMM/APR requests traced (KYTY_BC5_AMM_TRACE=1)
# and the draw-journal switches given as the second argument (the pixel-shader filter on the water's full-screen draw, its main draws
# and the linear-depth writer, every 15 s). Its default exp 0194
# build, comm "kyty_emulator"; the bench's own launcher copy keeps the old values: no PRT, old skip list. Conditions of
# the grant (top session, 2026-10-23 ~20:10 for the ~20:35 slot, as for exp 0244; at most 2 runs, the second only if the first lands in a menu): before the run no lock, no
# emulator, the same boot and /var/home under 80 %; during it dmesg is polled every 3 s and the run is stopped on any
# new amdgpu fault/timeout/reset line. The live saves are never used by the bench (private copy); their checksum is
# taken before and after. After the run: the journal's size and jr0240.py's summary (exp 0240's script) of it.
# The binary is build0245.py's private kyty_emulator (BC5_EMU, the last value wins in the bench's env).
# usage: ab0245.sh <tag> "<draw-journal switches>"   (on the box, from SSH; output in ~/bc5-work/exp0245/)
set -u
E=$HOME/bc5-work/exp0245
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
ENVX="KYTY_BC5_AMM_TRACE=1 $J BC5_EMU=$E/kyty_emulator" "$E/bench0245.sh" "$tag" 360 > "$E/$tag.bench.txt" 2>&1 &
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
for _ in $(seq 1 6); do grep -q "exp 0245 | bench $tag " ~/bc5-work/BOX-LOCK 2>/dev/null || break; sleep 5; done
grep -a "patch\|timed out\|ended early" "$E/$tag.bench.txt" | sed "s/^/  /"
jd=$(cat "$W/r-$tag/journal-dir.txt" 2>/dev/null)
if [ -n "$jd" ]; then
  echo "  journal: direct.log $(du -h "$jd/direct.log" | cut -f1), $(grep -ac '^draw journal buf' "$jd/direct.log") draw-journal lines ($(grep -a '^draw journal buf' "$jd/direct.log" | wc -c) bytes), $(grep -ac '^draw journal find' "$jd/direct.log") find lines"
  nice -n 10 python3 -I "$HOME/bc5-work/exp0240/jr0240.py" "$jd/direct.log" > "$E/$tag.jr.txt" 2>&1
  nice -n 10 python3 -I "$E/jr0245.py" "$jd/direct.log" "$E/gfx10.json" > "$E/$tag.db.txt" 2>&1
fi
echo "  written: run dir $(du -sh "$W/r-$tag" | cut -f1), journal dir $(du -sh "$jd" 2>/dev/null | cut -f1), emu.log $(du -sh "$W/r-$tag/emu.log" 2>/dev/null | cut -f1)"
echo "$(date +%T) live saves checksum after: $(saves); /var/home $(df --output=pcent /var/home | tail -1 | tr -d ' ')"
[ -n "$bad" ] && exit 1
echo "$(date +%T) done"
