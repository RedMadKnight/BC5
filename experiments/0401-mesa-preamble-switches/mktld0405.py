#!/usr/bin/env python3
"""BC5 experiment 0405 (series e6 of experiment 0401), tag "tld": the maintainer's decision 4 of exp 0405 (2026-11-04,
"=> B => B"): the HLE tables KytyPlus compiles but Libs::InitAll never loads are ported first, then loaded, each behind its
own switch (off by default; off is today's InitAll exactly). This script wires the loading of batch 1's six tables (their
functions are ported by tags tbc and tbn in their own units) into ONE unit of the e6 input tree:
  src/libs/libs.cpp   KYTY_BC5_LOAD_ZLIB       zlib       Libs::LibZlib::InitZlib_1         (libs/libZlib.cpp)
                      KYTY_BC5_LOAD_JPEG       jpeg       Libs::LibJpeg::InitJpeg_1         (libs/libJpeg.cpp)
                      KYTY_BC5_LOAD_IME        ime        Libs::LibIme::InitIme_1           (libs/libIme.cpp)
                      KYTY_BC5_LOAD_NPCOMMON   npcommon   Libs::NpCommon::InitNpCommon_1    (libs/libNp.cpp)
                      KYTY_BC5_LOAD_NPMANAGER  npmanager  Libs::NpManager::InitNpManager_1  (libs/libNp.cpp)
                      KYTY_BC5_LOAD_NPTROPHY   nptrophy   Libs::NpTrophy::InitNpTrophy_1    (libs/libNp.cpp)
A switch is on when set, non-empty and not "0" (env_flag.hpp's rule); each is read once, at the first InitAll, which prints
one stderr line: "[bc5] exp 0405: tables on (items: zlib,jpeg,...)" or "[bc5] exp 0405: tables off". The switched tables
load first, in the order above, before every live table (a key a live table also registers keeps the live function).
The input's md5 is pinned and asserted; a unit that has the edit already is refused; every anchor must occur exactly once;
every edit keeps braces, parentheses and brackets balanced; the inserted text is ASCII; LF stays LF. After editing, the
script undoes its own edits on the output and asserts that this gives the input back byte for byte. Only the one unit is
written. Prints "<relpath> <md5>" for it. No upstream code is inserted: the block wires this tree's own tables.
Notes: tld0405-notes.md; CPU test: tld0405.cpp.
usage: mktld0405.py <tree root in> <out dir>"""
import hashlib
import os
import sys

MARKS = (b"experiment 0405", b"KYTY_BC5_LOAD_", b"Bc5Tables", b"tables on (items")


def T(text):
    """C++ text written with a visible tab ("»") for each tab of the file's indentation, as ASCII bytes (LF)."""
    out = text.replace("»", "\t").encode("ascii")
    assert b"\r" not in out
    return out


