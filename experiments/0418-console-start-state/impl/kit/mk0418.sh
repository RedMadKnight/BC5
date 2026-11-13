#!/usr/bin/env bash
# BC5 exp 0418, the private build of the start-state table and the /dev/gc caller trace (impl/README.md), on the SHARED
# tree as it is (patch 0001 4651d1d3 since the integration of 2026-11-13, or candidate B 27b6416f after the swap; the kit
# has a diff and a sum list for each): a fresh private copy of ~/src/KytyPlus as
# ~/bc5-work/exp0418/tree, plus kit/0418-on-<P_TREE>.diff. Every change is behind a switch that is off by default
# (BC5_DIRECT_START_STATE, BC5_DIRECT_START_STATE_SKIP, BC5_DIRECT_GC_GS_RINGS, BC5_GC_IOCTL_TRACE; the four older
# switches keep their meaning). A full build of the normal and the lean variant under ~/bc5-work/exp0418/build-*.
# ~/src/KytyPlus, the shared build directories, the backend source and its archive are only read. No emulator is started.
# Only ~/bc5-work/exp0418 is written, and the lock line while it runs.
# usage (on the box): P_TREE=<4651d1d3|27b6416f> P_ARCH=<8 hex> P_DIFF=<sha256 of kit/0418-on-$P_TREE.diff, 16 hex> bash mk0418.sh
set -u
ulimit -c 0
export LC_ALL=C LANGUAGE=C
W=$HOME/bc5-work; E=$W/exp0418; HERE=$(cd "$(dirname "$0")" && pwd); K=$HOME/src/KytyPlus
LOCK=$W/BOX-LOCK; ID=$E/lock.line; ARCH=$W/backend-ubuntu/libbc5_backend.a; BSRC=$W/d19/export/backend; BBLD=$W/backend-ubuntu
: "${P_TREE:?the pin of the shared tree: git -C ~/src/KytyPlus diff --no-color f266548 | md5sum | cut -c1-8}"
: "${P_ARCH:?the pin of the backend archive: md5sum, 8 hex}"
m() { md5sum < "$1" | cut -c1-8; }
stop() { echo "mk0418 STOP: $*"; exit 1; }
own() { [ -s "$ID" ] && [ "$(cat "$LOCK" 2> /dev/null)" = "$(cat "$ID")" ]; }
claim() {
    local c=$LOCK.d19-claim t=$LOCK.0418-$$.new a=$LOCK.0418-$$.aside line
    pgrep '^kyty_emulator' > /dev/null && stop "an emulator runs"
    mkdir -p "$E" || stop "cannot make $E"
    line="exp 0418 | token $(date +%s)$$ | $1, no emulator, until $(date -d +"$2"min +%H:%M) | $(date '+%F %T')"
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
    if own; then : > "$LOCK" && [ ! -s "$LOCK" ] && { rm -f "$ID"; echo "lock released"; return 0; }; echo "mk0418: the lock could not be released"; return 1; fi
    echo "mk0418: the lock is not ours, left as it is: $(cat "$LOCK" 2> /dev/null)"; return 1
}
die() { echo "mk0418 STOP: $*"; release; exit 1; }
pgrep '^kyty_emulator' > /dev/null && stop "an emulator runs"
case "$P_TREE" in 4651d1d3 | 27b6416f) ;; *) stop "the kit has no diff for a shared tree $P_TREE" ;; esac
DIFF=$HERE/0418-on-$P_TREE.diff; SUMS=$HERE/tree-0418-on-$P_TREE.md5
[ "$(git -C "$K" diff --no-color f266548 | md5sum | cut -c1-8)" = "$P_TREE" ] || stop "the shared tree's diff is not $P_TREE"
[ "$(sha256sum < "$DIFF" | cut -c1-16)" = "${P_DIFF:?the diff sha256, 16 hex}" ] || stop "the diff is not the one sent"
for f in "$SUMS" "$HERE/test418.cpp"; do [ -s "$f" ] || stop "no $f in the kit"; done
[ "$(m "$ARCH")" = "$P_ARCH" ] || stop "the archive is not $P_ARCH"
[ -d "$BSRC/include/bc5" ] || stop "no backend include dir at $BSRC"
[ ! -e "$E/tree" ] && [ ! -e "$E/bin" ] || stop "$E/tree or $E/bin exists: built already"
claim "exp 0418: private build under exp0418 (tree, normal and lean builds), CPU only" 45
mkdir -p "$E/tree" "$E/raw/test" || die "mkdir"
echo "$(date '+%F %T') start; tree pin $P_TREE, archive $(m "$ARCH"), kit diff $(m "$DIFF") (on $P_TREE)"
ls "$W"/kytyplus-build/externals/ffmpeg-*.zip > /dev/null 2>&1 || die "no ffmpeg prebuilt in the shared build"
tar -C "$K" -cf - . | tar -C "$E/tree" -xf - || die "the tree copy"  # with .git: ffmpeg-core's CMake asks git for its commit
cmp -s "$K/src/libs/bc5LleAgc.cpp" "$E/tree/src/libs/bc5LleAgc.cpp" || die "the copy differs from the shared tree"
(cd "$E/tree" && git -c core.autocrlf=false apply --whitespace=nowarn "$DIFF") || die "the diff does not apply"
bad=0
while read -r sum f; do [ "$(md5sum < "$E/tree/$f" | cut -d' ' -f1)" = "$sum" ] || { echo "differs: $f"; bad=$((bad + 1)); }; done < "$SUMS"
[ "$bad" = 0 ] || die "$bad edited files differ from the laptop's tree"
echo "tree: $(wc -l < "$SUMS") edited files match the laptop's (on $P_TREE)"
T=$E/raw/test
distrobox enter ubuntu -- env LC_ALL=C g++ -std=c++20 -O1 -Wall -Wextra -Werror -I "$E/tree/src" "$HERE/test418.cpp" -o "$T/test418" < /dev/null > "$T/test418-build.out" 2>&1 ||
    die "test418 does not build: $(grep -m2 'error' "$T/test418-build.out" | cut -c1-200 | tr '\n' ' ')"
