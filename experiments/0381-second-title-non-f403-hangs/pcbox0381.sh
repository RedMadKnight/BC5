#!/usr/bin/env bash
# BC5 exp 0381 (PORT-CHAIN): the CPU-only check of fix/port-chain on the box: clang build with warnings as errors, Catch2
# and subsets, direct-selftest without --submit. Everything in ~/bc5-work/exp0381/pc; nothing shared, no GPU.
# It holds the queue record itself: the outcome line is written here, by the EXIT trap, only after pcrun0381.sh's claim
# passed its guard (the lock line is ours), and it says done only when every step passed. The laptop writes no outcome.
# usage: bash -s -- <source manifest expected>   (the manifest: pcrun0381.sh computes it from a clean export of the commit)
set -u
EXPECT=${1:?the source manifest}
W=$HOME/bc5-work; I=$W/exp0381/pc; LOCK=$W/BOX-LOCK
TAG='top exp 0381 | PORT-CHAIN'
pgrep '^kyty_emulator' > /dev/null && { echo "GUARD: an emulator runs"; exit 3; }
grep -q "^$TAG" "$LOCK" 2> /dev/null || { echo "GUARD: the lock is not this check's: $(cat "$LOCK" 2> /dev/null)"; exit 4; }
ok=0
finish() {
    if [ "$ok" = 1 ]; then echo "$TAG check done: all steps passed, no GPU; lock cleared | $(date '+%F %T')" >> "$W/BOX-QUEUE"
    else echo "$TAG check FAILED, see ~/bc5-work/exp0381/pc; no GPU; lock cleared | $(date '+%F %T')" >> "$W/BOX-QUEUE"; fi
    grep -q "^$TAG" "$LOCK" 2> /dev/null && : > "$LOCK"
}
trap finish EXIT
fail() { echo "FAIL: $1"; exit 1; }
box() { distrobox enter ubuntu -- sh -c "$1" < /dev/null; }
manifest() { (cd "$I" && find backend -type f -exec md5sum {} + | sed 's/ \*/  /' | LC_ALL=C sort -k2 | md5sum | cut -c1-16); }
m0=$(manifest); echo "sources before: $m0 (want $EXPECT), $(find "$I/backend" -type f | wc -l) files"
[ "$m0" = "$EXPECT" ] || fail "the sources are not the commit's"
CATCH=$(ls -d "$W"/exp03*/backend-build/_deps/catch2-src 2> /dev/null | head -1)
echo "== $(date +%T) configure"
box "nice -n 19 cmake -S '$I/backend' -B '$I/build' -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_C_COMPILER=clang -DCMAKE_CXX_COMPILER=clang++ -DBC5_WITH_AMDGPU=ON -DBC5_BUILD_TESTS=ON -DFETCHCONTENT_SOURCE_DIR_CATCH2='$CATCH'" > "$I/configure.log" 2>&1 || { tail -5 "$I/configure.log"; fail configure; }
echo "== $(date +%T) build"
box "nice -n 19 cmake --build '$I/build' -j 6" > "$I/build.log" 2>&1 || { grep -E "error" "$I/build.log" | head; fail build; }
echo "build rc 0, warnings $(grep -c 'warning:' "$I/build.log"), errors $(grep -c 'error:' "$I/build.log")"
for t in "" "[acb_restore]" "[chain]" "[full_state]" "[indirect_check]" "[zero_skip]" "[draw_args]"; do
    out=$I/tests-$(echo "${t:-all}" | tr -d '[]').log
    box "cd '$I/build' && ./bc5_backend_tests '$t'" > "$out" 2>&1; rc=$?
    echo "${t:-(all)} rc $rc: $(grep -a 'All tests passed\|test cases:' "$out" | tail -1)"
    [ "$rc" = 0 ] || fail "tests $t"
    grep -q 'No tests ran' "$out" && fail "no tests ran: $t"
    grep -q 'All tests passed' "$out" || fail "no pass line: $t"
done
n=0
for a in "" "--cp-check --zero-check"; do
    n=$((n + 1)); out=$I/selftest-$n.log
    box "cd '$I/build' && ./direct-selftest $a" > "$out" 2>&1; rc=$?
    echo "direct-selftest [$a] rc $rc: $(tail -1 "$out")"
    [ "$rc" = 0 ] || fail selftest
    grep -q '^direct-selftest: nothing done without --submit' "$out" || fail "selftest did not report doing nothing"
done
m1=$(manifest); echo "sources after: $m1"
[ "$m1" = "$EXPECT" ] || fail "the sources changed during the check"
echo "toolchain: $(box 'clang++ --version | head -1')"
echo "output library (built here, not an input): libbc5_backend.a md5 $(md5sum < "$I/build/libbc5_backend.a" | cut -d' ' -f1)"
echo "output binaries: bc5_backend_tests $(md5sum < "$I/build/bc5_backend_tests" | cut -d' ' -f1), direct-selftest $(md5sum < "$I/build/direct-selftest" | cut -d' ' -f1)"
ok=1
echo "CHECK PASS $(date +%T)"
