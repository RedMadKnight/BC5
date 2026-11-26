#!/usr/bin/env python3
"""BC5 experiment 0405 (series e7 of experiment 0401), tag "tl3": the maintainer's decision 4 of exp 0405 (2026-11-04,
"=> B => B"): the HLE tables KytyPlus compiles but Libs::InitAll never loads are ported first, then loaded, each behind its
own switch (off by default; off is today's InitAll exactly). Series e6 (tag "tld", mktld0405.py) wired batch 1's six
tables into src/libs/libs.cpp as the Bc5Tables block; tag "tl2" (mktl20405.py) added batch 2's library tables after them.
This script adds batch 2's hardware group (their functions are ported by series e7's port agents tcm, thv and tus in their
own units) to that block, after every row already in TABLES, in this order:
  KYTY_BC5_LOAD_CAMERA     camera     Libs::LibCamera::InitCamera_1        libCamera.cpp
  KYTY_BC5_LOAD_USBD       usbd       Libs::LibUsbd::InitUsbd_1            libUsbd.cpp
  KYTY_BC5_LOAD_HMD        hmd        Libs::LibHmd::InitHmd_1              libHmd.cpp
  KYTY_BC5_LOAD_VRTRACKER  vrtracker  Libs::LibVrTracker::InitVrTracker_1  libVrTracker.cpp
  KYTY_BC5_LOAD_MOVE       move       Libs::LibMove::InitMove_1            libMove.cpp
Each switch is default off, read once (batch 1's function-local static in Bc5Tables::On, unchanged), env_flag.hpp's rule
(on = set, non-empty and not "0"). The one stderr line stays e6's: "[bc5] exp 0405: tables on (items: ...)" lists only
the items that are on, in TABLES' order, or "[bc5] exp 0405: tables off"; the five rows go after every earlier row, so the
earlier rows keep their bit numbers, and with all five unset InitAll's record list and that line are byte for byte what
the input gives (On, LoadSwitched, InitAll and struct Table are not touched, and the earlier rows stay as they are:
asserted).
The anchors do not name any batch-2 row: the declarations go right before "namespace Bc5Tables {", the rows right before
TABLES' closing "};", and the count line "static_assert(TABLE_COUNT == N);" is found by pattern, N checked against the
input's rows and raised by five. So the script also applies to a tl2 output with a different set of batch-2 rows; only
the pin below has to change. Every change but the count line is an insertion; the count line is the one replaced line.
The input's md5 is pinned in PINNED below (one dict, so the top session can re-pin it when it chains scripts) and
asserted; a unit that has this edit already is refused; every anchor must occur exactly once; braces, parentheses and
brackets stay balanced; the inserted text is ASCII; LF stays LF. After editing, the script undoes its own changes on the
output and asserts that this gives the input back byte for byte. Only the one unit is written. Prints "<relpath> <md5>"
for it. No upstream code is inserted: the block loads this tree's own tables (KytyPlus, GPL-2.0).
Notes: tl30405-notes.md; CPU test: tl30405.cpp.
usage: mktl30405.py <tree root in> <out dir>"""
import hashlib
import os
import re
import sys

# The inputs this script edits, pinned (relpath -> md5). The input libs.cpp is mktl20405.py's output (tag tl2), its
# second version (2026-11-04 18:28: fourteen batch-2 rows, TABLE_COUNT 20). The script also applies, re-pinned, to tl2's
# first version (aa8f39d19b563da518b14502941c7386, seventeen rows); tl30405.cpp's kEarlier then needs its three rows.
PINNED = {
    "src/libs/libs.cpp": "3ba4e3cd08d88a6d063d34a5e9cd813b",
}

UNIT = "src/libs/libs.cpp"

# This edit's own marks: an input that has any of them has the edit already.
MARKS = (b'tag "tl3"', b"(tl3)", b"KYTY_BC5_LOAD_CAMERA", b"KYTY_BC5_LOAD_USBD", b"KYTY_BC5_LOAD_HMD",
         b"KYTY_BC5_LOAD_VRTRACKER", b"KYTY_BC5_LOAD_MOVE", b"InitCamera_1", b"InitUsbd_1", b"InitHmd_1",
         b"InitVrTracker_1", b"InitMove_1")

# Batch 1 (series e6, tag tld): must be the first six rows of the input's TABLES, exactly so, in this order.
BATCH1 = (
    ("KYTY_BC5_LOAD_ZLIB", "zlib", "LibZlib::InitZlib_1"),
    ("KYTY_BC5_LOAD_JPEG", "jpeg", "LibJpeg::InitJpeg_1"),
    ("KYTY_BC5_LOAD_IME", "ime", "LibIme::InitIme_1"),
    ("KYTY_BC5_LOAD_NPCOMMON", "npcommon", "NpCommon::InitNpCommon_1"),
    ("KYTY_BC5_LOAD_NPMANAGER", "npmanager", "NpManager::InitNpManager_1"),
    ("KYTY_BC5_LOAD_NPTROPHY", "nptrophy", "NpTrophy::InitNpTrophy_1"),
)

