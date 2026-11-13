#!/usr/bin/env bash
# BC5 exp 0417, the K1r fold (candidate patch P_NEW12: c55174b1 + exp 0412's rl412, K1r, fault record, watch, probe,
# first-fail catchers and save guard, K1r and the fault record ON by default, + the EOP counter): the private rebuild
# with a private backend archive, the CPU tests and the checks, ONE lock line for the whole chain (chainlock0417.inc).
# Private directories only (~/bc5-work/exp0413/p and /n). The chain STOPS at a failed build, a failed CPU test, or the
# first run that is not clean (a kernel line, a crash line, a run that did not reach its end, a new fault record).
#   build   p0417c.sh (tree, private backend and its tests, normal and lean); cpu0417c.sh (sources in $N/cpu12)
#   ASTRO BOT (K1r's first runs on this title), 120 s:  c1a, c2a plain     c3d KYTY_BC5_SWITCH_DEFAULTS=0
#   second title, RT on, no zero skip, exp 0415's counters to a file:
#     c4, c5     the scripted walk to G+240, nothing set (K1r and the fault record on by default)
#     c6cut      the cutscene arm: exp 0412's read-only snapshot of 2026-11-13, slot 4, no input, 240 s
#     c8k0       the walk with BC5_GUARD_K1R=0: the old path is reachable
#     c9eop      the walk with BC5_R3_SUBMIT_EOP_EVENT=1 BC5_R3_EOP_STAT=1: the largest count of chained EOP
#                publications between a push and its callback (the old ring wrapped at 4096)
#   lean, 120 s (c7), before c8k0
# usage (on the box, detached): P_NEW12=<patch md5> chk0417c.sh     MODE=resume: the runs only     MODE=post: on the SHARED binaries
set -u
ulimit -c 0
export LC_ALL=C
W=$HOME/bc5-work; E=$W/exp0413; N=$E/n; P=$E/p; R=$N/raw; FR=$HOME/bc5-data/captures/faults
cd "$N" || exit 1
. "$N/chainlock0417.inc"
halt() { echo "chk0417c STOP: $*"; echo "chk0417c ended $(date +%T): STOPPED"; exit 1; }   # the EXIT trap frees the chain's lock
chain_claim "exp 0417 K1r fold: private build, CPU tests, ASTRO BOT, the second title, lean (${MODE:-full})" 85 || { echo "chk0417c ended $(date +%T): NOT STARTED"; exit 1; }
T_CHAIN=$(date +%s)
recs() { find "$FR" -mindepth 1 -maxdepth 1 -type d -newermt "@$1" 2> /dev/null | wc -l; }
# nl412 removed the read of the default learned file (ASTRO BOT named none and read this one); it is moved away, not deleted
if [ -f "$W/direct-learned.txt" ]; then mkdir -p "$W/trash-20261113" && mv -n "$W/direct-learned.txt" "$W/trash-20261113/direct-learned.txt" && echo "moved ~/bc5-work/direct-learned.txt to trash-20261113 (patch 0001 no longer reads it)"; fi
if [ "${MODE:-}" = post ]; then
    BN=$W/kytyplus-build/src/kyty_emulator; BL=$W/kytyplus-build-lean/src/kyty_emulator; X=s
elif [ "${MODE:-}" = resume ]; then
    BN=$P/build-normal/src/kyty_emulator; BL=$P/build-lean/src/kyty_emulator; X=p
else
    : "${P_NEW12:?the patch md5}"
    (cd "$P/kit" && P_NEW12=$P_NEW12 bash ./p0417c.sh) > "$P/p0417c.log" 2>&1
    grep "^recipe check\|^private backend archive\|^backend tests\|done; normal\|^lock released" "$P/p0417c.log" | cut -c1-260
    grep -q "^lock released" "$P/p0417c.log" && grep -q " done; normal " "$P/p0417c.log" ||
        { grep -m8 "error:\|STOP\|differs\|lacks\|holds" "$P/p0417c.log" "$P"/build-*.build.log "$P"/backend-build.build.log 2> /dev/null | cut -c1-300; halt "the build did not end clean"; }
    bash "$N/cpu12/cpu0417c.sh" || halt "a CPU test failed"
    BN=$P/build-normal/src/kyty_emulator; BL=$P/build-lean/src/kyty_emulator; X=p
