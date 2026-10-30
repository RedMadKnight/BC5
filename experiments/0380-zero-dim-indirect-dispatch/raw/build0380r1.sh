#!/usr/bin/env bash
# BC5 experiment 0380 (F611): the second "test 0380 noclear" binary, ~/bc5-work/exp0380r1/bin/kyty_emulator =
#   the shared normal build's objects (58c4a627) and the shared backend archive (bb50b2e0)
#   + src/libs/bc5LleAgc.cpp = exp 0379's unit (exp0379t's patched copy, e62113a5; header zero_skip.hpp 782ca0e9) with
#     the recorder's edits as of F608 (mk-rec0380.py, rec0380.inc: the event matched by ring and the job's age)
#   + src/loader/runtimeLinker.cpp = the tree's (96e03695) with BC5_CRASH_FRAMES (mk-crash0380.py).
# Only those two units are recompiled (build0380y.py). ~/src/KytyPlus, the shared builds, the archive and play-pkg.sh are
# only read. CPU only, nice 19, no emulator. Made from build0380nc.sh.
# usage: bash ~/bc5-work/exp0380r1/build0380r1.sh   (with build0380y.py, mk-rec0380.py, rec0380.inc, mk-crash0380.py beside it)
set -u
W=$HOME/bc5-work; E=$W/exp0380r1; R=$E/raw; LOCK=$W/BOX-LOCK; B=$W/kytyplus-build; TREE=$HOME/src/KytyPlus
ARCH=$W/backend-ubuntu/libbc5_backend.a; Z=$W/exp0379t/src/src
m() { md5sum < "$1" | cut -c1-8; }
pgrep '^kyty_emulator' > /dev/null && { echo "an emulator runs: stop"; exit 1; }
grep -q '^top exp 0380 |' "$LOCK" || { echo "the lock line is not this session's: $(cat "$LOCK")"; exit 1; }
mkdir -p "$R" "$E/src/libs/bc5" "$E/src/loader" "$E/bin" "$E/obj"
RL=$TREE/src/loader/runtimeLinker.cpp
pins() { echo "shared normal $(m "$B/src/kyty_emulator") lean $(m "$W/kytyplus-build-lean/src/kyty_emulator") archive $(m "$ARCH") tree unit $(m "$TREE/src/libs/bc5LleAgc.cpp") play-pkg.sh $(m "$W/play-pkg.sh")"; }
P0=$(pins); echo "before: $P0" | tee "$R/build-pins.txt"
[ "$P0" = "shared normal 58c4a627 lean dcbeb440 archive bb50b2e0 tree unit e7cc2f60 play-pkg.sh 55531ab6" ] || { echo "a shared pin differs: stop"; exit 1; }
[ "$(m "$RL")" = 96e03695 ] && [ "$(m "$Z/libs/bc5LleAgc.cpp")" = e62113a5 ] && [ "$(m "$Z/bc5/zero_skip.hpp")" = 782ca0e9 ] || { echo "exp 0379's unit or header is not e62113a5 / 782ca0e9: stop"; exit 1; }
cp "$Z/libs/bc5LleAgc.cpp" "$E/src/bc5LleAgc.0379.cpp" && cp "$Z/bc5/zero_skip.hpp" "$E/src/libs/bc5/zero_skip.hpp" || exit 1
python3 -I "$E/mk-rec0380.py" "$E/src/bc5LleAgc.0379.cpp" "$E/rec0380.inc" "$E/src/libs/bc5LleAgc.cpp" || { echo "the recorder's edits did not apply: stop"; exit 1; }
python3 -I "$E/mk-crash0380.py" "$RL" "$E/src/loader/runtimeLinker.cpp" || { echo "the crash-frames edit did not apply: stop"; exit 1; }
echo "runtimeLinker.cpp: tree $(m "$RL") + crash frames = $(m "$E/src/loader/runtimeLinker.cpp")" | tee -a "$R/build-pins.txt"
echo "unit: 0379 $(m "$E/src/bc5LleAgc.0379.cpp") + recorder = $(m "$E/src/libs/bc5LleAgc.cpp"); ZERO_SKIP $(grep -c 'BC5_DIRECT_ZERO_SKIP' "$E/src/libs/bc5LleAgc.cpp"), rec0380( $(grep -c 'rec0380(' "$E/src/libs/bc5LleAgc.cpp")" | tee -a "$R/build-pins.txt"
BIN=$E/bin/kyty_emulator
[ -f "$BIN" ] && { echo "$BIN exists: stop"; exit 1; }
distrobox enter ubuntu -- sh -c "cd '$B' && ninja -t compdb -x" > "$E/compdb.json" 2> "$R/compdb.err" || { echo "compdb failed"; exit 1; }
echo "== $(date +%T) compile + relink"
distrobox enter ubuntu -- python3 -I "$E/build0380y.py" "$E/compdb.json" "$B" "$E/obj" "$BIN" "libs/bc5LleAgc.cpp.o=$E/src/libs/bc5LleAgc.cpp=$TREE/src/libs" "loader/runtimeLinker.cpp.o=$E/src/loader/runtimeLinker.cpp=$TREE/src/loader" > "$R/build.out" 2>&1
rc=$?; echo "== $(date +%T) rc $rc; errors $(grep -c 'error:' "$R/build.out"), warnings $(grep -c 'warning:' "$R/build.out")"
grep -n "error:\|undefined\|COMPILE FAILED" "$R/build.out" | head -20
[ $rc = 0 ] && [ -x "$BIN" ] || { echo "build failed: see $R/build.out"; exit 1; }
echo "binary $(m "$BIN"); strings: zero skip $(strings "$BIN" | grep -c '^zero skip: '), rec0380 $(strings "$BIN" | grep -c 'rec0380: '), BC5_0380_REC $(strings "$BIN" | grep -c '^BC5_0380_REC$'), BC5_DIRECT_ZERO_SKIP $(strings "$BIN" | grep -c '^BC5_DIRECT_ZERO_SKIP$'), PIECES_NO_CLEAR $(strings "$BIN" | grep -c '^BC5_DIRECT_PIECES_NO_CLEAR$'), CRASH_FRAMES $(strings "$BIN" | grep -c '^BC5_CRASH_FRAMES$'), REC_RING $(strings "$BIN" | grep -c '^BC5_0380_REC_RING$')" | tee -a "$R/build-pins.txt"
grep -n "warning:" "$R/build.out" | sed 's/^.*bc5LleAgc.cpp:\([0-9]*\).*\[\(-W[^]]*\)\].*$/line \1 \2/' | tee -a "$R/build-pins.txt"
P1=$(pins); echo "after: $P1" | tee -a "$R/build-pins.txt"
[ "$P1" = "$P0" ] || { echo "A SHARED PIN CHANGED"; exit 1; }
