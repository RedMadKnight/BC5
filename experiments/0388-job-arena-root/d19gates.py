#!/usr/bin/env python3
"""D19: the written gates of one 180-s S6N smoke, read from the runner's files. Fails closed.
usage: d19gates.py normal|lean <runner rc> <raw dir> <tag> <stub baseline file>
Exit 0 only if every required file is there, readable and from this run, and every check passes. Anything else is
rc 1 (a failed gate) or rc 2 (bad arguments, an error in here). Last line: GATES PASS or GATES FAIL.

Both variants need: rc 0, verdict pass, an end at the cap, the run's exe, route save read, GPU time still growing near
the end, RT-on configuration, no crash, TIMEOUT, kernel or devcoredump evidence, no new or forbidden stub.
Normal also needs: enough flips, flips late in the run, a journal of this run without a `ray tracing off:` line.
Lean cannot show: flips or frame rate, TIMEOUT lines (no journal, no probe), that RT stayed on after the start (only
the configuration it started with), any `ray tracing off:` drop, or which route point was reached past the save read.
A pass says the build starts, runs the route and meets no fault in 180 s. It is not a frame-rate result and says
nothing about F403 or F443."""
import os, re, sys

MIN_FLIPS = 2500      # normal: BL01-BL33 on the same route ran 26.3-30.5 flips/s over 180 s, about 5,000
LAST_FPS_T = 150      # normal: seconds; a later fps line, or the flips stopped before the end
MIN_DURATION = 175    # seconds of the run
MIN_GPU_NS = 1000000000  # GPU time that must be added between the two fdinfo reads: a floor, not a measurement
MIN_GPU_SPAN = 30     # seconds between those reads
SLACK = 2             # seconds: file times against the start file
TITLE_RT = "raytracing.ppsa03671"
# strcpy_s: its NID, and its name in case the line prints the name
FORBIDDEN_STUBS = ("5Xa2ACNECdo", "strcpy_s")
CRASH = ("Access violation", "Segmentation", "Aborted", "terminate called", "exception_address")
STUB = re.compile(r"stubbed import #0x[0-9a-fA-F]+: ([^\[\s]+)")
FPS = re.compile(r"fps counter: t ([0-9.]+) s: (\d+) flips")
FD = re.compile(r"^\s*(\d+)\s+drm-engine-[a-z0-9_-]+:\s+(\d+) ns\s*$")
FDAT = re.compile(r"^at (\d+) s( \(end\))?:\s*$")
EXE = {"normal": "/exp0388/kyty_emulator", "lean": "/kytyplus-build-lean/src/kyty_emulator"}
REQUIRED = ("-verdict.txt", "-end.txt", "-start.txt", "-play.log", "-crash.txt", "-dmesg-after.txt", "-devcoredump.txt",
            "-probe.txt", "-journal.txt", "-summary.txt", "-route.txt", "-fdinfo.txt")


def read(path):
    """The text, or None if it cannot be read."""
    try:
        with open(path, "rb") as f:
            return f.read().decode("utf-8", "replace")
    except OSError:
        return None


def gpu_ns(text):
    """[(seconds, ns over all engines)] for each fdinfo read; uniq -c counts repeated lines."""
    out = []
    for line in text.splitlines():
        m = FDAT.match(line)
        if m:
            out.append([int(m.group(1)), 0])
            continue
        m = FD.match(line)
        if m and out:
            out[-1][1] += int(m.group(1)) * int(m.group(2))
    return out


def journal_drops(path):
    """Lines with `ray tracing off:`, or None if the journal cannot be read. The journal can be large."""
    n = 0
    try:
        with open(path, "rb") as f:
            for line in f:
                if b"ray tracing off:" in line:
                    n += 1
    except OSError:
        return None
    return n


