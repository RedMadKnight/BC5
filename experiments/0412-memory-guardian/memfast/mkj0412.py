#!/usr/bin/env python3
"""BC5 experiment 0412, the two launcher-word arms (README section 95; the top session's slot of 2026-11-14 with the
maintainer's yes to the switch proposals).
  night0412j.sh from night0412i.sh: four long walks on b413a916, interleaved: n11Fg1, n11Fl1, n11Fg2, n11Fl2.
                g: the words without BC5_GUARD_FORGET; l: the words without BC5_DIRECT_LAZY_RELEASE and
                BC5_GUARD_SPLIT. The chain makes both private word files from the checked one and compares them
                with it; N9_DRY=1 shows that and stops at the stop file. Catchers armed as in the first chain
                (dc412 on). Stop rule as night0412i.sh. Stop file STOP-n11.
usage: mkj0412.py <night0412i.sh> <night0412j.sh>"""
import sys


def rep(s, old, new, n=1):
    assert s.count(old) == n, (s.count(old), old[:70])
    return s.replace(old, new)


MAKE = rb'''WG=$N/words-n11-noforget.txt; WL=$N/words-n11-nolazy.txt
grep -v '^BC5_GUARD_FORGET=' "$WORDS" > "$WG"; grep -v '^BC5_DIRECT_LAZY_RELEASE=\|^BC5_GUARD_SPLIT=' "$WORDS" > "$WL"
words_ok() {  # file, lines it must lack, the words it must not hold
    [ "$(wc -l < "$1")" = "$(($(wc -l < "$WORDS") - $2))" ] || return 1
    grep -q "$3" "$1" && return 1
    [ "$(diff "$WORDS" "$1" | grep -c '^>')" = 0 ] && [ "$(diff "$WORDS" "$1" | grep -c '^<')" = "$2" ]
}
words_ok "$WG" 1 '^BC5_GUARD_FORGET=' && words_ok "$WL" 2 '^BC5_DIRECT_LAZY_RELEASE=\|^BC5_GUARD_SPLIT=' || { echo "night0412 ended $(date +%T): NOT STARTED, a private words file is not the words minus the arm's"; exit 1; }
[ "$(grep -c '^BC5_GUARD_FORGET=\|^BC5_DIRECT_LAZY_RELEASE=\|^BC5_GUARD_SPLIT=' "$WORDS")" = 3 ] || { echo "night0412 ended $(date +%T): NOT STARTED, the words file does not hold the three words"; exit 1; }
'''


def main():
    assert len(sys.argv) == 3, __doc__
    s = open(sys.argv[1], "rb").read()
    assert b"\r" not in s
    s = rep(s, b"# night0412i (mki0412.py from night0412h.sh, README section 93):",
            b"# night0412j (mkj0412.py from night0412i.sh, README section 95): four long walks, n11Fg1, n11Fl1, n11Fg2, n11Fl2;\n# g: without BC5_GUARD_FORGET, l: without BC5_DIRECT_LAZY_RELEASE and BC5_GUARD_SPLIT (private word files made here).\n# night0412i was (mki0412.py from night0412h.sh, README section 93):")
    s = rep(s, b"# usage (on the box, detached): night0412i.sh\n", b"# usage (on the box, detached): night0412j.sh\n")
    s = rep(s, b"STOPF=$N/STOP-n10\n", b"STOPF=$N/STOP-n11\n")
    a = b'''[ "$(md5sum < "$WORDS" | cut -c1-8)" = "${N8_WORDS_MD5:?the words file md5}" ] || { echo "night0412 ended $(date +%T): NOT STARTED, the words file changed"; exit 1; }\n'''
    s = rep(s, a, a + MAKE)
    s = rep(s, b"long walks of the second title on the private build g412zg (F only, up to 8, stop at the first arm that is not clean; the maintainer's yes), about 2 hours",
            b"four long walks of the second title on the private build g412zg for two launcher-word arms (without BC5_GUARD_FORGET; without BC5_DIRECT_LAZY_RELEASE and BC5_GUARD_SPLIT), about 55 minutes")
    s = rep(s, b'P_WORDS="$WORDS" bash "$N/run0412p.sh"', b'P_WORDS="${AW:-$WORDS}" bash "$N/run0412p.sh"')
    a = b'''    echo "$tag dispatch count: '''
    s = rep(s, a, b'''    echo "$tag words file ${AW:-$WORDS}; journal lines: lazy release $(grep -a -c '^lazy release' "$J" 2> /dev/null), guard forget $(grep -a -c '^guard forget' "$J" 2> /dev/null); the last direct line: $(grep -a '^direct: [0-9]* views' "$J" 2> /dev/null | tail -1 | cut -c1-120)"\n''' + a)
    s = rep(s, b"night0412i: the stop file is there", b"night0412j: the stop file is there")
    a = b'if [ "${N9_DRY:-0}" = 1 ]; then\n'
    s = rep(s, a, a + b'''    echo "dry: without FORGET: $(diff "$WORDS" "$WG" | grep '^[<>]' | tr '\\n' ' ')"\n    echo "dry: without the LAZY pair: $(diff "$WORDS" "$WL" | grep '^[<>]' | tr '\\n' ' ')"\n''')
    i = s.index(b"FCLEAN=0; FKNOWN=0\n")
    s = s[:i] + b'''FCLEAN=0; FKNOWN=0
for A in g1 l1 g2 l2; do
    stopped
    case $A in g*) AW=$WG ;; l*) AW=$WL ;; esac
    arm "n11F$A" F BC5_DISPATCH_COUNT=1
    if [ "$CLEAN" = 1 ]; then FCLEAN=$((FCLEAN + 1)); else FKNOWN=$((FKNOWN + 1)); fi
    echo "-- $(date +%T) so far: up to n11F$A, clean $FCLEAN, known CPU fault $FKNOWN"
done
echo "night0412 totals: word arms n11Fg1, n11Fl1, n11Fg2, n11Fl2: clean $FCLEAN, known CPU fault $FKNOWN"
echo "night0412 ended $(date +%T): four walks done"
'''
    open(sys.argv[2], "wb").write(s)
    print("ok")


if __name__ == "__main__":
    main()
