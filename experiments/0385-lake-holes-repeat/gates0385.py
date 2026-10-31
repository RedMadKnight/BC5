#!/usr/bin/env python3
"""BC5 experiment 0385: the fail-closed gates of one lake run. Nothing here sources, runs or deletes anything.
usage: gates0385.py manifest <environ dump> <token> <tag>   this emulator's effective options against the table
       gates0385.py check <exp dir> <tag> pre|post          one run's evidence: exit 0 pass, 10 route failure, 1 stop
       gates0385.py decide <tz file> <mean patch>           the README's decision rule on one run
       gates0385.py arms <patch file> <arms file> <switch lines>   each arm's shots against the all-off shots
The table is D19's, copied from coordination/d19/d19manifest.py (sha256 ce98521e) with this experiment's private paths
and mark, for launcher 55531ab6 and bc5-run.env cb8ad5fc. It is an allow list: a missing, changed, forbidden or unknown
option blocks. The manifest prints table names and their values only; session names are counted, never printed, so its
output can go to Git while the raw dump stays private. Missing or unreadable evidence is a stop, never a zero."""
import os, re, statistics, sys

# Presence blocks, whatever the value (=0 too): experiments and diagnostics no lake run may carry.
FORBIDDEN = tuple("BC5_DIRECT_" + x for x in (
    "ARGS_COPY", "ARGS_WB", "ARGS_FLUSH", "ARGS_FLUSH_DRAWS", "FORCE_START_000", "GPU_CHECK_ZERO", "GPU_CHECK_YZ",
    "REBASE_DISPATCH", "CHAIN_BREAK_AT", "DRAW_ARGS_JOURNAL", "BO_JOURNAL", "ARGS_HISTOGRAM", "ZERO_SKIP",
    "ZEROSCAN_AT", "ZEROSCAN_OUT", "ACB_STATE_RESTORE", "PIECES_NO_CLEAR", "INDEX_BASE_DUP", "NO_CARRY",
    "MEC_SKIP_PGM", "MEC_ONLY_PGM")) + ("KYTY_BC5_RT",)

# A name with one of these prefixes that no table holds blocks. The emulator reads no other prefix (candidate inventory:
# BC5_, KYTY_, plus HOME, MANGOHUD_*, PIPEWIRE_PROPS, SDL_AUDIODRIVER); the rest reach it through libraries and drivers.
OPTION = ("BC5_", "KYTY_", "SHADPS4_", "SDL_", "PLAY_", "MALLOC_", "MANGOHUD", "PIPEWIRE_", "D19_", "LD_", "GLIBC_",
          "MESA_", "RADV_", "ACO_", "AMD_", "VK_", "GALLIUM_")

# Reviewed system background, observed on the host and in the toolbox. Exact value only; not derived from the launcher.
SYSTEM_BACKGROUND = {"SDL_VIDEO_MINIMIZE_ON_FOCUS_LOSS": "0"}

# The guards named by the reviews. They are also on the tables; these are named again so their loss reads as such.
GUARDS = ("BC5_DIRECT_GPU_CHECK", "BC5_DIRECT_GPU_CHECK_PRODUCT", "BC5_DIRECT_SHADOW_LABELS", "BC5_DIRECT_HOST_INDIRECT",
          "BC5_DIRECT_COMPUTE_RING", "BC5_DIRECT_CROSS_RING_WAITS", "BC5_DIRECT_RING_DEPS", "BC5_DIRECT_SOFT_WAIT_MS",
          "BC5_DIRECT_TWO_RING_WAIT_MS", "BC5_DIRECT_RING_ORDER_WAITS", "BC5_DIRECT_DMA_SYNC", "BC5_DIRECT_RINGS",
          "BC5_DIRECT_MAX_IN_FLIGHT", "BC5_DIRECT_ASYNC", "BC5_DIRECT_RING_ASYNC", "BC5_DIRECT_CHAIN")

