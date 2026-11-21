#!/usr/bin/env bash
# BC5 exp 0439 (tag ae439): the lean A/B of BC5_DIRECT_AGC_EOP_IDENT on ASTRO BOT, for the clean-boot chain after the
# maintainer's reboot, behind exp 0438's A/B (the top session's order of 2026-11-21 ~16:20; prepared, not run on the boot
# it was written). Adapted from exp 0438's r438o/ab438o.sh (main): ASTRO BOT, no input, through exp 0413's start0413g.sh,
# each run 180 s, one binary for both arms so only the switch differs:
#   C  the private exp 0439 lean (k439/lean, pinned 25338f8a) with BC5_DIRECT_AGC_EOP_IDENT unset (control)
#   O  the same binary with BC5_DIRECT_AGC_EOP_IDENT=1
#   in the order C O C O C O; MangoHud's own per-frame log is the frame counter, the Plasma shell stopped per lean run
#   (lean-session.sh), as in ab438o.sh. The binary must carry the switch's string (else it was compiled out of lean).
# One BOX-LOCK line for the whole chain, ulimit -c 0; boot check first (0 reset lines, a display, nothing running, no
# dead ASTRO mount); stops at the first failed run. DRY=1: checks and prints the plan, starts nothing, takes no lock.
#   systemd-run --user --unit=bc5-ab439ae --collect sh -c 'bash ~/bc5-work/exp0439/k439/ab439ae.sh q439aeA > ~/bc5-work/exp0439/ab439ae.log 2>&1'
set -u
ulimit -c 0
export LC_ALL=C
P=${1:?tag prefix}; W=${AB_W:-$HOME/bc5-work}; N=$W/exp0413/n; R=$N/raw; LOCK=$W/BOX-LOCK; DRY=${DRY:-0}
CB=$W/exp0439/k439/lean/kyty_emulator; OB=$CB
M=${AB_M:-$HOME/bc5-data/mnt/PPSA21567}; SECS=180; MHD=170
S=$R/$P-ab439ae.txt
m() { md5sum < "$1" | cut -d' ' -f1; }
say() { echo "$(date +%T) $*" | tee -a "$S"; }
case "$P" in *[!A-Za-z0-9]* | "") echo "the tag prefix is letters and digits"; exit 1 ;; esac
MC=$(m "$CB"); MO=$MC
{ [ "${AB_STANDIN:-0}" = 1 ] || [ "${MC:0:8}" = "${AB_PIN:-25338f8a}" ]; } || { echo "binary: private lean ${MC:0:8}: not the pinned one"; exit 1; }
[ "${AB_STANDIN:-0}" = 1 ] || grep -aq BC5_DIRECT_AGC_EOP_IDENT "$CB" || { echo "the lean binary has no BC5_DIRECT_AGC_EOP_IDENT: compiled out"; exit 1; }
for a in C1 O1 C2 O2 C3 O3; do [ -e "$R/$P$a-start.txt" ] && { echo "tag $P$a already used"; exit 1; }; done
deadmnt() { distrobox enter ubuntu -- sh -c 'M=$1; if mountpoint -q "$M" && ! head -c1 "$M/sce_sys/param.json" > /dev/null 2>&1; then echo dead; fi' _ "$M" 2> /dev/null < /dev/null | grep -q dead; }
busy() { pgrep -x kyty_emulator > /dev/null || pgrep -x bc5-mount > /dev/null; }
resets() { sudo -n dmesg 2> /dev/null | grep -E 'amdgpu [0-9a-f]{4}:' | grep -ciE 'ring .* timeout|reset (succeeded|failed)|GPU reset|device wedged'; }
display() { cat ${AB_DRM:-/sys/class/drm}/card*-DP-*/status ${AB_DRM:-/sys/class/drm}/card*-HDMI-*/status 2> /dev/null | grep -c '^connected$'; }
mkdir -p "$R"
echo "$(date '+%F %T') $P: boot $(cut -c1-8 /proc/sys/kernel/random/boot_id), up $(cut -d' ' -f1 /proc/uptime) s, kernel $(uname -r); private lean ${MC:0:8} (both arms)" > "$S"
# the boot check (the top session's step 1): 0 reset lines, a display connected, nothing running, no dead ASTRO mount
NDISP=$(display); BOOT="resets $(resets), displays connected $NDISP, busy $(busy && echo yes || echo no), dead mount $(deadmnt && echo yes || echo no)"
say "boot check: $BOOT"
if [ "$DRY" = 1 ]; then
    say "DRY: plan C1 O1 C2 O2 C3 O3 (lean, MangoHud, $SECS s; O with BC5_DIRECT_AGC_EOP_IDENT=1); lock now [$(cat "$LOCK")]; busy $(busy && echo yes || echo no); dead mount $(deadmnt && echo yes || echo no)"
    exit 0
