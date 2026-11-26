#!/usr/bin/env bash
# BC5 exp 0419, phase 2 of the dead code: ONE build round on the private tree (exp0413/p, at the test build T, patch
# fec3d656). The maintainer's order of 2026-11-14 through the top session. CPU only, no emulator, one lock line.
#   1. the private tree must be T's (tree23.md5); the files the cuts touch are saved to $P/p2-before/
#   2. mkp2_0419.py applies the steps given (all ten by default)
#   3. normal and lean are rebuilt in their build directories (ninja rebuilds what changed), nice 19
# A build error stops it with the error lines: the failing step is then left out by running this again with the
# remaining steps (the saved files are put back first), which is the same round, not a second one.
# usage (on the box): p2build0419.sh [step ...]
set -u
ulimit -c 0
export LC_ALL=C LANGUAGE=C
W=$HOME/bc5-work; P=$W/exp0413/p; N=$W/exp0413/n; HERE=$(cd "$(dirname "$0")" && pwd)
m() { md5sum < "$1" | cut -c1-8; }
FILES="src/libs/bc5LleAgc.cpp src/bc5/load_stat.hpp src/graphics/presentation/videoOut.cpp src/kernel/memory.cpp src/graphics/presentation/window/window.cpp"
pgrep '^kyty_emulator' > /dev/null && { echo "p2build0419: an emulator runs: NOT STARTED"; exit 1; }
. "$N/chainlock0417.inc"
[ -n "${CHAIN_LOCKLINE:-}" ] || chain_claim "exp 0419 phase 2: the cuts applied to the private tree and one rebuild of normal and lean (CPU only, no emulator)" 25 || { echo "p2build0419: NOT STARTED"; exit 1; }
trap chain_release EXIT
if [ -d "$P/p2-before" ]; then
    echo "putting the saved files back first"
    for f in $FILES; do cp -p "$P/p2-before/$f" "$P/tree/$f" || { echo "p2build0419 STOP: cannot restore $f"; exit 1; }; done
fi
bad=0
while read -r sum f; do [ "$(md5sum < "$P/tree/$f" | cut -d' ' -f1)" = "$sum" ] || { echo "differs: $f"; bad=$((bad + 1)); }; done < "$HERE/tree23.md5"
[ "$bad" = 0 ] || { echo "p2build0419 STOP: $bad files of the private tree are not T's"; exit 1; }
if [ ! -d "$P/p2-before" ]; then
    for f in $FILES; do mkdir -p "$P/p2-before/$(dirname "$f")" && cp -p "$P/tree/$f" "$P/p2-before/$f" || { echo "p2build0419 STOP: cannot save $f"; exit 1; }; done
    mkdir -p "$P/p2-before/bin" && cp -p "$P/build-normal/src/kyty_emulator" "$P/p2-before/bin/kyty_emulator.normal" && cp -p "$P/build-lean/src/kyty_emulator" "$P/p2-before/bin/kyty_emulator.lean"
fi
echo "steps: ${*:-all}"
python3 "$HERE/mkp2_0419.py" "$P/tree" "$@" || { echo "p2build0419 STOP: the generator refused"; exit 1; }
for f in $FILES; do echo "  $(m "$P/tree/$f")  $f"; done
for v in normal lean; do
    d=$P/build-$v
    echo "== $(date +%T) build $v"
    if ! distrobox enter ubuntu -- sh -c "cd '$d' && nice -n 19 ninja kyty_emulator" < /dev/null > "$d.build.log" 2>&1; then
        grep -m12 -E "error:" "$d.build.log" | cut -c1-260
        echo "p2build0419 STOP: build $v failed; leave the failing step out and run again"
        exit 1
    fi
    echo "$v: $(md5sum < "$d/src/kyty_emulator" | cut -d' ' -f1), warnings $(grep -c 'warning:' "$d.build.log")"
done
echo "p2build0419 done $(date +%T): normal $(m "$P/build-normal/src/kyty_emulator"), lean $(m "$P/build-lean/src/kyty_emulator")"
