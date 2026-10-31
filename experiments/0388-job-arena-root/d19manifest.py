#!/usr/bin/env python3
"""D19: the effective options of one emulator, from its raw /proc/PID/environ dump. An allow list; fails closed.
usage: d19manifest.py normal|lean <raw dir> <tag> <pinned patch 0001> <its md5> <sha256 of its sorted lean list>
       d19manifest.py static <play-pkg.sh> <bc5-run.env>     the tables below against the launcher chain, read as text
       d19manifest.py inherited <env -0 file>                only the reviewed system background may arrive from outside the chain
Run mode reads <raw>/<tag>-environ.bin and <raw>/<tag>-start.txt. The tag is D19<variant><run id>.
Every exec environ name must be on the table of its variant with the exact value, and every table name must be there:
a missing guard, a changed value, a forbidden name and an unknown option name all block. The forbidden list is a
second fuse and the reason text, not the control. Two columns stay apart: `exec environ` is what the process started
with; `after lean cleanup` is COMPUTED from the patch's list and was never observed in the process.
Nothing here sources or runs a settings file. Exit 0 only for a pass; 1 blocks; 2 is an error.
Last line: MANIFEST PASS or MANIFEST FAIL."""
import hashlib, os, re, shlex, sys

ENV_MD5 = "cb8ad5fcfd6eac2a5cafac2a501b3eba"   # the bc5-run.env these tables were read from (RUN_ENV in pins.env)
LAUNCHER_MD5 = "55531ab6277d6816c0603a7a6c6d62b4"
MAX_ENVIRON = 1 << 20
SLACK = 2  # seconds, as d19gates.py

# Presence blocks, whatever the value (=0 too): experiments and diagnostics no shared smoke may carry.
FORBIDDEN = tuple("BC5_DIRECT_" + x for x in (
    "ARGS_COPY", "ARGS_WB", "ARGS_FLUSH", "ARGS_FLUSH_DRAWS", "FORCE_START_000", "GPU_CHECK_ZERO", "GPU_CHECK_YZ",
    "REBASE_DISPATCH", "CHAIN_BREAK_AT", "DRAW_ARGS_JOURNAL", "BO_JOURNAL", "ARGS_HISTOGRAM", "ZERO_SKIP",
    "ZEROSCAN_AT", "ZEROSCAN_OUT", "ACB_STATE_RESTORE", "PIECES_NO_CLEAR", "INDEX_BASE_DUP", "NO_CARRY")) + ("KYTY_BC5_RT",)

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
    # the runner's private launcher and ENVS
    "KYTY_BC5_SAVEDATA_DIR": "{HOME}/bc5-work/d19/run/wd/_SaveData-pkg-play",
    "BC5_DIRECT_LEARNED": "{HOME}/bc5-work/d19/run/direct-learned-pkg.txt",
    "KYTY_BC5_INPUT_CONFIG": re.compile(r"/.*/bc5-work/d19/run/input-rton\.cfg|[A-Za-z]:/.*/input-rton\.cfg"),
    "BC5_0358_INPUT_CONFIG": re.compile(r"/.*/bc5-work/d19/run/input-rton\.cfg|[A-Za-z]:/.*/input-rton\.cfg"),
    "KYTY_BC5_INPUT_CMD": None,  # filled from the tag
    "BC5_EMU": None,             # filled from the variant
    "D19_OWNER": None,           # filled from the tag
    # exported by play-pkg.sh; not options, their values come from the session
    "XDG_RUNTIME_DIR": re.compile(r"/run/user/\d+"), "WAYLAND_DISPLAY": re.compile(r".+"), "DISPLAY": re.compile(r".+"),
}
NORMAL = {
    "KYTY_BC5_INPUT_RECORD": "/home/kjaniszewski/bc5-work/route-record.txt", "PLAY_CAPTURE": "1",
    "BC5_DIRECT_TIMEOUT_PROBE": "1", "BC5_DIRECT_TIMING": "1", "BC5_DIRECT_FRAME_PROFILE": "1",
    "BC5_GC_DUMP_DIR": re.compile(r"\{HOME\}/bc5-data/captures/play-\d{8}-\d{4}/gc"),
    "KYTY_BC5_FPS_COUNTER": "1", "KYTY_BC5_AUDIO_TRACE": "1", "KYTY_BC5_MEASURE": "1",
}
LEAN = {"BC5_LEAN": "1", "BC5_LOGS": "1"}
# May arrive through distrobox from d19box.sh's environment, or not: that cannot be read from the files. Checked if there.
MAYBE = {"BC5_0380_WANT": re.compile(r"[0-9a-f]{8}"), "D19_VARIANT": None, "D19_BIN": None}
EXE = {"normal": "/exp0388/kyty_emulator", "lean": "/kytyplus-build-lean/src/kyty_emulator"}


