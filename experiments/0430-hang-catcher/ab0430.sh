#!/usr/bin/env bash
# BC5 exp 0430: the interleaved A/B of the night of 2026-11-17 (the top session's plan (b)): the shared build (control,
# way 2 on, no fix) against build 7 (F3 + F4, the shared form + private archive), alternating on the same route, one run
# at a time through chain0430.sh (each run takes and frees its own BOX-LOCK line). Order: $ORDER (default C F C), tags
# h430C<k> / h430F<k> continuing the night's numbering (KC0 / KF0). Stops at the first run whose class is not NO_CRASH
# (R55) or at ~/bc5-work/exp0430/STOP. CATCH=swap: the fix's switch words (ignored by the control), the timeout probe.
# usage (on the box, detached): KC0=1 KF0=4 bash ab0430.sh
set -u
W=$HOME/bc5-work; E=$W/exp0430; HERE=$(cd "$(dirname "$0")" && pwd)
KC=${KC0:?the last control number}; KF=${KF0:?the last build-7 number}
for arm in ${ORDER:-C F C}; do
  [ -e "$E/STOP" ] && { echo "ab0430 $(date +%T): STOP file"; break; }
  if [ "$arm" = C ]; then bin=$W/kytyplus-build/src/kyty_emulator; tp=h430C; k0=$KC; KC=$((KC + 1))
  else bin=$E/b7/kyty_emulator; tp=h430F; k0=$KF; KF=$((KF + 1)); fi
  echo "ab0430 $(date +%T): arm $arm, ${tp}$((k0 + 1)), $(md5sum < "$bin" | cut -c1-8)"
  CHAIN_BIN=$bin CATCH=swap TAGP=$tp K0=$k0 MAX=1 bash "$HERE/chain0430.sh" > "$E/n/chain-ab-${tp}$((k0 + 1)).out" 2>&1
  tail -2 "$E/n/chain-ab-${tp}$((k0 + 1)).out"
  grep -q ": NO_CRASH$" "$E/n/chain-ab-${tp}$((k0 + 1)).out" || { echo "ab0430 $(date +%T): not NO_CRASH, stop"; break; }
done
echo "ab0430 $(date +%T): done"