fi
[ "$BOOT" = "resets 0, displays connected $NDISP, busy no, dead mount no" ] && [ "$NDISP" -ge 1 ] || { say "STOP: the boot check failed"; exit 1; }
LINE="exp0439 | ae439 lean A/B on ASTRO BOT $P (6 lean, $SECS s each), token $(date +%s)$$ | $(date '+%F %T')"
[ -e "$LOCK" ] || touch "$LOCK"
[ -f "$LOCK" ] && [ ! -L "$LOCK" ] && [ ! -s "$LOCK" ] || { echo "the box is locked: $(cat "$LOCK")"; exit 1; }
tl=$LOCK.0439ae-$$.new; al=$LOCK.0439ae-$$.aside
printf '%s\n' "$LINE" > "$tl" && mv -T "$LOCK" "$al" && ln "$tl" "$LOCK" || { [ -e "$LOCK" ] || mv -T "$al" "$LOCK"; rm -f "$tl"; echo "the claim failed"; exit 1; }
if [ -s "$al" ]; then mv -fT "$al" "$LOCK"; rm -f "$tl"; echo "a foreign line arrived during the claim: not started"; exit 1; fi
rm -f "$al" "$tl"
finish() {
    sync
    if busy; then say "LOCK KEPT: left: $(pgrep -ax 'kyty_emulator|bc5-mount' | cut -c1-60 | tr '\n' ' ')"; exit "$1"; fi
    if [ -f "$LOCK" ] && grep -qxF -- "$LINE" "$LOCK"; then t=$LOCK.0439ae-$$.rel; grep -vxF -- "$LINE" "$LOCK" > "$t"; mv -fT "$t" "$LOCK"; fi
    say "lock released: [$(cat "$LOCK")]"
    exit "$1"
}
stats() { # $1 tag: MangoHud's csv, from 30 s of its own clock
    local f; f=$(ls -t "$R/$1-mh"/*.csv 2> /dev/null | grep -v summary | head -1)
    [ -n "$f" ] || { echo "no MangoHud log"; return; }
    awk -F, 'h == 0 && /^fps,/ {for (i = 1; i <= NF; i++) {if ($i == "frametime") ft = i; if ($i == "elapsed") el = i}; h = 1; next}
      h == 1 && ft > 0 && el > 0 {t = $el / 1e9; if (t < 30) next; if (t0 == "") t0 = t; t1 = t; v[n++] = $ft; if ($ft > 50) o++}
      END {if (n < 2) {print "too few frames"; exit}; asort(v); printf "frames %d in %.1f s, flips/s %.2f, frame time median %.2f p95 %.2f p99 %.2f max %.2f ms, over 50 ms %d\n", n, t1 - t0, (n - 1) / (t1 - t0), v[int(n * 0.5)], v[int(n * 0.95)], v[int(n * 0.99)], v[n], o + 0}' "$f"
}
run() { # $1 arm tag, $2 binary, $3 md5, $4 lean 1/0, $5 extra KEY=VALUE or empty
    local t=$P$1 line lss
    busy && { say "STOP before $t: an emulator or bc5-mount runs"; finish 1; }
    deadmnt && { say "STOP before $t: a dead ASTRO mount inside the container"; finish 1; }
    local mh=()
    if [ "$4" = 1 ]; then
        mkdir -p "$R/$t-mh"
        mh=(MANGOHUD=1 "MANGOHUD_CONFIG=fps_only=1,alpha=0,background_alpha=0,autostart_log=1,log_interval=0,output_folder=$R/$t-mh,log_duration=$MHD")
        /usr/bin/bash "$W/lean-session.sh" stop $$ > /dev/null 2>&1; lss=$?
        [ "$lss" = 0 ] || { say "STOP: lean-session.sh stop exit $lss before $t"; finish 1; }
    fi
    line=$(cd "$N" && CHAIN_LOCKLINE=$LINE P_BIN=$2 P_WANT=$3 bash ./start0413g.sh "$t" astro "$SECS" BC5_FAULT_RECORD=1 ${5:+"$5"} "${mh[@]}" 2>&1 | tail -1)
    [ "$4" = 1 ] && /usr/bin/bash "$W/lean-session.sh" restore $$ > /dev/null 2>&1
    say "$t: $line"
    [ "$4" = 1 ] && say "$t: $(stats "$t")"
    case "$line" in *"PASS: ran $SECS s"*"kernel lines 0, crash lines 0"*) ;; *) say "STOP: $t did not pass"; finish 1 ;; esac
    sleep 5
}
for a in C1:C O1:O C2:C O2:O C3:C O3:O; do
    t=${a%%:*}; k=${a##*:}
    if [ "$k" = C ]; then run "$t" "$CB" "$MC" 1 ""; else run "$t" "$OB" "$MO" 1 BC5_DIRECT_AGC_EOP_IDENT=1; fi
done
finish 0