fi
MN=$(md5sum < "$BN" | cut -d' ' -f1); ML=$(md5sum < "$BL" | cut -d' ' -f1)
echo "binaries ($X): normal $MN lean $ML"
export P_BIN=$BN P_WANT=$MN
clean() {  # the step's own result line, the words a clean end has, the step's start (epoch)
    echo "$1"
    local n; n=$(recs "$3")
    [ "$n" = 0 ] || halt "$n new fault record(s) under $FR since this step began: a finding, read record.txt there"
    case "$1" in *"$2"*"kernel lines 0, crash lines 0"*) ;; *) halt "not a clean run: $(echo "$1" | cut -c1-160)" ;; esac
}
LINES="exp 0415: APR reads\|pending cap\|physmap sorted\|ranges fast\|acb state restore\|zero guards behind\|set-buffer with the map\|k1r\|K1r\|K1w\|would learn\|fault record\|exp 0412"
astro() {  # tag, words...
    local tag=$1 t0; t0=$(date +%s); shift
    local line; line=$(bash ./sweep0413g.sh "$tag" 120 "0" "$@" | grep "^n=0:")
    echo "$tag lines: $(grep -a -h "$LINES" "$R/${tag}0-play.log" 2> /dev/null | sed 's/\[bc5\] //' | cut -c1-110 | sort | uniq -c | sort -rn | head -14 | tr -s ' ' | tr '\n' ';')"
    clean "$line" "PASS: ran 120 s" "$t0"
}
astro c1${X}a
astro c2${X}a
astro c3${X}d KYTY_BC5_SWITCH_DEFAULTS=0
second() {  # tag, words and N_* settings (NAME=VALUE; N_* go to the runner's environment)
    local tag=$1 t0; t0=$(date +%s); shift
    local envs=() words=() w
    for w in "$@"; do case "$w" in N_*) envs+=("$w") ;; *) words+=("$w") ;; esac; done
    setsid nohup python3 ./fault0416.py "$R/$tag-faults.txt" 460 < /dev/null > /dev/null 2>&1 &
    local fp=$!
    local line; line=$(env "${envs[@]}" P_WORDS=$N/words0413nz.txt bash ./run0413p.sh "$tag" nozeroskip 240 KYTY_BC5_LOAD_STAT="$R/$tag-loadstat.txt" "${words[@]}" | grep "^$tag ")
    kill "$fp" 2> /dev/null; sleep 4
    local J; J=$(sed -n 's/^journal \([^ ]*\) .*$/\1/p' "$R/$tag-journal.txt" 2> /dev/null)
    echo "$tag lines: $(grep -a -h "$LINES" "$R/$tag-play.log" 2> /dev/null | sed 's/\[bc5\] //' | cut -c1-110 | sort | uniq -c | sort -rn | head -12 | tr -s ' ' | tr '\n' ';')"
    echo "$tag journal: removed-line $(grep -a -c 'learned windows: removed from this build' "$J" 2> /dev/null), k1r banner $(grep -a -c 'BC5_GUARD_K1R on' "$J" 2> /dev/null), k1r lines $(grep -a -c -i 'k1r' "$J" 2> /dev/null), would-learn $(grep -a -c '^would learn' "$J" 2> /dev/null), timeout-fault $(grep -a -c '^timeout: fault' "$J" 2> /dev/null), eop stat: $(grep -a '^eop stat' "$J" 2> /dev/null | tail -1 | cut -c1-150); last k1r: $(grep -a -i 'k1r' "$J" 2> /dev/null | tail -1 | cut -c1-200)"
    echo "$tag route: $(grep -h 'route:' "$R/$tag-start.txt" 2> /dev/null | tail -2 | tr '\n' ';' | cut -c1-240); catcher: $(grep -c ' fault: ' "$R/$tag-faults.txt" 2> /dev/null) fault lines; watchdog: $(tail -1 "$R/$tag-watchdog.txt" 2> /dev/null | cut -c21-140)"
    local bad; bad=$(grep -a -c 'IT MUST BE ZERO\|fault record (exp 0412, tag fr412): written to' "$J" 2> /dev/null)
    [ "${bad:-0}" = 0 ] || halt "$tag: the journal has $bad line(s) that a clean run must not have (a non-zero zero buffer, or a fault record written)"
    clean "$line" "ended at G+240" "$t0"
    sleep 5
}
second c4${X}
second c5${X}
second c6${X}cut N_SAVES=$HOME/bc5-data/saves/PPSA03671-20261113-0914-cutscene N_SLOT=4 N_NOWALK=1
t0=$(date +%s)
clean "$(P_BIN=$BL P_WANT=$ML P_WORDS=$N/words0413nz.txt bash ./start0413l.sh c7${X} lean 120 | grep "^c7${X} ")" "PASS: ran 120 s" "$t0"
second c8${X}k0 BC5_GUARD_K1R=0
second c9${X}eop BC5_R3_SUBMIT_EOP_EVENT=1 BC5_R3_EOP_STAT=1
echo "fault records since the chain began: $(recs "$T_CHAIN")"
echo "chk0417c ended $(date +%T): all clean"
