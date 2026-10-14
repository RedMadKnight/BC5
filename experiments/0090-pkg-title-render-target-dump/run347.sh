#!/usr/bin/env bash
# BC5 run 347 (shortcut settings, RT dump at 105 s) (maintainer present): the second title with the settings of its play shortcut
# (as run 323) plus all indirect draws and the code aliases, for the menu and its background
# (F118). One cross at 80 s turns the screen reader off; the menu should follow; nothing more
# is pressed. Run inside the ubuntu distrobox.
export PACK_DIR=$HOME/bc5-data/sysmodules-pack-hle-ampr SAVE_DIR=$HOME/bc5-work/_SaveData-pkg-test347 HEAVY_PROBE=0
export EAGER_NAMES="RenderGpuWcLarge,RenderGpuWcSmall,RenderGpuRwLarge,RenderGpuRwSmall,CommitIABufferAllocator,AMM,RenderAlloc,Physics,Decal Job Scheduler,VisualEffectInstanceHeap,DynamicHeap,DynamicHeap Small,ComponentHeap,ComponentHeap Small,MaterialHeap,DDLHeap,Physics query allocator"
export BC5_RUN_ENV=$HOME/bc5-work/bc5-run.env.pkg-noflipdefer
export BC5_DIRECT_RT_DUMP="105;113d770000:1664:936:r11g11b10;113f230000:1664:936:r32f;1164a00000:960:540:r11g11b10;1164c80000:480:270:r11g11b10;1167a20000:832:468:r11g11b10;11cb2c0000:384:216:r32f;114c6c0000:2560:1440:rgba8"
export BC5_DIRECT_INDIRECT_DRAWS=multi BC5_DIRECT_ALIASES=1
export KYTY_BC5_INPUT_CMD=$HOME/bc5-work/input347.cmd
exec ~/bc5-work/run-pkg.sh ~/bc5-data/pkg/game.pkg 130 --fullscreen
