"""Replay of the edits from the shared KytyPlus tree (f266548 + patch 0001 on main) to the private sources of g412L2/g412v.
Run with Windows Python from anywhere: python -X utf8 replay.py. Writes steps/NN-tag.patch, steps.tsv, log.txt."""
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
INT = os.path.dirname(HERE)
SCR = os.path.dirname(INT)
KP = os.path.join(SCR, "kp")
TREE = os.path.join(HERE, "tree")
STEPS = os.path.join(HERE, "steps")
SIDE = os.path.join(HERE, "side")
WORK = os.path.join(HERE, "work")
BOX = os.path.join(INT, "box")
R01 = r"C:\Users\kjani\Downloads\bc5\bc5\experiments\0401-mesa-preamble-switches"
R09 = r"C:\Users\kjani\Downloads\bc5\bc5\experiments\0409-install-and-amm-scatter\b70-agent"
G = r"C:\Users\kjani\Downloads\bc5\bc5-0412\experiments\0412-memory-guardian"
PY = [sys.executable, "-X", "utf8", "-I", os.path.join(HERE, "runner.py")]
LCK = "src/libs/bc5LleAgc.cpp"

LOG = open(os.path.join(HERE, "log.txt"), "w", encoding="utf-8", newline="\n")


def log(*a):
    s = " ".join(str(x) for x in a)
    print(s)
    LOG.write(s + "\n")
    LOG.flush()


