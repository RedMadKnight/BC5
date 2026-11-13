#!/usr/bin/env bash
# BC5 exp 0412 (g412b): the maintainer's desktop shortcuts for the second build's arms and for the two ASTRO BOT plays
# (the top session's order, 2026-11-10 night), on shortcut0412.sh's pattern:
#   orphans    "BC5 emulator (0412 orphans)"   play-guard-0412.sh orphans
#   cap        "BC5 emulator (0412 cap)"       play-guard-0412.sh cap
#   astro-off  "BC5 Astro (0412 capture off)"  play-astro-guard-0412.sh off
#   astro-on   "BC5 Astro (0412 capture on)"   play-astro-guard-0412.sh on
#   astro-evcap "BC5 Astro (0412 events cap)"  play-astro-ev-0412.sh cap   (2026-11-11, the events-cap build ev412)
#   zo         "BC5 emulator (0412 zo - best of the night)"  play-guard-0412.sh zo
# Writes only the one .desktop file (made as a temporary file in ~/bc5-work/exp0412, validated, then moved); removes
# nothing. The other shortcuts stay as they are ("0412 ledger" and "0412 low" run the same wrapper, so the new build).
# usage (on the box): WANT_W=<md5 of the wrapper the shortcut runs> bash shortcut0412b.sh orphans|cap|zo|astro-off|astro-on
set -u
E=$HOME/bc5-work/exp0412; WANT_W=${WANT_W:?the md5 of the wrapper}
G="e11 unpacked's switches plus the guardian's ledger"; FU="fuse: the emulator is killed past 12,400 MiB in its cgroup instead of the box dying"
case "${1:-}" in
  orphans)   W=$E/play-guard-0412.sh; ARG=orphans; NAME="BC5 emulator (0412 orphans)"
             WHAT="$G + orphan release (BC5_DIRECT_LAZY_RELEASE=10,eager: pinned memory under no view for 10 s is unpinned); $FU; private build g412b"
             LOGS="log ~/bc5-work/exp0412/play-last.log; sampler lines ~/bc5-work/exp0412/sampler/" ;;
  cap)       W=$E/play-guard-0412.sh; ARG=cap; NAME="BC5 emulator (0412 cap)"
             WHAT="$G + orphan release + the pin cap acting at 11,600 MiB (new streaming chunks over it read as zeros on the GPU: textures or geometry can be missing); $FU; private build g412b"
             LOGS="log ~/bc5-work/exp0412/play-last.log; sampler lines ~/bc5-work/exp0412/sampler/" ;;
  zo)        W=$E/play-guard-0412.sh; ARG=zo; NAME="BC5 emulator (0412 zo - best of the night)"
             WHAT="$G + zero skip (the list scanned at his save on 2026-11-10 night: all-zero chunks of the two render heaps are not pinned) + orphan release that works with aliases (BC5_GUARD_SPLIT); in the night's scripted runs 0.5-0.7 GiB less pinned and no memory pressure; one GPU ring reset in five runs with the zero skip (the box recovered); $FU; private build g412d"
             LOGS="log ~/bc5-work/exp0412/play-last.log; sampler lines ~/bc5-work/exp0412/sampler/" ;;
  astro-off) W=$E/play-astro-guard-0412.sh; ARG=off; NAME="BC5 Astro (0412 capture off)"
             WHAT="ASTRO BOT on the shared build with PLAY_CAPTURE off (no journal), the memory sampler beside it; $FU"
             LOGS="log ~/bc5-work/exp0412/astro-last.log; sampler lines ~/bc5-work/exp0412/sampler/astro-*" ;;
  astro-on)  W=$E/play-astro-guard-0412.sh; ARG=on; NAME="BC5 Astro (0412 capture on)"
             WHAT="ASTRO BOT on the shared build with PLAY_CAPTURE on (as the play the kernel killed on 2026-11-10), the memory sampler beside it; $FU"
             LOGS="log ~/bc5-work/exp0412/astro-last.log; sampler lines ~/bc5-work/exp0412/sampler/astro-*" ;;
  astro-evcap) W=$E/play-astro-ev-0412.sh; ARG=cap; NAME="BC5 Astro (0412 events cap)"
             WHAT="ASTRO BOT on the private build ev412 (the shared source + a bound of 64 on an event's pending queue, KYTY_BC5_EVENT_PENDING_CAP=64: the fix candidate for the host leak of 217 MiB/min), capture off, the memory sampler beside it; $FU"
             LOGS="log ~/bc5-work/exp0412/astro-ev-last.log; sampler lines ~/bc5-work/exp0412/sampler/astro-*" ;;
  pkg-evcap) W=$E/play-pkg-ev-0412.sh; ARG=cap; NAME="BC5 emulator (0412 events cap, unpacked)"
             WHAT="the second title, unpacked, on the private build ev412 (the SHARED source of 2026-11-02 + a bound of 64 on an event's pending queue; none of the e-series or guardian switches), the memory sampler beside it; $FU"
             LOGS="log ~/bc5-work/exp0412/pkg-ev-last.log; sampler lines ~/bc5-work/exp0412/sampler/play-*-evcap.txt" ;;
  zoe)       W=$E/play-guard-0412.sh; ARG=zoe; NAME="BC5 emulator (0412 zo + events cap)"
             WHAT="$G + zero skip + orphan release (the arm zo) + a bound of 64 on an event's pending queue (KYTY_BC5_EVENT_PENDING_CAP=64, the fix of ASTRO BOT's host leak carried into this line); $FU; private build g412e"
             LOGS="log ~/bc5-work/exp0412/play-last.log; sampler lines ~/bc5-work/exp0412/sampler/" ;;
  fast)      W=$E/play-guard-0412.sh; ARG=fast; NAME="BC5 emulator (0412 fast ranges)"
             WHAT="$G + KYTY_BC5_RANGES_FAST=1 (the host's range lookup by binary search: 30 percent more frames in both load phases of the scripted run) + orphan release + events cap; NO zero skip (it had 2 GPU ring timeouts in 8 runs); $FU; private build g412f"
             LOGS="log ~/bc5-work/exp0412/play-last.log; sampler lines ~/bc5-work/exp0412/sampler/" ;;
  fast2)     W=$E/play-guard-0412.sh; ARG=fast2; NAME="BC5 emulator (0412 fast2)"
             WHAT="$G + both fixes of the host's memory tables (KYTY_BC5_RANGES_FAST, KYTY_BC5_PHYSMAP_SORTED: about 50 percent more frames in the load phases of the scripted run than g412e) + orphan release with idle 4 s and forget 10 s + events cap; NO zero skip; $FU; private build g412i (the code of g412h, with line tables)"
             LOGS="log ~/bc5-work/exp0412/play-last.log; sampler lines ~/bc5-work/exp0412/sampler/" ;;
  fast4)     W=$E/play-guard-0412.sh; ARG=fast4; NAME="BC5 emulator (0412 fast4)"
             WHAT="$G + both fixes of the host's memory tables + orphan release with idle 30 s + events cap + the four heaps the title mapped without a GPU bit are not pinned (BC5_GUARD_NOGPU_UNPIN=Physics,ComponentHeap,DynamicHeap,InitAllocator: about 1 GiB less pinned in the scripted runs; the GPU gets zeros there); NO zero skip, no hard stop, no catchers; $FU; private build g412s; the picture has not been looked at yet"
             LOGS="log ~/bc5-work/exp0412/play-last.log; sampler lines ~/bc5-work/exp0412/sampler/" ;;
  fast5)     W=$E/play-guard-0412.sh; ARG=fast5; NAME="BC5 emulator (0412 fast5)"
             WHAT="$G + both fixes of the host's memory tables + orphan release with idle 30 s + events cap + the zero skip with its poll before every submission (BC5_DIRECT_ZERO_SKIP, BC5_GUARD_ZSKIP_POLL_SUBMIT: about 650 MiB less pinned, nine scripted runs without a GPU hang, README section 40); $FU; private build g412u"
             LOGS="log ~/bc5-work/exp0412/play-last.log; sampler lines ~/bc5-work/exp0412/sampler/" ;;
  fast6)     W=$E/play-guard-0412.sh; ARG=fast6; NAME="BC5 emulator (0412 fast6)"
             WHAT="$G + fast5 (table fixes, events cap, zero skip with its poll before every submission, fixed after the review) with the orphan release at 10 s idle and the fuse at 13,000 MiB (README section 46); private build g412v"
             LOGS="log ~/bc5-work/exp0412/play-last.log; sampler lines ~/bc5-work/exp0412/sampler/" ;;
  lean6)     W=$E/play-lean-0412.sh; ARG=; NAME="BC5 emulator (0412 lean6)"
             WHAT="the LEAN version of fast6 (README sections 43 and 46): binary built without journal, traces, tallies and this experiment's catchers; no direct.log, no sampler, no counters, no MangoHud, no log file; only the memory fuse stays (13,000 MiB)"
             LOGS="no logs by design" ;;
  fast7)     W=$E/play-guard-0412.sh; ARG=fast7; NAME="BC5 emulator (0412 fast7)"
             WHAT="$G + fast5 (table fixes, events cap, orphan release at 30 s, zero skip with its poll before every submission, fixed after the review) with the fuse at 13,000 MiB instead of 12,400 (README section 46); private build g412v"
             LOGS="log ~/bc5-work/exp0412/play-last.log; sampler lines ~/bc5-work/exp0412/sampler/" ;;
  lean7)     W=$E/play-lean-0412.sh; ARG=; NAME="BC5 emulator (0412 lean7)"
             WHAT="the LEAN version of fast7 (README sections 43 and 46): binary built without journal, traces, tallies and this experiment's catchers; no direct.log, no sampler, no counters, no MangoHud, no log file; only the memory fuse stays (13,000 MiB)"
             LOGS="no logs by design" ;;
  lean5)     W=$E/play-lean-0412.sh; ARG=; NAME="BC5 emulator (0412 lean5)"
             WHAT="the LEAN version of fast5 (README section 43): binary built without journal, traces, tallies and this experiment's catchers; no direct.log, no sampler, no counters, no MangoHud, no log file; only the memory fuse stays"
             LOGS="no logs by design" ;;
  k1rcut)    W=$E/play-guard-0412.sh; ARG=k1rcut; NAME="BC5 emulator (0412 K1R cutscena)"
             WHAT="fast9's words on the private build g412zd (shared tree B + K1r): never-written memory reads as zeros on the GPU (BC5_GUARD_K1R=1), a packet's unimported operand is imported (BC5_GUARD_K1_FILTER=1), no learned windows, no e11 reset-replay words; a GPU fault ends the game with a record in ~/bc5-data/captures/faults/ (README sections 71-73); fuse 13,000 MiB"
             LOGS="log ~/bc5-work/exp0412/play-last.log; sampler lines ~/bc5-work/exp0412/sampler/" ;;
  *) echo "usage: shortcut0412b.sh k1rcut|orphans|cap|zo|zoe|fast|fast2|fast4|fast5|fast6|fast7|lean5|lean6|lean7|astro-off|astro-on|astro-evcap|pkg-evcap"; exit 1 ;;
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
Exec=/usr/bin/bash $W${ARG:+ $ARG}
Icon=applications-games
Terminal=false
Categories=Game;
StartupNotify=false
EOF
if command -v desktop-file-validate > /dev/null; then desktop-file-validate "$t" || { rm -f "$t"; echo "the .desktop file is not valid: stop"; exit 1; }; fi
if [ -e "$D" ]; then k=$E/desktop-before-$(date +%Y%m%d-%H%M%S)-$1.bak; cp -p "$D" "$k" && echo "kept the old shortcut as $k"; fi
chmod +x "$t" && mv -fT "$t" "$D" || { rm -f "$t"; echo "cannot write $D"; exit 1; }
echo "shortcut $D, md5 $(m "$D")"; grep -E '^(Name|Exec)=' "$D"
