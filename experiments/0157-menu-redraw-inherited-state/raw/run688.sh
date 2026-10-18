#!/usr/bin/env bash
# BC5 run 688 (exp 0155, exp 0157: the full-state prefix without CLEAR_STATE on the drawing buffers (PREFIX_ALL=draws, PIECES_NO_CLEAR=1)): Initial Setup > View All Settings > Visuals, the list scrolled down and up at 2 s a step; screenshots every 2 s (watch688.sh).
export BC5_RUN_CWD=$HOME/bc5-work/exp0155-cwd KYTY_BC5_SAVEDATA_DIR=$HOME/bc5-work/_SaveData-exp0155 KYTY_BC5_INPUT_CMD=$HOME/bc5-work/input688.cmd
export BC5_DIRECT_PREFIX_ALL=draws
export BC5_DIRECT_PIECES_NO_CLEAR=1
export KYTY_BC5_APR_SYNC=1
exec ~/bc5-work/play-pkg-exp0155.sh