# =====================================================================================================================
# src/libs/libs.cpp
# =====================================================================================================================
BLOCK_ANCHOR = "void InitAll(Loader::SymbolDatabase* s) {\n"
BLOCK = r"""// ---- BC5 experiment 0405 (series e6 of experiment 0401), tag "tld": six dead tables loaded, each behind a switch ----
// KytyPlus f266548 compiles 32 HLE tables (a LIB_DEFINE with LIB_FUNC registrations) that InitAll below never calls. The
// maintainer's decision 4 of exp 0405 (2026-11-04, "=> B => B"): each table's functions are ported first, then the table
// is loaded, each behind its own switch, default off. Batch 1, the CPU-only tables (their functions: tags tbc and tbn):
//   KYTY_BC5_LOAD_ZLIB       zlib       LibZlib::InitZlib_1         libs/libZlib.cpp  libSceZlib v1, module v1.1
//   KYTY_BC5_LOAD_JPEG       jpeg       LibJpeg::InitJpeg_1         libs/libJpeg.cpp  libSceJpegEnc v1, module v1.1
//   KYTY_BC5_LOAD_IME        ime        LibIme::InitIme_1           libs/libIme.cpp   libSceIme v1, module v1.1 (not the
//                                                                                     live Ime::InitPlatform_1_Ime above)
//   KYTY_BC5_LOAD_NPCOMMON   npcommon   NpCommon::InitNpCommon_1    libs/libNp.cpp    libSceNpCommon v1, module v1.1
//   KYTY_BC5_LOAD_NPMANAGER  npmanager  NpManager::InitNpManager_1  libs/libNp.cpp    libSceNpManager v1, module v1.1
//   KYTY_BC5_LOAD_NPTROPHY   nptrophy   NpTrophy::InitNpTrophy_1    libs/libNp.cpp    libSceNpTrophy v1, module v1.1
// A switch is on when set, non-empty and not "0" (env_flag.hpp's rule). Each is read once, at the first InitAll, which
// prints one stderr line: "[bc5] exp 0405: tables on (items: zlib,jpeg,...)" or "[bc5] exp 0405: tables off".
// The switched tables load FIRST, in the order above, before every live table. SymbolDatabase::Add keeps every record in
// its list and points the record's key, nid[library_vN][module_vM.m][Type] with "libSce" removed, at the newest record
// (insert_or_assign). A key that a live table also registers therefore keeps the live function for Find, the loader's
// lookup of a title's import by library and module (input tree: 7 Ime keys, 2 NpManager keys). The loader's NID-only
// lookups (FindByNid: RuntimeLinker::Resolve's fallback for an import whose key is not registered, and the late resolve
// of a stubbed import) take the FIRST record with that NID and type: for those 9 NIDs they reach the switched table's
// function (tld0405-notes.md, risk 1). With every switch off InitAll makes today's calls in today's order.
// No upstream code: this block only loads this tree's own tables. GPL-2.0 as the rest of this file.
namespace LibZlib {
LIB_DEFINE(InitZlib_1);
} // namespace LibZlib
namespace LibJpeg {
LIB_DEFINE(InitJpeg_1);
} // namespace LibJpeg
namespace LibIme {
LIB_DEFINE(InitIme_1);
} // namespace LibIme
namespace NpCommon {
LIB_DEFINE(InitNpCommon_1);
} // namespace NpCommon
namespace NpManager {
LIB_DEFINE(InitNpManager_1);
} // namespace NpManager
namespace NpTrophy {
LIB_DEFINE(InitNpTrophy_1);
} // namespace NpTrophy

namespace Bc5Tables {

struct Table {
»const char* env;  // the switch
»const char* item; // its name on the stderr line
»void (*init)(Loader::SymbolDatabase* s);
};

// In load order.
static const Table TABLES[] = {
    {"KYTY_BC5_LOAD_ZLIB", "zlib", LibZlib::InitZlib_1},
    {"KYTY_BC5_LOAD_JPEG", "jpeg", LibJpeg::InitJpeg_1},
    {"KYTY_BC5_LOAD_IME", "ime", LibIme::InitIme_1},
    {"KYTY_BC5_LOAD_NPCOMMON", "npcommon", NpCommon::InitNpCommon_1},
    {"KYTY_BC5_LOAD_NPMANAGER", "npmanager", NpManager::InitNpManager_1},
    {"KYTY_BC5_LOAD_NPTROPHY", "nptrophy", NpTrophy::InitNpTrophy_1},
};
static constexpr size_t TABLE_COUNT = sizeof(TABLES) / sizeof(TABLES[0]);
static_assert(TABLE_COUNT <= 32);

// Bit i: TABLES[i]'s switch is on. Read once; the first call prints the line.
static uint32_t On() {
»static const uint32_t on = [] {
»»uint32_t    bits = 0;
»»std::string items;
»»for (size_t i = 0; i < TABLE_COUNT; i++) {
»»»const char* e = std::getenv(TABLES[i].env);
»»»if (e != nullptr && e[0] != '\0' && std::strcmp(e, "0") != 0) {
»»»»bits |= 1u << i;
»»»»items += items.empty() ? "" : ",";
»»»»items += TABLES[i].item;
»»»}
»»}
»»if (bits == 0) {
»»»std::fprintf(stderr, "[bc5] exp 0405: tables off\n");
»»} else {
»»»std::fprintf(stderr, "[bc5] exp 0405: tables on (items: %s)\n", items.c_str());
»»}
»»std::fflush(stderr);
»»return bits;
»}();
»return on;
}

// The switched tables, in TABLES' order; nothing when every switch is off.
static void LoadSwitched(Loader::SymbolDatabase* s) {
»const uint32_t on = On();
»for (size_t i = 0; i < TABLE_COUNT; i++) {
»»if ((on & (1u << i)) != 0) {
»»»TABLES[i].init(s);
»»}
»}
}

} // namespace Bc5Tables
// ---- end of experiment 0405's switched tables ----

"""

