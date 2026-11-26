#!/usr/bin/env bash
# BC5 exp 0412, build g412z (2026-11-13, README sections 59-63; "fixes first": one private build with all of it, each
# behind its switch), on a PRIVATE copy of the integrated shared tree (patch 0001 4651d1d3) and a PRIVATE copy of the
# backend source:
#   nl412   the learned path removed from the unit, the heap-end guards kept (mknl0412.py --keep-guards); the catcher
#           always on; BC5_GUARD_K1_STAT (default off)
#   rl412   BC5_DIRECT_RESET_LABELS_ADD (mkrl0412.py): the lost jobs' label writes when two jobs time out in one hang
#   k1r412  BC5_GUARD_K1R (mkk1r0412.py unit + backend): the read-only zero cover; the backend gets map_shared(readonly)
#   fr412   BC5_FAULT_RECORD (mkfr0412.py): at the first GPU fault a self-contained record is written and the game ends
#   sg412   the record's save guard (mksg0412.py, saveguard0412.inc): the exit lets a save being written finish;
#           marks in src/kernel/fileSystem.cpp and src/libs/libSaveData.cpp, the header src/bc5/save_guard0412.hpp
#   ff412   KYTY_BC5_MEM_FIRSTFAIL, KYTY_BC5_TRAP_LOG, BC5_DIRECT_MAX_BO_MIB (mkff0412.py)
# ~/src/KytyPlus, the shared build directories, the shared backend source and the shared archive are only read.
#   1. checks: no emulator; the shared tree is 0001 4651d1d3; the shared archive is 75e30335; the kit's sums
#   2. the lock (the hard-link claim); the five CPU tests
#   3. the private tree $P/tree (copied once, with .git); the units made from the SHARED tree's units in the order
#      nl, rl, k1r, fr, sg, ff and checked against the sums made on the laptop; the private backend source and its archive
#   4. configure (every time: the backend paths are private) and ninja kyty_emulator, nice 19
#   5. checks on the binary; it is put beside as bin-z/kyty_emulator with built-z.md5 (run0412n.sh's N_EMU form)
# usage (on the box, no emulator running): bash mk0412z.sh
set -u
ulimit -c 0
export LC_ALL=C LANGUAGE=C
W=$HOME/bc5-work; X=$W/exp0412; P=$X/p; KIT=$X/kit-z; K=$HOME/src/KytyPlus; LOCK=$W/BOX-LOCK
ARCH=$W/backend-ubuntu/libbc5_backend.a; BSRC=$W/d19/export/backend
m() { md5sum < "$1" 2> /dev/null | cut -c1-8; }
die() { echo "STOP: $*"; exit 1; }
pgrep '^kyty_emulator' > /dev/null && die "an emulator runs"
(cd "$KIT" && sha256sum -c --quiet kit.sha256) || die "the kit is not what was sent"
[ "$(git -C "$K" diff --no-color f266548 | md5sum | cut -c1-8)" = 4651d1d3 ] || die "the shared tree is not 0001 4651d1d3"
[ "$(m "$ARCH")" = 75e30335 ] || die "the shared archive is not 75e30335"
[ -d "$BSRC/include/bc5" ] && [ -f "$BSRC/src/direct.cpp" ] || die "no backend source at $BSRC"
for u in "src/kernel/memory.cpp eff24b4c" "src/libs/libAmpr.cpp a2d09d32" "src/libs/bc5LleAgc.cpp a81efd2c" "src/kernel/fileSystem.cpp 9194fc38" "src/libs/libSaveData.cpp 0e0c5d40"; do
  set -- $u; [ "$(m "$K/$1")" = "$2" ] || die "the shared tree's $1 is not $2"
