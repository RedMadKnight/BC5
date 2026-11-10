#!/usr/bin/env python3
"""BC5 experiment 0412, tag g412: the memory guardian's first build, as one edit of src/libs/bc5LleAgc.cpp.
Pinned input: exp 0401 e11's main unit (md5 f366ff7b..., the unit of the maintainer's "e11 unpacked" binary 70df5cb1).
The guardian's text is guard0412.inc, beside this script (pinned by INC_SHA256 once the kit is frozen; until then by the
kit's kit.sha256). Six switches, all default off (unset, empty and "0" are off): BC5_GUARD_LEDGER, BC5_GUARD_MLOCK,
BC5_GUARD_FILE (+ BC5_GUARD_FILE_ROOT), BC5_GUARD_PSI, BC5_GUARD_PIN_CAP, BC5_GUARD_APPLY_MIN_MS; guard0412.inc's head
says what each does.
The edit, four places:
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
    a1 = b"static void direct_sync_one(DState& S, bool force) {\n"
    e.append(("the declaration", a1, b"static void guard0412_imported(int kind, int fd, uint64_t off, uint64_t size); // exp 0412 (tag g412)\n" + a1))
    a2 = b"\t\t\tS.bytes += size;\n"
    e.append(("the import hook", a2, a2 + b"\t\t\tguard0412_imported(S.kind, fd, off, size); // exp 0412 (tag g412): the guardian's ledger and BC5_GUARD_MLOCK\n"))
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
    assert out.count(b"\tlearned_apply();\n") == 0 and out.count(b"learned_apply();") == 1, "learned_apply's one call"
    # The guardian sits after e11's reopen counter, before learned_apply, inside the direct build's #if.
    p = [out.index(x) for x in (b"static void guard0412_imported(int kind, int fd, uint64_t off, uint64_t size); // exp 0412", b"static void direct_sync_one(",
                                b"guard0412_imported(S.kind, fd, off, size);", b"// G412_PURE_BEGIN\n", b"static void learned_apply() {", b"if (!guard0412_defer_apply()) learned_apply();")]
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
