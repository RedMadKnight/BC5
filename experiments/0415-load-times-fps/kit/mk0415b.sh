#!/usr/bin/env bash
# BC5 exp 0415, the private build L1 (tag ls415): the shared host tree as it is after exp 0413's swap, plus kit/0415-l1.diff
# (the load counters, three measurement knobs, three candidate fixes; every word default off). Built under
# ~/bc5-work/exp0415 only: ~/src/KytyPlus, the shared build directories, the backend source and its archive are only read.
# After exp 0413's p0413g.sh (its claim, its cmake options); the normal and the lean build.
#   1. checks: no emulator; the shared tree's diff against f266548 is the pin given as P_TREE (the top session names it
#      after the swap); the kit's sha256; the archive's md5 as P_ARCH
#   2. the lock (atomic hard-link claim; only our exact line is ever removed)
#   3. the tree copied without .git, the diff applied (git apply, no CR conversion), the CPU test built and run
#   4. configure and build, nice 19; the binary must hold every new word; the archive must be unchanged
# No emulator is started. usage (on the box): P_TREE=<8 hex> P_ARCH=<8 hex> bash mk0415.sh
set -u
ulimit -c 0
export LC_ALL=C LANGUAGE=C
W=$HOME/bc5-work; E=$W/exp0415; HERE=$(cd "$(dirname "$0")" && pwd); K=$HOME/src/KytyPlus
LOCK=$W/BOX-LOCK; ID=$E/lock.line; ARCH=$W/backend-ubuntu/libbc5_backend.a; BSRC=$W/d19/export/backend; BBLD=$W/backend-ubuntu
: "${P_TREE:?the pin of the shared tree: git -C ~/src/KytyPlus diff --no-color f266548 | md5sum | cut -c1-8}"
: "${P_ARCH:?the pin of the backend archive: md5sum, 8 hex}"
m() { md5sum < "$1" | cut -c1-8; }
stop() { echo "mk0415 STOP: $*"; exit 1; }
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
die() { echo "mk0415 STOP: $*"; release; exit 1; }
pgrep '^kyty_emulator' > /dev/null && stop "an emulator runs"
[ "$(git -C "$K" diff --no-color f266548 | md5sum | cut -c1-8)" = "$P_TREE" ] || stop "the shared tree's diff is not $P_TREE"
(cd "$HERE" && sha256sum -c --quiet kit.sha256) || stop "the kit is not what was sent"
[ "$(m "$ARCH")" = "$P_ARCH" ] || stop "the archive is not $P_ARCH"
[ -d "$BSRC/include/bc5" ] || stop "no backend include dir at $BSRC"
[ ! -e "$E/bin" ] && [ ! -e "$E/bin-lean" ] || stop "$E/bin exists: a build was made; this script does not build over it"
# mk0415b (2026-11-12 19:3x): mk0415.sh's configure stopped: ffmpeg-core's CMake asks git for its commit and wants its
# prebuilt archive. As exp 0413's p0413.sh: the tree is copied WITH .git and the shared build's prebuilt is copied into
# each build directory. The first attempt's tree and build directory (ours, no binary in them) are removed first.
claim "exp 0415: private build L1 under exp0415 (tree copy, normal and lean builds), CPU only" 60
mkdir -p "$E/tree" "$E/raw" || die "mkdir"
echo "$(date '+%F %T') start; tree pin $P_TREE, archive $(m "$ARCH"), kit diff $(m "$HERE/0415-l1.diff")"
rm -rf "$HOME/bc5-work/exp0415/tree" "$HOME/bc5-work/exp0415/build-normal" "$HOME/bc5-work/exp0415/build-lean" && mkdir -p "$E/tree" || die "cannot clear the first attempt"
ls "$W"/kytyplus-build/externals/ffmpeg-*.zip > /dev/null 2>&1 || die "no ffmpeg prebuilt in the shared build"
tar -C "$K" -cf - . | tar -C "$E/tree" -xf - || die "the tree copy"  # with .git: ffmpeg-core's CMake asks git for its commit
cmp -s "$K/src/libs/bc5LleAgc.cpp" "$E/tree/src/libs/bc5LleAgc.cpp" || die "the copy differs from the shared tree"
(cd "$E/tree" && git -c core.autocrlf=false apply --whitespace=nowarn "$HERE/0415-l1.diff") || die "the diff does not apply"
bad=0
while read -r sum f; do [ "$(md5sum < "$E/tree/$f" | cut -d' ' -f1)" = "$sum" ] || { echo "differs: $f"; bad=$((bad + 1)); }; done < "$HERE/tree-l1.md5"
[ "$bad" = 0 ] || die "$bad edited files differ from the laptop's tree"
echo "tree: $(wc -l < "$HERE/tree-l1.md5") edited files match the laptop's"
pgrep '^kyty_emulator' > /dev/null && die "an emulator started; stopped before the test"
distrobox enter ubuntu -- env LC_ALL=C g++ -std=c++20 -O1 -Wall -Wextra -Werror -pthread -I "$E/tree/src" "$HERE/test0415.cpp" -o "$E/raw/test0415" < /dev/null > "$E/raw/test0415-build.out" 2>&1 ||
    die "the CPU test does not build: $(grep -m2 'error' "$E/raw/test0415-build.out" | cut -c1-160 | tr '\n' ' ')"
