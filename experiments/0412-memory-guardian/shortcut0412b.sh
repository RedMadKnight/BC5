#!/usr/bin/env bash
# BC5 exp 0412 (g412b): the maintainer's desktop shortcuts for the second build's arms and for the two ASTRO BOT plays
# (the top session's order, 2026-11-10 night), on shortcut0412.sh's pattern:
#   orphans    "BC5 emulator (0412 orphans)"   play-guard-0412.sh orphans
#   cap        "BC5 emulator (0412 cap)"       play-guard-0412.sh cap
#   astro-off  "BC5 Astro (0412 capture off)"  play-astro-guard-0412.sh off
#   astro-on   "BC5 Astro (0412 capture on)"   play-astro-guard-0412.sh on
# Writes only the one .desktop file (made as a temporary file in ~/bc5-work/exp0412, validated, then moved); removes
# nothing. The other shortcuts stay as they are ("0412 ledger" and "0412 low" run the same wrapper, so the new build).
# usage (on the box): WANT_W=<md5 of the wrapper the shortcut runs> bash shortcut0412b.sh orphans|cap|astro-off|astro-on
set -u
E=$HOME/bc5-work/exp0412; WANT_W=${WANT_W:?the md5 of the wrapper}
G="e11 unpacked's switches plus the guardian's ledger"; FU="fuse: the emulator is killed past 12,300 MiB in its cgroup instead of the box dying"
case "${1:-}" in
  orphans)   W=$E/play-guard-0412.sh; ARG=orphans; NAME="BC5 emulator (0412 orphans)"
             WHAT="$G + orphan release (BC5_DIRECT_LAZY_RELEASE=10,eager: pinned memory under no view for 10 s is unpinned); $FU; private build g412b"
             LOGS="log ~/bc5-work/exp0412/play-last.log; sampler lines ~/bc5-work/exp0412/sampler/" ;;
  cap)       W=$E/play-guard-0412.sh; ARG=cap; NAME="BC5 emulator (0412 cap)"
             WHAT="$G + orphan release + the pin cap acting at 11,600 MiB (new streaming chunks over it read as zeros on the GPU: textures or geometry can be missing); $FU; private build g412b"
             LOGS="log ~/bc5-work/exp0412/play-last.log; sampler lines ~/bc5-work/exp0412/sampler/" ;;
  astro-off) W=$E/play-astro-guard-0412.sh; ARG=off; NAME="BC5 Astro (0412 capture off)"
             WHAT="ASTRO BOT on the shared build with PLAY_CAPTURE off (no journal), the memory sampler beside it; $FU"
             LOGS="log ~/bc5-work/exp0412/astro-last.log; sampler lines ~/bc5-work/exp0412/sampler/astro-*" ;;
  astro-on)  W=$E/play-astro-guard-0412.sh; ARG=on; NAME="BC5 Astro (0412 capture on)"
             WHAT="ASTRO BOT on the shared build with PLAY_CAPTURE on (as the play the kernel killed on 2026-11-10), the memory sampler beside it; $FU"
             LOGS="log ~/bc5-work/exp0412/astro-last.log; sampler lines ~/bc5-work/exp0412/sampler/astro-*" ;;
  *) echo "usage: shortcut0412b.sh orphans|cap|astro-off|astro-on"; exit 1 ;;
esac
DESK=$(xdg-user-dir DESKTOP 2> /dev/null); DESK=${DESK:-$HOME/Pulpit}
m() { md5sum < "$1" 2> /dev/null | cut -d' ' -f1; }
pgrep '^kyty_emulator' > /dev/null && { echo "an emulator runs: stop"; exit 1; }
[ "$(m "$W")" = "$WANT_W" ] || { echo "$W is not $WANT_W: stop"; exit 1; }
bash -n "$W" || { echo "$W does not parse: stop"; exit 1; }
[ -d "$DESK" ] && [ ! -L "$DESK" ] || { echo "no desktop directory $DESK: stop"; exit 1; }
D="$DESK/$NAME.desktop"
[ ! -e "$D" ] || grep -qxF "Name=$NAME" "$D" || { echo "$D exists and is not ours: stop"; exit 1; }
t=$E/shortcut-0412b.tmp.$$.desktop
cat > "$t" << EOF
[Desktop Entry]
Type=Application
Version=1.0
Name=$NAME
Comment=BC5 exp 0412 (2026-11-10): $WHAT; starts the game directly; $LOGS
Exec=/usr/bin/bash $W $ARG
Icon=applications-games
Terminal=false
Categories=Game;
StartupNotify=false
EOF
if command -v desktop-file-validate > /dev/null; then desktop-file-validate "$t" || { rm -f "$t"; echo "the .desktop file is not valid: stop"; exit 1; }; fi
if [ -e "$D" ]; then k=$E/desktop-before-$(date +%Y%m%d-%H%M%S)-$1.bak; cp -p "$D" "$k" && echo "kept the old shortcut as $k"; fi
chmod +x "$t" && mv -fT "$t" "$D" || { rm -f "$t"; echo "cannot write $D"; exit 1; }
echo "shortcut $D, md5 $(m "$D")"; grep -E '^(Name|Exec)=' "$D"
