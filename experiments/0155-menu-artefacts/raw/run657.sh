#!/usr/bin/env bash
# BC5 run 657 (exp 0155, synchronous submission, one ring): Initial Setup > View All Settings > Visuals, the list scrolled down and up at 2 s a step; screenshots every 2 s (watch657.sh).
export BC5_RUN_CWD=$HOME/bc5-work/exp0155-cwd KYTY_BC5_SAVEDATA_DIR=$HOME/bc5-work/_SaveData-exp0155 KYTY_BC5_INPUT_CMD=$HOME/bc5-work/input657.cmd
export BC5_DIRECT_PKT_STATS=1
export BC5_UNSET="BC5_DIRECT_ASYNC BC5_DIRECT_RING_ASYNC BC5_DIRECT_COMPUTE_RING BC5_DIRECT_CROSS_RING_WAITS BC5_DIRECT_MAX_IN_FLIGHT"
exec ~/bc5-work/play-pkg-exp0155.sh
