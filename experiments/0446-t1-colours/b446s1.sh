#!/usr/bin/env bash
# exp 0446 (tag s1): build the stage-1 candidate from prep446s1.sh's s1/{new,be} with the shared builds' own compile and
# link commands (a copy of exp 0439's build0438.py in s1/k), on the host toolchain, nice 19 / ionice idle, no lock line
# (CPU only). Outputs: s1/backend/libbc5_backend.a, s1/normal/kyty_emulator, s1/lean/kyty_emulator. Nothing shared is
# written; the shared state is pinned before and after.
set -u
export LC_ALL=C LANGUAGE=C
W=$HOME/bc5-work; X=$W/exp0446; D=$X/${S1_DIR:-s1}; K=$X/s1/k; S=$D/src; BBUILD=$W/backend-ubuntu; SA=$BBUILD/libbc5_backend.a
UNITS_BE="src/direct.cpp src/full_state.cpp src/policy.cpp src/state_stack.cpp src/reimpl/select.cpp"
UNITS_KY="src/libs/bc5LleAgc.cpp src/graphics/presentation/videoOut.cpp src/libs/ajm.cpp src/main.cpp src/kernel/pthread.cpp src/libs/libAmpr.cpp src/libs/bc5Reimpl.cpp src/loader/runtimeLinker.cpp"
m8() { md5sum < "$1" 2> /dev/null | cut -c1-8; }
stop() { echo "b446s1 STOP: $*"; exit 1; }
words() { grep -x '\(KYTY_\)\?BC5_[A-Z0-9_]*' "$1" | sort -u; }
shared() { echo "normal $(m8 "$W/kytyplus-build/src/kyty_emulator") lean $(m8 "$W/kytyplus-build-lean/src/kyty_emulator") archive $(m8 "$SA")"; }
. "$HOME/bc5-toolchain/env.sh" || stop "toolchain env"
before=$(shared); echo "shared before: $before"
[ "$before" = "normal 5727b07f lean 94a6513c archive 09567e4a" ] || stop "the shared state is not bake H's"
[ -s "$D/new/bc5LleAgc.cpp" ] && [ -s "$D/be/src/direct.cpp" ] || stop "run prep446s1.sh first"
rm -rf "$S"; mkdir -p "$S/kyty/src/bc5/reimpl" "$S/kyty/src/libs/ajm" "$S/kyty/src/graphics/presentation" "$S/kyty/src/kernel" "$S/kyty/src/loader" "$S/backend" || stop mkdir
cp -r "$D/be/src" "$D/be/include" "$S/backend/" || stop "backend copy"
N=$D/new
cp "$N/switch_defaults.hpp" "$N/dc0439.hpp" "$N/cw0439.hpp" "$N/fp0439.hpp" "$N/dm0439.hpp" "$D/be/include/bc5/ib_chain.hpp" "$S/kyty/src/bc5/" \
    && cp "$D/be/include/bc5/reimpl/select.hpp" "$S/kyty/src/bc5/reimpl/" \
    && cp "$N/bc5LleAgc.cpp" "$N/ajm.cpp" "$N/libAmpr.cpp" "$N/bc5Reimpl.cpp" "$S/kyty/src/libs/" && cp "$N/atrac9_decoder.h" "$S/kyty/src/libs/ajm/" \
    && cp "$N/videoOut.cpp" "$S/kyty/src/graphics/presentation/" && cp "$N/main.cpp" "$S/kyty/src/" && cp "$N/pthread.cpp" "$S/kyty/src/kernel/" \
    && cp "$N/runtimeLinker.cpp" "$S/kyty/src/loader/" || stop "kit copy"
(cd "$S" && find . -type f | sort | xargs md5sum | cut -c1-8,33-) > "$D/src-md5.txt"
mkdir -p "$D/backend" "$D/raw"
(cd "$BBUILD" && ninja -t compdb) > "$D/backend/compdb.json" 2> /dev/null < /dev/null || stop "backend compdb"
rm -rf "$D/backend/obj" "$D/backend/member" "$D/backend/libbc5_backend.a"
# shellcheck disable=SC2086
nice -n 19 ionice -c 3 python3 -I "$K/build0438.py" archive "$D/backend/compdb.json" "$S/backend" "$D/backend" "$BBUILD" "$SA" "$D/backend/libbc5_backend.a" $UNITS_BE > "$D/raw/build-backend.out" 2>&1 < /dev/null \
    || { grep -n "error:\|FAILED\|Assertion" "$D/raw/build-backend.out" | head -20; stop "backend archive"; }
echo "archive $(m8 "$D/backend/libbc5_backend.a"): warnings $(grep -c 'warning:' "$D/raw/build-backend.out")"
for v in normal lean; do
    b=$W/kytyplus-build$([ $v = lean ] && echo -lean); bin=$D/$v/kyty_emulator
    mkdir -p "$D/$v"; rm -rf "$D/$v/obj" "$D/$v/lib"; [ -f "$bin" ] && mv "$bin" "$bin.$(m8 "$bin")"
    (cd "$b" && ninja -t compdb -x) > "$D/$v/compdb.json" 2> /dev/null < /dev/null || stop "compdb $v"
    # shellcheck disable=SC2086
    nice -n 19 ionice -c 3 python3 -I "$K/build0438.py" emu "$D/$v/compdb.json" "$S/kyty" "$D/$v" "$b" "$bin" "ARCHIVE=$D/backend/libbc5_backend.a" $UNITS_KY > "$D/raw/build-$v.out" 2>&1 < /dev/null
    rc=$?; echo "$v: rc $rc, errors $(grep -c 'error:' "$D/raw/build-$v.out"), warnings $(grep -c 'warning:' "$D/raw/build-$v.out")"
    grep -n "error:\|undefined\|COMPILE FAILED" "$D/raw/build-$v.out" | head -12
    [ "$rc" = 0 ] && [ -x "$bin" ] || stop "build $v"
    m8 "$bin" > "$D/$v/binary.md5"
    strings "$bin" > "$D/$v/strings.txt"; strings "$b/src/kyty_emulator" > "$D/$v/strings-shared.txt"
    echo "$v $(m8 "$bin"): words $(words "$D/$v/strings-shared.txt" | wc -l) -> $(words "$D/$v/strings.txt" | wc -l); gained [$(comm -13 <(words "$D/$v/strings-shared.txt") <(words "$D/$v/strings.txt") | tr '\n' ' ')]; lost [$(comm -23 <(words "$D/$v/strings-shared.txt") <(words "$D/$v/strings.txt") | tr '\n' ' ')]"
done
after=$(shared); [ "$after" = "$before" ] && echo "shared after: unchanged" || echo "SHARED CHANGED: $after"
