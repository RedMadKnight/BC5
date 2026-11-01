#!/usr/bin/env python3
"""BC5 exp 0388, the integration: the F454 route on the shared normal build, derived from exp 0388's runner.
What differs: the directory exp0388r; the shared binary, pinned by its first eight digits, the old one for tag S and the new
one otherwise; the fix may be on; the first letter of a tag is the check, and the log's wait line is proved; the series.
Tags: S baseline on the unchanged shared binary, which still has the fix, on. T the wait on. U the wait off. The new binary
has no fix. usage: mkroute.py <exp 0388 dir> <out dir>"""
import re, sys

SRC, OUT = sys.argv[1:3]
NAMES = ["run0388.sh", "go0388.sh", "series0388.sh", "s6n0388.sh", "prestart0388.sh", "check0388.py", "pins0388.env", "d19gates.py", "d19manifest.py"]
ARMS = {"S": "", "T": "KYTY_BC5_JOB_PUSH_TRACE=1", "U": "KYTY_BC5_JOB_PUSH_WAIT=0 KYTY_BC5_JOB_PUSH_TRACE=1"}


def R(s, a, b, n=1):
    assert s.count(a) == n, (a, s.count(a))
    return s.replace(a, b)


files = {n: open(f"{SRC}/{n}", encoding="utf-8", newline="").read().replace("exp0388", "exp0388r") for n in NAMES}

s = files["run0388.sh"]
s = R(s, 'case "$fix" in off) ;; *) die "every 0388 run has the fix off" ;; esac', 'case "$fix" in on | off) ;; *) die "the fix is on or off" ;; esac')
s = R(s, "for v in NORMAL LAUNCHER", "for v in NORMAL NEW LAUNCHER LAUNCHER_NEW")
s = R(s, "BIN=$EX/kyty_emulator  # 0388: the private test build\n", "BIN=$W/kytyplus-build/src/kyty_emulator  # the shared normal build\n    case \"$TAG\" in S*) WANT8=$NORMAL; WANTL=$LAUNCHER ;; *) WANT8=$NEW; WANTL=$LAUNCHER_NEW ;; esac\n")
s = R(s, '[ "$(m "$W/play-pkg.sh")" = "$LAUNCHER" ] || die "the launcher is not $LAUNCHER"', '[ "$(m "$W/play-pkg.sh")" = "$WANTL" ] || die "the launcher is not $WANTL"')
s = R(s, '[ "$(m "$BIN")" = "$NORMAL" ] || die "the binary is not $NORMAL"', '[ "$(m "$BIN" | cut -c1-8)" = "$WANT8" ] || die "the shared binary is not $WANT8"')
s = R(s, "BC5_0380_WANT=${NORMAL:0:8}", "BC5_0380_WANT=$WANT8")
files["run0388.sh"] = s

s = files["s6n0388.sh"]
s = R(s, "PLAY_PKG_MD5=55531ab6   # D19's pin; run0388.sh checks the full md5", "case \"$TAG\" in S*) PLAY_PKG_MD5=55531ab6 ;; *) PLAY_PKG_MD5=48a4dbf9 ;; esac  # the new launcher has exp 0399's line; run0388.sh checks the full md5")
s, n = re.subn(r'case "\$TAG" in\n  C\*\).*?\n  \*\) echo "no arm for \$TAG"; exit 1 ;;\nesac\n',
               'case "$TAG" in\n' + "".join(f'  {k}*) ARM="{v}" ;;\n' for k, v in ARMS.items()) + '  *) echo "no arm for $TAG"; exit 1 ;;\nesac\n', s, flags=re.S)
assert n == 1
s = R(s, "|KYTY_BC5_0388_[A-Z_]*|", "|KYTY_BC5_JOB_PUSH_[A-Z_]*|")
s = R(s, 'box_settings() { echo "swappiness $(cat /proc/sys/vm/swappiness); kernel $(uname -r);',
      'box_settings() { echo "os $(. /etc/os-release; echo "$VERSION_ID"); mesa $(rpm -q --qf "%{VERSION}" mesa-vulkan-drivers 2> /dev/null); swappiness $(cat /proc/sys/vm/swappiness); kernel $(uname -r);')
files["s6n0388.sh"] = s

