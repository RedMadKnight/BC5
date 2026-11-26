#!/usr/bin/env bash
# BC5 exp 0415, build L5a (tag fs415b) on the SHARED tree as it is since the integration of 2026-11-13 (patch 0001
# 4651d1d3, which holds this experiment's L4): a fresh private copy of ~/src/KytyPlus as tree5, plus kit/0415-l5a.diff
# (KYTY_BC5_FRAME_STAT records every job of a window of frames, with the host's stamps around the device mutex, also
# jobs the submitter completed itself; KYTY_BC5_FRAME_STAT_WIN). Default off, no change of behaviour. A full build of
# the normal and the lean variant under ~/bc5-work/exp0415/build5-*; the L4 binaries are kept as bin-l4/, bin-lean-l4/.
# ~/src/KytyPlus, the shared build directories, the backend source and its archive are only read. No emulator is started.
# usage (on the box): P_TREE=<8 hex> P_ARCH=<8 hex> P_DIFF=<sha256, 16 hex> bash mk0415h.sh
set -u
ulimit -c 0
export LC_ALL=C LANGUAGE=C
W=$HOME/bc5-work; E=$W/exp0415; HERE=$(cd "$(dirname "$0")" && pwd); K=$HOME/src/KytyPlus
LOCK=$W/BOX-LOCK; ID=$E/lock.line; ARCH=$W/backend-ubuntu/libbc5_backend.a; BSRC=$W/d19/export/backend; BBLD=$W/backend-ubuntu
: "${P_TREE:?the pin of the shared tree: git -C ~/src/KytyPlus diff --no-color f266548 | md5sum | cut -c1-8}"
: "${P_ARCH:?the pin of the backend archive: md5sum, 8 hex}"
m() { md5sum < "$1" | cut -c1-8; }
stop() { echo "mk0415h STOP: $*"; exit 1; }
own() { [ -s "$ID" ] && [ "$(cat "$LOCK" 2> /dev/null)" = "$(cat "$ID")" ]; }
claim() {
    local c=$LOCK.d19-claim t=$LOCK.0415-$$.new a=$LOCK.0415-$$.aside line
    pgrep '^kyty_emulator' > /dev/null && stop "an emulator runs"
    mkdir -p "$E" || stop "cannot make $E"
    line="exp 0415 | token $(date +%s)$$ | $1, no emulator, until $(date -d +"$2"min +%H:%M) | $(date '+%F %T')"
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
    if own; then : > "$LOCK" && [ ! -s "$LOCK" ] && { rm -f "$ID"; echo "lock released"; return 0; }; echo "mk0415: the lock could not be released"; return 1; fi
    echo "mk0415: the lock is not ours, left as it is: $(cat "$LOCK" 2> /dev/null)"; return 1
}
die() { echo "mk0415h STOP: $*"; release; exit 1; }
pgrep '^kyty_emulator' > /dev/null && stop "an emulator runs"
[ "$(git -C "$K" diff --no-color f266548 | md5sum | cut -c1-8)" = "$P_TREE" ] || stop "the shared tree's diff is not $P_TREE"
[ "$(sha256sum < "$HERE/0415-l5a.diff" | cut -c1-16)" = "${P_DIFF:?the diff sha256, 16 hex}" ] || stop "the diff is not the one sent"
for f in tree-l5a.md5 test0415.cpp test0415apr.cpp test0415sync.cpp test0415rec.cpp; do [ -s "$HERE/$f" ] || stop "no $f in the kit"; done
[ "$(m "$ARCH")" = "$P_ARCH" ] || stop "the archive is not $P_ARCH"
[ -d "$BSRC/include/bc5" ] || stop "no backend include dir at $BSRC"
[ ! -e "$E/tree5" ] && [ ! -e "$E/bin-l4" ] || stop "$E/tree5 or bin-l4 exists: L5a was built already"
[ -x "$E/bin/kyty_emulator" ] && [ -x "$E/bin-lean/kyty_emulator" ] || stop "no L4 binaries in place"
claim "exp 0415: private build L5a under exp0415 (tree5, normal and lean builds), CPU only" 45
mkdir -p "$E/tree5" "$E/raw/test-l5a" || die "mkdir"
echo "$(date '+%F %T') start; tree pin $P_TREE, archive $(m "$ARCH"), kit diff $(m "$HERE/0415-l5a.diff")"
ls "$W"/kytyplus-build/externals/ffmpeg-*.zip > /dev/null 2>&1 || die "no ffmpeg prebuilt in the shared build"
tar -C "$K" -cf - . | tar -C "$E/tree5" -xf - || die "the tree copy"  # with .git: ffmpeg-core's CMake asks git for its commit
cmp -s "$K/src/libs/bc5LleAgc.cpp" "$E/tree5/src/libs/bc5LleAgc.cpp" || die "the copy differs from the shared tree"
(cd "$E/tree5" && git -c core.autocrlf=false apply --whitespace=nowarn "$HERE/0415-l5a.diff") || die "the diff does not apply"
bad=0
while read -r sum f; do [ "$(md5sum < "$E/tree5/$f" | cut -d' ' -f1)" = "$sum" ] || { echo "differs: $f"; bad=$((bad + 1)); }; done < "$HERE/tree-l5a.md5"
[ "$bad" = 0 ] || die "$bad edited files differ from the laptop's tree"
echo "tree: $(wc -l < "$HERE/tree-l5a.md5") edited files match the laptop's"
pgrep '^kyty_emulator' > /dev/null && die "an emulator started; stopped before the test"
distrobox enter ubuntu -- env LC_ALL=C g++ -std=c++20 -O1 -Wall -Wextra -Werror -pthread -I "$E/tree5/src" "$HERE/test0415.cpp" -o "$E/raw/test-l5a/test0415" < /dev/null > "$E/raw/test-l5a/test0415-build.out" 2>&1 ||
    die "the CPU test does not build: $(grep -m2 'error' "$E/raw/test-l5a/test0415-build.out" | cut -c1-160 | tr '\n' ' ')"
