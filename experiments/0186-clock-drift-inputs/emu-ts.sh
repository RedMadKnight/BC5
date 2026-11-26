#!/usr/bin/env bash
# BC5 (experiment 0186): run an older emulator binary (copied as <dir>/kyty_emulator, so that the
# run scripts' pgrep/pkill -x kyty_emulator find it) with its AJM job lines turned into a timed
# index by ajm_ts.py. Use as BC5_EMU=~/bc5-work/emu-ts.sh with EMU_TS_BIN=<dir>/kyty_emulator,
# AJM_TS_OUT=<index file> and KYTY_BC5_AJM_TRACE=1.
"${EMU_TS_BIN:?}" "$@" 2>&1 | python3 -I -u ~/bc5-work/ajm_ts.py
exit "${PIPESTATUS[0]}"
