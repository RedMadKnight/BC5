#!/usr/bin/env bash
# BC5 exp 0412, build g412y (2026-11-13, README section 59): the catcher kit ff412 (KYTY_BC5_MEM_FIRSTFAIL,
# KYTY_BC5_TRAP_LOG, BC5_DIRECT_MAX_BO_MIB; all default off) on a PRIVATE copy of the integrated shared tree
# (patch 0001 4651d1d3), after exp 0413/0417's p*.sh: the copy keeps the tree's .git (the configure step needs it),
# has its own build directory, links the backend archive as it is. ~/src/KytyPlus, the shared build directories, the
# backend source and the archive are only read. Normal variant only.
#   1. checks: no emulator; the shared tree is 0001 4651d1d3; the archive is 75e30335; the kit's sums
#   2. the lock (the hard-link claim); the CPU test firstfail0412
#   3. the private tree $P/tree (copied once, with .git); the four units made by mkff0412.py FROM THE SHARED TREE's
#      units and checked against the sums made on the laptop; copied into the private tree
#   4. configure (first time) and ninja kyty_emulator, nice 19
#   5. checks on the binary; it is put beside as bin-y/kyty_emulator with built-y.md5 (run0412n.sh's N_EMU form)
# usage (on the box, no emulator running): bash mk0412y.sh
set -u
ulimit -c 0
export LC_ALL=C LANGUAGE=C
W=$HOME/bc5-work; X=$W/exp0412; P=$X/p; KIT=$X/kit-y; K=$HOME/src/KytyPlus; LOCK=$W/BOX-LOCK
ARCH=$W/backend-ubuntu/libbc5_backend.a; BSRC=$W/d19/export/backend; BBLD=$W/backend-ubuntu
m() { md5sum < "$1" 2> /dev/null | cut -c1-8; }
die() { echo "STOP: $*"; exit 1; }
pgrep '^kyty_emulator' > /dev/null && die "an emulator runs"
(cd "$KIT" && sha256sum -c --quiet kit.sha256) || die "the kit is not what was sent"
[ "$(git -C "$K" diff --no-color f266548 | md5sum | cut -c1-8)" = 4651d1d3 ] || die "the shared tree is not 0001 4651d1d3"
[ "$(m "$ARCH")" = 75e30335 ] || die "the archive is not 75e30335"
[ -d "$BSRC/include/bc5" ] || die "no backend include dir at $BSRC"
for u in "src/kernel/memory.cpp eff24b4c" "src/libs/libAmpr.cpp a2d09d32" "src/libs/bc5LleAgc.cpp a81efd2c"; do
  set -- $u; [ "$(m "$K/$1")" = "$2" ] || die "the shared tree's $1 is not $2"
done
LINE="guard exp 0412 | build g412y (the catcher kit ff412 on a private copy of the shared tree; CPU only), token $$"
[ -e "$LOCK" ] || touch "$LOCK"
[ -f "$LOCK" ] && [ ! -L "$LOCK" ] && [ ! -s "$LOCK" ] || die "the box is locked: $(cat "$LOCK")"
tl=$LOCK.0412-$$.new; al=$LOCK.0412-$$.aside
printf '%s\n' "$LINE" > "$tl" && mv -T "$LOCK" "$al" && ln "$tl" "$LOCK" || { [ -e "$LOCK" ] || mv -T "$al" "$LOCK"; rm -f "$tl"; die "the claim failed"; }
if [ -s "$al" ]; then mv -fT "$al" "$LOCK"; rm -f "$tl"; die "a foreign line arrived during the claim"; fi
rm -f "$al" "$tl"
release() { if grep -qxF -- "$LINE" "$LOCK" 2> /dev/null; then grep -vxF -- "$LINE" "$LOCK" > "$LOCK.0412-rel"; mv -fT "$LOCK.0412-rel" "$LOCK"; fi
  printf '%s\n' "guard exp 0412 | released: build g412y | $(date '+%F %T')" >> "$W/BOX-QUEUE"; }
trap release EXIT
printf '%s\n' "guard exp 0412 | claimed: build g412y | $(date '+%F %T')" >> "$W/BOX-QUEUE"
pgrep '^kyty_emulator' > /dev/null && die "an emulator started during the claim"
R=$X/raw-y; mkdir -p "$P" "$R" || die mkdir
echo "$(date '+%F %T') start"
distrobox enter ubuntu -- env LC_ALL=C g++ -std=c++20 -O1 -Wall -Wextra -Werror -I "$KIT" "$KIT/firstfail0412.cpp" -o "$R/firstfail0412" < /dev/null > "$R/firstfail0412-build.out" 2>&1 ||
    die "the CPU test does not build: $(grep -m2 error "$R/firstfail0412-build.out" | cut -c1-160 | tr '\n' ' ')"
distrobox enter ubuntu -- "$R/firstfail0412" < /dev/null > "$R/firstfail0412.out" 2>&1 || die "the CPU test failed: $(grep -m2 FAIL "$R/firstfail0412.out" | cut -c1-160 | tr '\n' ' ')"
grep -q '^firstfail0412: \([0-9]*\) of \1; end$' "$R/firstfail0412.out" || die "no end marker from the CPU test"
echo "cpu test: $(tail -1 "$R/firstfail0412.out")"
if [ ! -d "$P/tree/.git" ]; then
  [ ! -e "$P/tree" ] || die "$P/tree exists without .git"
  echo "$(date +%T) copying the shared tree (with .git) to $P/tree"
  cp -a --reflink=auto "$K" "$P/tree" || die "the copy failed"
