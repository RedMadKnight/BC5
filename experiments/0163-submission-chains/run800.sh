#!/usr/bin/env bash
# BC5 run 800 (exp 0163): as 799 with the submission chains (ADR 0010, BC5_DIRECT_CHAIN=1).
export BC5_DIRECT_CHAIN=1 KYTY_BC5_VIDEOOUT_TRACE=1 KYTY_BC5_INPUT_CMD=$HOME/bc5-work/input800.cmd
exec ~/bc5-work/play-pkg-log.sh
