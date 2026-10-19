#!/usr/bin/env bash
# BC5 run 805 (exp 0165): chains held across the game thread's ioctls (ADR 0010 section B, BC5_DIRECT_CHAIN=2, hold 2 ms); route as 799.
export BC5_DIRECT_CHAIN=2 KYTY_BC5_VIDEOOUT_TRACE=1 KYTY_BC5_INPUT_CMD=$HOME/bc5-work/input805.cmd
exec ~/bc5-work/play-pkg-log.sh
