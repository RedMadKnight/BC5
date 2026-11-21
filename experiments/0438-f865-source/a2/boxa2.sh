#!/usr/bin/env bash
# BC5 experiment 0438 (tag a2): the private build of A2 (the backend's sorted mapping list as a chunked index, switch
# BC5_DIRECT_0438_A2), CPU only, nice 19 + ionice idle, NO lock line (the top session's GO of 2026-11-21: exp 0439
# holds BOX-LOCK). exp 0436's boxbake436.sh build() with its pins moved to the shared state since exp 0438's bake and
# its kit files to A2's: the reference direct.cpp (the shared backend source, eacf8d2a) compiled the same way must
# give the shared archive's member byte for byte; then the kit's direct.cpp into a private copy of the archive, and the
# host unit (a2host.cpp) with the shared normal and lean builds' own commands, linked with the private archive:
# ~/bc5-work/exp0438/a2/{normal,lean}/kyty_emulator, ~/bc5-work/exp0438/a2/backend/libbc5_backend.a.
#   boxa2.sh build
# Beside this script (scp'd to ~/bc5-work/exp0438/a2kit): build0438.py, a2host.cpp, be/direct.cpp, be/direct.hpp,
# be/mapping_index.hpp.
set -u
export LC_ALL=C LANGUAGE=C
W=$HOME/bc5-work; E=$W/exp0438/a2; R=$E/raw; S=$E/src; LOCK=$W/BOX-LOCK; ID=$E/lock.line
TREE=$HOME/src/KytyPlus; HERE=$(cd "$(dirname "$0")" && pwd)
# the shared archive d6638808 (exp 0436's bake): its direct.cpp.o from the shared backend source d19/export/backend
# (direct.cpp eacf8d2a, direct.hpp 9256f3b9), built in backend-ubuntu
BTREE=$W/d19/export/backend; BBUILD=$W/backend-ubuntu; SA=$W/backend-ubuntu/libbc5_backend.a
UNIT=src/libs/bc5LleAgc.cpp
P_UNIT=ff9e8fe2e4139264ebaf74f9e84bd892    # the shared tree's bc5LleAgc.cpp (patch 9889b06a's)
P_BE_CPP=eacf8d2a
P_BE_HPP=9256f3b9
P_ARCH=d6638808; P_NORMAL=b1b57df9; P_LEAN=d3485ed4
K_UNIT=0402a183e527bca6d1d27b5d02bc0c38; K_BE_CPP=66f9893767d2b18adf1a6ed3eb8aec80; K_BE_HPP=18c66de84ae1a6705462cd4953cd6633; K_MI=39952c484209fe5c64a55167f02107b7
K_PY=3fe0aacaa3a2859de7f9903e127a5a63
NICE="nice -n 19 ionice -c 3"
stop() { echo "a2 STOP: $*"; exit 1; }
m() { md5sum < "$1" 2> /dev/null | cut -d' ' -f1; }
own() { [ -s "$ID" ] && [ "$(cat "$LOCK" 2> /dev/null)" = "$(cat "$ID")" ]; }
claim() {
    local c=$LOCK.d19-claim t=$LOCK.0436-$$.new a=$LOCK.0436-$$.aside line
    pgrep '^kyty_emulator' > /dev/null && stop "an emulator runs"
    [ ! -L "$E" ] || stop "$E is a link"
    mkdir -p "$R" || stop "cannot make $R"
    line="exp 0436 | token $(date +%s)$$ | $1, until $(date -d +"$2"min +%H:%M) | $(date '+%F %T')"
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
    mkdir -p "$R" || stop "cannot make $R" # no claim here (no lock line): the directory is made by build itself
    pgrep '^kyty_emulator' > /dev/null && stop "an emulator runs"
    local v b bin rc sn sl sa
    sn=$(m "$W/kytyplus-build/src/kyty_emulator"); sl=$(m "$W/kytyplus-build-lean/src/kyty_emulator"); sa=$(m "$SA")
    [ "${sn:0:8}" = "$P_NORMAL" ] && [ "${sl:0:8}" = "$P_LEAN" ] && [ "${sa:0:8}" = "$P_ARCH" ] \
        || stop "the shared builds are not normal $P_NORMAL / lean $P_LEAN / archive $P_ARCH: ${sn:0:8} ${sl:0:8} ${sa:0:8}"
    [ "$(m "$TREE/$UNIT")" = "$P_UNIT" ] || stop "the shared tree's $UNIT is not patch 9889b06a's ($(m "$TREE/$UNIT"))"
    [ "$(m "$BTREE/src/direct.cpp" | cut -c1-8)" = "$P_BE_CPP" ] && [ "$(m "$BTREE/include/bc5/direct.hpp" | cut -c1-8)" = "$P_BE_HPP" ] \
        || stop "the shared backend source is not main's: direct.cpp $(m "$BTREE/src/direct.cpp"), direct.hpp $(m "$BTREE/include/bc5/direct.hpp")"
    [ "$(m "$HERE/a2host.cpp")" = "$K_UNIT" ] && [ "$(m "$HERE/be/direct.cpp")" = "$K_BE_CPP" ] && [ "$(m "$HERE/be/direct.hpp")" = "$K_BE_HPP" ] \
        && [ "$(m "$HERE/be/mapping_index.hpp")" = "$K_MI" ] && [ "$(m "$HERE/build0438.py")" = "$K_PY" ] || stop "the kit's files are not the pinned ones"
    rm -rf "$S"; mkdir -p "$S/kyty/src/libs" "$S/kyty/src/bc5" "$S/backend/src" "$S/backend/include/bc5" "$E/backend" || stop "mkdir $S"
    cp "$HERE/a2host.cpp" "$S/kyty/$UNIT" && cp "$HERE/be/direct.hpp" "$S/kyty/src/bc5/direct.hpp" && cp "$HERE/be/mapping_index.hpp" "$S/kyty/src/bc5/mapping_index.hpp" \
        && cp "$HERE/be/direct.cpp" "$S/backend/src/direct.cpp" && cp "$HERE/be/direct.hpp" "$S/backend/include/bc5/direct.hpp" && cp "$HERE/be/mapping_index.hpp" "$S/backend/include/bc5/mapping_index.hpp" || stop "copy the kit"
    (cd "$S" && find . -type f | sort | xargs md5sum) > "$R/src-md5.txt"; cat "$R/src-md5.txt"
    # the private archive: the shared archive with direct.cpp.o compiled from the kit's direct.cpp (the -I of the copy first)
    distrobox enter ubuntu -- sh -c "cd '$BBUILD' && ninja -t compdb" > "$E/backend/compdb.json" 2> "$R/compdb-backend.err" < /dev/null || stop "backend compdb failed"
    # the reference: main's direct.cpp, unchanged, compiled the same way, must give the shared archive's member byte for byte
    rm -rf "$S/ref" "$E/backend-ref"; mkdir -p "$S/ref/src" "$S/ref/include/bc5" "$E/backend-ref" || stop "mkdir ref"
    cp "$BTREE/src/direct.cpp" "$S/ref/src/direct.cpp" && cp "$BTREE/include/bc5/direct.hpp" "$S/ref/include/bc5/direct.hpp" || stop "copy ref"
    distrobox enter ubuntu -- $NICE env LC_ALL=C LANGUAGE=C python3 -I "$HERE/build0438.py" archive "$E/backend/compdb.json" "$S/ref" "$E/backend-ref" "$BBUILD"         "$SA" "$E/backend-ref/libbc5_backend.a" src/direct.cpp > "$R/build-backend-ref.out" 2>&1 < /dev/null || { tail -30 "$R/build-backend-ref.out"; stop "the reference compile failed"; }
    distrobox enter ubuntu -- sh -c "cd '$E/backend-ref' && ar p '$SA' direct.cpp.o > shared-direct.o && ar p libbc5_backend.a direct.cpp.o > ref-direct.o" < /dev/null || stop "ar p"
    if cmp -s "$E/backend-ref/shared-direct.o" "$E/backend-ref/ref-direct.o"; then echo "reference: direct.cpp.o of eacf8d2a compiled here == the shared archive's member ($(m "$E/backend-ref/ref-direct.o" | cut -c1-8))"
    else stop "the reference direct.cpp.o ($(m "$E/backend-ref/ref-direct.o" | cut -c1-8)) is not the shared archive's ($(m "$E/backend-ref/shared-direct.o" | cut -c1-8))"; fi
    rm -f "$E/backend/libbc5_backend.a"; rm -rf "$E/backend/obj" "$E/backend/member"
    distrobox enter ubuntu -- $NICE env LC_ALL=C LANGUAGE=C python3 -I "$HERE/build0438.py" archive "$E/backend/compdb.json" "$S/backend" "$E/backend" "$BBUILD" \
        "$SA" "$E/backend/libbc5_backend.a" src/direct.cpp > "$R/build-backend.out" 2>&1 < /dev/null \
        || { tail -40 "$R/build-backend.out"; stop "backend archive failed"; }
    echo "backend: errors $(grep -c 'error:' "$R/build-backend.out"); warnings $(grep -c 'warning:' "$R/build-backend.out")"
    echo "MemAvailable before the links: $(awk '/^MemAvailable/{print int($2/1024)}' /proc/meminfo) MiB"
    echo "MemAvailable $(awk '/^MemAvailable/{print int($2/1024)}' /proc/meminfo) MiB (build0438.py waits before each link while under 4 GiB)"
    m "$E/backend/libbc5_backend.a" > "$E/backend/archive.md5"
    for v in normal lean; do
        b=$W/kytyplus-build$([ $v = lean ] && echo -lean); bin=$E/$v/kyty_emulator
        mkdir -p "$E/$v"; rm -rf "$E/$v/obj" "$E/$v/lib"
        [ -f "$bin" ] && mv "$bin" "$bin.$(m "$bin" | cut -c1-8)"
        distrobox enter ubuntu -- sh -c "cd '$b' && ninja -t compdb -x" > "$E/$v/compdb.json" 2> "$R/compdb-$v.err" < /dev/null || stop "compdb $v failed"
        distrobox enter ubuntu -- $NICE env LC_ALL=C LANGUAGE=C python3 -I "$HERE/build0438.py" emu "$E/$v/compdb.json" "$S/kyty" "$E/$v" "$b" "$bin" \
            "ARCHIVE=$E/backend/libbc5_backend.a" "$UNIT" > "$R/build-$v.out" 2>&1 < /dev/null
        rc=$?; echo "$v: build rc $rc; errors $(grep -c 'error:' "$R/build-$v.out"); warnings $(grep -c 'warning:' "$R/build-$v.out")"
        grep -n "error:\|undefined\|COMPILE FAILED\|AssertionError" "$R/build-$v.out" | head -20
        [ "$rc" = 0 ] && [ -x "$bin" ] || stop "build $v failed: $R/build-$v.out"
        m "$bin" > "$E/$v/binary.md5"
        strings "$bin" > "$E/$v/strings.txt"
        echo "$v: $(cut -c1-8 "$E/$v/binary.md5"); BC5_DIRECT_0438_A2 $(grep -c 'BC5_DIRECT_0438_A2$' "$E/$v/strings.txt"); A2_CHECK $(grep -c 'BC5_DIRECT_0438_A2_CHECK' "$E/$v/strings.txt"); EARLYREG $(grep -c BC5_0438_EARLYREG "$E/$v/strings.txt")"
        grep -qx 'BC5_DIRECT_0438_A2' "$E/$v/strings.txt" && grep -q 'BC5_DIRECT_0438_A2_CHECK' "$E/$v/strings.txt" && grep -q 'BC5_0438_EARLYREG' "$E/$v/strings.txt" || stop "a switch is not in $v"
    done
    echo "private normal $(cut -c1-8 "$E/normal/binary.md5"), lean $(cut -c1-8 "$E/lean/binary.md5"), backend archive $(cut -c1-8 "$E/backend/archive.md5")"
    [ "$sn" = "$(m "$W/kytyplus-build/src/kyty_emulator")" ] && [ "$sl" = "$(m "$W/kytyplus-build-lean/src/kyty_emulator")" ] \
        && [ "$sa" = "$(m "$SA")" ] && [ "$(m "$TREE/$UNIT")" = "$P_UNIT" ] || stop "a shared binary, the archive or the tree changed"
    echo "shared normal ${sn:0:8}, lean ${sl:0:8}, archive ${sa:0:8}, tree unit ${P_UNIT:0:8}: unchanged"
}
case "${1:-}" in
    build) build ;;
    *) stop "usage: boxa2.sh build" ;;
esac
