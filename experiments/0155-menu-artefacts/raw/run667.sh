#!/usr/bin/env bash
# BC5 run 667 (exp 0155, automatic AMM maps zero-filled (KYTY_BC5_AMM_ZERO_AUTO=1), AMM trace on): Initial Setup > View All Settings > Visuals, the list scrolled down and up at 2 s a step; screenshots every 2 s (watch667.sh).
export BC5_RUN_CWD=$HOME/bc5-work/exp0155-cwd KYTY_BC5_SAVEDATA_DIR=$HOME/bc5-work/_SaveData-exp0155 KYTY_BC5_INPUT_CMD=$HOME/bc5-work/input667.cmd
export BC5_DIRECT_PKT_STATS=1
export KYTY_BC5_AMM_ZERO_AUTO=1
export KYTY_BC5_AMM_TRACE=1
exec ~/bc5-work/play-pkg-exp0155.sh
