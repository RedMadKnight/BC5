#!/usr/bin/env bash
# BC5 exp 0381, re-reads: the whole series from the laptop, on the top session's slot, stopping at the first failed step: claim and
# build, calibration, A C A C, release, copy of the numbers. The kernel log is streamed to the laptop. Run from the worktree's root.
# usage: bash series0381r.sh <run-id> <out-dir>   (needs the cycle's copy of lock0381tb2.inc and boxcap0381.sh on the box, in in-tb2)
set -u
ID=${1:?run id: letters and digits}; OUT=${2:?out dir}
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(git -C "$HERE" rev-parse --show-toplevel)
CAP=900
CAND="BC5_MOUNT_DROP_BACKING=1 BC5_MOUNT_MAX_READAHEAD_KIB=32 BC5_MOUNT_PREFETCH_KIB=512"
mkdir -p "$OUT"
TOKEN=$(date +%Y%m%d%H%M%S)$RANDOM
echo "$TOKEN" > "$OUT/token"
RDIR='$HOME/bc5-work/exp0381/reread'
stop_stream() {
    kill "${KP:-}" 2> /dev/null
    ssh bc250 'pgrep -f "^timeout 7000 journalctl -k" | xargs -r kill'
}
step() { local n=$1; shift; echo "== $n"; "$@"; local rc=$?; echo "== $n rc $rc"; [ "$rc" = 0 ] || { release; stop_stream; exit "$rc"; }; }
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
BC5_SRC=\$W/exp0381/reread/tools.tar
$(cat "$HERE/setup0381r.sh")
S
)
}
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
ssh bc250 "timeout 7000 journalctl -k -f -n 0 -o short-precise" > "$OUT/kern-$ID.txt" 2>&1 &
KP=$!
step setup send
step baseline arm A0
stream
step A1 arm A1
step C1 arm C1 $CAND
step A2 arm A2
step C2 arm C2 $CAND
release
stop_stream
ssh bc250 "tar -cf - -C ~/bc5-work/exp0381/reread raw" | tar -xf - -C "$OUT"
ssh bc250 'L=$(ls -t ~/bc5-work/exp0381/tb2/play/mount-*.log | head -5); tar -cf - $L' | tar -xf - -C "$OUT"