def table(variant, home, tag=None):
    """name -> exact text, or a compiled pattern. Variant-dependent entries filled in."""
    t = dict(COMMON)
    t.update(SYSTEM_BACKGROUND)
    t.update(NORMAL if variant == "normal" else LEAN)
    out = {}
    for k, v in t.items():
        if isinstance(v, str):
            v = v.replace("{HOME}", home)
        elif isinstance(v, re.Pattern) and r"\{HOME\}" in v.pattern:
            v = re.compile(v.pattern.replace(r"\{HOME\}", re.escape(home)))
        out[k] = v
    out["BC5_EMU"] = re.compile(r".*" + re.escape(EXE[variant]))
    run = re.fullmatch(r"D19(?:normal|lean)(\d+)", tag or "")
    out["D19_OWNER"] = run.group(1) if run else re.compile(r"\d+")
    out["KYTY_BC5_INPUT_CMD"] = re.compile(r".*/in-" + re.escape(tag or "") + r"\.cmd") if tag else re.compile(r".*/in-.*\.cmd")
    return out


def matches(want, value):
    return bool(want.fullmatch(value)) if isinstance(want, re.Pattern) else value == want


def is_option(name):
    return name.startswith(OPTION)


def lean_list(patch_text):
    found = re.findall(r"kDiagnostic\[\] = \{(.*?)\};", patch_text, re.S)
    if len(found) != 1:
        raise ValueError(f"{len(found)} diagnostic lists in the patch")
    names = re.findall(r'"([A-Za-z0-9_]+)"', found[0])
    if not names:
        raise ValueError("an empty diagnostic list")
    if len(set(names)) != len(names):
        raise ValueError("a duplicate name in the diagnostic list")
    return set(names)


def list_sha(names):
    return hashlib.sha256(("\n".join(sorted(names)) + "\n").encode()).hexdigest()


def parse_environ(data):
    """[(name, value)] in dump order; raises on anything a whole environ cannot be. Bytes stay exact."""
    if not data:
        raise ValueError("an empty dump")
    if len(data) > MAX_ENVIRON:
        raise ValueError("a dump over 1 MiB")
    if not data.endswith(b"\0"):
        raise ValueError("a truncated dump: no final NUL")
    out = []
    for x in data[:-1].split(b"\0"):
        if not x:
            raise ValueError("an empty entry in the dump")
        if b"=" not in x:
            raise ValueError("an entry without = in the dump: " + repr(x[:40]))
        k, v = x.split(b"=", 1)
        k = k.decode("utf-8", "surrogateescape")
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", k):
            raise ValueError("a malformed name in the dump: " + repr(k[:40]))
        out.append((k, v.decode("utf-8", "surrogateescape")))
    return out


