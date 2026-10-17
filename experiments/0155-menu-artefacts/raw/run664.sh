#!/usr/bin/env bash
# BC5 run 664 (exp 0155, the play shortcut as is; dispatches whose user data point into the staging ring journaled (FIND_VA), the 12 KiB copy destination snapshotted): Initial Setup > View All Settings > Visuals, the list scrolled down and up at 2 s a step; screenshots every 2 s (watch664.sh).
export BC5_RUN_CWD=$HOME/bc5-work/exp0155-cwd KYTY_BC5_SAVEDATA_DIR=$HOME/bc5-work/_SaveData-exp0155 KYTY_BC5_INPUT_CMD=$HOME/bc5-work/input664.cmd
export BC5_DIRECT_PKT_STATS=1
export BC5_DIRECT_FIND_VA=1122000000:1125000000
export BC5_DIRECT_SNAP=11e0e1c200:12288:997
exec ~/bc5-work/play-pkg-exp0155.sh
