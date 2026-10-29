#!/usr/bin/env bash
# BC5 experiment 0380 (F604): the "test 0380 noclear" binary, ~/bc5-work/exp0380nc/bin/kyty_emulator =
#   the shared normal build's objects (58c4a627) and the shared backend archive (bb50b2e0)
#   + src/libs/bc5LleAgc.cpp = exp 0379's unit (exp0379t's patched copy, e62113a5: patch0379-bc5LleAgc.diff on the
#     tree's e7cc2f60, header zero_skip.hpp 782ca0e9) with the recorder's four edits (mk-rec0380.py, rec0380.inc).
# Only that unit is recompiled (build0380x.py, as b8561eaa). ~/src/KytyPlus, the shared builds, the archive and
# play-pkg.sh are only read. CPU only, nice 19, no emulator.
# usage: bash ~/bc5-work/exp0380nc/build0380nc.sh   (with build0380x.py, mk-rec0380.py and rec0380.inc beside it)
set -u
W=$HOME/bc5-work; E=$W/exp0380nc; R=$E/raw; LOCK=$W/BOX-LOCK; B=$W/kytyplus-build; TREE=$HOME/src/KytyPlus
ARCH=$W/backend-ubuntu/libbc5_backend.a; Z=$W/exp0379t/src/src
m() { md5sum < "$1" | cut -c1-8; }
pgrep '^kyty_emulator' > /dev/null && { echo "an emulator runs: stop"; exit 1; }
grep -q '^top exp 0380 | noclear' "$LOCK" || { echo "the lock line is not this session's: $(cat "$LOCK")"; exit 1; }
mkdir -p "$R" "$E/src/libs/bc5" "$E/bin" "$E/obj"
pins() { echo "shared normal $(m "$B/src/kyty_emulator") lean $(m "$W/kytyplus-build-lean/src/kyty_emulator") archive $(m "$ARCH") tree unit $(m "$TREE/src/libs/bc5LleAgc.cpp") play-pkg.sh $(m "$W/play-pkg.sh")"; }
P0=$(pins); echo "before: $P0" | tee "$R/build-pins.txt"
[ "$P0" = "shared normal 58c4a627 lean dcbeb440 archive bb50b2e0 tree unit e7cc2f60 play-pkg.sh 55531ab6" ] || { echo "a shared pin differs: stop"; exit 1; }
[ "$(m "$Z/libs/bc5LleAgc.cpp")" = e62113a5 ] && [ "$(m "$Z/bc5/zero_skip.hpp")" = 782ca0e9 ] || { echo "exp 0379's unit or header is not e62113a5 / 782ca0e9: stop"; exit 1; }
cp "$Z/libs/bc5LleAgc.cpp" "$E/src/bc5LleAgc.0379.cpp" && cp "$Z/bc5/zero_skip.hpp" "$E/src/libs/bc5/zero_skip.hpp" || exit 1
python3 -I "$E/mk-rec0380.py" "$E/src/bc5LleAgc.0379.cpp" "$E/rec0380.inc" "$E/src/libs/bc5LleAgc.cpp" || { echo "the recorder's edits did not apply: stop"; exit 1; }
echo "unit: 0379 $(m "$E/src/bc5LleAgc.0379.cpp") + recorder = $(m "$E/src/libs/bc5LleAgc.cpp"); ZERO_SKIP $(grep -c 'BC5_DIRECT_ZERO_SKIP' "$E/src/libs/bc5LleAgc.cpp"), rec0380( $(grep -c 'rec0380(' "$E/src/libs/bc5LleAgc.cpp")" | tee -a "$R/build-pins.txt"
BIN=$E/bin/kyty_emulator
[ -f "$BIN" ] && { echo "$BIN exists: stop"; exit 1; }
distrobox enter ubuntu -- sh -c "cd '$B' && ninja -t compdb -x" > "$E/compdb.json" 2> "$R/compdb.err" || { echo "compdb failed"; exit 1; }
echo "== $(date +%T) compile + relink"
distrobox enter ubuntu -- python3 -I "$E/build0380x.py" "$E/compdb.json" "$B" "$E/src/libs/bc5LleAgc.cpp" "$E/obj" "$BIN" "$TREE/src/libs" > "$R/build.out" 2>&1
rc=$?; echo "== $(date +%T) rc $rc; errors $(grep -c 'error:' "$R/build.out"), warnings $(grep -c 'warning:' "$R/build.out")"
grep -n "error:\|undefined\|COMPILE FAILED" "$R/build.out" | head -20
[ $rc = 0 ] && [ -x "$BIN" ] || { echo "build failed: see $R/build.out"; exit 1; }
echo "binary $(m "$BIN"); strings: zero skip $(strings "$BIN" | grep -c '^zero skip: '), rec0380 $(strings "$BIN" | grep -c 'rec0380: '), BC5_0380_REC $(strings "$BIN" | grep -c '^BC5_0380_REC$'), BC5_DIRECT_ZERO_SKIP $(strings "$BIN" | grep -c '^BC5_DIRECT_ZERO_SKIP$'), PIECES_NO_CLEAR $(strings "$BIN" | grep -c '^BC5_DIRECT_PIECES_NO_CLEAR$')" | tee -a "$R/build-pins.txt"
grep -n "warning:" "$R/build.out" | sed 's/^.*bc5LleAgc.cpp:\([0-9]*\).*\[\(-W[^]]*\)\].*$/line \1 \2/' | tee -a "$R/build-pins.txt"
P1=$(pins); echo "after: $P1" | tee -a "$R/build-pins.txt"
[ "$P1" = "$P0" ] || { echo "A SHARED PIN CHANGED"; exit 1; }
