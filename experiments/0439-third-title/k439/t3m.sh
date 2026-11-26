#!/usr/bin/env bash
# BC5 exp 0439: the graphics-mode walk (the top session, 11-21 ~23:55, the maintainer's wish for more fps than "Quality"):
# crosses at 45 and 125 s to the "Graphics mode" screen (up from 130 s in the 00:10 walk), then d-pad right at 135, 150 and 165 s with a shot 2 s after each;
# no confirm; bound 210 s. The DMC build.
#   t3m.sh <md5-8 of the private normal build>
set -u
PIN=${1:?md5}
cd "$HOME/bc5-work/exp0439" || exit 1
T3S_TAG=-m2 T3S_BOUND=175 T3S_PRESSES="45 125 135:right 150:right 165:right" T3S_EXTRA="BC5_0439_AUDIO_CATCH=1" bash k439/t3s.sh "$PIN" unset "" script 2>&1 | tail -12
echo "== presses"; cat runs/t3s-vunset-m2.keys
echo "== shots"; ls -d ~/bc5-data/priv/t3-screens/t3s-vunset-m2-* | tail -1
