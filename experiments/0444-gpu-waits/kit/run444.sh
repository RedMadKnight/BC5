#!/usr/bin/env bash
# BC5 exp 0444: one wait-rings case on the GPU (--submit). CLAUDE.md hard rule 5: it can hang or reset
# the machine; it runs only in the top session's slot, on a clean boot, one case per unit, never in a chain.
#   run444.sh <case> [one|separate]   case: a wait-rings case name or alias (T5 first: every other case
#                                     relies on its rescue); contexts default one
#   W444_BIN=<path> W444_WANT=<md5>   the binary and its md5 (default: the kit's build, pinned by PIN)
#   GATE_DMESG="cmd"                  the kernel-log read (default sudo -n dmesg), for the stand-in
# Order: the R60/R43 gate (a failed or empty read refuses; any amdgpu/drm timeout or reset line on this
# boot refuses), no emulator, BOX-LOCK claimed by an atomic hard link (only our line is removed), the
# case, then the gate again (a new kernel line is reported and this boot is closed: R60).
# Start: systemd-run --user --unit=bc5-w444-<case> --collect -p RuntimeMaxSec=120 \
#        bash ~/bc5-work/exp0444/kit/run444.sh <case> [one|separate]
set -u
ulimit -c 0
export LC_ALL=C
W=$HOME/bc5-work/exp0444
KIT=$(cd "$(dirname "$0")" && pwd)
LOCK=$HOME/bc5-work/BOX-LOCK
C=${1:?case}; X=${2:-one}
case "$C" in *[!A-Za-z0-9-]* | "") echo "a case name"; exit 1 ;; esac
case "$X" in one | separate) ;; *) echo "contexts: one or separate"; exit 1 ;; esac
BIN=${W444_BIN:-$W/build/wait-rings}
WANT=${W444_WANT:-$(cat "$KIT/PIN" 2> /dev/null)}
R=$W/runs; mkdir -p "$R" || exit 1
T=$(date +%Y%m%d-%H%M%S)-$C-$X
OUT=$R/$T.txt
say() { echo "$*" | tee -a "$OUT"; }
gate() { # gate WHEN: 0 admitted, 2 a GPU kernel line, 3 the read failed or was empty
    local o rc hit k
    o=$(${GATE_DMESG:-sudo -n dmesg} 2> /dev/null); rc=$?
    if [ $rc -ne 0 ] || [ -z "$o" ]; then say "gate ($1): REFUSED: the kernel log read failed (rc $rc) or was empty: no data is not zero (R43)"; return 3; fi
    hit=$(printf '%s\n' "$o" | grep -a 'amdgpu.*\(timeout\|reset\)\|drm.*\(timeout\|reset\)' | grep -a -v 'bc5-gpu-watch: watching the kernel log' | grep -a -v -e '] Kernel command line: ' -e '] Command line: ')
    k=$(printf '%s' "$hit" | grep -a -c .)
    if [ "$k" != 0 ]; then say "gate ($1): REFUSED: $k amdgpu/drm timeout or reset lines on this boot (R55, R60)"; printf '%s\n' "$hit" | head -3 | tee -a "$OUT"; return 2; fi
    say "gate ($1): admitted: 0 amdgpu/drm timeout or reset lines in $(printf '%s\n' "$o" | grep -c .) lines"
    return 0
}
say "== run444 $C ($X): $(date '+%F %T'), kernel $(uname -r), boot $(cut -c1-8 /proc/sys/kernel/random/boot_id), up $(cut -d' ' -f1 /proc/uptime) s"
gate "before" || exit $?
[ -n "$WANT" ] && [ "$(md5sum < "$BIN" 2> /dev/null | cut -c1-8)" = "${WANT:0:8}" ] || { say "REFUSED: $BIN is not md5 ${WANT:-<no PIN>}"; exit 1; }
pgrep '^kyty_emulator' > /dev/null && { say "REFUSED: an emulator runs"; exit 1; }
LINE="exp 0444 | wait-rings $C ($X), token $(date +%Y%m%d%H%M%S)$$"
[ -e "$LOCK" ] || touch "$LOCK"
[ -f "$LOCK" ] && [ ! -L "$LOCK" ] && [ ! -s "$LOCK" ] || { say "REFUSED: the box is locked: $(cat "$LOCK" 2> /dev/null)"; exit 1; }
tl=$LOCK.0444-$$.new; al=$LOCK.0444-$$.aside
printf '%s\n' "$LINE" > "$tl" && mv -T "$LOCK" "$al" && ln "$tl" "$LOCK" || { [ -e "$LOCK" ] || mv -T "$al" "$LOCK"; rm -f "$tl"; say "REFUSED: the lock claim failed"; exit 1; }
if [ -s "$al" ]; then mv -fT "$al" "$LOCK"; rm -f "$tl"; say "REFUSED: a foreign lock line arrived during the claim"; exit 1; fi
rm -f "$al" "$tl"
release() { if [ -f "$LOCK" ] && grep -qxF -- "$LINE" "$LOCK"; then local t=$LOCK.0444-$$.rel; grep -vxF -- "$LINE" "$LOCK" > "$t"; mv -fT "$t" "$LOCK"; fi; }
trap release EXIT
say "lock: $LINE"
distrobox enter ubuntu -- "$BIN" --submit --case "$C" --contexts "$X" >> "$OUT" 2>&1
RC=$?
say "== wait-rings exit $RC (0 every case ended; 3 STUCK; 4 T5 failed: the rescue cannot be trusted)"
grep -a -E '^(verdict|STUCK|T5 failed|SKIPPED)' "$OUT" | tail -20
sleep 3
gate "after"; G=$?
[ "$G" = 0 ] || say "R60: a GPU kernel line after the case: this boot is closed for GPU runs"
say "== run444 $C ($X) end $(date '+%T'), log $OUT"
[ "$RC" = 0 ] && [ "$G" = 0 ]
