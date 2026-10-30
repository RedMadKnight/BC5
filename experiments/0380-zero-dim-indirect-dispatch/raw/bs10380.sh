#!/usr/bin/env bash
# BC5 experiment 0380: the smoke BS1 for the B loop's manifest (MANIFEST-B-loop-r1.md, Codex's follow-up of 2026-10-30): one
# 180-s try of s6n0380r1.sh, RT on, with the loop's two switches plus BC5_0380_REC_SELFTEST_S=150, the only difference.
# Reads the full hashes, saves and shared pins before and after, and passes only with the runner's verdict pass, the
# recorder's self-test line and file, unchanged saves and pins, and none of the experiments' other switches in the
# emulator's environment. One try: it never restarts. Exits non-zero on anything else.
# usage: bash ~/bc5-work/exp0380r1/bs10380.sh <expected live-saves sum> [tag, BS1]   (on the box)
set -u -o pipefail
SAVES=${1:?the live saves sum}; TAG=${2:-BS1}
W=$HOME/bc5-work; LOCK=$W/BOX-LOCK; E=$W/exp0380r1/run; R=$E/raw; BIN=$W/exp0380r1/bin/kyty_emulator; S6N=$W/exp0380r1/s6n0380r1.sh
SW="BC5_CRASH_FRAMES=1 BC5_0380_REC=1 BC5_0380_REC_SELFTEST_S=150"
FORBID='^BC5_(DIRECT_(ACB_STATE_RESTORE|DRAW_ARGS_JOURNAL|PIECES_NO_CLEAR|ZERO_SKIP|ZEROSCAN_[A-Z]+|ARGS_[A-Z]+|REBASE_DISPATCH|FORCE_START_000|GPU_CHECK_ZERO|GPU_CHECK_YZ)|NO_TIMEOUT_PROBE)='
OUT=$R/$TAG-smoke.txt
fail() { echo "FAIL: $*" | tee -a "$OUT"; exit 1; }
hashes() {
  echo "binary $(md5sum < "$BIN" | cut -d' ' -f1); runner $(md5sum < "$S6N" | cut -d' ' -f1)"
  echo "shared normal $(md5sum < "$W/kytyplus-build/src/kyty_emulator" | cut -d' ' -f1), lean $(md5sum < "$W/kytyplus-build-lean/src/kyty_emulator" | cut -d' ' -f1), archive $(md5sum < "$W/backend-ubuntu/libbc5_backend.a" | cut -d' ' -f1), play-pkg.sh $(md5sum < "$W/play-pkg.sh" | cut -d' ' -f1), learned $(md5sum < "$W/direct-learned-pkg.txt" | cut -d' ' -f1)"
}
saves() { (cd "$W/_SaveData" && find PPSA03671 -type f -exec md5sum {} + | sort -k2 | md5sum | cut -c1-16); }
pgrep '^kyty_emulator' > /dev/null && { echo "an emulator runs: not started"; exit 1; }
[ -s "$LOCK" ] && { echo "the box is locked: $(cat "$LOCK")"; exit 1; }
[ -e "$OUT" ] && { echo "$OUT exists: a new tag"; exit 1; }
mkdir -p "$R"
FREE=$(df -Pk "$W" | awk 'NR == 2 {print int($4 / 1048576)}')
[ "$FREE" -ge 20 ] || { echo "$FREE GiB free"; exit 1; }
[ "$(md5sum < "$BIN" | cut -c1-8)" = 44417414 ] || { echo "the binary is not 44417414"; exit 1; }
[ "$(md5sum < "$S6N" | cut -c1-8)" = 494ac253 ] || { echo "the runner is not 494ac253"; exit 1; }
H0=$(hashes); L0=$(saves)
{ echo "== $(date '+%F %T') $TAG, 180 s, RT on, switches: $SW"; echo "$H0"; echo "live saves $L0; $FREE GiB free; boot $(cut -c1-8 /proc/sys/kernel/random/boot_id)"; } | tee "$OUT"
[ "$L0" = "$SAVES" ] || fail "the live saves read $L0, not $SAVES"
# the emulator's environment, names and values of the BC5 switches only
( for _ in $(seq 1 120); do P=$(pgrep -o -x kyty_emulator) && break; sleep 0.5; done
  [ -n "${P:-}" ] && sleep 2 && tr '\0' '\n' < "/proc/$P/environ" | grep '^BC5_' | sort > "$R/$TAG-environ.txt" ) &
BC5_0368_SWITCHES="$SW" bash "$S6N" "$SAVES" "$TAG" 180 on > "$R/$TAG-runner.out" 2>&1; RC=$?
echo "top exp 0380 | $TAG checks, then release | $(date '+%F %T')" > "$LOCK"
trap 'grep -q "^top exp 0380 |" "$LOCK" 2> /dev/null && : > "$LOCK"' EXIT
wait
V=$(cat "$R/$TAG-verdict.txt" 2> /dev/null || echo "no verdict")
J=$(ls -td "$HOME"/bc5-data/captures/play-*/gc 2> /dev/null | head -1)
{ echo "== $(date '+%F %T') runner rc $RC; verdict $V"; cat "$R/$TAG-summary.txt" "$R/$TAG-0358.txt" 2> /dev/null; cat "$R/$TAG-box-settings.txt" 2> /dev/null; echo "journal $J"
  grep -a '^rec0380: ' "$J/direct.log" | cut -c1-260; grep -c . "$R/$TAG-environ.txt"; hashes; } | tee -a "$OUT"
H1=$(hashes); L1=$(saves); echo "live saves after $L1" | tee -a "$OUT"
[ "$RC" = 0 ] || fail "runner rc $RC"
[ "$V" = pass ] || fail "verdict $V"
[ "$H1" = "$H0" ] || fail "a hash changed"
[ "$L1" = "$L0" ] || fail "the live saves changed: tell the maintainer before anything is restored"
[ -s "$R/$TAG-environ.txt" ] || fail "the emulator's environment was not read"
grep -E "$FORBID" "$R/$TAG-environ.txt" && fail "a switch of another test is set"
for s in $SW; do grep -qxF -- "$s" "$R/$TAG-environ.txt" || fail "$s is not set"; done
grep -aq '^rec0380: .*start (self-test)' "$J/direct.log" && grep -aq '^rec0380: .*written ' "$J/direct.log" || fail "no recorder self-test lines"
ls "$J"/rec0380-*.txt > /dev/null 2>&1 || fail "no recorder file"
echo "== $(date '+%F %T') $TAG passed" | tee -a "$OUT"
