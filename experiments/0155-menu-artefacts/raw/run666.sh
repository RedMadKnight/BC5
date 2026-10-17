#!/usr/bin/env bash
# BC5 run 666 (exp 0155, the emulator pinned to CPUs 0-3 (taskset): a CPU-timing probe): Initial Setup > View All Settings > Visuals, the list scrolled down and up at 2 s a step; screenshots every 2 s (watch666.sh).
export BC5_RUN_CWD=$HOME/bc5-work/exp0155-cwd KYTY_BC5_SAVEDATA_DIR=$HOME/bc5-work/_SaveData-exp0155 KYTY_BC5_INPUT_CMD=$HOME/bc5-work/input666.cmd
export BC5_DIRECT_PKT_STATS=1
export BC5_EMU_PREFIX="taskset -c 0-3"
exec ~/bc5-work/play-pkg-exp0155.sh
