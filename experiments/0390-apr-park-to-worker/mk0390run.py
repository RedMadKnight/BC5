#!/usr/bin/env python3
"""BC5 exp 0390: the box scripts, derived from exp 0388's reviewed set (branch exp/0388-job-arena-root, 68ea1ffe).
What differs: libAmpr.cpp is the one private unit; the job-arena fix is on in every run, as in shared use; the first
letter of a tag is the arm, P without the switch and Q with it; the emulator's APR threads are read before it stops,
because only they show whether the changed branch ran; the series is one run of each arm with one spare.
usage: mk0390run.py <0388 dir> <this dir>"""
import re, sys

SRC, OUT = sys.argv[1:3]
MAP = {
    "run0388.sh": "run0390.sh", "go0388.sh": "go0390.sh", "series0388.sh": "series0390.sh", "s6n0388.sh": "s6n0390.sh",
    "prestart0388.sh": "prestart0390.sh", "check0388.py": "check0390.py", "pins0388.env": "pins0390.env",
    "d19gates.py": "d19gates.py", "d19manifest.py": "d19manifest.py", "box0388.sh": "box0390.sh",
    "build0388.py": "build0390.py", "test_box0388.sh": "test_box0390.sh", "test0388run.sh": "test0390run.sh",
}
ARMS = {"P": "", "Q": "KYTY_BC5_APR_PARK_TO_WORKER=1"}


def R(s, a, b, n=1):
    assert s.count(a) == n, (a, s.count(a))
    return s.replace(a, b)


def load(name):
    return open(f"{SRC}/{name}", encoding="utf-8", newline="").read().replace("0388", "0390")


files = {new: load(old) for old, new in MAP.items()}

s = files["run0390.sh"]
s = R(s, 'off) ;; *) die "every 0390 run has the fix off" ;; esac', 'on) ;; *) die "every 0390 run has the job-arena fix on" ;; esac')
s = R(s, "check $c saves same $cl", "check $c $cl")
files["run0390.sh"] = s

s = files["s6n0390.sh"]
i = s.index('case "$TAG" in\n  C*)')
j = s.index('SWITCHES="KYTY_BC5_JOB_ARENA_FIX=$FIXV $ARM"')
s = s[:i] + 'case "$TAG" in\n  P*) ARM="" ;;\n  Q*) ARM="KYTY_BC5_APR_PARK_TO_WORKER=1" ;;\n  *) echo "no arm for $TAG"; exit 1 ;;\nesac\n' + s[j:]
s = R(s, "|KYTY_BC5_JOB_ARENA_FIX|KYTY_BC5_0390_[A-Z_]*|", "|KYTY_BC5_JOB_ARENA_FIX|KYTY_BC5_APR_PARK_TO_WORKER|")
# 0390: bc5-apr-wait exists only if the wait thread started, so this read shows whether the changed branch ran.
s = R(s, "cpuidle_read() {", 'apr_threads() { cat /proc/"$EP"/task/*/comm 2> /dev/null | grep "^bc5-apr-" | sort | uniq -c; }\ncpuidle_read() {')
s = R(s, 'cpuidle_read > "$R/$TAG-cpuidle-end.txt"\nstop_emu', 'apr_threads > "$R/$TAG-apr-threads.txt"\ncpuidle_read > "$R/$TAG-cpuidle-end.txt"\nstop_emu')
# 0390: no live-save reads or comparisons (the maintainer, 2026-10-31): the named snapshot, a private copy reset from it,
# and the copy's sum, by route_sum's recipe, for repeatability.
lines = s.split("\n")
keep = [x for x in lines if not x.startswith(("saves() {", "LIVE=$(saves)", "WANT_SAVES=$(saves)", 'echo "$(date \'+%F %T\') live saves $WANT_SAVES', "S1=$(saves);"))]
assert len(lines) - len(keep) == 5, len(lines) - len(keep)
s = "\n".join(keep)
s = R(s, """ echo "$(date '+%F %T') aborted" >> "$R/s6n-saves.txt"; sync; exit 1; }""", " sync; exit 1; }")
s = R(s, """find "$SROOT/PPSA03671" -type f -exec touch -a -d '2020-01-01 00:00:00' {} +\n""",
      """find "$SROOT/PPSA03671" -type f -exec touch -a -d '2020-01-01 00:00:00' {} +\n"""
      """(cd "$SROOT/PPSA03671" && find . -type f -exec md5sum {} + | LC_ALL=C sort -k2 | md5sum | cut -c1-16) > "$R/$TAG-savecopy.txt"  # 0390: run0390.sh's route_sum, on the private copy\n""")
