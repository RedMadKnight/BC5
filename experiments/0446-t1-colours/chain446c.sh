#!/usr/bin/env bash
# exp 0446 (tag p446, 2026-11-26): where the candidate's ~1 % on the second title goes. One boot, the second title from the
# NAS, the route into play:
#   lean, 600 s each, frame log, per-thread CPU (thr446.sh): S (shared lean), C (candidate s3 lean 577e1e06),
#     M (C + DMA_SYNC_MEC=0 DMA_SYNC_LABEL=0), X (C + PREFIX_CHAINS=0), W (C + CHAIN_WRITERS=0)
#   normal, 300 s each, the emulator's own frame profile in the journal (normal-build figures): SN (shared 5727b07f),
#     CN (candidate s3 normal 5a407b8d)
# Each run waits for no lock, no emulator, no compiler (ser446.sh). Stop with: touch ~/bc5-work/exp0446/STOP
set -u
X=$HOME/bc5-work/exp0446; cd "$X" || exit 1; R=$X/raw; TAG=${CHAIN_TAG:-x446p}
CL=$X/s3/lean/kyty_emulator; CN=$X/s3/normal/kyty_emulator; SL=$HOME/bc5-work/kytyplus-build-lean/src/kyty_emulator; SN=$HOME/bc5-work/kytyplus-build/src/kyty_emulator
run() { # tag letter, binary, pin, lean 0/1, seconds, words
    [ -e STOP ] && return 1
    THR_S=5 bash ./thr446.sh "$R/$TAG$1D-thr.txt" & local th=$!
    SER_WAIT=10800 SER_BIN=$2 SER_PIN=$3 SER_LEAN=$4 SER_MH=$4 SER_SECS=$5 SER_EXTRA="$6" bash ./ser446.sh "$TAG$1" D 2>&1 | grep -E "^.{8} ser " | grep -v "arm D words"
    kill $th 2> /dev/null; wait $th 2> /dev/null
}
run S "$SL" 94a6513c 1 600 "KYTY_BC5_MANGOHUD=0" || exit 0
run C "$CL" 577e1e06 1 600 "KYTY_BC5_MANGOHUD=0" || exit 0
run M "$CL" 577e1e06 1 600 "KYTY_BC5_MANGOHUD=0 BC5_DIRECT_DMA_SYNC_MEC=0 BC5_DIRECT_DMA_SYNC_LABEL=0" || exit 0
run X "$CL" 577e1e06 1 600 "KYTY_BC5_MANGOHUD=0 BC5_DIRECT_PREFIX_CHAINS=0" || exit 0
run W "$CL" 577e1e06 1 600 "KYTY_BC5_MANGOHUD=0 BC5_DIRECT_CHAIN_WRITERS=0" || exit 0
run SN "$SN" 5727b07f 0 300 "" || exit 0
run CN "$CN" 5a407b8d 0 300 "" || exit 0
echo "chain446c done $(date +%T)"