def identity(start, raw_bytes, tag, variant):
    """Ties the dump to this run's emulator: the tag, the one pid, the exe, the size and hash in the start file."""
    fails = []
    if not re.search(r"^arm " + re.escape(tag) + r",", start, re.M):
        fails.append("the start file is not of tag " + tag)
    emu = re.findall(r"^emulator pid (\d+) exe (\S+) cwd \S+", start, re.M)
    cap = re.findall(r"^environ capture pid (\d+) bytes (\d+) sha256 ([0-9a-f]{64})$", start, re.M)
    if len(emu) != 1:
        fails.append(f"{len(emu)} emulator lines in the start file")
    if len(cap) != 1:
        fails.append(f"{len(cap)} environ capture lines in the start file")
    if len(emu) == 1 and not emu[0][1].endswith(EXE[variant]):
        fails.append("the emulator was not the " + variant + " binary: " + emu[0][1])
    if len(emu) == 1 and len(cap) == 1 and emu[0][0] != cap[0][0]:
        fails.append(f"the dump is of pid {cap[0][0]}, the emulator was pid {emu[0][0]}")
    if len(cap) == 1:
        if int(cap[0][1]) != len(raw_bytes):
            fails.append("the dump's size is not the recorded size")
        if cap[0][2] != hashlib.sha256(raw_bytes).hexdigest():
            fails.append("the dump's hash is not the recorded hash")
    return fails, (emu[0][0] if emu else "?")


def check(variant, entries, tag, removed):
    """Prints the columns; returns the blocking reasons."""
    fails = []
    seen = {}
    for k, v in entries:
        if k in seen:
            fails.append(f"duplicate entry {k}" + ("" if seen[k] == v else " with a conflicting value"))
        seen.setdefault(k, v)
    home = seen.get("HOME")
    if not home:
        return fails + ["no HOME in the dump"]
    want = table(variant, home, tag)
    maybe = dict(MAYBE)
    maybe["D19_VARIANT"] = re.compile(re.escape(variant))
    maybe["D19_BIN"] = re.compile(r".*" + re.escape(EXE[variant]))
    print("name | exec environ (observed at exec) | after lean cleanup (COMPUTED, not observed) | class")
    other = 0
    for k, v in entries:
        if k in FORBIDDEN:
            cls = "FORBIDDEN"
            fails.append("forbidden name " + k)
        elif k in want:
            cls = "system background" if k in SYSTEM_BACKGROUND else "chain"
            if not matches(want[k], v):
                cls = "WRONG VALUE"
                fails.append(f"{k} is {v!r}, not the chain's value")
        elif k in maybe:
            cls = "runner, passed through"
            if not matches(maybe[k], v):
                cls = "WRONG VALUE"
                fails.append(f"{k} is {v!r}")
        elif k in removed:
            cls = "NOT IN CHAIN"
            fails.append("a lean-list name the chain does not set: " + k)
        elif is_option(k):
            cls = "NOT IN CHAIN"
            fails.append("an option the chain does not set: " + k)
        else:
            cls = "session, not an option"
            other += 1
        shown = v if cls != "session, not an option" else f"<{len(v)} bytes, in the dump>"
        if variant == "lean":
            after = "removed" if k in removed else ("0, set" if k == "BC5_LOGGING" else "kept")
        else:
            after = "no cleanup in normal"
        print(f"{k} | {shown} | {after} | {cls}")
    if variant == "lean":
        print("BC5_LOGGING | (not in exec environ) | 0, set | computed by the constructor")
    for k in want:
        if k not in seen:
            fails.append(("missing guard " if k in GUARDS else "missing chain name ") + k)
    print(f"{len(entries)} names, {other} session names not treated as options")
    return fails


def fail(msg, rc=2):
    print("error:", msg)
    print("MANIFEST FAIL")
    return rc