# Batch 2's hardware group (this script), in load order: (switch, item, namespace, init function, unit, library name of
# its LIB_VERSION). Every init function, its namespace (inside Libs) and its LIB_VERSION ("libSce<X>", 1, "libSce<X>",
# 1, 1) were checked in the e7 input tree; file:line in tl30405-notes.md.
HW = (
    ("KYTY_BC5_LOAD_CAMERA", "camera", "LibCamera", "InitCamera_1", "libs/libCamera.cpp", "libSceCamera"),
    ("KYTY_BC5_LOAD_USBD", "usbd", "LibUsbd", "InitUsbd_1", "libs/libUsbd.cpp", "libSceUsbd"),
    ("KYTY_BC5_LOAD_HMD", "hmd", "LibHmd", "InitHmd_1", "libs/libHmd.cpp", "libSceHmd"),
    ("KYTY_BC5_LOAD_VRTRACKER", "vrtracker", "LibVrTracker", "InitVrTracker_1", "libs/libVrTracker.cpp",
     "libSceVrTracker"),
    ("KYTY_BC5_LOAD_MOVE", "move", "LibMove", "InitMove_1", "libs/libMove.cpp", "libSceMove"),
)
assert len(HW) == 5


def T(text):
    """C++ text written with a visible tab ("»") for each tab of the file's indentation, as ASCII bytes (LF)."""
    out = text.replace("»", "\t").encode("ascii")
    assert b"\r" not in out
    return out


# =====================================================================================================================
# src/libs/libs.cpp
# =====================================================================================================================
def _decl_text():
    lines = [
        '// ---- BC5 experiment 0405 (series e7 of experiment 0401), tag "tl3": batch 2\'s hardware group, five more dead',
        "// tables, each behind a switch. The same decision 4 (\"=> B => B\"): each table's functions are ported first",
        "// (series e7's port agents, in each table's own unit), then the table is loaded here, behind its own switch,",
        "// default off. They load after every table above, in this order (TABLES below):",
    ]
    for env, item, ns, init, unit, lib in HW:
        lines.append("//   %-24s %-10s %-22s %s" % (env, item, unit, lib))
    lines += [
        "// Each is library v1, module v1.1. The same rule and the same one stderr line as batch 1: the line lists the items",
        "// that are on, these last, so with all five unset InitAll's records and its line are what the tables above give.",
        "// Each table's own unit decides what its init registers (series e7: held stubs are not registered with the switch",
        "// on); tl30405.cpp counts the records at run time.",
        "// No key and no NID+type of these five tables is registered by a live table or by another dead table (e7 input",
        "// tree, tl30405-notes.md), so no lookup of another table moves; tl30405.cpp fails if one appears. Loading only",
        "// registers the tables' functions: nothing here opens a device.",
        "// No upstream code: this only loads this tree's own tables. GPL-2.0 as the rest of this file.",
    ]
    for env, item, ns, init, unit, lib in HW:
        lines += ["namespace %s {" % ns, "LIB_DEFINE(%s);" % init, "} // namespace %s" % ns]
    return "\n".join(lines) + "\n"


def _rows_text():
    lines = ['    // Batch 2\'s hardware group (series e7, tag "tl3"), after every row above:']
    for env, item, ns, init, unit, lib in HW:
        lines.append('    {"%s", "%s", %s::%s},' % (env, item, ns, init))
    return "\n".join(lines) + "\n"


# The declarations go between the last declaration and the blank line before "namespace Bc5Tables {".
DECL_ANCHOR = "\n\nnamespace Bc5Tables {\n"
# The rows go before TABLES' closing "};" (the line after it is the count's definition).
ROWS_ANCHOR = "\n};\nstatic constexpr size_t TABLE_COUNT = sizeof(TABLES) / sizeof(TABLES[0]);\n"
# The count line, whatever the comment after it says: "static_assert(TABLE_COUNT == N);" with N = the input's rows.
COUNT_RE = re.compile(rb"^static_assert\(TABLE_COUNT == ([0-9]+)\);[^\n]*\n", re.M)


def _count_text(n_in):
    n2 = n_in - len(BATCH1)
    return ("static_assert(TABLE_COUNT == %d); // BC5 experiment 0405 (tl3): batch 1's %d, batch 2's %d, its hardware "
            "group's %d\n" % (n_in + len(HW), len(BATCH1), n2, len(HW)))


