#!/usr/bin/env bash
# BC5 exp 0438 (tag r438o): the check before r438o's bake, on a clean boot (the top session's order of 2026-11-21).
# ASTRO BOT (the second title is uninstalled), no input, through exp 0413's start0413g.sh (its derived ASTRO launcher,
# a private _SaveData), each run 180 s:
#   C  the shared lean d3485ed4 (control)        O  the private r438o lean aae9c294
#   in the order C O C O C O; MangoHud's own per-frame log is the frame counter (MANGOHUD_CONFIG autostart_log, as
#   exp 0430's N_MH), the Plasma shell stopped for each lean run as the lean shortcut does (lean-session.sh);
#   N  then one run of the private r438o NORMAL 0c3a60fb for r438's 60-s line with r438o's counters (early writes,
#      renumbered, kept by the trim, BUG lines) and the GIVEN UP lines. Its frame numbers are diagnosis only.
# One BOX-LOCK line for the whole chain (start0413g.sh inherits it), ulimit -c 0. Before each run: no emulator, no
# bc5-mount, no dead ASTRO mount inside the container. Stops at the first failed run or kernel line. Per lean run:
# frames and frame times from 30 s of MangoHud's clock to its end (mean fps, frame time p50 / p99 / max, frames over
# 50 ms). DRY=1: checks and prints the plan, starts nothing, takes no lock.
#   bash ab438o.sh <tag-prefix>      (on the box, detached under the user manager, e.g.
#   systemd-run --user --unit=bc5-ab438o --collect sh -c 'bash ~/bc5-work/exp0438/r438okit/ab438o.sh q438oA > ~/bc5-work/exp0438/r438o/ab.log 2>&1')
set -u
ulimit -c 0
export LC_ALL=C
P=${1:?tag prefix}; W=$HOME/bc5-work; N=$W/exp0413/n; R=$N/raw; LOCK=$W/BOX-LOCK; DRY=${DRY:-0}
CB=$W/kytyplus-build-lean/src/kyty_emulator; OB=$W/exp0438/r438o/lean/kyty_emulator; NB=$W/exp0438/r438o/normal/kyty_emulator
M=$HOME/bc5-data/mnt/PPSA21567; SECS=180; MHD=170
S=$R/$P-ab438o.txt
m() { md5sum < "$1" | cut -d' ' -f1; }
say() { echo "$(date +%T) $*" | tee -a "$S"; }
case "$P" in *[!A-Za-z0-9]* | "") echo "the tag prefix is letters and digits"; exit 1 ;; esac
MC=$(m "$CB"); MO=$(m "$OB"); MN=$(m "$NB")
[ "${MC:0:8}" = d3485ed4 ] && [ "${MO:0:8}" = aae9c294 ] && [ "${MN:0:8}" = 0c3a60fb ] || { echo "binaries: control ${MC:0:8}, r438o lean ${MO:0:8}, normal ${MN:0:8}: not the pinned ones"; exit 1; }
for a in C1 O1 C2 O2 C3 O3 N1; do [ -e "$R/$P$a-start.txt" ] && { echo "tag $P$a already used"; exit 1; }; done
deadmnt() { distrobox enter ubuntu -- sh -c 'M=$1; if mountpoint -q "$M" && ! head -c1 "$M/sce_sys/param.json" > /dev/null 2>&1; then echo dead; fi' _ "$M" 2> /dev/null < /dev/null | grep -q dead; }
busy() { pgrep -x kyty_emulator > /dev/null || pgrep -x bc5-mount > /dev/null; }
mkdir -p "$R"
echo "$(date '+%F %T') $P: boot $(cut -c1-8 /proc/sys/kernel/random/boot_id), up $(cut -d' ' -f1 /proc/uptime) s, kernel $(uname -r); control ${MC:0:8}, r438o lean ${MO:0:8}, normal ${MN:0:8}" > "$S"
if [ "$DRY" = 1 ]; then
    say "DRY: plan C1 O1 C2 O2 C3 O3 (lean, MangoHud, $SECS s) then N1 (normal, $SECS s); lock now [$(cat "$LOCK")]; busy $(busy && echo yes || echo no); dead mount $(deadmnt && echo yes || echo no)"
    exit 0
