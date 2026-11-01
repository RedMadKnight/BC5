#!/usr/bin/env bash
# BC5 exp 0381, re-reads: the route gate against journal lines made here, on the laptop. usage: bash test_arm.sh
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
. "$HERE/gate0381r.inc"
fail=0
check() { if eval "$2"; then echo "ok   $1"; else echo "FAIL $1"; fail=1; fi; }
RR=$T; CMD=$T/cmd; : > "$CMD"; printf 'stick l 128 0 15000\n' > "$T/walk0381r.cmd"
for f in arm0381r.sh gate0381r.inc setup0381r.sh series0381r.sh streamstop0381r.sh sample-reread.sh; do bash -n "$HERE/$f" || fail=1; done
check "no box script lets distrobox read its stdin" "! grep -h 'distrobox enter' \"\$HERE/setup0381r.sh\" \"\$HERE/arm0381r.sh\" | grep -v '< /dev/null'"
fast() { awk -v t="$1" 'BEGIN { for (i = 0; i < 90; i++) printf "frame profile: t %.3f s, 33.3 ms since the last flip; x\n", t - 3 + i * 0.033 }' > "$T/j"; }
slow() { awk -v t="$1" 'BEGIN { for (i = 0; i < 12; i++) printf "frame profile: t %.3f s, 200.0 ms since the last flip; x\n", t - 3 + i * 0.25 }' > "$T/j"; }
fast 100
read -r NT FPS3 SLOW5 <<< "$(gate "$T/j")"
check "fast screen" "[ \"\$SLOW5\" = 0 ] && awk -v f=\"\$FPS3\" 'BEGIN { exit !(f >= 25) }'"
slow 100
read -r NT FPS3 SLOW5 <<< "$(gate "$T/j")"
check "slow screen" "[ \"\$SLOW5\" = 1 ]"
RS=0; K=0; FASTN=0; PREV=0; LOADT=""; G=""; WHY=""
tick() { NOW=$1; read -r NT FPS3 SLOW5 <<< "$(gate "$T/j")"; route_step; }
fast 90; tick 90; fast 91; tick 91
check "start screen: cross after two fast polls" "[ \"\$RS\" = 1 ] && [ \"\$(cat \"\$CMD\")\" = 'press cross' ]"
for n in 92 93 94 95 96 97 98 99; do fast $n; tick $n; done
check "save list: down three times, then cross" "[ \"\$RS\" = 2 ] && [ \"\$(grep -c 'press down' \"\$CMD\")\" = 3 ]"
for n in 100 101 102 103 104 105 106 107; do fast $n; tick $n; done
check "Continue" "[ \"\$RS\" = 3 ]"
for n in 108 109 110; do slow $n; tick $n; done
check "the load is seen" "[ -n \"\$LOADT\" ] && [ -z \"\$G\" ]"
for n in 120 121 122 123; do fast $n; tick $n; done
check "gameplay starts the walk" "[ \"\$RS\" = 4 ] && [ -n \"\$G\" ] && grep -q '^stick l' \"\$CMD\""
RS=0; FASTN=0; PREV=999; WHY=""; slow 100; tick 170
check "a start screen that never runs ends the arm" "[ -n \"\$WHY\" ]"
[ "$fail" = 0 ] && echo "all passed"
exit $fail
