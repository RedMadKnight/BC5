#!/usr/bin/env bash
# BC5 exp 0412, build g412zg (2026-11-14, README section 91; mkzg0412.py from mk0412zf.sh): g412zf plus ph412
# (BC5_FAULT_POINTERS), tl412 (BC5_TIMEOUT_LAYOUT), dc412 (BC5_DISPATCH_COUNT), all default off; the binary goes to bin-g.
# g412zf was (README section 85): candidate F (exp 0419, patch d9af28ca, unit 59d17cf5)
# with exp 0412's switches for the memory wall's arms, all default off, on PRIVATE copies:
#   bd412  BC5_GUARD_BYDATA_NAMES (mkbd0412.py): a named eager heap is imported by data, not whole
#   wc412  BC5_GUARD_WRITERS=2 (mkbd0412.py): the writers catcher's CPU/GPU split by the soft-dirty bit
#   kc412  BC5_GUARD_COVER_LOG (mkkc0412.py unit): one journal line per rebuild in which a cover gave way to data
#   ff412  the first-failure catcher's arming line (mkkc0412.py memory)
# The source is exp 0413's private tree and private backend source as candidate F left them: only READ here (their
# sums are checked against that experiment's own tree18.md5). exp 0412's private tree $P/tree is brought to that state
# by content (rsync --checksum without times, so a file whose content changed is newer than every object built from
# it), then the two files are replaced. ~/src/KytyPlus, the shared builds, the shared backend and archive are not
# touched. The binary goes beside as bin-g/kyty_emulator with built-g.md5.
# usage (on the box, no emulator running): bash mk0412zf.sh      (takes the chain's lock line when CHAIN_LOCKLINE holds)
set -u
ulimit -c 0
export LC_ALL=C LANGUAGE=C
W=$HOME/bc5-work; X=$W/exp0412; P=$X/p; KIT=$X/kit-zg; LOCK=$W/BOX-LOCK; IP=$W/exp0413/p
m() { md5sum < "$1" 2> /dev/null | cut -c1-8; }
die() { echo "STOP: $*"; exit 1; }
pgrep '^kyty_emulator' > /dev/null && die "an emulator runs"
(cd "$KIT" && sha256sum -c --quiet kit.sha256) || die "the kit is not what was sent"
[ "$(m "$IP/tree/src/libs/bc5LleAgc.cpp")" = 59d17cf5 ] && [ "$(m "$IP/tree/src/kernel/memory.cpp")" = f51c803e ] || die "exp 0413's private tree is not candidate F (59d17cf5, f51c803e)"
bad=0
while read -r sum f; do [ "$(md5sum < "$IP/tree/$f" | cut -d' ' -f1)" = "$sum" ] || { echo "differs: $f"; bad=$((bad + 1)); }; done < "$IP/kit/tree18.md5"
[ "$bad" = 0 ] || die "$bad files of exp 0413's private tree are not candidate F's (tree18.md5)"
[ "$(m "$IP/backend-src/include/bc5/direct.hpp")" = e96e5c73 ] && [ "$(m "$IP/backend-src/src/direct.cpp")" = 28100ce5 ] || die "exp 0413's private backend source is not e96e5c73/28100ce5"
[ -d "$P/tree/.git" ] && [ -f "$P/build-normal/build.ninja" ] || die "no private tree or build directory at $P"
INHERIT=0
LINE="guard exp 0412 | build g412zg (g412zf + ph412 + tl412 + dc412, private copies; CPU only), token $$"
if [ -n "${CHAIN_LOCKLINE:-}" ] && [ -f "$LOCK" ] && [ ! -L "$LOCK" ] && [ "$(cat "$LOCK")" = "$CHAIN_LOCKLINE" ]; then INHERIT=1
else
  [ -e "$LOCK" ] || touch "$LOCK"
  [ -f "$LOCK" ] && [ ! -L "$LOCK" ] && [ ! -s "$LOCK" ] || die "the box is locked: $(cat "$LOCK")"
  tl=$LOCK.0412-$$.new; al=$LOCK.0412-$$.aside
  printf '%s\n' "$LINE" > "$tl" && mv -T "$LOCK" "$al" && ln "$tl" "$LOCK" || { [ -e "$LOCK" ] || mv -T "$al" "$LOCK"; rm -f "$tl"; die "the claim failed"; }
  if [ -s "$al" ]; then mv -fT "$al" "$LOCK"; rm -f "$tl"; die "a foreign line arrived during the claim"; fi
  rm -f "$al" "$tl"
  printf '%s\n' "guard exp 0412 | claimed: build g412zg | $(date '+%F %T')" >> "$W/BOX-QUEUE"