fi
LINE="exp 0438 | r438o lean A/B on ASTRO BOT $P (6 lean + 1 normal, $SECS s each), token $(date +%s)$$ | $(date '+%F %T')"
[ -e "$LOCK" ] || touch "$LOCK"
[ -f "$LOCK" ] && [ ! -L "$LOCK" ] && [ ! -s "$LOCK" ] || { echo "the box is locked: $(cat "$LOCK")"; exit 1; }
tl=$LOCK.0438ab-$$.new; al=$LOCK.0438ab-$$.aside
printf '%s\n' "$LINE" > "$tl" && mv -T "$LOCK" "$al" && ln "$tl" "$LOCK" || { [ -e "$LOCK" ] || mv -T "$al" "$LOCK"; rm -f "$tl"; echo "the claim failed"; exit 1; }
if [ -s "$al" ]; then mv -fT "$al" "$LOCK"; rm -f "$tl"; echo "a foreign line arrived during the claim: not started"; exit 1; fi
rm -f "$al" "$tl"
finish() {
    sync
    if busy; then say "LOCK KEPT: left: $(pgrep -ax 'kyty_emulator|bc5-mount' | cut -c1-60 | tr '\n' ' ')"; exit "$1"; fi
    if [ -f "$LOCK" ] && grep -qxF -- "$LINE" "$LOCK"; then t=$LOCK.0438ab-$$.rel; grep -vxF -- "$LINE" "$LOCK" > "$t"; mv -fT "$t" "$LOCK"; fi
    say "lock released: [$(cat "$LOCK")]"
    exit "$1"
}
stats() { # $1 tag: MangoHud's csv, from 30 s of its own clock
    local f; f=$(ls -t "$R/$1-mh"/*.csv 2> /dev/null | grep -v summary | head -1)
    [ -n "$f" ] || { echo "no MangoHud log"; return; }
    awk -F, 'h == 0 && /^fps,/ {for (i = 1; i <= NF; i++) {if ($i == "frametime") ft = i; if ($i == "elapsed") el = i}; h = 1; next}
      h == 1 && ft > 0 && el > 0 {t = $el / 1e9; if (t < 30) next; if (t0 == "") t0 = t; t1 = t; v[n++] = $ft; if ($ft > 50) o++}
      END {if (n < 2) {print "too few frames"; exit}; asort(v); printf "frames %d in %.1f s, mean %.2f fps, frame time p50 %.2f p99 %.2f max %.2f ms, over 50 ms %d\n", n, t1 - t0, (n - 1) / (t1 - t0), v[int(n * 0.5)], v[int(n * 0.99)], v[n], o + 0}' "$f"
}
run() { # $1 arm tag, $2 binary, $3 md5, $4 lean 1/0
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
    line=$(cd "$N" && CHAIN_LOCKLINE=$LINE P_BIN=$2 P_WANT=$3 bash ./start0413g.sh "$t" astro "$SECS" BC5_FAULT_RECORD=1 "${mh[@]}" 2>&1 | tail -1)
    [ "$4" = 1 ] && /usr/bin/bash "$W/lean-session.sh" restore $$ > /dev/null 2>&1
    say "$t: $line"
    [ "$4" = 1 ] && say "$t: $(stats "$t")"
    case "$line" in *"PASS: ran $SECS s"*"kernel lines 0, crash lines 0"*) ;; *) say "STOP: $t did not pass"; finish 1 ;; esac
    sleep 5
}
for a in C1:C O1:O C2:C O2:O C3:C O3:O; do
    t=${a%%:*}; k=${a##*:}
    if [ "$k" = C ]; then run "$t" "$CB" "$MC" 1; else run "$t" "$OB" "$MO" 1; fi
done
run N1 "$NB" "$MN" 0
say "N1 r438 lines: $(grep -ac 'r438 (exp 0438, b438)' "$R/${P}N1-play.log"), BUG $(grep -ac 'r438 (exp 0438, b438): BUG' "$R/${P}N1-play.log"), GIVEN UP $(grep -aci 'given up' "$R/${P}N1-play.log")"
grep -a 'r438 (exp 0438, b438): t ' "$R/${P}N1-play.log" | tail -3 | tee -a "$S"
finish 0
