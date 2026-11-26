#!/usr/bin/env bash
# BC5 exp 0381, re-reads: the whole series from the laptop, on the top session's slot, stopping at the first failed step: claim and
# build, calibration, A C A C, release, copy of the numbers. The kernel log is streamed to the laptop. Run from the worktree's root.
# usage: bash series0381r.sh <run-id> <out-dir> [rest]   (needs the cycle's copy of lock0381tb2.inc and boxcap0381.sh on the box, in in-tb2)
# rest: no calibration, only A C A C. cache: a fill arm, then A W A W, W on the private 64 GiB disk cache.
# trace: two default arms, each with the mount's read trace.
set -u
ID=${1:?run id: letters and digits}; OUT=${2:?out dir}; REST=${3:-}
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(git -C "$HERE" rev-parse --show-toplevel)
CAP=900
CAND="BC5_MOUNT_DROP_BACKING=1 BC5_MOUNT_MAX_READAHEAD_KIB=32 BC5_MOUNT_PREFETCH_KIB=512"
WARM="BC5_0381_DC=1 BC5_MOUNT_DISK_CACHE_MIB=65536"
mkdir -p "$OUT"
TOKEN=$(date +%Y%m%d%H%M%S)$RANDOM
echo "$TOKEN" > "$OUT/token"
# The claim comes first: a busy box starts nothing. Everything after it ends in finish, the stream before the lock goes.
claim() {
    ssh bc250 "bash -s" -- "$TOKEN" <<'S'
set -u
W=$HOME/bc5-work; TB2_TOKEN=$1
pgrep '^kyty_emulator' > /dev/null && { echo "GUARD: an emulator runs"; exit 3; }
. $W/exp0381/in-tb2/experiments/0381-second-title-non-f403-hangs/lock0381tb2.inc
trap tb2_held_release EXIT
tb2_claim
tb2_own
pgrep '^kyty_emulator' > /dev/null && { echo "GUARD: an emulator runs"; exit 3; }
tb2_queue "$TB2_LINE: mount reread series | $(date '+%F %T')"
mkdir -p $W/exp0381/reread/raw
TB2_HELD=0
S
}
# exec keeps the shell's PID, so the file names the stream itself, with its start time.
start_stream() {
    ssh bc250 "F=\$HOME/bc5-work/exp0381/reread/stream-$TOKEN.pid; echo \"\$\$ \$(sed 's/^.*) //' /proc/\$\$/stat | awk '{ print \$20 }')\" > \"\$F\"; exec timeout 7000 journalctl -k -f -n 0 -o short-precise" < /dev/null > "$OUT/kern-$ID.txt" 2>&1 &
    KP=$!
}
stop_stream() {
    ssh bc250 'bash -s' -- "$TOKEN" < "$HERE/streamstop0381r.sh"
    kill "$KP" 2> /dev/null
    wait "$KP" 2> /dev/null
}
# A stopped series keeps its numbers too: the copy comes before the release.
collect() {
    ssh bc250 "tar -cf - -C ~/bc5-work/exp0381/reread raw" | tar -xf - -C "$OUT"
    ssh bc250 'L=$(ls -t ~/bc5-work/exp0381/tb2/play/mount-*.log | head -5); tar -cf - $L' | tar -xf - -C "$OUT"
}
finish() { stop_stream; collect; release; }
step() { local n=$1; shift; echo "== $n"; "$@"; local rc=$?; echo "== $n rc $rc"; [ "$rc" = 0 ] || { finish; exit "$rc"; }; }
send() {
    ssh bc250 "bash -s" -- "$TOKEN" < <(cat <<S
set -u
W=\$HOME/bc5-work
TB2_TOKEN=\$1
pgrep '^kyty_emulator' > /dev/null && { echo "GUARD: an emulator runs"; exit 3; }
. \$W/exp0381/in-tb2/experiments/0381-second-title-non-f403-hangs/lock0381tb2.inc
mkdir -p \$W/exp0381/reread
base64 -d > \$W/exp0381/reread/tools.tar <<'B'
$(git -C "$ROOT" -c core.autocrlf=false archive HEAD tools | base64 -w76)
B
base64 -d > \$W/exp0381/reread/gate0381r.inc <<'B'
$(base64 -w76 "$HERE/gate0381r.inc")
B
base64 -d > \$W/exp0381/reread/sample-reread.sh <<'B'
$(base64 -w76 "$HERE/sample-reread.sh")
B
base64 -d > \$W/exp0381/reread/walk0381r.cmd <<'B'
$(base64 -w76 "$HERE/walk0381r.cmd")
B
base64 -d > \$W/exp0381/reread/mkcatch0381r.py <<'B'
$(base64 -w76 "$HERE/mkcatch0381r.py")
B
base64 -d > \$W/exp0381/reread/catch0381r_pure.inc <<'B'
$(base64 -w76 "$HERE/catch0381r_pure.inc")
B
base64 -d > \$W/exp0381/reread/catch0381r_host.inc <<'B'
$(base64 -w76 "$HERE/catch0381r_host.inc")
B
BC5_SRC=\$W/exp0381/reread/tools.tar
$(cat "$HERE/setup0381r.sh")
S
)
}
# The setup's last line says it ran to its end: the script comes on stdin, and a command that reads stdin ends it early with rc 0.
setup() { local rc; send > "$OUT/setup.txt"; rc=$?; cat "$OUT/setup.txt"; [ "$rc" = 0 ] || return "$rc"; grep -q '^set up:' "$OUT/setup.txt"; }
arm() { local tag=$1; shift; ssh bc250 'bash -s' -- "$ID$tag" "$TOKEN" "$CAP" "$@" < "$HERE/arm0381r.sh"; }
release() {
    ssh bc250 "bash -s" -- "$TOKEN" <<'S'
W=$HOME/bc5-work; TB2_TOKEN=$1
. $W/exp0381/in-tb2/experiments/0381-second-title-non-f403-hangs/lock0381tb2.inc
tb2_queue_q "$TB2_LINE: mount reread series ended | $(date '+%F %T')"
tb2_release
S
}
# The streaming gate (F634, F635): minutes of 4 GiB or more from 2 minutes after gameplay. It only says what the arms can show,
# so it does not stop them: under 3 minutes, only the load window counts.
stream() {
    ssh bc250 "R=\$HOME/bc5-work/exp0381/reread/raw; G=\$(sed -n 's/.*gameplay at \([0-9]*\),.*/\1/p' \$R/${ID}A0-start.txt); grep '^T ' \$R/${ID}A0-sample.txt | tr ' ' '\n' | grep '^mount_read_bytes=' | cut -d= -f2 | awk -v g=\"\${G:-0}\" 'NR > g + 120 && (NR % 60) == 0 { if (p && \$1 - p >= 4 * 2^30) n++; p = \$1 } END { print n + 0, \"minutes at 4 GiB or more\" }'" | tee "$OUT/stream.txt"
}
echo "== claim"
claim; rc=$?
echo "== claim rc $rc"
[ "$rc" = 0 ] || exit "$rc"
start_stream
step setup setup
if [ "$REST" = trace ]; then
    step T1 arm T1 BC5_0381_TRACE=1
    step T2 arm T2 BC5_0381_TRACE=1
    finish
    exit 0
fi
if [ "$REST" = cache ]; then
    step fill arm W0 $WARM
    step A1 arm A1
    step W1 arm W1 $WARM
    step A2 arm A2
    step W2 arm W2 $WARM
    finish
    exit 0
fi
if [ "$REST" != rest ]; then
    step baseline arm A0
    stream
fi
step A1 arm A1
step C1 arm C1 $CAND
step A2 arm A2
step C2 arm C2 $CAND
finish
