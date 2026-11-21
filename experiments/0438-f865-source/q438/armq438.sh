#!/usr/bin/env bash
# BC5 exp 0438 (tag stack438): one 60-s GPU-risk arm of the bisect of q438sQ2's hang (the top session's GO of 2026-11-21):
# ASTRO BOT on the stack's normal build 137ef7af with the switch words given, BC5_FAULT_RECORD=1, under an atomically
# claimed lock held only for the run. Before the run: no emulator / bc5-mount, no dead ASTRO mount inside the container;
# the reset count before and after; start0413g.sh ends the run on any amdgpu line; a watcher ends it on an A2 MISMATCH.
# Reports the result, the reset lines, r438's and q438's BUG lines (from the run's journal, direct.log), GIVEN UP, the
# fault record's directory.
#   bash armq438.sh <tag> [SWITCH=1 ...]     (on the box, under the user manager)
set -u
ulimit -c 0
export LC_ALL=C
P=${1:?tag}; shift; ARGS=("$@"); W=$HOME/bc5-work; N=$W/exp0413/n; R=$N/raw; LOCK=$W/BOX-LOCK
BIN=$W/exp0438/stack/normal/kyty_emulator; M=$HOME/bc5-data/mnt/PPSA21567; S=$R/$P-armq438.txt
case "$P" in *[!A-Za-z0-9]* | "") echo "the tag prefix is letters and digits"; exit 1 ;; esac
WANT=$(md5sum < "$BIN" | cut -d' ' -f1)
[ "${WANT:0:8}" = 853e16e9 ] && [ "$WANT" = "$(cat "$(dirname "$BIN")/binary.md5")" ] || { echo "the binary is ${WANT:0:8}, not the stack's normal 853e16e9: not started"; exit 1; }
[ -e "$R/$P-start.txt" ] && { echo "tag $P already used"; exit 1; }
mkdir -p "$R"
say() { echo "$(date +%T) $*" | tee -a "$S"; }
resets() { sudo -n dmesg 2> /dev/null | grep -E 'amdgpu [0-9a-f]{4}:' | grep -ciE 'ring .* timeout|reset (succeeded|failed)|GPU reset|device wedged'; }
busy() { pgrep -x kyty_emulator > /dev/null || pgrep -x bc5-mount > /dev/null; }
deadmnt() { distrobox enter ubuntu -- sh -c 'M=$1; if mountpoint -q "$M" && ! head -c1 "$M/sce_sys/param.json" > /dev/null 2>&1; then echo dead; fi' _ "$M" 2> /dev/null < /dev/null | grep -q dead; }
echo "$(date '+%F %T') $P: boot $(cut -c1-8 /proc/sys/kernel/random/boot_id), binary $WANT" > "$S"
busy && { say "an emulator or bc5-mount runs: not started"; exit 1; }
LINE="exp 0438 | stack438 bisect arm $P (ASTRO BOT 60 s: ${ARGS[*]:-no switch}), token $(date +%s)$$ | $(date '+%F %T')"
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
    local t=$P line r0 r1 wp
    busy && { say "STOP before $t: an emulator or bc5-mount runs"; finish 1; }
    deadmnt && { say "STOP before $t: a dead ASTRO mount inside the container"; finish 1; }
    r0=$(resets)
    local MK=$R/$t-marker; : > "$MK"
    ( while sleep 2; do
        if grep -aq 'exp 0438 (tag a2): MISMATCH' "$N/astro-last.log" 2> /dev/null; then echo "$(date +%T) $t: A2 MISMATCH seen: the emulator is ended" >> "$S"; pkill -TERM -o -x kyty_emulator; break; fi
      done ) &
    wp=$!
    line=$(cd "$N" && CHAIN_LOCKLINE=$LINE P_BIN=$BIN P_WANT=$WANT bash ./start0413g.sh "$t" astro 60 BC5_FAULT_RECORD=1 "$@" 2>&1 | tail -1)
    kill "$wp" 2> /dev/null
    r1=$(resets)
    local L=$R/$t-play.log
    say "$t [$*]: $line"
    local J; J=$(find ~/bc5-data/captures -maxdepth 1 -name "play-*" -newer "$MK" 2> /dev/null | sort | head -1)/gc/direct.log
    say "$t: journal $J: q438 BUG $(grep -ac 'q438 (exp 0438): BUG' "$J"), r438 BUG $(grep -ac 'r438 (exp 0438, b438): BUG' "$J"); fault record: $(ls -dt ~/bc5-data/captures/faults/* | head -1 | xargs basename) $(grep -ac 'GPU FAULT' "$L") GPU FAULT lines"
    grep -qi 'reset failed' "$R/$t-dmesg-after.txt" 2> /dev/null && say "$t: A RING RESET FAILED (the box may reboot)"
    say "$t: reset lines: $(grep -o 'ring [a-z_0-9.]* timeout\|Ring [a-z_0-9.]* reset [a-z]*' "$R/$t-dmesg-after.txt" 2> /dev/null | sort | uniq -c | tr -s ' ' | tr '
' ';')"
    say "$t: resets $r0 -> $r1; r438 BUG lines $(grep -ac 'r438 (exp 0438, b438): BUG' "$L"), of them waits over 100 ms $(grep -ac 'has waited .* for an early-registered writer' "$L"); GIVEN UP $(grep -aci 'given up' "$L"); A2 MISMATCH $(grep -ac 'tag a2): MISMATCH' "$L"); q438 lines $(grep -ac 'q438' "$L")"
    grep -a 'r438 (exp 0438, b438): t \|tag a1c438): t \|tag a2c438): t ' "$L" | tail -3 | cut -c1-400 | tee -a "$S"
    grep -a 'r438 (exp 0438, b438): BUG\|q438.*BUG' "$L" | head -5 | cut -c1-300 | tee -a "$S"
    case "$line" in *"PASS: ran 60 s"*"kernel lines 0, crash lines 0"*) ;; *) say "RESULT $t: NOT CLEAN"; finish 2 ;; esac
    [ "$r0" = "$r1" ] || { say "RESULT $t: the reset count changed"; finish 2; }
    local mm; mm=$(grep -ac 'tag a2): MISMATCH' "$L" 2> /dev/null); [ "${mm:-0}" = 0 ] || { say "RESULT $t: an A2 mismatch"; finish 2; }
    local qb; qb=$(grep -ac 'q438 (exp 0438): BUG' "$J" 2> /dev/null)
    if [ "${qb:-0}" = 0 ]; then say "RESULT $t: CLEAN"; else say "RESULT $t: no GPU line, but ${qb} q438 BUG lines (Q438's invariant broken: not clean)"; fi
}
run "${ARGS[@]}"
finish 0
