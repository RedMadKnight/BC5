#!/usr/bin/env python3
"""BC5 exp 0388: the fight runs, derived from exp 0386's reviewed runner (branch exp/0386-fight-job-arena, 5f4f7af5).
What differs: the private binary; every run has the job-arena fix off; the first letter of a tag is the arm, which sets
the 0388 switches; the job threads are counted at 70 s; the series and its rule. usage: mk0388run.py <0386 dir> <this dir>"""
import re, sys

SRC, OUT = sys.argv[1:3]
MAP = {
    "box0386.sh": "run0388.sh", "go0386.sh": "go0388.sh", "series0386.sh": "series0388.sh", "s6n0386.sh": "s6n0388.sh",
    "prestart0386.sh": "prestart0388.sh", "check0386.py": "check0388.py", "pins0386.env": "pins0388.env",
    "d19gates.py": "d19gates.py", "d19manifest.py": "d19manifest.py",
}
ARMS = {
    "C": "KYTY_BC5_0388_TRACE=1",
    "G": "KYTY_BC5_0388_TRACE=1",  # the second cycle's control
    "A": "KYTY_BC5_0388_CPU_MASK=1 KYTY_BC5_0388_TRACE=1",
    "B": "KYTY_BC5_0388_CPU_MASK=1 KYTY_BC5_0388_CURRENT_CPU=1 KYTY_BC5_0388_APPLY_AFFINITY=1 KYTY_BC5_0388_TRACE=1",
    "D": "KYTY_BC5_0388_PUSH_SPIN_US=200 KYTY_BC5_0388_TRACE=1",
    "E": "KYTY_BC5_0388_PUSH_SPIN_US=500 KYTY_BC5_0388_TRACE=1",
    "F": "KYTY_BC5_0388_PUSH_UNTIL_TAKEN_US=500 KYTY_BC5_0388_TRACE=1",
}


def R(s, a, b, n=1):
    assert s.count(a) == n, (a, s.count(a))
    return s.replace(a, b)


def common(s):
    s = s.replace("box0386", "run0388").replace("E0386", "E0388").replace("e0386", "e0388")
    return s.replace("0386", "0388")


def load(name):
    return common(open(f"{SRC}/{name}", encoding="utf-8", newline="").read())


files = {new: load(old) for old, new in MAP.items()}

s = files["run0388.sh"]
s = R(s, "emu_pids() { pgrep -x kyty_emulator; return 0; }", "emu_pids() { pgrep '^kyty_emulator'; return 0; }")
s = R(s, "BIN=$W/kytyplus-build/src/kyty_emulator\n", "BIN=$EX/kyty_emulator  # 0388: the private test build\n")
s = R(s, 'on | off) ;; *) die "the fix is on or off" ;; esac', 'off) ;; *) die "every 0388 run has the fix off" ;; esac')
files["run0388.sh"] = s

s = files["s6n0388.sh"]
s = R(s, "emu_pids() { pgrep -x kyty_emulator; return 0; }", "emu_pids() { pgrep '^kyty_emulator'; return 0; }")
arms = "".join(f'  {k}*) ARM="{v}" ;;\n' for k, v in ARMS.items())
s = R(s, 'SWITCHES="KYTY_BC5_JOB_ARENA_FIX=$FIXV"  # 0388\n',
      f'# 0388: the first letter of the tag is the arm; the check reads the same table\ncase "$TAG" in\n{arms}  *) echo "no arm for $TAG"; exit 1 ;;\nesac\n'
      'SWITCHES="KYTY_BC5_JOB_ARENA_FIX=$FIXV $ARM"\n')
s = R(s, "DISK_MAX=80; T_ROUTE=60;", "JOBS=\"\"; T_JOBS=70; DISK_MAX=80; T_ROUTE=60;")
s = R(s, '  if [ -z "$FDINFO" ] && [ "$(el)" -ge "$T_FD" ]; then',
      '  if [ -z "$JOBS" ] && [ "$(el)" -ge "$T_JOBS" ]; then  # 0388: how many workers the title made\n'
      '    JOBS=1; cat /proc/"$EP"/task/*/comm 2> /dev/null | grep -c "^Job " > "$R/$TAG-jobs.txt"\n  fi\n'
      '  if [ -z "$FDINFO" ] && [ "$(el)" -ge "$T_FD" ]; then')
