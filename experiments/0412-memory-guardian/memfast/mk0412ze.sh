#!/usr/bin/env bash
# BC5 exp 0412, build g412ze (2026-11-13, README section 74): FORM 2 for the shared fold (exp 0419's candidate E takes
# this order): g412zd WITHOUT the read probe pr412 (a deliberate-fault tool has no place in a shared build), and since
# the top's order of 2026-11-13 evening (README section 76) with K1R, cv412, kl412 and K1_FILTER ON by default and the
# options BC5_GUARD_K1R_COVERS_VISIBLE, _COVER_WRITTEN, _WRITTEN_SCAN_MS, _REPLACE removed (off switches left: BC5_GUARD_K1R=0,
# BC5_GUARD_K1_FILTER=0; BC5_GUARD_LAZY_BY_DATA stays off, undecided). The K1r family on the SHARED tree as it is since
# 15:47 (candidate B, patch 0001 27b6416f: it already carries nl412, rl412, fr412, sg412 and ff412), on a PRIVATE copy
# of that tree and a PRIVATE copy of the backend source. "Fixes first": one build, each thing behind its switch.
#   k1r412  BC5_GUARD_K1R (mkk1r0412.py unit + backend): the read-only zero cover; backend map_shared(readonly)
#   wa412   BC5_GUARD_WATCH (mkwa0412.py): the state of up to four guest addresses in the journal
#   cv412   (mkcv0412.py unit + backend; BC5_GUARD_K1R_COVERS_VISIBLE=1 turns it off) a cover is invisible to the host
#   k1f412  BC5_GUARD_K1_FILTER (mkk1f0412.py): =1 imports a packet's unmapped operand under a view; =log names it
#   kl412   (mkkl0412.py; BC5_GUARD_K1R_COVER_WRITTEN=1 turns it off) under a lazy view a written chunk gets no cover;
#           BC5_GUARD_LAZY_BY_DATA=1: no view is lazy (a written chunk is imported)
# ~/src/KytyPlus, the shared build directories, the shared backend source and the shared archive are only read.
# The private tree $P/tree is brought to the shared tree's state with rsync (times kept, .git left alone), then the
# one unit is replaced. The binary goes beside as bin-e/kyty_emulator with built-e.md5 (run0412n.sh's N_EMU form).
# usage (on the box, no emulator running): bash mk0412ze.sh
set -u
ulimit -c 0
export LC_ALL=C LANGUAGE=C
W=$HOME/bc5-work; X=$W/exp0412; P=$X/p; KIT=$X/kit-ze; K=$HOME/src/KytyPlus; LOCK=$W/BOX-LOCK
ARCH=$W/backend-ubuntu/libbc5_backend.a; BSRC=$W/d19/export/backend
m() { md5sum < "$1" 2> /dev/null | cut -c1-8; }
die() { echo "STOP: $*"; exit 1; }
pgrep '^kyty_emulator' > /dev/null && die "an emulator runs"
(cd "$KIT" && sha256sum -c --quiet kit.sha256) || die "the kit is not what was sent"
[ "$(git -C "$K" diff --no-color f266548 | md5sum | cut -c1-8)" = 27b6416f ] || die "the shared tree is not 0001 27b6416f"
[ "$(m "$ARCH")" = 75e30335 ] || die "the shared archive is not 75e30335"
[ "$(m "$BSRC/include/bc5/direct.hpp")" = a9fcb26b ] && [ "$(m "$BSRC/src/direct.cpp")" = 51279eae ] || die "the shared backend source is not a9fcb26b/51279eae"
[ "$(m "$K/src/libs/bc5LleAgc.cpp")" = 8126c0aa ] || die "the shared tree's unit is not 8126c0aa"
[ -d "$P/tree/.git" ] || die "no private tree at $P/tree"
LINE="guard exp 0412 | build g412ze (k1r412 + wa412 + cv412 + k1f412 + kl412, no probe, on private copies of the shared tree B and backend; CPU only), token $$"
[ -e "$LOCK" ] || touch "$LOCK"
[ -f "$LOCK" ] && [ ! -L "$LOCK" ] && [ ! -s "$LOCK" ] || die "the box is locked: $(cat "$LOCK")"
tl=$LOCK.0412-$$.new; al=$LOCK.0412-$$.aside
printf '%s\n' "$LINE" > "$tl" && mv -T "$LOCK" "$al" && ln "$tl" "$LOCK" || { [ -e "$LOCK" ] || mv -T "$al" "$LOCK"; rm -f "$tl"; die "the claim failed"; }
if [ -s "$al" ]; then mv -fT "$al" "$LOCK"; rm -f "$tl"; die "a foreign line arrived during the claim"; fi
rm -f "$al" "$tl"
release() { if grep -qxF -- "$LINE" "$LOCK" 2> /dev/null; then grep -vxF -- "$LINE" "$LOCK" > "$LOCK.0412-rel"; mv -fT "$LOCK.0412-rel" "$LOCK"; fi
  printf '%s\n' "guard exp 0412 | released: build g412ze | $(date '+%F %T')" >> "$W/BOX-QUEUE"; }
