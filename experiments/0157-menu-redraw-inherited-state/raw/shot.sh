#!/usr/bin/env bash
# BC5: wait $2 seconds, then one full-screen screenshot to ~/bc5-work/shots${SHOTS:-280}/$1.jpg (private, chat only)
sleep "${2:-0}"
D=~/bc5-work/shots${SHOTS:-280}; mkdir -p "$D"
XDG_RUNTIME_DIR=/run/user/1000 WAYLAND_DISPLAY=wayland-0 spectacle -b -n -f -o "$D/$1.png" >/dev/null 2>&1
python3 -c "from PIL import Image; im=Image.open(\"$D/$1.png\").convert(\"RGB\"); im.thumbnail((1280,720)); im.save(\"$D/$1.jpg\", quality=80)" 2>/dev/null || magick "$D/$1.png" -resize 1280x720 -quality 80 "$D/$1.jpg"
ls -la "$D/$1.jpg"; pgrep -x kyty_emulator >/dev/null && echo running || echo NOT-running
