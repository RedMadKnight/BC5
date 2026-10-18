#!/usr/bin/env bash
# BC5 run 682 (exp 0155, exp 0157: layer crop dumped at the completion of every UI buffer, compute-queue buffers journaled, FIND layer): Initial Setup > View All Settings > Visuals, the list scrolled down and up at 2 s a step; screenshots every 2 s (watch682.sh).
export BC5_RUN_CWD=$HOME/bc5-work/exp0155-cwd KYTY_BC5_SAVEDATA_DIR=$HOME/bc5-work/_SaveData-exp0155 KYTY_BC5_INPUT_CMD=$HOME/bc5-work/input682.cmd
export BC5_DIRECT_DRAW_JOURNAL=90:100000
export BC5_DIRECT_DRAW_JOURNAL_PS=09099c
export BC5_DIRECT_DRAW_JOURNAL_ACB=1
export BC5_DIRECT_DRAW_JOURNAL_FIND=11b2dc00,layer
export BC5_DIRECT_RT_DUMP="112;layer:3840:2160:rgba8@0,172,1920,928"
export BC5_DIRECT_RT_DUMP_EVERY=1000
export BC5_DIRECT_RT_DUMP_AT_COMPLETION=1
export KYTY_BC5_APR_SYNC=1
export BC5_DIRECT_IB_DUMP=0:0:90:600:/home/kjaniszewski/bc5-data/captures/exp0157-ib682
exec ~/bc5-work/play-pkg-exp0155.sh
