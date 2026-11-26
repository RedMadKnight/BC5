#!/usr/bin/env bash
# exp 0446 (2026-11-26): the trimmed stage-1 candidate (s3: cleaned + FLIP_LABEL_GPU removed), built when the box is quiet,
# then on its lean: the first title once (image, 180 s), and the second title from the NAS, 600 s each with the frame log:
# C (as built), P (FLIP_LABEL_PIECES=0), I (IB_CHAIN=0, IB_CHAIN_FLAT=0), S (the shared lean). Each run waits for no lock,
# no emulator and no compiler (ser446.sh's gate). Stop it with: touch ~/bc5-work/exp0446/STOP
set -u
X=$HOME/bc5-work/exp0446; cd "$X" || exit 1
quiet() { [ "$(pgrep -c '^clang|^cc1plus|^ninja|^cargo|^rustc')" = 0 ] && [ ! -s "$HOME/bc5-work/BOX-LOCK" ] && ! pgrep '^kyty_emulator' > /dev/null; }
if [ ! -x s3/lean/kyty_emulator ]; then
    ok=0; t0=$(date +%s)
    while [ $ok -lt 8 ] && [ $(( $(date +%s) - t0 )) -lt 14400 ]; do if quiet; then ok=$((ok + 1)); else ok=0; fi; sleep 15; done
    [ $ok -ge 8 ] || { echo "never quiet for 2 min in 4 h"; exit 1; }
    S1_DIR=s3 bash b446s1.sh 2>&1 | grep -E "STOP|archive|rc |^lean|^normal|shared after" | cut -c1-300
fi
CL=$X/s3/lean/kyty_emulator; P=$(md5sum < "$CL" | cut -c1-8); echo "trimmed lean $P, normal $(md5sum < s3/normal/kyty_emulator | cut -c1-8)"
[ -e STOP ] && exit 0
t0=$(date +%s); while ! quiet && [ $(( $(date +%s) - t0 )) -lt 10800 ]; do sleep 15; done
echo "first title before: load $(cut -d' ' -f1 /proc/loadavg)"
AB_PIN_C=94a6513c AB_PIN_O=ef76f031 AB_PIN_N=94e0e462 AB_KIND=t1 AB_LEAN=1 AB_SECS=180 AB_SHOT_S=10 AB_GUARD_MB=1200 AB_ROUNDS=1 AB_ARMS="K" \
    AB_ARM_K="$CL|$P|KYTY_BC5_INPUT_CMD=$X/press446.cmd KYTY_BC5_MENU_DIR=$X/menu-full" bash ./ab446.sh x446c5 2>&1 | grep -E "PASS|ENDED|GUARD|STOP|memory:|lock"
SL=$HOME/bc5-work/kytyplus-build-lean/src/kyty_emulator
for a in "C|$CL|$P|KYTY_BC5_MANGOHUD=0" "P|$CL|$P|KYTY_BC5_MANGOHUD=0 BC5_0439_FLIP_LABEL_PIECES=0" \
         "I|$CL|$P|KYTY_BC5_MANGOHUD=0 BC5_DIRECT_IB_CHAIN=0 BC5_DIRECT_IB_CHAIN_FLAT=0" "S|$SL|94a6513c|KYTY_BC5_MANGOHUD=0"; do
    [ -e STOP ] && break
    IFS='|' read -r k b p x <<< "$a"
    SER_WAIT=10800 SER_BIN=$b SER_PIN=$p SER_LEAN=1 SER_MH=1 SER_SECS=600 SER_EXTRA="$x" bash ./ser446.sh "x446m$k" D 2>&1 | grep -E "^.{8} ser "
done
# then exp 0439's log-only arm on the second title (priv88, sampler v7.1; imports nothing): its play log and direct.log kept
[ -e STOP ] && exit 0
G=$HOME/bc5-work/exp0439/k439/normal/kyty_emulator.5c47ece4; DT=$HOME/bc5-data/captures/dt439
SER_WAIT=10800 SER_BIN=$G SER_PIN=5c47ece4 SER_SECS=180 SER_EXTRA="BC5_DIRECT_EAGER_GPU_WRITE=0 BC5_GUARD_DESC_TARGETS=2 BC5_0439_DT_IMAGES=1 BC5_0439_DT_STRICT=1 BC5_0439_DT_SET=$DT/v71c-set.txt BC5_0439_DT_TGT=$DT/v71c-tgt.txt BC5_0439_DT_GW=$DT/v71c-gw.txt BC5_0439_DT_GW_SYNC=1 BC5_0439_DT_GW_EPOCH=1 BC5_0439_PR_RUN=1" \
    bash ./ser446.sh x446v71 D 2>&1 | grep -E "^.{8} ser " | grep -v "arm D words"
echo "x446v71 play log: $X/raw/x446v71D-play-pkg.log; capture dir: $(grep -m1 -o 'play-2026[0-9-]*' "$X/raw/x446v71D-play-pkg.log" 2>/dev/null)"