distrobox enter ubuntu -- "$E/raw/test0415" off < /dev/null > "$E/raw/test0415-off.out" 2>&1 || die "the CPU test (off) failed: $(grep -m2 FAIL "$E/raw/test0415-off.out" | cut -c1-160 | tr '\n' ' ')"
distrobox enter ubuntu -- "$E/raw/test0415" on "$E/raw/test0415-stat.txt" < /dev/null > "$E/raw/test0415-on.out" 2>&1 || die "the CPU test (on) failed: $(grep -m2 FAIL "$E/raw/test0415-on.out" | cut -c1-160 | tr '\n' ' ')"
grep -q '^test0415: \([0-9]*\) of \1; end$' "$E/raw/test0415-off.out" && grep -q '^test0415: \([0-9]*\) of \1; end$' "$E/raw/test0415-on.out" || die "no end marker from the CPU test"
echo "cpu test: off $(tail -1 "$E/raw/test0415-off.out"), on $(tail -1 "$E/raw/test0415-on.out")"
for v in normal lean; do
    pgrep '^kyty_emulator' > /dev/null && die "an emulator started; stopped before $v"
    d=$E/build-$v; x=""; o=bin; [ $v = lean ] && { x="-DKYTY_BC5_LEAN=ON"; o=bin-lean; }
    mkdir -p "$d/externals" && cp -p "$W"/kytyplus-build/externals/ffmpeg-*.zip "$d/externals/" || die "the ffmpeg prebuilt copy"  # no download
    distrobox enter ubuntu -- cmake -S "$E/tree" -B "$d" -U "*PIPEWIRE*" -G Ninja -DCMAKE_BUILD_TYPE=Release \
        -DCMAKE_C_COMPILER=clang -DCMAKE_CXX_COMPILER=clang++ -DKYTY_BUILD_LAUNCHER=OFF \
        -DKYTY_BC5_BACKEND_SRC="$BSRC" -DKYTY_BC5_BACKEND_BUILD="$BBLD" $x < /dev/null > "$d.configure.log" 2>&1 || die "configure $v: $(tail -3 "$d.configure.log" | tr '\n' ' ')"
    echo "== $(date +%T) build $v"
    distrobox enter ubuntu -- sh -c "cd '$d' && nice -n 19 ninja kyty_emulator" < /dev/null > "$d.build.log" 2>&1 || { grep -m5 -E "error:" "$d.build.log"; die "the build ($v)"; }
    b=$d/src/kyty_emulator
    [ -x "$b" ] || die "no binary ($v)"
    for s in KYTY_BC5_LOAD_STAT KYTY_BC5_RING_POLL_US KYTY_BC5_LOAD_DELAY KYTY_BC5_RING_SPIN_US KYTY_BC5_TIMERSLACK_NS KYTY_BC5_MUTEX_SPIN_US KYTY_BC5_SEMA_TARGETED_WAKE KYTY_BC5_EVENT_COALESCE_SAME "tag ls415" bc5-loadstat KYTY_BC5_SWITCH_DEFAULTS KYTY_BC5_RANGES_FAST KYTY_BC5_PHYSMAP_SORTED; do
        grep -aqF -- "$s" "$b" || die "the $v binary lacks [$s]"
    done
    mkdir -p "$E/$o" && cp -p "$b" "$E/$o/kyty_emulator" || die "cannot place the $v binary"
    echo "$v: $(m "$E/$o/kyty_emulator"), warnings $(sed 's/\x1b\[[0-9;]*m//g' "$d.build.log" | grep -c 'warning:')"
done
[ "$(m "$ARCH")" = "$P_ARCH" ] || die "the archive changed"
{ printf '%s  bin/kyty_emulator\n' "$(md5sum < "$E/bin/kyty_emulator" | cut -d' ' -f1)"; printf '%s  bin-lean/kyty_emulator\n' "$(md5sum < "$E/bin-lean/kyty_emulator" | cut -d' ' -f1)"; } > "$E/built.md5"
echo "$(date '+%F %T') done; L1 normal $(m "$E/bin/kyty_emulator"), lean $(m "$E/bin-lean/kyty_emulator")"
release