s = R(s, "|KYTY_BC5_JOB_ARENA_FIX|", "|KYTY_BC5_JOB_ARENA_FIX|KYTY_BC5_0388_[A-Z_]*|")
files["s6n0388.sh"] = s

s = files["go0388.sh"]
s = R(s, 'FILES="run0388.sh s6n0388.sh prestart0388.sh check0388.py d19gates.py d19manifest.py pins0388.env"',
      'FILES="run0388.sh s6n0388.sh prestart0388.sh check0388.py d19gates.py d19manifest.py pins0388.env"  # the private binary is pinned there')
files["go0388.sh"] = s

s = files["check0388.py"]
s = R(s, 'def tables(fix):\n', 'ARMS = {\n' + "".join(f'    "{k}": "{v}",\n' for k, v in ARMS.items()) + '}\n\n\ndef tables(fix, tag):\n')
s = R(s, '    m.COMMON["KYTY_BC5_JOB_ARENA_FIX"] = "1" if fix == "on" else "0"\n',
      '    m.COMMON["KYTY_BC5_JOB_ARENA_FIX"] = "1" if fix == "on" else "0"\n'
      '    for kv in ARMS[tag[0]].split():  # 0388: exactly the arm\'s switches; any other 0388 name stays unknown and blocks\n'
      '        k, v = kv.split("=")\n        m.COMMON[k] = v\n')
s = R(s, "    tables(fix)\n", "    tables(fix, tag)\n")
i = s.index("def rule(path):")
j = s.index("def main():")
s = s[:i] + '''def rule(path):
    """The rule of the README, fixed before the runs. Prints RULE <verdict> and the counts."""
    rows = [x.split() for x in open(path) if x.strip()]
    def arm(a):
        return [r for r in rows if r[0].startswith(a)]
    site = sum(r[3] == "target" for r in arm("G"))
    print(f"control: {site} of {len(arm('G'))} crashed at the site")
    if site < 2:
        print("RULE AMBIGUOUS the control did not crash; no conclusion on any arm")
        return 0
    for a in "EF":
        clean = sum(r[2] == "NO_CRASH" for r in arm(a))
        hit = sum(r[3] == "target" for r in arm(a))
        other = sum(r[2] == "CRASH_OTHER" for r in arm(a))
        verdict = "HOLDS" if clean == 5 and hit == 0 and other == 0 else "REFUTED" if hit else "OPEN"
        print(f"RULE arm {a} {verdict}: {clean} clean, {hit} at the site, {other} elsewhere, of {len(arm(a))}")
    return 0


''' + s[j:]
files["check0388.py"] = s

s = files["series0388.sh"]
s = R(s, "ON, OFF, ON, OFF, ON, OFF, one go0388.sh at a time, under one deadline of 35 min.", "G1 E1 F1 E2 F2 G2 E3 F3 E4 F4 G3 E5 F5, one go0388.sh at a time, under one deadline of 75 min.")
s = R(s, "LIMIT=2100;", "LIMIT=4500;")
s = R(s, "for t in K1N:on K1F:off K2N:on K2F:off K3N:on K3F:off; do", "for t in G1:off E1:off F1:off E2:off F2:off G2:off E3:off F3:off E4:off F4:off G3:off E5:off F5:off; do")
files["series0388.sh"] = s

s = files["pins0388.env"]
s = re.sub(r"NORMAL=[0-9a-f]+", "NORMAL=FILL", s)  # the second build, filled after it
s = re.sub(r"INPUT_CFG=[0-9a-f]+", "INPUT_CFG=a5259c60c2beed35f5565f4744255ac5", s)
s = re.sub(r"LEARNED=[0-9a-f]+", "LEARNED=5b92521f646a897b8957cec4cd754ba4", s)
files["pins0388.env"] = s

for name in ("d19manifest.py", "d19gates.py"):  # 0388: the private binary is the run's exe
    files[name] = R(files[name], 'EXE = {"normal": "/kytyplus-build/src/kyty_emulator",', 'EXE = {"normal": "/exp0388/kyty_emulator",')

for name, text in files.items():
    with open(f"{OUT}/{name}", "w", encoding="utf-8", newline="") as f:
        f.write(text)
    print(name, len(text))
