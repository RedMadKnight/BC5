#!/usr/bin/env bash
# BC5 run 659 (exp 0155, compute-buffer DMA sources copied at submission too (BC5_DIRECT_DMA_SNAPSHOT_ACB=1)): Initial Setup > View All Settings > Visuals, the list scrolled down and up at 2 s a step; screenshots every 2 s (watch659.sh).
export BC5_RUN_CWD=$HOME/bc5-work/exp0155-cwd KYTY_BC5_SAVEDATA_DIR=$HOME/bc5-work/_SaveData-exp0155 KYTY_BC5_INPUT_CMD=$HOME/bc5-work/input659.cmd
export BC5_DIRECT_PKT_STATS=1
export BC5_DIRECT_DMA_SNAPSHOT_ACB=1
exec ~/bc5-work/play-pkg-exp0155.sh