def gates(variant, rc, raw, tag, baseline):
    fails = []
    if variant not in EXE:
        return ["invalid variant " + repr(variant)]
    if not re.fullmatch(r"[A-Za-z0-9]+", tag):
        return ["invalid tag " + repr(tag)]
    if not os.path.isdir(raw):
        return ["no raw directory " + raw]
    if not re.fullmatch(r"\d+", rc):
        fails.append("invalid runner rc " + repr(rc))
    elif rc != "0":
        fails.append("runner rc " + rc)
    p = lambda s: os.path.join(raw, tag + s)

    # Every required file: readable, and not older than this run's start.
    ev = {}
    for s in REQUIRED:
        ev[s] = read(p(s))
        if ev[s] is None:
            fails.append("missing or unreadable " + tag + s)
    if ev["-start.txt"] is None:
        fails.append("no start file: nothing can be tied to this run")
    else:
        t0 = os.path.getmtime(p("-start.txt"))
        for s in REQUIRED:
            if ev[s] is not None and os.path.getmtime(p(s)) < t0 - SLACK:
                fails.append("stale evidence " + tag + s)

    verdict = (ev["-verdict.txt"] or "").strip()
    if verdict != "pass":
        fails.append("runner verdict: " + (verdict or "none"))

    # The end line must say the cap stopped the run. HANG, DOWN, SETUP and `ended by itself` do not match.
    dur = 0
    end = (ev["-end.txt"] or "").strip()
    m = re.fullmatch(re.escape(tag) + r" stopped at (\d+) s \(after (\d+) s\)", end)
    if m:
        dur = int(m.group(2))
    else:
        fails.append("the run did not end at its cap: " + (end or "none"))
    if dur < MIN_DURATION:
        fails.append(f"ran {dur} s, under {MIN_DURATION}")

    # Fault evidence, read explicitly.
    crash = (ev["-crash.txt"] or "").strip()
    if crash:
        fails.append("crash lines: " + str(len(crash.splitlines())))
    kern = (ev["-dmesg-after.txt"] or "").strip()
    if kern:
        fails.append("kernel lines: " + str(len(kern.splitlines())))
    if (ev["-devcoredump.txt"] or "").strip():
        fails.append("a devcoredump appeared")
    nt = sum("TIMEOUT" in x for x in (ev["-probe.txt"] or "").splitlines())
    if nt:
        fails.append(f"{nt} TIMEOUT lines in the probe file")
    play = ev["-play.log"] or ""
    nt = sum("TIMEOUT" in x for x in play.splitlines())
    if nt:
        fails.append(f"{nt} TIMEOUT lines in the play log")
    for w in CRASH:
        if w in play:
            fails.append("crash text in the play log: " + w)
    if not play.strip() or play.startswith("no log of this run"):
        fails.append("no play log of this run")

    # This run's binary and mode: the exe path and the environment the emulator really had.
    start = ev["-start.txt"] or ""
    if not re.search(r"^arm " + re.escape(tag) + r",", start, re.M):
        fails.append("the start file is not of tag " + tag)
    exes = re.findall(r"^emulator pid \d+ exe (\S+) cwd \S+", start, re.M)
    if len(exes) != 1 or not exes[0].endswith(EXE[variant]):
        fails.append("the emulator was not the " + variant + " binary: " + (" ".join(exes) or "none"))
    envs = re.findall(r"^environ: (.*)$", start, re.M)
    env = {}
    if len(envs) != 1:
        fails.append("no environ line in the start file")
    else:
        env = dict(x.split("=", 1) for x in envs[0].split() if "=" in x)
    if variant == "lean" and (env.get("BC5_LEAN") != "1" or env.get("BC5_LOGS") != "1"):
        fails.append("lean without BC5_LEAN=1 BC5_LOGS=1")
    if variant == "normal" and "BC5_LEAN" in env:
        fails.append("normal with BC5_LEAN set")

    # RT on at the start, both variants: the switch and the configuration the emulator was given.
    if env.get("KYTY_BC5_RT") == "0":
        fails.append("KYTY_BC5_RT=0: ray tracing started off")
    cfg = env.get("KYTY_BC5_INPUT_CONFIG")
    text = read(cfg) if cfg else None
    if text is None:
        fails.append("no readable input configuration in the emulator's environment")
    else:
        rt = [x.split("=", 1) for x in text.splitlines() if x.strip().lower().startswith(TITLE_RT + "=")]
        if len(rt) != 1 or rt[0][1].strip() != "on":
            fails.append("the input configuration does not say RayTracing.PPSA03671=on once")

    # RT stayed on, where a journal exists. Normal must have one; lean has none.
    jt = (ev["-journal.txt"] or "").strip()
    jm = re.match(r"journal (\S+)", jt)
    if jm:
        drops = journal_drops(jm.group(1))
        if drops is None:
            fails.append("the journal cannot be read: " + jm.group(1))
        elif drops:
            fails.append(f"{drops} ray tracing off lines in the journal")
        elif ev["-start.txt"] is not None and os.path.getmtime(jm.group(1)) < os.path.getmtime(p("-start.txt")) - SLACK:
            fails.append("stale journal " + jm.group(1))
    elif variant == "normal":
        fails.append("no journal of this run: RT on is not shown")

    # Route and progress, both variants: the route save was read, and the GPU kept working into the end.
    if not re.search(r"^routed at \d+ s: \S", ev["-route.txt"] or "", re.M):
        fails.append("the route save read is not shown")
    gpu = gpu_ns(ev["-fdinfo.txt"] or "")
    if len(gpu) < 2:
        fails.append("under two fdinfo reads: GPU progress is not shown")
    else:
        span, grew = gpu[-1][0] - gpu[0][0], gpu[-1][1] - gpu[0][1]
        print("gpu", grew, "ns over", span, "s")
        if span < MIN_GPU_SPAN or grew < MIN_GPU_NS:
            fails.append(f"GPU time grew {grew} ns over {span} s, under {MIN_GPU_NS} ns over {MIN_GPU_SPAN} s")

    if variant == "normal":
        n, last = 0, 0.0
        for g in FPS.finditer(play):
            last = max(last, float(g.group(1)))
            n += int(g.group(2))
        if n < MIN_FLIPS:
            fails.append(f"{n} flips, under {MIN_FLIPS}")
        if last < LAST_FPS_T:
            fails.append(f"last fps line at {last} s, under {LAST_FPS_T}")
        print("flips", n, "last at", last)
    else:
        print("lean: flips, TIMEOUT lines and RT after the start are not observable")

    # Stubs: both variants. The baseline must be there and valid; an unparsable stub line fails.
    btext = read(baseline)
    base = set()
    if btext is None:
        fails.append("missing or unreadable baseline " + baseline)
    else:
        base = set(x.strip() for x in btext.splitlines() if x.strip())
        if not base or any(re.search(r"[\s\[\]#]", x) for x in base):
            fails.append("invalid baseline " + baseline)
            base = set()
    lines = [x for x in play.splitlines() if "stubbed import #" in x]
    stubs = set()
    for x in lines:
        g = STUB.search(x)
        if g:
            stubs.add(g.group(1))
        else:
            fails.append("unparsable stub line: " + x[:80])
    new = sorted(stubs - base)
    print(f"stubs {len(stubs)}, baseline {len(base)}, new {len(new)}")
    if base:
        for s in new:
            print("new stub", s)
            fails.append("new stub " + s)
    for s in FORBIDDEN_STUBS:
        if any(s in x for x in stubs):
            fails.append("forbidden stub " + s)
    print("duration", dur, "verdict", verdict or "none")
    return fails


def main():
    if len(sys.argv) != 6:
        print(__doc__)
        print("FAIL wrong arguments")
        print("GATES FAIL")
        return 2
    try:
        fails = gates(*sys.argv[1:6])
    except Exception as e:  # any surprise is a failed gate
        print("FAIL error in the gates:", repr(e))
        print("GATES FAIL")
        return 2
    for f in fails:
        print("FAIL", f)
    print("GATES PASS" if not fails else "GATES FAIL")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
