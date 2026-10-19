#!/usr/bin/env bash
# BC5 run 0165a (exp 0165 follow-up, chain session only): audio pacing with chains across ioctls (BC5_DIRECT_CHAIN=2), route as 799; run 811 is the off reference.
export BC5_DIRECT_CHAIN=2 KYTY_BC5_AUDIO_TRACE=1 KYTY_BC5_VIDEOOUT_TRACE=1 KYTY_BC5_INPUT_CMD=$HOME/bc5-work/input0165a.cmd
exec ~/bc5-work/play-pkg-log.sh
