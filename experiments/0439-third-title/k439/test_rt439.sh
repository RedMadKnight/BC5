#!/usr/bin/env bash
# BC5 exp 0439 (tag rt439): laptop stand-in (R66) for t3s.sh T3S_ROUTE: the route block is cut out of t3s.sh and run with
# the emulator, shots, the image compare and the clock mocked. Usage: SCREENS_LIST="<what each look sees>" [CHECK_RES=quality] bash test_rt439.sh
# Cases run 2026-11-22: all screens seen (route to play), graphics never seen (stop, 3 crosses), check quality (stop, no confirm).
SP=$(mktemp -d); K=$(cd "$(dirname "$0")" && pwd); mkdir -p $SP/sh
awk '/T3S_ROUTE:-}" \]; then # exp 0439/{f=1} f{print} f && /done; exit 0/{exit}' "$K/t3s.sh" > $SP/route.sh; echo '    fi' >> $SP/route.sh
cd $SP; O=$SP/run; SH=$SP/sh; CMDF=$SP/cmd; BOUND=200; T3S_NEED_S=9; T3S_SCREEN_REFS=x; T3S_REF_DIR=x; touch alive; : > $O.keys
pgrep() { [ -f $SP/alive ]; }
pkill() { rm -f $SP/alive; echo "PKILL" >> $O.keys; }
sleep() { [ "$1" = 18 ] && echo $(( $(cat $SP/n) + 30 )) > $SP/n; :; }
shot() { touch "$SH/$1.png"; }
SCREENS=(${SCREENS_LIST}); idx=0
python3() { if [[ "$*" == *"quality"* ]]; then echo "quality 9.00; performance 1.00; raytracing 8.00; closest ${CHECK_RES:-performance}"; else i=$(cat $SP/n 2>/dev/null || echo 0); s=${SCREENS[$i]:-none}; echo $((i+1)) > $SP/n; echo "difficulty 5; experience 5; graphics 5; loading 5 closest $s"; fi; }
date() { if [ "$1" = +%s ]; then echo $((1000 + $(cat $SP/n 2>/dev/null || echo 0) * 3)); else command date "$@"; fi; }
t0=1000; T3S_ROUTE=${ROUTE:-"wait45 cross need=difficulty cross need=experience cross need=graphics right check cross play"}
( source $SP/route.sh ) ; true
cat $O.keys | sed 's/^[0-9:]* //'; echo "--- presses:"; cat $CMDF 2>/dev/null | tr '\n' ' '; echo
