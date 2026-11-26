#!/usr/bin/env bash
# BC5 exp 0432 item D: the maintainer's 09:46 scene (slot 4 of the read-only snapshot $SNAP, no input after the load,
# RT on), alternating arms, one run each in the order of $ORDER (default "D S D S O"):
#   D  the private build (DBIN), unmap-nowait on (its default)
#   S  the shared normal build as it is
#   O  the private build with BC5_DIRECT_UNMAP_NOWAIT=0: the old blocking wait, with D's counters
#   T  the ONE test build (TBIN: items D, A, V and S on); U, A, V, G: T with one item off; Z: T with every item off
# ROUTE=1 runs the long route instead of the scene (PLAY then counts from G; 1500 is the whole walk).
# After exp 0430's scene0430.sh. Tags d432<arm><k>. A run that is not NO_CRASH stops the series (LESSONS R55): a kernel
# GPU line or a fault is read before anything else runs. Stops also at ~/bc5-work/exp0432/STOP or at an emulator that
# is not ours. One run at a time; each run takes and frees its own BOX-LOCK line.
# usage (on the box, detached): SNAP=<dir holding TITLE2> DBIN=<binary> K0=0 bash scene0432.sh
set -u
ulimit -c 0
W=$HOME/bc5-work; E=$W/exp0432; N=$E/n; HERE=$(cd "$(dirname "$0")" && pwd)
SNAP=${SNAP:?the read-only snapshot dir}; [ -d "$SNAP/TITLE2" ] && [ ! -L "$SNAP" ] || { echo "scene0432: no $SNAP/TITLE2"; exit 1; }
DBIN=${DBIN:-/nonexistent}  # arms D and O
PLAY=${PLAY:-300}; k=${K0:?the last run number}
WORDS=$W/exp0413/n/words0413nz.txt; [ -s "$WORDS" ] || { echo "scene0432: no $WORDS"; exit 1; }
SB=$W/kytyplus-build/src/kyty_emulator
echo "scene0432 $(date +%T): snapshot $SNAP ($(cd "$SNAP" && find TITLE2 -type f -exec md5sum {} + | sort -k2 | md5sum | cut -c1-16)), play $PLAY s, order ${ORDER:-D S D S O}"
for arm in ${ORDER:-D S D S O}; do
  k=$((k + 1))
  [ -e "$E/STOP" ] && { echo "scene0432 $(date +%T): STOP file"; break; }
  pgrep '^kyty_emulator' > /dev/null && { echo "scene0432 $(date +%T): an emulator runs (not ours): stop"; break; }
  case "$arm" in
    D) bin=$DBIN; aw="" ;;
    S) bin=$SB; aw="" ;;
    O) bin=$DBIN; aw="BC5_DIRECT_UNMAP_NOWAIT=0" ;;
    T) bin=${TBIN:?the test build}; aw="" ;;                                 # the ONE test build, every item on
    U) bin=${TBIN:?the test build}; aw="BC5_DIRECT_UNMAP_NOWAIT=0" ;;        # ... without item D
    A) bin=${TBIN:?the test build}; aw="BC5_DIRECT_ANON_EVENTS=0" ;;         # ... item A off (its default since build 2)
    P) bin=${TBIN:?the test build}; aw="BC5_DIRECT_SLOT_PREALLOC=0" ;;       # ... without item P
    W) bin=${TBIN:?the test build}; aw="BC5_DIRECT_ANON_THREAD=0" ;;         # ... without item W
    V) bin=${TBIN:?the test build}; aw="BC5_DIRECT_VIEWS_KEPT=1" ;;          # ... WITH item V (off by default since build 4)
    X) bin=${TBIN:?the test build}; aw="BC5_DIRECT_MAPS_DIFF=verify" ;;      # ... WITH item X, checked against the old rebuild at every use (off by default)
    Y) bin=${TBIN:?the test build}; aw="BC5_DIRECT_MAPS_DIFF=1" ;;           # ... WITH item X, unchecked (only after an X run with 0 mismatches)
    G) bin=${TBIN:?the test build}; aw="BC5_DIRECT_SLOT_GROW=0" ;;           # ... without item S
    M) bin=${TBIN:?the test build}; aw="BC5_DIRECT_MAPS_FAST=0" ;;           # ... without item M
    Z) bin=${TBIN:?the test build}; aw="BC5_DIRECT_ANON_THREAD=0 BC5_DIRECT_SLOT_PREALLOC=0 BC5_DIRECT_MAPS_FAST=0 BC5_DIRECT_UNMAP_NOWAIT=0 BC5_DIRECT_ANON_EVENTS=0 BC5_DIRECT_VIEWS_KEPT=0 BC5_DIRECT_SLOT_GROW=0 KYTY_BC5_ANON_SYNC=verify" ;;  # every item off, exp 0415's verify counting event misses
    L) bin=${LBIN:?the lean test build}; aw="" ;;                            # the test build made with the lean build's commands (box0432.sh, LEAN=1)
    K) bin=$W/kytyplus-build-lean/src/kyty_emulator; aw="" ;;                # the shared lean build as it is
    *) echo "scene0432: arm $arm?"; break ;;
  esac
  t=d432$arm$k; while [ -e "$N/raw/$t-start.txt" ]; do t=${t}b; done
  [ "${FS:-0}" = 1 ] && aw="$aw KYTY_BC5_FRAME_STAT=$N/raw/$t-fs.txt"  # FS=1: exp 0415's per-job record (64 of every 512 frames), the same word in every arm
  want=$(md5sum < "$bin" | cut -d' ' -f1)
  echo "scene0432 $(date +%T): arm $arm, $t, ${want:0:8}"
  # shellcheck disable=SC2086
  [ -x "$bin" ] || { echo "scene0432: no $bin"; break; }
  if [ "${ROUTE:-0}" = 1 ]; then RUNENV="N_WALK_AFTER=1"; else RUNENV="N_SAVES=$SNAP N_SLOT=4 N_NOWALK=1"; fi  # ROUTE=1: the long route (fight record, then the walk) from exp 0425's named snapshot
  line=$(env $RUNENV N_FUSE=0 N_NOWD=1 ${SIDE:+N_SIDE=$SIDE} P_BIN=$bin P_WANT=$want P_WORDS=$WORDS bash "$HERE/run0432f.sh" "$t" "$arm" "$PLAY" $aw | grep "^$t ")
  echo "${line:-$t: no result line}" | cut -c1-600
  grep -a 'tag d432' "$N/raw/$t-play.log" 2> /dev/null | tail -1 | cut -c1-500
  case "$line" in *"; CLASS NO_CRASH;"*) ;; *) echo "scene0432 $(date +%T): $t not NO_CRASH: stop (R55)"; break ;; esac
  sleep 20
done
echo "scene0432 $(date +%T): done"