def md5f(p):
    with open(p, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()


def tp(rel):
    return os.path.join(TREE, rel.replace("/", os.sep))


def put(src, rel):
    os.makedirs(os.path.dirname(tp(rel)), exist_ok=True)
    shutil.copyfile(src, tp(rel))


def git(*a, out=None):
    r = subprocess.run(["git", "-c", "core.autocrlf=false", "-c", "core.safecrlf=false"] + list(a), cwd=TREE,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if r.returncode != 0:
        raise SystemExit("git %s: %s" % (a, r.stderr.decode(errors="replace")))
    if out:
        with open(out, "wb") as f:
            f.write(r.stdout)
    return r.stdout


def run(script, args, tag):
    r = subprocess.run(PY + [script] + args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    o, e = r.stdout.decode(errors="replace"), r.stderr.decode(errors="replace")
    with open(os.path.join(WORK, tag + ".out"), "w", encoding="utf-8", newline="\n") as f:
        f.write("$ %s %s\nrc %d\n--- stdout\n%s--- stderr\n%s" % (os.path.basename(script), " ".join(args), r.returncode, o, e))
    return r.returncode, o, e


def rows(name):
    """The E4_EDITS / E5_EDITS ... arrays of box0401.sh."""
    txt = open(os.path.join(R01, "box0401.sh"), encoding="utf-8").read()
    m = re.search(r"^%s=\(\n(.*?)^\)" % name, txt, re.S | re.M)
    return [re.match(r'\s*"([^"]*)"', l).group(1) for l in m.group(1).splitlines() if l.strip().startswith('"')]


TSV = []
NN = [0]


def finish(tag, series, cmd, units, switches, verified, note, side_from=None):
    NN[0] += 1
    nn = "%02d" % NN[0]
    if side_from:
        d = os.path.join(SIDE, nn + "-" + tag)
        os.makedirs(d, exist_ok=True)
        for p in side_from:
            shutil.copyfile(p, os.path.join(d, os.path.basename(p)))
    git("add", "-A")
    pf = os.path.join(STEPS, "%s-%s.patch" % (nn, tag))
    git("diff", "--no-color", "base", out=pf)
    TSV.append([nn, tag, series, cmd, " ".join(u[0] for u in units),
                " ".join("%s:%s>%s" % (u[0].split("/")[-1], u[1][:8], u[2][:8]) for u in units), switches,
                "yes" if verified else "no", note, md5f(pf)])
    log("%s %s %s verified=%s %s | patch %s" % (nn, tag, series, verified, note, md5f(pf)[:8]))


def check_outputs(outs, src_of):
    """outs: [(rel, md5 in, md5 out)]; src_of(rel) -> produced file. Returns (all ok, [(rel, in, actual out)])."""
    ok, got = True, []
    for rel, a, b in outs:
        p = src_of(rel)
        m = md5f(p) if os.path.exists(p) else "MISSING"
        got.append((rel, a, m))
        if m != b:
            ok = False
            log("   MISMATCH %s: got %s want %s" % (rel, m, b))
    return ok, got


def unit_step(tag, series, script, rel, want_in, want_out, extra_args=(), switches="", in_file=None, note="", side=None):
    """script <unit in> <unit out> [extra]: input from the tree (or in_file)."""
    src = in_file or tp(rel)
    mi = md5f(src)
    if mi != want_in:
        log("   INPUT %s is %s, want %s" % (rel, mi, want_in))
    w = os.path.join(WORK, tag)
    shutil.rmtree(w, ignore_errors=True)
    os.makedirs(w)
    out = os.path.join(w, os.path.basename(rel))
    args = [src, out] + [a.replace("@W", w) for a in extra_args]
    rc, o, e = run(script, args, tag)
    if rc != 0:
        log("   RC %d: %s" % (rc, e.strip().splitlines()[-1] if e.strip() else o[-200:]))
    ok, got = check_outputs([(rel, want_in, want_out)], lambda r: out)
    if os.path.exists(out):
        put(out, rel)
    sidef = [os.path.join(w, f) for f in os.listdir(w) if f.endswith(".inc")]
    cmd = "%s %s" % (os.path.basename(script), " ".join(["<in>", "<out>"] + list(extra_args)))
    finish(tag, series, cmd, [(rel, mi, got[0][2])], switches, ok and rc == 0 and mi == want_in, note, sidef or side)
    return ok


def root_step(tag, series, script, opt, specs, switches="", note="", tree_root=None, extra_files=()):
    """Box0401 E5-style row: stage the inputs ('+rel:md5' read only) into a root, run script [opt] <root> <out>.
    tree_root: run on that whole tree instead (E4 style: the shared tree)."""
    w = os.path.join(WORK, tag)
    shutil.rmtree(w, ignore_errors=True)
    r, x = os.path.join(w, "r"), os.path.join(w, "x")
    os.makedirs(r)
    ins_ok = True
    outs = []
    for s in specs:
        ro = s.startswith("+")
        s = s.lstrip("+")
        parts = s.split(":")
        rel, a = parts[0], parts[1]
        srcf = os.path.join(tree_root, rel) if tree_root else tp(rel)
        m = md5f(srcf)
        if m != a:
            ins_ok = False
            log("   INPUT %s is %s, want %s" % (rel, m, a))
        if not tree_root:
            os.makedirs(os.path.dirname(os.path.join(r, rel)), exist_ok=True)
            shutil.copyfile(srcf, os.path.join(r, rel))
        if not ro:
            outs.append((rel, a, parts[2]))
    args = ([opt] if opt and opt != "-" else []) + [tree_root or r, x]
    rc, o, e = run(script, args, tag)
    if rc != 0:
        log("   RC %d: %s" % (rc, (e.strip().splitlines() or [o[-200:]])[-1]))
    ok, got = check_outputs(outs, lambda rel: os.path.join(x, rel))
    for rel, _, m in got:
        if m != "MISSING":
            put(os.path.join(x, rel), rel)
    for src, rel in extra_files:
        put(src, rel)
    sidef = []
    for d, _, fs in os.walk(x):
        for f in fs:
            p = os.path.join(d, f)
            rel = os.path.relpath(p, x).replace(os.sep, "/")
            if rel not in [g[0] for g in got]:
                sidef.append(p)
    cmd = "%s %s<root> <out>" % (os.path.basename(script), "" if opt in (None, "-") else opt + " ")
    finish(tag, series, cmd, got, switches, ok and ins_ok and rc == 0, note, sidef)
    return ok


def main():
    os.makedirs(WORK, exist_ok=True)
    os.makedirs(SIDE, exist_ok=True)
    base_lck = os.path.join(KP, "src", "libs", "bc5LleAgc.cpp")
    mk = os.path.join(R01, "mkunit0401.py")
    # --- exp 0401, the main unit by mkunit0401.py: every series re-runs it on the shared unit with more flags
    for tag, ser, flags, want, sw in [
        ("u0401", "0401 (first)", [], "9eec0a3856bc1857ba7956b001c93aaf", "BC5_DIRECT_CP_COHER_START_DELAY BC5_DIRECT_SPI_REQ_CTRL_PS"),
        ("u0401c", "0401c", ["--acb-restore"], "29c88be321cc81908085b1cddcc70d2e", "BC5_DIRECT_ACB_STATE_RESTORE (+ BC5_DIRECT_ACB_CS_PREFIX code)"),
        ("u0401e", "0401e", ["--acb-restore", "--catcher"], "0d65c14d3705887717bac71dd97e05ab", "BC5_DIRECT_TABLE_CATCHER"),
    ]:
        unit_step(tag, ser, mk, LCK, "d18b448299a335aadac75bbd202155fd", want, ["@W/mesa_preamble_prefix.inc"] + flags, sw,
                  in_file=base_lck, note="mkunit0401.py on the shared unit " + " ".join(flags))
    # series e's other two units
    np_in = os.path.join(SCR, "np-in.cpp")
    w = os.path.join(WORK, "np0401")
    shutil.rmtree(w, ignore_errors=True)
    os.makedirs(w)
    rc, o, e = run(os.path.join(R01, "mknp0401.py"), [np_in, os.path.join(w, "libNpCppWebApi.cpp")], "np0401")
    m = md5f(os.path.join(w, "libNpCppWebApi.cpp")) if rc == 0 else "FAILED"
    ok = m == "935fcc7e4ab1108f3d2d8b33eaf65bf6"
    log("   np0401 offline: 7c40b784 -> %s (%s)" % (m, "ok" if ok else "MISMATCH"))
    finish("np0401", "0401e", "mknp0401.py <old patch-0001 unit 7c40b784> <out>",
           [("src/libs/libNpCppWebApi.cpp", "7c40b784e36ef45e816be07b0a3fb0a8", m)], "KYTY_BC5_NP_SESSION_V2",
           ok, "verified off-tree only: the tree keeps exp 0413's 910acbb5 (same ten exports, on by default); no tree change")
    mm = os.path.join(R01, "mkmem0401.py")
    root_step("mem0401", "0401e", mm, None, [
        "src/kernel/memory.cpp:f61546925dcf96ee9bbc1278b0f8ae6c:43713ef677ec887a8ca273f7ab5cee90",
        "src/loader/systemContent.cpp:7121c22ca8b893ac37fbeabde48b4a6b:4e33b30a4acf89481942cec435b76c37",
        "src/loader/systemContent.h:8890c158627f20f59ee55205e73d36c3:2b2b21eb1faf35c2a538917049aea85e"],
        "KYTY_BC5_MEMORY_FROM_PARAM", "mkmem0401.py <shared tree> <out>", tree_root=KP)
    unit_step("u0401e3", "0401e3", mk, LCK, "d18b448299a335aadac75bbd202155fd", "d3b7f9b0ab43184ee11de83e9e233ff8",
              ["@W/mesa_preamble_prefix.inc", "--acb-restore", "--catcher", "--inherit3", "--memline"],
              "BC5_DIRECT_ACB_INHERIT (off|journal|queue|skip), BC5_DIRECT_MEM_LINE", in_file=base_lck,
              note="mkunit0401.py on the shared unit --acb-restore --catcher --inherit3 --memline (e2's --inherit is not in the line)")
    unit_step("fl0401", "0401e4", os.path.join(R01, "mkfl0401.py"), LCK, "d3b7f9b0ab43184ee11de83e9e233ff8",
              "df12bb2de3e90b8c82a234eedf0babb5", ["@W"], "BC5_DIRECT_FL_CRUMBS BC5_DIRECT_FL_SKIP_ES", note="exp 0404's two switches")
    sw4 = {"sav": "KYTY_BC5_SAVEDATA_FIXES _EVENT_CB _SORT", "pth": "KYTY_BC5_PTHREAD_FIXES", "aud": "KYTY_BC5_AUDIO_FIXES",
           "vo": "KYTY_BC5_VIDEOOUT_STATUS", "amm": "KYTY_BC5_AMM_PRT_CMDS KYTY_BC5_AMM_EXTRA_CMDS KYTY_BC5_AMPR_WAITS"}
    for row in rows("E4_EDITS"):
        tag, script, *specs = row.split()
        root_step(tag, "0401e4", os.path.join(R01, script), None, specs, sw4.get(tag, ""), "%s <shared tree> <out>" % script, tree_root=KP)
    for ser, name in (("0401e5", "E5_EDITS"), ("0401e6", "E6_EDITS"), ("0401e7", "E7_EDITS"), ("0401e8", "E8_EDITS")):
        for row in rows(name):
            tag, script, opt, *specs = row.split()
            if tag == "fwn":
                fwn_step(script, opt, specs)
                continue
            root_step(tag, ser, os.path.join(R01, script), opt, specs, "", "box0401.sh %s row" % name)
    # exp 0409: the AMM scatter (libAmpr.cpp) and the install menu (hostMenu.cpp)
    unit_dir_step("pool0409", "0409", os.path.join(R09, "work", "mkpool0401.py"), "src/libs/libAmpr.cpp",
                  "0a1762f6440f421586b56767d27d0770", "a4760fe65d0ba50457a4fa5a15e5ec89", "KYTY_BC5_AMM_SCATTER")
    unit_dir_step("menu0409", "0409", os.path.join(R09, "host", "mkmenu.py"), "src/graphics/presentation/hostMenu.cpp",
                  "d3810c9f6d25b2742c3c29b6976e9330", "53c61393aec09429d9ae21af9c8d0dd2", "(none: File > Install game..., exit code 78)")
    # exp 0411 e11
    root_step("m110411", "0401e11 (exp 0411)", os.path.join(R01, "mkm110401.py"), None,
              ["src/libs/bc5LleAgc.cpp:bd1811690b685369194602027b61a2d5:f366ff7bfc2c15a81cb9a5d091de6168"],
              "BC5_DIRECT_RESET_REPLAY_ACB BC5_DIRECT_RESET_LABELS BC5_DIRECT_LEARN_GUEST_ONLY BC5_DIRECT_RESET_LABEL_JOURNAL", "mk0411.sh")
    # exp 0412
    root_step("guard0412", "0412 g412d", os.path.join(G, "mkguard0412.py"), None,
              ["src/libs/bc5LleAgc.cpp:f366ff7bfc2c15a81cb9a5d091de6168:5361c8baac7690e5167e89a27cc7b4c7"],
              "BC5_GUARD_LEDGER _MLOCK _FILE _FILE_ROOT _PSI _PIN_CAP _APPLY_MIN_MS _CAP_ACT _CAP_NAMES _SPLIT _FORGET", "mk0412d.sh")
    ev_step()
    mf = os.path.join(G, "memfast")
    unit_step("mem0412", "0412 memfast", os.path.join(mf, "mkmem0412.py"), "src/kernel/memory.cpp",
              "ee24c888f976cc125502cf3a31006349", "68c90f4b7746cec114300e82fd0bc93a", (), "KYTY_BC5_RANGES_FAST", note="mk0412L2.sh / mk0412v.sh")
    unit_step("phys0412", "0412 memfast", os.path.join(mf, "mkphys0412.py"), "src/kernel/memory.cpp",
              "68c90f4b7746cec114300e82fd0bc93a", "72bcd493cc28ec602fe12c9ca638c365", (), "KYTY_BC5_PHYSMAP_CHECK", note="mk0412L2.sh / mk0412v.sh")
    unit_step("sort0412", "0412 memfast", os.path.join(mf, "mksort0412.py"), "src/kernel/memory.cpp",
              "72bcd493cc28ec602fe12c9ca638c365", "6ae3ff7236610a14360739b54c53adc1", (), "KYTY_BC5_PHYSMAP_SORTED", note="mk0412L2.sh / mk0412v.sh")
    unit_step("zpolll0412", "0412 g412L2", os.path.join(mf, "mkzpolll0412.py"), LCK,
              "5361c8baac7690e5167e89a27cc7b4c7", "8f6e92b36ade2ceafcbaec32197cc076", (), "BC5_GUARD_ZSKIP_POLL_SUBMIT",
              note="mk0412L2.sh: the poll with the R12 fix, lean line")
    with open(os.path.join(HERE, "steps.tsv"), "w", encoding="utf-8", newline="\n") as f:
        f.write("NN\ttag\tseries\tscript+args\tunits\tmd5 in>out\tswitches\tverified\tnote\tpatch md5\n")
        for t in TSV:
            f.write("\t".join(t) + "\n")


def unit_dir_step(tag, series, script, rel, want_in, want_out, switches):
    """script <unit in> <out dir> -> <out dir>/<basename>."""
    src = tp(rel)
    mi = md5f(src)
    if mi != want_in:
        log("   INPUT %s is %s, want %s" % (rel, mi, want_in))
    w = os.path.join(WORK, tag)
    shutil.rmtree(w, ignore_errors=True)
    rc, o, e = run(script, [src, w], tag)
    out = os.path.join(w, os.path.basename(rel))
    ok, got = check_outputs([(rel, want_in, want_out)], lambda r: out)
    if os.path.exists(out):
        put(out, rel)
    finish(tag, series, "%s <in> <out dir>" % os.path.basename(script), [(rel, mi, got[0][2])], switches,
           ok and rc == 0 and mi == want_in, "")


def fwn_step(script, opt, specs):
    """e6's fwn: verify on e8's own input (libNpCppWebApi 935fcc7e from the box copy), then apply to the tree with
    exp 0413's 910acbb5 in its place (attempt; recorded)."""
    np_rel = "src/libs/libNpCppWebApi.cpp"
    w = os.path.join(WORK, "fwn-verify")
    shutil.rmtree(w, ignore_errors=True)
    r, x = os.path.join(w, "r"), os.path.join(w, "x")
    for s in specs:
        rel = s.split(":")[0]
        os.makedirs(os.path.dirname(os.path.join(r, rel)), exist_ok=True)
        srcf = os.path.join(BOX, "exp0401e8", "src", "libNpCppWebApi.cpp") if rel == np_rel else tp(rel)
        shutil.copyfile(srcf, os.path.join(r, rel))
    rc, o, e = run(os.path.join(R01, script), [r, x], "fwn-verify")
    allok = rc == 0
    for s in specs:
        rel, a, b = s.split(":")
        m = md5f(os.path.join(x, rel)) if os.path.exists(os.path.join(x, rel)) else "MISSING"
        log("   fwn-verify %s %s -> %s %s" % (rel, a[:8], m[:8], "ok" if m == b else "MISMATCH want " + b[:8]))
        allok = allok and m == b
    # on the tree: every unit but libNpCppWebApi from the verified run; the NpCppWebApi part tried on 910acbb5
    w2 = os.path.join(WORK, "fwn-tree")
    shutil.rmtree(w2, ignore_errors=True)
    r2, x2 = os.path.join(w2, "r"), os.path.join(w2, "x")
    for s in specs:
        rel = s.split(":")[0]
        os.makedirs(os.path.dirname(os.path.join(r2, rel)), exist_ok=True)
        shutil.copyfile(tp(rel), os.path.join(r2, rel))
    rc2, o2, e2 = run(os.path.join(R01, script), [r2, x2], "fwn-tree")
    log("   fwn on the tree (NpCppWebApi 910acbb5): rc %d %s" % (rc2, (e2.strip().splitlines() or [""])[-1][:200]))
    units = []
    for s in specs:
        rel, a, b = s.split(":")
        if rel == np_rel:
            # the fold: fwn's edit of 935fcc7e (all of it above the first line where 0413's 910acbb5 differs) on 910acbb5
            old = open(os.path.join(r, rel), "rb").read().splitlines(True)
            new = open(os.path.join(x, rel), "rb").read().splitlines(True)
            tgt = open(tp(rel), "rb").read().splitlines(True)
            k = next(i for i in range(min(len(old), len(tgt))) if old[i] != tgt[i])
            tail = old[k:]
            assert new[len(new) - len(tail):] == tail, "fwn edits below 0413's first changed line"
            out = b"".join(new[:len(new) - len(tail)] + tgt[k:])
            mi = md5f(tp(rel))
            with open(tp(rel), "wb") as f:
                f.write(out)
            mo = hashlib.md5(out).hexdigest()
            log("   fwn npwebapi folded onto 910acbb5 (0413 first differs at line %d): %s" % (k + 1, mo))
            units.append((rel, mi, mo + "(fold)"))
            continue
        put(os.path.join(x, rel), rel)
        units.append((rel, a, md5f(os.path.join(x, rel))))
    finish("fwn", "0401e6", "mkfwn0405.py <root> <out>", units, "KYTY_BC5_FW_NET (rtc, rudp, resolver, param400, npwebapi)",
           False, "4 units byte-exact; NpCppWebApi verified off-tree 935fcc7e->e613bc8f, in the tree FOLDED onto exp 0413's "
           "910acbb5 (no box counterpart: = e613bc8f with 0413's 26 changed lines; see REPORT)" if allok else "fwn verify FAILED")


def ev_step():
    eq_rel, sy_rel = "src/kernel/eventQueue.cpp", "src/graphics/host_gpu/renderer/sync.cpp"
    w = os.path.join(WORK, "ev0412")
    shutil.rmtree(w, ignore_errors=True)
    x = os.path.join(w, "x")
    mi_eq, mi_sy = md5f(tp(eq_rel)), md5f(tp(sy_rel))
    rc, o, e = run(os.path.join(G, "events", "mkev0412.py"), ["--eq", tp(eq_rel), KP, x], "ev0412")
    if rc != 0:
        log("   RC %d %s" % (rc, (e.strip().splitlines() or [""])[-1][:200]))
    ok, got = check_outputs([(eq_rel, "d8eaa6d22e3e415ea8331dced30867c0", "64e176a797565f1b910d575947582aa5"),
                             (sy_rel, "68733b6c5be980f238571723296f7d05", "06c1349c95f39aad41c5cf18901d4fc8")],
                            lambda rel: os.path.join(x, rel))
    for rel, _, m in got:
        if m != "MISSING":
            put(os.path.join(x, rel), rel)
    hdr = os.path.join(G, "events", "event_cap0412.hpp")
    put(hdr, "src/kernel/event_cap0412.hpp")
    hok = md5f(hdr) == "dae6fedc528b004142eb95dffd60cd37"
    got = [(eq_rel, mi_eq, got[0][2]), (sy_rel, mi_sy, got[1][2]), ("src/kernel/event_cap0412.hpp", "new", md5f(hdr))]
    finish("ev0412", "0412 g412e", "mkev0412.py --eq <eventQueue.cpp> <shared tree> <out>; event_cap0412.hpp copied beside eventQueue.cpp",
           got, "KYTY_BC5_EVENT_PENDING_CAP KYTY_BC5_EVENT_PENDING_LOG", ok and hok and rc == 0 and mi_eq == "d8eaa6d22e3e415ea8331dced30867c0",
           "header placed in src/kernel/ (the box put kit-e on the include path)")


if __name__ == "__main__":
    main()
