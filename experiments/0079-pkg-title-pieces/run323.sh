#!/usr/bin/env bash
# BC5 run 323: the second title with the settings of its play shortcut (play-pkg.sh) and
# bc5-run.env, which now has BC5_DIRECT_PIECES_FULL=1 and BC5_DIRECT_PIECES_DRY=1 (ADR 0008).
# 180 s, no input. Run inside the ubuntu distrobox.
export PACK_DIR=$HOME/bc5-data/sysmodules-pack-hle-ampr SAVE_DIR=$HOME/bc5-work/_SaveData-pkg-play HEAVY_PROBE=0
export EAGER_NAMES="RenderGpuWcLarge,RenderGpuWcSmall,RenderGpuRwLarge,RenderGpuRwSmall,CommitIABufferAllocator,AMM,RenderAlloc,Physics,Decal Job Scheduler,VisualEffectInstanceHeap,DynamicHeap,DynamicHeap Small,ComponentHeap,ComponentHeap Small,MaterialHeap,DDLHeap,Physics query allocator"
exec ~/bc5-work/run-pkg.sh ~/bc5-data/pkg/game.pkg 180 --fullscreen
