#!/bin/bash
# SPDX-License-Identifier: GPL-2.0
# BC5 exp 0438 (tag bake438b): q438/test_q438.sh's identity, random and section 5 (inflight, rings; Q438_ONLY=inflight)
# for the GATE-ONLY unit of mkbake438b.py, which test_q438.sh cannot build (it needs a q438 block for Q438_NEW and a
# labelmap block for the gate's pieces). The same cuts as test_q438.sh's cutunit (plus the unit's tag ng438w block), the
# same test_q438.cpp (a copy made by gatecpp438b.py: four #if lines), built old (the shared unit 2e6168de) and new.
# The switches: unset = ON in the bake; "0" = off. Every run is one foreground command; the fixed lists stop at the first
# failure (set -e).
#   bash test_gate438b.sh NEW_UNIT [OLD_UNIT]
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd); exp=$(cd "$here/.." && pwd); unit=$1; base=${2:-$exp/r438o/r438o.cpp}; out=$(mktemp -d)
py=${PYTHON:-python}
w() { if command -v cygpath > /dev/null; then cygpath -w "$1"; else echo "$1"; fi; }
cutunit() { # cutunit UNIT DIR GATE(0|1)
	local u=$1 d=$2 a b; mkdir -p "$d"
	lineof() { grep -n -m1 -F -- "$1" "$u" | cut -d: -f1; }
	endf() { awk -v s="$1" 'NR > s && /^}/ {print NR; exit}' "$u"; }
	piece() { sed -n "${1},${2}p" "$u" | tr -d '\r' > "$d/$3"; }
	a=$(lineof 'kR438Early = 1ull << 63u'); b=$(lineof 'static std::atomic<uint64_t> g_r438_slices'); piece "$a" "$b" q_state.inc
	a=$(lineof 'static thread_local bool t_wait_given_up = false;'); b=$(lineof '// Experiment 0055: the label writes with immediate data'); piece "$a" "$((b - 1))" q_chain.inc
	a=$(lineof 'struct PendingLabelWrite {'); b=$(lineof 'static std::condition_variable             g_plw_cv;'); piece "$a" "$b" q_plw.inc
	a=$(lineof 'static void register_label_writes(const uint32_t* ib'); piece "$a" "$(endf "$a")" q_reg.inc
	a=$(lineof 'static bool ring_will_satisfy(const uint32_t* p, bool is64, int ring) {'); piece "$a" "$(endf "$a")" q_rws.inc
	if [ "$3" = 1 ]; then
		a=$(lineof '// ---- BC5 experiment 0438 (tag q438ng)'); b=$(lineof '// ---- end of exp 0438 (tag q438ng)'); piece "$a" "$b" q_ng.inc
		a=$(lineof '// ---- BC5 experiment 0438 (tag ng438w)'); b=$(lineof '// ---- end of exp 0438 (tag ng438w)'); piece "$a" "$b" q_w.inc
	fi
	a=$(lineof 'namespace ho430 {'); b=$(lineof '} // namespace ho430'); piece "$a" "$b" q_ho.inc
	"$py" -I "$(w "$here/gatecpp438b.py")" "$(w "$exp/q438/test_q438.cpp")" "$(w "$d/test_q438.cpp")"
}
cxx=${CXX:-g++}
[ -z "${CXX:-}" ] && [ -x "/c/Program Files/Microsoft Visual Studio/18/Community/VC/Tools/Llvm/x64/bin/clang++.exe" ] && cxx="/c/Program Files/Microsoft Visual Studio/18/Community/VC/Tools/Llvm/x64/bin/clang++.exe"
build() { # build DIR EXE FLAGS...
	local d=$1 e=$2; shift 2
	(cd "$d" && "$cxx" -std=c++20 -O1 -Wall -Wextra -Werror -Wno-unused-function -Wno-unused-variable -Wno-unused-parameter -D_CRT_SECURE_NO_WARNINGS -DQ438_ORIG "$@" -o "$e" test_q438.cpp)
}
plant() { # plant DIR FILE OLD NEW
	"$py" -I -c 'import sys; p,o,n=sys.argv[1:4]; s=open(p,"rb").read().decode(); assert s.count(o)==1, o; open(p,"wb").write(s.replace(o,n).encode())' "$(w "$1/$2")" "$3" "$4"
}
echo "== md5: $(md5sum < "$unit" | cut -c1-32) gate-only unit; $(md5sum < "$base" | cut -c1-32) shared unit; test_q438.cpp $(md5sum < "$exp/q438/test_q438.cpp" | cut -c1-8)"
cutunit "$unit" "$out/new" 1; cutunit "$base" "$out/old" 0
echo "== 1. the cut pieces: lines removed from the shared unit's (must be 0), lines inserted"
for f in q_state.inc q_chain.inc q_plw.inc q_reg.inc q_rws.inc q_ho.inc; do
	rm_n=$(diff "$out/old/$f" "$out/new/$f" | grep -c '^<' || true); add_n=$(diff "$out/old/$f" "$out/new/$f" | grep -c '^>' || true)
	echo "   $f: removed $rm_n, inserted $add_n"
	[ "$rm_n" = 0 ] || { echo "FAIL: $f lost lines"; diff "$out/old/$f" "$out/new/$f" | grep '^<' | head -5; exit 1; }