done
LINE="guard exp 0412 | build g412z (nl412 + rl412 + k1r412 + fr412 + sg412 + ff412 on private copies of the shared tree and backend; CPU only), token $$"
[ -e "$LOCK" ] || touch "$LOCK"
[ -f "$LOCK" ] && [ ! -L "$LOCK" ] && [ ! -s "$LOCK" ] || die "the box is locked: $(cat "$LOCK")"
tl=$LOCK.0412-$$.new; al=$LOCK.0412-$$.aside
printf '%s\n' "$LINE" > "$tl" && mv -T "$LOCK" "$al" && ln "$tl" "$LOCK" || { [ -e "$LOCK" ] || mv -T "$al" "$LOCK"; rm -f "$tl"; die "the claim failed"; }
if [ -s "$al" ]; then mv -fT "$al" "$LOCK"; rm -f "$tl"; die "a foreign line arrived during the claim"; fi
rm -f "$al" "$tl"
release() { if grep -qxF -- "$LINE" "$LOCK" 2> /dev/null; then grep -vxF -- "$LINE" "$LOCK" > "$LOCK.0412-rel"; mv -fT "$LOCK.0412-rel" "$LOCK"; fi
  printf '%s\n' "guard exp 0412 | released: build g412z | $(date '+%F %T')" >> "$W/BOX-QUEUE"; }
trap release EXIT
printf '%s\n' "guard exp 0412 | claimed: build g412z | $(date '+%F %T')" >> "$W/BOX-QUEUE"
pgrep '^kyty_emulator' > /dev/null && die "an emulator started during the claim"
R=$X/raw-z; mkdir -p "$P" "$R" || die mkdir
echo "$(date '+%F %T') start"
for t in firstfail0412 maprule0412 rlabels0412 k1r0412 saveguard0412; do
  distrobox enter ubuntu -- env LC_ALL=C g++ -std=c++20 -O1 -Wall -Wextra -Werror -pthread -I "$KIT" "$KIT/$t.cpp" -o "$R/$t" < /dev/null > "$R/$t-build.out" 2>&1 ||
      die "the CPU test $t does not build: $(grep -m2 error "$R/$t-build.out" | cut -c1-160 | tr '\n' ' ')"
  distrobox enter ubuntu -- "$R/$t" "$R" < /dev/null > "$R/$t.out" 2>&1 || die "the CPU test $t failed: $(grep -m2 FAIL "$R/$t.out" | cut -c1-160 | tr '\n' ' ')"
  grep -q "^$t: \([0-9]*\) of \1; end\$" "$R/$t.out" || die "no end marker from the CPU test $t"
  echo "cpu test: $(tail -1 "$R/$t.out")"
done
if [ ! -d "$P/tree/.git" ]; then
  [ ! -e "$P/tree" ] || die "$P/tree exists without .git"
  echo "$(date +%T) copying the shared tree (with .git) to $P/tree"
  cp -a --reflink=auto "$K" "$P/tree" || die "the copy failed"