RT_BUILD = "909974400,909939400,909936c00,909939700,909939900,909974200,909973900,909973b00,909973d00,909973f00,11d049aa00,11d04a6000,11d04bb900"
EAGER = "RenderGpuWcLarge,RenderGpuWcSmall,RenderGpuRwLarge,RenderGpuRwSmall,CommitIABufferAllocator,AMM,RenderAlloc,Physics,Decal Job Scheduler,VisualEffectInstanceHeap,DynamicHeap,DynamicHeap Small,ComponentHeap,ComponentHeap Small,MaterialHeap,DDLHeap,Physics query allocator"
# Both variants, in the order the chain settles them. {HOME} is the HOME of the dump.
COMMON = {
    # bc5-run.env
    "BC5_GC_MODE": "direct", "BC5_DIRECT_STAGE": "all", "BC5_DIRECT_RINGS": "1", "BC5_DIRECT_REOPEN": "1",
    "BC5_DIRECT_GDS_KIB": "64", "BC5_DIRECT_OA": "16", "BC5_DIRECT_GWS": "64", "BC5_DIRECT_GDS_ALL": "1",
    "BC5_DIRECT_GDS_SHADOW": "1", "BC5_DIRECT_JOURNAL": "min", "BC5_DIRECT_ASYNC": "1",
    "KYTY_BC5_ALL_RW": "1", "KYTY_BC5_DMABUF": "1", "KYTY_BC5_CACHE_MIB": "96,16,16,16", "KYTY_BC5_VMA_BLOCK_MIB": "16",
    "KYTY_GUEST_MEMORY_MB": "13824", "SDL_JOYSTICK_DISABLE_UDEV": "1", "SDL_VIDEODRIVER": "wayland",
    "BC5_DIRECT_RING_ASYNC": "1", "BC5_DIRECT_MAX_IN_FLIGHT": "24", "BC5_DIRECT_PIECES_DRY": "1", "BC5_DIRECT_PIECES_FULL": "1",
    # play-pkg.sh 55531ab6
    "BC5_DIRECT_LAZY_NAMES": "orbis_user_malloc,Wwise,SoundAlloc,FileSystem,UIStringAlloc",
    "SHADPS4_SYSMODULES_PACK_DIR": "{HOME}/bc5-data/sysmodules-pack-hle-ampr-noplaygo", "BC5_DIRECT_EAGER_NAMES": EAGER,
    "BC5_DIRECT_MEC_INDIRECT": "1", "BC5_DIRECT_GPU_CHECK": "1", "BC5_DIRECT_DMA_SYNC": "1", "BC5_DIRECT_RING_ORDER_WAITS": "1",
    "BC5_DIRECT_REMEMBER_UNMAPPED": "1", "KYTY_BC5_APR_PARALLEL": "8", "BC5_MOUNT_DISK_CACHE": "{HOME}/bc5-data/cache/bc5-mount",
    "BC5_DIRECT_DMA_SNAPSHOT": "4096", "BC5_DIRECT_GC_TF_RING": "1", "BC5_DIRECT_FLAT_APERTURE": "1", "BC5_DIRECT_AMM_PRT": "1",
    "BC5_DIRECT_SKIP_PGM": "0", "KYTY_BC5_RT_BUILD_PGM": RT_BUILD, "BC5_DIRECT_CHAIN": "2", "BC5_DIRECT_CS_PREFIX": "1",
    "KYTY_BC5_APR_READAHEAD": "4", "KYTY_BC5_MIN_FLIP_RATE": "0", "BC5_DIRECT_INDIRECT_DRAWS": "multi", "BC5_DIRECT_ALIASES": "1",
    "BC5_DIRECT_COMPUTE_RING": "-1", "BC5_DIRECT_CROSS_RING_WAITS": "all", "BC5_DIRECT_GPU_CHECK_PRODUCT": "1",
    "BC5_DIRECT_SHADOW_LABELS": "1", "BC5_DIRECT_HOST_INDIRECT": "learn:1100000000", "BC5_DIRECT_SOFT_WAIT_MS": "8",
    "BC5_DIRECT_RING_DEPS": "dcb", "BC5_DIRECT_TWO_RING_WAIT_MS": "4",
    # this experiment's private launcher and its launch line
    "KYTY_BC5_SAVEDATA_DIR": "{HOME}/bc5-work/exp0385/wd/_SaveData-pkg-play",
    "BC5_DIRECT_LEARNED": "{HOME}/bc5-work/exp0385/direct-learned-pkg.txt",
    "KYTY_BC5_INPUT_CONFIG": re.compile(r"/.*/bc5-work/exp0385/input-0385\.cfg"),
    "BC5_0385_INPUT_CONFIG": re.compile(r"/.*/bc5-work/exp0385/input-0385\.cfg"),
    "KYTY_BC5_INPUT_CMD": None,  # filled from the tag
    "BC5_0385_OWNER": None,      # filled from the token
    # exported by play-pkg.sh; not options, their values come from the session
    "XDG_RUNTIME_DIR": re.compile(r"/run/user/\d+"), "WAYLAND_DISPLAY": re.compile(r".+"), "DISPLAY": re.compile(r".+"),
}
NORMAL = {
    "KYTY_BC5_INPUT_RECORD": "/home/kjaniszewski/bc5-work/route-record.txt", "PLAY_CAPTURE": "1",
    "BC5_DIRECT_TIMEOUT_PROBE": "1", "BC5_DIRECT_TIMING": "1", "BC5_DIRECT_FRAME_PROFILE": "1",
    "BC5_GC_DUMP_DIR": re.compile(r"\{HOME\}/bc5-data/captures/play-\d{8}-\d{4}/gc"),
    "KYTY_BC5_FPS_COUNTER": "1", "KYTY_BC5_AUDIO_TRACE": "1", "KYTY_BC5_MEASURE": "1",
}

