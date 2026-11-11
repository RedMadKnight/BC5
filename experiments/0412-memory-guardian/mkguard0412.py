#!/usr/bin/env python3
"""BC5 experiment 0412, tag g412: the memory guardian's first build, as one edit of src/libs/bc5LleAgc.cpp.
Pinned input: exp 0401 e11's main unit (md5 f366ff7b..., the unit of the maintainer's "e11 unpacked" binary 70df5cb1).
The guardian's text is guard0412.inc, beside this script (pinned by INC_SHA256 once the kit is frozen; until then by the
kit's kit.sha256). Eight switches, all default off (unset, empty and "0" are off): BC5_GUARD_LEDGER, BC5_GUARD_MLOCK,
BC5_GUARD_FILE (+ BC5_GUARD_FILE_ROOT), BC5_GUARD_PSI, BC5_GUARD_PIN_CAP, BC5_GUARD_APPLY_MIN_MS, BC5_GUARD_CAP_ACT, BC5_GUARD_CAP_NAMES; guard0412.inc's head
says what each does.
The edit, four places for the first build (g412) and five more for the second (g412b: 1 also declares the four new hooks;
in direct_sync_one, guard0412_cap after the import list is made, guard0412_cap_changed in the drain's and the rebuild's
conditions, guard0412_want before the wanted mappings are sorted, guard0412_synced after the retired BOs are freed):
  1. a declaration of guard0412_imported before direct_sync_one;
  2. in direct_sync_one's import loop, after "S.bytes += size;": guard0412_imported(S.kind, fd, off, size);
  3. guard0412.inc's text before learned_apply (after e11's g_m11_reopens, which it reads);
  4. at learned_apply's one call: "if (!guard0412_defer_apply()) learned_apply();".
With every switch off the binary does what e11's does, plus one config read and two early returns.
Every anchor occurs exactly once; the inserted text is ASCII with LF line ends; a unit that has the edit already is refused,
and so is an input that is not the pinned one (--any-input lifts only the md5 pin, for the laptop's stand-in run; never on
the box). After editing, the script undoes its edits and asserts that this gives the input back byte for byte.
Prints "<relpath> <md5>".
CPU test: test0412.cpp (the pure part). Syntax check of the host part: syn0412.cpp.
usage: mkguard0412.py [--any-input] <tree root in> <out dir>"""
import hashlib
import os
import sys

MAIN = "src/libs/bc5LleAgc.cpp"
MAIN_MD5_PREFIX = "f366ff7bfc2c15a81cb9a5d091de6168"  # e11's main unit, read on the box 2026-11-10 19:27 (the whole md5)
MARKS = (b"guard0412_", b"g412", b"BC5_GUARD_", b"exp 0412")
HERE = os.path.dirname(os.path.abspath(__file__))


def md5(b):
    return hashlib.md5(b).hexdigest()


