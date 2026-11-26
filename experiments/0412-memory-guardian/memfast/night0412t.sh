#!/usr/bin/env bash
# BC5 exp 0412, the night of 2026-11-14 (the top session's GO: the box until 07:00; README section 85). One chain, one
# lock line. The second title's long walks to G+620 on exp 0412's private build g412zf (candidate F + default-off
# switches; bin-n), a private save copy reset from exp 0412's named snapshot before every arm, RT on, fuse and watchdog:
#   F<n>  the build's defaults (K1r on), catchers on
#   W<n>  arm w0: BC5_GUARD_WRITERS=2 with the zero scan (a diagnostic arm; counted apart from F)
#   B1    arm b1: BC5_GUARD_BYDATA_NAMES=CommitIABufferAllocator, ONCE, and only after two clean W arms
# In every arm: KYTY_BC5_MEM_FIRSTFAIL=1 KYTY_BC5_TRAP_LOG=1 BC5_GUARD_COVER_LOG=1, the fault record (on by default),
# the sampler every 5 s, pad keys recorded.
# A fault is an arm's RESULT: its record, the first failed memory call, the memory at that moment and the last K1r,
# cover-log and writers lines are printed, and the next arm runs. The chain stops on a failed GPU reset, on two SETUP
# or ROUTE endings in a row, and starts no arm after N8_LAST (default 06:40). A reboot ends it by itself: nothing
# restarts it.
# night0412t (mkt0412.py from night0412i.sh): the night series on test build T (exp 0419's night-series-T.md): arms
# tA tJ tP tD in turn, up to T_MAX walks, until T_LAST, the stop file $N/STOP-n12 or the first walk that is not clean.
# start: T_BIN=... T_WANT=<md5> T_WORDS=... N8_WORDS_MD5=<8> night0412t.sh   (T_FIRST=<k> to resume the count)
# night0412i was (mki0412.py from night0412h.sh, README section 93): the second chain resumed, n10F3..n10F8; the title's
# known CPU fault (eboot.bin+0x1b349f, exit 65, nothing from the kernel or the GPU) is recorded and does not stop it.
# night0412h was (mkh0412.py from night0412g.sh, README section 92): the second chain, tags n10F1..n10F8; odd arms with
# BC5_DISPATCH_COUNT=1, even arms with BC5_DISPATCH_COUNT=0; stop file $N/STOP-n10.
# night0412g was (mkzg0412.py from night0412b.sh, README section 91): build g412zg in bin-g; F arms only, n9F1..n9F8, with
# BC5_TIMEOUT_LAYOUT, BC5_DISPATCH_COUNT, BC5_FAULT_POINTERS and the timeout snapshot; a stop file looked at before
# every arm (touch $N/STOP-n9: the arm in flight ends by itself, no later arm starts); N9_DRY=1 with the stop file
# present is the dry check of that path (claims, sees the file, releases; no arm).
# night0412b was (mknight0412b.py): stop first, F and W arms only from number 7, the claim inside a mkdir mutex.
# usage (on the box, detached): night0412t.sh
set -u
ulimit -c 0
export LC_ALL=C
W=$HOME/bc5-work; X=$W/exp0412; N=$X/n8; R=$N/raw; FR=$HOME/bc5-data/captures/faults; LOCK=$W/BOX-LOCK
mkdir -p "$R" && cd "$N" || exit 1
BIN=${T_BIN:?the path of the kyty_emulator of T}; [ -x "$BIN" ] || { echo "night0412 ended $(date +%T): NOT STARTED, no binary $BIN"; exit 1; }
MD=$(md5sum < "$BIN" | cut -d' ' -f1)
[ "$MD" = "${T_WANT:?the md5 of the binary of T}" ] || { echo "night0412 ended $(date +%T): NOT STARTED, $BIN is $MD, not $T_WANT"; exit 1; }
STOPF=$N/STOP-n12
if [ "${N9_DRY:-0}" = 1 ]; then [ -e "$STOPF" ] || { echo "night0412 ended $(date +%T): NOT STARTED, a dry check needs the stop file"; exit 1; }
else [ ! -e "$STOPF" ] || { echo "night0412 ended $(date +%T): NOT STARTED, the stop file $STOPF is there"; exit 1; }; fi
WORDS=${T_WORDS:?the words file of T}   # exp 0419's words for test build T, only read
[ -s "$WORDS" ] || { echo "night0412 ended $(date +%T): NOT STARTED, no words file $WORDS"; exit 1; }
[ "$(md5sum < "$WORDS" | cut -c1-8)" = "${N8_WORDS_MD5:?the words file md5}" ] || { echo "night0412 ended $(date +%T): NOT STARTED, the words file changed"; exit 1; }
pgrep '^kyty_emulator' > /dev/null && { echo "night0412 ended $(date +%T): NOT STARTED, an emulator runs"; exit 1; }
LAST=${T_LAST:-06:45}; TEND=$(date -d "$LAST" +%s); [ "$TEND" -gt "$(date +%s)" ] || TEND=$(date -d "tomorrow $LAST" +%s)
TMAX=${T_MAX:-60}; TFIRST=${T_FIRST:-1}
case "$TMAX$TFIRST" in *[!0-9]*) echo "night0412 ended $(date +%T): NOT STARTED, T_MAX and T_FIRST are numbers"; exit 1 ;; esac
CHAIN_LOCKLINE="guard exp 0412 | chain: the night series on test build T: long walks of the second title, arms tA tJ tP tD in turn, up to $TMAX walks or $LAST, stop at the first walk that is not clean (R55) | token $(date +%Y%m%d%H%M%S)$$ | $(date '+%F %T')"
MUT=$LOCK.d19-claim
mkdir "$MUT" 2> /dev/null || { echo "night0412 ended $(date +%T): NOT STARTED, another claim runs, or $MUT was left behind"; exit 1; }
unmut() { rmdir "$MUT" 2> /dev/null; }
[ -e "$LOCK" ] || touch "$LOCK"
[ -f "$LOCK" ] && [ ! -L "$LOCK" ] && [ ! -s "$LOCK" ] || { echo "night0412 ended $(date +%T): NOT STARTED, the box is locked: $(cat "$LOCK")"; unmut; exit 1; }
tl=$LOCK.0412c-$$.new; al=$LOCK.0412c-$$.aside
printf '%s\n' "$CHAIN_LOCKLINE" > "$tl" && mv -T "$LOCK" "$al" && ln "$tl" "$LOCK" || { [ -e "$LOCK" ] || mv -T "$al" "$LOCK"; rm -f "$tl"; echo "night0412 ended $(date +%T): NOT STARTED, the claim failed"; unmut; exit 1; }
if [ -s "$al" ]; then mv -fT "$al" "$LOCK"; rm -f "$tl"; echo "night0412 ended $(date +%T): NOT STARTED, a foreign line arrived during the claim"; unmut; exit 1; fi
rm -f "$al" "$tl"
unmut
[ "$(cat "$LOCK")" = "$CHAIN_LOCKLINE" ] || { echo "night0412 ended $(date +%T): NOT STARTED, the lock does not read back as ours"; exit 1; }
export CHAIN_LOCKLINE
printf '%s\n' "guard exp 0412 | claimed: $CHAIN_LOCKLINE" >> "$W/BOX-QUEUE"
echo "chain lock: $CHAIN_LOCKLINE"
PADS=()
padstop() { [ ${#PADS[@]} = 0 ] || kill "${PADS[@]}" 2> /dev/null; PADS=(); }
fin() {
    padstop
    if [ -f "$LOCK" ] && grep -qxF -- "$CHAIN_LOCKLINE" "$LOCK"; then
        grep -vxF -- "$CHAIN_LOCKLINE" "$LOCK" > "$LOCK.0412c-$$.rel"; mv -fT "$LOCK.0412c-$$.rel" "$LOCK"
        printf '%s\n' "guard exp 0412 | released: chain, $(date '+%F %T')" >> "$W/BOX-QUEUE"; echo "chain lock released"
    else echo "the lock no longer holds our line, left as it is: $(cat "$LOCK" 2> /dev/null)"; fi
}
trap fin EXIT
BOOT=$(cat /proc/sys/kernel/random/boot_id)
ZN=$(sed -n 's/^export BC5_DIRECT_EAGER_NAMES="\(.*\)"$/\1/p' "$X/play-pkg-0412.sh" | head -1)
[ -n "$ZN" ] || { echo "night0412 ended $(date +%T): NOT STARTED, no BC5_DIRECT_EAGER_NAMES line in the launcher"; exit 1; }
echo "binary $MD ($BIN); words $WORDS; walks $TFIRST..$TMAX; boot ${BOOT:0:8}; kernel $(uname -r); $(grep MemAvailable /proc/meminfo | tr -s ' '); last arm starts by $LAST"
CATCH=(KYTY_BC5_AUDIO_TRAIL=1 KYTY_BC5_MEM_FIRSTFAIL=1 KYTY_BC5_TRAP_LOG=1 BC5_GUARD_COVER_LOG=1 BC5_TIMEOUT_LAYOUT=1 BC5_FAULT_POINTERS=1 BC5_DIRECT_SNAP_ON_TIMEOUT=11a5ae8000:1572864)
CLEAN=0; BADSETUP=0
at() {  # tag, second: "avail MiB / GTT MiB" of the sampler's first line at or after that second
    awk -F'|' -v s="$2" '$1 + 0 >= s { split($2, a, " "); g = $5; gsub(/ /, "", g); print a[1] " / " g; exit }' "$R/$1-sampler.txt" 2> /dev/null
}
known_cpu_fault() {  # tag, the arm's start (epoch): 0 when the arm ended by the title's known CPU fault and nothing else
    local tag=$1 t0=$2 J
    grep -aq 'off=00000000001b349f, module=eboot.bin' "$R/$tag-play.log" 2> /dev/null || return 1
    grep -aq 'exit 65$' "$R/$tag-crash.txt" 2> /dev/null || return 1
    [ "$(grep -c . "$R/$tag-dmesg-after.txt" 2> /dev/null)" = 0 ] || return 1
    [ -z "$(find "$FR" -mindepth 1 -maxdepth 1 -type d -newermt "@$t0" 2> /dev/null | head -1)" ] || return 1
    J=$(sed -n 's/^journal \([^ ]*\) .*$/\1/p' "$R/$tag-journal.txt" 2> /dev/null)
    [ -n "$J" ] && [ -e "$J" ] || return 1
    [ "$(ls "$(dirname "$J")" | grep -c '^timeout-')" = 0 ] || return 1
    [ "$(grep -a -c '^timeout: \|tag tl412' "$J")" = 0 ] || return 1
    return 0
}
arm() {  # tag, kind (F, W, B), words...
    local tag=$1 kind=$2 t0 d n=0 J line PADN; t0=$(date +%s); shift 2; CLEAN=0; KNOWN=0
    echo "== $(date +%T) $tag: $(echo "${*:-no extra word}" | cut -c1-260)"
    : > "$R/$tag-pad.txt"
    for d in /dev/input/by-id/*-event-joystick; do
        [ -e "$d" ] || continue
        n=$((n + 1))
        stdbuf -oL evtest "$d" 2> /dev/null | grep --line-buffered 'EV_KEY.*value 1' >> "$R/$tag-pad.txt" &
        PADS+=($!)
    done
    line=$(N_FUSE="13000 2048" N_WD_MIB=220 P_BIN="$BIN" P_WANT="$MD" P_WORDS="$WORDS" bash "$N/run0412p.sh" "$tag" "n8$kind" 620 KYTY_BC5_LOAD_STAT="$R/$tag-loadstat.txt" "${CATCH[@]}" "$@" | grep "^$tag ")
    padstop; pkill -u "$USER" -x evtest 2> /dev/null
    J=$(sed -n 's/^journal \([^ ]*\) .*$/\1/p' "$R/$tag-journal.txt" 2> /dev/null)
    PADN=$(wc -l < "$R/$tag-pad.txt")
    echo "${line:-$tag: NO SUMMARY LINE ($(tail -1 "$R/$tag-end.txt" 2> /dev/null))}"
    echo "$tag journal $J"
    echo "$tag route: $(grep -h 'route:' "$R/$tag-start.txt" 2> /dev/null | tr '\n' ';' | cut -c1-300); watchdog: $(tail -1 "$R/$tag-watchdog.txt" 2> /dev/null | cut -c21-140)"
    echo "$tag input: $n joystick(s) watched, pad key presses $PADN"
    echo "$tag avail / GTT MiB at 420 s: $(at "$tag" 420); at 600 s: $(at "$tag" 600); lowest avail: $(awk -F'|' '$1 + 0 > 0 { split($2, a, " "); v = a[1] + 0; if (m == "" || v < m) { m = v; t = $1 + 0 } } END { print m " at " t " s" }' "$R/$tag-sampler.txt" 2> /dev/null)"
    echo "$tag armed: first-failure $(grep -a -c 'KYTY_BC5_MEM_FIRSTFAIL on, armed' "$R/$tag-play.log" 2> /dev/null), trap $(grep -a -c 'KYTY_BC5_TRAP_LOG on' "$R/$tag-play.log" 2> /dev/null), cover log $(grep -a -c 'BC5_GUARD_COVER_LOG on, armed' "$J" 2> /dev/null)"
    echo "$tag first-failure lines: $(grep -a -c 'mem firstfail (exp 0412, tag ff412): failure' "$R/$tag-play.log" 2> /dev/null)"; grep -a -A1 'mem firstfail (exp 0412, tag ff412): failure' "$R/$tag-play.log" 2> /dev/null | head -4 | cut -c1-300
    echo "$tag cover-log lines: $(grep -a -c '^cover log (exp 0412, tag kc412): t ' "$J" 2> /dev/null); the last two:"; grep -a '^cover log (exp 0412, tag kc412): t ' "$J" 2> /dev/null | tail -2 | cut -c1-260
    echo "$tag k1r, last line: $(grep -a '^k1r (exp 0412, tag k1r412): t ' "$J" 2> /dev/null | tail -1 | cut -c1-200)"
    echo "$tag desc targets: $(grep -a '^desc targets (exp 0412, tag dt412): t [0-9]* s: mode' "$J" 2> /dev/null | tail -1 | cut -c1-220)"
    echo "$tag audio trail: $(grep -a -c 'exp 0419 ajt:' "$R/$tag-play.log" 2> /dev/null) line(s); the last: $(grep -a 'exp 0419 ajt:' "$R/$tag-play.log" 2> /dev/null | tail -1 | cut -c1-200)"
    echo "$tag dispatch count: $(grep -a '^dispatch count (exp 0412, tag dc412): t ' "$J" 2> /dev/null | tail -1 | cut -c1-240)"
    echo "$tag timeout layout: $(grep -a -c 'tag tl412' "$J" 2> /dev/null) line(s); files: $(ls "$(dirname "$J")" 2> /dev/null | grep -c '^timeout-')"
    echo "$tag journal: would-learn $(grep -a -c '^would learn' "$J" 2> /dev/null), timeout-fault $(grep -a -c '^timeout: fault' "$J" 2> /dev/null), fault record lines $(grep -a -c 'fault record (exp 0412' "$J" 2> /dev/null), k1f lines $(grep -a -c 'tag k1f412' "$J" 2> /dev/null)"
    if [ "$kind" = W ]; then
        echo "$tag soft-dirty: $(grep -a 'tag wc412' "$J" 2> /dev/null | grep -a -m2 'soft-dirty: \|NOT available' | cut -c1-240 | tr '\n' ';')"
        echo "$tag writers lines: $(grep -a -c '^writers (exp 0412' "$J" 2> /dev/null); zero scan lines $(grep -a -c '^zero scan' "$J" 2> /dev/null)"
        grep -a '^writers (exp 0412, tag wc412): scan' "$J" 2> /dev/null | grep -a -v ': of the 0 NOT named' | tail -12 | cut -c1-300
    fi
    [ "$kind" = B ] && { echo "$tag by-data: $(grep -a -m1 'tag bd412' "$R/$tag-play.log" 2> /dev/null | cut -c1-200)"; grep -a 'tag bd412' "$J" 2> /dev/null | head -2 | cut -c1-240; }
    for d in $(find "$FR" -mindepth 1 -maxdepth 1 -type d -newermt "@$t0" 2> /dev/null | sort); do
        echo "$tag FAULT RECORD $d"
        grep -a -m1 '^what the host saw' "$d/record.txt" | cut -c1-300
        grep -a -m1 '^when' "$d/record.txt" | cut -c1-120
        grep -a -i -m6 'timed out\|acb #\|dcb #\|page fault\|under the read-only zero cover' "$d/journal-tail.txt" 2> /dev/null | cut -c1-300
    done
    if [ -s "$R/$tag-crash.txt" ]; then echo "$tag crash text:"; grep -a -m4 'exception_address\|Access violation\|access_violation_vaddr\|Segmentation\|Aborted' "$R/$tag-crash.txt" | cut -c1-200; fi
    case "$line" in
        *"ended at G+620"*"kernel lines 0, crash lines 0"*) if [ -z "$(find "$FR" -mindepth 1 -maxdepth 1 -type d -newermt "@$t0" 2> /dev/null | head -1)" ]; then CLEAN=1; else echo "$tag: a NEW FAULT RECORD"; fi ;;
        *) echo "$tag: NOT a clean run"
           echo "$tag memory, the journal's last three lines:"; grep -a '^memory (exp 0401)' "$J" 2> /dev/null | tail -3 | cut -c1-200
           echo "$tag sampler, the last three lines:"; tail -3 "$R/$tag-sampler.txt" 2> /dev/null | cut -c1-160
           echo "$tag kernel lines: $(grep -c . "$R/$tag-dmesg-after.txt" 2> /dev/null)"; grep -i 'timeout\|reset\|fault' "$R/$tag-dmesg-after.txt" 2> /dev/null | cut -c1-200 | head -6
           [ "$kind" = W ] && { echo "$tag writers, the last lines:"; grep -a '^writers (exp 0412' "$J" 2> /dev/null | tail -3 | cut -c1-260; } ;;
    esac
    if [ "$CLEAN" = 0 ]; then case "$line" in *"ended by itself"*"kernel lines 0,"*) if known_cpu_fault "$tag" "$t0"; then
        KNOWN=1
        sed -n '/^kyty_exception_handler:/,/^--- Build ---/p' "$R/$tag-play.log" > "$R/$tag-cpufault.txt"
        echo "$tag: the title's KNOWN CPU FAULT (eboot.bin+0x1b349f), nothing from the kernel or the GPU: recorded in $R/$tag-cpufault.txt ($(wc -l < "$R/$tag-cpufault.txt") lines), the chain goes on"
        grep -a -m3 'access_violation_vaddr\|^Stack trace\|^guest rdi' "$R/$tag-cpufault.txt" | cut -c1-200
    fi ;; esac; fi
    case "$line" in *SETUP:* | *ROUTE:* | "") BADSETUP=$((BADSETUP + 1)) ;; *) BADSETUP=0 ;; esac
    if grep -qi 'reset.*fail\|fail.*reset\|MODE1' "$R/$tag-dmesg-after.txt" 2> /dev/null; then echo "night0412 STOP after $tag: the kernel reports a failed reset"; echo "night0412 ended $(date +%T): STOPPED"; exit 1; fi
    [ "$(cat /proc/sys/kernel/random/boot_id)" = "$BOOT" ] || { echo "night0412 ended $(date +%T): STOPPED, the boot id changed"; exit 1; }
    [ "$BADSETUP" -lt 2 ] || { echo "night0412 ended $(date +%T): STOPPED, two SETUP or ROUTE endings in a row"; exit 1; }
    [ "$CLEAN" = 1 ] || [ "$KNOWN" = 1 ] || { echo "night0412b STOP after $tag: the arm was not clean (stop first: no later arm starts)"; echo "night0412 ended $(date +%T): STOPPED"; exit 1; }
    sync; sleep 15
}
stopped() { if [ -e "$STOPF" ]; then echo "night0412t: the stop file is there, no further arm"; echo "night0412 ended $(date +%T): STOPPED by the stop file"; exit 0; fi; }
if [ "${N9_DRY:-0}" = 1 ]; then
    known_cpu_fault n10F2 "$(date +%s)" && echo "dry: n10F2 is the known CPU fault (right)" || echo "dry: n10F2 NOT known: WRONG"
    known_cpu_fault n10F1 "$(date +%s)" && echo "dry: n10F1 known: WRONG" || echo "dry: n10F1 is not it (right)"
fi
stopped
[ "${N9_DRY:-0}" = 1 ] && { echo "night0412 ended $(date +%T): a dry check ran past the stop file: WRONG"; exit 1; }
FCLEAN=0; FKNOWN=0; K=$TFIRST
while [ "$K" -le "$TMAX" ]; do
    stopped
    [ "$(date +%s)" -lt "$TEND" ] || { echo "night0412 ended $(date +%T): the time limit $LAST; walks done up to $((K - 1)), clean $FCLEAN, known CPU fault $FKNOWN"; exit 0; }
    RND=$(((K + 3) / 4))   # the round: the k-th walk of each arm
    case $(((K - 1) % 4)) in
        0) arm "n12A$RND" F "BC5_DISPATCH_COUNT=$((RND % 2))" ;;
        1) arm "n12J$RND" F BC5_DISPATCH_COUNT=1 KYTY_BC5_AJM_DEFER=1 KYTY_BC5_AJM_LIVE_IDS=1 ;;
        2) arm "n12P$RND" F BC5_DISPATCH_COUNT=1 KYTY_BC5_DIAG_UNFORCE=KYTY_BC5_APR_POSIX KYTY_BC5_APR_POSIX=0 ;;
        3) arm "n12D$RND" F BC5_DISPATCH_COUNT=1 BC5_GUARD_DESC_TARGETS=2 ;;
    esac
    if [ "$CLEAN" = 1 ]; then FCLEAN=$((FCLEAN + 1)); else FKNOWN=$((FKNOWN + 1)); fi
    echo "-- $(date +%T) so far: walk $K of $TMAX, clean $FCLEAN, known CPU fault $FKNOWN (this start)"
    K=$((K + 1))
done
echo "night0412 totals: walks $TFIRST..$TMAX: clean $FCLEAN, known CPU fault $FKNOWN: no GPU line"
echo "night0412 ended $(date +%T): the series is done"
