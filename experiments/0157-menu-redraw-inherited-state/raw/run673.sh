#!/usr/bin/env bash
# BC5 run 673 (exp 0155, exp 0157: UI draws journaled, FIND of the atlases with tables, RT dumps of the three atlases every 2 s, APR sync as before): Initial Setup > View All Settings > Visuals, the list scrolled down and up at 2 s a step; screenshots every 2 s (watch673.sh).
export BC5_RUN_CWD=$HOME/bc5-work/exp0155-cwd KYTY_BC5_SAVEDATA_DIR=$HOME/bc5-work/_SaveData-exp0155 KYTY_BC5_INPUT_CMD=$HOME/bc5-work/input673.cmd
export BC5_DIRECT_DRAW_JOURNAL=90:100000
export BC5_DIRECT_DRAW_JOURNAL_PS=09099c
export BC5_DIRECT_DRAW_JOURNAL_FIND=11b2dc00,11b0ec00,11b15c00
export BC5_DIRECT_RT_DUMP="112;11b2dc0000:1024:1024:r8;11b0ec0000:1024:1024:r16f;11b15c0000:1024:1024:rgba8"
export BC5_DIRECT_RT_DUMP_EVERY=2
export KYTY_BC5_APR_SYNC=1
exec ~/bc5-work/play-pkg-exp0155.sh
