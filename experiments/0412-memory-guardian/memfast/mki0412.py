#!/usr/bin/env python3
"""BC5 experiment 0412, the second chain resumed (README section 93; the top session's GO of 2026-11-14).
  night0412i.sh from night0412h.sh: arms n10F3..n10F8, the same alternation of BC5_DISPATCH_COUNT; the stop rule
                changes in one point: the title's known CPU fault (eboot.bin+0x1b349f, exit 65, 0 kernel lines, no
                timeout, no new fault record) does not stop the chain; its dump is copied to raw/<tag>-cpufault.txt
                and the next arm starts. Everything else stops it as before. N9_DRY=1 also runs the detector over
                the files of n10F2 (must say known) and n10F1 (must say not).
usage: mki0412.py <night0412h.sh> <night0412i.sh>"""
import sys


def rep(s, old, new, n=1):
    assert s.count(old) == n, (s.count(old), old[:70])
    return s.replace(old, new)


KNOWN = rb'''known_cpu_fault() {  # tag, the arm's start (epoch): 0 when the arm ended by the title's known CPU fault and nothing else
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
'''


def main():
    assert len(sys.argv) == 3, __doc__
    s = open(sys.argv[1], "rb").read()
    assert b"\r" not in s
    s = rep(s, b"# night0412h (mkh0412.py from night0412g.sh, README section 92):",
            b"# night0412i (mki0412.py from night0412h.sh, README section 93): the second chain resumed, n10F3..n10F8; the title's\n# known CPU fault (eboot.bin+0x1b349f, exit 65, nothing from the kernel or the GPU) is recorded and does not stop it.\n# night0412h was (mkh0412.py from night0412g.sh, README section 92):")
    s = rep(s, b"# usage (on the box, detached): night0412h.sh\n", b"# usage (on the box, detached): night0412i.sh\n")
    s = rep(s, b"arm() {  # tag, kind (F, W, B), words...\n", KNOWN + b"arm() {  # tag, kind (F, W, B), words...\n")
    s = rep(s, b"shift 2; CLEAN=0\n", b"shift 2; CLEAN=0; KNOWN=0\n")
    a = b'''    case "$line" in *SETUP:* | *ROUTE:* | "") BADSETUP='''
    s = rep(s, a, b'''    if [ "$CLEAN" = 0 ]; then case "$line" in *"ended by itself"*"kernel lines 0,"*) if known_cpu_fault "$tag" "$t0"; then
        KNOWN=1
        sed -n '/^kyty_exception_handler:/,/^--- Build ---/p' "$R/$tag-play.log" > "$R/$tag-cpufault.txt"
        echo "$tag: the title's KNOWN CPU FAULT (eboot.bin+0x1b349f), nothing from the kernel or the GPU: recorded in $R/$tag-cpufault.txt ($(wc -l < "$R/$tag-cpufault.txt") lines), the chain goes on"
        grep -a -m3 'access_violation_vaddr\\|^Stack trace\\|^guest rdi' "$R/$tag-cpufault.txt" | cut -c1-200
    fi ;; esac; fi
''' + a)
    s = rep(s, b'''    [ "$CLEAN" = 1 ] || { echo "night0412b STOP after $tag''', b'''    [ "$CLEAN" = 1 ] || [ "$KNOWN" = 1 ] || { echo "night0412b STOP after $tag''')
    s = rep(s, b"night0412h: the stop file is there", b"night0412i: the stop file is there")
    i = s.index(b"stopped\n[ \"${N9_DRY:-0}\" = 1 ]")
    j = s.index(b"FCLEAN=0\n")
    s = s[:i] + b'''if [ "${N9_DRY:-0}" = 1 ]; then
    known_cpu_fault n10F2 "$(date +%s)" && echo "dry: n10F2 is the known CPU fault (right)" || echo "dry: n10F2 NOT known: WRONG"
    known_cpu_fault n10F1 "$(date +%s)" && echo "dry: n10F1 known: WRONG" || echo "dry: n10F1 is not it (right)"
fi
''' + s[i:j] + b'''FCLEAN=0; FKNOWN=0
for FN in 3 4 5 6 7 8; do
    stopped
    arm "n10F$FN" F "BC5_DISPATCH_COUNT=$((FN % 2))"
    if [ "$CLEAN" = 1 ]; then FCLEAN=$((FCLEAN + 1)); else FKNOWN=$((FKNOWN + 1)); fi
    echo "-- $(date +%T) so far: F arms up to n10F$FN, clean $FCLEAN, known CPU fault $FKNOWN"
done
echo "night0412 totals: F arms n10F3..n10F8, clean $FCLEAN, known CPU fault $FKNOWN: the hang did not come"
echo "night0412 ended $(date +%T): six walks done"
'''
    open(sys.argv[2], "wb").write(s)
    print("ok")


if __name__ == "__main__":
    main()
