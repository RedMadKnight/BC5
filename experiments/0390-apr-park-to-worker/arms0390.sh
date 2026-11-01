#!/usr/bin/env bash
# BC5 experiment 0390: the harness arms, laptop only. Every arm runs N times; a run passes on exit code 0 with no
# AddressSanitizer report. usage: arms0390.sh <dir of b-base/h.exe and b-new/h.exe> <output file> [N]
B=$1
OUT=$2
N=${3:-10}
export PATH="/c/Program Files/Microsoft Visual Studio/18/Community/VC/Tools/Llvm/x64/lib/clang/22/lib/windows:$PATH"
: > "$OUT"

arm() { # name exe scenario env...
  local name=$1 exe=$2 scenario=$3
  shift 3
  local pass=0 asan=0 hang=0 other=0 last=""
  for i in $(seq 1 "$N"); do
    local log
    log=$(env "$@" timeout 40 "$B/$exe/h.exe" "$scenario" 2>&1)
    local rc=$?
    local line
    line=$(printf '%s\n' "$log" | grep -m1 "^$scenario:")
    local err
    err=$(printf '%s\n' "$log" | grep -m1 "ERROR: AddressSanitizer" | sed 's/^.*ERROR: AddressSanitizer: //' | cut -c1-60)
    if [ -n "$err" ]; then
      asan=$((asan + 1))
      echo "$name #$i rc=$rc ASAN $err" >> "$OUT"
    elif [ "$rc" -eq 124 ]; then
      hang=$((hang + 1))
      echo "$name #$i rc=$rc TIMEOUT" >> "$OUT"
    elif [ "$rc" -eq 0 ]; then
      pass=$((pass + 1))
      echo "$name #$i rc=0 $line" >> "$OUT"
    else
      other=$((other + 1))
      echo "$name #$i rc=$rc $line" >> "$OUT"
    fi
    [ -n "$line" ] && last=$line
  done
  printf '%-12s pass %2d/%d  asan %2d  wrong counts %2d  hang %d | %s\n' "$name" "$pass" "$N" "$asan" "$other" "$hang" "$last"
}

arm control-off new none A=0
arm control-on new none KYTY_BC5_APR_PARK_TO_WORKER=1
arm old-ra4 base busy A=0
arm old-ra0 base busy KYTY_BC5_APR_READAHEAD=0
arm off-ra4 new busy A=0
arm off-ra0 new busy KYTY_BC5_APR_READAHEAD=0
arm off0-ra0 new busy KYTY_BC5_APR_PARK_TO_WORKER=0 KYTY_BC5_APR_READAHEAD=0
arm on-ra4 new busy KYTY_BC5_APR_PARK_TO_WORKER=1
arm on-ra0 new busy KYTY_BC5_APR_PARK_TO_WORKER=1 KYTY_BC5_APR_READAHEAD=0
arm alone-off new alone A=0
arm alone-on new alone KYTY_BC5_APR_PARK_TO_WORKER=1
arm sync-on new busy KYTY_BC5_APR_SYNC=1 KYTY_BC5_APR_PARK_TO_WORKER=1
