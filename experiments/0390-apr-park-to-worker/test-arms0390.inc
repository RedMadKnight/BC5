if t arms; then
  reset; go Q1N on; want "arm Q: no crash through the cap" 0 "CLASS NO_CRASH fix on crash none reached 1"
  grep -q 'KYTY_BC5_APR_PARK_TO_WORKER=1' "$R/Q1N-start.txt" && ok "arm Q: the switch is in the start file" || bad "arm Q: start file"
  grep -q 'APR wait thread: absent' "$R/Q1N-check.txt" && ok "arm Q: the thread list says absent" || bad "arm Q: thread list"
  reset; go P2N on; want "arm P: no crash through the cap" 0 "CLASS NO_CRASH fix on crash none reached 1"
  grep -q 'KYTY_BC5_APR_PARK_TO_WORKER' "$R/P2N-start.txt" && bad "arm P: the switch is set" || ok "arm P: no switch"
  reset; echo 'KYTY_BC5_APR_PARK_TO_WORKER=1' > "$F/env-add"; go P3N on; want "arm P with the switch in the environment: invalid" 0 "CLASS INVALID"; rm -f "$F/env-add"
  reset; echo 'KYTY_BC5_APR_PARK_TO_WORKER=0' > "$F/env-add"; go Q3N on; want "arm Q with the switch at 0: invalid" 0 "CLASS INVALID"; rm -f "$F/env-add"
  reset; printf '      1 bc5-apr-q1\n      1 bc5-apr-wait\n' > "$F/apr-threads"; go P4N on; want "the wait thread ran: the run still classes" 0 "CLASS NO_CRASH"
  grep -q 'APR wait thread: present' "$R/P4N-check.txt" && ok "the wait thread ran: reported" || bad "wait thread: not reported"
  reset; : > "$F/apr-threads"; go P5N on; want "no thread list: the run still classes" 0 "CLASS NO_CRASH"
  grep -q 'APR wait thread: not read' "$R/P5N-check.txt" && ok "no thread list: not read, not absent" || bad "thread list: reported as a zero"
  reset; go P6N on; touch -d '2020-01-01 00:00:00' "$R/P6N-apr-threads.txt"; (cd "$RUND" && python check0390.py run P6N on 0 "$(cygpath -m "$R")" "$W/d19/raw/stubs-baseline.txt") > "$F/stale" 2>&1
  grep -q 'APR wait thread: not read' "$F/stale" && ok "a thread list older than the run: not read" || bad "stale thread list: $(grep 'APR wait' "$F/stale")"
fi
if t rule; then
  ru() { printf '%s\n' "$@" > "$F/rows"; python "$RUND/check0390.py" rule "$F/rows"; }
  A="P1 on NO_CRASH none"; B="Q1 on NO_CRASH none"
  case "$(ru "$A" "$B")" in *"RULE PASS"*) ok "rule: both arms clean" ;; *) bad "rule pass" ;; esac
  case "$(ru "$A" "Q1 on CRASH_OTHER other")" in *"RULE FAIL Q1"*) ok "rule: a crash in one arm" ;; *) bad "rule fail" ;; esac
  case "$(ru "$A" "Q1 on NOT_ROUTED none")" in *"RULE FAIL Q1"*) ok "rule: a run that did not reach the fight is no pass" ;; *) bad "rule not routed" ;; esac
  case "$(ru "$A")" in *"RULE OPEN no run of arm Q"*) ok "rule: one arm proves nothing" ;; *) bad "rule open" ;; esac
fi
if t series; then
  cat > "$F/go-stub.sh" <<EOF
#!/usr/bin/env bash
echo "\$1 \$2" >> "$F/go-calls"
c=\$(cat "$F/go-plan-\$1" 2> /dev/null); [ -n "\$c" ] || c="NO_CRASH none"
echo "RESULT \$1 runner 0 check 0 CLASS \${c% *} fix \$2 crash \${c#* } reached 1"
[ ! -e "$F/go-rc-\$1" ] || exit "\$(cat "$F/go-rc-\$1")"
EOF
  sed "s#^GO=.*#GO=$F/go-stub.sh#" "$RUND/series0390.sh" > "$F/series.sh"; sed -i 's#HERE=$(cd "$(dirname "$0")" \&\& pwd)#HERE='"$RUND"'#' "$F/series.sh"
  rm -f "$F"/go-calls "$F"/go-plan-* "$F"/go-rc-*
  o=$(bash "$F/series.sh" 2>&1); rc=$?; [ "$rc" = 0 ] && [ "$(tr '\n' ' ' < "$F/go-calls")" = "P1 on Q1 on " ] && case "$o" in *"RULE PASS"*) true ;; *) false ;; esac && ok "series: one run of each arm, the rule" || bad "series: rc $rc $(echo "$o" | tail -2 | cut -c1-160)"
  rm -f "$F/go-calls"; echo "CRASH_TARGET target" > "$F/go-plan-P1"; o=$(bash "$F/series.sh" 2>&1); rc=$?; [ "$rc" = 1 ] && [ "$(grep -c . "$F/go-calls")" = 1 ] && ok "series: a crash at the site stops it" || bad "series target: rc $rc"
  rm -f "$F/go-calls" "$F/go-plan-P1"; echo "NOT_ROUTED none" > "$F/go-plan-P1"; o=$(bash "$F/series.sh" 2>&1); [ "$(grep -c '^P1R' "$F/go-calls")" = 1 ] && [ "$(grep -c . "$F/go-calls")" = 3 ] && case "$o" in *"RULE PASS"*) true ;; *) false ;; esac && ok "series: one replacement" || bad "series replacement: $(tr '\n' ' ' < "$F/go-calls")"
  rm -f "$F/go-calls"; echo "NOT_ROUTED none" > "$F/go-plan-Q1"; o=$(bash "$F/series.sh" 2>&1); [ "$(grep -c 'R ' "$F/go-calls")" = 1 ] && ok "series: only one replacement in all" || bad "series two: $(tr '\n' ' ' < "$F/go-calls")"
  rm -f "$F/go-calls" "$F"/go-plan-*; echo 2 > "$F/go-rc-P1"; o=$(bash "$F/series.sh" 2>&1); rc=$?; [ "$rc" = 1 ] && [ "$(grep -c . "$F/go-calls")" = 1 ] && ok "series: a stopped run ends it, no retry" || bad "series stop: rc $rc"
  rm -f "$F/go-calls" "$F"/go-rc-*; echo "KERNEL none" > "$F/go-plan-P1"; o=$(bash "$F/series.sh" 2>&1); rc=$?; [ "$rc" = 1 ] && ok "series: a kernel class ends it" || bad "series kernel: rc $rc"
fi
