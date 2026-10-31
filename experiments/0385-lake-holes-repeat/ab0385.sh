#!/usr/bin/env bash
# BC5 experiment 0385: exp 0369's ab0369.sh with 0369 -> 0385, the box-side cap and the C-locale saves sum added (mkkit0385.py). Older comments below keep their wording.
# BC5 experiment 0385, run K2: exp 0365's ab0365.sh (RT ON), paths and lock text 0385.
# BC5 experiment 0385: exp 0362's ab0362.sh (RT ON), paths and lock text 0385.
# BC5 experiment 0312 (exp 0311's ab0311.sh): one lake-bench run (bench0385.sh) with the given switches,
# attended. Before: no lock but ours, no emulator, /var/home under 80 %, the tag unused, the live saves at the given
# checksum. During: our BOX-LOCK line, dmesg polled every 3 s, the run stopped at any new amdgpu fault/timeout/reset
# line. After: the live saves checksum again (never used by the run), the lock line removed (on failure too).
# Conditions: the top session's GO for exp 0385; RT ON (the input configuration's RayTracing line); stop at the first
# reset or machine-down.
# usage: ab0312.sh <tag> <live saves checksum> "<switches>" [secs]   (on the box, from SSH; output in ~/bc5-work/exp0385/)
set -u
E=$HOME/bc5-work/exp0385
tag=$1; REF=$2; J=$3; SECS=${4:-330}
saves() { (cd ~/bc5-work/_SaveData && find PPSA03671 -type f -exec md5sum {} + | LC_ALL=C sort -k2 | md5sum | cut -c1-16); }
L=$(grep -v "water session exp 0385" ~/bc5-work/BOX-LOCK 2>/dev/null)
[ -n "$L" ] && { echo "$tag: box locked, stopping: $L"; exit 1; }
pgrep "^kyty_emulator" > /dev/null && { echo "$tag: an emulator is running"; exit 1; }
use=$(df --output=pcent /var/home | tail -1 | tr -dc 0-9)
[ "$use" -ge 80 ] && { echo "$tag: /var/home at $use %, stopping"; exit 1; }
[ -e "$E/r-$tag" ] && { echo "$tag: tag used"; exit 1; }
grep -q "^RayTracing.PPSA03671=on$" "$E/input-0385.cfg" || { echo "$tag: input-0385.cfg does not set RT on: stopping"; exit 1; }
S=$(saves); echo "$(date +%T) $tag live saves before: $S"
[ "$S" = "$REF" ] || { echo "$tag: live saves differ from $REF: stopping"; exit 1; }
echo "water session exp 0385 | lake bench $tag (RT on, $J) | start $(date +%H:%M) | until ~$(date -d "+$(( (SECS + 90) / 60 )) min" +%H:%M)" >> ~/bc5-work/BOX-LOCK
trap 'sed -i "/water session exp 0385 | lake bench $tag /d" ~/bc5-work/BOX-LOCK' EXIT
before=$(sudo -n dmesg | wc -l)
echo "$(date +%T) $tag start: binary $(md5sum ~/bc5-work/kytyplus-build/src/kyty_emulator | cut -c1-8), /var/home $use %, dmesg $before lines; switches: $J"
ENVX="$J" "$E/bench0385.sh" "$tag" "$SECS" > "$E/$tag.out" 2>&1 &
BP=$!
# box-side cap (the top session, 2026-10-30, after a dropped ssh left an emulator running): watches only this run's
# emulator, ends with it, stops it at SECS + 60 s
setsid bash -c 'for _ in $(seq 1 60); do p=$(pgrep -n -x kyty_emulator) && break; sleep 1; done; [ -n "$p" ] || exit 0; end=$(( $(date +%s) + $1 )); while kill -0 "$p" 2>/dev/null; do if [ "$(date +%s)" -ge "$end" ]; then echo "cap: stopping emulator $p at $(date +%T)"; kill "$p"; sleep 6; kill -9 "$p" 2>/dev/null; exit 0; fi; sleep 3; done' _ $((SECS + 60)) > "$E/$tag.cap.txt" 2>&1 < /dev/null &
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
sed "s/^/  /" "$E/$tag.out"
S2=$(saves); echo "$(date +%T) $tag live saves after: $S2; /var/home $(df --output=pcent /var/home | tail -1 | tr -d ' ')"
[ "$S2" = "$REF" ] || echo "$tag: LIVE SAVES CHANGED ($S2): ask the top session before anything else"
[ -n "$bad" ] && { echo "  devcoredumps (newest): $(ls -t ~/bc5-data/captures/devcoredump/ 2>/dev/null | head -3 | tr '\n' ' ')"; exit 1; }
echo "$(date +%T) $tag done"
