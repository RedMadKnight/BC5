#!/usr/bin/env bash
# BC5 run 670 (exp 0155, exp 0156: draw journal of small-target draws (<=1024 px) in buffers of 4000+ dwords from 90 s): Initial Setup > View All Settings > Visuals, the list scrolled down and up at 2 s a step; screenshots every 2 s (watch670.sh).
export BC5_RUN_CWD=$HOME/bc5-work/exp0155-cwd KYTY_BC5_SAVEDATA_DIR=$HOME/bc5-work/_SaveData-exp0155 KYTY_BC5_INPUT_CMD=$HOME/bc5-work/input670.cmd
export BC5_DIRECT_DRAW_JOURNAL=90:3000:4000:1024
exec ~/bc5-work/play-pkg-exp0155.sh
