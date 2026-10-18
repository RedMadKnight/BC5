#!/usr/bin/env bash
# BC5 run 687 (exp 0155, exp 0157: control on the final build, no prefix (APR sync only): rate and fps today): Initial Setup > View All Settings > Visuals, the list scrolled down and up at 2 s a step; screenshots every 2 s (watch687.sh).
export BC5_RUN_CWD=$HOME/bc5-work/exp0155-cwd KYTY_BC5_SAVEDATA_DIR=$HOME/bc5-work/_SaveData-exp0155 KYTY_BC5_INPUT_CMD=$HOME/bc5-work/input687.cmd
export KYTY_BC5_APR_SYNC=1
exec ~/bc5-work/play-pkg-exp0155.sh