done
build "$out/old" tq.exe; build "$out/new" tq.exe -DQ438_X -DQ438_GATE
export BC5_DIRECT_CHAIN=2
off() { BC5_0438_INFLIGHT_NG=0 BC5_0438_OPEN_NG=0 "$@"; }
dflt() { env -u BC5_0438_INFLIGHT_NG -u BC5_0438_OPEN_NG "$@"; }
unset BC5_0438_SUBMITQ BC5_0438_INFLIGHT_NG BC5_0438_OPEN_NG
echo "== 2. identity: the shared unit; the gate unit with both switches 0 and with both unset (on)"
"$out/old/tq.exe" identity > "$out/id-old.txt"
off "$out/new/tq.exe" identity > "$out/id-0.txt"
dflt "$out/new/tq.exe" identity > "$out/id-on.txt"
for f in id-0 id-on; do
	if diff <(tail -n +2 "$out/id-old.txt") <(tail -n +2 "$out/$f.txt") > /dev/null; then echo "   $f = the shared unit ($(wc -l < "$out/$f.txt") lines)"; else echo "FAIL: $f differs"; diff "$out/id-old.txt" "$out/$f.txt" | head; exit 1; fi
done
echo "== 3. random (owners, the watchdog, flush_all): shared unit, gate unit 0, gate unit on"
"$out/old/tq.exe" random | tail -2 | sed 's/^/   old: /'
off "$out/new/tq.exe" random | tail -2 | sed 's/^/   0:   /'
dflt "$out/new/tq.exe" random | tail -2 | sed 's/^/   on:  /'
echo "== 4. inflight (test_q438.sh section 5)"
echo "   shared unit:"; "$out/old/tq.exe" inflight | sed 's/^/      /'
echo "   gate unit, both 0:"; off "$out/new/tq.exe" inflight > "$out/if-0.txt"; sed 's/^/      /' "$out/if-0.txt"
grep -q 'THE HAZARD' "$out/if-0.txt" || { echo "FAIL: with both 0 the hazard of the shared unit is not shown"; exit 1; }
echo "   gate unit, unset (on):"; dflt "$out/new/tq.exe" inflight > "$out/if-on.txt"; sed 's/^/      /' "$out/if-on.txt"
grep -q 'the gate with the writer in its submit_now: HELD' "$out/if-on.txt" || { echo "FAIL: the default did not hold the acb"; exit 1; }
echo "== 5. rings"
echo "   shared unit:"; "$out/old/tq.exe" rings | grep '^rings\|stuck' | sed 's/^/      /'
echo "   gate unit, both 0:"; off "$out/new/tq.exe" rings > "$out/rg-0.txt"; grep '^rings\|stuck' "$out/rg-0.txt" | sed 's/^/      /'
grep -q 'THE TWO-RING HANG' "$out/rg-0.txt" || { echo "FAIL: with both 0 the shared unit's hang is not shown"; exit 1; }
echo "   gate unit, unset (on), by D's state (no queue: flight, open, real) x the split; then INFLIGHT_NG alone at open:"
for c in flight:0 flight:1 open:0 open:1 real:0 real:1; do
	st=${c%%:*}; sp=${c##*:}; rc=0
	dflt env Q438_RINGS_STATE=$st Q438_RINGS_SPLIT=$sp "$out/new/tq.exe" rings > "$out/rg-$st-$sp.txt" || rc=$?
	grep '^rings, D\|^rings:' "$out/rg-$st-$sp.txt" | sed 's/^/      /'
	[ "$rc" = 0 ] || { echo "FAIL: rings $st split $sp with the defaults (rc $rc)"; grep '^FAIL' "$out/rg-$st-$sp.txt"; exit 1; }
done
BC5_0438_OPEN_NG=0 env -u BC5_0438_INFLIGHT_NG Q438_RINGS_STATE=open "$out/new/tq.exe" rings | grep '^rings, D\|^rings:' | sed 's/^/      OPEN_NG=0: /'
echo "== 6. planted bugs in the gate unit's q_ng.inc (each must FAIL with the defaults)"
d="$out/p-inflight-off"; cp -r "$out/new" "$d"; rm -f "$d/tq.exe"; plant "$d" q_ng.inc $'\t\tunready = in;' $'\t\tunready = false;'; build "$d" tq.exe -DQ438_X -DQ438_GATE
rc=0; dflt "$d/tq.exe" inflight > "$d/if.txt" || rc=$?; rc2=0; dflt "$d/tq.exe" rings > "$d/rg.txt" || rc2=$?
[ "$rc" != 0 ] && [ "$rc2" != 0 ] && echo "   inflight-off: inflight rc $rc, rings rc $rc2: caught" || { echo "FAIL: planted inflight-off not caught ($rc, $rc2)"; exit 1; }
d="$out/p-open-off"; cp -r "$out/new" "$d"; rm -f "$d/tq.exe"; plant "$d" q_ng.inc $'\t\tunready = in2;' $'\t\tunready = false;'; build "$d" tq.exe -DQ438_X -DQ438_GATE
rc=0; dflt env Q438_RINGS_STATE=open "$d/tq.exe" rings > "$d/rg.txt" || rc=$?
[ "$rc" != 0 ] && echo "   open-off: rings open rc $rc: caught" || { echo "FAIL: planted open-off not caught"; exit 1; }
d="$out/p-live0"; cp -r "$out/new" "$d"; rm -f "$d/tq.exe"; plant "$d" q_ng.inc 'const bool live = g_ng_live.load() != 0;' 'const bool live = false;'; build "$d" tq.exe -DQ438_X -DQ438_GATE
rc=0; dflt "$d/tq.exe" inflight > "$d/if.txt" || rc=$?
[ "$rc" != 0 ] && echo "   ngcount live=0 (the guard skips a pending writer): inflight rc $rc: caught" || { echo "FAIL: planted live0 not caught"; exit 1; }
echo "== 7. r438o/test_r438o.sh on copies (test_r438o.cpp's ng438_tick stub, there only for a labelmap unit, made unconditional:"
echo "      the gate unit's register_label_writes calls it): identity with EARLYREG unset and 0 against the shared unit, then order, trim"
r="$out/r438o"; mkdir -p "$r"; cp "$exp/r438o/test_r438o.sh" "$exp/r438o/test_r438o.cpp" "$r/"
"$py" -I -c 'import sys; p=sys.argv[1]; s=open(p,"rb").read().decode(); o="static void ng438_tick() {} // the q438ng block"; i=s.index(o); j=s.index("\n",i)+1; line=s[i:j]; assert s.count(o)==1; s=s[:i]+s[j:]; a="#include \"r_state.inc\"\n"; assert s.count(a)==1; open(p,"wb").write(s.replace(a,a+line).encode())' "$(w "$r/test_r438o.cpp")"
for v in unset 0; do
	if [ $v = unset ]; then e=(-u BC5_0438_EARLYREG); else e=(BC5_0438_EARLYREG=0); fi
	env "${e[@]}" bash "$r/test_r438o.sh" "$base" identity | tr -d '\r' > "$r/id-old-$v.txt"
	env "${e[@]}" BC5_0438_INFLIGHT_NG=0 BC5_0438_OPEN_NG=0 bash "$r/test_r438o.sh" "$unit" identity | tr -d '\r' > "$r/id-0-$v.txt"
	env -u BC5_0438_INFLIGHT_NG -u BC5_0438_OPEN_NG "${e[@]}" bash "$r/test_r438o.sh" "$unit" identity | tr -d '\r' > "$r/id-on-$v.txt"
	for f in id-0 id-on; do
		cmp -s "$r/id-old-$v.txt" "$r/$f-$v.txt" && echo "   identity EARLYREG $v, gate switches ${f#id-}: = the shared unit ($(wc -l < "$r/$f-$v.txt") lines)" || { echo "FAIL: identity EARLYREG $v ${f#id-} differs"; diff "$r/id-old-$v.txt" "$r/$f-$v.txt" | head; exit 1; }
	done
done
for m in order trim; do
	env -u BC5_0438_EARLYREG bash "$r/test_r438o.sh" "$unit" "$m" | tr -d '\r' | tail -1 | sed "s/^/   $m (gate unit, defaults): /"
done
echo "== all done: PASS"