EDITS = (
    ("includes",
     "#include \"loader/symbolDatabase.h\"\n\nnamespace Libs {\n",
     "#include \"loader/symbolDatabase.h\"\n\n"
     "#include <cstdint> // BC5 experiment 0405 (tld): the switched tables\n"
     "#include <cstdio>\n#include <cstdlib>\n#include <cstring>\n#include <string>\n\nnamespace Libs {\n"),
    ("InitAll: the switched tables first",
     "void InitAll(Loader::SymbolDatabase* s) {\n»LIB_LOAD(InitAudio_1);\n",
     "void InitAll(Loader::SymbolDatabase* s) {\n"
     "»Bc5Tables::LoadSwitched(s); // BC5 experiment 0405 (KYTY_BC5_LOAD_*): the switched tables first; none when all are off\n"
     "»LIB_LOAD(InitAudio_1);\n"),
)
# Must be in the input once, before the block's anchor (the block's declarations sit after today's ones).
BEFORE = ("namespace Ime {\nLIB_DEFINE(InitPlatform_1_Ime);\n} // namespace Ime\n", "LIB_DEFINE(InitBc5LleAgc_1);\n\n")
# Must be in the input once, after the block's anchor.
AFTER = ("»LIB_LOAD(InitBc5LleAgc_1);\n}\n", "namespace LibContentExport {\n\nLIB_VERSION(")
# Exact counts in the output.
USES = (("Bc5Tables::LoadSwitched(s)", 1), ("static void LoadSwitched(", 1), ("On()", 2), ("TABLES[i]", 4),
        ("KYTY_BC5_LOAD_", 13), ("LIB_DEFINE(InitZlib_1)", 1), ("LIB_DEFINE(InitJpeg_1)", 1), ("LIB_DEFINE(InitIme_1)", 1),
        ("LIB_DEFINE(InitNpCommon_1)", 1), ("LIB_DEFINE(InitNpManager_1)", 1), ("LIB_DEFINE(InitNpTrophy_1)", 1),
        ("LIB_LOAD(", 42), ("[bc5] exp 0405: tables ", 4))

UNIT = "src/libs/libs.cpp"
PINNED = "309aecf7c85a5b47217060bb87ec6512"  # base tree's libs.cpp (KytyPlus f266548 + patch 0001; not in E5-FILES.txt)


def balance(b):
    return (b.count(b"{") - b.count(b"}"), b.count(b"(") - b.count(b")"), b.count(b"[") - b.count(b"]"))


def md5(b):
    return hashlib.md5(b).hexdigest()


def edit_unit(s):
    for m in MARKS:
        assert m not in s, ("the unit has the edit already", UNIT, m)
    assert b"\r" not in s, ("a CR in the LF unit", UNIT)
    assert s.count(b"LIB_LOAD(") == 42, ("today's InitAll is not the expected one", s.count(b"LIB_LOAD("))
    A = T(BLOCK_ANCHOR)
    B = T(BLOCK)
    assert balance(B) == (0, 0, 0), ("the block is not balanced", balance(B))
    assert s.count(A) == 1, ("the block's anchor", s.count(A))
    at = s.index(A)
    for b in BEFORE:
        bb = T(b)
        assert s.count(bb) == 1 and s.index(bb) < at, ("must come before the block, once", b[:70], s.count(bb))
    for b in AFTER:
        bb = T(b)
        assert s.count(bb) == 1 and s.index(bb) > at, ("must come after the block, once", b[:70], s.count(bb))
    out = s.replace(A, B + A)
    done = []
    for what, old, new in EDITS:
        o, n = T(old), T(new)
        assert out.count(o) == 1, ("anchor", what, out.count(o))
        assert balance(o) == balance(n), ("the edit changes the balance", what, balance(o), balance(n))
        out = out.replace(o, n)
        done.append((o, n))
    assert balance(out) == balance(s), ("the unit's balance changed", balance(s), balance(out))
    for name, n in USES:
        c = out.count(name.encode("ascii"))
        assert c == n, ("uses", name, c, n)
    # InitAll's first statement is the switched tables; today's 41 loads follow in today's order.
    body = out[out.index(T("void InitAll(Loader::SymbolDatabase* s) {\n")):]
    body = body[:body.index(b"\n}\n")]
    old_body = s[s.index(T("void InitAll(Loader::SymbolDatabase* s) {\n")):]
    old_body = old_body[:old_body.index(b"\n}\n")]
    new_lines = body.split(b"\n")
    assert new_lines[1].startswith(T("»Bc5Tables::LoadSwitched(s);")), new_lines[1]
    assert b"\n".join(new_lines[:1] + new_lines[2:]) == old_body, "InitAll's other lines changed"
    # Undo the edits on the output (last first) and the block: the input must come back byte for byte.
    back = out
    for o, n in reversed(done):
        assert back.count(n) == 1, ("undo", n[:60])
        back = back.replace(n, o)
    assert back.count(B) == 1
    back = back.replace(B, b"")
    assert back == s, "undoing the edits does not give the input back"
    # The inserted text is ASCII; the unit stays LF.
    B.decode("ascii")
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
    assert md5(s) == PINNED, ("refused: not the pinned input", UNIT, md5(s), PINNED)
    out = edit_unit(s)
    print(f"# in:  {UNIT} {md5(s)}  ({len(s)} bytes, LF)", file=sys.stderr)
    dst = os.path.join(outdir, UNIT)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    with open(dst, "wb") as f:
        f.write(out)
    print(f"{UNIT} {md5(out)}")


if __name__ == "__main__":
    main()
