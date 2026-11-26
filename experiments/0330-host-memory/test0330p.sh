#!/usr/bin/env bash
# BC5 experiment 0330: the test shortcut's host side (2026-10-26, F395). It starts the sampler beside the session, then the
# test launcher in the distrobox, as the first form of the shortcut did.
E=$HOME/bc5-work/exp0330; T=$(date +%Y%m%d-%H%M%S)
mkdir -p "$E/play"
pgrep '^kyty_emulator' > /dev/null || setsid nohup "$E/sample0330p.sh" "$E/play/mem-$T.txt" 7200 < /dev/null > /dev/null 2>&1 &
exec /usr/bin/distrobox enter ubuntu -- /usr/bin/env BC5_EMU="$E/kyty_emulator" "$E/play-pkg-0330t.sh"