distrobox enter ubuntu -- "$T/test418" < /dev/null > "$T/test418.out" 2>&1 || die "test418 failed: $(grep -m3 FAIL "$T/test418.out" | cut -c1-160 | tr '\n' ' ')"
grep -q '^test418: \([0-9]*\) of \1; end$' "$T/test418.out" || die "no end marker from test418"
echo "cpu test: $(tail -1 "$T/test418.out")"
for v in normal lean; do
    pgrep '^kyty_emulator' > /dev/null && die "an emulator started; stopped before $v"
    d=$E/build-$v; x=""; o=new/normal; [ $v = lean ] && { x="-DKYTY_BC5_LEAN=ON"; o=new/lean; }
    mkdir -p "$d/externals" && cp -p "$W"/kytyplus-build/externals/ffmpeg-*.zip "$d/externals/" || die "the ffmpeg prebuilt copy"  # no download
    distrobox enter ubuntu -- cmake -S "$E/tree" -B "$d" -U "*PIPEWIRE*" -G Ninja -DCMAKE_BUILD_TYPE=Release \
        -DCMAKE_C_COMPILER=clang -DCMAKE_CXX_COMPILER=clang++ -DKYTY_BUILD_LAUNCHER=OFF \
        -DKYTY_BC5_BACKEND_SRC="$BSRC" -DKYTY_BC5_BACKEND_BUILD="$BBLD" $x < /dev/null > "$d.configure.log" 2>&1 || die "configure $v: $(tail -3 "$d.configure.log" | tr '\n' ' ')"
    echo "== $(date +%T) build $v"
    distrobox enter ubuntu -- sh -c "cd '$d' && nice -n 19 ninja kyty_emulator" < /dev/null > "$d.build.log" 2>&1 || { grep -m5 -E "error:" "$d.build.log"; die "the build ($v)"; }
    b=$d/src/kyty_emulator
    [ -x "$b" ] || die "no binary ($v)"
    for s in BC5_DIRECT_START_STATE BC5_DIRECT_START_STATE_SKIP BC5_DIRECT_GC_GS_RINGS "start state (exp 0418)" "GS ring sizes" \
             BC5_DIRECT_GC_TF_RING BC5_DIRECT_GC_HS_OFFCHIP BC5_DIRECT_CP_COHER_START_DELAY BC5_DIRECT_SPI_REQ_CTRL_PS KYTY_BC5_SWITCH_DEFAULTS; do
        grep -aqF -- "$s" "$b" || die "the $v binary lacks [$s]"
    done
    if [ $v = normal ]; then
        grep -aqF -- "BC5_GC_IOCTL_TRACE" "$b" && grep -aqF -- "[bc5-gc-trace]" "$b" || die "the normal binary lacks the trace"
    else
        grep -aqF -- "[bc5-gc-trace]" "$b" && die "the lean binary has the trace (it must be compiled out)"
    fi
    mkdir -p "$E/$o" && cp -p "$b" "$E/$o/kyty_emulator" || die "cannot place the $v binary"
    echo "$v: $(m "$E/$o/kyty_emulator"), warnings $(sed 's/\x1b\[[0-9;]*m//g' "$d.build.log" | grep -c 'warning:')"
done
[ "$(m "$ARCH")" = "$P_ARCH" ] || die "the archive changed"
mkdir "$E/bin" "$E/bin-lean" && mv -T "$E/new/normal/kyty_emulator" "$E/bin/kyty_emulator" && mv -T "$E/new/lean/kyty_emulator" "$E/bin-lean/kyty_emulator" || die "placing the binaries"
{ printf '%s  bin/kyty_emulator\n' "$(md5sum < "$E/bin/kyty_emulator" | cut -d' ' -f1)"; printf '%s  bin-lean/kyty_emulator\n' "$(md5sum < "$E/bin-lean/kyty_emulator" | cut -d' ' -f1)"; } > "$E/built.md5"
echo "$(date '+%F %T') done; normal $(m "$E/bin/kyty_emulator"), lean $(m "$E/bin-lean/kyty_emulator")"
release
