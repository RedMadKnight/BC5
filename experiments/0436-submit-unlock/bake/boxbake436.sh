#!/usr/bin/env bash
# BC5 experiment 0436, the BAKE's private build (2026-11-20, the maintainer's order to deploy at once): the candidate with its
# switch BC5_DIRECT_SUBMIT_UNLOCK removed (bake/mkbake436.py), CPU only (nice 19), nothing shared written; box0436.sh
# with the kit's unit, the output under ~/bc5-work/exp0436/bake and the strings check turned round (no switch word). After exp 0433's box0433.sh (its atomic
# claim, R35) and exp 0430's private archive.
#   box0436.sh claim [what] [minutes]   takes ~/bc5-work/BOX-LOCK atomically (hard link), refuses a foreign line
#   box0436.sh build                    with our lock: pins the shared inputs (tree unit, backend source, archive, builds),
#                                       puts this kit's three files into copies, compiles direct.cpp into a private copy of
#                                       the shared archive (the shared backend build's own command) and bc5LleAgc.cpp with
#                                       the shared normal and lean builds' own commands, links each with the private archive:
#                                       ~/bc5-work/exp0436/{normal,lean}/kyty_emulator, ~/bc5-work/exp0436/backend/libbc5_backend.a
#   box0436.sh release                  clears the lock only if it holds our exact line
# Beside this script (scp'd to ~/bc5-work/exp0436/kit): build0436.py (exp 0433's build0433.py, unchanged),
# bc5LleAgc.cpp (patch 8986853b's unit + mkhost436.py), be/direct.cpp and be/direct.hpp (main's backend + mkbe436.py).
set -u
export LC_ALL=C LANGUAGE=C
W=$HOME/bc5-work; E=$W/exp0436/bake; R=$E/raw; S=$E/src; LOCK=$W/BOX-LOCK; ID=$E/lock.line
TREE=$HOME/src/KytyPlus; HERE=$(cd "$(dirname "$0")" && pwd)
# the shared archive (51db2c91) is exp 0433's copy of exp 0432's 6eac453e with policy.cpp.o replaced; its direct.cpp.o was
# compiled by exp 0432 from $W/exp0432/be-src (d19/export/backend + main's direct.cpp 52f74d0e) in $W/exp0432/be-build.
# ~/src/bc5 on the box is an old modified checkout (d0c2668) and is not used.
BTREE=$W/exp0432/be-src; BBUILD=$W/exp0432/be-build; SA=$W/backend-ubuntu/libbc5_backend.a
UNIT=src/libs/bc5LleAgc.cpp
# pins: the shared inputs as patch 8986853b's swap left them, and this kit's files
P_UNIT=6f4bf71a38502fa7d6d40bfb806bce1d    # the shared tree's bc5LleAgc.cpp (patch 8986853b's, as on main)
P_BE_CPP=52f74d0ef67f37f6b9d304f9a5fef610  # ~/src/bc5/backend/src/direct.cpp (main's)
P_BE_HPP=24988c4ea441e812775743d2d6c5c28c  # ~/src/bc5/backend/include/bc5/direct.hpp (main's)
P_ARCH=51db2c91; P_NORMAL=99f2a567; P_LEAN=82720cca
K_UNIT=a62e8bf6251a44f147a23d9689449e21; K_BE_CPP=eacf8d2a11de31eb43c3dba1560c798e; K_BE_HPP=9256f3b96dc979db4a6471c7e4a1e410
K_PY=5dfb35d884bee8af31d81e3ad8b92548
stop() { echo "0436 STOP: $*"; exit 1; }
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
    own || stop "no lock held by 0436"
    pgrep '^kyty_emulator' > /dev/null && stop "an emulator runs"
    local v b bin rc sn sl sa
    sn=$(m "$W/kytyplus-build/src/kyty_emulator"); sl=$(m "$W/kytyplus-build-lean/src/kyty_emulator"); sa=$(m "$SA")
    [ "${sn:0:8}" = "$P_NORMAL" ] && [ "${sl:0:8}" = "$P_LEAN" ] && [ "${sa:0:8}" = "$P_ARCH" ] \
        || stop "the shared builds are not normal $P_NORMAL / lean $P_LEAN / archive $P_ARCH: ${sn:0:8} ${sl:0:8} ${sa:0:8}"
    [ "$(m "$TREE/$UNIT")" = "$P_UNIT" ] || stop "the shared tree's $UNIT is not patch 8986853b's ($(m "$TREE/$UNIT"))"
    [ "$(m "$BTREE/src/direct.cpp")" = "$P_BE_CPP" ] && [ "$(m "$BTREE/include/bc5/direct.hpp")" = "$P_BE_HPP" ] \
        || stop "the shared backend source is not main's: direct.cpp $(m "$BTREE/src/direct.cpp"), direct.hpp $(m "$BTREE/include/bc5/direct.hpp")"
    [ "$(m "$HERE/bc5LleAgc.cpp")" = "$K_UNIT" ] && [ "$(m "$HERE/be/direct.cpp")" = "$K_BE_CPP" ] && [ "$(m "$HERE/be/direct.hpp")" = "$K_BE_HPP" ] \
        && [ "$(m "$HERE/build0436.py")" = "$K_PY" ] || stop "the kit's files are not the pinned ones"
    rm -rf "$S"; mkdir -p "$S/kyty/src/libs" "$S/kyty/src/bc5" "$S/backend/src" "$S/backend/include/bc5" "$E/backend" || stop "mkdir $S"
    cp "$HERE/bc5LleAgc.cpp" "$S/kyty/$UNIT" && cp "$HERE/be/direct.hpp" "$S/kyty/src/bc5/direct.hpp" \
        && cp "$HERE/be/direct.cpp" "$S/backend/src/direct.cpp" && cp "$HERE/be/direct.hpp" "$S/backend/include/bc5/direct.hpp" || stop "copy the kit"
    (cd "$S" && find . -type f | sort | xargs md5sum) > "$R/src-md5.txt"; cat "$R/src-md5.txt"
    # the private archive: the shared archive with direct.cpp.o compiled from the kit's direct.cpp (the -I of the copy first)
    distrobox enter ubuntu -- sh -c "cd '$BBUILD' && ninja -t compdb" > "$E/backend/compdb.json" 2> "$R/compdb-backend.err" < /dev/null || stop "backend compdb failed"
    # the reference: main's direct.cpp, unchanged, compiled the same way, must give the shared archive's member byte for byte
    rm -rf "$S/ref" "$E/backend-ref"; mkdir -p "$S/ref/src" "$S/ref/include/bc5" "$E/backend-ref" || stop "mkdir ref"
    cp "$BTREE/src/direct.cpp" "$S/ref/src/direct.cpp" && cp "$BTREE/include/bc5/direct.hpp" "$S/ref/include/bc5/direct.hpp" || stop "copy ref"
    distrobox enter ubuntu -- env LC_ALL=C LANGUAGE=C python3 -I "$HERE/build0436.py" archive "$E/backend/compdb.json" "$S/ref" "$E/backend-ref" "$BBUILD"         "$SA" "$E/backend-ref/libbc5_backend.a" src/direct.cpp > "$R/build-backend-ref.out" 2>&1 < /dev/null || { tail -30 "$R/build-backend-ref.out"; stop "the reference compile failed"; }
    distrobox enter ubuntu -- sh -c "cd '$E/backend-ref' && ar p '$SA' direct.cpp.o > shared-direct.o && ar p libbc5_backend.a direct.cpp.o > ref-direct.o" < /dev/null || stop "ar p"
    if cmp -s "$E/backend-ref/shared-direct.o" "$E/backend-ref/ref-direct.o"; then echo "reference: direct.cpp.o of 52f74d0e compiled here == the shared archive's member ($(m "$E/backend-ref/ref-direct.o" | cut -c1-8))"
    else stop "the reference direct.cpp.o ($(m "$E/backend-ref/ref-direct.o" | cut -c1-8)) is not the shared archive's ($(m "$E/backend-ref/shared-direct.o" | cut -c1-8))"; fi
    rm -f "$E/backend/libbc5_backend.a"; rm -rf "$E/backend/obj" "$E/backend/member"
    distrobox enter ubuntu -- env LC_ALL=C LANGUAGE=C python3 -I "$HERE/build0436.py" archive "$E/backend/compdb.json" "$S/backend" "$E/backend" "$BBUILD" \
        "$SA" "$E/backend/libbc5_backend.a" src/direct.cpp > "$R/build-backend.out" 2>&1 < /dev/null \
        || { tail -40 "$R/build-backend.out"; stop "backend archive failed"; }
    echo "backend: errors $(grep -c 'error:' "$R/build-backend.out"); warnings $(grep -c 'warning:' "$R/build-backend.out")"
    m "$E/backend/libbc5_backend.a" > "$E/backend/archive.md5"
    for v in normal lean; do
        b=$W/kytyplus-build$([ $v = lean ] && echo -lean); bin=$E/$v/kyty_emulator
        mkdir -p "$E/$v"; rm -rf "$E/$v/obj" "$E/$v/lib"
        [ -f "$bin" ] && mv "$bin" "$bin.$(m "$bin" | cut -c1-8)"
        distrobox enter ubuntu -- sh -c "cd '$b' && ninja -t compdb -x" > "$E/$v/compdb.json" 2> "$R/compdb-$v.err" < /dev/null || stop "compdb $v failed"
        distrobox enter ubuntu -- env LC_ALL=C LANGUAGE=C python3 -I "$HERE/build0436.py" emu "$E/$v/compdb.json" "$S/kyty" "$E/$v" "$b" "$bin" \
            "ARCHIVE=$E/backend/libbc5_backend.a" "$UNIT" > "$R/build-$v.out" 2>&1 < /dev/null
        rc=$?; echo "$v: build rc $rc; errors $(grep -c 'error:' "$R/build-$v.out"); warnings $(grep -c 'warning:' "$R/build-$v.out")"
        grep -n "error:\|undefined\|COMPILE FAILED\|AssertionError" "$R/build-$v.out" | head -20
        [ "$rc" = 0 ] && [ -x "$bin" ] || stop "build $v failed: $R/build-$v.out"
        m "$bin" > "$E/$v/binary.md5"
        strings "$bin" > "$E/$v/strings.txt"
        echo "$v: $(cut -c1-8 "$E/$v/binary.md5"); 'tag su436' $(grep -c 'tag su436' "$E/$v/strings.txt"); SUBMIT_UNLOCK $(grep -c 'SUBMIT_UNLOCK' "$E/$v/strings.txt")"
        grep -q 'SUBMIT_UNLOCK' "$E/$v/strings.txt" && stop "a SUBMIT_UNLOCK word is in $v"
        if [ $v = normal ]; then grep -q 'tag su436' "$E/$v/strings.txt" || stop "normal lacks the su436 count line"
        else grep -q 'tag su436' "$E/$v/strings.txt" && stop "lean holds the su436 count line"; fi
    done
    echo "private normal $(cut -c1-8 "$E/normal/binary.md5"), lean $(cut -c1-8 "$E/lean/binary.md5"), backend archive $(cut -c1-8 "$E/backend/archive.md5")"
    [ "$sn" = "$(m "$W/kytyplus-build/src/kyty_emulator")" ] && [ "$sl" = "$(m "$W/kytyplus-build-lean/src/kyty_emulator")" ] \
        && [ "$sa" = "$(m "$SA")" ] && [ "$(m "$TREE/$UNIT")" = "$P_UNIT" ] || stop "a shared binary, the archive or the tree changed"
    echo "shared normal ${sn:0:8}, lean ${sl:0:8}, archive ${sa:0:8}, tree unit ${P_UNIT:0:8}: unchanged"
}
case "${1:-}" in
    claim) claim "${2:-private build}" "${3:-30}" ;;
    build) build ;;
    release) release ;;
    *) stop "usage: box0436.sh claim|build|release" ;;
esac
