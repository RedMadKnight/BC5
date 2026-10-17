#!/usr/bin/env bash
# BC5 run 654 (exp 0155, cross-queue waits given up only after 2 s (DCB_WAIT_MS=2000, ACB_WAIT_MS=2000)): Initial Setup > View All Settings > Visuals, the list scrolled down and up at 2 s a step; screenshots every 2 s (watch654.sh).
export BC5_RUN_CWD=$HOME/bc5-work/exp0155-cwd KYTY_BC5_SAVEDATA_DIR=$HOME/bc5-work/_SaveData-exp0155 KYTY_BC5_INPUT_CMD=$HOME/bc5-work/input654.cmd
export BC5_DIRECT_PKT_STATS=1
export BC5_DIRECT_DCB_WAIT_MS=2000
export BC5_DIRECT_ACB_WAIT_MS=2000
exec ~/bc5-work/play-pkg-exp0155.sh
