#!/usr/bin/env bash
# BC5 exp 0421: ONE build round on the private tree (exp0413/p, build W): mk0421.py (FileSystem late import, on by
# default), then normal and lean rebuilt, nice 19. CPU only, no emulator, one lock line.
# usage (on the box, from ~/bc5-work/exp0421): b0421.sh        build
#                                              b0421.sh back   the main unit and the binaries' sources as before
set -u
ulimit -c 0
export LC_ALL=C LANGUAGE=C
W=$HOME/bc5-work; P=$W/exp0413/p; N=$W/exp0413/n; HERE=$(cd "$(dirname "$0")" && pwd)
U=$P/tree/src/libs/bc5LleAgc.cpp; H=$P/tree/src/bc5/late_import.hpp; SAVE=$P/p421-before
m() { md5sum < "$1" | cut -c1-8; }
pgrep '^kyty_emulator' > /dev/null && { echo "b0421: an emulator runs: NOT STARTED"; exit 1; }
. "$N/chainlock0417.inc"
[ -n "${CHAIN_LOCKLINE:-}" ] || chain_claim "exp 0421: W + FileSystem late import, one rebuild of normal and lean (CPU only, no emulator)" 30 || { echo "b0421: NOT STARTED"; exit 1; }
trap chain_release EXIT
if [ "${1:-}" = back ]; then
    [ -f "$SAVE/bc5LleAgc.cpp" ] || { echo "b0421: nothing saved"; exit 1; }
    cp -p "$SAVE/bc5LleAgc.cpp" "$U" && rm -f "$H" && echo "b0421: the main unit is back ($(m "$U")); rebuild with ninja"
    exit 0
fi
if [ -f "$SAVE/bc5LleAgc.cpp" ]; then
    echo "b0421: an earlier round's copy exists: the unit is restored from it first"
    cp -p "$SAVE/bc5LleAgc.cpp" "$U" && rm -f "$H" || { echo "b0421 STOP: cannot restore"; exit 1; }
else
    mkdir -p "$SAVE" && cp -p "$U" "$SAVE/bc5LleAgc.cpp" || { echo "b0421 STOP: cannot save the unit"; exit 1; }
    for v in normal lean; do cp -p "$P/build-$v/src/kyty_emulator" "$SAVE/kyty_emulator.$v" || exit 1; done
fi
echo "before: unit $(m "$U"), normal $(m "$P/build-normal/src/kyty_emulator"), lean $(m "$P/build-lean/src/kyty_emulator")"
grep -c 'BC5_DIAG_LAZY_FILESYSTEM' "$U" | sed 's/^/lazyfs lines in the unit: /'
python3 "$HERE/mk0421.py" "$P/tree" || { echo "b0421 STOP: mk0421.py refused"; exit 1; }
echo "after: unit $(m "$U"), header $(m "$H")"
for v in normal lean; do
    d=$P/build-$v
    echo "== $(date +%T) build $v"
    if ! distrobox enter ubuntu -- sh -c "cd '$d' && nice -n 19 ninja kyty_emulator" < /dev/null > "$d.build421.log" 2>&1; then
        grep -m12 -E "error:" "$d.build421.log" | cut -c1-260
        echo "b0421 STOP: build $v failed"
        exit 1
    fi
    echo "$v: $(m "$d/src/kyty_emulator"), warnings $(grep -c 'warning:' "$d.build421.log"), of them in bc5LleAgc.cpp near fs421: $(grep -c 'fs421\|late_import' "$d.build421.log")"
    nice -n 19 strings "$d/src/kyty_emulator" | grep -c -x 'BC5_DIRECT_FS_LATE' | sed "s/^/$v: BC5_DIRECT_FS_LATE in the binary: /"
done
echo "b0421 done $(date +%T)"
