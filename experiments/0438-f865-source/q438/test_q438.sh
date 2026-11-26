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
	a=$(lineof 'struct PendingLabelWrite {'); b=$(lineof 'static std::condition_variable             g_plw_cv;')
	grep -q -F -- '// ---- end of exp 0438 (q438) g_plw trim' "$u" && b=$(lineof '// ---- end of exp 0438 (q438) g_plw trim')
	piece "$a" "$b" q_plw.inc
	a=$(lineof 'static void register_label_writes(const uint32_t* ib'); piece "$a" "$(endf "$a")" q_reg.inc
	a=$(lineof 'static bool ring_will_satisfy(const uint32_t* p, bool is64, int ring) {'); piece "$a" "$(endf "$a")" q_rws.inc
	if grep -q -F '// ---- BC5 experiment 0438 (tag q438)' "$u"; then
		a=$(lineof '// ---- BC5 experiment 0438 (tag q438)'); b=$(lineof '// ---- end of exp 0438 (tag q438)'); piece "$a" "$b" q_q.inc
	fi
	if grep -q -F '// ---- BC5 experiment 0438 (tag labelmap)' "$u"; then # mkq438x.py: the filter's check, acb_ready's test, ho430
		a=$(lineof 'static bool covered_sorted(const bc5::direct::MappingIndex& maps, uint64_t a, uint64_t bytes) {'); piece "$a" "$(endf "$a")" q_cov.inc
		a=$(lineof '// ---- BC5 experiment 0438 (tag labelmap)'); b=$(lineof '// ---- end of exp 0438 (tag labelmap)'); piece "$a" "$b" q_lwm.inc
		a=$(lineof '// ---- BC5 experiment 0438 (tag q438ng)'); b=$(lineof '// ---- end of exp 0438 (tag q438ng)'); piece "$a" "$b" q_ng.inc
	fi
	a=$(lineof 'namespace ho430 {'); b=$(lineof '} // namespace ho430'); piece "$a" "$b" q_ho.inc # every unit: the inflight case
	cp "$here/test_q438.cpp" "$d/"
}
cxx=${CXX:-g++}
[ -z "${CXX:-}" ] && [ -x "/c/Program Files/Microsoft Visual Studio/18/Community/VC/Tools/Llvm/x64/bin/clang++.exe" ] && cxx="/c/Program Files/Microsoft Visual Studio/18/Community/VC/Tools/Llvm/x64/bin/clang++.exe"
build() { # build DIR DEFINE EXE
	(cd "$1" && "$cxx" -std=c++20 -O1 -Wall -Wextra -Werror -Wno-unused-function -Wno-unused-variable -Wno-unused-parameter -D_CRT_SECURE_NO_WARNINGS -D"$2" $([ "${STACK438:-0}" = 1 ] && echo -DQ438_STACK) $([ "$2" = Q438_NEW ] && [ -f "$1/q_lwm.inc" ] && echo -DQ438_X) -o "$3" test_q438.cpp)
}
echo "== md5: $(md5sum "$unit" | cut -c1-32) q438 unit; $(md5sum "$bake" | cut -c1-32) bake unit"
cutunit "$unit" "$out/new"; cutunit "$bake" "$out/old"
echo "== 1. the chain block: lines removed from the bake unit's (must be 0), lines inserted"
for f in q_state.inc q_chain.inc q_plw.inc q_reg.inc q_rws.inc; do
	rm_n=$(diff "$out/old/$f" "$out/new/$f" | grep -c '^<' || true); add_n=$(diff "$out/old/$f" "$out/new/$f" | grep -c '^>' || true)
	echo "   $f: removed $rm_n, inserted $add_n"
	if [ "$rm_n" != 0 ]; then # STACK438=1 (mkstack438.py): only r438o's three lines may change in place (the trim's and the renumbering's conditions)
		bad=$(diff "$out/old/$f" "$out/new/$f" | grep '^<' | grep -vF -e 'if (!r438_on()) {' -e 'if (r438_on() && g_r438o_live != 0) {' -e 'w.seq != t_r438_own && std::any_of(' || true)
		if [ "${STACK438:-0}" = 1 ] && [ -z "$bad" ]; then echo "   $f: the $rm_n changed lines are r438o's conditions (STACK438)"; else echo "FAIL: $f lost lines"; exit 1; fi
	fi
