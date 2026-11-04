#!/usr/bin/env python3
"""BC5 experiment 0405 (series e7 of experiment 0401), tag "tl2": the maintainer's decision 4 of exp 0405 (2026-11-04,
"=> B => B"): the HLE tables KytyPlus compiles but Libs::InitAll never loads are ported first, then loaded, each behind its
own switch (off by default; off is today's InitAll exactly). Series e6 (tag "tld", mktld0405.py) wired batch 1's six
tables into src/libs/libs.cpp as the Bc5Tables block. This script adds batch 2's fourteen library tables (their functions
are ported by series e7's port agents in their own units) to that block, after batch 1's six, in this order:
  KYTY_BC5_LOAD_NPTUS              nptus              Libs::NpTus::InitNpTus_1                              libNp.cpp
  KYTY_BC5_LOAD_NPPARTY            npparty            Libs::NpParty::InitNpParty_1                          libNp.cpp
  KYTY_BC5_LOAD_NPPARTNER          nppartner          Libs::NpPartner::InitNpPartner_1                      libNp.cpp
  KYTY_BC5_LOAD_NPSNSFACEBOOK      npsnsfacebook      Libs::NpSnsFacebookDialog::InitNpSnsFacebookDialog_1  libNp.cpp
  KYTY_BC5_LOAD_VOICE              voice              Libs::LibVoice::InitVoice_1                           libVoice.cpp
  KYTY_BC5_LOAD_SCREENSHOT         screenshot         Libs::LibScreenShot::InitScreenShot_1                 libScreenShot.cpp
  KYTY_BC5_LOAD_DISCMAP            discmap            Libs::LibDiscMap::InitDiscMap_1                       libDiscMap.cpp
  KYTY_BC5_LOAD_ULOBJMGR           ulobjmgr           Libs::LibUlobjmgr::InitUlobjmgr_1                     libUlobjmgr.cpp
  KYTY_BC5_LOAD_COMPANIONHTTPD     companionhttpd     Libs::CompanionHttpd::InitCompanionHttpd_1            libCompanion.cpp
  KYTY_BC5_LOAD_COMPANIONUTIL      companionutil      Libs::CompanionUtil::InitCompanionUtil_1              libCompanion.cpp
  KYTY_BC5_LOAD_INVITATIONDIALOG   invitationdialog   Libs::LibInvitationDialog::InitInvitationDialog_1     libInvitationDialog.cpp
  KYTY_BC5_LOAD_WEBBROWSERDIALOG   webbrowserdialog   Libs::LibWebBrowserDialog::InitWebBrowserDialog_1     libWebBrowserDialog.cpp
  KYTY_BC5_LOAD_SHAREPLAY          shareplay          Libs::LibSharePlay::InitSharePlay_1                   libSharePlay.cpp
  KYTY_BC5_LOAD_GAMELIVESTREAMING  gamelivestreaming  Libs::LibGameLiveStreaming::InitGameLiveStreaming_1   libGameLiveStreaming.cpp
Not loaded here (the top session, 2026-11-04): remoteplay (nothing ported, no switch), videorecording (its one function is
held, so its table would register nothing), npauth (its functions go into libNet.cpp's live NpAuth table, behind
KYTY_BC5_LOAD_NPAUTH read there; no dead table to load). With a table's switch on, its init registers only the ported
functions (series e7's rule for the ports: held stubs are skipped), so no count here or in the test is taken from the
input's LIB_FUNC lines.
Each switch is default off, read once (batch 1's function-local static in Bc5Tables::On, unchanged), env_flag.hpp's rule
(on = set, non-empty and not "0"). The one stderr line stays e6's: "[bc5] exp 0405: tables on (items: ...)" lists only
the items that are on, in TABLES' order, or "[bc5] exp 0405: tables off"; with all fourteen unset InitAll's record list
and that line are byte for byte what e6's libs.cpp gives (On, LoadSwitched and InitAll are not touched: asserted).
Every change is an insertion (three: the declarations, the rows, a count assertion). The input's md5 is pinned in PINNED
below (one dict, so the top session can re-pin it when it chains scripts) and asserted; a unit that has this edit already
is refused; every anchor must occur exactly once; braces, parentheses and brackets stay balanced; the inserted text is
ASCII; LF stays LF. After editing, the script undoes its own insertions on the output and asserts that this gives the
input back byte for byte. Only the one unit is written. Prints "<relpath> <md5>" for it. No upstream code is inserted: the
block loads this tree's own tables (KytyPlus, GPL-2.0).
Notes: tl20405-notes.md; CPU test: tl20405.cpp.
usage: mktl20405.py <tree root in> <out dir>"""
import hashlib
import os
import re
import sys