fi
[ "$(git -C "$P/tree" rev-parse HEAD)" = "$(git -C "$K" rev-parse HEAD)" ] || die "the private tree is not at the shared tree's commit"
# The unit's chain, from the shared tree's unit: nl (guards kept), rl, k1r, fr; then ff over a staged copy of the four units.
S=$P/stage; rm -rf "$S" "$P/out" && mkdir -p "$S/src/kernel" "$S/src/libs" "$S/src/common" || die "mkdir stage"
python3 -I "$KIT/mknl0412.py" "$K/src/libs/bc5LleAgc.cpp" "$P/u-nl.cpp" --keep-guards > "$R/mknl.out" 2>&1 || die "mknl0412.py: $(tail -1 "$R/mknl.out")"
[ "$(m "$P/u-nl.cpp")" = cfb7533e ] || die "the unit after nl412 is not cfb7533e"
python3 -I "$KIT/mkrl0412.py" "$P/u-nl.cpp" "$P/u-rl.cpp" > "$R/mkrl.out" 2>&1 || die "mkrl0412.py: $(tail -1 "$R/mkrl.out")"
[ "$(m "$P/u-rl.cpp")" = 0878903e ] || die "the unit after rl412 is not 0878903e"
python3 -I "$KIT/mkk1r0412.py" unit "$P/u-rl.cpp" "$P/u-k1r.cpp" > "$R/mkk1r.out" 2>&1 || die "mkk1r0412.py unit: $(tail -1 "$R/mkk1r.out")"
[ "$(m "$P/u-k1r.cpp")" = 0d265595 ] || die "the unit after k1r412 is not 0d265595"
python3 -I "$KIT/mkfr0412.py" "$P/u-k1r.cpp" "$P/u-fr.cpp" > "$R/mkfr.out" 2>&1 || die "mkfr0412.py: $(tail -1 "$R/mkfr.out")"
[ "$(m "$P/u-fr.cpp")" = 0a4fa422 ] || die "the unit after fr412 is not 0a4fa422"
python3 -I "$KIT/mksg0412.py" "$K" "$P/sg-out" "$KIT/saveguard0412.inc" > "$R/mksg.out" 2>&1 || die "mksg0412.py: $(tail -1 "$R/mksg.out")"
cat "$R/mksg.out"
cp -p "$K/src/kernel/memory.cpp" "$S/src/kernel/" && cp -p "$K/src/libs/libAmpr.cpp" "$S/src/libs/" && cp -p "$K/src/common/hostException.cpp" "$S/src/common/" && cp "$P/u-fr.cpp" "$S/src/libs/bc5LleAgc.cpp" || die "staging"
python3 -I "$KIT/mkff0412.py" "$S" "$P/out" > "$R/mkff0412.out" 2> "$R/mkff0412.err" || die "mkff0412.py: $(tail -1 "$R/mkff0412.err")"
cat "$R/mkff0412.out"
for u in "src/kernel/memory.cpp 961da63a" "src/libs/libAmpr.cpp d88da83d" "src/common/hostException.cpp e978e975" "src/libs/bc5LleAgc.cpp 1c5d1ec2"; do
  set -- $u; [ "$(m "$P/out/$1")" = "$2" ] || die "$1 is not the unit checked on the laptop ($2)"
  cp -p "$P/out/$1" "$P/tree/$1" || die "cannot put $1 into the private tree"
done
for u in "src/kernel/fileSystem.cpp 3d2b9c0b" "src/libs/libSaveData.cpp 0bd91bb4" "src/bc5/save_guard0412.hpp 1f1585b4"; do
  set -- $u; [ "$(m "$P/sg-out/$1")" = "$2" ] || die "$1 is not the unit checked on the laptop ($2)"
  cp -p "$P/sg-out/$1" "$P/tree/$1" || die "cannot put $1 into the private tree"
done
D=$(diff -rq --exclude=.git "$K/src" "$P/tree/src" | grep -v -E "src/kernel/memory.cpp|src/libs/libAmpr.cpp|src/common/hostException.cpp|src/libs/bc5LleAgc.cpp|src/kernel/fileSystem.cpp|src/libs/libSaveData.cpp|save_guard0412.hpp" | head -5)
[ -z "$D" ] || die "the private tree differs from the shared one beyond the six units and the header: $D"
# The private backend: the shared source copied, map_shared(readonly) added, its own build directory.
PB=$P/backend-src; BB=$P/backend-build
rm -rf "$PB" && cp -a "$BSRC" "$PB" || die "cannot copy the backend source"
python3 -I "$KIT/mkk1r0412.py" backend "$BSRC" "$PB" > "$R/mkk1r-backend.out" 2>&1 || die "mkk1r0412.py backend: $(tail -1 "$R/mkk1r-backend.out")"
cat "$R/mkk1r-backend.out"
[ "$(diff -rq "$BSRC" "$PB" | grep -c .)" = 2 ] || die "the private backend differs from the shared one by more than direct.hpp and direct.cpp: $(diff -rq "$BSRC" "$PB" | head -4 | tr '\n' ' ')"
echo "== $(date +%T) backend"
distrobox enter ubuntu -- cmake -S "$PB" -B "$BB" -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_C_COMPILER=clang -DCMAKE_CXX_COMPILER=clang++ \
    -DBC5_WITH_AMDGPU=ON -DBC5_BUILD_TESTS=OFF < /dev/null > "$BB.configure.log" 2>&1 || die "backend configure: $(tail -3 "$BB.configure.log" | tr '\n' ' ' | cut -c1-300)"
