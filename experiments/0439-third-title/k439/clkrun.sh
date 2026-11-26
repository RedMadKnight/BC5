#!/usr/bin/env bash
# BC5 exp 0439: the Performance run with the 20-Hz clock sampler (clk439.sh), the umr watchdog off, FLAT=1, ring layout default.
cd "$HOME/bc5-work/exp0439" || exit 1
bash k439/clk439.sh runs/clk439.txt &
T3P6_SUFFIX=c T3P6_FLAT=1 T3S_NO_UMR=1 bash k439/t3p6.sh 389521e4
wait
