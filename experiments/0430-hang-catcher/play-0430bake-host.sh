#!/usr/bin/env bash
# BC5 exp 0430 BAKE TEST (2026-11-18 evening; the maintainer: "Przygotuj mi też wersję lean bezpośrednio bez distro"): the
# second title on the private LEAN build with the hang fix built in (F10 + F4 + F16 + F18, no switch; patch d1388db0's unit
# 8eb42a10, binary pinned below), run on the Bazzite host without the ubuntu distrobox (exp 0423). Not a shared launcher.
# It changes nothing shared: the shared play-any.sh and play-pkg.sh run as they are (the lean session as the "BC5 emulator
# (lean, host)" shortcut has it, RT on in his input.cfg, his saves, ulimit -c 0, no learned windows, no JobArenaFix);
# only the binary is this build (BC5_EMU_LEAN for the menu, BC5_EMU for the title script), checked by md5 here.
set -u
LEAN_BIN=/home/kjaniszewski/bc5-work/exp0430/lean/kyty_emulator
WANT=85befb72
say() { echo "$*"; command -v notify-send > /dev/null 2>&1 && notify-send "BC5" "$*" 2> /dev/null; }
[ -x "$LEAN_BIN" ] && [ "$(md5sum < "$LEAN_BIN" | cut -c1-8)" = "$WANT" ] || { say "exp 0430: $LEAN_BIN is not the build $WANT"; exit 1; }
[ -e /run/.containerenv ] && { say "exp 0430: this launcher is for the host, not a container"; exit 1; }
unset BC5_GUARD_MAP_RULE BC5_GUARD_PRT_BG  # CLAUDE.md: never set in a launcher
export BC5_LEAN=1 BC5_EMU_LEAN=$LEAN_BIN BC5_EMU=$LEAN_BIN
exec /home/kjaniszewski/bc5-work/play-any.sh /home/kjaniszewski/bc5-data/games/PPSA03671
