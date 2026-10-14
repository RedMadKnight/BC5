#!/usr/bin/env bash
# BC5 run 326 (maintainer present): the second title with all indirect draws and the code aliases
# (the settings of runs 272-278, bc5-run.env as before experiment 0060), which hang the GPU in the
# reflection traversal at ~150 s, plus snapshots of the traversal's instance-table window
# (F116/F118: base s[100:101] = 0x118c5f0000) every 4000 submissions. Started with the root hang
# watcher. Run inside the ubuntu distrobox.
export BC5_RUN_ENV=$HOME/bc5-work/bc5-run.env.before-0060
export BC5_DIRECT_INDIRECT_DRAWS=multi BC5_DIRECT_ALIASES=1
export BC5_DIRECT_SNAP=118c5f0000:262144:4000
export KYTY_BC5_INPUT_CMD=$HOME/bc5-work/input326.cmd
exec ~/bc5-work/run-pkg.sh ~/bc5-data/pkg/game.pkg 240
