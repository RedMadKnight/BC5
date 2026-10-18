#!/usr/bin/env bash
# BC5 run 674 (exp 0155, exp 0157: UI draws journaled, the UI layer list area dumped every 2 s (crop 0,172 2112x1340), APR sync as before): Initial Setup > View All Settings > Visuals, the list scrolled down and up at 2 s a step; screenshots every 2 s (watch674.sh).
export BC5_RUN_CWD=$HOME/bc5-work/exp0155-cwd KYTY_BC5_SAVEDATA_DIR=$HOME/bc5-work/_SaveData-exp0155 KYTY_BC5_INPUT_CMD=$HOME/bc5-work/input674.cmd
export BC5_DIRECT_DRAW_JOURNAL=90:100000
export BC5_DIRECT_DRAW_JOURNAL_PS=09099c
export BC5_DIRECT_DRAW_JOURNAL_FIND=11b2dc00
export BC5_DIRECT_RT_DUMP="112;layer:3840:2160:rgba8@0,172,2112,1340"
export BC5_DIRECT_RT_DUMP_EVERY=2
export KYTY_BC5_APR_SYNC=1
exec ~/bc5-work/play-pkg-exp0155.sh
