#!/usr/bin/env bash
# BC5 experiment 0233 (from exp 0232): lake-bench runs with a camera nudge after the first shot series (NUDGE=1, bench0233.sh) and with the title's AMM/APR requests traced (KYTY_BC5_AMM_TRACE=1), the water
# shaders' journal, and exp 0212's texture-table dumps (DUMPS=1: a CRC per 4-KiB page every second, dumps before each
# frozen-view shot), one per tag, one after the other, on bench0233.sh (exp 0212's bench plus the nudge; its default exp 0194 build, comm
# "kyty_emulator"; the bench's own launcher copy keeps the old values: no PRT, old skip list). Conditions of the grant
# (top session, 2026-10-23, as for exp 0232): before each run no lock, no emulator, the same boot and /var/home under 80 %;
# during each run dmesg is polled every 3 s and the run is stopped on any new amdgpu fault/timeout/reset line; at most
# the tags given. The live saves are never used by the bench (private copy); their checksum is taken before and after.
# usage: ab0233.sh N1 N2 N3 N4   (on the box, from SSH; output in ~/bc5-work/exp0233/)
set -u
E=$HOME/bc5-work/exp0233
W=$HOME/bc5-work/exp0194
BOOT=$(cat /proc/sys/kernel/random/boot_id)
export DUMPS=1 NUDGE=1
J="BC5_DIRECT_DRAW_JOURNAL=150:4 BC5_DIRECT_DRAW_JOURNAL_EVERY=15 BC5_DIRECT_DRAW_JOURNAL_PS=11d01ff900,11d01d7100"
saves() { (cd ~/bc5-work/_SaveData && find PPSA03671 -type f -exec md5sum {} + | sort -k2 | md5sum | cut -c1-16); }
echo "$(date +%T) live saves checksum before: $(saves)"
for tag in "$@"; do
  for _ in $(seq 1 60); do
    L=$(cat ~/bc5-work/BOX-LOCK 2>/dev/null)
    # any lock but this series' own bench lock (e.g. the maintainer's play): stop at once, start nothing
    [ -n "$L" ] && [ "${L#water session exp 0233 | bench }" = "$L" ] && { echo "$tag: lock by someone else, stopping: $L"; exit 1; }
    [ -s ~/bc5-work/BOX-LOCK ] || pgrep -x kyty_emulator > /dev/null || break; sleep 5
  done
  [ -s ~/bc5-work/BOX-LOCK ] && { echo "$tag: box locked: $(cat ~/bc5-work/BOX-LOCK)"; exit 1; }
  pgrep -x kyty_emulator > /dev/null && { echo "$tag: an emulator is running"; exit 1; }
  [ "$(cat /proc/sys/kernel/random/boot_id)" = "$BOOT" ] || { echo "$tag: the box rebooted"; exit 1; }
  use=$(df --output=pcent /var/home | tail -1 | tr -dc 0-9)
  [ "$use" -ge 80 ] && { echo "$tag: /var/home at $use %, stopping"; exit 1; }
  [ -e "$W/r-$tag" ] && { echo "$tag: tag used"; exit 1; }
  before=$(sudo -n dmesg | wc -l)
  echo "$(date +%T) $tag start: /var/home $use %, dmesg $before lines"
  ENVX="KYTY_BC5_AMM_TRACE=1 $J" "$E/bench0233.sh" "$tag" 360 > "$E/$tag.bench.txt" 2>&1 &
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
  for _ in $(seq 1 6); do grep -q "exp 0233 | bench $tag " ~/bc5-work/BOX-LOCK 2>/dev/null || break; sleep 5; done
  grep -a "patch\|timed out\|ended early" "$E/$tag.bench.txt" | sed "s/^/  /"
  jd=$(cat "$W/r-$tag/journal-dir.txt" 2>/dev/null)
  [ -n "$jd" ] && nice -n 10 python3 -I "$HOME/bc5-work/exp0212/desc0212.py" "$jd/direct.log" 11d01ff900 > "$E/$tag.desc.txt" 2>&1
  echo "  written: run dir $(du -sh "$W/r-$tag" | cut -f1), journal dir $(du -sh "$jd" 2>/dev/null | cut -f1), emu.log $(du -sh "$W/r-$tag/emu.log" 2>/dev/null | cut -f1)"
  [ -n "$bad" ] && exit 1
done
echo "$(date +%T) live saves checksum after: $(saves); /var/home $(df --output=pcent /var/home | tail -1 | tr -d ' ')"
echo "$(date +%T) done"
