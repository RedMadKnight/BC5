#!/usr/bin/env bash
# BC5 exp 0438: the three steps of the top session's order of 2026-11-21 13:02, under ONE BOX-LOCK line:
#  1. the ASTRO mount alone (bc5-mount in the ubuntu distrobox, as the launcher does): the time until the mountpoint
#     shows and until sce_sys/param.json is readable (bounded 30 s), bc5-mount's stderr, sce_sys listed, unmount,
#     /proc/mounts clean;
#  2. the control: the shared normal build, ASTRO for 30 s through start0413g.sh (the same launcher);
#  3. the recording run (runa1j.sh, 180 s).
# A step that fails stops the chain. The lock is released only when no kyty_emulator / bc5-mount and no bc5 FUSE mount
# is left (LESSONS R68).
#   bash mnt438.sh <tag-prefix>     (on the box, under the user manager)
set -u
export LC_ALL=C
P=${1:?tag prefix}; W=$HOME/bc5-work; N=$W/exp0413/n; R=$N/raw; LOCK=$W/BOX-LOCK; HERE=$(cd "$(dirname "$0")" && pwd)
C="$HOME/bc5-data/games/PPSA21567 - ASTRO BOT_4xx.ffpfsc"; M=$HOME/bc5-data/mnt/PPSA21567; BM=$W/bc5-tools-ubuntu/release/bc5-mount
S=$R/$P-mnt438.txt; mkdir -p "$R"
say() { echo "$(date +%T) $*" | tee -a "$S"; }
LINE="exp 0438 | mount test, control and recording $P, token $(date +%s)$$ | $(date '+%F %T')"
[ -e "$LOCK" ] || touch "$LOCK"
[ -f "$LOCK" ] && [ ! -L "$LOCK" ] && [ ! -s "$LOCK" ] || { echo "the box is locked: $(cat "$LOCK")"; exit 1; }
tl=$LOCK.0438m-$$.new; al=$LOCK.0438m-$$.aside
printf '%s\n' "$LINE" > "$tl" && mv -T "$LOCK" "$al" && ln "$tl" "$LOCK" || { [ -e "$LOCK" ] || mv -T "$al" "$LOCK"; rm -f "$tl"; echo "the claim failed"; exit 1; }
if [ -s "$al" ]; then mv -fT "$al" "$LOCK"; rm -f "$tl"; echo "a foreign line arrived during the claim: not started"; exit 1; fi
rm -f "$al" "$tl"
leftovers() { { pgrep -x kyty_emulator; pgrep -x bc5-mount; } | tr '\n' ' '; grep -c "$M" /proc/mounts | sed 's/^0$//; s/^\([1-9]\)/mounts \1/'; }
finish() {
    sync
    local l; l=$(leftovers | tr -s ' ')
    if [ -z "${l// /}" ]; then
        if [ -f "$LOCK" ] && grep -qxF -- "$LINE" "$LOCK"; then t=$LOCK.0438m-$$.rel; grep -vxF -- "$LINE" "$LOCK" > "$t"; mv -fT "$t" "$LOCK"; fi
        say "lock released: [$(cat "$LOCK")]"
    else
        say "LOCK KEPT: left: $l"
    fi
    exit "$1"
}
echo "$(date '+%F %T') $P: lock line [$LINE]" > "$S"
[ -z "$(leftovers | tr -d ' ')" ] || { say "STOP: something is left before the start: $(leftovers)"; finish 1; }
mountpoint -q "$M" && { say "STOP: $M is already a mountpoint"; finish 1; }
say "step 1: $M holds $(ls -A "$M" | wc -l) entries; bc5-mount $(md5sum < "$BM" | cut -c1-8); image $(stat -c %s "$C") bytes"

# step 1: the mount alone, inside the container (the launcher's own sequence: mkdir -p, bc5-mount mount &, poll)
distrobox enter ubuntu -- bash -c '
M=$1; C=$2; BM=$3; E=$4
mkdir -p "$M"; echo "mkdir rc $?"
t0=$(date +%s%N); "$BM" mount "$C" "$M" > "$E" 2>&1 & MP=$!
tm=""; tf=""
for i in $(seq 1 150); do
  [ -z "$tm" ] && mountpoint -q "$M" && tm=$(( ($(date +%s%N) - t0) / 1000000 ))
  [ -z "$tf" ] && head -c 1 "$M/sce_sys/param.json" > /dev/null 2>&1 && tf=$(( ($(date +%s%N) - t0) / 1000000 ))
  [ -n "$tm" ] && [ -n "$tf" ] && break
  sleep 0.2
done
echo "mountpoint after ${tm:-never} ms; param.json readable after ${tf:-never} ms; bc5-mount pid $MP alive $( [ -d /proc/$MP ] && echo yes || echo no)"
echo "sce_sys: $(ls "$M/sce_sys" 2>&1 | head -20 | tr "\n" " ")"
echo "param.json: $(wc -c < "$M/sce_sys/param.json" 2>&1) bytes, md5 $(md5sum < "$M/sce_sys/param.json" 2>&1 | cut -c1-8)"
fusermount3 -u "$M"; echo "fusermount3 -u rc $?"
for i in $(seq 1 50); do [ -d /proc/$MP ] || break; sleep 0.2; done
echo "bc5-mount ended: $( [ -d /proc/$MP ] && echo NO || echo yes)"
' _ "$M" "$C" "$BM" "$R/$P-mnt438-stderr.txt" 2>&1 | tee -a "$S"
say "bc5-mount stderr: $(tr '\n' '|' < "$R/$P-mnt438-stderr.txt" | cut -c1-400)"
say "/proc/mounts entries for $M after the unmount: $(grep -c "$M" /proc/mounts)"
grep -q "param.json readable after [0-9]" "$S" && [ "$(grep -c "$M" /proc/mounts)" = 0 ] && ! pgrep -x bc5-mount > /dev/null || { say "STOP: step 1 failed"; finish 1; }

# step 2: the control, the shared normal build for 30 s
SB=$W/kytyplus-build/src/kyty_emulator; SW=$(md5sum < "$SB" | cut -d' ' -f1)
[ "${SW:0:8}" = b1b57df9 ] || { say "STOP: the shared normal is ${SW:0:8}, not b1b57df9"; finish 1; }
(cd "$N" && CHAIN_LOCKLINE=$LINE P_BIN=$SB P_WANT=$SW bash ./start0413g.sh "${P}ctl" astro 30 BC5_FAULT_RECORD=1 > "$R/${P}ctl-runner.txt" 2>&1)
say "step 2 control: $(tail -1 "$R/${P}ctl-runner.txt")"
sleep 3
[ -z "$(leftovers | tr -d ' ')" ] || { say "STOP: left after the control: $(leftovers)"; finish 1; }
grep -q "PASS: ran 30 s" "$R/${P}ctl-runner.txt" || { say "STOP: the control did not pass"; finish 1; }

# step 3: the recording run
CHAIN_LOCKLINE=$LINE bash "$HERE/runa1j.sh" "${P}rec" astro 180 > "$R/$P-rec-wrap.txt" 2>&1
say "step 3 recording: $(grep 'runner exit' "$R/$P-rec-wrap.txt")"
cat "$R/$P-rec-wrap.txt" >> "$S"
finish 0
