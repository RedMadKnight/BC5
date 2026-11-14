#!/usr/bin/env bash
# BC5 exp 0419, build V = U + the library folds + V's other steps: ONE build round on the private tree (exp0413/p, at
# build U, patch 5b185960). CPU only, no emulator, one lock line. Made from p2build0419.sh.
#   1. the private tree must be U's (tree24.md5); every file the round may touch is saved to $P/p3-before/ with U's
#      two binaries
#   2. mkfold0419.py applies the levels file (FOLD=0 leaves the folds out); mkv0419.py applies the steps given
#   3. normal and lean are rebuilt in their build directories, nice 19
# A build error stops it with the error lines. The failing part is then left out by running this again with it taken
# away (a file's line set to level 0 in the levels file, or a step not named); the saved files are put back first, so
# it is the same round.
# usage (on the box): [FOLD=0] p3build0419.sh [step ...]     steps: touchfn lazyfs liveids; "none" for no step
set -u
ulimit -c 0
export LC_ALL=C LANGUAGE=C
W=$HOME/bc5-work; P=$W/exp0413/p; N=$W/exp0413/n; HERE=$(cd "$(dirname "$0")" && pwd)
m() { md5sum < "$1" | cut -c1-8; }
FILES="src/libs/controller.cpp src/libs/controller.h src/libs/ajm.cpp src/libs/bc5LleAgc.cpp $(grep -v '^#' "$HERE/fold-levels.txt" | awk '{print "src/" $2}' | tr '\n' ' ')"
pgrep '^kyty_emulator' > /dev/null && { echo "p3build0419: an emulator runs: NOT STARTED"; exit 1; }
. "$N/chainlock0417.inc"
[ -n "${CHAIN_LOCKLINE:-}" ] || chain_claim "exp 0419 build V: the library folds and V's steps applied to the private tree, one rebuild of normal and lean (CPU only, no emulator)" 30 || { echo "p3build0419: NOT STARTED"; exit 1; }
trap chain_release EXIT
if [ -d "$P/p3-before" ]; then
    echo "putting the saved files back first"
    for f in $FILES; do cp -p "$P/p3-before/$f" "$P/tree/$f" || { echo "p3build0419 STOP: cannot restore $f"; exit 1; }; done
fi
bad=0
while read -r sum f; do [ "$(md5sum < "$P/tree/$f" | cut -d' ' -f1)" = "$sum" ] || { echo "differs: $f"; bad=$((bad + 1)); }; done < "$HERE/tree24.md5"
[ "$bad" = 0 ] || { echo "p3build0419 STOP: $bad files of the private tree are not U's"; exit 1; }
if [ ! -d "$P/p3-before" ]; then
    for f in $FILES; do mkdir -p "$P/p3-before/$(dirname "$f")" && cp -p "$P/tree/$f" "$P/p3-before/$f" || { echo "p3build0419 STOP: cannot save $f"; exit 1; }; done
    mkdir -p "$P/p3-before/bin" && cp -p "$P/build-normal/src/kyty_emulator" "$P/p3-before/bin/kyty_emulator.normal" && cp -p "$P/build-lean/src/kyty_emulator" "$P/p3-before/bin/kyty_emulator.lean"
fi
if [ "${FOLD:-1}" = 1 ]; then
    python3 "$HERE/mkfold0419.py" "$P/tree" "$HERE/fold-levels.txt" || { echo "p3build0419 STOP: the fold refused"; exit 1; }
else
    echo "folds: left out (FOLD=0)"
fi
echo "steps: ${*:-touchfn lazyfs}"
if [ "${1:-}" != none ]; then
    python3 "$HERE/mkv0419.py" "$P/tree" "$@" || { echo "p3build0419 STOP: mkv0419.py refused"; exit 1; }
fi
for f in $FILES; do echo "  $(m "$P/tree/$f")  $f"; done
for v in normal lean; do
    d=$P/build-$v
    echo "== $(date +%T) build $v"
    if ! distrobox enter ubuntu -- sh -c "cd '$d' && nice -n 19 ninja kyty_emulator" < /dev/null > "$d.build.log" 2>&1; then
        grep -m12 -E "error:" "$d.build.log" | cut -c1-260
        echo "p3build0419 STOP: build $v failed; leave the failing part out and run again"
        exit 1
    fi
    echo "$v: $(md5sum < "$d/src/kyty_emulator" | cut -d' ' -f1), warnings $(grep -c 'warning:' "$d.build.log")"
done
echo "p3build0419 done $(date +%T): normal $(m "$P/build-normal/src/kyty_emulator"), lean $(m "$P/build-lean/src/kyty_emulator")"
