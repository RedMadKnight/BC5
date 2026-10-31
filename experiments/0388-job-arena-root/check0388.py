#!/usr/bin/env python3
"""Exp 0388: classify one fight run from the runner's files, fails closed; and the series rule.
usage: check0388.py run <tag> <on|off> <runner rc> <raw dir> <stub baseline>
       check0388.py rule <file of lines: tag fix class crash>
Run mode prints its reasons and ends with one line:  CLASS <class> fix <on|off> crash <none|target|other> reached <0|1>
Classes: NO_CRASH, CRASH_TARGET, CRASH_OTHER, NOT_ROUTED, INVALID, KERNEL. Exit 0 for a valid class, 1 for INVALID or
KERNEL, 2 for bad arguments. A class needs this run's own evidence: the emulator's environment as the table demands
(d19manifest.py with this experiment's paths and the fix switch), its own journal readable and fresh with no RT-off
line and with frame profiles, its own play log with the fix line of this arm. NO_CRASH also needs every d19gates.py
gate. Missing evidence is INVALID, never a zero count."""
import os, re, sys

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import d19gates as g
import d19manifest as m

REQUIRED = ("-verdict.txt", "-end.txt", "-start.txt", "-play.log", "-dmesg-after.txt", "-devcoredump.txt", "-journal.txt",
            "-environ.bin", "-reads.txt")
AV = "Access violation: Read [000000000000000c]"
SITE = ("off=0000000003d7eca0, module=eboot.bin", "kyty_exception_handler: 0000000903d7eca0")
ANY = ("Access violation", "Segmentation", "Aborted", "terminate called")
FIXLINE = re.compile(r"job-arena fix (ON|OFF) for PPSA03671")


ARMS = {
    "C": "KYTY_BC5_0388_TRACE=1",
    "G": "KYTY_BC5_0388_TRACE=1",
    "A": "KYTY_BC5_0388_CPU_MASK=1 KYTY_BC5_0388_TRACE=1",
    "B": "KYTY_BC5_0388_CPU_MASK=1 KYTY_BC5_0388_CURRENT_CPU=1 KYTY_BC5_0388_APPLY_AFFINITY=1 KYTY_BC5_0388_TRACE=1",
    "D": "KYTY_BC5_0388_PUSH_SPIN_US=200 KYTY_BC5_0388_TRACE=1",
    "E": "KYTY_BC5_0388_PUSH_SPIN_US=500 KYTY_BC5_0388_TRACE=1",
    "F": "KYTY_BC5_0388_PUSH_UNTIL_TAKEN_US=500 KYTY_BC5_0388_TRACE=1",
}


def tables(fix, tag):
    """d19manifest's tables with this experiment's private paths and the one switch of the arm."""
    for k, v in list(m.COMMON.items()):
        if isinstance(v, str):
            m.COMMON[k] = v.replace("bc5-work/d19/run/", "bc5-work/exp0388/run/")
        elif isinstance(v, re.Pattern):
            m.COMMON[k] = re.compile(v.pattern.replace("bc5-work/d19/run/", "bc5-work/exp0388/run/"))
    m.COMMON["KYTY_BC5_JOB_ARENA_FIX"] = "1" if fix == "on" else "0"
    for kv in ARMS[tag[0]].split():  # 0388: exactly the arm's switches; any other 0388 name stays unknown and blocks
        k, v = kv.split("=")
        m.COMMON[k] = v


def manifest(raw, tag, fix):
    """The blocking reasons of the environment dump, and the dump's entries."""
    p = lambda s: os.path.join(raw, tag + s)
    data = open(p("-environ.bin"), "rb").read()
    start = open(p("-start.txt"), encoding="utf-8", errors="replace").read()
    fails, _ = m.identity(start, data, tag, "normal")
    if os.path.getmtime(p("-environ.bin")) < os.path.getmtime(p("-start.txt")) - m.SLACK:
        fails.append("stale dump")
    entries = m.parse_environ(data)
    tables(fix, tag)
    import contextlib, io
    with contextlib.redirect_stdout(io.StringIO()):
        fails += m.check("normal", entries, tag, set())
    return fails, dict(entries)


def common(tag, rc, raw, baseline, not_routed):
    """Every d19gates gate that every arm must meet. Only what an intended crash or an unrouted run cannot show is dropped:
    the runner's own status for that outcome, the cap and duration, the crash text, progress and flips, the second fdinfo
    read. Kernel, devcoredump, TIMEOUT, stale files, stubs, RT and journal gates all stay."""
    import contextlib, io
    with contextlib.redirect_stdout(io.StringIO()):
        gf = g.gates("normal", rc, raw, tag, baseline)
    drop = ["the run did not end at its cap: ", "ran ", "crash lines: ", "crash text in the play log: ", "under two fdinfo reads",
            "GPU time grew", "last fps line at ", "missing or unreadable " + tag + "-fdinfo.txt"]
    if rc == "1":
        drop += ["runner rc 1", "runner verdict: CRASH: "]
    if not_routed:
        drop += ["runner verdict: FAIL:", "the route save read is not shown", "missing or unreadable " + tag + "-route.txt"]
    return [x for x in gf if not x.startswith(tuple(drop)) and not re.fullmatch(r"\d+ flips, under \d+", x)]


