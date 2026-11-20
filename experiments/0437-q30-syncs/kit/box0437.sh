#!/usr/bin/env bash
# BC5 experiment 0437 (tag vg437): the ONE private test build of candidate vg437 (BC5_DIRECT_VIEWS_GEN: the direct view
# list keyed on the direct ranges' generation) on the BC-250, CPU only (nice 19), nothing shared written. After exp
# 0436's box0436.sh (its atomic claim, R35); host units only, the backend archive is the shared one, unchanged.
#   box0437.sh claim [what] [minutes]   takes ~/bc5-work/BOX-LOCK atomically (hard link), refuses a foreign line
#   box0437.sh build                    with our lock: pins the shared inputs (the tree's three units, the archive, the
#                                       builds), puts this kit's three files into copies, compiles memory.cpp and
#                                       bc5LleAgc.cpp with the shared normal and lean builds' own commands, links each with
#                                       the shared archive: ~/bc5-work/exp0437/{normal,lean}/kyty_emulator; then the class
#                                       test (test_vg437.sh) with the container's g++ on the kit's memory.cpp
#   box0437.sh release                  clears the lock only if it holds our exact line
# Beside this script (scp'd to ~/bc5-work/exp0437/kit): build0437.py (exp 0436's build0436.py, unchanged), memory.h,
# memory.cpp and bc5LleAgc.cpp (patch bb04219b's units + mkvg437.py), test_vg437.sh and test_vg437.cpp.
set -u
export LC_ALL=C LANGUAGE=C
W=$HOME/bc5-work; E=$W/exp0437; R=$E/raw; S=$E/src; LOCK=$W/BOX-LOCK; ID=$E/lock.line
TREE=$HOME/src/KytyPlus; HERE=$(cd "$(dirname "$0")" && pwd)
SA=$W/backend-ubuntu/libbc5_backend.a
UNIT=src/libs/bc5LleAgc.cpp; MEMC=src/kernel/memory.cpp; MEMH=src/kernel/memory.h
# pins: the shared inputs as exp 0436's bake left them (patch bb04219b), and this kit's files
P_UNIT=a62e8bf6251a44f147a23d9689449e21   # the tree's bc5LleAgc.cpp (patch bb04219b, = exp 0436's bake K_UNIT)
P_MEMC=aa7d7f5b3fdbbe8d57bd440e7aa80922   # the tree's memory.cpp (patch bb04219b applied to f266548, LF)
P_MEMH=224b9fa896fdea0755d9e00f12accaf3   # the tree's memory.h (the same)
P_ARCH=d6638808; P_NORMAL=f345db74; P_LEAN=6a735b81
K_UNIT=39664b965aae1c10a13a4426572e7aef; K_MEMC=281b18efb7d6563602294c0cbdf76ff4; K_MEMH=0b3ac45ff4bff7e8b107ce1286f76427
K_PY=5dfb35d884bee8af31d81e3ad8b92548
stop() { echo "0437 STOP: $*"; exit 1; }
m() { md5sum < "$1" 2> /dev/null | cut -d' ' -f1; }
own() { [ -s "$ID" ] && [ "$(cat "$LOCK" 2> /dev/null)" = "$(cat "$ID")" ]; }
claim() {
    local c=$LOCK.d19-claim t=$LOCK.0437-$$.new a=$LOCK.0437-$$.aside line
    pgrep '^kyty_emulator' > /dev/null && stop "an emulator runs"
    [ ! -L "$E" ] || stop "$E is a link"
    mkdir -p "$R" || stop "cannot make $R"
    line="exp 0437 | token $(date +%s)$$ | $1, until $(date -d +"$2"min +%H:%M) | $(date '+%F %T')"
    mkdir "$c" 2> /dev/null || stop "another claim runs, or $c was left behind"
    fail() { rm -f "$t"; rmdir "$c"; stop "$1"; }
    printf '%s\n' "$line" > "$t" || fail "cannot write $t"
    if [ -e "$LOCK" ] || [ -L "$LOCK" ]; then
        { [ -L "$LOCK" ] || [ ! -f "$LOCK" ]; } && fail "$LOCK is not a plain file"
        [ -s "$LOCK" ] && fail "foreign lock: $(cat "$LOCK")"
        mv -T "$LOCK" "$a" || fail "the lock moved under us"
    fi
    if ! ln "$t" "$LOCK" 2> /dev/null; then
        [ -s "$a" ] || rm -f "$a"
        fail "lost the claim to: $(cat "$LOCK" 2> /dev/null)"
    fi
    if [ -s "$a" ]; then
        local w; w=$(cat "$a"); mv -fT "$a" "$LOCK"; fail "a foreign lock arrived during the claim: $w"
    fi
    rm -f "$a" "$t"; rmdir "$c" || stop "cannot remove $c"
    printf '%s\n' "$line" > "$ID" || stop "cannot record the line; the lock is held: $line"
    own || stop "the lock does not read back as ours"
    echo "claimed: $line"
}
release() {
    if own; then : > "$LOCK" && [ ! -s "$LOCK" ] && { rm -f "$ID"; echo "lock released"; return 0; }; stop "the lock could not be released"; fi
    stop "the lock is not ours, left as it is: $(cat "$LOCK" 2> /dev/null)"
}
build() {
    own || stop "no lock held by 0437"
    pgrep '^kyty_emulator' > /dev/null && stop "an emulator runs"
    local v b bin rc sn sl sa
    sn=$(m "$W/kytyplus-build/src/kyty_emulator"); sl=$(m "$W/kytyplus-build-lean/src/kyty_emulator"); sa=$(m "$SA")
    [ "${sn:0:8}" = "$P_NORMAL" ] && [ "${sl:0:8}" = "$P_LEAN" ] && [ "${sa:0:8}" = "$P_ARCH" ] \
        || stop "the shared builds are not normal $P_NORMAL / lean $P_LEAN / archive $P_ARCH: ${sn:0:8} ${sl:0:8} ${sa:0:8}"
    [ "$(m "$TREE/$UNIT")" = "$P_UNIT" ] && [ "$(m "$TREE/$MEMC")" = "$P_MEMC" ] && [ "$(m "$TREE/$MEMH")" = "$P_MEMH" ] \
        || stop "the shared tree is not patch bb04219b's: $UNIT $(m "$TREE/$UNIT"), $MEMC $(m "$TREE/$MEMC"), $MEMH $(m "$TREE/$MEMH")"
    [ "$(m "$HERE/bc5LleAgc.cpp")" = "$K_UNIT" ] && [ "$(m "$HERE/memory.cpp")" = "$K_MEMC" ] && [ "$(m "$HERE/memory.h")" = "$K_MEMH" ] \
        && [ "$(m "$HERE/build0437.py")" = "$K_PY" ] || stop "the kit's files are not the pinned ones"
    rm -rf "$S"; mkdir -p "$S/kyty/src/libs" "$S/kyty/src/kernel" "$S/kyty/src/bc5" || stop "mkdir $S"
    cp "$HERE/bc5LleAgc.cpp" "$S/kyty/$UNIT" && cp "$HERE/memory.cpp" "$S/kyty/$MEMC" && cp "$HERE/memory.h" "$S/kyty/$MEMH" || stop "copy the kit"
    (cd "$S" && find . -type f | sort | xargs md5sum) > "$R/src-md5.txt"; cat "$R/src-md5.txt"
    # memory.h gains one declaration (Bc5DirectRangesGeneration); every other unit that includes it is unchanged in code
    # and keeps its shared object. The two units that use it are compiled here with the copy's src/ first on -I.
    for v in normal lean; do
        b=$W/kytyplus-build$([ $v = lean ] && echo -lean); bin=$E/$v/kyty_emulator
        mkdir -p "$E/$v"; rm -rf "$E/$v/obj" "$E/$v/lib"
        [ -f "$bin" ] && mv "$bin" "$bin.$(m "$bin" | cut -c1-8)"
        distrobox enter ubuntu -- sh -c "cd '$b' && ninja -t compdb -x" > "$E/$v/compdb.json" 2> "$R/compdb-$v.err" < /dev/null || stop "compdb $v failed"
        distrobox enter ubuntu -- env LC_ALL=C LANGUAGE=C python3 -I "$HERE/build0437.py" emu "$E/$v/compdb.json" "$S/kyty" "$E/$v" "$b" "$bin" \
            "ARCHIVE=$SA" "$MEMC" "$UNIT" > "$R/build-$v.out" 2>&1 < /dev/null
        rc=$?; echo "$v: build rc $rc; errors $(grep -c 'error:' "$R/build-$v.out"); warnings $(grep -c 'warning:' "$R/build-$v.out")"
        grep -n "error:\|undefined\|COMPILE FAILED\|AssertionError" "$R/build-$v.out" | head -20
        [ "$rc" = 0 ] && [ -x "$bin" ] || stop "build $v failed: $R/build-$v.out"
        m "$bin" > "$E/$v/binary.md5"
        strings "$bin" > "$E/$v/strings.txt"
        echo "$v: $(cut -c1-8 "$E/$v/binary.md5"); 'tag vg437' $(grep -c 'tag vg437' "$E/$v/strings.txt"); BC5_DIRECT_VIEWS_GEN $(grep -c 'BC5_DIRECT_VIEWS_GEN' "$E/$v/strings.txt")"
        grep -q 'BC5_DIRECT_VIEWS_GEN' "$E/$v/strings.txt" || stop "the switch is not in $v"
    done
    echo "private normal $(cut -c1-8 "$E/normal/binary.md5"), lean $(cut -c1-8 "$E/lean/binary.md5"), backend archive the shared ${sa:0:8}"
    [ "$sn" = "$(m "$W/kytyplus-build/src/kyty_emulator")" ] && [ "$sl" = "$(m "$W/kytyplus-build-lean/src/kyty_emulator")" ] \
        && [ "$sa" = "$(m "$SA")" ] && [ "$(m "$TREE/$UNIT")" = "$P_UNIT" ] && [ "$(m "$TREE/$MEMC")" = "$P_MEMC" ] \
        || stop "a shared binary, the archive or the tree changed"
    echo "shared normal ${sn:0:8}, lean ${sl:0:8}, archive ${sa:0:8}, tree units: unchanged"
    # the class test on the box's compiler (the laptop ran it with clang 22): the kit's memory.cpp and the tree's headers
    rm -rf "$E/t437"; mkdir -p "$E/t437/src/kernel" "$E/t437/src/bc5" || stop "mkdir t437"
    cp "$HERE/memory.cpp" "$E/t437/src/kernel/" && cp "$TREE/src/bc5/map_records.hpp" "$TREE/src/bc5/env_rule.hpp" "$E/t437/src/bc5/" || stop "copy t437"
    distrobox enter ubuntu -- env CXX=g++ TMPDIR="$E/t437" bash "$HERE/test_vg437.sh" "$E/t437" 200 > "$R/test-vg437.out" 2>&1 < /dev/null
    rc=$?; tail -3 "$R/test-vg437.out"; [ "$rc" = 0 ] || stop "the class test failed (rc $rc): $R/test-vg437.out"
}
case "${1:-}" in
    claim) claim "${2:-private build}" "${3:-30}" ;;
    build) build ;;
    release) release ;;
    *) stop "usage: box0437.sh claim|build|release" ;;
esac
