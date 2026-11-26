#!/usr/bin/env bash
# BC5 run 425 (intro start: APR reads on 8 threads, on-disk decoded block cache; maintainer available): the second title with the settings of its play shortcut
# (as run 323) plus all indirect draws and the code aliases, for the menu and its background
# (F118). One cross at 80 s turns the screen reader off; the menu should follow; nothing more
# is pressed. Run inside the ubuntu distrobox.
export PACK_DIR=$HOME/bc5-data/sysmodules-pack-hle-ampr SAVE_DIR=$HOME/bc5-work/_SaveData-pkg-test425 HEAVY_PROBE=0
export EAGER_NAMES="RenderGpuWcLarge,RenderGpuWcSmall,RenderGpuRwLarge,RenderGpuRwSmall,CommitIABufferAllocator,AMM,RenderAlloc,Physics,Decal Job Scheduler,VisualEffectInstanceHeap,DynamicHeap,DynamicHeap Small,ComponentHeap,ComponentHeap Small,MaterialHeap,DDLHeap,Physics query allocator"
export BC5_RUN_ENV=$HOME/bc5-work/bc5-run.env.pkg-noflipdefer
export BC5_DIRECT_INDIRECT_DRAWS=multi BC5_DIRECT_ALIASES=1
export KYTY_BC5_INPUT_CMD=$HOME/bc5-work/input373.cmd
export BC5_MOUNT_STATS=1 KYTY_BC5_APR_PARALLEL=8 BC5_MOUNT_DISK_CACHE=$HOME/bc5-data/cache/bc5-mount BC5_DIRECT_REMEMBER_UNMAPPED=1 BC5_DIRECT_PACE_FIX=11d0288100:100/170
exec ~/bc5-work/run-pkg.sh ~/bc5-data/pkg/game.pkg 30 --fullscreen
