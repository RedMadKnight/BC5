#!/usr/bin/env bash
# Exp 0418, laptop side of a box run: stream the box's kernel log while a run goes, and stop the run's emulator (TERM,
# bounded ssh, retried) at the first amdgpu error line. Fixed after run t418a (2026-11-13 18:26): a global OOM printed a
# backtrace whose frame "amdgpu_gem_fault+0x95/0x100 [amdgpu]" matched "amdgpu ... fault"; the first form of this stopper
# (and exp 0413's run0413p.sh, line 204) took it for a GPU error. Now:
#   - a GPU error line names amdgpu and timeout/reset/fault/fail/error/hang, and is NOT a stack frame
#     ("name+0xOFF/0xLEN"); the lean mode's plasmashell restarts print "Unsupported screen format RA24" as a [drm]
#     *ERROR*, which is skipped too;
#   - an OOM (oom-killer, "Out of memory: Killed process") is counted and named, not stopped on: a run that meets the
#     memory wall is a result, and its runner's own fuse and watchdog decide.
# Ends by itself when the run's output has its end line (pattern 2), or after 25 minutes. Every ssh is bounded.
# usage: kern0418.sh <stream file> <grep pattern of the run's end line> [box file holding that line]
#        kern0418.sh --classify <file>     (prints the GPU error lines and the OOM lines a stream holds; for tests)
gpu_errors() { grep -a -i 'amdgpu' "$1" | grep -a -v -E '[A-Za-z_][A-Za-z0-9_.]*\+0x[0-9a-f]+/0x[0-9a-f]+' | grep -a -v 'Unsupported screen format' | grep -a -i -E 'timeout|reset|fault|fail|error|hang'; }
ooms() { grep -a -E 'invoked oom-killer|Out of memory: Killed process' "$1"; }
if [ "${1:-}" = --classify ]; then
    echo "gpu error lines: $(gpu_errors "$2" | grep -c .)"; gpu_errors "$2" | cut -c1-200
    echo "oom lines: $(ooms "$2" | grep -c .)"; ooms "$2" | cut -c1-200
    exit 0
fi
OUT=${1:?the stream file}; ENDPAT=${2:?the end line pattern}; ENDFILE=${3:-}
: > "$OUT"
timeout 1500 ssh -o ConnectTimeout=10 -o ServerAliveInterval=15 bc250 'journalctl -k -f -n 0 -o short-precise' >> "$OUT" 2>&1 &
SP=$!
trap 'kill $SP 2> /dev/null' EXIT
stopped=0; oomn=0; t0=$(date +%s); n=0
while [ $(($(date +%s) - t0)) -lt 1500 ]; do
    sleep 3
    n=$((n + 1))
    o=$(ooms "$OUT" | grep -c .)
    [ "$o" != "$oomn" ] && { echo "kern0418 $(date +%T): OOM lines now $o (not stopped): $(ooms "$OUT" | tail -1 | cut -c1-160)"; oomn=$o; }
    if [ "$stopped" = 0 ] && [ -n "$(gpu_errors "$OUT" | head -1)" ]; then
        echo "kern0418 $(date +%T): amdgpu error line: $(gpu_errors "$OUT" | head -1 | cut -c1-200)"
        for k in 1 2 3; do
            timeout 20 ssh -o ConnectTimeout=10 bc250 'pkill -TERM "^kyty_emulator"; sleep 2; pgrep "^kyty_emulator" > /dev/null && echo still || echo gone' && break
        done
        stopped=1
    fi
    if [ -n "$ENDFILE" ] && [ $((n % 10)) = 0 ]; then
        e=$(timeout 20 ssh -o ConnectTimeout=10 bc250 "grep -a -E '$ENDPAT' $ENDFILE" 2> /dev/null)
        if [ -n "$e" ]; then
            echo "kern0418 $(date +%T): the run ended: $e"
            sleep 5
            echo "kern0418: kernel lines $(grep -a -c . "$OUT"), GPU error lines $(gpu_errors "$OUT" | grep -c .), OOM lines $(ooms "$OUT" | grep -c .), stopped $stopped"
            exit 0
        fi
    fi
done
echo "kern0418 $(date +%T): 25 minutes passed without the run's end line; stopped $stopped"