trap release EXIT
printf '%s\n' "guard exp 0412 | claimed: build g412ze | $(date '+%F %T')" >> "$W/BOX-QUEUE"
pgrep '^kyty_emulator' > /dev/null && die "an emulator started during the claim"
R=$X/raw-ze; mkdir -p "$R" || die mkdir
echo "$(date '+%F %T') start"
for t in k1r0412 cover0412 kl0412; do
  distrobox enter ubuntu -- env LC_ALL=C g++ -std=c++20 -O1 -Wall -Wextra -Werror -pthread -I "$KIT" "$KIT/$t.cpp" -o "$R/$t" < /dev/null > "$R/$t-build.out" 2>&1 ||
      die "the CPU test $t does not build: $(grep -m2 error "$R/$t-build.out" | cut -c1-160 | tr '\n' ' ')"
  distrobox enter ubuntu -- "$R/$t" "$R" < /dev/null > "$R/$t.out" 2>&1 || die "the CPU test $t failed: $(grep -m2 FAIL "$R/$t.out" | cut -c1-160 | tr '\n' ' ')"
  grep -q "^$t: \([0-9]*\) of \1; end\$" "$R/$t.out" || die "no end marker from the CPU test $t"
  echo "cpu test: $(tail -1 "$R/$t.out")"
