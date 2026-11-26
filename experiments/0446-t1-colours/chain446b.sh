#!/usr/bin/env bash
# exp 0446 (2026-11-26 afternoon): the second boot of the trimmed candidate's lean arms (s3 lean 577e1e06), all on one boot
# so they compare: S (the shared lean), C (as built), P (FLIP_LABEL_PIECES=0), I (IB_CHAIN=0, IB_CHAIN_FLAT=0), P again;
# the second title from the NAS, 600 s each with the frame log; then exp 0439's priv88 log-only arm. Each run waits for no
# lock, no emulator and no compiler (ser446.sh's gate). Stop with: touch ~/bc5-work/exp0446/STOP
set -u
X=$HOME/bc5-work/exp0446; cd "$X" || exit 1
CL=$X/s3/lean/kyty_emulator; P=577e1e06; SL=$HOME/bc5-work/kytyplus-build-lean/src/kyty_emulator; TAG=${CHAIN_TAG:-x446n}
[ "$(md5sum < "$CL" | cut -c1-8)" = $P ] || { echo "s3 lean is not $P"; exit 1; }
for a in "S|$SL|94a6513c|KYTY_BC5_MANGOHUD=0" "C|$CL|$P|KYTY_BC5_MANGOHUD=0" "P|$CL|$P|KYTY_BC5_MANGOHUD=0 BC5_0439_FLIP_LABEL_PIECES=0" \
         "I|$CL|$P|KYTY_BC5_MANGOHUD=0 BC5_DIRECT_IB_CHAIN=0 BC5_DIRECT_IB_CHAIN_FLAT=0" "Q|$CL|$P|KYTY_BC5_MANGOHUD=0 BC5_0439_FLIP_LABEL_PIECES=0"; do
    [ -e STOP ] && exit 0
    IFS='|' read -r k b p x <<< "$a"
    SER_WAIT=10800 SER_BIN=$b SER_PIN=$p SER_LEAN=1 SER_MH=1 SER_SECS=600 SER_EXTRA="$x" bash ./ser446.sh "$TAG$k" D 2>&1 | grep -E "^.{8} ser "
done
[ -e STOP ] && exit 0
G=$HOME/bc5-work/exp0439/k439/normal/kyty_emulator.5c47ece4; DT=$HOME/bc5-data/captures/dt439
SER_WAIT=10800 SER_BIN=$G SER_PIN=5c47ece4 SER_SECS=180 SER_EXTRA="BC5_DIRECT_EAGER_GPU_WRITE=0 BC5_GUARD_DESC_TARGETS=2 BC5_0439_DT_IMAGES=1 BC5_0439_DT_STRICT=1 BC5_0439_DT_SET=$DT/v71c-set.txt BC5_0439_DT_TGT=$DT/v71c-tgt.txt BC5_0439_DT_GW=$DT/v71c-gw.txt BC5_0439_DT_GW_SYNC=1 BC5_0439_DT_GW_EPOCH=1 BC5_0439_PR_RUN=1" \
    bash ./ser446.sh x446v71 D 2>&1 | grep -E "^.{8} ser " | grep -v "arm D words"
echo "x446v71 play log: $X/raw/x446v71D-play-pkg.log; capture dir: $(grep -m1 -o 'play-2026[0-9-]*' "$X/raw/x446v71D-play-pkg.log" 2>/dev/null)"
