#!/usr/bin/env bash
# BC5 run 627 (exp 0155): the play shortcut with an empty save-data directory of its own (first-boot Initial Setup, then View All Settings > Visuals as in run 506), the pad script appended live between screenshots, BC5_DIRECT_PKT_STATS=1 for the filter drop tally.
export BC5_RUN_CWD=$HOME/bc5-work/exp0155-cwd KYTY_BC5_SAVEDATA_DIR=$HOME/bc5-work/_SaveData-exp0155 KYTY_BC5_INPUT_CMD=$HOME/bc5-work/input627.cmd BC5_DIRECT_PKT_STATS=1
exec ~/bc5-work/play-pkg-exp0155.sh