distrobox enter ubuntu -- "$E/raw/test-l5a/test0415" off < /dev/null > "$E/raw/test-l5a/test0415-off.out" 2>&1 || die "the CPU test (off) failed: $(grep -m2 FAIL "$E/raw/test-l5a/test0415-off.out" | cut -c1-160 | tr '\n' ' ')"
distrobox enter ubuntu -- "$E/raw/test-l5a/test0415" on "$E/raw/test-l5a/test0415-stat.txt" < /dev/null > "$E/raw/test-l5a/test0415-on.out" 2>&1 || die "the CPU test (on) failed: $(grep -m2 FAIL "$E/raw/test-l5a/test0415-on.out" | cut -c1-160 | tr '\n' ' ')"
grep -q '^test0415: \([0-9]*\) of \1; end$' "$E/raw/test-l5a/test0415-off.out" && grep -q '^test0415: \([0-9]*\) of \1; end$' "$E/raw/test-l5a/test0415-on.out" || die "no end marker from the CPU test"
distrobox enter ubuntu -- env LC_ALL=C g++ -std=c++20 -O1 -Wall -Wextra -Werror -I "$E/tree5/src" "$HERE/test0415apr.cpp" -o "$E/raw/test-l5a/test0415apr" < /dev/null > "$E/raw/test-l5a/test0415apr-build.out" 2>&1 ||
    die "test0415apr does not build: $(grep -m2 'error' "$E/raw/test-l5a/test0415apr-build.out" | cut -c1-200 | tr '\n' ' ')"
distrobox enter ubuntu -- "$E/raw/test-l5a/test0415apr" "$E/raw/test-l5a" < /dev/null > "$E/raw/test-l5a/apr.out" 2>&1 || die "test0415apr failed: $(grep -m3 FAIL "$E/raw/test-l5a/apr.out" | cut -c1-160 | tr '\n' ' ')"
grep -q '^test0415apr: \([0-9]*\) of \1; end$' "$E/raw/test-l5a/apr.out" || die "no end marker from test0415apr"
distrobox enter ubuntu -- env LC_ALL=C g++ -std=c++20 -O1 -Wall -Wextra -Werror -I "$E/tree5/src" "$HERE/test0415sync.cpp" -o "$E/raw/test-l5a/test0415sync" < /dev/null > "$E/raw/test-l5a/test0415sync-build.out" 2>&1 ||
    die "test0415sync does not build: $(grep -m2 'error' "$E/raw/test-l5a/test0415sync-build.out" | cut -c1-200 | tr '\n' ' ')"
distrobox enter ubuntu -- "$E/raw/test-l5a/test0415sync" < /dev/null > "$E/raw/test-l5a/sync.out" 2>&1 || die "test0415sync failed: $(grep -m3 FAIL "$E/raw/test-l5a/sync.out" | cut -c1-160 | tr '\n' ' ')"
grep -q '^test0415sync: \([0-9]*\) of \1; end$' "$E/raw/test-l5a/sync.out" || die "no end marker from test0415sync"
distrobox enter ubuntu -- env LC_ALL=C g++ -std=c++20 -O1 -Wall -Wextra -Werror -I "$E/tree5/src" "$HERE/test0415rec.cpp" -o "$E/raw/test-l5a/test0415rec" < /dev/null > "$E/raw/test-l5a/test0415rec-build.out" 2>&1 ||
    die "test0415rec does not build: $(grep -m2 'error' "$E/raw/test-l5a/test0415rec-build.out" | cut -c1-200 | tr '\n' ' ')"
