#!/bin/bash
# SPDX-License-Identifier: GPL-2.0
# BC5 exp 0438 (tag q438): cut the chain block, r438's state, g_plw, register_label_writes, ring_will_satisfy and the q438
# block, unchanged, from the q438 unit (and the same pieces from the bake unit), build test_q438.cpp against them and run:
#   1. the cuts of the chain block differ from the bake unit's by inserted lines only;
#   2. identity: the bake unit and the q438 unit with BC5_0438_SUBMITQ unset, =0 and =2 print the same trace;
#   3. random with the switch off (both units) and on; det with the switch on: PASS;
#   4. four planted bugs in copies of the q438 block (no early registration; LIFO instead of FIFO; the tail clears the
#      whole flight set as today; the drain does not wait): each must FAIL.
# Laptop: VS clang++.   bash test_q438.sh [q438-unit] [bake-unit]
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd); unit=${1:-$here/q438.cpp}; bake=${2:-$here/../bake438.cpp}; out=$(mktemp -d)
cutunit() { # cutunit UNIT DIR
	local u=$1 d=$2; mkdir -p "$d"
	lineof() { grep -n -m1 -F -- "$1" "$u" | cut -d: -f1; }
	endf() { awk -v s="$1" 'NR > s && /^}/ {print NR; exit}' "$u"; }
	piece() { sed -n "${1},${2}p" "$u" | tr -d '\r' > "$d/$3"; }
	local a b
	a=$(lineof 'kR438Early = 1ull << 63u'); b=$(lineof 'static std::atomic<uint64_t> g_r438_slices'); piece "$a" "$b" q_state.inc
	a=$(lineof 'static thread_local bool t_wait_given_up = false;'); b=$(lineof '// Experiment 0055: the label writes with immediate data'); piece "$a" "$((b - 1))" q_chain.inc
	a=$(lineof 'struct PendingLabelWrite {'); b=$(lineof 'static std::condition_variable             g_plw_cv;'); piece "$a" "$b" q_plw.inc
	a=$(lineof 'static void register_label_writes(const uint32_t* ib'); piece "$a" "$(endf "$a")" q_reg.inc
	a=$(lineof 'static bool ring_will_satisfy(const uint32_t* p, bool is64, int ring) {'); piece "$a" "$(endf "$a")" q_rws.inc
	if grep -q -F '// ---- BC5 experiment 0438 (tag q438)' "$u"; then
		a=$(lineof '// ---- BC5 experiment 0438 (tag q438)'); b=$(lineof '// ---- end of exp 0438 (tag q438)'); piece "$a" "$b" q_q.inc
	fi
	cp "$here/test_q438.cpp" "$d/"
}
cxx=${CXX:-g++}
[ -z "${CXX:-}" ] && [ -x "/c/Program Files/Microsoft Visual Studio/18/Community/VC/Tools/Llvm/x64/bin/clang++.exe" ] && cxx="/c/Program Files/Microsoft Visual Studio/18/Community/VC/Tools/Llvm/x64/bin/clang++.exe"
build() { # build DIR DEFINE EXE
	(cd "$1" && "$cxx" -std=c++20 -O1 -Wall -Wextra -Werror -Wno-unused-function -Wno-unused-variable -Wno-unused-parameter -D_CRT_SECURE_NO_WARNINGS -D"$2" -o "$3" test_q438.cpp)
}
echo "== md5: $(md5sum "$unit" | cut -c1-32) q438 unit; $(md5sum "$bake" | cut -c1-32) bake unit"
cutunit "$unit" "$out/new"; cutunit "$bake" "$out/old"
echo "== 1. the chain block: lines removed from the bake unit's (must be 0), lines inserted"
for f in q_state.inc q_chain.inc q_plw.inc q_reg.inc q_rws.inc; do
	rm_n=$(diff "$out/old/$f" "$out/new/$f" | grep -c '^<' || true); add_n=$(diff "$out/old/$f" "$out/new/$f" | grep -c '^>' || true)
	echo "   $f: removed $rm_n, inserted $add_n"; [ "$rm_n" = 0 ] || { echo "FAIL: $f lost lines"; exit 1; }
