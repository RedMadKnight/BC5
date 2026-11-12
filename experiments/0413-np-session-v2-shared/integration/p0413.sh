#!/usr/bin/env bash
# BC5 exp 0413, the PRIVATE build of the integration (the top session's GO, 2026-11-12 10:56, slot to 12:30): patch 0001
# 76c1d045 (branch int/0413-tested-into-shared) built under ~/bc5-work/exp0413/p only. ~/src/KytyPlus, the shared build
# directories, the backend source and the backend archive are only read.
#   1. checks: no emulator, the shared tree's diff is 0001-old (2dbed49a), the kit's md5s, the archive's md5
#   2. the lock; the shared tree copied without .git; 0001-old reversed and 0001-new applied; every patched file checked
#      against tree.md5 (made from the laptop's replay tree)
#   3. configure and build normal and lean (bc5-build.sh's options, the shared backend paths), nice 19
#   4. checks on the binaries; the archive unchanged; the lock released
# usage (on the box, in ~/bc5-work/exp0413/p/kit): bash p0413.sh
set -u
ulimit -c 0
export LC_ALL=C LANGUAGE=C
W=$HOME/bc5-work; E=$W/exp0413; P=$E/p; HERE=$(cd "$(dirname "$0")" && pwd); K=$HOME/src/KytyPlus
LOCK=$W/BOX-LOCK; ID=$E/lock.line; ARCH=$W/backend-ubuntu/libbc5_backend.a; BSRC=$W/d19/export/backend; BBLD=$W/backend-ubuntu
m() { md5sum < "$1" | cut -c1-8; }
stop() { echo "p0413 STOP: $*"; exit 1; }
own() { [ -s "$ID" ] && [ "$(cat "$LOCK" 2> /dev/null)" = "$(cat "$ID")" ]; }
claim() {
    local c=$LOCK.d19-claim t=$LOCK.0413-$$.new a=$LOCK.0413-$$.aside line
    pgrep '^kyty_emulator' > /dev/null && stop "an emulator runs"
    mkdir -p "$E" || stop "cannot make $E"
    line="exp 0413 | token $(date +%s)$$ | $1, no emulator, until $(date -d +"$2"min +%H:%M) | $(date '+%F %T')"
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
    if own; then : > "$LOCK" && [ ! -s "$LOCK" ] && { rm -f "$ID"; echo "lock released"; return 0; }; echo "p0413: the lock could not be released"; return 1; fi
    echo "p0413: the lock is not ours, left as it is: $(cat "$LOCK" 2> /dev/null)"; return 1
}
die() { echo "p0413 STOP: $*"; release; exit 1; }
pgrep '^kyty_emulator' > /dev/null && stop "an emulator runs"
[ "$(git -C "$K" diff --no-color f266548 | md5sum | cut -c1-8)" = 2dbed49a ] || stop "the shared tree is not 0001 2dbed49a"
[ "$(m "$HERE/0001-old.patch")" = 2dbed49a ] && [ "$(m "$HERE/0001-new.patch")" = 76c1d045 ] || stop "the kit's patches are not the pins"
[ "$(m "$ARCH")" = 75e30335 ] || stop "the archive is not 75e30335"
[ -d "$BSRC/include/bc5" ] || stop "no backend include dir at $BSRC"
claim "exp 0413: private build of the integration (normal + lean) under exp0413/p, CPU only" 60
echo "$(date '+%F %T') start; archive $(m "$ARCH")"
rm -rf "$P/tree" "$P/build-normal" "$P/build-lean" || die "cannot clear $P"
mkdir -p "$P/tree" || die "mkdir"
tar -C "$K" -cf - . | tar -C "$P/tree" -xf - || die "tree copy"  # with .git: ffmpeg-core's CMake asks git for its commit
(cd "$P/tree" && git apply -R --whitespace=nowarn "$HERE/0001-old.patch") || die "reversing 0001-old"
(cd "$P/tree" && git apply --whitespace=nowarn "$HERE/0001-new.patch") || die "applying 0001-new"
bad=0
while read -r sum f; do [ "$(md5sum < "$P/tree/$f" | cut -d' ' -f1)" = "$sum" ] || { echo "differs: $f"; bad=$((bad + 1)); }; done < "$HERE/tree.md5"
[ "$bad" = 0 ] || die "$bad files differ from the laptop's tree"
echo "tree: $(wc -l < "$HERE/tree.md5") patched files match the laptop's"
cfg() {  # build dir, extra -D
    distrobox enter ubuntu -- cmake -S "$P/tree" -B "$1" -U "*PIPEWIRE*" -G Ninja -DCMAKE_BUILD_TYPE=Release \
        -DCMAKE_C_COMPILER=clang -DCMAKE_CXX_COMPILER=clang++ -DKYTY_BUILD_LAUNCHER=OFF \
        -DKYTY_BC5_BACKEND_SRC="$BSRC" -DKYTY_BC5_BACKEND_BUILD="$BBLD" $2 < /dev/null > "$1.configure.log" 2>&1
}
for v in normal lean; do
    pgrep '^kyty_emulator' > /dev/null && die "an emulator started; stopped before $v"
    d=$P/build-$v; x=""; [ $v = lean ] && x="-DKYTY_BC5_LEAN=ON"
    mkdir -p "$d/externals" && cp -p "$W/kytyplus-build/externals/ffmpeg-94dde08.zip" "$d/externals/" || die "ffmpeg prebuilt copy"  # no download
    echo "== $(date +%T) configure $v"
    cfg "$d" "$x" || { tail -20 "$d.configure.log"; die "configure $v"; }
    echo "== $(date +%T) build $v"
    distrobox enter ubuntu -- sh -c "cd '$d' && nice -n 19 ninja kyty_emulator" < /dev/null > "$d.build.log" 2>&1 || { grep -m5 -E "error:" "$d.build.log"; die "build $v"; }
    b=$d/src/kyty_emulator
    [ -x "$b" ] || die "no binary for $v"
    echo "$v: $(md5sum < "$b" | cut -d' ' -f1), warnings $(grep -c 'warning:' "$d.build.log")"
    for s in "NpCppWebApi SessionManager V2 on (10 exports registered)" KYTY_BC5_SWITCH_DEFAULTS KYTY_BC5_EVENT_PENDING_CAP KYTY_BC5_RANGES_FAST KYTY_BC5_PHYSMAP_SORTED BC5_GUARD_ZSKIP_POLL_SUBMIT KYTY_BC5_FW_NET KYTY_BC5_AMM_SCATTER; do
        grep -aqF -- "$s" "$b" || die "$v lacks [$s]"
    done
    for n in eVU3cXIJz0w BY1jyWLZrcA JiY4sfHkV34 LbhH9NeB93I XuVY56j7GM0 fIzsqjyD5oY sRn6qePT54Q -0Vv7HKZaBM yl3T9brJay4 xjVhrq2KPJA; do
        strings "$b" | grep -qx -- "$n" || die "$v lacks the NID $n"
    done
done
[ "$(m "$ARCH")" = 75e30335 ] || die "the archive changed"
echo "$(date '+%F %T') done; normal $(m "$P/build-normal/src/kyty_emulator"), lean $(m "$P/build-lean/src/kyty_emulator")"
release