done
# The unit's chain from the shared tree's unit, each step checked against the sum made on the laptop.
U=$K/src/libs/bc5LleAgc.cpp
step() { # <script> <mode or -> <in> <out> <sum>
  if [ "$2" = - ]; then python3 -I "$KIT/$1" "$3" "$4" > "$R/$1.out" 2>&1; else python3 -I "$KIT/$1" "$2" "$3" "$4" > "$R/$1.out" 2>&1; fi || die "$1: $(tail -1 "$R/$1.out")"
  [ "$(m "$4")" = "$5" ] || die "the unit after $1 is $(m "$4"), not $5"
}
rm -f "$P"/e-u[1-6].cpp
step mkk1r0412.py unit "$U" "$P/e-u1.cpp" 496a339c
step mkwa0412.py - "$P/e-u1.cpp" "$P/e-u2.cpp" 3e5a6851
step mkcv0412.py unit "$P/e-u2.cpp" "$P/e-u4.cpp" 3732021b
step mkk1f0412.py - "$P/e-u4.cpp" "$P/e-u5.cpp" dcb7aa43
step mkkl0412.py - "$P/e-u5.cpp" "$P/e-u6.cpp" 9a54eaa4
echo "$(date +%T) the private tree is brought to the shared tree's state"
rsync -a --delete --exclude=.git "$K/" "$P/tree/" || die "rsync of the shared tree failed"
[ "$(git -C "$P/tree" rev-parse HEAD)" = "$(git -C "$K" rev-parse HEAD)" ] || die "the private tree is not at the shared tree's commit"
[ -z "$(diff -rq --exclude=.git "$K" "$P/tree" | head -3)" ] || die "the private tree differs from the shared one after rsync: $(diff -rq --exclude=.git "$K" "$P/tree" | head -3 | tr '\n' ' ')"
cp "$P/e-u6.cpp" "$P/tree/src/libs/bc5LleAgc.cpp" || die "cannot put the unit into the private tree"
D=$(diff -rq --exclude=.git "$K" "$P/tree" | grep -v "src/libs/bc5LleAgc.cpp" | head -5)
[ -z "$D" ] || die "the private tree differs from the shared one beyond the unit: $D"
# The private backend: the shared source copied, map_shared(readonly), the probe and the cover's readonly report added.
PB=$P/backend-src; BB=$P/backend-build
rm -rf "$PB" && cp -a "$BSRC" "$PB" || die "cannot copy the backend source"
python3 -I "$KIT/mkk1r0412.py" backend "$BSRC" "$PB" > "$R/mkk1r-backend.out" 2>&1 || die "mkk1r0412.py backend: $(tail -1 "$R/mkk1r-backend.out")"
python3 -I "$KIT/mkcv0412.py" backend "$PB" "$PB" > "$R/mkcv-backend.out" 2>&1 || die "mkcv0412.py backend: $(tail -1 "$R/mkcv-backend.out")"
[ "$(m "$PB/include/bc5/direct.hpp")" = e96e5c73 ] && [ "$(m "$PB/src/direct.cpp")" = 28100ce5 ] || die "the private backend is not the one checked on the laptop (e96e5c73, 28100ce5)"
[ "$(diff -rq "$BSRC" "$PB" | grep -c .)" = 2 ] || die "the private backend differs from the shared one by more than direct.hpp and direct.cpp"
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
for s in BC5_GUARD_LAZY_BY_DATA "tag kl412" BC5_GUARD_K1_FILTER "tag k1f412" BC5_GUARD_WATCH "tag wa412" BC5_FAULT_RECORD "tag fr412" BC5_GUARD_K1R "tag k1r412" BC5_DIRECT_RESET_LABELS_ADD; do
  grep -aqF -- "$s" "$b" || die "the binary lacks [$s]"
done
[ "$(m "$ARCH")" = 75e30335 ] || die "the shared archive changed"
[ "$(m "$K/src/libs/bc5LleAgc.cpp")" = 8126c0aa ] || die "the shared tree's unit changed"
for s in BC5_GUARD_K1R_REPLACE BC5_GUARD_K1R_PROBE BC5_GUARD_K1R_COVERS_VISIBLE BC5_GUARD_K1R_COVER_WRITTEN BC5_GUARD_K1R_WRITTEN_SCAN_MS; do grep -aqF -- "$s" "$b" && die "the binary still holds [$s]"; done
mkdir -p "$X/bin-e" || die "mkdir bin-e"
cp -p "$b" "$X/bin-e/kyty_emulator.new-$$" && mv -fT "$X/bin-e/kyty_emulator.new-$$" "$X/bin-e/kyty_emulator" || die "cannot put the binary beside"
distrobox enter ubuntu -- ldd "$X/bin-e/kyty_emulator" < /dev/null 2> /dev/null | grep -q "not found" && die "the copy in bin-e lacks a library"
printf '%s  bin-e/kyty_emulator\n' "$(md5sum < "$X/bin-e/kyty_emulator" | cut -d' ' -f1)" > "$X/built-e.md5" || die "built-e.md5"
echo "binary beside $(m "$X/bin-e/kyty_emulator") (bin-e); the shared builds, backend and archive only read"
echo "$(date '+%F %T') built: g412ze"
