#!/usr/bin/env bash
# BC5 run 650 (exp 0155, the play shortcut as is): Initial Setup swept down/up 10 times, screenshots per half-sweep (watch650.sh).
export BC5_RUN_CWD=$HOME/bc5-work/exp0155-cwd KYTY_BC5_SAVEDATA_DIR=$HOME/bc5-work/_SaveData-exp0155 KYTY_BC5_INPUT_CMD=$HOME/bc5-work/input650.cmd
export BC5_DIRECT_PKT_STATS=1
exec ~/bc5-work/play-pkg-exp0155.sh
