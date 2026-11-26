#!/usr/bin/env bash
# BC5 experiment 0212: bench0212.sh runs with DUMPS=1 and the water shaders' journal, one per "<tag>:<binary>" argument
# (x = the cutscene session's exp 0203 binary with its switch off, s = the shared build), one after the other. Before each
# run: no lock, no emulator, the same boot as at the start. After each: no new amdgpu, fault or timeout line in dmesg, and
# the bench finished, else it stops. Then the run's descriptors are decoded (desc0212.py on its journal).
# usage: ab0212.sh C1:x C2:s C3:x C4:s   (on the box, from SSH; output in ~/bc5-work/exp0212/<tag>.*)
set -u
E=$HOME/bc5-work/exp0212
BOOT=$(cat /proc/sys/kernel/random/boot_id)
export DUMPS=1
J="BC5_DIRECT_DRAW_JOURNAL=150:4 BC5_DIRECT_DRAW_JOURNAL_EVERY=15 BC5_DIRECT_DRAW_JOURNAL_PS=11d01ff900,11d01d7100"
for tb in "$@"; do
  tag=${tb%%:*}; b=${tb##*:}
  for _ in $(seq 1 60); do [ -s ~/bc5-work/BOX-LOCK ] || pgrep -x kyty_emulator > /dev/null || break; sleep 5; done
  [ -s ~/bc5-work/BOX-LOCK ] && { echo "$tag: box locked: $(cat ~/bc5-work/BOX-LOCK)"; exit 1; }
  pgrep -x kyty_emulator > /dev/null && { echo "$tag: an emulator is running"; exit 1; }
  [ "$(cat /proc/sys/kernel/random/boot_id)" = "$BOOT" ] || { echo "$tag: the box rebooted"; exit 1; }
  before=$(sudo -n dmesg | wc -l)
  case $b in
    x) BIN=$HOME/bc5-work/exp0203/kyty_emulator ;;
    s) BIN=$HOME/bc5-work/kytyplus-build/src/kyty_emulator ;;
    *) echo "$tag: binary $b?"; exit 1 ;;
  esac
  echo "$(date +%T) $tag binary $b: $BIN"
  ENVX="BC5_EMU=$BIN $J" "$E/bench0212.sh" "$tag" > "$E/$tag.bench.txt" 2>&1
  rc=$?
  [ $rc -ne 0 ] && { echo "$tag: bench exit $rc, stopping:"; tail -3 "$E/$tag.bench.txt"; exit 1; }
  for _ in $(seq 1 60); do pgrep -x kyty_emulator > /dev/null || break; sleep 5; done
  for _ in $(seq 1 6); do [ -s ~/bc5-work/BOX-LOCK ] || break; sleep 5; done
  grep -a "patch\|^==" "$E/$tag.bench.txt" | sed "s/^/  /"
  jd=$(cat ~/bc5-work/exp0194/r-$tag/journal-dir.txt 2>/dev/null)
  [ -n "$jd" ] && nice -n 10 python3 -I "$E/desc0212.py" "$jd/direct.log" > "$E/$tag.desc.txt" 2>&1
  new=$(sudo -n dmesg | tail -n +$((before + 1)) | grep -i "amdgpu\|fault\|timeout")
  [ -n "$new" ] && { echo "$tag: new kernel lines, stopping:"; echo "$new"; exit 1; }
done
echo "$(date +%T) done"