# Least evidence of a run that reached the lake. K2 and K3 had 2,228 and 2,069 frames, 408 and 372 snapshots, 37 and 182
# finals used; a route that missed the lake polls an image that does not change.
SHOTS, FRAMES_MIN, SNAPS_MIN, FLIPS_MIN, FINALS_MIN = 53, 500, 100, 1000, 30
# Shots 0-16 run with every switch off (arms0385.txt): they alone decide whether a run qualifies. CLEAN is above the clean
# level with RT on (K2 9.2, K3 9.9, H1 9.7).
BASE_SHOTS, QUALIFY, CLEAN = 17, 20.0, 12.0
MAX_ENVIRON = 1 << 20


def table(home, token, tag):
    """name -> exact text, or a compiled pattern."""
    t = dict(COMMON)
    t.update(SYSTEM_BACKGROUND)
    t.update(NORMAL)
    out = {}
    for k, v in t.items():
        if isinstance(v, str):
            v = v.replace("{HOME}", home)
        elif isinstance(v, re.Pattern) and r"\{HOME\}" in v.pattern:
            v = re.compile(v.pattern.replace(r"\{HOME\}", re.escape(home)))
        out[k] = v
    out["BC5_0385_OWNER"] = token
    out["KYTY_BC5_INPUT_CMD"] = re.compile(r"/.*/bc5-work/exp0385/r-" + re.escape(tag) + r"/input\.cmd")
    # the test build: its binary and its switches
    out["BC5_EMU"] = re.compile(r"/.*/bc5-work/exp0385/tb/kyty_emulator")
    out["BC5_DIRECT_LAKE_CTL"] = re.compile(r"/.*/bc5-work/exp0385/r-" + re.escape(tag) + r"/lake\.ctl")
    out["BC5_DIRECT_LAKE_OUT"] = re.compile(r"/.*/bc5-data/priv/exp0385/" + re.escape(tag) + r"/zpass\.dat")
    return out


def matches(want, value):
    return bool(want.fullmatch(value)) if isinstance(want, re.Pattern) else value == want


def parse_environ(data):
    """[(name, value)] in dump order; raises on anything a whole environ cannot be."""
    if not data:
        raise ValueError("an empty dump")
    if len(data) > MAX_ENVIRON:
        raise ValueError("a dump over 1 MiB")
    if not data.endswith(b"\0"):
        raise ValueError("a truncated dump: no final NUL")
    out = []
    for x in data[:-1].split(b"\0"):
        if not x or b"=" not in x:
            raise ValueError("a malformed entry in the dump")
        k, v = x.split(b"=", 1)
        k = k.decode("utf-8", "surrogateescape")
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", k):
            raise ValueError("a malformed name in the dump")
        out.append((k, v.decode("utf-8", "surrogateescape")))
    return out


