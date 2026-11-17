#!/usr/bin/env bash
# BC5 exp 0432 item D: the maintainer's 09:46 scene (slot 4 of the read-only snapshot $SNAP, no input after the load,
# RT on), alternating arms, one run each in the order of $ORDER (default "D S D S O"):
#   D  the private build (DBIN), unmap-nowait on (its default)
#   S  the shared normal build as it is
#   O  the private build with BC5_DIRECT_UNMAP_NOWAIT=0: the old blocking wait, with D's counters
# After exp 0430's scene0430.sh. Tags d432<arm><k>. A run that is not NO_CRASH stops the series (LESSONS R55): a kernel
# GPU line or a fault is read before anything else runs. Stops also at ~/bc5-work/exp0432/STOP or at an emulator that
# is not ours. One run at a time; each run takes and frees its own BOX-LOCK line.
# usage (on the box, detached): SNAP=<dir holding PPSA03671> DBIN=<binary> K0=0 bash scene0432.sh
set -u
ulimit -c 0
W=$HOME/bc5-work; E=$W/exp0432; N=$E/n; HERE=$(cd "$(dirname "$0")" && pwd)
SNAP=${SNAP:?the read-only snapshot dir}; [ -d "$SNAP/PPSA03671" ] && [ ! -L "$SNAP" ] || { echo "scene0432: no $SNAP/PPSA03671"; exit 1; }
DBIN=${DBIN:?the private binary}; [ -x "$DBIN" ] || { echo "scene0432: no $DBIN"; exit 1; }
PLAY=${PLAY:-300}; k=${K0:?the last run number}
WORDS=$W/exp0413/n/words0413nz.txt; [ -s "$WORDS" ] || { echo "scene0432: no $WORDS"; exit 1; }
SB=$W/kytyplus-build/src/kyty_emulator
echo "scene0432 $(date +%T): snapshot $SNAP ($(cd "$SNAP" && find PPSA03671 -type f -exec md5sum {} + | sort -k2 | md5sum | cut -c1-16)), play $PLAY s, order ${ORDER:-D S D S O}"
for arm in ${ORDER:-D S D S O}; do
  k=$((k + 1))
  [ -e "$E/STOP" ] && { echo "scene0432 $(date +%T): STOP file"; break; }
  pgrep '^kyty_emulator' > /dev/null && { echo "scene0432 $(date +%T): an emulator runs (not ours): stop"; break; }
  case "$arm" in
    D) bin=$DBIN; aw="" ;;
    S) bin=$SB; aw="" ;;
    O) bin=$DBIN; aw="BC5_DIRECT_UNMAP_NOWAIT=0" ;;
    *) echo "scene0432: arm $arm?"; break ;;
  esac
  t=d432$arm$k; while [ -e "$N/raw/$t-start.txt" ]; do t=${t}b; done
  want=$(md5sum < "$bin" | cut -d' ' -f1)
  echo "scene0432 $(date +%T): arm $arm, $t, ${want:0:8}"
  # shellcheck disable=SC2086
  line=$(N_SAVES=$SNAP N_SLOT=4 N_NOWALK=1 N_FUSE=0 N_NOWD=1 ${SIDE:+N_SIDE=$SIDE} P_BIN=$bin P_WANT=$want P_WORDS=$WORDS bash "$HERE/run0432f.sh" "$t" "$arm" "$PLAY" $aw | grep "^$t ")
  echo "${line:-$t: no result line}" | cut -c1-600
  grep -a 'tag d432' "$N/raw/$t-play.log" 2> /dev/null | tail -1 | cut -c1-500
  case "$line" in *"; CLASS NO_CRASH;"*) ;; *) echo "scene0432 $(date +%T): $t not NO_CRASH: stop (R55)"; break ;; esac
  sleep 20
done
echo "scene0432 $(date +%T): done"
