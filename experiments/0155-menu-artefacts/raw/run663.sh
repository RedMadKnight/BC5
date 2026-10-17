#!/usr/bin/env bash
# BC5 run 663 (exp 0155, DMA sources copied from 64 KiB only (BC5_DIRECT_DMA_SNAPSHOT=65536: the 12 KiB per-frame copy left in place)): Initial Setup > View All Settings > Visuals, the list scrolled down and up at 2 s a step; screenshots every 2 s (watch663.sh).
export BC5_RUN_CWD=$HOME/bc5-work/exp0155-cwd KYTY_BC5_SAVEDATA_DIR=$HOME/bc5-work/_SaveData-exp0155 KYTY_BC5_INPUT_CMD=$HOME/bc5-work/input663.cmd
export BC5_DIRECT_PKT_STATS=1
export BC5_OVERRIDE=BC5_DIRECT_DMA_SNAPSHOT=65536
exec ~/bc5-work/play-pkg-exp0155.sh
