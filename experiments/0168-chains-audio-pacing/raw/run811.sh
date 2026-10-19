#!/usr/bin/env bash
# BC5 run 811 (exp 0167): gameplay from the save with the stall watchdog (all threads dumped when the journal stops for 400 ms).
export KYTY_BC5_AUDIO_TRACE=1 KYTY_BC5_VIDEOOUT_TRACE=1 KYTY_BC5_SAVE_TRACE=1 KYTY_BC5_INPUT_CMD=$HOME/bc5-work/input811.cmd
exec ~/bc5-work/play-pkg-log.sh