distrobox enter ubuntu -- sh -c "cd '$BB' && nice -n 19 ninja" < /dev/null > "$BB.build.log" 2>&1 || { grep -m6 -E "error:" "$BB.build.log" | cut -c1-240; die "the backend build failed"; }
[ -f "$BB/libbc5_backend.a" ] || die "no private backend archive"
echo "private backend archive $(m "$BB/libbc5_backend.a") (the shared one $(m "$ARCH") untouched)"
B=$P/build-normal
echo "== $(date +%T) configure"
distrobox enter ubuntu -- cmake -S "$P/tree" -B "$B" -U "*PIPEWIRE*" -G Ninja -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_C_COMPILER=clang -DCMAKE_CXX_COMPILER=clang++ -DKYTY_BUILD_LAUNCHER=OFF \
    -DKYTY_BC5_BACKEND_SRC="$PB" -DKYTY_BC5_BACKEND_BUILD="$BB" < /dev/null > "$B.configure.log" 2>&1 || die "configure: $(tail -3 "$B.configure.log" | tr '\n' ' ' | cut -c1-300)"
pgrep '^kyty_emulator' > /dev/null && die "an emulator started; stopped before the build"
echo "== $(date +%T) build"
distrobox enter ubuntu -- sh -c "cd '$B' && nice -n 19 ninja kyty_emulator" < /dev/null > "$B.build.log" 2>&1 || { grep -m8 -E "error:" "$B.build.log" | cut -c1-260; die "the build failed"; }
b=$B/src/kyty_emulator
[ -x "$b" ] || die "no binary"
echo "normal: $(md5sum < "$b" | cut -d' ' -f1), warnings $(grep -c 'warning:' "$B.build.log")"
for s in BC5_FAULT_RECORD "tag fr412" "tag sg412" "MAY BE INCOMPLETE" BC5_GUARD_K1R_REPLACE KYTY_BC5_MEM_FIRSTFAIL KYTY_BC5_TRAP_LOG BC5_DIRECT_MAX_BO_MIB "tag ff412" BC5_GUARD_K1R "tag k1r412" BC5_DIRECT_RESET_LABELS_ADD "tag rl412" "tag nl412" BC5_GUARD_K1_STAT KYTY_BC5_AMM_SCATTER KYTY_BC5_AMM_SETBUFFER_GUARD; do
  grep -aqF -- "$s" "$b" || die "the binary lacks [$s]"
done
grep -aqF "direct-learned" "$b" && echo "note: the string direct-learned is still in the binary (another unit?)"
[ "$(m "$ARCH")" = 75e30335 ] || die "the shared archive changed"
mkdir -p "$X/bin-z" || die "mkdir bin-z"
cp -p "$b" "$X/bin-z/kyty_emulator.new-$$" && mv -fT "$X/bin-z/kyty_emulator.new-$$" "$X/bin-z/kyty_emulator" || die "cannot put the binary beside"
L1=$(distrobox enter ubuntu -- ldd "$b" < /dev/null 2> /dev/null | awk '{print $1, $3}' | sort | md5sum | cut -c1-8)
L2=$(distrobox enter ubuntu -- ldd "$X/bin-z/kyty_emulator" < /dev/null 2> /dev/null | awk '{print $1, $3}' | sort | md5sum | cut -c1-8)
[ "$L1" = "$L2" ] && ! distrobox enter ubuntu -- ldd "$X/bin-z/kyty_emulator" < /dev/null 2> /dev/null | grep -q "not found" || die "the copy in bin-z does not resolve the same libraries as the build's binary ($L1 / $L2)"
printf '%s  bin-z/kyty_emulator\n' "$(md5sum < "$X/bin-z/kyty_emulator" | cut -d' ' -f1)" > "$X/built-z.md5" || die "built-z.md5"
[ "$(md5sum < "$X/bin/kyty_emulator" | cut -c1-8)" = bc4356a5 ] || die "the build in place changed"
echo "binary beside $(m "$X/bin-z/kyty_emulator") (bin-z); g412v in place untouched; the shared builds, backend and archive only read"
echo "$(date '+%F %T') built: g412z"