def check_manifest(entries, token, tag):
    """(lines to print, blocking reasons)."""
    fails, shown, seen = [], [], {}
    for k, v in entries:
        if k in seen:
            fails.append("duplicate entry " + k)
        seen.setdefault(k, v)
    home = seen.get("HOME")
    if not home:
        return shown, fails + ["no HOME in the dump"]
    want = table(home, token, tag)
    session = 0
    for k, v in entries:
        if k in FORBIDDEN:
            fails.append("forbidden name " + k)
        elif k in want:
            shown.append(f"{k}={v}")
            if not matches(want[k], v):
                fails.append(f"{k} is not the chain's value")
        elif k.startswith(OPTION):
            fails.append("an option the chain does not set: " + k)
        else:
            session += 1
    for k in want:
        if k not in seen:
            fails.append(("missing guard " if k in GUARDS else "missing chain name ") + k)
    shown.append(f"{session} session names, not options, not printed")
    return shown, fails


def cmd_manifest(dump, token, tag):
    try:
        with open(dump, "rb") as f:
            entries = parse_environ(f.read())
    except (OSError, ValueError) as e:
        print("error:", e)
        print("MANIFEST FAIL")
        return 1
    shown, fails = check_manifest(entries, token, tag)
    print("\n".join(shown))
    for x in fails:
        print("FAIL:", x)
    print("MANIFEST FAIL" if fails else "MANIFEST PASS")
    return 1 if fails else 0