files["s6n0390.sh"] = s

s = files["check0390.py"]
s = R(s, """    if rc == "3":\n        return "INVALID", "none", 0, reasons + ["the live saves changed"]\n""", "")
i = s.index("ARMS = {\n")
j = s.index("def tables(fix, tag):")
s = s[:i] + "ARMS = {\n" + "".join(f'    "{k}": "{v}",\n' for k, v in ARMS.items()) + "}\n\n\n" + s[j:]
s = R(s, '''    print(f"CLASS {cl} fix {fix} crash {crash} reached {reached}")''',
      '''    print("APR wait thread: " + apr_wait(raw, tag))
    print(f"CLASS {cl} fix {fix} crash {crash} reached {reached}")''')
i = s.index("def rule(path):")
j = s.index("def main():")
s = s[:i] + '''def apr_wait(raw, tag):
    """absent, present or not read: a run with no thread list says nothing about the changed branch."""
    p = os.path.join(raw, tag + "-apr-threads.txt")
    text = g.read(p) or ""
    if "bc5-apr-q" not in text or os.path.getmtime(p) < os.path.getmtime(os.path.join(raw, tag + "-start.txt")) - g.SLACK:
        return "not read"  # LESSONS R11: a list older than this run's start is not this run's
    return "present" if "bc5-apr-wait" in text else "absent"


def rule(path):
    """The smoke's rule, fixed before the runs. It can show no regression, nothing more: the changed branch does not run in
    the second title. PASS needs a NO_CRASH run of each arm."""
    rows = [x.split() for x in open(path) if x.strip()]
    missing = [a for a in ARMS if not any(r[0].startswith(a) for r in rows)]
    if missing:
        print("RULE OPEN no run of arm " + " ".join(missing))
        return 0
    bad = [r[0] for r in rows if r[2] != "NO_CRASH"]
    print("RULE " + ("FAIL " + " ".join(bad) if bad else "PASS") + f": {len(rows) - len(bad)} of {len(rows)} runs NO_CRASH")
    return 0


''' + s[j:]
files["check0390.py"] = s

s = files["series0390.sh"]
i = s.index("# BC5 exp 0390 from the laptop:")
j = s.index("# usage: series0390.sh")
s = s[:i] + ("# BC5 exp 0390 from the laptop: the smoke, one run of each arm, one go0390.sh at a time, under one deadline of 30 min.\n"
             "# A run that did not reach the fight gets at most one replacement. Any stop ends the series.\n") + s[j:]
s = R(s, "LIMIT=6300; RUN_NEED=430   # 35 min for everything;", "LIMIT=1800; RUN_NEED=430   # 30 min for everything;")
s = re.sub(r"for t in G4:off [^;]*; do", 'for t in "${1:-P1}:on" Q1:on; do', s, count=1)
s = R(s, "# usage: series0390.sh     Exit:", "# usage: series0390.sh [first tag, P1 by default; the box refuses a used tag]     Exit:")
s = R(s, '*" saves same CLASS "*', '*" CLASS "*')
files["series0390.sh"] = s

s = files["pins0390.env"]
s = re.sub(r"NORMAL=[0-9a-f]+", "NORMAL=FILL", s)  # the private binary, known after the build
files["pins0390.env"] = s

s = files["box0390.sh"]
s = R(s, 'UNITS="src/kernel/pthread.cpp src/kernel/pthread.h src/kernel/semaphore.cpp src/libs/libKernel.cpp"', 'UNITS="src/libs/libAmpr.cpp"')
s = R(s, "#   box0390.sh build      private test build: four patched units, the shared objects otherwise (CPU only, nice 19, ~5 min)",
      "#   box0390.sh build      private test build: patched libAmpr.cpp, the shared objects otherwise (CPU only, nice 19, ~2 min)")
# Nothing is written before the lock is ours (LESSONS R35, R37).
s = R(s, '    mkdir -p "$R" || stop "cannot make $R"\n', "")
s = R(s, '    printf \'%s\\n\' "$line" > "$ID" || stop "cannot record the line; the lock is held: $line"\n',
      '    mkdir -p "$R" "$E/s" || stop "cannot make $R; the lock is held: $line"\n'
      '    printf \'%s\\n\' "$line" > "$ID" || stop "cannot record the line; the lock is held: $line"\n')