def edits(inc):
    e = []
    a0 = b"static LzrPass lzr_pass(DState& S, const std::vector<DView>& views, uint64_t sig, int fd, uint64_t now, uint32_t merged, std::vector<uint32_t>& retired, uint32_t merge_remaps,\n"
    e.append(("the split's declaration", a0, b"static bool guard0412_split(); // exp 0412 (tag g412c): BC5_GUARD_SPLIT\n" + a0))
    a0b = b"\tconst bool          splits = std::getenv(\"BC5_DIRECT_ALIASES\") == nullptr;\n"
    e.append(("the split", a0b, b"\tconst bool          splits = std::getenv(\"BC5_DIRECT_ALIASES\") == nullptr || guard0412_split(); // exp 0412 (tag g412c)\n"))
    a1 = b"static void direct_sync_one(DState& S, bool force) {\n"
    e.append(("the declarations", a1, b"static void guard0412_imported(int kind, int fd, uint64_t off, uint64_t size); // exp 0412 (tag g412)\n"
              b"static void guard0412_cap(DState& S, const std::vector<DView>& views, std::vector<uint64_t>& need); // exp 0412 (tag g412b)\n"
              b"static bool guard0412_cap_changed(const DState& S);\n"
              b"static void guard0412_want(const DState& S, const std::vector<DView>& views, std::vector<DMap>& want);\n"
              b"static void guard0412_synced(const DState& S);\n"
              b"static void guard0412_after_cuts(size_t cuts); // exp 0412 (tag g412c)\n"
              b"static void aliases_apply(bool force);\n"
              b"static void guard0412_forget(DState& S, const std::vector<DView>& views, uint64_t sig, uint64_t now); // exp 0412 (tag g412d)\n" + a1))
    a10 = b"\tconst bool zskip_on = S.kind == 0 && !g_zskip.empty();\n"
    e.append(("the forget", a10, b"\tguard0412_forget(S, views, sig, now); // exp 0412 (tag g412d): BC5_GUARD_FORGET\n" + a10))
    a5 = b"\tneed.erase(std::unique(need.begin(), need.end()), need.end());\n\tuint32_t imported = 0;\n"
    e.append(("the cap", a5, b"\tneed.erase(std::unique(need.begin(), need.end()), need.end());\n"
              b"\tguard0412_cap(S, views, need); // exp 0412 (tag g412b): BC5_GUARD_CAP_ACT puts soft chunks over the cap off\n\tuint32_t imported = 0;\n"))
    a2 = b"\t\t\tS.bytes += size;\n"
    e.append(("the import hook", a2, a2 + b"\t\t\tguard0412_imported(S.kind, fd, off, size); // exp 0412 (tag g412): the guardian's ledger and BC5_GUARD_MLOCK\n"))
    a6 = b"\tif (!retired.empty() || sig != S.views_sig) {\n\t\twait_jobs(); // mappings are about to go or be replaced\n"
    e.append(("the drain", a6, b"\tif (!retired.empty() || sig != S.views_sig || guard0412_cap_changed(S)) { // exp 0412 (tag g412b)\n\t\twait_jobs(); // mappings are about to go or be replaced\n"))
    a7 = b"\tif (sig != S.views_sig || S.bos.size() != S.bos_mapped || !retired.empty()) {\n\t\tstd::vector<DMap> want;\n"
    e.append(("the rebuild", a7, b"\tif (sig != S.views_sig || S.bos.size() != S.bos_mapped || !retired.empty() || guard0412_cap_changed(S)) { // exp 0412 (tag g412b)\n\t\tstd::vector<DMap> want;\n"))
    a8 = b"\t\tstd::sort(want.begin(), want.end(), [](const DMap& a, const DMap& b) { return a.va < b.va; });\n"
    e.append(("the zero mappings", a8, b"\t\tguard0412_want(S, views, want); // exp 0412 (tag g412b): the zero buffer under the views of put-off chunks\n" + a8))
    a9 = b"\tfor (const uint32_t id: retired) g_dev->free_shared(id);\n\tif (merged != 0 || deferred != 0) {\n"
    e.append(("the sync's end", a9, b"\tfor (const uint32_t id: retired) g_dev->free_shared(id);\n\tguard0412_after_cuts(lzr.done.size()); // exp 0412 (tag g412c): BC5_GUARD_SPLIT\n"
              b"\tguard0412_synced(S); // exp 0412 (tag g412b): the ledger's view of what is imported\n\tif (merged != 0 || deferred != 0) {\n"))
    a3 = b"static void learned_apply() {\n"
    e.append(("the guardian", a3, inc + b"\n" + a3))
    a4 = b"\tconst uint64_t t1 = SoftCp::now_ns();\n\tlearned_apply();\n"
    e.append(("the put-off", a4, b"\tconst uint64_t t1 = SoftCp::now_ns();\n\tif (!guard0412_defer_apply()) learned_apply(); // exp 0412 (tag g412): BC5_GUARD_APPLY_MIN_MS\n"))
    return e


def naive_balance(b):
    return (b.count(b"{") - b.count(b"}"), b.count(b"(") - b.count(b")"), b.count(b"[") - b.count(b"]"))


