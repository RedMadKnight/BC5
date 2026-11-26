#!/usr/bin/env python3
# exp 0381: Codex review REVIEW-06-J2: F680's wording, F682 after F681, README notes and §14, build hashes, script notes.
# usage: python handoff0381i.py docs/HANDOFF.md <experiment dir> <readme-s14.md>
import re
import sys
from pathlib import Path

p = Path(sys.argv[1])
s = p.read_text(encoding="utf-8")
a = "but not a pass: no start put an acb right in front of the F679 buffer, so all count as no test under the rules written first.**"
assert s.count(a) == 1
s = s.replace(a, "but not a pass: the five starts are eligibility unverified (F682).**")
s, n = re.subn(r"^(\| F681 \| )", lambda m: m.group(1) + "*Limited by F682: the offsets cover one burst of each start, not the whole run.* ", s, count=1, flags=re.M)
assert n == 1
s, n = re.subn(r"^(\| F663 \| )", lambda m: m.group(1), s, count=1, flags=re.M)
row = (
    "| F682 | **Codex review (REVIEW-06-J2): exp 0381's J2 checkers filtered on the journal's chain offset, which already "
    "includes host prefixes, so an opener at dword 13 reads 71 behind the 58-dword restore and was rejected (Codex's probe "
    "on the real scripts: 13 → 1, 71 → 0); the J2 journals hold no segment identity, so J2's five starts are eligibility "
    "unverified.** The odds quoted for J2 are withdrawn: they assumed independent, identical trials. The switch is also a "
    "bundle (packets, copying, timing), so off-against-on tests the bundle, not the register mechanism alone. In reply the "
    "host diff journals job, segment, original offset and the `USER_DATA_0` in each segment's emitted prefix, "
    "`last_missing` compares offsets, `j3check0381.py` replaces the two checkers, and J3's rule compares off and on at one "
    "chain-hold value, with evidence for the mechanism requiring an eligible ON start with the restore attributed to the "
    "target segment. Laptop: 101 of 101 test cases, the checker's 6 cases; the new unit is not compiled on the box. | "
    "experiment 0381 (README §14, `j3check0381.py`, `test_j3check0381.py`); Codex review (REVIEW-06-J2) | High for the "
    "false negative and the code path; J3 not run |\n"
)
m = re.search(r"^\| F681 \|[^\n]*\n", s, re.M)
s = s[: m.end()] + row + s[m.end():]
p.write_text(s, encoding="utf-8", newline="\n")

d = Path(sys.argv[2])
r = d / "README.md"
t = r.read_text(encoding="utf-8")
t, n = re.subn(r"If\s+the\s+switch\s+changed\s+nothing,\s+3\s+clean\s+starts\s+would\s+have\s+a\s+chance\s+of\s+about\s+1\s+in\s+27\s+at\s+2\s+of\s+3,\s+and\s+1\s+in\s+64\s+at\s+3\s+of\s+4\.", "*The odds that stood here are withdrawn (§14).*", t)
assert n == 1
a = "**J3's rule, written before it runs.**"
assert t.count(a) == 1
t = t.replace(a, "**J3's rule as first written; replaced by §14.**")
a = "**Pass:** 3 clean starts, no F443 in any."
assert t.count(a) == 1
t = t.replace(a, "*The checks below were applied with a faulty detector; J2 is eligibility unverified (§14).*\n\n" + a)
t = t.rstrip("\n") + "\n" + Path(sys.argv[3]).read_text(encoding="utf-8")
r.write_text(t, encoding="utf-8", newline="\n")

b = d / "build0381.sh"
u = b.read_text(encoding="utf-8")
u, n = re.subn(r"EXPECT_UNIT=9d4649ba; EXPECT_DIFF=6629134b", "EXPECT_UNIT=637f964c; EXPECT_DIFF=d36d6fb7", u)
assert n == 1
b.write_text(u, encoding="utf-8", newline="\n")

for name in ("j2check0381.py", "j2job0381.py"):
    f = d / name
    v = f.read_text(encoding="utf-8")
    v = v.replace("#!/usr/bin/env python3\n", "#!/usr/bin/env python3\n# SUPERSEDED by j3check0381.py: this filters on the chain offset, a false negative behind a prefix (REVIEW-06-J2).\n", 1)
    f.write_text(v, encoding="utf-8", newline="\n")
print("ok")
