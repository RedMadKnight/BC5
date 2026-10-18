#!/usr/bin/env bash
# BC5 run 671 (exp 0155, exp 0156: draw journal of the UI pixel shaders (09099c) in buffers of 4000+ dwords from 90 s): Initial Setup > View All Settings > Visuals, the list scrolled down and up at 2 s a step; screenshots every 2 s (watch671.sh).
export BC5_RUN_CWD=$HOME/bc5-work/exp0155-cwd KYTY_BC5_SAVEDATA_DIR=$HOME/bc5-work/_SaveData-exp0155 KYTY_BC5_INPUT_CMD=$HOME/bc5-work/input671.cmd
export BC5_DIRECT_DRAW_JOURNAL=90:100000:4000
export BC5_DIRECT_DRAW_JOURNAL_PS=09099c
exec ~/bc5-work/play-pkg-exp0155.sh