def run(variant, raw, tag, patch, patch_md5, list_hash):
    if not re.fullmatch("D19" + variant + r"\d+", tag):
        return fail(f"tag {tag!r} is not of variant {variant}", 1)
    p = lambda s: os.path.join(raw, tag + s)
    with open(patch, "rb") as f:
        pb = f.read()
    if hashlib.md5(pb).hexdigest() != patch_md5:
        return fail("the patch is not the pinned patch " + patch_md5, 1)
    removed = lean_list(pb.decode("utf-8", "replace"))
    if list_sha(removed) != list_hash:
        return fail("the patch's lean list is not the pinned list " + list_hash, 1)
    with open(p("-environ.bin"), "rb") as f:
        data = f.read()
    with open(p("-start.txt"), encoding="utf-8", errors="replace") as f:
        start = f.read()
    fails, pid = identity(start, data, tag, variant)
    if os.path.getmtime(p("-environ.bin")) < os.path.getmtime(p("-start.txt")) - SLACK:
        fails.append("stale dump: older than this run's start file")
    print(f"manifest {variant}, tag {tag}, pid {pid}, lean list {len(removed)} names")
    entries = parse_environ(data)
    fails += check(variant, entries, tag, removed)
    if variant == "lean":
        print("lean: the after-cleanup column is computed from the pinned list; /proc shows the exec environment only")
    for f in fails:
        print("FAIL", f)
    print("MANIFEST PASS" if not fails else "MANIFEST FAIL")
    return 1 if fails else 0


# ---- static mode: the chain as text. Nothing is sourced or run. ----
COND = re.compile(r'\[ "\$\{(\w+)(:?-)([^}"]*)\}" (=|!=) (\w+) \]$')


def expand(v, env):
    v = re.sub(r"\$\{(\w+):\+\$\1,\}", lambda m: env[m.group(1)] + "," if env.get(m.group(1)) else "", v)
    v = re.sub(r"\$\{(\w+):-([^}]*)\}", lambda m: env.get(m.group(1)) or m.group(2), v)
    v = v.replace("$HOME", "/home/static").replace("~", "/home/static")
    if "$" in v.replace("$(date)", "").replace("$(id)", ""):
        raise ValueError("cannot expand " + v)
    return v.replace("$(date)", "20261031-0000").replace("$(id)", "1000")


def cond(s, env):
    m = COND.match(s.strip())
    if not m:
        raise ValueError("a condition this reader does not know: " + s)
    name, op, dflt, test, val = m.groups()
    have = env.get(name) if op == "-" or env.get(name) else None
    have = have if have is not None else dflt
    return (have == val) if test == "=" else (have != val)


def stmt(s, env):
    s = s.strip()
    words = shlex.split(s, comments=True)
    if not words:
        return
    if words[0] == "unset":
        for w in words[1:]:
            env.pop(w, None)
    elif words[0] == "export":
        for w in words[1:]:
            k, v = w.split("=", 1)
            env[k] = expand(v, env)
    else:
        raise ValueError("a statement this reader does not know: " + s)


def derive(launcher, runenv, variant):
    """The environment the pinned chain gives, statement by statement. Anything unknown that sets options raises."""
    env = {"BC5_LEAN": "1", "BC5_LOGS": "1"} if variant == "lean" else {}
    skip = []
    in_while = False
    for raw in launcher.splitlines():
        line = re.sub(r"\$\(date [^)]*\)", "$(date)", raw)
        line = re.sub(r"\$\(id -u\)", "$(id)", line)
        line = re.sub(r"\s+#\s.*$", "", line).strip()
        if line.startswith("#") or not line:
            continue
        if line.startswith("while IFS= read -r line"):
            in_while = True
            continue
        if in_while:
            if line == 'done < "$ENVF"':
                in_while = False
                for e in runenv.splitlines():
                    if not e or e.startswith("#"):
                        continue
                    k, v = e.split("=", 1)
                    if k != "PLAY_ARGS":
                        env[k] = v
            elif line.startswith("done"):
                in_while = False
            continue
        if line == "fi":
            skip.pop()
            continue
        if line.startswith("if ") and line.endswith("; then"):
            c = line[3:-6]
            skip.append(False if c == '[ -r "$PKG_ENV" ]' else None)
            if skip[-1] is None:
                skip[-1] = cond(c, env) if COND.match(c) else True
            continue
        if line.startswith("if ") and "; then " in line and line.endswith("; fi"):
            if not re.search(r"(^|\s)(export|unset)\s", line):
                continue
            c, rest = line[3:].split("; then ", 1)
            a, b = rest[:-4].split("; else ", 1)
            stmt(a if cond(c, env) else b, env)
            continue
        if not all(skip):
            continue
        code = shlex.split(line, comments=True, posix=False)
        text = " ".join(code)
        if not re.search(r"(^|\s)(export|unset)\s", text):
            continue
        # [ a ] || [ b ] && stmt, read left to right
        rest = text
        ok = True
        while rest.startswith("["):
            m = re.match(r"(\[ .*? \]) (\|\||&&) (.*)$", rest)
            if not m:
                raise ValueError("a line this reader does not know: " + raw)
            r = cond(m.group(1), env)
            if m.group(2) == "||":
                ok = not r
                if r:
                    rest = ""
                    break
            else:
                ok = r
                if not r:
                    rest = ""
                    break
            rest = m.group(3)
        if rest and ok:
            stmt(rest, env)
    if skip:
        raise ValueError("an if without its fi")
    # The runner's derived launcher and its ENVS.
    env["KYTY_BC5_SAVEDATA_DIR"] = "/home/static/bc5-work/d19/run/wd/_SaveData-pkg-play"
    env["BC5_DIRECT_LEARNED"] = "/home/static/bc5-work/d19/run/direct-learned-pkg.txt"
    return env


