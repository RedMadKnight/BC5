#!/usr/bin/env bash
# BC5 exp 0438 (tag stack438): the first GPU runs of the stacked test build (the top session's conditional GO of 2026-11-21):
#   1. The first title 60 s, the stack's normal build, BC5_0438_SUBMITQ=1, A1 / A1P / A2 off, BC5_FAULT_RECORD=1;
#   2. only if 1 is clean: 60 s with every switch on (SUBMITQ, KYTY_BC5_0438_A1, _A1P, BC5_DIRECT_0438_A2, _A2_CHECK).
# One BOX-LOCK line for both, claimed atomically, passed to start0413g.sh (CHAIN_LOCKLINE), released once nothing is left.
# Before each run: no emulator / bc5-mount, no dead first-title mount inside the container; the reset count before and after;
# start0413g.sh ends the run at once on an amdgpu timeout / reset / fault line and ends the emulator by its PID after 60 s.
# Beside each run a watcher ends the emulator on the first A2 MISMATCH line. Per run: r438's BUG lines (waits over
# 100 ms for an early writer, early writes that never reached the ring), GIVEN UP lines, kernel and crash lines, and the
# 60-s counter lines.
#   bash runq438.sh <tag-prefix>     (on the box, under the user manager)
set -u
ulimit -c 0
export LC_ALL=C
P=${1:?tag prefix}; W=$HOME/bc5-work; N=$W/exp0413/n; R=$N/raw; LOCK=$W/BOX-LOCK
BIN=$W/exp0438/stack/normal/kyty_emulator; M=$HOME/bc5-data/mnt/TITLE1; S=$R/$P-runq438.txt
case "$P" in *[!A-Za-z0-9]* | "") echo "the tag prefix is letters and digits"; exit 1 ;; esac
WANT=$(md5sum < "$BIN" | cut -d' ' -f1)
[ "${WANT:0:8}" = 137ef7af ] && [ "$WANT" = "$(cat "$(dirname "$BIN")/binary.md5")" ] || { echo "the binary is ${WANT:0:8}, not the stack's normal 137ef7af: not started"; exit 1; }
for t in Q1 Q2; do [ -e "$R/$P$t-start.txt" ] && { echo "tag $P$t already used"; exit 1; }; done
mkdir -p "$R"
say() { echo "$(date +%T) $*" | tee -a "$S"; }
resets() { sudo -n dmesg 2> /dev/null | grep -E 'amdgpu [0-9a-f]{4}:' | grep -ciE 'ring .* timeout|reset (succeeded|failed)|GPU reset|device wedged'; }
busy() { pgrep -x kyty_emulator > /dev/null || pgrep -x bc5-mount > /dev/null; }
deadmnt() { distrobox enter ubuntu -- sh -c 'M=$1; if mountpoint -q "$M" && ! head -c1 "$M/sce_sys/param.json" > /dev/null 2>&1; then echo dead; fi' _ "$M" 2> /dev/null < /dev/null | grep -q dead; }
echo "$(date '+%F %T') $P: boot $(cut -c1-8 /proc/sys/kernel/random/boot_id), binary $WANT" > "$S"
busy && { say "an emulator or bc5-mount runs: not started"; exit 1; }
LINE="exp 0438 | stack438 GPU-risk runs $P (the first title 60 s SUBMITQ=1, then 60 s all switches), token $(date +%s)$$ | $(date '+%F %T')"
[ -e "$LOCK" ] || touch "$LOCK"
[ -f "$LOCK" ] && [ ! -L "$LOCK" ] && [ ! -s "$LOCK" ] || { say "the box is locked: $(cat "$LOCK")"; exit 1; }
tl=$LOCK.0438q-$$.new; al=$LOCK.0438q-$$.aside
printf '%s\n' "$LINE" > "$tl" && mv -T "$LOCK" "$al" && ln "$tl" "$LOCK" || { [ -e "$LOCK" ] || mv -T "$al" "$LOCK"; rm -f "$tl"; say "the claim failed"; exit 1; }
if [ -s "$al" ]; then mv -fT "$al" "$LOCK"; rm -f "$tl"; say "a foreign line arrived during the claim: not started"; exit 1; fi
rm -f "$al" "$tl"
say "lock claimed"
finish() {
    sleep 3
    for p in $(pgrep -x kyty_emulator); do [ "$(md5sum < "/proc/$p/exe" | cut -d' ' -f1)" = "$WANT" ] && kill -TERM "$p"; done
    sleep 2; sync
    if busy; then say "LOCK KEPT: left: $(pgrep -ax 'kyty_emulator|bc5-mount' | cut -c1-60 | tr '\n' ' ')"; exit "$1"; fi
    if [ -f "$LOCK" ] && grep -qxF -- "$LINE" "$LOCK"; then t=$LOCK.0438q-$$.rel; grep -vxF -- "$LINE" "$LOCK" > "$t"; mv -fT "$t" "$LOCK"; fi
    say "lock released: [$(cat "$LOCK")]"
    exit "$1"
}
run() { # $1 tag suffix, then the switch words
    local t=$P$1 line r0 r1 wp; shift
    busy && { say "STOP before $t: an emulator or bc5-mount runs"; finish 1; }
    deadmnt && { say "STOP before $t: a dead first-title mount inside the container"; finish 1; }
    r0=$(resets)
    ( while sleep 2; do
        if grep -aq 'exp 0438 (tag a2): MISMATCH' "$N/t1-last.log" 2> /dev/null; then echo "$(date +%T) $t: A2 MISMATCH seen: the emulator is ended" >> "$S"; pkill -TERM -o -x kyty_emulator; break; fi
      done ) &
    wp=$!
    line=$(cd "$N" && CHAIN_LOCKLINE=$LINE P_BIN=$BIN P_WANT=$WANT bash ./start0413g.sh "$t" t1 60 BC5_FAULT_RECORD=1 "$@" 2>&1 | tail -1)
    kill "$wp" 2> /dev/null
    r1=$(resets)
    local L=$R/$t-play.log
    say "$t [$*]: $line"
    say "$t: resets $r0 -> $r1; r438 BUG lines $(grep -ac 'r438 (exp 0438, b438): BUG' "$L"), of them waits over 100 ms $(grep -ac 'has waited .* for an early-registered writer' "$L"); GIVEN UP $(grep -aci 'given up' "$L"); A2 MISMATCH $(grep -ac 'tag a2): MISMATCH' "$L"); q438 lines $(grep -ac 'q438' "$L")"
    grep -a 'r438 (exp 0438, b438): t \|tag a1c438): t \|tag a2c438): t ' "$L" | tail -3 | cut -c1-400 | tee -a "$S"
    grep -a 'r438 (exp 0438, b438): BUG\|q438.*BUG' "$L" | head -5 | cut -c1-300 | tee -a "$S"
    case "$line" in *"PASS: ran 60 s"*"kernel lines 0, crash lines 0"*) ;; *) say "STOP: $t did not pass"; finish 1 ;; esac
    [ "$r0" = "$r1" ] || { say "STOP: the reset count changed"; finish 1; }
    [ "$(grep -ac 'tag a2): MISMATCH' "$L")" = 0 ] || { say "STOP: an A2 mismatch"; finish 1; }
    sleep 5
}
run Q1 BC5_0438_SUBMITQ=1
run Q2 BC5_0438_SUBMITQ=1 KYTY_BC5_0438_A1=1 KYTY_BC5_0438_A1P=1 BC5_DIRECT_0438_A2=1 BC5_DIRECT_0438_A2_CHECK=1
finish 0