fi
release() {
  [ "$INHERIT" = 1 ] && return 0
  if grep -qxF -- "$LINE" "$LOCK" 2> /dev/null; then grep -vxF -- "$LINE" "$LOCK" > "$LOCK.0412-rel"; mv -fT "$LOCK.0412-rel" "$LOCK"; fi
  printf '%s\n' "guard exp 0412 | released: build g412zg | $(date '+%F %T')" >> "$W/BOX-QUEUE"
}
trap release EXIT
pgrep '^kyty_emulator' > /dev/null && die "an emulator started during the claim"
R=$X/raw-zg; mkdir -p "$R" || die mkdir
echo "$(date '+%F %T') start"
for t in bd0412 wc0412 kc0412 ww0412 k1r0412 ph0412 dw0412; do
  distrobox enter ubuntu -- env LC_ALL=C g++ -std=c++20 -O1 -Wall -Wextra -Werror -pthread -I "$KIT" "$KIT/$t.cpp" -o "$R/$t" < /dev/null > "$R/$t-build.out" 2>&1 ||
      die "the CPU test $t does not build: $(grep -m2 error "$R/$t-build.out" | cut -c1-160 | tr '\n' ' ')"
  distrobox enter ubuntu -- "$R/$t" "$R" < /dev/null > "$R/$t.out" 2>&1 || die "the CPU test $t failed: $(grep -m2 FAIL "$R/$t.out" | cut -c1-160 | tr '\n' ' ')"
  grep -q "^$t: \([0-9]*\) of \1; end\$" "$R/$t.out" || die "no end marker from the CPU test $t"
  echo "cpu test: $(tail -1 "$R/$t.out")"
done
step() { # <script> <mode or -> <in> <out> <sum>
  if [ "$2" = - ]; then python3 -I "$KIT/$1" "$3" "$4" > "$R/$1-$5.out" 2>&1; else python3 -I "$KIT/$1" "$2" "$3" "$4" > "$R/$1-$5.out" 2>&1; fi || die "$1: $(tail -1 "$R/$1-$5.out")"
  [ "$(m "$4")" = "$5" ] || die "the file after $1 is $(m "$4"), not $5"
}
rm -f "$P"/f-u[1234].cpp "$P"/f-memory.cpp
step mkbd0412.py - "$IP/tree/src/libs/bc5LleAgc.cpp" "$P/f-u1.cpp" 8f07ccf6
step mkkc0412.py unit "$P/f-u1.cpp" "$P/f-u2.cpp" 7af3f752
step mkph0412.py - "$P/f-u2.cpp" "$P/f-u3.cpp" 4a8d5211
step mkdw0412.py - "$P/f-u3.cpp" "$P/f-u4.cpp" a53e98b7
step mkkc0412.py memory "$IP/tree/src/kernel/memory.cpp" "$P/f-memory.cpp" afc69dfe
echo "$(date +%T) the private tree is brought to candidate F's state (by content)"
rsync -rlpgoD --checksum --delete --exclude=.git "$IP/tree/" "$P/tree/" || die "rsync of exp 0413's private tree failed"
[ -z "$(diff -rq --exclude=.git "$IP/tree" "$P/tree" | head -3)" ] || die "the private tree differs from candidate F's after rsync: $(diff -rq --exclude=.git "$IP/tree" "$P/tree" | head -3 | tr '\n' ' ')"
cp "$P/f-u4.cpp" "$P/tree/src/libs/bc5LleAgc.cpp" && cp "$P/f-memory.cpp" "$P/tree/src/kernel/memory.cpp" || die "cannot put the two files into the private tree"
[ "$(diff -rq --exclude=.git "$IP/tree" "$P/tree" | grep -c .)" = 2 ] || die "the private tree differs from candidate F's by more than the two files"
PB=$P/backend-src; BB=$P/backend-build
rm -rf "$PB" "$BB" && cp -a "$IP/backend-src" "$PB" || die "cannot copy the backend source"
[ -z "$(diff -rq "$IP/backend-src" "$PB" | head -1)" ] || die "the private backend source is not exp 0413's"
echo "== $(date +%T) backend"
distrobox enter ubuntu -- cmake -S "$PB" -B "$BB" -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_C_COMPILER=clang -DCMAKE_CXX_COMPILER=clang++ \
    -DBC5_WITH_AMDGPU=ON -DBC5_BUILD_TESTS=OFF < /dev/null > "$BB.configure.log" 2>&1 || die "backend configure: $(tail -3 "$BB.configure.log" | tr '\n' ' ' | cut -c1-300)"
