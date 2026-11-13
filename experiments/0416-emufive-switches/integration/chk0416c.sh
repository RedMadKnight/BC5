#!/usr/bin/env bash
# BC5 integration of 2026-11-13 (exp 0416 + 0415 + 0412): the private rebuild, the CPU tests and the checks, one
# unattended chain in the top session's slot (until 04:00). Private directories only (~/bc5-work/exp0413/p and /n, exp
# 0413's tools); every step takes and releases BOX-LOCK by itself and refuses when an emulator runs.
# The chain STOPS at a failed build, a failed CPU test, or the first run that is not clean (a kernel line, a crash
# line, a run that did not reach its end): the top's rule "stop at the first kernel error".
#   build     p0416c.sh: the private tree from a099e662 to P_NEW9, normal and lean
#   cpu       cpu0416.sh (its sources in $N/cpu9)
#   ASTRO BOT, 120 s each:  a9p plain    a9d KYTY_BC5_SWITCH_DEFAULTS=0
#   second title, RT on, no zero skip, 240 s after G, exp 0415's counters to a file (KYTY_BC5_LOAD_STAT):
#     r9apr  the code default (KYTY_BC5_APR_POSIX=direct from kFixes)     r9old  KYTY_BC5_APR_POSIX=0
#   lean start 120 s, nothing set
# usage (on the box, detached): P_NEW9=<patch md5> chk0416c.sh        MODE=post: the same runs on the SHARED binaries
set -u
ulimit -c 0
export LC_ALL=C
W=$HOME/bc5-work; E=$W/exp0413; N=$E/n; P=$E/p; R=$N/raw
cd "$N" || exit 1
halt() { echo "chk0416c STOP: $*"; echo "chk0416c ended $(date +%T): STOPPED"; exit 1; }
if [ "${MODE:-}" = post ]; then
    BN=$W/kytyplus-build/src/kyty_emulator; BL=$W/kytyplus-build-lean/src/kyty_emulator; X=s
else
    : "${P_NEW9:?the patch md5}"
    (cd "$P/kit" && P_NEW9=$P_NEW9 bash ./p0416c.sh) > "$P/p0416c.log" 2>&1
    tail -3 "$P/p0416c.log"
    grep -q "^lock released" "$P/p0416c.log" && grep -q " done; normal " "$P/p0416c.log" ||
        { grep -m8 "error:\|STOP\|differs\|lacks" "$P/p0416c.log" "$P"/build-*.build.log 2> /dev/null | cut -c1-300; halt "the build did not end clean"; }
    bash "$N/cpu9/cpu0416.sh" || halt "a CPU test failed"
    BN=$P/build-normal/src/kyty_emulator; BL=$P/build-lean/src/kyty_emulator; X=p
fi
MN=$(md5sum < "$BN" | cut -d' ' -f1); ML=$(md5sum < "$BL" | cut -d' ' -f1)
echo "binaries ($X): normal $MN lean $ML"
export P_BIN=$BN P_WANT=$MN
clean() {  # the step's own result line: stop unless it says a clean end
    local line=$1 want=$2
    echo "$line"
    case "$line" in *"$want"*"kernel lines 0, crash lines 0"*) ;; *) halt "not a clean run: $(echo "$line" | cut -c1-160)" ;; esac
}
astro() {  # tag, words...
    local tag=$1; shift
    clean "$(bash ./sweep0413g.sh "$tag" 120 "0" "$@" | grep "^n=0:")" "PASS: ran 120 s"
    echo "$tag lines: $(grep -a -h "exp 0415: APR reads\|exp 0412 events: pending cap\|set-buffer with the map\|tag mr412\|SessionManager V2 o" "$R/${tag}0-play.log" 2> /dev/null | sed 's/\[bc5\] //' | cut -c1-80 | sort | uniq -c | tr -s ' ' | tr '\n' ';')"
}
astro a9${X}p
astro a9${X}d KYTY_BC5_SWITCH_DEFAULTS=0
second() {  # tag, words...
    local tag=$1; shift
    setsid nohup python3 ./fault0416.py "$R/$tag-faults.txt" 460 < /dev/null > /dev/null 2>&1 &
    local fp=$!
    local line; line=$(P_WORDS=$N/words0413nz.txt bash ./run0413p.sh "$tag" nozeroskip 240 KYTY_BC5_LOAD_STAT="$R/$tag-loadstat.txt" "$@" | grep "^$tag ")
    kill "$fp" 2> /dev/null; sleep 4
    echo "$tag catcher: $(grep -c ' fault: ' "$R/$tag-faults.txt" 2> /dev/null) fault lines; $(tail -1 "$R/$tag-faults.txt" 2> /dev/null | cut -c1-200)"
    echo "$tag APR line: $(grep -a -c 'exp 0415: APR reads by pread' "$R/$tag-play.log" 2> /dev/null); counters: $(grep -a -h -i 'apr' "$R/$tag-loadstat.txt" 2> /dev/null | tail -6 | tr -s ' ' | tr '\n' ';' | cut -c1-600)"
    clean "$line" "ended at G+240"
    sleep 5
}
second r9${X}apr
second r9${X}old KYTY_BC5_APR_POSIX=0
clean "$(P_BIN=$BL P_WANT=$ML P_WORDS=$N/words0413nz.txt bash ./start0413l.sh l9${X} lean 120 | grep "^l9${X} ")" "PASS: ran 120 s"
echo "chk0416c ended $(date +%T): all clean"
