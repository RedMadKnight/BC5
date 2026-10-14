#!/usr/bin/env bash
# BC5 run 378 (menu: UI layer coverage and scratch dump; unattended, menu only): the second title with the settings of its play shortcut
# (as run 323) plus all indirect draws and the code aliases, for the menu and its background
# (F118). One cross at 80 s turns the screen reader off; the menu should follow; nothing more
# is pressed. Run inside the ubuntu distrobox.
export PACK_DIR=$HOME/bc5-data/sysmodules-pack-hle-ampr SAVE_DIR=$HOME/bc5-work/_SaveData-pkg-test378 HEAVY_PROBE=0
export EAGER_NAMES="RenderGpuWcLarge,RenderGpuWcSmall,RenderGpuRwLarge,RenderGpuRwSmall,CommitIABufferAllocator,AMM,RenderAlloc,Physics,Decal Job Scheduler,VisualEffectInstanceHeap,DynamicHeap,DynamicHeap Small,ComponentHeap,ComponentHeap Small,MaterialHeap,DDLHeap,Physics query allocator"
export BC5_RUN_ENV=$HOME/bc5-work/bc5-run.env.pkg-noflipdefer
export BC5_DIRECT_INDIRECT_DRAWS=multi BC5_DIRECT_ALIASES=1
export KYTY_BC5_INPUT_CMD=$HOME/bc5-work/input327.cmd
export BC5_DIRECT_REMEMBER_UNMAPPED=1 BC5_DIRECT_RT_DUMP="100;81db010000:3840:2160:rgba8;114c6c0000:2560:1440:rgba8" BC5_DIRECT_DRAW_JOURNAL=99:200
exec ~/bc5-work/run-pkg.sh ~/bc5-data/pkg/game.pkg 110 --fullscreen
