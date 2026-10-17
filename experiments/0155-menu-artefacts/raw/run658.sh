#!/usr/bin/env bash
# BC5 run 658 (exp 0155, the play shortcut as is, with the ranges dump and snapshots of the 720 KiB copies destination): Initial Setup > View All Settings > Visuals, the list scrolled down and up at 2 s a step; screenshots every 2 s (watch658.sh).
export BC5_RUN_CWD=$HOME/bc5-work/exp0155-cwd KYTY_BC5_SAVEDATA_DIR=$HOME/bc5-work/_SaveData-exp0155 KYTY_BC5_INPUT_CMD=$HOME/bc5-work/input658.cmd
export BC5_DIRECT_PKT_STATS=1
export BC5_DIRECT_RANGES_DUMP=1
export BC5_DIRECT_SNAP=11f0d1cc00:720896:1500
exec ~/bc5-work/play-pkg-exp0155.sh