done
build "$out/new" Q438_NEW tq.exe; build "$out/old" Q438_ORIG tq.exe
export BC5_DIRECT_CHAIN=2
inflight() { # the stale-value window without the queue (BC5_0438_SUBMITQ unset), on the input unit and the new one
	echo "== 5. inflight, BC5_0438_SUBMITQ unset"
	echo "   input unit:"; (unset BC5_0438_SUBMITQ BC5_0438_INFLIGHT_NG; "$out/old/tq.exe" inflight) | sed 's/^/   /'
	echo "   input unit, rings:"; (unset BC5_0438_SUBMITQ BC5_0438_INFLIGHT_NG; "$out/old/tq.exe" rings) | sed 's/^/   /'
	echo "   new unit, rings, BC5_0438_INFLIGHT_NG unset:"; (unset BC5_0438_SUBMITQ BC5_0438_INFLIGHT_NG; "$out/new/tq.exe" rings) | sed 's/^/   /'
	if [ -f "$out/new/q_ng.inc" ]; then echo "   new unit, rings, BC5_0438_INFLIGHT_NG=1:"; (unset BC5_0438_SUBMITQ; BC5_0438_INFLIGHT_NG=1 "$out/new/tq.exe" rings) | sed 's/^/   /'; fi
	if [ -f "$out/new/q_ng.inc" ]; then # D's state when X is decided, x the split, under INFLIGHT_NG=1 alone, then with OPEN_NG=1 (must not hang)
		echo "   rings by D's state (STATE:SUBMITQ), INFLIGHT_NG=1 alone, then + OPEN_NG=1:"
		local c rc st sq sp
		for c in flight:0 open:0 open:1 queued:1 submitnow:1 real:0 real:1; do
			st=${c%%:*}; sq=${c##*:}
			for sp in 0 1; do
				(unset BC5_0438_SUBMITQ BC5_0438_OPEN_NG; [ "$sq" = 1 ] && export BC5_0438_SUBMITQ=1; BC5_0438_INFLIGHT_NG=1 Q438_RINGS_STATE=$st Q438_RINGS_SPLIT=$sp "$out/new/tq.exe" rings) | grep '^rings' | sed 's/^/      /'
				rc=0; (unset BC5_0438_SUBMITQ; [ "$sq" = 1 ] && export BC5_0438_SUBMITQ=1; BC5_0438_INFLIGHT_NG=1 BC5_0438_OPEN_NG=1 Q438_RINGS_STATE=$st Q438_RINGS_SPLIT=$sp "$out/new/tq.exe" rings) > "$out/rings-$st-$sq-$sp.txt" || rc=$?
				grep '^rings' "$out/rings-$st-$sq-$sp.txt" | sed 's/^/      /'
				[ "$rc" = 0 ] || { echo "FAIL: rings $st SUBMITQ=$sq split=$sp with INFLIGHT_NG=1 OPEN_NG=1"; grep '^FAIL' "$out/rings-$st-$sq-$sp.txt"; exit 1; }
			done
		done
		local e="$out/p-early-dec"; cp -r "$out/new" "$e"; rm -f "$e/tq.exe" # ngcount: the slot's count falls at the take, not after the registration
		python -I -c 'import sys; p,o,n=sys.argv[1:4]; s=open(p,"rb").read().decode(); assert s.count(o)==1, o; open(p,"wb").write(s.replace(o,n).encode())' "$e/q_chain.inc" 'const bool now = !s.f10_flight.empty() || !s.f10_writes.empty();' 'const bool now = !s.f10_writes.empty();'
		build "$e" Q438_NEW tq.exe
		local r1=0 r2=0; (unset BC5_0438_SUBMITQ; BC5_0438_INFLIGHT_NG=1 BC5_0438_OPEN_NG=1 Q438_RINGS_STATE=flight "$e/tq.exe" rings) > "$e/rings.txt" || r1=$?
		(unset BC5_0438_SUBMITQ; BC5_0438_INFLIGHT_NG=1 BC5_0438_OPEN_NG=1 "$e/tq.exe" inflight) > "$e/inflight.txt" || r2=$?
		if [ "$r1" != 0 ] && [ "$r2" != 0 ]; then echo "   planted early-dec (rings flight and inflight, INFLIGHT_NG=1 OPEN_NG=1): FAIL as it must (rc $r1, $r2)"; grep -h '^FAIL\|^rings:' "$e/rings.txt" "$e/inflight.txt" | sed 's/^/      /'; else echo "FAIL: planted early-dec not caught (rc $r1, $r2)"; exit 1; fi
		local d="$out/p-open-off"; cp -r "$out/new" "$d"; rm -f "$d/tq.exe"
		python -I -c 'import sys; p,o,n=sys.argv[1:4]; s=open(p,"rb").read().decode(); assert s.count(o)==1, o; open(p,"wb").write(s.replace(o,n).encode())' "$d/q_ng.inc" $'\t\tunready = in2;' $'\t\tunready = false;'
		build "$d" Q438_NEW tq.exe
		rc=0; (unset BC5_0438_SUBMITQ; BC5_0438_INFLIGHT_NG=1 BC5_0438_OPEN_NG=1 Q438_RINGS_STATE=open "$d/tq.exe" rings) > "$d/rings.txt" || rc=$?
		if [ "$rc" != 0 ]; then echo "   planted open-off, rings open (INFLIGHT_NG=1 OPEN_NG=1): FAIL as it must (rc $rc)"; grep '^FAIL' "$d/rings.txt" | sed 's/^/      /'; else echo "FAIL: planted open-off not caught"; exit 1; fi
	fi
	echo "   new unit, BC5_0438_INFLIGHT_NG unset:"; (unset BC5_0438_SUBMITQ BC5_0438_INFLIGHT_NG; "$out/new/tq.exe" inflight) | sed 's/^/   /'
	if [ -f "$out/new/q_ng.inc" ]; then
		echo "   new unit, BC5_0438_INFLIGHT_NG=1:"; (unset BC5_0438_SUBMITQ; BC5_0438_INFLIGHT_NG=1 "$out/new/tq.exe" inflight) | sed 's/^/   /'
		local d="$out/p-inflight-off"; cp -r "$out/new" "$d"; rm -f "$d/tq.exe"
		python -I -c 'import sys; p,o,n=sys.argv[1:4]; s=open(p,"rb").read().decode(); assert s.count(o)==1, o; open(p,"wb").write(s.replace(o,n).encode())' "$d/q_ng.inc" $'\t\tunready = in;' $'\t\tunready = false;'
		build "$d" Q438_NEW tq.exe
		local rc=0; (unset BC5_0438_SUBMITQ; BC5_0438_INFLIGHT_NG=1 "$d/tq.exe" inflight) > "$d/inflight.txt" || rc=$?
		local rc3=0; (unset BC5_0438_SUBMITQ; BC5_0438_INFLIGHT_NG=1 "$d/tq.exe" rings) > "$d/rings.txt" || rc3=$?
		if [ "$rc3" != 0 ]; then echo "   planted inflight-off, rings (BC5_0438_INFLIGHT_NG=1): FAIL as it must (rc $rc3)"; grep '^FAIL\|^rings' "$d/rings.txt" | sed 's/^/      /'; else echo "FAIL: planted inflight-off not caught by rings"; exit 1; fi
		if [ "$rc" != 0 ]; then echo "   planted inflight-off (BC5_0438_INFLIGHT_NG=1): FAIL as it must (rc $rc)"; grep '^FAIL' "$d/inflight.txt" | sed 's/^/      /'; else echo "FAIL: planted inflight-off not caught"; exit 1; fi
	fi
}
shape67() { # the full set's first broken order (cq438f1): D's wait on d40 given up while acb_ready holds A1
	echo "== 6. shape67 (INFLIGHT_NG=1 OPEN_NG=1 unless shown)"
	local dly he rc
	for dly in 1 20; do for he in 0 1; do
		rc=0; (unset BC5_0438_SUBMITQ BC5_0438_HELD_EARLY; [ "$he" = 1 ] && export BC5_0438_HELD_EARLY=1; BC5_0438_INFLIGHT_NG=1 BC5_0438_OPEN_NG=1 Q438_SHAPE_DELAY_MS=$dly "$out/new/tq.exe" shape67) > "$out/sh-$dly-$he.txt" || rc=$?
		grep '^shape67\|^FAIL' "$out/sh-$dly-$he.txt" | sed 's/^/   /'; [ "$rc" = 0 ] || { echo "FAIL: shape67 delay $dly HELD_EARLY $he"; exit 1; }
	done; done
	(unset BC5_0438_SUBMITQ BC5_0438_HELD_EARLY BC5_0438_INFLIGHT_NG BC5_0438_OPEN_NG; Q438_SHAPE_DELAY_MS=20 "$out/new/tq.exe" shape67) | grep '^shape67' | sed 's/^/   /'
	local d="$out/p-held-off"; cp -r "$out/new" "$d"; rm -f "$d/tq.exe"
	python -I -c 'import sys; p,o,n=sys.argv[1:4]; s=open(p,"rb").read().decode(); assert s.count(o)==1, o; open(p,"wb").write(s.replace(o,n).encode())' "$d/q_q.inc" 'if (g_held438.count({ib, num_dwords}) != 0) return; // once per hold' 'return;'
	build "$d" Q438_NEW tq.exe
	rc=0; (unset BC5_0438_SUBMITQ; BC5_0438_HELD_EARLY=1 BC5_0438_INFLIGHT_NG=1 BC5_0438_OPEN_NG=1 Q438_SHAPE_DELAY_MS=20 "$d/tq.exe" shape67) > "$d/sh.txt" || rc=$?
	if [ "$rc" != 0 ]; then echo "   planted held-off (HELD_EARLY=1, delay 20): FAIL as it must (rc $rc)"; grep '^FAIL\|^shape67' "$d/sh.txt" | sed 's/^/      /'; else echo "FAIL: planted held-off not caught"; exit 1; fi
}
if [ "${Q438_ONLY:-}" = shape67 ]; then shape67; echo "== all done"; exit 0; fi
if [ "${Q438_ONLY:-}" = inflight ]; then inflight; echo "== all done"; exit 0; fi
if [ "${Q438_ONLY:-}" = plants ]; then skip23=1; else skip23=0; fi
if [ "$skip23" = 0 ]; then
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
export Q438_TIMER1=${Q438_TIMER1:-1} # Windows: the timer at 1 ms (test_q438.cpp), so the stub's 100-300-us sleeps are not 15.6-ms ticks
echo "== 3c. random, q438 unit, BC5_0438_SUBMITQ=1, $runs runs (misses per run)"; BC5_0438_SUBMITQ=1 "$out/new/tq.exe" random
bad=0; per=""
for i in $(seq 2 "$runs"); do
	rc=0; BC5_0438_SUBMITQ=1 "$out/new/tq.exe" random > "$out/r$i.txt" || rc=$?
	m=$(sed -n 's/.*writer not found \([0-9]*\);.*/\1/p' "$out/r$i.txt"); per="$per ${m:-?}"
	[ "$rc" = 0 ] || { bad=$((bad + 1)); grep '^FAIL' "$out/r$i.txt" | sed "s/^/   run $i: /"; }
done
echo "   runs 2..$runs misses:$per; failed runs $bad"; [ "$bad" = 0 ] || { echo "FAIL: random not clean in every run"; exit 1; }
echo "== 3d. det, BC5_0438_SUBMITQ=1"; BC5_0438_SUBMITQ=1 "$out/new/tq.exe" det
fi # Q438_ONLY=plants: sections 2 and 3 skipped
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
if [ "${STACK438:-0}" = 1 ]; then # mkstack438.py: the renumbering and the trim are r438o's
	plant no-order 'if ((r438_on() && g_r438o_live != 0) || q438_on()) {' 'if (false) {' q_reg.inc
	plant trim-drops 'if (!r438_on() && !q438_on()) {' 'if (true) {' q_plw.inc
else
	plant no-order 'if (q438_on()) { // exp 0438 (q438): queued chains' 'if (false) { // exp 0438 (q438): queued chains' q_reg.inc
	plant trim-drops 'if (gone < 4096 && (w.seq & kR438Early) == 0) {' 'if (gone < 4096) {' q_plw.inc
fi
if [ -f "$out/new/q_lwm.inc" ]; then # mkq438x.py
	plant lwm-noscan 'if (t_lwm != nullptr && (h >> 30u) == 3 && !lw_packet_mapped(' 'if (false && (h >> 30u) == 3 && !lw_packet_mapped('
	plant ng-off 'if (!unready) unready = q438_on() && q438_writer_queued(label);' '(void)0;' q_ng.inc
fi
inflight
shape67
echo "== all done"
