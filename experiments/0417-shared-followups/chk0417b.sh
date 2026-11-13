#!/usr/bin/env bash
# BC5 exp 0417, the next patch change (exp 0417's candidate + exp 0415 L5c + exp 0412 nl412 keep-guards +
# BC5_DIRECT_HEAP_GUARDS): the private rebuild, the CPU tests and the checks, one unattended chain. Private
# directories only (~/bc5-work/exp0413/p and /n, exp 0413's tools); every step takes and releases BOX-LOCK by itself
# and refuses when an emulator runs. The chain STOPS at a failed build, a failed CPU test, or the first run that is
# not clean (a kernel line, a crash line, a run that did not reach its end).
#   build   p0417b.sh: the private tree 33bddfa1 -> P_NEW11, normal and lean
#   cpu     cpu0417.sh (its sources in $N/cpu11)
#   ASTRO BOT, 120 s:  b1p plain    b1d KYTY_BC5_SWITCH_DEFAULTS=0
#   second title, RT on, no zero skip, 240 s after G, exp 0415's counters to a file:
#     g1on g2on   nothing set: the zero guards behind the eager heaps ON (the default)
#   lean, 120 s, nothing set
#     g3off g4off BC5_DIRECT_HEAP_GUARDS=0: no guard (the full removal's behaviour). LAST on purpose: a heap-end
#                 fault here is the measurement the top session asked for, and it stops the chain with nothing left.
# usage (on the box, detached): P_NEW11=<patch md5> chk0417b.sh      MODE=post: the same runs on the SHARED binaries
#   MODE=resume: only the runs, on the private binaries already built (after a foreign lock stopped the chain between steps)
set -u
ulimit -c 0
export LC_ALL=C
W=$HOME/bc5-work; E=$W/exp0413; N=$E/n; P=$E/p; R=$N/raw
cd "$N" || exit 1
halt() { echo "chk0417b STOP: $*"; echo "chk0417b ended $(date +%T): STOPPED"; exit 1; }
if [ "${MODE:-}" = post ]; then
    BN=$W/kytyplus-build/src/kyty_emulator; BL=$W/kytyplus-build-lean/src/kyty_emulator; X=s
elif [ "${MODE:-}" = resume ]; then  # the private binaries as they are (the build and the CPU tests were done by an earlier call)
    BN=$P/build-normal/src/kyty_emulator; BL=$P/build-lean/src/kyty_emulator; X=p
else
    : "${P_NEW11:?the patch md5}"
    (cd "$P/kit" && P_NEW11=$P_NEW11 bash ./p0417b.sh) > "$P/p0417b.log" 2>&1
    tail -3 "$P/p0417b.log"
    grep -q "^lock released" "$P/p0417b.log" && grep -q " done; normal " "$P/p0417b.log" ||
        { grep -m8 "error:\|STOP\|differs\|lacks\|holds" "$P/p0417b.log" "$P"/build-*.build.log 2> /dev/null | cut -c1-300; halt "the build did not end clean"; }
    bash "$N/cpu11/cpu0417.sh" || halt "a CPU test failed"
    BN=$P/build-normal/src/kyty_emulator; BL=$P/build-lean/src/kyty_emulator; X=p
fi
MN=$(md5sum < "$BN" | cut -d' ' -f1); ML=$(md5sum < "$BL" | cut -d' ' -f1)
echo "binaries ($X): normal $MN lean $ML"
export P_BIN=$BN P_WANT=$MN
clean() {  # the step's own result line, the words a clean end has
    echo "$1"
    case "$1" in *"$2"*"kernel lines 0, crash lines 0"*) ;; *) halt "not a clean run: $(echo "$1" | cut -c1-160)" ;; esac
}
LINES="exp 0415: APR reads\|pending cap\|physmap sorted\|ranges fast\|acb state restore\|zero guards behind\|set-buffer with the map\|exp 0417 hook"
astro() {  # tag, words...
    local tag=$1; shift
    local line; line=$(bash ./sweep0413g.sh "$tag" 120 "0" "$@" | grep "^n=0:")
    echo "$tag lines: $(grep -a -h "$LINES" "$R/${tag}0-play.log" 2> /dev/null | sed 's/\[bc5\] //' | cut -c1-90 | sort | uniq -c | tr -s ' ' | tr '\n' ';')"
    clean "$line" "PASS: ran 120 s"
}
astro b1${X}p
astro b1${X}d KYTY_BC5_SWITCH_DEFAULTS=0
second() {  # tag, words...
    local tag=$1; shift
    setsid nohup python3 ./fault0416.py "$R/$tag-faults.txt" 460 < /dev/null > /dev/null 2>&1 &
    local fp=$!
    local line; line=$(P_WORDS=$N/words0413nz.txt bash ./run0413p.sh "$tag" nozeroskip 240 KYTY_BC5_LOAD_STAT="$R/$tag-loadstat.txt" "$@" | grep "^$tag ")
    kill "$fp" 2> /dev/null; sleep 4
    echo "$tag lines: $(grep -a -h "$LINES" "$R/$tag-play.log" 2> /dev/null | sed 's/\[bc5\] //' | cut -c1-90 | sort | uniq -c | tr -s ' ' | tr '\n' ';')"
    local J; J=$(sed -n 's/^journal \([^ ]*\) .*$/\1/p' "$R/$tag-journal.txt" 2> /dev/null)  # the run's direct.log (run0413p.sh records its path)
    echo "$tag journal: removed-line $(grep -a -c 'learned windows: removed from this build' "$J" 2> /dev/null), would-learn $(grep -a -c '^would learn' "$J" 2> /dev/null), timeout-fault $(grep -a -c '^timeout: fault' "$J" 2> /dev/null), acb line $(grep -a -c 'acb state restore' "$J" 2> /dev/null); catcher: $(grep -c ' fault: ' "$R/$tag-faults.txt" 2> /dev/null) fault lines; watchdog: $(tail -1 "$R/$tag-watchdog.txt" 2> /dev/null | cut -c21-140)"
    echo "$tag counters: $(grep '^s ' "$R/$tag-loadstat.txt" 2> /dev/null | tail -1 | grep -o 'apr_read=[0-9,]*\|learned=[0-9,]*\|learned_apply=[0-9,]*\|anon_sync=[0-9,]*\|dev_hold=[0-9,]*' | tr '\n' ' ')"
    clean "$line" "ended at G+240"
    sleep 5
}
second g1${X}on
second g2${X}on
clean "$(P_BIN=$BL P_WANT=$ML P_WORDS=$N/words0413nz.txt bash ./start0413l.sh l11${X} lean 120 | grep "^l11${X} ")" "PASS: ran 120 s"
second g3${X}off BC5_DIRECT_HEAP_GUARDS=0
second g4${X}off BC5_DIRECT_HEAP_GUARDS=0
echo "chk0417b ended $(date +%T): all clean"
