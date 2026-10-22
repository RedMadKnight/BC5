#!/usr/bin/env bash
# BC5 experiment 0205: the APR readahead A/B on the lake bench. Runs bench0205.sh once per "<tag>:<arm>" argument, one
# after the other (arm A: the cutscene session's exp 0203 binary, KYTY_BC5_APR_READAHEAD off; arm B: the same with
# KYTY_BC5_APR_READAHEAD=4), each with the page sampler over the water's four textures. Before each run: no lock, no
# emulator, the same boot as at the start. After each: no new amdgpu, fault or timeout line in dmesg, else it stops.
# usage: ab0205.sh A1:A B1:B A2:A   (on the box, from SSH; output in ~/bc5-work/exp0205/<tag>.bench.txt)
set -u
BIN=$HOME/bc5-work/exp0203/kyty_emulator
BOOT=$(cat /proc/sys/kernel/random/boot_id)
export PAGES=1 PAGES_RANGES="8492504000:800000 80907c4000:200000 8001810000:800000 8001010000:200000"
for ta in "$@"; do
  tag=${ta%%:*}; arm=${ta##*:}
  for _ in $(seq 1 60); do [ -s ~/bc5-work/BOX-LOCK ] || pgrep -x kyty_emulator > /dev/null || break; sleep 5; done
  [ -s ~/bc5-work/BOX-LOCK ] && { echo "$tag: box locked: $(cat ~/bc5-work/BOX-LOCK)"; exit 1; }
  pgrep -x kyty_emulator > /dev/null && { echo "$tag: an emulator is running"; exit 1; }
  [ "$(cat /proc/sys/kernel/random/boot_id)" = "$BOOT" ] || { echo "$tag: the box rebooted"; exit 1; }
  before=$(sudo -n dmesg | wc -l)
  case $arm in
    A) ENVX="BC5_EMU=$BIN" ;;
    B) ENVX="BC5_EMU=$BIN KYTY_BC5_APR_READAHEAD=4" ;;
    *) echo "$tag: arm $arm?"; exit 1 ;;
  esac
  echo "$(date +%T) $tag arm $arm: $ENVX"
  ENVX="$ENVX" ~/bc5-work/exp0205/bench0205.sh "$tag" > ~/bc5-work/exp0205/"$tag".bench.txt 2>&1
  rc=$?
  [ $rc -ne 0 ] && { echo "$tag: bench exit $rc, stopping:"; tail -3 ~/bc5-work/exp0205/"$tag".bench.txt; exit 1; }
  for _ in $(seq 1 60); do pgrep -x kyty_emulator > /dev/null || break; sleep 5; done
  for _ in $(seq 1 6); do [ -s ~/bc5-work/BOX-LOCK ] || break; sleep 5; done
  new=$(sudo -n dmesg | tail -n +$((before + 1)) | grep -i "amdgpu\|fault\|timeout")
  grep -a "patch\|^==" ~/bc5-work/exp0205/"$tag".bench.txt | sed "s/^/  /"
  [ -n "$new" ] && { echo "$tag: new kernel lines, stopping:"; echo "$new"; exit 1; }
done
echo "$(date +%T) done"