# e6's functions that must stay byte for byte (the line, the read-once static, the load loop, InitAll, the row type).
KEEP = (
    ("static uint32_t On() {\n", "\n}\n"),
    ("static void LoadSwitched(Loader::SymbolDatabase* s) {\n", "\n}\n"),
    ("void InitAll(Loader::SymbolDatabase* s) {\n", "\n}\n"),
    ("struct Table {\n", "\n};\n"),
)

# Exact counts in the input (e6's block, tl2's rows) and in the output, for the names that must not change.
SAME_USES = (("Bc5Tables::LoadSwitched(s)", 1), ("static void LoadSwitched(", 1), ("On()", 2), ("TABLES[i]", 4),
             ("LIB_LOAD(", 42), ("[bc5] exp 0405: tables ", 4), ("namespace Bc5Tables {", 1),
             ("} // namespace Bc5Tables\n", 1), ("static_assert(TABLE_COUNT", 2),
             ("static_assert(TABLE_COUNT <= 32);\n", 1), ("static const Table TABLES[] = {\n", 1))


def balance(b):
    return (b.count(b"{") - b.count(b"}"), b.count(b"(") - b.count(b")"), b.count(b"[") - b.count(b"]"))


def md5(b):
    return hashlib.md5(b).hexdigest()


def span(s, start, end):
    a = T(start)
    assert s.count(a) == 1, ("must occur once", start, s.count(a))
    i = s.index(a)
    j = s.index(T(end), i)
    return s[i:j + len(T(end))]


def table_rows(s):
    """TABLES' rows in order: (switch, item, init) from the text between "static const Table TABLES[] = {" and "};"."""
    body = span(s, "static const Table TABLES[] = {\n", "\n};\n").decode("ascii")
    rows = re.findall(r'^    \{"([A-Z0-9_]+)", "([a-z0-9]+)", ([A-Za-z0-9_:]+)\},$', body, re.M)
    assert len(rows) == body.count('{"KYTY_BC5_LOAD_'), ("a row of TABLES does not parse", body)
    return rows


def decl_of(init):
    """The declaration a row's init function has in the block: namespace NS { LIB_DEFINE(F); } // namespace NS."""
    ns, f = init.split("::")
    return T("namespace %s {\nLIB_DEFINE(%s);\n} // namespace %s\n" % (ns, f, ns))


