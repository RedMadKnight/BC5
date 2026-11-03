#!/usr/bin/env bash
# BC5 exp 0388, memory: the maintainer's play on the private zero-skip build, with the skip on or off, the shared launcher,
# his saves and his input.cfg, which it does not change. usage: play0389z.sh on|off
set -u
BIN=$HOME/bc5-work/exp0388/z/kyty_emulator; L=$HOME/bc5-work/exp0388/m/zero-list-moving.txt
case "${1:-}" in on) SK=(BC5_DIRECT_ZERO_SKIP="$L") ;; off) SK=() ;; *) echo "play0389z: on or off"; exit 1 ;; esac
pgrep '^kyty_emulator' > /dev/null && { echo "play0389z: an emulator runs"; exit 1; }
[ ! -s "$HOME/bc5-work/BOX-LOCK" ] || { echo "play0389z: the box is locked: $(cat "$HOME/bc5-work/BOX-LOCK")"; exit 1; }
[ -x "$BIN" ] && [ -s "$L" ] || { echo "play0389z: no binary or list"; exit 1; }
echo "play0389z: skip $1, binary $(md5sum < "$BIN" | cut -c1-8), list $(md5sum < "$L" | cut -c1-8), the shared launcher $(md5sum < "$HOME/bc5-work/play-pkg.sh" | cut -c1-8)"
exec distrobox enter ubuntu -- env BC5_EMU="$BIN" "${SK[@]}" "$HOME/bc5-work/play-pkg.sh"