# The inputs this script edits, pinned (relpath -> md5). e7's input tree = e6's output: libs.cpp is mktld0405.py's output.
PINNED = {
    "src/libs/libs.cpp": "903fa699db7c20b2b3f288ab572bce8d",
}

UNIT = "src/libs/libs.cpp"

# This edit's own marks: an input that has any of them has the edit already.
MARKS = (b'tag "tl2"', b"(tl2)", b"KYTY_BC5_LOAD_NPTUS", b"KYTY_BC5_LOAD_GAMELIVESTREAMING", b"InitNpTus_1")

# Not loaded (the top session's follow-up of 2026-11-04): neither declared nor a row in the output.
DROPPED = (
    ("KYTY_BC5_LOAD_NPAUTH", "npauth", "NpAuth", "InitNpAuth_1"),
    ("KYTY_BC5_LOAD_REMOTEPLAY", "remoteplay", "LibRemotePlay", "InitRemotePlay_1"),
    ("KYTY_BC5_LOAD_VIDEORECORDING", "videorecording", "LibVideoRecording", "InitVideoRecording_1"),
)

# Batch 1 (series e6, tag tld): must be in the input exactly so, in this order.
BATCH1 = (
    ("KYTY_BC5_LOAD_ZLIB", "zlib", "LibZlib::InitZlib_1"),
    ("KYTY_BC5_LOAD_JPEG", "jpeg", "LibJpeg::InitJpeg_1"),
    ("KYTY_BC5_LOAD_IME", "ime", "LibIme::InitIme_1"),
    ("KYTY_BC5_LOAD_NPCOMMON", "npcommon", "NpCommon::InitNpCommon_1"),
    ("KYTY_BC5_LOAD_NPMANAGER", "npmanager", "NpManager::InitNpManager_1"),
    ("KYTY_BC5_LOAD_NPTROPHY", "nptrophy", "NpTrophy::InitNpTrophy_1"),
)

# Batch 2 (this script), in load order: (switch, item, namespace, init function, unit, library name of its LIB_VERSION).
# Every init function, its namespace (inside Libs) and its LIB_VERSION were checked in the e7 input tree; file:line in
# tl20405-notes.md.
BATCH2 = (
    ("KYTY_BC5_LOAD_NPTUS", "nptus", "NpTus", "InitNpTus_1", "libs/libNp.cpp", "libSceNpTus"),
    ("KYTY_BC5_LOAD_NPPARTY", "npparty", "NpParty", "InitNpParty_1", "libs/libNp.cpp", "libSceNpParty"),
    ("KYTY_BC5_LOAD_NPPARTNER", "nppartner", "NpPartner", "InitNpPartner_1", "libs/libNp.cpp", "libSceNpPartner001"),
    ("KYTY_BC5_LOAD_NPSNSFACEBOOK", "npsnsfacebook", "NpSnsFacebookDialog", "InitNpSnsFacebookDialog_1", "libs/libNp.cpp",
     "libSceNpSnsFacebookDialog"),
    ("KYTY_BC5_LOAD_VOICE", "voice", "LibVoice", "InitVoice_1", "libs/libVoice.cpp", "libSceVoice"),
    ("KYTY_BC5_LOAD_SCREENSHOT", "screenshot", "LibScreenShot", "InitScreenShot_1", "libs/libScreenShot.cpp",
     "libSceScreenShot"),
    ("KYTY_BC5_LOAD_DISCMAP", "discmap", "LibDiscMap", "InitDiscMap_1", "libs/libDiscMap.cpp", "libSceDiscMap"),
    ("KYTY_BC5_LOAD_ULOBJMGR", "ulobjmgr", "LibUlobjmgr", "InitUlobjmgr_1", "libs/libUlobjmgr.cpp", "ulobjmgr"),
    ("KYTY_BC5_LOAD_COMPANIONHTTPD", "companionhttpd", "CompanionHttpd", "InitCompanionHttpd_1", "libs/libCompanion.cpp",
     "libSceCompanionHttpd"),
    ("KYTY_BC5_LOAD_COMPANIONUTIL", "companionutil", "CompanionUtil", "InitCompanionUtil_1", "libs/libCompanion.cpp",
     "libSceCompanionUtil"),
    ("KYTY_BC5_LOAD_INVITATIONDIALOG", "invitationdialog", "LibInvitationDialog", "InitInvitationDialog_1",
     "libs/libInvitationDialog.cpp", "libSceInvitationDialog"),
    ("KYTY_BC5_LOAD_WEBBROWSERDIALOG", "webbrowserdialog", "LibWebBrowserDialog", "InitWebBrowserDialog_1",
     "libs/libWebBrowserDialog.cpp", "libSceWebBrowserDialog"),
    ("KYTY_BC5_LOAD_SHAREPLAY", "shareplay", "LibSharePlay", "InitSharePlay_1", "libs/libSharePlay.cpp", "libSceSharePlay"),
    ("KYTY_BC5_LOAD_GAMELIVESTREAMING", "gamelivestreaming", "LibGameLiveStreaming", "InitGameLiveStreaming_1",
     "libs/libGameLiveStreaming.cpp", "libSceGameLiveStreaming"),
)
assert len(BATCH2) == 14
assert not {d[0] for d in DROPPED} & {b[0] for b in BATCH2}


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
        '// ---- BC5 experiment 0405 (series e7 of experiment 0401), tag "tl2": batch 2, fourteen more dead tables, each',
        "// behind a switch. The same decision 4 (\"=> B => B\"): each table's functions are ported first (series e7's port",
        "// agents, in each table's own unit), then the table is loaded here, behind its own switch, default off. Batch 2,",
        "// the CPU-only library tables, loads after batch 1's six, in this order (TABLES below):",
    ]
    for env, item, ns, init, unit, lib in BATCH2:
        lines.append("//   %-32s %-18s %-30s %s" % (env, item, unit, lib))
    lines += [
        "// Each is library v1, module v1.1. The same rule and the same one stderr line as batch 1: the line lists the items",
        "// that are on, these after batch 1's, so with all fourteen unset InitAll's records and its line are series e6's.",
        "// With its switch on, a table's init registers only its ported functions (held stubs are skipped there).",
        "// Not loaded here: remoteplay (nothing ported), videorecording (its one function held), npauth (its functions go",
        "// into libNet.cpp's live NpAuth table, behind KYTY_BC5_LOAD_NPAUTH read there).",
        "// No key and no NID+type of these fourteen tables is registered by a live table (e7 input tree, tl20405-notes.md),",
        "// so the NID-only lookups described above do not move for them; tl20405.cpp fails if one appears.",
        "// No upstream code: this only loads this tree's own tables. GPL-2.0 as the rest of this file.",
    ]
    for env, item, ns, init, unit, lib in BATCH2:
        lines += ["namespace %s {" % ns, "LIB_DEFINE(%s);" % init, "} // namespace %s" % ns]
    return "\n".join(lines) + "\n"


