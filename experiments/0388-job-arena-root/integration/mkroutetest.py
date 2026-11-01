#!/usr/bin/env python3
"""BC5 exp 0388, the integration: exp 0388's stand-in suite for the route runner, with cases for what differs.
usage: mkroutetest.py <exp 0388 dir> <route dir>"""
import re, sys

SRC, OUT = sys.argv[1:3]
s = open(f"{SRC}/test0388run.sh", encoding="utf-8", newline="").read()
s = s.replace("exp0388", "exp0388r")
s = re.sub(r"\bA([0-9G][0-9]?[NF]?)\b", r"T\1", s)
for a, b, n in (
    ('home + "/bc5-work/exp0388r/kyty_emulator"', 'home + "/bc5-work/kytyplus-build/src/kyty_emulator"', 1),
    ('mkdir -p "$W/exp0388r"; echo binary > "$W/exp0388r/kyty_emulator"\n', 'echo binary > "$W/kytyplus-build/src/kyty_emulator"\n', 1),
    ('{ echo "NORMAL=$(m "$W/exp0388r/kyty_emulator")";', '{ echo "NORMAL=$(m "$W/kytyplus-build/src/kyty_emulator" | cut -c1-8)"; echo "NEW=$(m "$W/kytyplus-build/src/kyty_emulator" | cut -c1-8)";', 1),
    ('mkdir -p "$EX"; echo binary > "$EX/kyty_emulator"\n', 'mkdir -p "$EX"; echo binary > "$W/kytyplus-build/src/kyty_emulator"; echo "job push wait ON, 2000 us at most" > "$F/waitline"\n', 1),
    ('echo x >> "$W/exp0388r/kyty_emulator"', 'echo x >> "$W/kytyplus-build/src/kyty_emulator"', 1),
    ("printf 'binary\\n' > \"$W/exp0388r/kyty_emulator\"", "printf 'binary\\n' > \"$W/kytyplus-build/src/kyty_emulator\"", 1),
    ('  { echo "game fix (temporary, exp 0359): job-arena fix $(cat "$F/fixline") for PPSA03671 (environment)"\n',
     '  { { [ ! -s "$F/waitline" ] || [ "$(cat "$F/fixline")" = ON ]; } && echo "game fix (temporary, exp 0359): job-arena fix $(cat "$F/fixline") for PPSA03671 (environment)"\n    [ ! -s "$F/waitline" ] || cat "$F/waitline"\n', 1),
):
    assert s.count(a) == n, (a, s.count(a))
    s = s.replace(a, b)
CASES = r'''
if t route; then
  reset; echo "" > "$F/waitline"; go T1N off; want "route: no wait line where it must be on: invalid" 0 "CLASS INVALID"
  reset; go U1N off; want "route: the off switch with the line ON: invalid" 0 "CLASS INVALID"
  reset; echo "job push wait OFF, 2000 us at most" > "$F/waitline"; go U2N off; want "route: the off switch with the line OFF" 0 "CLASS NO_CRASH fix off crash none reached 1"
  reset; echo "job push wait OFF, 2000 us at most" > "$F/waitline"; echo crash-target > "$F/scn"; go U3N off; want "route: the control may crash" 0 "CLASS CRASH_TARGET fix off crash target reached 1"
  reset; : > "$F/waitline"; echo ON > "$F/fixline"; go S1N on; want "route: the baseline, fix on, no wait line" 0 "CLASS NO_CRASH fix on crash none reached 1"
  reset; echo ON > "$F/fixline"; go S2N on; want "route: a wait line on the old binary: invalid" 0 "CLASS INVALID"
  reset; sed -i 's/^NEW=.*/NEW=FILL/' "$RUND/pins0388.env"; go T4N off; want "route: the new pin unfilled stops before the launch" 2 "no result file"
  reset; sed -i 's/^NEW=.*/NEW=00000000/' "$RUND/pins0388.env"; go T5N off; want "route: the old binary under a T tag stops" 2 "no result file"
  reset; sed -i 's/^NEW=.*/NEW=00000000/' "$RUND/pins0388.env"; : > "$F/waitline"; echo ON > "$F/fixline"; go S3N on; want "route: tag S needs only the old pin" 0 "CLASS NO_CRASH fix on crash none reached 1"
fi
'''
i = s.rindex('if t series; then')
s = s[:i] + CASES + s[i:]
# The series test has its own tags and rule; the route series is a short loop over the same go0388.sh.
j = s.index('if t series; then')
k = s.index("\nfi\n", j) + 4
s = s[:j] + s[k:]
open(f"{OUT}/test0388run.sh", "w", encoding="utf-8", newline="").write(s)
print("ok")
