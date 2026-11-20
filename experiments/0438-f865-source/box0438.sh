#!/usr/bin/env bash
# BC5 experiment 0438 (F865): box helper. claim/release as exp 0436's box0436.sh (atomic hard-link claim, R35);
#   box0438.sh claim [what] [minutes]
#   box0438.sh release
#   box0438.sh pack     with our lock: read-only copies of F865's records into ~/bc5-work/exp0438/fetch (gz), for scp
#   box0438.sh buildcat with our lock: exp 0438's catcher c438 (mkcat438.py on the tree's unit, records only, normal build
#                       only), compiled with the shared normal build's own command: ~/bc5-work/exp0438/cat/normal/kyty_emulator
#   box0438.sh buildr   with our lock: r438 (mkr438.py) + c438, normal build only: ~/bc5-work/exp0438/r438/normal/kyty_emulator
#   box0438.sh buildb   with our lock: b438 (mkb438.py on the tree's unit: r438 alone with PLWCV, the bake shape), normal AND
#                       lean, each with the shared build's own command: ~/bc5-work/exp0438/b438/{normal,lean}/kyty_emulator;
#                       the normal build also gets o438 (mko438.py: sync spans in six tree files, off unless
#                       BC5_0438_OUTSIDE=1; lean recompiles the unit only, so it has no o438)
#   box0438.sh buildk   with our lock: the BAKE's private build (bake/mkbake438.py: b438 without p438 and without lean's
#                       lost-write counter; EARLYREG and PLWCV kept, on unless "0"), normal and lean, unit only, the
#                       shared archive: ~/bc5-work/exp0438/bake/{normal,lean}/kyty_emulator. Nothing shared written.
#   box0438.sh build    with our lock: pins the shared builds (patch bb04219b: normal f345db74, lean 6a735b81, archive
#                       d6638808), the shared tree's unit and this kit's files; compiles the kit's bc5LleAgc.cpp (mk0438.py
#                       on the tree's unit) with the shared normal and lean builds' own commands and links each with the
#                       shared link line (shared archive): ~/bc5-work/exp0438/{normal,lean}/kyty_emulator. Nothing shared written.
set -u
export LC_ALL=C LANGUAGE=C
W=$HOME/bc5-work; E=$W/exp0438; R=$E/raw; S=$E/src; LOCK=$W/BOX-LOCK; ID=$E/lock.line
TREE=$HOME/src/KytyPlus; HERE=$(cd "$(dirname "$0")" && pwd); UNIT=src/libs/bc5LleAgc.cpp
SA=$W/backend-ubuntu/libbc5_backend.a
P_UNIT=a62e8bf6251a44f147a23d9689449e21   # the shared tree's bc5LleAgc.cpp (patch bb04219b's)
P_ARCH=d6638808; P_NORMAL=f345db74; P_LEAN=6a735b81
K_UNIT=680bda1f3430b676f2dadef8808ae24a  # k438 (off by default, refuted) + k438b (BC5_0438_HOLD); was 59a5df70 for build d4a2f86d
K_PY=5dfb35d884bee8af31d81e3ad8b92548
K_R438=94d696fbfe6cca223346ba255338a0f0  # r438.cpp: mkr438.py on cat/bc5LleAgc.cpp (3623fd41)
K_U438=78f319da0beee7c0bbb7f6b582470a2e  # u438.cpp: mkr438 -> mkc438d -> mku438 on cat/bc5LleAgc.cpp
K_S438=a56293942679688016778eef88c704c1  # s438.cpp: mks438 on u438.cpp (s438 + i438)
K_E438=3fe3a79a459cb1ea60a7d27ff92f8c14  # e438.cpp: mks438y -> mke438 on s438.cpp (e438 + y438 + i438)
K_B438=a31a2091ddeed206db7daec79771e932  # b438.cpp: mkb438.py on a62e8bf6 (r438 alone, mode 1, PLWCV, lean counter, p438 prologue merge)
K_BAKE=ff9e8fe2e4139264ebaf74f9e84bd892  # bake438.cpp: bake/mkbake438.py (mkb438.py 3b00ab29 steps 1-6, lean counter out) on a62e8bf6
K_MKO=4513a0ec8b9b53129c59329a09047f84; K_O438H=bace03013bfc35c761bf560b5bca9cf6  # mko438.py, o438.hpp
O438_UNITS="src/kernel/semaphore.cpp src/kernel/eventFlag.cpp src/kernel/pthread.cpp src/kernel/eventQueue.cpp src/libs/libKernel.cpp src/graphics/presentation/videoOut.cpp"
K_F438=346ebf6efa736bdbc5bf054901f40253  # f438.cpp: mkf438 on e438.cpp (build 12: the mapping index updated in place)
K_W438=91557164b555b297f6e1b98ddc3f887d  # w438.cpp: mkr438 -> mkc438d -> mkw438 on cat/bc5LleAgc.cpp
K_C438D=3a10750dd8e6e996afb59fc604668293  # c438d.cpp: mkc438d.py on cat/bc5LleAgc.cpp (3623fd41)
K_CAT=3623fd41142c49514fce913c34c2efab  # cat/bc5LleAgc.cpp: mkcat438.py on a62e8bf6
K_VG=cad85761590d642235cded7094c9b48c      # exp 0437's mkvg437.py (branch exp/0437-q30-syncs f89c3861), folded in (top, 2026-11-20)
MEMC=src/kernel/memory.cpp; MEMH=src/kernel/memory.h
stop() { echo "0438 STOP: $*"; exit 1; }
m() { md5sum < "$1" 2> /dev/null | cut -d' ' -f1; }
own() { [ -s "$ID" ] && [ "$(cat "$LOCK" 2> /dev/null)" = "$(cat "$ID")" ]; }
claim() {
    local c=$LOCK.d19-claim t=$LOCK.0438-$$.new a=$LOCK.0438-$$.aside line
    pgrep '^kyty_emulator' > /dev/null && stop "an emulator runs"
    [ ! -L "$E" ] || stop "$E is a link"
    mkdir -p "$R" || stop "cannot make $R"
    line="exp 0438 | token $(date +%s)$$ | $1, until $(date -d +"$2"min +%H:%M) | $(date '+%F %T')"
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
pack() {
    own || stop "no lock held by 0438"
    local g=$HOME/bc5-data/captures/play-20261120-0055/gc d=$HOME/bc5-data/captures/devcoredump/20261120-005901-devcd10.txt f=$E/fetch
    [ -d "$g" ] && [ -f "$d" ] || stop "records missing: $g $d"
    mkdir -p "$f" || stop "mkdir $f"
    ls -la "$g" > "$f/gc-ls.txt"
    for x in "$g"/ib-timeout-* ; do [ -f "$x" ] && gzip -c "$x" > "$f/$(basename "$x").gz"; done
    gzip -c "$g/direct.log" > "$f/direct.log.gz" || stop "gzip direct.log"
    gzip -c "$d" > "$f/devcd10.txt.gz" || stop "gzip devcd"
    ls -la "$f"
}
build() {
    own || stop "no lock held by 0438"
    pgrep '^kyty_emulator' > /dev/null && stop "an emulator runs"
    local v b bin rc sn sl sa
    sn=$(m "$W/kytyplus-build/src/kyty_emulator"); sl=$(m "$W/kytyplus-build-lean/src/kyty_emulator"); sa=$(m "$SA")
    [ "${sn:0:8}" = "$P_NORMAL" ] && [ "${sl:0:8}" = "$P_LEAN" ] && [ "${sa:0:8}" = "$P_ARCH" ]         || stop "the shared builds are not normal $P_NORMAL / lean $P_LEAN / archive $P_ARCH: ${sn:0:8} ${sl:0:8} ${sa:0:8}"
    [ "$(m "$TREE/$UNIT")" = "$P_UNIT" ] || stop "the shared tree's $UNIT is not patch bb04219b's ($(m "$TREE/$UNIT"))"
    [ "$(m "$HERE/bc5LleAgc.cpp")" = "$K_UNIT" ] && [ "$(m "$HERE/build0438.py")" = "$K_PY" ] && [ "$(m "$HERE/mkvg437.py")" = "$K_VG" ]         || stop "the kit's files are not the pinned ones"
    mkdir -p "$R" || stop "mkdir $R"
    rm -rf "$S"; mkdir -p "$S/kyty/src/libs" "$S/kyty/src/kernel" || stop "mkdir $S"
    # k438 first (its input is pinned), then exp 0437's vg437 on the copy (memory.cpp, memory.h, the unit; its anchors
    # do not touch k438's). memory.h gains one free-function declaration only, so the other units are unchanged.
    cp "$HERE/bc5LleAgc.cpp" "$S/kyty/$UNIT" && cp "$TREE/$MEMC" "$S/kyty/$MEMC" && cp "$TREE/$MEMH" "$S/kyty/$MEMH" || stop "copy the kit"
    echo "tree memory.cpp $(m "$TREE/$MEMC"), memory.h $(m "$TREE/$MEMH")"
    python3 -I "$HERE/mkvg437.py" "$S/kyty" > "$R/mkvg437.out" 2>&1 || { cat "$R/mkvg437.out"; stop "mkvg437.py failed"; }
    cat "$R/mkvg437.out"
    (cd "$S/kyty" && md5sum "$UNIT" "$MEMC" "$MEMH") | tee "$R/src-md5.txt"
    for v in normal lean; do
        b=$W/kytyplus-build$([ $v = lean ] && echo -lean); bin=$E/$v/kyty_emulator
        mkdir -p "$E/$v"; rm -rf "$E/$v/obj" "$E/$v/lib"
        [ -f "$bin" ] && mv "$bin" "$bin.$(m "$bin" | cut -c1-8)"
        distrobox enter ubuntu -- sh -c "cd '$b' && ninja -t compdb -x" > "$E/$v/compdb.json" 2> "$R/compdb-$v.err" < /dev/null || stop "compdb $v failed"
        distrobox enter ubuntu -- env LC_ALL=C LANGUAGE=C python3 -I "$HERE/build0438.py" emu "$E/$v/compdb.json" "$S/kyty" "$E/$v" "$b" "$bin"             "$UNIT" "$MEMC" > "$R/build-$v.out" 2>&1 < /dev/null
        rc=$?; echo "$v: build rc $rc; errors $(grep -c 'error:' "$R/build-$v.out"); warnings $(grep -c 'warning:' "$R/build-$v.out")"
        grep -n "error:\|undefined\|COMPILE FAILED\|AssertionError" "$R/build-$v.out" | head -20
        [ "$rc" = 0 ] && [ -x "$bin" ] || stop "build $v failed: $R/build-$v.out"
        m "$bin" > "$E/$v/binary.md5"
        strings "$bin" > "$E/$v/strings.txt"
        echo "$v: $(cut -c1-8 "$E/$v/binary.md5"); BC5_0438_KEEP $(grep -c 'BC5_0438_KEEP' "$E/$v/strings.txt"); k438 journal $(grep -c 'k438 (exp 0438)' "$E/$v/strings.txt")"
        grep -q 'BC5_0438_KEEP' "$E/$v/strings.txt" && grep -q 'BC5_0438_HOLD' "$E/$v/strings.txt" && grep -q 'BC5_DIRECT_VIEWS_GEN' "$E/$v/strings.txt" || stop "a switch is not in $v"
    done
    echo "private normal $(cut -c1-8 "$E/normal/binary.md5"), lean $(cut -c1-8 "$E/lean/binary.md5")"
    [ "$sn" = "$(m "$W/kytyplus-build/src/kyty_emulator")" ] && [ "$sl" = "$(m "$W/kytyplus-build-lean/src/kyty_emulator")" ]         && [ "$sa" = "$(m "$SA")" ] && [ "$(m "$TREE/$UNIT")" = "$P_UNIT" ] || stop "a shared binary, the archive or the tree changed"
    echo "shared normal ${sn:0:8}, lean ${sl:0:8}, archive ${sa:0:8}, tree unit ${P_UNIT:0:8}: unchanged"
}
buildcat() {
    own || stop "no lock held by 0438"
    pgrep '^kyty_emulator' > /dev/null && stop "an emulator runs"
    local b bin rc sn sl sa C=$E/cat
    sn=$(m "$W/kytyplus-build/src/kyty_emulator"); sl=$(m "$W/kytyplus-build-lean/src/kyty_emulator"); sa=$(m "$SA")
    [ "${sn:0:8}" = "$P_NORMAL" ] && [ "${sl:0:8}" = "$P_LEAN" ] && [ "${sa:0:8}" = "$P_ARCH" ] || stop "the shared builds are not $P_NORMAL/$P_LEAN/$P_ARCH"
    [ "$(m "$TREE/$UNIT")" = "$P_UNIT" ] || stop "the shared tree's $UNIT is not patch bb04219b's"
    [ "$(m "$HERE/cat/bc5LleAgc.cpp")" = "$K_CAT" ] && [ "$(m "$HERE/build0438.py")" = "$K_PY" ] || stop "the catcher kit is not the pinned one"
    mkdir -p "$R" "$C/normal" || stop "mkdir"
    rm -rf "$C/src"; mkdir -p "$C/src/kyty/src/libs" && cp "$HERE/cat/bc5LleAgc.cpp" "$C/src/kyty/$UNIT" || stop "copy"
    b=$W/kytyplus-build; bin=$C/normal/kyty_emulator; rm -rf "$C/normal/obj" "$C/normal/lib"
    [ -f "$bin" ] && mv "$bin" "$bin.$(m "$bin" | cut -c1-8)"
    distrobox enter ubuntu -- sh -c "cd '$b' && ninja -t compdb -x" > "$C/normal/compdb.json" 2> "$R/compdb-cat.err" < /dev/null || stop "compdb failed"
    distrobox enter ubuntu -- env LC_ALL=C LANGUAGE=C python3 -I "$HERE/build0438.py" emu "$C/normal/compdb.json" "$C/src/kyty" "$C/normal" "$b" "$bin" "$UNIT" > "$R/build-cat.out" 2>&1 < /dev/null
    rc=$?; echo "cat normal: build rc $rc; errors $(grep -c 'error:' "$R/build-cat.out"); warnings $(grep -c 'warning:' "$R/build-cat.out")"
    grep -n "error:\|undefined\|COMPILE FAILED" "$R/build-cat.out" | head -20
    [ "$rc" = 0 ] && [ -x "$bin" ] || stop "build failed: $R/build-cat.out"
    m "$bin" > "$C/normal/binary.md5"; strings "$bin" > "$C/normal/strings.txt"
    echo "cat normal: $(cut -c1-8 "$C/normal/binary.md5"); c438 lines $(grep -c 'c438 (exp 0438)' "$C/normal/strings.txt")"
    grep -q 'c438 (exp 0438)' "$C/normal/strings.txt" || stop "the catcher is not in the binary"
    [ "$sn" = "$(m "$W/kytyplus-build/src/kyty_emulator")" ] && [ "$sa" = "$(m "$SA")" ] && [ "$(m "$TREE/$UNIT")" = "$P_UNIT" ] || stop "a shared file changed"
    echo "shared normal ${sn:0:8}, archive ${sa:0:8}, tree unit ${P_UNIT:0:8}: unchanged"
}
buildd() {
    own || stop "no lock held by 0438"
    pgrep '^kyty_emulator' > /dev/null && stop "an emulator runs"
    local b bin rc sn sl sa C=$E/c438d
    sn=$(m "$W/kytyplus-build/src/kyty_emulator"); sl=$(m "$W/kytyplus-build-lean/src/kyty_emulator"); sa=$(m "$SA")
    [ "${sn:0:8}" = "$P_NORMAL" ] && [ "${sl:0:8}" = "$P_LEAN" ] && [ "${sa:0:8}" = "$P_ARCH" ] || stop "the shared builds are not $P_NORMAL/$P_LEAN/$P_ARCH"
    [ "$(m "$TREE/$UNIT")" = "$P_UNIT" ] || stop "the shared tree's $UNIT is not patch bb04219b's"
    [ "$(m "$HERE/c438d.cpp")" = "$K_C438D" ] && [ "$(m "$HERE/build0438.py")" = "$K_PY" ] || stop "the c438d kit is not the pinned one"
    mkdir -p "$R" "$C/normal" || stop "mkdir"
    rm -rf "$C/src"; mkdir -p "$C/src/kyty/src/libs" && cp "$HERE/c438d.cpp" "$C/src/kyty/$UNIT" || stop "copy"
    b=$W/kytyplus-build; bin=$C/normal/kyty_emulator; rm -rf "$C/normal/obj" "$C/normal/lib"
    [ -f "$bin" ] && mv "$bin" "$bin.$(m "$bin" | cut -c1-8)"
    distrobox enter ubuntu -- sh -c "cd '$b' && ninja -t compdb -x" > "$C/normal/compdb.json" 2> "$R/compdb-c438d.err" < /dev/null || stop "compdb failed"
    distrobox enter ubuntu -- env LC_ALL=C LANGUAGE=C python3 -I "$HERE/build0438.py" emu "$C/normal/compdb.json" "$C/src/kyty" "$C/normal" "$b" "$bin" "$UNIT" > "$R/build-c438d.out" 2>&1 < /dev/null
    rc=$?; echo "c438d normal: build rc $rc; errors $(grep -c 'error:' "$R/build-c438d.out"); warnings $(grep -c 'warning:' "$R/build-c438d.out")"
    grep -n "error:\|undefined\|COMPILE FAILED" "$R/build-c438d.out" | head -20
    [ "$rc" = 0 ] && [ -x "$bin" ] || stop "build failed: $R/build-c438d.out"
    m "$bin" > "$C/normal/binary.md5"; strings "$bin" > "$C/normal/strings.txt"
    echo "c438d normal: $(cut -c1-8 "$C/normal/binary.md5"); c438 lines $(grep -c 'c438 (exp 0438)' "$C/normal/strings.txt")"
    grep -q 'c438d (exp 0438)' "$C/normal/strings.txt" || stop "c438d is not in the binary"
    [ "$sn" = "$(m "$W/kytyplus-build/src/kyty_emulator")" ] && [ "$sa" = "$(m "$SA")" ] && [ "$(m "$TREE/$UNIT")" = "$P_UNIT" ] || stop "a shared file changed"
    echo "shared normal ${sn:0:8}, archive ${sa:0:8}, tree unit ${P_UNIT:0:8}: unchanged"
}
buildu() {
    own || stop "no lock held by 0438"
    pgrep '^kyty_emulator' > /dev/null && stop "an emulator runs"
    local b bin rc sn sl sa C=$E/u438
    sn=$(m "$W/kytyplus-build/src/kyty_emulator"); sl=$(m "$W/kytyplus-build-lean/src/kyty_emulator"); sa=$(m "$SA")
    [ "${sn:0:8}" = "$P_NORMAL" ] && [ "${sl:0:8}" = "$P_LEAN" ] && [ "${sa:0:8}" = "$P_ARCH" ] || stop "the shared builds are not $P_NORMAL/$P_LEAN/$P_ARCH"
    [ "$(m "$TREE/$UNIT")" = "$P_UNIT" ] || stop "the shared tree's $UNIT is not patch bb04219b's"
    [ "$(m "$HERE/u438.cpp")" = "$K_U438" ] && [ "$(m "$HERE/build0438.py")" = "$K_PY" ] || stop "the u438 kit is not the pinned one"
    mkdir -p "$R" "$C/normal" || stop "mkdir"
    rm -rf "$C/src"; mkdir -p "$C/src/kyty/src/libs" && cp "$HERE/u438.cpp" "$C/src/kyty/$UNIT" || stop "copy"
    b=$W/kytyplus-build; bin=$C/normal/kyty_emulator; rm -rf "$C/normal/obj" "$C/normal/lib"
    [ -f "$bin" ] && mv "$bin" "$bin.$(m "$bin" | cut -c1-8)"
    distrobox enter ubuntu -- sh -c "cd '$b' && ninja -t compdb -x" > "$C/normal/compdb.json" 2> "$R/compdb-u438.err" < /dev/null || stop "compdb failed"
    distrobox enter ubuntu -- env LC_ALL=C LANGUAGE=C python3 -I "$HERE/build0438.py" emu "$C/normal/compdb.json" "$C/src/kyty" "$C/normal" "$b" "$bin" "$UNIT" > "$R/build-u438.out" 2>&1 < /dev/null
    rc=$?; echo "u438 normal: build rc $rc; errors $(grep -c 'error:' "$R/build-u438.out"); warnings $(grep -c 'warning:' "$R/build-u438.out")"
    grep -n "error:\|undefined\|COMPILE FAILED" "$R/build-u438.out" | head -20
    [ "$rc" = 0 ] && [ -x "$bin" ] || stop "build failed: $R/build-u438.out"
    m "$bin" > "$C/normal/binary.md5"; strings "$bin" > "$C/normal/strings.txt"
    echo "u438 normal: $(cut -c1-8 "$C/normal/binary.md5"); c438 lines $(grep -c 'c438 (exp 0438)' "$C/normal/strings.txt")"
    grep -q 'BC5_0438_SPLIT' "$C/normal/strings.txt" || stop "u438 is not in the binary"
    [ "$sn" = "$(m "$W/kytyplus-build/src/kyty_emulator")" ] && [ "$sa" = "$(m "$SA")" ] && [ "$(m "$TREE/$UNIT")" = "$P_UNIT" ] || stop "a shared file changed"
    echo "shared normal ${sn:0:8}, archive ${sa:0:8}, tree unit ${P_UNIT:0:8}: unchanged"
}
builds() {
    own || stop "no lock held by 0438"
    pgrep '^kyty_emulator' > /dev/null && stop "an emulator runs"
    local b bin rc sn sl sa C=$E/s438
    sn=$(m "$W/kytyplus-build/src/kyty_emulator"); sl=$(m "$W/kytyplus-build-lean/src/kyty_emulator"); sa=$(m "$SA")
    [ "${sn:0:8}" = "$P_NORMAL" ] && [ "${sl:0:8}" = "$P_LEAN" ] && [ "${sa:0:8}" = "$P_ARCH" ] || stop "the shared builds are not $P_NORMAL/$P_LEAN/$P_ARCH"
    [ "$(m "$TREE/$UNIT")" = "$P_UNIT" ] || stop "the shared tree's $UNIT is not patch bb04219b's"
    [ "$(m "$HERE/s438.cpp")" = "$K_S438" ] && [ "$(m "$HERE/build0438.py")" = "$K_PY" ] || stop "the s438 kit is not the pinned one"
    mkdir -p "$R" "$C/normal" || stop "mkdir"
    rm -rf "$C/src"; mkdir -p "$C/src/kyty/src/libs" && cp "$HERE/s438.cpp" "$C/src/kyty/$UNIT" || stop "copy"
    b=$W/kytyplus-build; bin=$C/normal/kyty_emulator; rm -rf "$C/normal/obj" "$C/normal/lib"
    [ -f "$bin" ] && mv "$bin" "$bin.$(m "$bin" | cut -c1-8)"
    distrobox enter ubuntu -- sh -c "cd '$b' && ninja -t compdb -x" > "$C/normal/compdb.json" 2> "$R/compdb-s438.err" < /dev/null || stop "compdb failed"
    distrobox enter ubuntu -- env LC_ALL=C LANGUAGE=C python3 -I "$HERE/build0438.py" emu "$C/normal/compdb.json" "$C/src/kyty" "$C/normal" "$b" "$bin" "$UNIT" > "$R/build-s438.out" 2>&1 < /dev/null
    rc=$?; echo "s438 normal: build rc $rc; errors $(grep -c 'error:' "$R/build-s438.out"); warnings $(grep -c 'warning:' "$R/build-s438.out")"
    grep -n "error:\|undefined\|COMPILE FAILED" "$R/build-s438.out" | head -20
    [ "$rc" = 0 ] && [ -x "$bin" ] || stop "build failed: $R/build-s438.out"
    m "$bin" > "$C/normal/binary.md5"; strings "$bin" > "$C/normal/strings.txt"
    echo "s438 normal: $(cut -c1-8 "$C/normal/binary.md5"); c438 lines $(grep -c 'c438 (exp 0438)' "$C/normal/strings.txt")"
    grep -q 'BC5_0438_MERGESCAN' "$C/normal/strings.txt" || stop "s438 is not in the binary"
    [ "$sn" = "$(m "$W/kytyplus-build/src/kyty_emulator")" ] && [ "$sa" = "$(m "$SA")" ] && [ "$(m "$TREE/$UNIT")" = "$P_UNIT" ] || stop "a shared file changed"
    echo "shared normal ${sn:0:8}, archive ${sa:0:8}, tree unit ${P_UNIT:0:8}: unchanged"
}
builde() {
    own || stop "no lock held by 0438"
    pgrep '^kyty_emulator' > /dev/null && stop "an emulator runs"
    local b bin rc sn sl sa C=$E/e438
    sn=$(m "$W/kytyplus-build/src/kyty_emulator"); sl=$(m "$W/kytyplus-build-lean/src/kyty_emulator"); sa=$(m "$SA")
    [ "${sn:0:8}" = "$P_NORMAL" ] && [ "${sl:0:8}" = "$P_LEAN" ] && [ "${sa:0:8}" = "$P_ARCH" ] || stop "the shared builds are not $P_NORMAL/$P_LEAN/$P_ARCH"
    [ "$(m "$TREE/$UNIT")" = "$P_UNIT" ] || stop "the shared tree's $UNIT is not patch bb04219b's"
    [ "$(m "$HERE/e438.cpp")" = "$K_E438" ] && [ "$(m "$HERE/build0438.py")" = "$K_PY" ] || stop "the e438 kit is not the pinned one"
    mkdir -p "$R" "$C/normal" || stop "mkdir"
    rm -rf "$C/src"; mkdir -p "$C/src/kyty/src/libs" && cp "$HERE/e438.cpp" "$C/src/kyty/$UNIT" || stop "copy"
    b=$W/kytyplus-build; bin=$C/normal/kyty_emulator; rm -rf "$C/normal/obj" "$C/normal/lib"
    [ -f "$bin" ] && mv "$bin" "$bin.$(m "$bin" | cut -c1-8)"
    distrobox enter ubuntu -- sh -c "cd '$b' && ninja -t compdb -x" > "$C/normal/compdb.json" 2> "$R/compdb-e438.err" < /dev/null || stop "compdb failed"
    distrobox enter ubuntu -- env LC_ALL=C LANGUAGE=C python3 -I "$HERE/build0438.py" emu "$C/normal/compdb.json" "$C/src/kyty" "$C/normal" "$b" "$bin" "$UNIT" > "$R/build-e438.out" 2>&1 < /dev/null
    rc=$?; echo "e438 normal: build rc $rc; errors $(grep -c 'error:' "$R/build-e438.out"); warnings $(grep -c 'warning:' "$R/build-e438.out")"
    grep -n "error:\|undefined\|COMPILE FAILED" "$R/build-e438.out" | head -20
    [ "$rc" = 0 ] && [ -x "$bin" ] || stop "build failed: $R/build-e438.out"
    m "$bin" > "$C/normal/binary.md5"; strings "$bin" > "$C/normal/strings.txt"
    echo "e438 normal: $(cut -c1-8 "$C/normal/binary.md5"); c438 lines $(grep -c 'c438 (exp 0438)' "$C/normal/strings.txt")"
    grep -q 'BC5_0438_LAYOUT' "$C/normal/strings.txt" || stop "e438 is not in the binary"
    [ "$sn" = "$(m "$W/kytyplus-build/src/kyty_emulator")" ] && [ "$sa" = "$(m "$SA")" ] && [ "$(m "$TREE/$UNIT")" = "$P_UNIT" ] || stop "a shared file changed"
    echo "shared normal ${sn:0:8}, archive ${sa:0:8}, tree unit ${P_UNIT:0:8}: unchanged"
}
buildf() {
    own || stop "no lock held by 0438"
    pgrep '^kyty_emulator' > /dev/null && stop "an emulator runs"
    local b bin rc sn sl sa C=$E/f438
    sn=$(m "$W/kytyplus-build/src/kyty_emulator"); sl=$(m "$W/kytyplus-build-lean/src/kyty_emulator"); sa=$(m "$SA")
    [ "${sn:0:8}" = "$P_NORMAL" ] && [ "${sl:0:8}" = "$P_LEAN" ] && [ "${sa:0:8}" = "$P_ARCH" ] || stop "the shared builds are not $P_NORMAL/$P_LEAN/$P_ARCH"
    [ "$(m "$TREE/$UNIT")" = "$P_UNIT" ] || stop "the shared tree's $UNIT is not patch bb04219b's"
    [ "$(m "$HERE/f438.cpp")" = "$K_F438" ] && [ "$(m "$HERE/build0438.py")" = "$K_PY" ] || stop "the f438 kit is not the pinned one"
    mkdir -p "$R" "$C/normal" || stop "mkdir"
    rm -rf "$C/src"; mkdir -p "$C/src/kyty/src/libs" && cp "$HERE/f438.cpp" "$C/src/kyty/$UNIT" || stop "copy"
    b=$W/kytyplus-build; bin=$C/normal/kyty_emulator; rm -rf "$C/normal/obj" "$C/normal/lib"
    [ -f "$bin" ] && mv "$bin" "$bin.$(m "$bin" | cut -c1-8)"
    distrobox enter ubuntu -- sh -c "cd '$b' && ninja -t compdb -x" > "$C/normal/compdb.json" 2> "$R/compdb-f438.err" < /dev/null || stop "compdb failed"
    distrobox enter ubuntu -- env LC_ALL=C LANGUAGE=C python3 -I "$HERE/build0438.py" emu "$C/normal/compdb.json" "$C/src/kyty" "$C/normal" "$b" "$bin" "$UNIT" > "$R/build-f438.out" 2>&1 < /dev/null
    rc=$?; echo "f438 normal: build rc $rc; errors $(grep -c 'error:' "$R/build-f438.out"); warnings $(grep -c 'warning:' "$R/build-f438.out")"
    grep -n "error:\|undefined\|COMPILE FAILED" "$R/build-f438.out" | head -20
    [ "$rc" = 0 ] && [ -x "$bin" ] || stop "build failed: $R/build-f438.out"
    m "$bin" > "$C/normal/binary.md5"; strings "$bin" > "$C/normal/strings.txt"
    echo "f438 normal: $(cut -c1-8 "$C/normal/binary.md5"); c438 lines $(grep -c 'c438 (exp 0438)' "$C/normal/strings.txt")"
    grep -q 'BC5_0438_LAYOUT' "$C/normal/strings.txt" || stop "f438 is not in the binary"
    [ "$sn" = "$(m "$W/kytyplus-build/src/kyty_emulator")" ] && [ "$sa" = "$(m "$SA")" ] && [ "$(m "$TREE/$UNIT")" = "$P_UNIT" ] || stop "a shared file changed"
    echo "shared normal ${sn:0:8}, archive ${sa:0:8}, tree unit ${P_UNIT:0:8}: unchanged"
}
buildb() {
    own || stop "no lock held by 0438"
    pgrep '^kyty_emulator' > /dev/null && stop "an emulator runs"
    local b bin rc sn sl sa v C=$E/b438
    sn=$(m "$W/kytyplus-build/src/kyty_emulator"); sl=$(m "$W/kytyplus-build-lean/src/kyty_emulator"); sa=$(m "$SA")
    [ "${sn:0:8}" = "$P_NORMAL" ] && [ "${sl:0:8}" = "$P_LEAN" ] && [ "${sa:0:8}" = "$P_ARCH" ] || stop "the shared builds are not $P_NORMAL/$P_LEAN/$P_ARCH"
    [ "$(m "$TREE/$UNIT")" = "$P_UNIT" ] || stop "the shared tree's $UNIT is not patch bb04219b's"
    [ "$(m "$HERE/b438.cpp")" = "$K_B438" ] && [ "$(m "$HERE/build0438.py")" = "$K_PY" ] && [ "$(m "$HERE/mko438.py")" = "$K_MKO" ] && [ "$(m "$HERE/o438.hpp")" = "$K_O438H" ] || stop "the b438 kit is not the pinned one"
    mkdir -p "$R" || stop "mkdir"
    rm -rf "$C/src"; mkdir -p "$C/src/kyty/src/libs" && cp "$HERE/b438.cpp" "$C/src/kyty/$UNIT" || stop "copy"
    python3 -I "$HERE/mko438.py" "$TREE" "$C/src/kyty" > "$R/mko438.out" 2>&1 || { cat "$R/mko438.out"; stop "mko438.py failed (a tree file is not patch bb04219b's)"; }
    cat "$R/mko438.out"
    for v in normal lean; do
        b=$W/kytyplus-build$([ $v = lean ] && echo -lean); bin=$C/$v/kyty_emulator
        mkdir -p "$C/$v"; rm -rf "$C/$v/obj" "$C/$v/lib"
        [ -f "$bin" ] && mv "$bin" "$bin.$(m "$bin" | cut -c1-8)"
        distrobox enter ubuntu -- sh -c "cd '$b' && ninja -t compdb -x" > "$C/$v/compdb.json" 2> "$R/compdb-b438-$v.err" < /dev/null || stop "compdb $v failed"
        units=$UNIT; [ $v = normal ] && units="$UNIT $O438_UNITS"
        # shellcheck disable=SC2086
        distrobox enter ubuntu -- env LC_ALL=C LANGUAGE=C python3 -I "$HERE/build0438.py" emu "$C/$v/compdb.json" "$C/src/kyty" "$C/$v" "$b" "$bin" $units > "$R/build-b438-$v.out" 2>&1 < /dev/null
        rc=$?; echo "b438 $v: build rc $rc; errors $(grep -c 'error:' "$R/build-b438-$v.out"); warnings $(grep -c 'warning:' "$R/build-b438-$v.out")"
        grep -n "error:\|undefined\|COMPILE FAILED" "$R/build-b438-$v.out" | head -20
        [ "$rc" = 0 ] && [ -x "$bin" ] || stop "build $v failed: $R/build-b438-$v.out"
        m "$bin" > "$C/$v/binary.md5"; strings "$bin" > "$C/$v/strings.txt"
        echo "b438 $v: $(cut -c1-8 "$C/$v/binary.md5"); BC5_0438_EARLYREG $(grep -c BC5_0438_EARLYREG "$C/$v/strings.txt"); BC5_0438_PLWCV $(grep -c BC5_0438_PLWCV "$C/$v/strings.txt"); r438 lines $(grep -c 'r438 (exp 0438, b438)' "$C/$v/strings.txt"); o438 $(grep -c 'BC5_0438_OUTSIDE' "$C/$v/strings.txt")"
        grep -q 'BC5_0438_EARLYREG' "$C/$v/strings.txt" && grep -q 'BC5_0438_PLWCV' "$C/$v/strings.txt" && grep -q 'BC5_0438_PROLMERGE' "$C/$v/strings.txt" || stop "r438's or p438's switches are not in $v"
    done
    grep -q 'r438 (exp 0438, b438): t ' "$C/lean/strings.txt" && stop "lean holds r438's journal lines (BC5_LEAN not applied)"
    grep -q 'BC5_0438_OUTSIDE' "$C/lean/strings.txt" && stop "lean holds o438"
    grep -q 'p438 (exp 0438): t ' "$C/lean/strings.txt" && stop "lean holds p438's journal line"
    grep -q 'BC5_0438_OUTSIDE' "$C/normal/strings.txt" || stop "o438 is not in the normal build"
    grep -q 'b438, lean' "$C/lean/strings.txt" || stop "lean's lost-write counter is not in the lean build"
    [ "$sn" = "$(m "$W/kytyplus-build/src/kyty_emulator")" ] && [ "$sl" = "$(m "$W/kytyplus-build-lean/src/kyty_emulator")" ] && [ "$sa" = "$(m "$SA")" ] && [ "$(m "$TREE/$UNIT")" = "$P_UNIT" ] || stop "a shared file changed"
    echo "shared normal ${sn:0:8}, lean ${sl:0:8}, archive ${sa:0:8}, tree unit ${P_UNIT:0:8}: unchanged"
}
buildk() {
    own || stop "no lock held by 0438"
    pgrep '^kyty_emulator' > /dev/null && stop "an emulator runs"
    local b bin rc sn sl sa v C=$E/bake
    sn=$(m "$W/kytyplus-build/src/kyty_emulator"); sl=$(m "$W/kytyplus-build-lean/src/kyty_emulator"); sa=$(m "$SA")
    [ "${sn:0:8}" = "$P_NORMAL" ] && [ "${sl:0:8}" = "$P_LEAN" ] && [ "${sa:0:8}" = "$P_ARCH" ] || stop "the shared builds are not $P_NORMAL/$P_LEAN/$P_ARCH"
    [ "$(m "$TREE/$UNIT")" = "$P_UNIT" ] || stop "the shared tree's $UNIT is not patch bb04219b's"
    [ "$(m "$HERE/bake438.cpp")" = "$K_BAKE" ] && [ "$(m "$HERE/build0438.py")" = "$K_PY" ] || stop "the bake kit is not the pinned one"
    mkdir -p "$R" || stop "mkdir"
    rm -rf "$C/src"; mkdir -p "$C/src/kyty/src/libs" && cp "$HERE/bake438.cpp" "$C/src/kyty/$UNIT" || stop "copy"
    for v in normal lean; do
        b=$W/kytyplus-build$([ $v = lean ] && echo -lean); bin=$C/$v/kyty_emulator
        mkdir -p "$C/$v"; rm -rf "$C/$v/obj" "$C/$v/lib"
        [ -f "$bin" ] && mv "$bin" "$bin.$(m "$bin" | cut -c1-8)"
        distrobox enter ubuntu -- sh -c "cd '$b' && ninja -t compdb -x" > "$C/$v/compdb.json" 2> "$R/compdb-bake-$v.err" < /dev/null || stop "compdb $v failed"
        distrobox enter ubuntu -- env LC_ALL=C LANGUAGE=C python3 -I "$HERE/build0438.py" emu "$C/$v/compdb.json" "$C/src/kyty" "$C/$v" "$b" "$bin" "$UNIT" > "$R/build-bake-$v.out" 2>&1 < /dev/null
        rc=$?; echo "bake $v: build rc $rc; errors $(grep -c 'error:' "$R/build-bake-$v.out"); warnings $(grep -c 'warning:' "$R/build-bake-$v.out")"
        grep -n "error:\|undefined\|COMPILE FAILED" "$R/build-bake-$v.out" | head -20
        [ "$rc" = 0 ] && [ -x "$bin" ] || stop "build $v failed: $R/build-bake-$v.out"
        m "$bin" > "$C/$v/binary.md5"; strings "$bin" > "$C/$v/strings.txt"
        echo "bake $v: $(cut -c1-8 "$C/$v/binary.md5"); BC5_0438_EARLYREG $(grep -c BC5_0438_EARLYREG "$C/$v/strings.txt"); BC5_0438_PLWCV $(grep -c BC5_0438_PLWCV "$C/$v/strings.txt"); r438 lines $(grep -c 'r438 (exp 0438, b438)' "$C/$v/strings.txt")"
        grep -q 'BC5_0438_EARLYREG' "$C/$v/strings.txt" && grep -q 'BC5_0438_PLWCV' "$C/$v/strings.txt" || stop "r438's switches are not in $v"
        grep -q 'BC5_0438_PROLMERGE\|p438 (exp 0438)\|BC5_0438_OUTSIDE\|b438, lean' "$C/$v/strings.txt" && stop "$v holds p438, o438 or lean's counter"
    done
    grep -q 'r438 (exp 0438, b438): t ' "$C/normal/strings.txt" || stop "normal lacks r438's count line"
    grep -q 'r438 (exp 0438, b438)' "$C/lean/strings.txt" && stop "lean holds r438's journal lines (BC5_LEAN not applied)"
    [ "$sn" = "$(m "$W/kytyplus-build/src/kyty_emulator")" ] && [ "$sl" = "$(m "$W/kytyplus-build-lean/src/kyty_emulator")" ] && [ "$sa" = "$(m "$SA")" ] && [ "$(m "$TREE/$UNIT")" = "$P_UNIT" ] || stop "a shared file changed"
    echo "shared normal ${sn:0:8}, lean ${sl:0:8}, archive ${sa:0:8}, tree unit ${P_UNIT:0:8}: unchanged"
}
buildw() {
    own || stop "no lock held by 0438"
    pgrep '^kyty_emulator' > /dev/null && stop "an emulator runs"
    local b bin rc sn sl sa C=$E/w438
    sn=$(m "$W/kytyplus-build/src/kyty_emulator"); sl=$(m "$W/kytyplus-build-lean/src/kyty_emulator"); sa=$(m "$SA")
    [ "${sn:0:8}" = "$P_NORMAL" ] && [ "${sl:0:8}" = "$P_LEAN" ] && [ "${sa:0:8}" = "$P_ARCH" ] || stop "the shared builds are not $P_NORMAL/$P_LEAN/$P_ARCH"
    [ "$(m "$TREE/$UNIT")" = "$P_UNIT" ] || stop "the shared tree's $UNIT is not patch bb04219b's"
    [ "$(m "$HERE/w438.cpp")" = "$K_W438" ] && [ "$(m "$HERE/build0438.py")" = "$K_PY" ] || stop "the w438 kit is not the pinned one"
    mkdir -p "$R" "$C/normal" || stop "mkdir"
    rm -rf "$C/src"; mkdir -p "$C/src/kyty/src/libs" && cp "$HERE/w438.cpp" "$C/src/kyty/$UNIT" || stop "copy"
    b=$W/kytyplus-build; bin=$C/normal/kyty_emulator; rm -rf "$C/normal/obj" "$C/normal/lib"
    [ -f "$bin" ] && mv "$bin" "$bin.$(m "$bin" | cut -c1-8)"
    distrobox enter ubuntu -- sh -c "cd '$b' && ninja -t compdb -x" > "$C/normal/compdb.json" 2> "$R/compdb-w438.err" < /dev/null || stop "compdb failed"
    distrobox enter ubuntu -- env LC_ALL=C LANGUAGE=C python3 -I "$HERE/build0438.py" emu "$C/normal/compdb.json" "$C/src/kyty" "$C/normal" "$b" "$bin" "$UNIT" > "$R/build-w438.out" 2>&1 < /dev/null
    rc=$?; echo "w438 normal: build rc $rc; errors $(grep -c 'error:' "$R/build-w438.out"); warnings $(grep -c 'warning:' "$R/build-w438.out")"
    grep -n "error:\|undefined\|COMPILE FAILED" "$R/build-w438.out" | head -20
    [ "$rc" = 0 ] && [ -x "$bin" ] || stop "build failed: $R/build-w438.out"
    m "$bin" > "$C/normal/binary.md5"; strings "$bin" > "$C/normal/strings.txt"
    echo "w438 normal: $(cut -c1-8 "$C/normal/binary.md5"); c438 lines $(grep -c 'c438 (exp 0438)' "$C/normal/strings.txt")"
    grep -q 'BC5_0438_WATCHER' "$C/normal/strings.txt" || stop "w438 is not in the binary"
    [ "$sn" = "$(m "$W/kytyplus-build/src/kyty_emulator")" ] && [ "$sa" = "$(m "$SA")" ] && [ "$(m "$TREE/$UNIT")" = "$P_UNIT" ] || stop "a shared file changed"
    echo "shared normal ${sn:0:8}, archive ${sa:0:8}, tree unit ${P_UNIT:0:8}: unchanged"
}
buildr() {
    own || stop "no lock held by 0438"
    pgrep '^kyty_emulator' > /dev/null && stop "an emulator runs"
    local b bin rc sn sl sa C=$E/r438
    sn=$(m "$W/kytyplus-build/src/kyty_emulator"); sl=$(m "$W/kytyplus-build-lean/src/kyty_emulator"); sa=$(m "$SA")
    [ "${sn:0:8}" = "$P_NORMAL" ] && [ "${sl:0:8}" = "$P_LEAN" ] && [ "${sa:0:8}" = "$P_ARCH" ] || stop "the shared builds are not $P_NORMAL/$P_LEAN/$P_ARCH"
    [ "$(m "$TREE/$UNIT")" = "$P_UNIT" ] || stop "the shared tree's $UNIT is not patch bb04219b's"
    [ "$(m "$HERE/r438.cpp")" = "$K_R438" ] && [ "$(m "$HERE/build0438.py")" = "$K_PY" ] || stop "the r438 kit is not the pinned one"
    mkdir -p "$R" "$C/normal" || stop "mkdir"
    rm -rf "$C/src"; mkdir -p "$C/src/kyty/src/libs" && cp "$HERE/r438.cpp" "$C/src/kyty/$UNIT" || stop "copy"
    b=$W/kytyplus-build; bin=$C/normal/kyty_emulator; rm -rf "$C/normal/obj" "$C/normal/lib"
    [ -f "$bin" ] && mv "$bin" "$bin.$(m "$bin" | cut -c1-8)"
    distrobox enter ubuntu -- sh -c "cd '$b' && ninja -t compdb -x" > "$C/normal/compdb.json" 2> "$R/compdb-r438.err" < /dev/null || stop "compdb failed"
    distrobox enter ubuntu -- env LC_ALL=C LANGUAGE=C python3 -I "$HERE/build0438.py" emu "$C/normal/compdb.json" "$C/src/kyty" "$C/normal" "$b" "$bin" "$UNIT" > "$R/build-r438.out" 2>&1 < /dev/null
    rc=$?; echo "r438 normal: build rc $rc; errors $(grep -c 'error:' "$R/build-r438.out"); warnings $(grep -c 'warning:' "$R/build-r438.out")"
    grep -n "error:\|undefined\|COMPILE FAILED" "$R/build-r438.out" | head -20
    [ "$rc" = 0 ] && [ -x "$bin" ] || stop "build failed: $R/build-r438.out"
    m "$bin" > "$C/normal/binary.md5"; strings "$bin" > "$C/normal/strings.txt"
    echo "r438 normal: $(cut -c1-8 "$C/normal/binary.md5"); c438 lines $(grep -c 'c438 (exp 0438)' "$C/normal/strings.txt"); BC5_0438_EARLYREG $(grep -c BC5_0438_EARLYREG "$C/normal/strings.txt")"
    grep -q 'BC5_0438_EARLYREG' "$C/normal/strings.txt" || stop "r438 is not in the binary"
    [ "$sn" = "$(m "$W/kytyplus-build/src/kyty_emulator")" ] && [ "$sa" = "$(m "$SA")" ] && [ "$(m "$TREE/$UNIT")" = "$P_UNIT" ] || stop "a shared file changed"
    echo "shared normal ${sn:0:8}, archive ${sa:0:8}, tree unit ${P_UNIT:0:8}: unchanged"
}
case "${1:-}" in
    claim) claim "${2:-F865 records read}" "${3:-20}" ;;
    release) release ;;
    pack) pack ;;
    build) build ;;
    buildcat) buildcat ;;
    buildd) buildd ;;
    buildw) buildw ;;
    buildu) buildu ;;
    builds) builds ;;
    builde) builde ;;
    buildf) buildf ;;
    buildb) buildb ;;
    buildk) buildk ;;
    buildr) buildr ;;
    *) echo "usage: $0 claim|release|pack|build|buildcat|buildr|buildd|buildw|buildu|builds|builde|buildf|buildb|buildk"; exit 2 ;;
esac