def edit_unit(s):
    for m in MARKS:
        assert m not in s, ("the unit has the edit already", UNIT, m)
    assert b"\r" not in s, ("a CR in the LF unit", UNIT)
    for name, n in SAME_USES:
        c = s.count(name.encode("ascii"))
        assert c == n, ("not the expected libs.cpp (e6's block with tl2's rows)", name, c, n)
    rows_in = table_rows(s)
    n_in = len(rows_in)
    assert rows_in[:len(BATCH1)] == list(BATCH1), ("TABLES does not start with batch 1's six", rows_in[:6])
    assert n_in > len(BATCH1) and n_in + len(HW) <= 32, ("row count", n_in)
    assert len({r[0] for r in rows_in}) == n_in and len({r[1] for r in rows_in}) == n_in, "rows not unique"
    for env, item, init in rows_in:
        assert env == "KYTY_BC5_LOAD_" + item.upper(), (env, item)
    for env, item, ns, init, unit, lib in HW:
        assert init.encode() not in s and env.encode() not in s, ("already in the input", init, env)
        assert ("namespace %s {" % ns).encode() not in s, ("namespace already in the input", ns)
        assert ('"%s"' % item).encode() not in s, ("item already in the input", item)
    # The count line: once, and it says the input's row count.
    found = COUNT_RE.findall(s)
    assert len(found) == 1 and int(found[0]) == n_in, ("the count line", found, n_in)
    count_old = COUNT_RE.search(s).group(0)
    # Every row's declaration: once, inside the block, before "namespace Bc5Tables {"; the block's region.
    blk0 = s.index(b"// ---- BC5 experiment 0405 (series e6 of experiment 0401), tag \"tld\"")
    blk1 = s.index(b"} // namespace Bc5Tables\n")
    bt = s.index(b"namespace Bc5Tables {\n")
    for env, item, init in rows_in:
        d = decl_of(init)
        assert s.count(d) == 1 and blk0 < s.index(d) < bt, ("the declaration of a row", init)
    # Anchors: once each, in this order, inside the block.
    da, ra = T(DECL_ANCHOR), T(ROWS_ANCHOR)
    assert s.count(da) == 1 and s.count(ra) == 1, ("anchors", s.count(da), s.count(ra))
    assert blk0 < s.index(da) < s.index(ra) < s.index(count_old) < blk1, "anchors out of place"
    # Right before the declaration anchor: a declaration's closing line; right before the rows anchor: the last row.
    before = s[:s.index(da) + 1]
    assert re.search(rb"\n\} // namespace [A-Za-z0-9_]+\n$", before), ("not after a declaration", before[-80:])
    last = rows_in[-1]
    assert s[:s.index(ra) + 1].endswith(T('    {"%s", "%s", %s},\n' % last)), ("not after the last row", last)

    decl, rows, count_new = T(_decl_text()), T(_rows_text()), T(_count_text(n_in))
    for what, t in (("the five declarations", decl), ("the five rows", rows), ("the count", count_new)):
        assert balance(t) == (0, 0, 0), ("the inserted text is not balanced", what, balance(t))
        t.decode("ascii")
    # (old, new) pairs; each old occurs once in the input.
    changes = (
        (da, b"\n" + decl + da[1:]),
        (ra, b"\n" + rows + ra[1:]),
        (count_old, count_new),
    )
    out = s
    for old, new in changes:
        assert out.count(old) == 1, ("anchor", old[:60])
        out = out.replace(old, new)
    assert balance(out) == balance(s), ("the unit's balance changed", balance(s), balance(out))
    for name, n in SAME_USES:
        c = out.count(name.encode("ascii"))
        assert c == n, ("uses", name, c, n)
    assert out.count(b'{"KYTY_BC5_LOAD_') == n_in + len(HW)
    assert out.count(b"KYTY_BC5_LOAD_") == s.count(b"KYTY_BC5_LOAD_") + 2 * len(HW)
    for env, item, ns, init, unit, lib in HW:
        assert out.count(("LIB_DEFINE(%s);" % init).encode()) == 1, init
        assert out.count(decl_of("%s::%s" % (ns, init))) == 1, init
        assert out.count(("%s::%s}," % (ns, init)).encode()) == 1, init
        assert out.count(('"%s"' % env).encode()) == 1 and out.count(('"%s"' % item).encode()) == 1, env
        assert env == "KYTY_BC5_LOAD_" + item.upper(), (env, item)
    # TABLES: the input's rows unchanged and first (so each keeps its bit), then the five in the brief's order.
    rows_out = table_rows(out)
    assert rows_out == rows_in + [(e, i, "%s::%s" % (ns, f)) for e, i, ns, f, u, l in HW], rows_out
    n_out = len(rows_out)
    assert len({r[0] for r in rows_out}) == n_out == n_in + 5 <= 32 and len({r[1] for r in rows_out}) == n_out
    assert [int(x) for x in COUNT_RE.findall(out)] == [n_out], "the count line of the output"
    # The declarations sit after every earlier declaration and before the block's namespace.
    last_decl = max(out.index(decl_of(init)) for env, item, init in rows_in)
    assert last_decl < out.index(b"namespace LibCamera {") < out.index(b"namespace LibMove {") < out.index(
        b"namespace Bc5Tables {\n")
    for start, end in KEEP:
        assert span(out, start, end) == span(s, start, end), ("changed", start)
    # Everything outside the block is byte for byte the input's.
    assert out[:blk0] == s[:blk0], "changed before the block"
    assert out[out.index(b"} // namespace Bc5Tables\n"):] == s[blk1:], "changed after the block"
    # Undo the changes on the output (last first): the input must come back byte for byte.
    back = out
    for old, new in reversed(changes):
        assert back.count(new) == 1, ("undo", new[:60])
        back = back.replace(new, old)
    assert back == s, "undoing the changes does not give the input back"
    assert b"\r" not in out, "a CR in the LF unit"
    return out


def main():
    assert len(sys.argv) == 3, __doc__
    root, outdir = sys.argv[1], sys.argv[2]
    assert os.path.abspath(root) != os.path.abspath(outdir), "the out dir must not be the tree"
    with open(os.path.join(root, UNIT), "rb") as f:
        s = f.read()
    for m in MARKS:
        assert m not in s, ("refused: the unit has the edit already", UNIT, m.decode())
    assert md5(s) == PINNED[UNIT], ("refused: not the pinned input", UNIT, md5(s), PINNED[UNIT])
    out = edit_unit(s)
    print(f"# in:  {UNIT} {md5(s)}  ({len(s)} bytes, LF, {len(table_rows(s))} rows)", file=sys.stderr)
    dst = os.path.join(outdir, UNIT)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    with open(dst, "wb") as f:
        f.write(out)
    print(f"{UNIT} {md5(out)}")


if __name__ == "__main__":
    main()
