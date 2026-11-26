#!/usr/bin/env bash
# BC5 exp 0417, the K1r fold (cpu0417.sh plus exp 0412's five tests: firstfail, rlabels, k1r, saveguard; maprule was there).
# BC5 exp 0417, the next patch change (made from the integration's cpu0416.sh by mkkit0417b.py): exp 0415's counts
# for L5c and its test0415anon; sb.cpp is exp 0417's plain test (the hook compiled out).
# BC5 integration of 2026-11-13: the CPU tests of the three experiments, built with g++ in the ubuntu container against
# the PRIVATE tree's headers (~/bc5-work/exp0413/p/tree/src). No emulator, no GPU, no lock: it refuses when an emulator
# runs and writes only into its own directory.
#   exp 0416  sema.cpp (mktest0416.py on the folded semaphore.cpp), run with the switch unset and =1
#             sb.cpp (mktest0416sb.py on the folded libAmpr.cpp), four runs: guard on/off x map opt-in off/on
#             test0416fault.py (the catcher's synthetic cases; here also the Linux ones)
#   exp 0412  maprule0412.cpp with maprule0412.inc (tag mr412)
#   exp 0415  test0415.cpp (two processes: off, then on <file>), test0415apr.cpp <scratch dir>, test0415sync.cpp, test0415rec.cpp
# usage (on the box): cpu0417.sh        (the sources lie beside this script)
set -u
ulimit -c 0
export LC_ALL=C
HERE=$(cd "$(dirname "$0")" && pwd); T=$HERE/out; SRC=$HOME/bc5-work/exp0413/p/tree/src
pgrep '^kyty_emulator' > /dev/null && { echo "cpu0417: an emulator runs: not started"; exit 1; }
[ -f "$SRC/bc5/apr_posix.hpp" ] && [ -f "$SRC/bc5/anon_sync.hpp" ] || { echo "cpu0417: the private tree has no exp 0415 L5c headers"; exit 1; }
rm -rf "$T"; mkdir -p "$T/scratch" || exit 1
fails=0
gxx() {  # name, extra flags...: builds $HERE/<name>.cpp
    local n=$1; shift
    distrobox enter ubuntu -- env LC_ALL=C g++ -std=c++20 -O1 -Wall -Wextra "$@" "$HERE/$n.cpp" -o "$T/$n" < /dev/null > "$T/$n-build.out" 2>&1 ||
        { echo "FAIL build $n: $(grep -m2 'error' "$T/$n-build.out" | cut -c1-200 | tr '\n' ' ')"; fails=$((fails + 1)); return 1; }
}
run() {  # label, command...: the last line of the output is the result
    local l=$1; shift
    if distrobox enter ubuntu -- env LC_ALL=C "$@" < /dev/null > "$T/$l.out" 2>&1; then echo "ok   $l: $(tail -1 "$T/$l.out" | cut -c1-140)"
    else echo "FAIL $l (status $?): $(grep -m2 'FAIL' "$T/$l.out" | cut -c1-200 | tr '\n' ' ') $(tail -1 "$T/$l.out" | cut -c1-140)"; fails=$((fails + 1)); fi
}
gxx sema -pthread && { run sema-off "$T/sema"; run sema-on KYTY_BC5_SEMA_TARGETED_WAKE=1 "$T/sema"; }
gxx sb && {
    run sb-default "$T/sb" "$T/sb1.err"
    run sb-map KYTY_BC5_AMM_SETBUFFER_MAP=1 "$T/sb" "$T/sb2.err"
    run sb-noguard KYTY_BC5_AMM_SETBUFFER_GUARD=0 "$T/sb" "$T/sb3.err"
    run sb-noguard-map KYTY_BC5_AMM_SETBUFFER_GUARD=0 KYTY_BC5_AMM_SETBUFFER_MAP=1 "$T/sb" "$T/sb4.err"
}
if python3 -I "$HERE/test0416fault.py" > "$T/fault.out" 2>&1; then echo "ok   fault0416: $(grep -c '^ok' "$T/fault.out") checks, $(tail -1 "$T/fault.out")"
else echo "FAIL fault0416: $(grep -m3 '^FAIL' "$T/fault.out" | cut -c1-160 | tr '\n' ' ')"; fails=$((fails + 1)); fi
gxx maprule0412 -Werror -I "$HERE" && run maprule0412 "$T/maprule0412"
gxx firstfail0412 -Werror -I "$HERE" && run firstfail0412 "$T/firstfail0412"
gxx rlabels0412 -Werror -I "$HERE" && run rlabels0412 "$T/rlabels0412"
gxx k1r0412 -Werror -I "$HERE" && run k1r0412 "$T/k1r0412"
mkdir -p "$T/sgdir" && gxx saveguard0412 -Werror -pthread -I "$HERE" && run saveguard0412 "$T/saveguard0412" "$T/sgdir"
gxx test0415 -Werror -pthread -I "$SRC" && { run test0415-off "$T/test0415" off; run test0415-on "$T/test0415" on "$T/scratch/loadstat.txt"; }
gxx test0415apr -Werror -I "$SRC" && run test0415apr "$T/test0415apr" "$T/scratch"
gxx test0415sync -Werror -I "$SRC" && run test0415sync "$T/test0415sync"
gxx test0415rec -Werror -I "$SRC" && run test0415rec "$T/test0415rec"
gxx test0415anon -Werror -I "$SRC" && run test0415anon "$T/test0415anon"
# the counts exp 0415 names for L5c: test0415 off 76, on 32; apr 33; sync 15; rec 11; anon 31
for want in "test0415-off:76 of 76" "test0415-on:32 of 32" "test0415apr:33 of 33" "test0415sync:15 of 15" "test0415rec:11 of 11" "test0415anon:31 of 31" "maprule0412:15281 of 15281" "firstfail0412:101506 of 101506" "rlabels0412:4970 of 4970" "k1r0412:17742 of 17742" "saveguard0412:178 of 178"; do
    grep -q -- "${want#*:}; end" "$T/${want%%:*}.out" 2> /dev/null || { echo "FAIL count ${want%%:*}: want ${want#*:}, got $(tail -1 "$T/${want%%:*}.out" 2> /dev/null | cut -c1-80)"; fails=$((fails + 1)); }
done
echo "cpu0417c: $fails failed"
[ "$fails" = 0 ]