def _rows_text():
    lines = ['    // Batch 2 (series e7, tag "tl2"), after batch 1:']
    for env, item, ns, init, unit, lib in BATCH2:
        lines.append('    {"%s", "%s", %s::%s},' % (env, item, ns, init))
    return "\n".join(lines) + "\n"


DECL_ANCHOR = "namespace NpTrophy {\nLIB_DEFINE(InitNpTrophy_1);\n} // namespace NpTrophy\n"
ROWS_ANCHOR = '    {"KYTY_BC5_LOAD_NPTROPHY", "nptrophy", NpTrophy::InitNpTrophy_1},\n'
COUNT_ANCHOR = "static_assert(TABLE_COUNT <= 32);\n"
COUNT_TEXT = "static_assert(TABLE_COUNT == 20); // BC5 experiment 0405 (tl2): batch 1's six, then batch 2's fourteen\n"

# (what, anchor, text inserted right after the anchor)
INSERTS = (
    ("the fourteen declarations", DECL_ANCHOR, _decl_text()),
    ("the fourteen rows of TABLES", ROWS_ANCHOR, _rows_text()),
    ("the count", COUNT_ANCHOR, COUNT_TEXT),
)

# e6's functions that must stay byte for byte (the line, the read-once static, the load loop, InitAll).
KEEP = (
    ("static uint32_t On() {\n", "\n}\n"),
    ("static void LoadSwitched(Loader::SymbolDatabase* s) {\n", "\n}\n"),
    ("void InitAll(Loader::SymbolDatabase* s) {\n", "\n}\n"),
    ("struct Table {\n", "\n};\n"),
)

# Exact counts in the input (e6's block as mktld0405.py wrote it) and in the output.
IN_USES = (("Bc5Tables::LoadSwitched(s)", 1), ("static void LoadSwitched(", 1), ("On()", 2), ("TABLES[i]", 4),
           ("KYTY_BC5_LOAD_", 13), ('{"KYTY_BC5_LOAD_', 6), ("LIB_LOAD(", 42), ("[bc5] exp 0405: tables ", 4),
           ("namespace Bc5Tables {", 1), ("static_assert(TABLE_COUNT", 1))
