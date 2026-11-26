#!/usr/bin/env bash
# BC5 exp 0439 (tag dg439): the diagnosis build for the run with hang-dump v3 (top, 11-22 15:35): mkpa439.py (pa439 with
# sc439) over the pre-pa439 unit, exp 0444's mkqc444.py (the busy-queue histogram) over that, ud439patch.py on the private
# backend copy (after pw439 and cl439), then box439.sh with the normal build only. CPU only. Writes k439/ only.
#   dg439.sh        (in ~/bc5-work/exp0439/k439)
set -u
cd "$(dirname "$0")" || exit 1
stop() { echo "dg439 STOP: $*"; exit 1; }
m8() { md5sum < "$1" | cut -c1-8; }
pgrep "^kyty_emulator" > /dev/null && stop "an emulator runs"
# BOX-LOCK through e0439.sh like every box job (top, 11-22 ~16:05), dropped at any exit
L=$HOME/bc5-work/BOX-LOCK
(cd .. && bash e0439.sh lock "dg439 build" 2>&1 | tail -1)
grep -q '^exp0439 ' "$L" || stop "lock not taken: [$(cat "$L")]"
trap '(cd .. && bash e0439.sh unlock 2>&1 | tail -1)' EXIT
[ -f new/bc5LleAgc.cpp.pre-pa439 ] || stop "no new/bc5LleAgc.cpp.pre-pa439"
echo "pre-pa439 $(m8 new/bc5LleAgc.cpp.pre-pa439) (laptop's 31c06acb); new/be/direct.cpp $(m8 new/be/direct.cpp)"
grep -q 'tag pw439' new/be/direct.cpp && grep -q 'tag cl439' new/be/direct.cpp || stop "new/be/direct.cpp lacks pw439 or cl439"
if ! grep -q 'tag ud439' new/be/direct.cpp; then
    cp new/be/direct.cpp new/be/direct.cpp.pre-ud439 && python3 -I ud439patch.py new/be/direct.cpp || stop "ud439patch"
fi
if ! grep -q 'tag ud439b' new/be/direct.cpp; then python3 -I ud439bpatch.py new/be/direct.cpp || stop "ud439b"; fi # exp 0439 (tag ud439b)
echo "be direct.cpp $(m8 new/be/direct.cpp), ud439 lines $(grep -c 'tag ud439' new/be/direct.cpp)"
[ -f new/bc5LleAgc.cpp ] && cp new/bc5LleAgc.cpp "new/bc5LleAgc.cpp.$(m8 new/bc5LleAgc.cpp)"
python3 -I mkpa439.py new/bc5LleAgc.cpp.pre-pa439 new/pa.tmp && cp pa0439.hpp new/pa0439.hpp || stop "mkpa439"
echo "pa439 $(m8 new/pa.tmp) (laptop's 0c2582f7); sc439 $(grep -c 'tag sc439' new/pa.tmp)"
if python3 -I mkqc444.py new/pa.tmp new/qc.tmp; then mv new/qc.tmp new/bc5LleAgc.cpp; QC=1; else echo "qc444 did not fit: left out"; mv new/pa.tmp new/bc5LleAgc.cpp; QC=0; fi
rm -f new/pa.tmp
python3 -I mkfp439.py new/bc5LleAgc.cpp new/fp.tmp && mv new/fp.tmp new/bc5LleAgc.cpp && cp fp0439.hpp new/fp0439.hpp || stop "mkfp439" # exp 0439 (tag fp439)
python3 -I mkbl439.py new/bc5LleAgc.cpp new/bl.tmp && mv new/bl.tmp new/bc5LleAgc.cpp || stop "mkbl439" # exp 0439 (tag bl439)
python3 -I mkvl439.py new/bc5LleAgc.cpp new/vl.tmp && mv new/vl.tmp new/bc5LleAgc.cpp || stop "mkvl439" # exp 0439 (tag vl439)
# exp 0439 (tag ap439): libAmpr.cpp from the tree with the APR result before the completion (mkap439.py)
T=$HOME/src/KytyPlus/src/libs/libAmpr.cpp
python3 -I mkap439.py "$T" new/libAmpr.cpp || stop "mkap439"
echo "libAmpr.cpp $(m8 "$T") -> $(m8 new/libAmpr.cpp)"
# exp 0439 (tag vd439): libVideoDec2.cpp from the tree with stream-sized memory answers (mkvd439.py)
TV=$HOME/src/KytyPlus/src/libs/libVideoDec2.cpp
python3 -I mkvd439.py "$TV" new/libVideoDec2.cpp || stop "mkvd439"
echo "libVideoDec2.cpp $(m8 "$TV") -> $(m8 new/libVideoDec2.cpp) (laptop's 3f9df834 -> a315ac6d)"
echo "unit $(m8 new/bc5LleAgc.cpp) (laptop's 02fd5346 with qc444, fp439, bl439 and vl439); qc444 $QC"
BOX439_ONLY=normal bash box439.sh build 2>&1 | tail -25
S=normal/strings.txt
echo "normal $(cut -c1-8 normal/binary.md5); strings: sc439 $(grep -c 'tag sc439\|sc439 ' $S) ud439 $(grep -c 'tag ud439' $S) qc444 $(grep -c 'qc444' $S) rs439 $(grep -c 'rs439' $S) cl439 $(grep -c 'tag cl439' $S) nf439 $(grep -c 'nf439' $S) fp439 $(grep -c 'tag fp439' $S) ap439 $(grep -c 'tag ap439' $S) bl439 $(grep -c 'bl439' $S) ud439b $(grep -c 'tag ud439b' $S) vl439 $(grep -c 'vl439' $S) vd439 $(grep -c 'tag vd439' $S)"