def apply(s, inc):
    for m in MARKS:
        assert m not in s, ("refused: the unit has the edit already", m.decode())
    assert b"\r" not in s, "a CR in the LF unit"
    assert b"\r" not in inc and b"\t" not in inc, "guard0412.inc must be LF and tab-free"
    inc.decode("ascii")
    assert inc.count(b"// G412_PURE_BEGIN\n") == 1 and inc.count(b"// G412_PURE_END\n") == 1 and inc.endswith(b"#endif // !GUARD0412_TEST\n"), "guard0412.inc's frame"
    out, at, done = s, -1, []
    for name, old, new in edits(inc):
        assert out.count(old) == 1, ("an anchor does not occur exactly once", name, out.count(old))
        if name != "the guardian":  # the three small edits; guard0412.inc's own balance is what syn0412.cpp's compile shows
            assert naive_balance(old) == naive_balance(new), ("the edit changes the balance", name)
        new.decode("ascii")
        pos = out.index(old)
        assert pos > at, ("the edits are not in file order", name)
        at = pos
        out = out.replace(old, new)
        done.append((name, old, new))
    back = out
    for name, old, new in reversed(done):
        assert back.count(new) == 1, ("undo", name)
        back = back.replace(new, old)
    assert back == s, "undoing the edits does not give the input back"
    # The uses: the declaration, the definition and one call; the put-off's definition and one call.
    assert out.count(b"guard0412_imported(") == 3 and out.count(b"guard0412_defer_apply(") == 2, "the hooks' uses"
    # The second build's hooks: a declaration, a definition and one call each (two calls of guard0412_cap_changed).
    assert [out.count(x) for x in (b"guard0412_cap(", b"guard0412_cap_changed(", b"guard0412_want(", b"guard0412_synced(")] == [3, 4, 3, 3], "the second build's hooks"
    assert [out.count(x) for x in (b"guard0412_split(", b"guard0412_after_cuts(", b"static void aliases_apply(bool force)")] == [4, 3, 2], "the third build's hooks"
    assert out.count(b"guard0412_forget(") == 3, "the fourth build's hook"
    assert out.index(b"static uint32_t scratch_bo() {") < out.index(b"// G412_PURE_BEGIN\n"), "the zero buffer is defined before the guardian"
    assert out.count(b"\tlearned_apply();\n") == 0 and out.count(b"learned_apply();") == 1, "learned_apply's one call"
    # The guardian sits after e11's reopen counter, before learned_apply, inside the direct build's #if.
    p = [out.index(x) for x in (b"static void guard0412_imported(int kind, int fd, uint64_t off, uint64_t size); // exp 0412", b"static void direct_sync_one(",
                                b"guard0412_cap(S, views, need);", b"guard0412_imported(S.kind, fd, off, size);", b"guard0412_want(S, views, want);", b"guard0412_synced(S);",
                                b"// G412_PURE_BEGIN\n", b"static void learned_apply() {", b"if (!guard0412_defer_apply()) learned_apply();")]
    assert p == sorted(p), ("the edits' places", p)
    assert out.rfind(b"\n#if defined(KYTY_BC5_DIRECT)\n", 0, p[0]) > 0, "the direct build's #if"
    return out


def main():
    args = sys.argv[1:]
    any_input = "--any-input" in args
    args = [a for a in args if a != "--any-input"]
    assert len(args) == 2, __doc__
    root, outdir = args
    assert os.path.abspath(root) != os.path.abspath(outdir), "the out dir must not be the tree"
    with open(os.path.join(root, MAIN), "rb") as f:
        s = f.read()
    with open(os.path.join(HERE, "guard0412.inc"), "rb") as f:
        inc = f.read()
    if any_input:
        print("# --any-input: the md5 pin is lifted (a stand-in run; never a box build)", file=sys.stderr)
    else:
        assert md5(s).startswith(MAIN_MD5_PREFIX), ("refused: not the pinned input", MAIN, md5(s), MAIN_MD5_PREFIX)
        g = s.find(b"static std::atomic<uint64_t> g_m11_reopens {0};")
        assert 0 < g < s.index(b"static void learned_apply() {\n"), "e11's reopen counter is not before learned_apply"
    out = apply(s, inc)
    print(f"# in:  {MAIN} {md5(s)}  ({len(s)} bytes); guard0412.inc sha256 {hashlib.sha256(inc).hexdigest()}", file=sys.stderr)
    dst = os.path.join(outdir, MAIN)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    with open(dst, "wb") as f:
        f.write(out)
    print(f"{MAIN} {md5(out)}")


if __name__ == "__main__":
    main()
