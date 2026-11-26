#!/usr/bin/env bash
# BC5 (experiment 0200): a BC5_EMU wrapper for play-pkg.sh (as exp 0186's emu-ts.sh). It runs the shared build
# (EMU_TS_BIN to override) with its output through filt0200.py, which writes the AJM decoder jobs into
# raw/<tag>-ajm-index.txt and the APR lines of KYTY_BC5_AMM_TRACE into raw/<tag>-amm.txt, and starts
# sample0200.py beside it (raw/<tag>-sample.txt). The binary keeps the name kyty_emulator, so the launchers'
# pgrep/pkill find it. Tag: EXP0200_TAG (default run).
E=$HOME/bc5-work/exp0200
BIN=${EMU_TS_BIN:-$HOME/bc5-work/kytyplus-build/src/kyty_emulator}
TAG=${EXP0200_TAG:-run}
export AJM_TS_OUT=${AJM_TS_OUT:-$E/raw/$TAG-ajm-index.txt} AMM_OUT=${AMM_OUT:-$E/raw/$TAG-amm.txt}
setsid nice -n 5 python3 -I "$E/sample0200.py" "$E/raw/$TAG-sample.txt" 20 < /dev/null > "$E/raw/$TAG-sampler.err" 2>&1 &
"$BIN" "$@" 2>&1 | python3 -I -u "$E/filt0200.py"
exit "${PIPESTATUS[0]}"
