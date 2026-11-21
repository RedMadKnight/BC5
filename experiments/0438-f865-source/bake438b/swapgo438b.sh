#!/usr/bin/env bash
# BC5 exp 0438: the bake438b swap, run as ONE named systemd --user unit (LESSONS R73): wait (bounded 30 min) until the
# BOX-LOCK is empty and no kyty_emulator / bc5-mount runs, then run-swap0438b.sh (the swap, then the smoke, under one lock
# line). Writes swap.log and swap.done beside the kit.
set -u
K=$HOME/bc5-work/exp0438/bake438bkit; L=$HOME/bc5-work/BOX-LOCK
cd "$K" || exit 1
rm -f swap.log swap.done
t0=$(date +%s)
while [ $(( $(date +%s) - t0 )) -lt 1800 ]; do
    if [ ! -s "$L" ] && ! pgrep -x kyty_emulator > /dev/null && ! pgrep -x bc5-mount > /dev/null; then break; fi
    sleep 15
done
if [ -s "$L" ] || pgrep -x kyty_emulator > /dev/null; then echo "no free slot within 30 min: not started" > swap.log; echo 1 > swap.done; exit 1; fi
PATCH_NEW=589ef163 bash run-swap0438b.sh > swap.log 2>&1; echo $? > swap.done