def read(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return None


def kv(path):
    t = read(path)
    if t is None:
        return None
    return {x[0]: (x[1].strip() if len(x) > 1 else "") for x in (l.split(" ", 1) for l in t.splitlines() if l)}


def number(d, name):
    """An int from a kv dict, or None: an empty count is a failed read, never a zero."""
    v = d.get(name, "") if d else ""
    return int(v) if re.fullmatch(r"\d+", v) else None


def patch_values(text):
    return [float(x) for x in re.findall(r"png: patch\s+([0-9.]+) %", text or "")]


def tz_summary(text):
    """The number of finals from tz's four summary lines, or None if any is missing."""
    lines = [l for l in (text or "").splitlines() if l.startswith("#")]
    m = re.match(r"# (\d+) finals;", lines[0]) if lines else None
    want = ("# tiles with a hole", "# mid against", "# changed dwords")
    if not m or not all(any(l.startswith(w) for l in lines) for w in want):
        return None
    return int(m.group(1))


def run_check(exp, tag, stage):
    """(stops, routes, mean patch or None). Stops outrank a route failure."""
    p = lambda s: os.path.join(exp, tag + s)
    stop, route = [], []
    k = kv(p(".kernel.txt"))
    if number(k, "lines") != 0:
        stop.append("kernel lines, or no kernel record")
    if number(k, "devcoredumps") != 0:
        stop.append("a devcoredump, or no devcoredump record")
    saves = read(p(".saves.txt"))
    rows = re.findall(r"^(live|lake|learned) (\S*) want (\S*)$", saves or "", re.M)
    if {r[0] for r in rows} != {"live", "lake", "learned"} or len(rows) != 3:
        stop.append("no saves record")
    for name, got, want in rows:
        if not got or got != want:
            stop.append(f"{name} changed: {got or 'unreadable'}, want {want}")
    man = read(p(".manifest.txt"))
    if man is None or man.strip().splitlines()[-1:] != ["MANIFEST PASS"]:
        stop.append("no passing manifest")
    j = kv(p(".journal.txt"))
    if j is None:
        stop.append("no journal record")
    elif "why" in j:
        stop.append("journal: " + j["why"])
    else:
        for name, what in (("rtoff", "ray tracing off"), ("skip", "skip pgm"), ("timeouts", "TIMEOUT")):
            n = number(j, name)
            if n is None:
                stop.append(f"the journal's {what} count could not be read")
            elif n:
                stop.append(f"{n} {what} lines in the journal")
        if number(j, "flips") is None:
            stop.append("the journal's flip count could not be read")
    r = kv(p(".route.txt"))
    b, q, s = number(r, "bench_rc"), number(r, "poller_rc"), number(r, "save_read")
    if b is None or q is None or s is None:
        stop.append("no route record")
    else:
        if b != 0:
            route.append(f"the bench exited {b}")
        if s != 1:
            route.append("the lake save was not read")
        if number(r, "capped") != 0:
            route.append("the emulator's time ran out")
        if b == 0 and q != 0:
            stop.append(f"the poller exited {q}")
        if b == 0 and q == 0:
            # a route that missed the lake polls an image that does not change: this comes before any analysis of it
            m = re.search(r"; (\d+) frames; (\d+) captures, (\d+) snapshots", read(p(".pl.txt")) or "")
            if not m:
                stop.append("no poller summary")
            elif int(m.group(1)) < FRAMES_MIN or int(m.group(3)) < SNAPS_MIN:
                route.append(f"{m.group(1)} frames, {m.group(3)} snapshots: the lake was not reached")
    mean = None
    if stage == "post":
        if number(r, "ana_rc") != 0:
            stop.append("the analysis failed: " + " ".join((read(p(".ana.log")) or "no log").split())[:120])
        v = patch_values(read(p(".patch.txt")))
        if len(v) != SHOTS:
            stop.append(f"{len(v)} patch values, want {SHOTS}")
        else:
            mean = sum(v[:BASE_SHOTS]) / BASE_SHOTS
        if (number(j, "flips") or 0) < FLIPS_MIN:
            route.append(f"{j.get('flips') if j else '?'} flips")
        if not (read(p(".bursts.txt")) or "").strip():
            stop.append("no bursts")
        n = tz_summary(read(p(".tz.txt")))
        if n is None:
            stop.append("tz's summary is missing or incomplete")
        elif n < FINALS_MIN:
            route.append(f"{n} finals: the lake was not reached")
    return stop, route, mean


def cmd_check(exp, tag, stage):
    stop, route, mean = run_check(exp, tag, stage)
    for x in stop:
        print("STOP:", x)
    for x in route:
        print("ROUTE:", x)
    if stop:
        print("GATES STOP: " + "; ".join(stop))
        return 1
    if route:
        print("GATES ROUTE: " + "; ".join(route))
        return 10
    if stage == "pre":
        print("GATES PRE PASS")
        return 0
    print(f"GATES PASS mean patch {mean:.1f} qualify {'yes' if mean >= QUALIFY else 'no'}")
    return 0


def periods(text):
    """[(switches, counts)] from the host's lines: what each span of the run's switches did."""
    out, cur = [], ""
    for line in (text or "").splitlines():
        m = re.search(r"experiment 0385 at [0-9.]+ ms: (.*)$", line)
        if m:
            cur = m.group(1).strip()
            continue
        m = re.search(r"experiment 0385 period: (.*)$", line)
        if m:
            w = m.group(1).split()
            out.append((cur, dict(zip(w[0::2], (int(x) for x in w[1::2])))))
    return out


def effective(text, counts):
    """Did the host's own counts show this arm's switches doing something? Each switch has its own count."""
    t = text.split()
    checks = []
    if "cull=1" in t:
        checks.append(counts.get("cull_barriers", 0) > 0)
    if "dbmeta=1" in t:
        checks.append(counts.get("htile_fills", 0) > 0)
    if "trackercf=1" in t:
        checks.append(counts.get("chain_stops", 0) > 0)
    if [x for x in t if x not in ("cull=1", "dbmeta=1", "trackercf=1") and not x.startswith("cache_at=")]:
        checks.append(counts.get("inserted_words", 0) > 0)
    return any(checks)


def arms(patch_text, arms_text, switch_text):
    """[(first shot, switches, shot values, verdict)]. The README's rule: with all-off shots at QUALIFY or more, an arm clears
    the holes if every one of its shots is at CLEAN or less. An arm the host's counts do not show working is not called anything
    else: its shots say nothing about its fix."""
    v = patch_values(patch_text)
    spans = periods(switch_text)
    rows = []
    for line in arms_text.splitlines():
        if line and not line.startswith("#"):
            a, _, b = line.partition("|")
            rows.append((int(a), b.strip()))
    base = v[:BASE_SHOTS]
    level = statistics.median(base) if base else 0.0
    out, at = [], 0
    for k, (first, text) in enumerate(rows):
        last = rows[k + 1][0] if k + 1 < len(rows) else len(v)
        got = v[first:last]
        worked = False
        if text:
            tokens = text.split()
            for n in range(at, len(spans)):
                if all(x in spans[n][0].split() for x in tokens):
                    worked = effective(text, spans[n][1])
                    at = n + 1
                    break
        if not text:
            verdict = "all off"
        elif not worked:
            verdict = "NOT EFFECTIVE: the host's counts show nothing"
        elif level < QUALIFY:
            verdict = "no verdict: no holes in the all-off shots"
        elif got and max(got) <= CLEAN:
            verdict = "CLEARS"
        else:
            verdict = "no effect" if got else "no shots"
        out.append((first, text, got, verdict))
    return out


FINAL = re.compile(r"^\s+(c\d+\.f\d+) w \d+ holes ([0-9.]+) mixed true ([0-9.]+|nan) shifted ([0-9.]+|nan) one-block [0-9.nan]+"
                   r"(?: \| changed [0-9.nan]+ hole tiles ([0-9.]+|nan) drawn tiles ([0-9.]+|nan))?")


def decide(text, mean):
    """The README's table, on one run. (outcome, numbers)."""
    finals, pairs = [], []
    for line in text.splitlines():
        m = FINAL.match(line)
        if not m:
            continue
        if float(m.group(2)) >= 0.01 and m.group(3) != "nan" and m.group(4) != "nan":
            finals.append((float(m.group(3)), float(m.group(4))))
        if m.group(5) not in (None, "nan") and m.group(6) not in (None, "nan"):
            pairs.append((float(m.group(5)), float(m.group(6))))
    n = dict(hole_finals=len(finals), pairs=len(pairs), mean_patch=mean)
    if mean < QUALIFY:
        return "No verdict from this run", n
    if len(finals) < 30 or len(pairs) < 7:
        return "Inconclusive", n
    t = statistics.median(f[0] for f in finals)
    z = statistics.median(f[1] for f in finals)
    d = statistics.median(f[1] - f[0] for f in finals)
    a = statistics.median(f[0] for f in pairs)
    b = statistics.median(f[1] for f in pairs)
    n.update(T=t, Z=z, Z_minus_T=d, A=a, B=b)
    if (t <= 0.02 and z >= 0.10) or a >= 0.05:
        return "Overturned", n
    if abs(d) <= 0.05 and t > 0.02 and a <= 0.01 and b >= 0.10:
        return "Confirmed", n
    return "Inconclusive", n


if __name__ == "__main__":
    sys.stdout.reconfigure(newline=chr(10))
    a = sys.argv[1:]
    if len(a) == 4 and a[0] == "manifest":
        sys.exit(cmd_manifest(a[1], a[2], a[3]))
    if len(a) == 4 and a[0] == "check" and a[3] in ("pre", "post"):
        sys.exit(cmd_check(a[1], a[2], a[3]))
    if len(a) == 4 and a[0] == "arms":
        for first, text, got, verdict in arms(read(a[1]) or "", read(a[2]) or "", read(a[3]) or ""):
            print(f"{first:2d} {verdict} | {' '.join(f'{x:.1f}' for x in got)} | {text or 'all off'}")
        sys.exit(0)
    if len(a) == 3 and a[0] == "decide":
        out, nums = decide(read(a[1]) or "", float(a[2]))
        print(out, nums)
        sys.exit(0)
    print(__doc__)
    sys.exit(2)