s = files["check0388.py"]
s, n = re.subn(r'ARMS = \{\n.*?\n\}\n', "ARMS = {\n" + "".join(f'    "{k}": "{v}",\n' for k, v in ARMS.items()) + "}\nWAITLINE = re.compile(r\"job push wait (ON|OFF), \")\nWAITWANT = {\"S\": set(), \"T\": {\"ON\"}, \"U\": {\"OFF\"}}\n", s, count=1, flags=re.S)
assert n == 1
s = R(s, '''    if arms != {"ON" if fix == "on" else "OFF"}:
''', '''    if arms != ({"ON"} if tag[0] == "S" else set()):  # only the old binary has the fix
''')
s = R(s, '''    for kv in ARMS[tag[0]].split():  # 0388: exactly the arm\'s switches; any other 0388 name stays unknown and blocks
''', '''    if tag[0] != "S":
        m.COMMON["BC5_DIRECT_GC_HS_OFFCHIP"] = "1"  # exp 0399\'s line in the new launcher
    for kv in ARMS[tag[0]].split():  # 0388: exactly the arm\'s switches; any other 0388 name stays unknown and blocks
''')
s = R(s, '''    # Reached the fight: the load was seen, then gameplay, then the inputs went in.
''', '''    if set(WAITLINE.findall(play)) != WAITWANT[tag[0]]:
        reasons.append(f"the wait line of the log says {sorted(set(WAITLINE.findall(play))) or 'nothing'}, the arm is {tag[0]}")

    # Reached the fight: the load was seen, then gameplay, then the inputs went in.
''')
i, j = s.index("def rule(path):"), s.index("def main():")
s = s[:i] + '''def rule(path):
    """The checks after the swap. Prints RULE <verdict> and the counts. U's crash is expected and proves nothing about J."""
    rows = [x.split() for x in open(path) if x.strip()]
    for a, what in (("S", "baseline on the old binary, fix on"), ("T", "the wait on")):
        got = [r for r in rows if r[0].startswith(a)]
        clean = sum(r[2] == "NO_CRASH" for r in got)
        verdict = "NONE" if not got else "PASS" if clean == len(got) else "FAIL"
        print(f"RULE {a} {verdict}: {clean} clean of {len(got)}, {what}")
    for r in (r for r in rows if r[0].startswith("U")):
        print(f"RULE U INFO: {r[0]} {r[2]} crash {r[3]}, the wait off: a crash here is the control, no crash is no failure")
    return 0


''' + s[j:]
files["check0388.py"] = s

s = files["series0388.sh"]
s = R(s, "the third cycle's 22 runs, one go0388.sh at a time, under one deadline of 105 min.", "the route runs on the shared build, one go0388.sh at a time, under one deadline.")
s = R(s, "# usage: series0388.sh     Exit:", "# usage: series0388.sh baseline|post     Exit:")
s = R(s, "LIMIT=6300;", 'case "${1:-}" in baseline) LIMIT=900; RUNS="S2:on" ;; post) LIMIT=3000; RUNS="T4:off T5:off T6:off U2:off" ;; *) echo "baseline or post"; exit 1 ;; esac\n')
s = R(s, "for t in G4:off F6:off H1:off J1:off K1:off L1:off H2:off J2:off G5:off F7:off K2:off L2:off H3:off J3:off H4:off J4:off G6:off F8:off K3:off L3:off H5:off J5:off; do", "for t in $RUNS; do")
s = R(s, 'OUT=$HERE/raw/series.txt; ROWS=$HERE/raw/rows.txt\nmkdir -p "$HERE/raw"; : > "$OUT"; : > "$ROWS"\n', 'OUT=$HERE/raw/series.txt; ROWS=$HERE/raw/rows.txt\nmkdir -p "$HERE/raw"; touch "$OUT" "$ROWS"\n')
files["series0388.sh"] = s

s = files["pins0388.env"]
s = re.sub(r"NORMAL=[0-9a-f]+\n", "NORMAL=78f25172\nNEW=FILL\nLAUNCHER_NEW=FILL\n", s)
s = re.sub(r"INPUT_CFG=[0-9a-f]+", "INPUT_CFG=a4df3b9e721d74fe17dc838d25eeb923", s)
s = re.sub(r"LEARNED=[0-9a-f]+", "LEARNED=23ef45ec8917208381a61eb19aea05f6", s)
files["pins0388.env"] = s

for name in ("d19manifest.py", "d19gates.py"):
    files[name] = R(files[name], '"normal": "/exp0388r/kyty_emulator"', '"normal": "/kytyplus-build/src/kyty_emulator"')

for name, text in files.items():
    with open(f"{OUT}/{name}", "w", encoding="utf-8", newline="") as f:
        f.write(text)
    print(name, len(text))
