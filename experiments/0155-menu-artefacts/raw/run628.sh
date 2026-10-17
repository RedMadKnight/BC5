#!/usr/bin/env bash
# BC5 run 628 (exp 0155): run 627 (private empty save directory, Initial Setup > View All Settings > Visuals) with synchronous submission on one ring: BC5_DIRECT_ASYNC, RING_ASYNC, COMPUTE_RING and CROSS_RING_WAITS taken away; BC5_DIRECT_DROP_TALLY=1 and PKT_STATS for the filter's drops.
export BC5_RUN_CWD=$HOME/bc5-work/exp0155-cwd KYTY_BC5_SAVEDATA_DIR=$HOME/bc5-work/_SaveData-exp0155 KYTY_BC5_INPUT_CMD=$HOME/bc5-work/input628.cmd BC5_DIRECT_PKT_STATS=1 BC5_DIRECT_DROP_TALLY=1
export BC5_UNSET="BC5_DIRECT_ASYNC BC5_DIRECT_RING_ASYNC BC5_DIRECT_COMPUTE_RING BC5_DIRECT_CROSS_RING_WAITS BC5_DIRECT_MAX_IN_FLIGHT"
exec ~/bc5-work/play-pkg-exp0155.sh
