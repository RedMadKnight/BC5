#!/usr/bin/env bash
# BC5 run 660 (exp 0155, graphics pieces off (BC5_DIRECT_PIECES_FULL and PIECES_DRY taken away)): Initial Setup > View All Settings > Visuals, the list scrolled down and up at 2 s a step; screenshots every 2 s (watch660.sh).
export BC5_RUN_CWD=$HOME/bc5-work/exp0155-cwd KYTY_BC5_SAVEDATA_DIR=$HOME/bc5-work/_SaveData-exp0155 KYTY_BC5_INPUT_CMD=$HOME/bc5-work/input660.cmd
export BC5_DIRECT_PKT_STATS=1
export BC5_UNSET="BC5_DIRECT_PIECES_FULL BC5_DIRECT_PIECES_DRY"
exec ~/bc5-work/play-pkg-exp0155.sh