def static(launcher_path, runenv_path):
    with open(launcher_path, "rb") as f:
        lb = f.read()
    with open(runenv_path, "rb") as f:
        rb = f.read()
    fails = []
    if hashlib.md5(lb).hexdigest() != LAUNCHER_MD5:
        fails.append("the launcher is not " + LAUNCHER_MD5)
    if hashlib.md5(rb).hexdigest() != ENV_MD5:
        fails.append("the settings file is not " + ENV_MD5)
    from_runner = {"KYTY_BC5_INPUT_CONFIG", "BC5_0358_INPUT_CONFIG", "KYTY_BC5_INPUT_CMD", "BC5_EMU", "D19_OWNER"}
    session = {"XDG_RUNTIME_DIR", "WAYLAND_DISPLAY", "DISPLAY"}
    for variant in ("normal", "lean"):
        env = derive(lb.decode("utf-8", "replace"), rb.decode("utf-8", "replace"), variant)
        want = table(variant, "/home/static")
        for k in sorted(set(env) | set(want)):
            if k in from_runner or k in session or k in SYSTEM_BACKGROUND:
                continue
            if k not in env:
                fails.append(f"{variant}: the table has {k}, the chain does not")
            elif k not in want:
                fails.append(f"{variant}: the chain sets {k}, the table does not")
            elif not matches(want[k], env[k]):
                fails.append(f"{variant}: {k} is {env[k]!r} in the chain")
        for k in env:
            if k in FORBIDDEN:
                fails.append(f"{variant}: the chain sets the forbidden name {k}")
        print(f"{variant}: {len(env)} names from the chain")
    for f in fails:
        print("FAIL", f)
    print("MANIFEST PASS" if not fails else "MANIFEST FAIL")
    return 1 if fails else 0


def inherited(path):
    with open(path, "rb") as f:
        entries = parse_environ(f.read())
    bad = [k for k, v in entries if is_option(k) and
           (k not in SYSTEM_BACKGROUND or not matches(SYSTEM_BACKGROUND[k], v))]
    seen = set()
    for k, _ in entries:
        if k in SYSTEM_BACKGROUND and k in seen:
            bad.append(k)
        seen.add(k)
    for k in bad:
        print("FAIL an option from outside the chain:", k)
    print(f"{len(entries)} inherited names, {len(bad)} options")
    print("MANIFEST PASS" if not bad else "MANIFEST FAIL")
    return 1 if bad else 0


def main():
    a = sys.argv[1:]
    try:
        if len(a) == 6 and a[0] in ("normal", "lean"):
            return run(*a)
        if len(a) == 3 and a[0] == "static":
            return static(a[1], a[2])
        if len(a) == 2 and a[0] == "inherited":
            return inherited(a[1])
    except Exception as e:  # unreadable, malformed, unknown: all block
        return fail(repr(e))
    print(__doc__)
    print("MANIFEST FAIL")
    return 2


if __name__ == "__main__":
    sys.exit(main())
