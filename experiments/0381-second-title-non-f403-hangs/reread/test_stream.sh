#!/usr/bin/env bash
# BC5 exp 0381, re-reads: who the series signals, on the laptop, with a stand-in ssh and /proc. A busy lock starts nothing and stops
# nothing; a full series stops its stream before it releases; only the token's own process is signalled. usage: bash test_stream.sh
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
fail=0
check() { if eval "$2"; then echo "ok   $1"; else echo "FAIL $1"; fail=1; fi; }
mkdir -p "$T/bin"
cat > "$T/bin/ssh" <<'E'
#!/bin/bash
# One line per call: its kind, read from the arguments and the script on stdin.
in=""; [ -t 0 ] || in=$(cat)
a="$* $in"
case "$a" in
    *tb2_claim*) k=claim ;;
    *"exec timeout 7000 journalctl"*) k=stream-start ;;
    *"streamstop"* | *"not ours any more"*) k=stream-stop ;;
    *tb2_release*) k=release ;;
    *"tar -cf"*) k=copy ;;
    *lock0381tb2.inc*"BC5_SRC"*) k=setup ;;
    *"arm "*) k=arm ;;
    *) k=other ;;
esac
echo "$k" >> "$SLOG"
[ "$k" = claim ] && exit "${CLAIM_RC:-0}"
[ "$k" = setup ] && [ -z "${SETUP_SILENT:-}" ] && echo "set up: stand-in"
[ "$k" = setup ] && exit "${SETUP_RC:-0}"
exit 0
E
chmod +x "$T/bin/ssh"
run() { SLOG=$T/log PATH="$T/bin:$PATH" bash "$HERE/series0381r.sh" T1 "$T/out" > "$T/out.txt" 2>&1; }
: > "$T/log"; CLAIM_RC=4 run; rc=$?
check "busy lock: the claim's rc" "[ $rc = 4 ]"
check "busy lock: one call, no stream, no stop, no release" "[ \"\$(cat '$T/log')\" = claim ]"
: > "$T/log"; SETUP_RC=5 run; rc=$?
check "failed step: its rc" "[ $rc = 5 ]"
check "failed step: the stream stops, the numbers copy, then the lock goes" "[ \"\$(tail -4 '$T/log' | tr '\n' ' ')\" = 'stream-stop copy copy release ' ]"
: > "$T/log"; SETUP_SILENT=1 run; rc=$?
check "a setup that ends early with rc 0 stops the series" "[ $rc = 1 ] && ! grep -q arm '$T/log'"
: > "$T/log"; run; rc=$?
check "full series passes" "[ $rc = 0 ]"
check "full series: claim, then the stream" "[ \"\$(head -2 '$T/log' | tr '\n' ' ')\" = 'claim stream-start ' ]"
check "full series: five arms" "[ \"\$(grep -c '^arm' '$T/log')\" = 5 ]"
check "full series: the stream stops, the numbers copy, then the lock goes, last" "[ \"\$(tail -4 '$T/log' | tr '\n' ' ')\" = 'stream-stop copy copy release ' ]"
: > "$T/log"; SLOG=$T/log PATH="$T/bin:$PATH" bash "$HERE/series0381r.sh" T1 "$T/out" rest > "$T/out.txt" 2>&1; rc=$?
check "rest: four arms, no calibration" "[ $rc = 0 ] && [ \"\$(grep -c '^arm' '$T/log')\" = 4 ]"
check "no global match is left in the series" "! grep -q 'pgrep -f' '$HERE/series0381r.sh'"
P=$T/proc; RR=$T/rr; mkdir -p "$RR" "$P/10" "$P/20"
stat() { echo "$1 (timeout) S 1 1 1 0 -1 0 0 0 0 0 0 0 0 0 20 0 1 0 $2 0 0" > "$P/$1/stat"; printf 'timeout\0007000\000journalctl\000-k\000-f\000' > "$P/$1/cmdline"; }
stat 10 555; stat 20 777
mkk() { printf '#!/bin/sh\necho "$1" >> %s/killed\n' "$T" > "$T/bin/fakekill"; chmod +x "$T/bin/fakekill"; }
mkk
stop() { RR=$RR PROC=$P KILL=$T/bin/fakekill bash "$HERE/streamstop0381r.sh" tok; }
echo "10 555" > "$RR/stream-tok.pid"; stop > /dev/null
check "own stream signalled, the foreign one not" "[ \"\$(cat '$T/killed')\" = 10 ]"
check "the file is gone" "[ ! -e '$RR/stream-tok.pid' ]"
rm -f "$T/killed"; echo "10 999" > "$RR/stream-tok.pid"; stop > /dev/null
check "a reused PID is left alone" "[ ! -e '$T/killed' ]"
printf 'sleep\000100\000' > "$P/10/cmdline"; echo "10 555" > "$RR/stream-tok.pid"; stop > /dev/null
check "another command at that PID is left alone" "[ ! -e '$T/killed' ]"
echo "30 555" > "$RR/stream-tok.pid"; stop > /dev/null
check "a process that is gone is left alone" "[ ! -e '$T/killed' ]"
[ "$fail" = 0 ] && echo "all passed"
exit $fail
