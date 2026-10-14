#!/usr/bin/env bash
# BC5 run 377 (menu buffers dumped, scratch and layer users found; unattended, menu only): the second title with the settings of its play shortcut
# (as run 323) plus all indirect draws and the code aliases, for the menu and its background
# (F118). One cross at 80 s turns the screen reader off; the menu should follow; nothing more
# is pressed. Run inside the ubuntu distrobox.
export PACK_DIR=$HOME/bc5-data/sysmodules-pack-hle-ampr SAVE_DIR=$HOME/bc5-work/_SaveData-pkg-test377 HEAVY_PROBE=0
export EAGER_NAMES="RenderGpuWcLarge,RenderGpuWcSmall,RenderGpuRwLarge,RenderGpuRwSmall,CommitIABufferAllocator,AMM,RenderAlloc,Physics,Decal Job Scheduler,VisualEffectInstanceHeap,DynamicHeap,DynamicHeap Small,ComponentHeap,ComponentHeap Small,MaterialHeap,DDLHeap,Physics query allocator"
export BC5_RUN_ENV=$HOME/bc5-work/bc5-run.env.pkg-noflipdefer
export BC5_DIRECT_INDIRECT_DRAWS=multi BC5_DIRECT_ALIASES=1
export KYTY_BC5_INPUT_CMD=$HOME/bc5-work/input327.cmd
export BC5_DIRECT_REMEMBER_UNMAPPED=1 BC5_DIRECT_IB_DUMP=30:30000:100:700:/home/kjaniszewski/bc5-data/captures/ibdump-377 BC5_DIRECT_FIND_ALL=100:3:114c6c00,81db0100,80d36d00
exec ~/bc5-work/run-pkg.sh ~/bc5-data/pkg/game.pkg 110 --fullscreen
