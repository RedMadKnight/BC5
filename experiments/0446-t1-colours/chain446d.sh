#!/usr/bin/env bash
# exp 0446 (tag q446, 2026-11-26 evening): the GPU-side arms for the stage-1 build's ~1 % on the second title, on one fresh
# boot, under ONE BOX-LOCK line for the whole chain (X446_HELD: ser446/nas446 run inside it): the second title from the NAS,
# lean, 600 s each, frame log, per-thread CPU:
#   O the old shared lean (kept as kytyplus-build-lean/src/kyty_emulator.bakeH, 94a6513c)
#   D the deployed shared lean (the stage-1 build), as deployed
#   Z D with BC5_DIRECT_DCC_PRESENT=0 (no decompress at the flip)
#   M D with BC5_DIRECT_DMA_SYNC_MEC=0 BC5_DIRECT_DMA_SYNC_LABEL=0
# Waits up to 1 h for an empty lock, no emulator and no compiler, then claims the lock. Stop: touch ~/bc5-work/exp0446/STOP
set -u
X=$HOME/bc5-work/exp0446; W=$HOME/bc5-work; cd "$X" || exit 1; R=$X/raw; LOCK=$W/BOX-LOCK; TAG=${CHAIN_TAG:-x446q}
LB=$W/kytyplus-build-lean/src/kyty_emulator; OB=$LB.bakeH
m8() { md5sum < "$1" | cut -c1-8; }
[ "$(m8 "$OB")" = 94a6513c ] || { echo "the kept old lean is not 94a6513c"; exit 1; }
DP=$(m8 "$LB"); [ "$DP" != 94a6513c ] || { echo "the shared lean is still the old one: no deployment?"; exit 1; }
busy() { [ -s "$LOCK" ] || pgrep '^kyty_emulator' > /dev/null || pgrep -x bc5-mount > /dev/null || [ "$(pgrep -c '^clang|^cc1plus|^ninja|^cargo|^rustc')" != 0 ]; }
t0=$(date +%s); while busy && [ $(( $(date +%s) - t0 )) -lt 3600 ]; do sleep 15; done
busy && { echo "box busy for an hour: not started"; exit 1; }
LINE="exp 0446 | GPU-side arms O D Z M (one line for the chain, about 45 min), token $(date +%s)$$ | $(date '+%F %T')"
[ -e "$LOCK" ] || touch "$LOCK"; tl=$LOCK.q446-$$.new; al=$LOCK.q446-$$.aside
printf '%s\n' "$LINE" > "$tl" && mv -T "$LOCK" "$al" && ln "$tl" "$LOCK" || { [ -e "$LOCK" ] || mv -T "$al" "$LOCK"; rm -f "$tl"; echo "claim failed"; exit 1; }
if [ -s "$al" ]; then mv -fT "$al" "$LOCK"; rm -f "$tl"; echo "locked: $(cat "$LOCK")"; exit 1; fi
rm -f "$al" "$tl"
unlock() { if grep -qxF -- "$LINE" "$LOCK"; then grep -vxF -- "$LINE" "$LOCK" > "$LOCK.q446-$$.rel"; mv -fT "$LOCK.q446-$$.rel" "$LOCK"; fi; }
trap unlock EXIT
export X446_HELD=$LINE
echo "$(date +%T) chain446d: lock held; boot $(uptime -s); old lean 94a6513c, deployed lean $DP"
for a in "O|$OB|94a6513c|KYTY_BC5_MANGOHUD=0" "D|$LB|$DP|KYTY_BC5_MANGOHUD=0" "Z|$LB|$DP|KYTY_BC5_MANGOHUD=0 BC5_DIRECT_DCC_PRESENT=0" \
         "M|$LB|$DP|KYTY_BC5_MANGOHUD=0 BC5_DIRECT_DMA_SYNC_MEC=0 BC5_DIRECT_DMA_SYNC_LABEL=0"; do
    [ -e STOP ] && break
    IFS='|' read -r k b p x <<< "$a"
    echo "$(date +%T) before $k: $(( $(awk '/MemAvailable/ {print $2}' /proc/meminfo) / 1024 )) MiB available, load $(cut -d' ' -f1 /proc/loadavg)"
    THR_S=5 bash ./thr446.sh "$R/$TAG${k}D-thr.txt" & th=$!
    SER_WAIT=600 SER_BIN=$b SER_PIN=$p SER_LEAN=1 SER_MH=1 SER_SECS=600 SER_EXTRA="$x" bash ./ser446.sh "$TAG$k" D 2>&1 | grep -E "^.{8} ser " | grep -v "arm D words"
    kill $th 2> /dev/null; wait $th 2> /dev/null
done
echo "$(date +%T) chain446d done"
