#!/usr/bin/env bash
# BC5 run 427 (ASTRO BOT start, PFSC blocks inflated once; maintainer available): ASTRO BOT with its play
# settings (bc5-run.env) for 90 s, no input, to check the init_once fast path. Ubuntu distrobox.
while IFS= read -r line; do
  case "$line" in ""|"#"*) continue ;; esac
  key=${line%%=*}; val=${line#*=}
  [ "$key" = PLAY_ARGS ] || export "$key=$val"
done < $HOME/bc5-work/bc5-run.env
unset KYTY_BC5_INPUT_RECORD PLAY_CAPTURE
export BC5_DIRECT_TIMING=1 BC5_DIRECT_FRAME_PROFILE=1 RUN_SECONDS=60 BC5_MOUNT_STATS=1
exec ~/bc5-work/run-astro-kytyplus.sh