fi
[ "$(git -C "$P/tree" rev-parse HEAD)" = "$(git -C "$K" rev-parse HEAD)" ] || die "the private tree is not at the shared tree's commit"
rm -rf "$P/out" && python3 -I "$KIT/mkff0412.py" "$K" "$P/out" > "$R/mkff0412.out" 2> "$R/mkff0412.err" || die "mkff0412.py: $(tail -1 "$R/mkff0412.err")"
cat "$R/mkff0412.out"
for u in "src/kernel/memory.cpp 961da63a" "src/libs/libAmpr.cpp d88da83d" "src/common/hostException.cpp e978e975" "src/libs/bc5LleAgc.cpp d8270884"; do
  set -- $u; [ "$(m "$P/out/$1")" = "$2" ] || die "$1 is not the unit checked on the laptop ($2)"
  cp -p "$P/out/$1" "$P/tree/$1" || die "cannot put $1 into the private tree"
done
# Everything else in the private tree must still be the shared tree's.
D=$(diff -rq --exclude=.git --exclude='build*' "$K/src" "$P/tree/src" | grep -v -E "src/kernel/memory.cpp|src/libs/libAmpr.cpp|src/common/hostException.cpp|src/libs/bc5LleAgc.cpp" | head -5)
[ -z "$D" ] || die "the private tree differs from the shared one beyond the four units: $D"
B=$P/build-normal
if [ ! -f "$B/build.ninja" ]; then
  echo "== $(date +%T) configure"
  distrobox enter ubuntu -- cmake -S "$P/tree" -B "$B" -U "*PIPEWIRE*" -G Ninja -DCMAKE_BUILD_TYPE=Release \
      -DCMAKE_C_COMPILER=clang -DCMAKE_CXX_COMPILER=clang++ -DKYTY_BUILD_LAUNCHER=OFF \
      -DKYTY_BC5_BACKEND_SRC="$BSRC" -DKYTY_BC5_BACKEND_BUILD="$BBLD" < /dev/null > "$B.configure.log" 2>&1 || die "configure: $(tail -3 "$B.configure.log" | tr '\n' ' ' | cut -c1-300)"
fi
pgrep '^kyty_emulator' > /dev/null && die "an emulator started; stopped before the build"
echo "== $(date +%T) build"
distrobox enter ubuntu -- sh -c "cd '$B' && nice -n 19 ninja kyty_emulator" < /dev/null > "$B.build.log" 2>&1 || { grep -m6 -E "error:" "$B.build.log" | cut -c1-240; die "the build failed"; }
b=$B/src/kyty_emulator
[ -x "$b" ] || die "no binary"
echo "normal: $(md5sum < "$b" | cut -d' ' -f1), warnings $(grep -c 'warning:' "$B.build.log")"
for s in KYTY_BC5_MEM_FIRSTFAIL KYTY_BC5_TRAP_LOG BC5_DIRECT_MAX_BO_MIB "tag ff412" BC5_GUARD_LEARN_LOG KYTY_BC5_AMM_SCATTER KYTY_BC5_AMM_SETBUFFER_GUARD; do
  grep -aqF -- "$s" "$b" || die "the binary lacks [$s]"
done
[ "$(m "$ARCH")" = 75e30335 ] || die "the archive changed"
# Beside the others, where run0412n.sh's N_EMU takes it. The copy must find the same libraries as the original.
mkdir -p "$X/bin-y" || die "mkdir bin-y"
cp -p "$b" "$X/bin-y/kyty_emulator.new-$$" && mv -fT "$X/bin-y/kyty_emulator.new-$$" "$X/bin-y/kyty_emulator" || die "cannot put the binary beside"
L1=$(distrobox enter ubuntu -- ldd "$b" < /dev/null 2> /dev/null | awk '{print $1, $3}' | sort | md5sum | cut -c1-8)
L2=$(distrobox enter ubuntu -- ldd "$X/bin-y/kyty_emulator" < /dev/null 2> /dev/null | awk '{print $1, $3}' | sort | md5sum | cut -c1-8)
[ "$L1" = "$L2" ] && ! distrobox enter ubuntu -- ldd "$X/bin-y/kyty_emulator" < /dev/null 2> /dev/null | grep -q "not found" || die "the copy in bin-y does not resolve the same libraries as the build's binary ($L1 / $L2)"
printf '%s  bin-y/kyty_emulator\n' "$(md5sum < "$X/bin-y/kyty_emulator" | cut -d' ' -f1)" > "$X/built-y.md5" || die "built-y.md5"
[ "$(md5sum < "$X/bin/kyty_emulator" | cut -c1-8)" = bc4356a5 ] || die "the build in place changed"
echo "binary beside $(m "$X/bin-y/kyty_emulator") (bin-y); g412v in place untouched; the shared builds and the archive only read"
echo "$(date '+%F %T') built: g412y"