distrobox enter ubuntu -- sh -c "cd '$BB' && nice -n 19 ninja" < /dev/null > "$BB.build.log" 2>&1 || { grep -m6 -E "error:" "$BB.build.log" | cut -c1-240; die "the backend build failed"; }
[ -f "$BB/libbc5_backend.a" ] || die "no private backend archive"
echo "private backend archive $(m "$BB/libbc5_backend.a") (exp 0413's private one: $(m "$IP/backend-build/libbc5_backend.a"))"
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
echo "normal: $(md5sum < "$b" | cut -d' ' -f1), warnings $(grep -c 'warning:' "$B.build.log"), compiled $(grep -c '^\[' "$B.build.log") steps"
for s in BC5_FAULT_POINTERS "tag ph412" BC5_TIMEOUT_LAYOUT "tag tl412" BC5_DISPATCH_COUNT "tag dc412" BC5_GUARD_COVER_LOG "tag kc412" BC5_GUARD_BYDATA_NAMES "tag bd412" "tag wc412" BC5_GUARD_WRITERS "KYTY_BC5_MEM_FIRSTFAIL on, armed" KYTY_BC5_TRAP_LOG BC5_DIRECT_START_STATE_SKIP \
         BC5_GUARD_K1_FILTER BC5_FAULT_RECORD BC5_GUARD_K1R KYTY_BC5_SAVEDATA_TRANSFER_FIX KYTY_BC5_TITLE_DEFAULTS; do
  grep -aqF -- "$s" "$b" || die "the binary lacks [$s]"
done
for s in BC5_GUARD_K1R_PROBE BC5_GUARD_K1R_REPLACE; do grep -aqF -- "$s" "$b" && die "the binary still holds [$s]"; done
[ "$(m "$IP/tree/src/libs/bc5LleAgc.cpp")" = 59d17cf5 ] && [ "$(m "$IP/tree/src/kernel/memory.cpp")" = f51c803e ] || die "exp 0413's private tree changed"
mkdir -p "$X/bin-g" || die "mkdir bin-g"
cp -p "$b" "$X/bin-g/kyty_emulator.new-$$" && mv -fT "$X/bin-g/kyty_emulator.new-$$" "$X/bin-g/kyty_emulator" || die "cannot put the binary beside"
distrobox enter ubuntu -- ldd "$X/bin-g/kyty_emulator" < /dev/null 2> /dev/null | grep -q "not found" && die "the copy in bin-g lacks a library"
printf '%s  bin-g/kyty_emulator\n' "$(md5sum < "$X/bin-g/kyty_emulator" | cut -d' ' -f1)" > "$X/built-g.md5" || die "built-g.md5"
echo "binary beside $(m "$X/bin-g/kyty_emulator") (bin-g); exp 0413's tree and backend, the shared builds and archive only read"
echo "$(date '+%F %T') built: g412zg"