done
build "$out/new" Q438_NEW tq.exe; build "$out/old" Q438_ORIG tq.exe
export BC5_DIRECT_CHAIN=2
echo "== 2. identity"
(unset BC5_0438_SUBMITQ; "$out/old/tq.exe" identity) > "$out/id-bake.txt"
(unset BC5_0438_SUBMITQ; "$out/new/tq.exe" identity) > "$out/id-unset.txt"
BC5_0438_SUBMITQ=0 "$out/new/tq.exe" identity > "$out/id-0.txt"
BC5_0438_SUBMITQ=2 "$out/new/tq.exe" identity > "$out/id-2.txt"
for f in id-unset id-0 id-2; do
	if diff <(tail -n +2 "$out/id-bake.txt") <(tail -n +2 "$out/$f.txt") > /dev/null; then echo "   $f = bake ($(wc -l < "$out/$f.txt") lines)"; else echo "FAIL: $f differs from the bake unit"; diff "$out/id-bake.txt" "$out/$f.txt" || true; exit 1; fi
done
sed 's/^/   | /' "$out/id-bake.txt"
echo "== 3a. random, bake unit";            (unset BC5_0438_SUBMITQ; "$out/old/tq.exe" random)
echo "== 3b. random, q438 unit, switch unset"; (unset BC5_0438_SUBMITQ; "$out/new/tq.exe" random)
runs=${Q438_RUNS:-30}
echo "== 3c. random, q438 unit, BC5_0438_SUBMITQ=1, $runs runs (misses per run)"; BC5_0438_SUBMITQ=1 "$out/new/tq.exe" random
bad=0; per=""
for i in $(seq 2 "$runs"); do
	rc=0; BC5_0438_SUBMITQ=1 "$out/new/tq.exe" random > "$out/r$i.txt" || rc=$?
	m=$(sed -n 's/.*writer not found \([0-9]*\);.*/\1/p' "$out/r$i.txt"); per="$per ${m:-?}"
	[ "$rc" = 0 ] || { bad=$((bad + 1)); grep '^FAIL' "$out/r$i.txt" | sed "s/^/   run $i: /"; }
done
echo "   runs 2..$runs misses:$per; failed runs $bad"; [ "$bad" = 0 ] || { echo "FAIL: random not clean in every run"; exit 1; }
echo "== 3d. det, BC5_0438_SUBMITQ=1"; BC5_0438_SUBMITQ=1 "$out/new/tq.exe" det
echo "== 4. planted bugs (each must FAIL)"
plant() { # plant NAME OLD NEW [FILE]
	local d="$out/p-$1"; cp -r "$out/new" "$d"; rm -f "$d/tq.exe"
	python -I -c 'import sys; p,o,n=sys.argv[1:4]; s=open(p,"rb").read().decode(); assert s.count(o)==1, o; open(p,"wb").write(s.replace(o,n).encode())' "$d/${4:-q_q.inc}" "$2" "$3"
	build "$d" Q438_NEW tq.exe
	local rc=0; BC5_0438_SUBMITQ=1 "$d/tq.exe" det > "$d/det.txt" || rc=$?; local rc2=0; BC5_0438_SUBMITQ=1 "$d/tq.exe" random > "$d/random.txt" || rc2=$?
	local f1 f2; f1=$(grep -c '^FAIL' "$d/det.txt" || true); f2=$(grep -c '^FAIL' "$d/random.txt" || true)
	if [ "$rc" != 0 ] && [ "$rc2" != 0 ]; then echo "   $1: det FAIL ($f1 lines, rc $rc), random FAIL ($f2 lines, rc $rc2): caught"
	elif [ "$rc" != 0 ] || [ "$rc2" != 0 ]; then echo "   $1: det rc $rc ($f1 FAIL lines), random rc $rc2 ($f2 FAIL lines): caught"
	else echo "FAIL: planted bug $1 not caught"; exit 1; fi
	grep -m3 '^FAIL' "$d/det.txt" "$d/random.txt" | sed 's/^/      /' || true
}
plant no-early 'e.early = q438_early_begin(e.c);' 'e.early = 0;'
plant lifo 'e = std::move(s.q.front());
				s.q.pop_front();' 'e = std::move(s.q.back());
				s.q.pop_back();'
plant flight-clear 'q438_flight_locked(s); // exp 0430 F10: its writes are registered now' 's.f10_flight.clear(); s.q_sets.clear();'
plant no-drain 'if (why == 5 || why == 8) q438_wait_done(s);' '(void)why;'
plant no-order 'if (q438_on()) { // exp 0438 (q438): queued chains' 'if (false) { // exp 0438 (q438): queued chains' q_reg.inc
echo "== all done"