distrobox enter ubuntu -- "$E/raw/test-l5a/test0415rec" < /dev/null > "$E/raw/test-l5a/rec.out" 2>&1 || die "test0415rec failed: $(grep -m3 FAIL "$E/raw/test-l5a/rec.out" | cut -c1-160 | tr '\n' ' ')"
grep -q '^test0415rec: \([0-9]*\) of \1; end$' "$E/raw/test-l5a/rec.out" || die "no end marker from test0415rec"
echo "cpu tests: $(tail -1 "$E/raw/test-l5a/test0415-off.out") | $(tail -1 "$E/raw/test-l5a/test0415-on.out") | $(tail -1 "$E/raw/test-l5a/apr.out") | $(tail -1 "$E/raw/test-l5a/sync.out") | $(tail -1 "$E/raw/test-l5a/rec.out")"
for v in normal lean; do
    pgrep '^kyty_emulator' > /dev/null && die "an emulator started; stopped before $v"
    d=$E/build5-$v; x=""; o=new5/normal; [ $v = lean ] && { x="-DKYTY_BC5_LEAN=ON"; o=new5/lean; }
    mkdir -p "$d/externals" && cp -p "$W"/kytyplus-build/externals/ffmpeg-*.zip "$d/externals/" || die "the ffmpeg prebuilt copy"  # no download
    distrobox enter ubuntu -- cmake -S "$E/tree5" -B "$d" -U "*PIPEWIRE*" -G Ninja -DCMAKE_BUILD_TYPE=Release \
        -DCMAKE_C_COMPILER=clang -DCMAKE_CXX_COMPILER=clang++ -DKYTY_BUILD_LAUNCHER=OFF \
        -DKYTY_BC5_BACKEND_SRC="$BSRC" -DKYTY_BC5_BACKEND_BUILD="$BBLD" $x < /dev/null > "$d.configure.log" 2>&1 || die "configure $v: $(tail -3 "$d.configure.log" | tr '\n' ' ')"
    echo "== $(date +%T) build $v"
    distrobox enter ubuntu -- sh -c "cd '$d' && nice -n 19 ninja kyty_emulator" < /dev/null > "$d.build.log" 2>&1 || { grep -m5 -E "error:" "$d.build.log"; die "the build ($v)"; }
    b=$d/src/kyty_emulator
    [ -x "$b" ] || die "no binary ($v)"
    for s in KYTY_BC5_FRAME_STAT_WIN KYTY_BC5_FRAME_STAT KYTY_BC5_APR_POSIX KYTY_BC5_MAP_RECORDS KYTY_BC5_LOAD_STAT KYTY_BC5_SWITCH_DEFAULTS "tag ls415b" bc5-mapschk; do
        grep -aqF -- "$s" "$b" || die "the $v binary lacks [$s]"
    done
    mkdir -p "$E/$o" && cp -p "$b" "$E/$o/kyty_emulator" || die "cannot place the $v binary"
    echo "$v: $(m "$E/$o/kyty_emulator"), warnings $(sed 's/\x1b\[[0-9;]*m//g' "$d.build.log" | grep -c 'warning:')"
done
[ "$(m "$ARCH")" = "$P_ARCH" ] || die "the archive changed"
mv -T "$E/bin" "$E/bin-l4" && mv -T "$E/bin-lean" "$E/bin-lean-l4" && mkdir "$E/bin" "$E/bin-lean" &&
    mv -T "$E/new5/normal/kyty_emulator" "$E/bin/kyty_emulator" && mv -T "$E/new5/lean/kyty_emulator" "$E/bin-lean/kyty_emulator" || die "placing the binaries"
{ printf '%s  bin/kyty_emulator\n' "$(md5sum < "$E/bin/kyty_emulator" | cut -d' ' -f1)"; printf '%s  bin-lean/kyty_emulator\n' "$(md5sum < "$E/bin-lean/kyty_emulator" | cut -d' ' -f1)"; } > "$E/built.md5"
echo "$(date '+%F %T') done; L5a normal $(m "$E/bin/kyty_emulator"), lean $(m "$E/bin-lean/kyty_emulator"); L4 kept in bin-l4, bin-lean-l4"
release
