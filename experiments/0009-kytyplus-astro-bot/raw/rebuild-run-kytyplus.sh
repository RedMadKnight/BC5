#!/usr/bin/env bash
set -u; S=$(date +%s)
cmake --build ~/bc5-work/kytyplus-build --target kyty_emulator -j8 2>&1 | grep -i "error\|warning: unused\|Linking" | head -5
echo "rebuild exit ${PIPESTATUS[0]} after $(( $(date +%s) - S )) s"
KYTY_GUEST_MEMORY_MB=13824 SDL_VIDEODRIVER=wayland RUN_SECONDS=240 ~/bc5-work/run-astro-kytyplus.sh