def classify(tag, fix, rc, raw, baseline):
    """(class, crash, reached, reasons)"""
    reasons = []
    p = lambda s: os.path.join(raw, tag + s)
    ev = {}
    for s in REQUIRED:
        if s == "-environ.bin":
            ev[s] = "" if os.path.isfile(p(s)) else None
        else:
            ev[s] = g.read(p(s))
        if ev[s] is None:
            reasons.append("missing " + tag + s)
    if reasons:
        return "INVALID", "none", 0, reasons
    t0 = os.path.getmtime(p("-start.txt"))
    for s in REQUIRED:
        if os.path.getmtime(p(s)) < t0 - g.SLACK:
            reasons.append("stale " + tag + s)
    if not re.fullmatch(r"\d+", rc):
        reasons.append("invalid runner rc " + rc)

    verdict = ev["-verdict.txt"].strip()
    end = ev["-end.txt"].strip()
    kern = ev["-dmesg-after.txt"].strip()
    if kern or ev["-devcoredump.txt"].strip() or verdict.startswith(("HANG", "DOWN")):
        return "KERNEL", "none", 0, reasons + ["kernel lines, a devcoredump, or a hang: " + verdict]
    if rc == "3":
        return "INVALID", "none", 0, reasons + ["the live saves changed"]
    if rc not in ("0", "1"):
        reasons.append("the runner did not finish, rc " + rc)

    fails, env = manifest(raw, tag, fix)
    reasons += ["manifest: " + f for f in fails]
    if ev["-reads.txt"].strip() != "kernel 1 devcore 1":
        reasons.append("the kernel or devcoredump read did not succeed: " + ev["-reads.txt"].strip())
    not_read = "route save was not read" in end
    if not_read:
        reasons += ["gate: " + x for x in common(tag, rc, raw, baseline, True)]
        if reasons:
            return "INVALID", "none", 0, reasons
        return "NOT_ROUTED", "none", 0, ["the route save was not read"]

    # This run's journal: the path must be the emulator's own.
    jm = re.match(r"journal (\S+)", ev["-journal.txt"].strip())
    gc = env.get("BC5_GC_DUMP_DIR", "")
    if not jm:
        reasons.append("no journal of this run: RT on is not shown")
    elif not gc or jm.group(1) != gc + "/direct.log":
        reasons.append("the journal is not the one in the emulator's environment")
    else:
        drops = g.journal_drops(jm.group(1))
        if drops is None:
            reasons.append("the journal cannot be read")
        elif drops:
            reasons.append(f"{drops} ray tracing off lines")
        elif os.path.getmtime(jm.group(1)) < t0 - g.SLACK:
            reasons.append("stale journal")
        else:
            with open(jm.group(1), "rb") as f:
                if b"frame profile: t" not in f.read():
                    reasons.append("the journal has no frame profile line")

    # This run's log, and the arm the emulator itself reports.
    play = ev["-play.log"]
    if not play.strip() or play.startswith("no log of this run"):
        reasons.append("no play log of this run")
    arms = set(FIXLINE.findall(play))
    if arms != {"ON" if fix == "on" else "OFF"}:
        reasons.append(f"the fix line of the log says {sorted(arms) or 'nothing'}, the arm is {fix}")

    # Reached the fight: the load was seen, then gameplay, then the inputs went in.
    done = g.read(p("-phase2-done.txt")) or ""
    pm = re.match(r"phase2 appended (\d+) load (\d+) gameplay ([01]) lines (\d+)", done)
    reached = 1 if pm and pm.group(3) == "1" and int(pm.group(4)) > 0 else 0

    crash = "none"
    if any(w in play for w in ANY):
        crash = "target" if AV in play and any(s in play for s in SITE) else "other"
    reasons += ["gate: " + x for x in common(tag, rc, raw, baseline, not reached)]
    if reasons:
        return "INVALID", crash, reached, reasons
    if end.split(" ", 1)[-1].startswith("SETUP"):
        return "INVALID", crash, reached, ["setup: " + end]
    if not reached:
        return "NOT_ROUTED", crash, 0, ["the Continue load and gameplay were not both seen: " + (done.strip() or "no phase 2")]
    if re.search(r" ended by itself at \d+ s", end) or crash != "none":
        if crash == "none":
            return "CRASH_OTHER", "other", reached, ["the emulator ended by itself with no crash line"]
        return ("CRASH_TARGET" if crash == "target" else "CRASH_OTHER"), crash, reached, []
    gf = g.gates("normal", rc, raw, tag, baseline)
    if gf:
        return "INVALID", crash, reached, ["gate: " + x for x in gf]
    return "NO_CRASH", "none", reached, []


def rule(path):
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


def main():
    a = sys.argv[1:]
    if len(a) == 2 and a[0] == "rule":
        return rule(a[1])
    if len(a) != 6 or a[0] != "run" or a[2] not in ("on", "off") or not re.fullmatch(r"[A-Za-z0-9]+", a[1]):
        print(__doc__)
        return 2
    _, tag, fix, rc, raw, baseline = a
    try:
        cl, crash, reached, why = classify(tag, fix, rc, raw, baseline)
    except Exception as e:  # any unreadable piece blocks
        cl, crash, reached, why = "INVALID", "none", 0, ["error: " + repr(e)]
    for x in why:
        print(x)
    print(f"CLASS {cl} fix {fix} crash {crash} reached {reached}")
    return 1 if cl in ("INVALID", "KERNEL") else 0


if __name__ == "__main__":
    sys.exit(main())
