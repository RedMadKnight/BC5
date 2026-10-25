#!/usr/bin/env bash
# BC5 experiment 0303 (exp 0299's ab0299.sh, for the RT-on runs L8/L9): one lab-bench run (run0303.sh: the shared normal build, today's launcher in a private working
# directory, the lab save's private copy) with the given switches, attended. Before: no lock but ours, no emulator,
# /var/home under 80 %, the tag unused, the live saves at the given checksum. During: our BOX-LOCK line, dmesg polled
# every 3 s, the run stopped at any new amdgpu fault/timeout/reset line. After: the live saves checksum again (they are
# never used by the run), the journal's ray-tracing and skip lines, the draw-journal line count, the whiteness of the
# shots (wh0299.py), the lock line removed (on failure too). Conditions: the top session's GO for exp 0299 (RT off
# unless announced; stop on any fault, timeout or machine-down). Exp 0303: the RT-on runs approved by the maintainer ("zgadzam się na komplet Twoich testów"); the session stops at the first reset or machine-down.
# usage: ab0299.sh <tag> <live saves checksum> "<switches>" [secs]   (on the box, from SSH; output in ~/bc5-work/exp0299/)
set -u
E=$HOME/bc5-work/exp0303
tag=$1; REF=$2; J=$3; SECS=${4:-260}
saves() { (cd ~/bc5-work/_SaveData && find PPSA03671 -type f -exec md5sum {} + | sort -k2 | md5sum | cut -c1-16); }
L=$(grep -v "water session exp 0303" ~/bc5-work/BOX-LOCK 2>/dev/null)
[ -n "$L" ] && { echo "$tag: box locked, stopping: $L"; exit 1; }
pgrep "^kyty_emulator" > /dev/null && { echo "$tag: an emulator is running"; exit 1; }
use=$(df --output=pcent /var/home | tail -1 | tr -dc 0-9)
[ "$use" -ge 80 ] && { echo "$tag: /var/home at $use %, stopping"; exit 1; }
[ -e "$E/r-$tag" ] && { echo "$tag: tag used"; exit 1; }
S=$(saves); echo "$(date +%T) $tag live saves before: $S"
[ "$S" = "$REF" ] || { echo "$tag: live saves differ from $REF: stopping"; exit 1; }
echo "water session exp 0303 | bench $tag (lab, $J) | start $(date +%H:%M) | until ~$(date -d "+$(( (SECS + 90) / 60 )) min" +%H:%M)" >> ~/bc5-work/BOX-LOCK  # appended: the session's window line stays
trap 'sed -i "/water session exp 0303 | bench $tag /d" ~/bc5-work/BOX-LOCK' EXIT
before=$(sudo -n dmesg | wc -l)
echo "$(date +%T) $tag start: binary $(md5sum ~/bc5-work/kytyplus-build/src/kyty_emulator | cut -c1-8), /var/home $use %, dmesg $before lines; switches: $J"
ENVX="$J" "$E/run0303.sh" "$tag" "$SECS" > "$E/$tag.out" 2>&1 &
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
cat "$E/$tag.out" | sed "s/^/  /"
jd=$(cat "$E/r-$tag/journal-dir.txt" 2>/dev/null)
if [ -n "$jd" ] && [ -f "$jd/direct.log" ]; then
  echo "  journal $jd: $(du -h "$jd/direct.log" | cut -f1), $(grep -ac '^draw journal buf' "$jd/direct.log") draw-journal lines, $(grep -ac 'ray tracing off:' "$jd/direct.log") ray-tracing-off lines, $(grep -ac 'skip pgm' "$jd/direct.log") skip lines"
  grep -a "ray tracing: program" "$jd/direct.log" | sort -u > "$E/$tag.rtprog.txt"
  echo "  ray-tracing scan: $(grep -c "uses image_bvh" "$E/$tag.rtprog.txt") programs with ray queries, $(grep -c "has no ray" "$E/$tag.rtprog.txt") without"
  grep -a "ray tracing off:\|skip pgm" "$jd/direct.log" | sed 's/(.*so far)//' | sort | uniq -c | sort -rn | head -20 > "$E/$tag.drops.txt"
fi
nice -n 5 distrobox enter ubuntu -- python3 -I "$HOME/bc5-work/exp0299/wh0299.py" "$E/r-$tag/shots" > "$E/$tag.wh.txt" 2>&1
grep -v "^Container\|OK \]\|^.\[0m$" "$E/$tag.wh.txt" | sed "s/^/  /" | head -20
S2=$(saves); echo "$(date +%T) $tag live saves after: $S2; /var/home $(df --output=pcent /var/home | tail -1 | tr -d ' ')"
[ "$S2" = "$REF" ] || echo "$tag: LIVE SAVES CHANGED ($S2): restore from $E/saves-live-snap only after asking the top session"
[ -n "$bad" ] && { echo "  devcoredumps (newest): $(ls -t ~/bc5-data/captures/devcoredump/ 2>/dev/null | head -3 | tr '\n' ' ')"; exit 1; }
echo "$(date +%T) $tag done"
