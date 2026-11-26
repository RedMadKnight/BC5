#!/usr/bin/env bash
# BC5 (experiment 0203): a BC5_EMU wrapper for play-pkg.sh, as exp 0200's emu0200.sh, writing into
# ~/bc5-work/exp0203/raw. It runs the test binary (EMU_TS_BIN) with its output through exp 0200's filt0200.py
# (AJM decoder jobs into raw/<tag>-ajm-index.txt, the APR lines of KYTY_BC5_AMM_TRACE into raw/<tag>-amm.txt;
# everything else, the "apr journal (exp 0203)" lines too, into the play log) and starts exp 0200's sample0200.py
# beside it (raw/<tag>-sample.txt). Tag: EXP0203_TAG (default run).
E=$HOME/bc5-work/exp0203
T=$HOME/bc5-work/exp0200
BIN=${EMU_TS_BIN:-$E/kyty_emulator}
TAG=${EXP0203_TAG:-run}
export AJM_TS_OUT=${AJM_TS_OUT:-$E/raw/$TAG-ajm-index.txt} AMM_OUT=${AMM_OUT:-$E/raw/$TAG-amm.txt}
setsid nice -n 5 python3 -I "$T/sample0200.py" "$E/raw/$TAG-sample.txt" 20 < /dev/null > "$E/raw/$TAG-sampler.err" 2>&1 &
"$BIN" "$@" 2>&1 | python3 -I -u "$T/filt0200.py"
exit "${PIPESTATUS[0]}"
