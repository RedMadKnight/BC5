#!/usr/bin/env bash
# BC5 run 348 (RT dump of the small chain levels) (maintainer present): the second title with the settings of its play shortcut
# (as run 323) plus all indirect draws and the code aliases, for the menu and its background
# (F118). One cross at 80 s turns the screen reader off; the menu should follow; nothing more
# is pressed. Run inside the ubuntu distrobox.
export PACK_DIR=$HOME/bc5-data/sysmodules-pack-hle-ampr SAVE_DIR=$HOME/bc5-work/_SaveData-pkg-test348 HEAVY_PROBE=0
export EAGER_NAMES="RenderGpuWcLarge,RenderGpuWcSmall,RenderGpuRwLarge,RenderGpuRwSmall,CommitIABufferAllocator,AMM,RenderAlloc,Physics,Decal Job Scheduler,VisualEffectInstanceHeap,DynamicHeap,DynamicHeap Small,ComponentHeap,ComponentHeap Small,MaterialHeap,DDLHeap,Physics query allocator"
export BC5_RUN_ENV=$HOME/bc5-work/bc5-run.env.pkg-noflipdefer
export BC5_DIRECT_RT_DUMP="105;113d770000:1664:936:r11g11b10;1164d40000:240:135:r11g11b10;11d05b1000:120:68:r11g11b10;11d05bd000:60:34:r11g11b10;11d05c1000:30:17:r11g11b10;11d05c2000:15:9:r11g11b10;11cb2c0000:384:216:r32f;11cb2c0000:384:216:r11g11b10"
export BC5_DIRECT_INDIRECT_DRAWS=multi BC5_DIRECT_ALIASES=1
export KYTY_BC5_INPUT_CMD=$HOME/bc5-work/input348.cmd
exec ~/bc5-work/run-pkg.sh ~/bc5-data/pkg/game.pkg 130 --fullscreen