OUT_USES = (("Bc5Tables::LoadSwitched(s)", 1), ("static void LoadSwitched(", 1), ("On()", 2), ("TABLES[i]", 4),
            ("KYTY_BC5_LOAD_", 13 + 14 + 14 + 1), ('{"KYTY_BC5_LOAD_', 6 + 14), ("LIB_LOAD(", 42),
            ("[bc5] exp 0405: tables ", 4), ("namespace Bc5Tables {", 1), ("static_assert(TABLE_COUNT", 2))


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
    return re.findall(r'^    \{"([A-Z0-9_]+)", "([a-z0-9]+)", ([A-Za-z0-9_:]+)\},$', body, re.M)


def edit_unit(s):
    for m in MARKS:
        assert m not in s, ("the unit has the edit already", UNIT, m)
    assert b"\r" not in s, ("a CR in the LF unit", UNIT)
    for name, n in IN_USES:
        c = s.count(name.encode("ascii"))
        assert c == n, ("not e6's libs.cpp", name, c, n)
    assert table_rows(s) == list(BATCH1), ("TABLES is not batch 1's six", table_rows(s))
    for env, item, ns, init, unit, lib in BATCH2:
        assert init.encode() not in s and env.encode() not in s, ("already in the input", init, env)
        assert ("namespace %s {" % ns).encode() not in s, ("namespace already in the input", ns)
    # Anchors: once each, in this order, inside the block.
    blk0 = s.index(b"namespace LibZlib {\nLIB_DEFINE(InitZlib_1);")
    blk1 = s.index(b"} // namespace Bc5Tables\n")
    last = blk0
    for what, anchor, text in INSERTS:
        a = T(anchor)
        assert s.count(a) == 1, ("anchor", what, s.count(a))
        at = s.index(a)
        assert last <= at < blk1, ("anchor out of place", what)
        last = at
    out = s
    done = []
    for what, anchor, text in INSERTS:
        a, t = T(anchor), T(text)
        assert balance(t) == (0, 0, 0), ("the inserted text is not balanced", what, balance(t))
        assert out.count(a) == 1, ("anchor", what, out.count(a))
        out = out.replace(a, a + t)
        done.append((a, a + t))
    assert balance(out) == balance(s), ("the unit's balance changed", balance(s), balance(out))
    for name, n in OUT_USES:
        c = out.count(name.encode("ascii"))
        assert c == n, ("uses", name, c, n)
    for env, item, ns, init, unit, lib in BATCH2:
        assert out.count(("LIB_DEFINE(%s);" % init).encode()) == 1, init
        assert out.count(("%s::%s}," % (ns, init)).encode()) == 1, init
        assert out.count(('"%s"' % env).encode()) == 1 and out.count(('"%s"' % item).encode()) == 1, env
        assert env == "KYTY_BC5_LOAD_" + item.upper(), (env, item)
    # The three dropped tables: no declaration, no row, no quoted switch or item (KYTY_BC5_LOAD_NPAUTH is named once, in
    # the comment, as libNet.cpp's switch).
    for env, item, ns, init in DROPPED:
        assert init.encode() not in out and ("namespace %s {" % ns).encode() not in out, ("dropped table declared", init)
        assert ('"%s"' % env).encode() not in out and ('"%s"' % item).encode() not in out, ("dropped table's row", env)
    assert out.count(b"KYTY_BC5_LOAD_NPAUTH") == 1 and out.count(b"KYTY_BC5_LOAD_REMOTEPLAY") == 0
    assert out.count(b"KYTY_BC5_LOAD_VIDEORECORDING") == 0
    # TABLES: batch 1's six unchanged and first, then the fourteen in the top session's order; switches and items unique.
    rows = table_rows(out)
    assert rows == list(BATCH1) + [(e, i, "%s::%s" % (ns, f)) for e, i, ns, f, u, l in BATCH2], rows
    assert len({r[0] for r in rows}) == len(rows) == 20 and len({r[1] for r in rows}) == 20
    # The declarations sit before TABLES and after batch 1's; e6's functions stay byte for byte.
    assert out.index(b"LIB_DEFINE(InitNpTrophy_1);") < out.index(b"LIB_DEFINE(InitNpTus_1);") < out.index(
        b"static const Table TABLES[] = {")
    for start, end in KEEP:
        assert span(out, start, end) == span(s, start, end), ("changed", start)
    # Undo the insertions on the output (last first): the input must come back byte for byte.
    back = out
    for o, n in reversed(done):
        assert back.count(n) == 1, ("undo", n[:60])
        back = back.replace(n, o)
    assert back == s, "undoing the insertions does not give the input back"
    # The inserted text is ASCII; the unit stays LF.
    for o, n in done:
        n.decode("ascii")
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
    print(f"# in:  {UNIT} {md5(s)}  ({len(s)} bytes, LF)", file=sys.stderr)
    dst = os.path.join(outdir, UNIT)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    with open(dst, "wb") as f:
        f.write(out)
    print(f"{UNIT} {md5(out)}")


if __name__ == "__main__":
    main()