s = R(s, '    echo "claimed: $line"\n', '    { printf \'%s\\n\' "$line" >> "$W/BOX-QUEUE"; } 2> /dev/null || echo "the queue line was not written"\n    echo "claimed: $line"\n')
s = R(s, 'rm -rf "$S" "$E/obj"; mkdir -p "$S/src/bc5"', 'rm -rf "$S" "$E/obj"; mkdir -p "$S/src"')
s = R(s, '    cp "$HERE/cpu_model.hpp" "$S/src/bc5/" || stop "no cpu_model.hpp"\n', "")
s = R(s, '    python3 -I "$HERE/patch0390.py" "$S" > "$R/patch.out" 2>&1 || { cat "$R/patch.out"; stop "patch failed"; }\n',
      '    python3 -I "$HERE/patch0390.py" "$S" > "$R/patch.out" 2>&1 || { cat "$R/patch.out"; stop "patch failed"; }\n'
      '    (cd "$S" && sha256sum -c "$HERE/patched0390.sha256") >> "$R/units.txt" 2>&1 || { cat "$R/units.txt"; stop "the patched file is not the pin"; }\n')
s = R(s, "[ \"$(strings \"$bin\" | grep -c 'KYTY_BC5_0390_')\" -ge 11 ]", "[ \"$(strings \"$bin\" | grep -c 'KYTY_BC5_APR_PARK_TO_WORKER')\" -ge 1 ]")
s = R(s, 'sha256sum -c "$HERE/units.sha256"', 'sha256sum -c "$HERE/units0390.sha256"')
files["box0390.sh"] = s

s = files["build0390.py"]
i = s.index("UNITS = {")
j = s.index("def clean_compile(cmd):")
s = s[:i] + 'UNITS = {\n    "src/CMakeFiles/kyty_emulator.dir/libs/libAmpr.cpp.o": "src/libs/libAmpr.cpp",\n}\n' + s[j:]
s = R(s, "the shared normal build's compile commands for the private patched copies of\n# three units into private objects",
      "the shared normal build's compile command for the private patched copy of\n# libAmpr.cpp into a private object")
files["build0390.py"] = s

s = files["test0390run.sh"]
s = R(s, 'cat > "$F/fake.sh" <<EOF\n', 'cat > "$F/fake.sh" <<EOF\napr_threads() { cat "$F/apr-threads" 2> /dev/null; }\n')
s = R(s, 'echo OFF > "$F/fixline"\n  cp "$F/pins.good"', 'echo ON > "$F/fixline"; printf \'      1 bc5-apr-q1\n\' > "$F/apr-threads"\n  cp "$F/pins.good"')
s = re.sub(r"\bA(?=[0-9A-I][0-9NF]R?\b)", "P", s)  # every tag's arm letter
s = re.sub(r"(go P\w+) off\b", r"\1 on", s)
s = s.replace("fix off crash", "fix on crash").replace("fixarm off; ", "")
s = R(s, 'echo ON > "$F/fixline"; go P7F on', 'echo OFF > "$F/fixline"; go P7F on')
s = R(s, "grep -q 'KYTY_BC5_JOB_ARENA_FIX=0' \"$R/P1N-start.txt\"", "grep -q 'KYTY_BC5_JOB_ARENA_FIX=1' \"$R/P1N-start.txt\"")
s = R(s, "python check0390.py run PG2 off 1", "python check0390.py run PG2 on 1")
s = "\n".join(x for x in s.split("\n") if not x.startswith("saves_c() {"))  # 0390: no live-save sum anywhere
s = R(s, """ok "positive on: live saves untouched" || bad "live saves"\n""",
      """ok "positive on: live saves untouched" || bad "live saves"\n"""
      """  [ "$(cat "$R/P1N-savecopy.txt")" = "$(route_c)" ] && ok "positive on: the private copy's sum is the snapshot's" || bad "copy sum"\n"""
      """  grep -q 'saves() {\\|WANT_SAVES\\|LIVE=' "$RUND/s6n0390.sh" && bad "a live-save read is left" || ok "no live-save read in the runner"\n""")
i = s.index("if t rule; then")
j = s.index('echo "== $P passed, $N failed"')
s = s[:i] + open(f"{OUT}/test-arms0390.inc", encoding="utf-8", newline="").read() + s[j:]
files["test0390run.sh"] = s

for name, text in files.items():
    with open(f"{OUT}/{name}", "w", encoding="utf-8", newline="") as f:
        f.write(text)
    print(name, len(text))
