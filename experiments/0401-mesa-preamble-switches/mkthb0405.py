#!/usr/bin/env python3
"""BC5 experiment 0405 (series e7 of experiment 0401), tag "thb": batch 1's held stubs are not registered when their
table's switch is on (the top session's decision of 2026-11-04, the rule batch 2 already follows). A held stub is a
function with no behaviour, ours or upstream's: AnyPS5 does not implement it (a throwing placeholder, or no export), or
its only source is one we cannot use (batch 1 held it on provenance). With the table's switch on, its init no longer
registers it, so a title's import of it stays unresolved, as before the table was loaded: the runtime linker's thunk
answers 0 and journals it (exp 0327's "[bc5] stubbed import called"). With the switch off, each init registers every
LIB_FUNC as today, in today's order. Series e6 is not changed (mktbc0405.py and mktbn0405.py stay as built).
Units (inputs: e7's chain at this point):
  src/libs/libIme.cpp  tbc's output (e6), InitIme_1 only: 39 held (KYTY_BC5_LOAD_IME, any item on)
  src/libs/libNp.cpp   e7's chain after tbt and tbp; only the inits of the namespaces NpCommon, NpManager, NpTrophy:
                       InitNpCommon_1 unchanged (all 28 ported), InitNpManager_1 4 held (KYTY_BC5_LOAD_NPMANAGER; its
                       two NIDs shared with libNet.cpp stay registered only when off, as tbn left them),
                       InitNpTrophy_1 64 held (KYTY_BC5_LOAD_NPTROPHY)
  src/libs/libZlib.cpp and src/libs/libJpeg.cpp are not edited: every function they register has behaviour when on
  (Jpeg Encode's held part is the encode inside a ported function, not a held function).
Each held LIB_FUNC line is wrapped in "if (<switch off>) { ... }" (the form tbp uses in the same file); its text is
unchanged. One comment is added after each edited init's switch read. Nothing else changes.
Every input's md5 is pinned in PINNED below (one dict, so the top session can re-pin it when it chains scripts) and
asserted; a unit that has this edit already is refused; every anchor must occur exactly once, inside its own init; each
held function must be a stub with no switch use; the held lists must be exactly the init's stubs with no behaviour
(less the one that already matches AnyPS5); every edit keeps braces, parentheses and brackets balanced; the inserted
text is ASCII; line ends and the BOM stay as they are (both units: LF, UTF-8 BOM); each init's LIB_FUNC order is
unchanged. After editing, the script undoes its own edits on the output and asserts that this gives the input back byte
for byte. Only the two units are written, and only when both are done. Prints "<relpath> <md5>" per written file.
Notes: thb0405-notes.md; CPU tests: tbc0405e7.cpp, tbn0405e7.cpp (e7's copies of tbc0405.cpp and tbn0405.cpp).
usage: mkthb0405.py <tree root in> <out dir>"""
import hashlib
import os
import re
import sys

PINNED = {  # input md5 of each unit this script edits (e7's chain at this point)
    "src/libs/libIme.cpp": "49fa46f1d8005245e7f0b266d8b29659",  # tbc's output (series e6), in the e7 input tree
    "src/libs/libNp.cpp": "e60a2844e6b607f7bafc019db8e872c2",   # e7's chain after tbt and tbp
}

MARKS = (b"experiment 0405 (thb", b"(thb):")

# ---- the held stubs, in each init's order (batch 1's notes: tbc0405-notes.md "Held Ime", tbn0405-notes.md HELD) ----
# Ime (tbc): sceImeFilterText held on provenance (AnyPS5's note libSceIme.md:22 names a disassembly with addresses); 36
# calls AnyPS5 does not implement (NotImplemented_nid_no_patch); sceImeOpenInternal and sceImeVshDisableController are
# not in AnyPS5.
IME_HELD = (
    ("mN+ZoSN-8hQ", "FinalizeImeModule"), ("uTW+63goeJs", "InitializeImeModule"),
    ("Lf3DeGWC6xg", "sceImeCheckFilterText"), ("zHuMUGb-AQI", "sceImeCheckRemoteEventParam"),
    ("OTb0Mg+1i1k", "sceImeCheckUpdateTextInfo"), ("Ho5NVQzpKHo", "sceImeConfigGet"),
    ("P5dPeiLwm-M", "sceImeConfigSet"), ("tKLmVIUkpyM", "sceImeConfirmCandidate"),
    ("NYDsL9a0oEo", "sceImeDicAddWord"), ("l01GKoyiQrY", "sceImeDicDeleteLearnDics"),
    ("E2OcGgi-FPY", "sceImeDicDeleteUserDics"), ("JAiMBkOTYKI", "sceImeDicDeleteWord"),
    ("JoPdCUXOzMU", "sceImeDicGetWords"), ("FuEl46uHDyo", "sceImeDicReplaceWord"),
    ("E+f1n8e8DAw", "sceImeDisableController"), ("evjOsE18yuI", "sceImeFilterText"),
    ("oYkJlMK51SA", "sceImeKeyboardOpenInternal"), ("3Hx2Uw9xnv8", "sceImeKeyboardUpdate"),
    ("16UI54cWRQk", "sceImeOpenInternal"), ("TQaogSaqkEk", "sceImeSetCandidateIndex"),
    ("oOwl47ouxoM", "sceImeVshClearPreedit"), ("gtoTsGM9vEY", "sceImeVshClose"),
    ("wTKF4mUlSew", "sceImeVshConfirmPreedit"), ("rM-1hkuOhh0", "sceImeVshDisableController"),
    ("42xMaQ+GLeQ", "sceImeVshGetPanelPositionAndForm"), ("ZmmV6iukhyo", "sceImeVshInformConfirmdString"),
    ("EQBusz6Uhp8", "sceImeVshInformConfirmdString2"), ("LBicRa-hj3A", "sceImeVshOpen"),
    ("-IAOwd2nO7g", "sceImeVshSendTextInfo"), ("qDagOjvJdNk", "sceImeVshSetCaretGeometry"),
    ("tNOlmxee-Nk", "sceImeVshSetCaretIndexInPreedit"), ("rASXozKkQ9g", "sceImeVshSetPanelPosition"),
    ("idvMaIu5H+k", "sceImeVshSetParam"), ("ga5GOgThbjo", "sceImeVshSetPreeditGeometry"),
    ("RuSca8rS6yA", "sceImeVshSetSelectGeometry"), ("J7COZrgSFRA", "sceImeVshSetSelectionText"),
    ("WqAayyok5p0", "sceImeVshUpdate"), ("O7Fdd+Oc-qQ", "sceImeVshUpdateContext"),
    ("fwcPR7+7Rks", "sceImeVshUpdateContext2"),
)
# NpManager (tbn): AnyPS5's throwing placeholders (PendingExports.cpp:733, 753, 757, AdditionalExports.cpp:804).
NPM_HELD = (
    ("KswxLxk4c1Y", "sceNpRegisterGamePresenceCallbackA"), ("aJZyCcHxzu4", "sceNpUnregisterGamePresenceCallbackA"),
    ("0c7HbXRKUt4", "sceNpRegisterStateCallbackForToolkit"),
    ("YIvqqvJyjEc", "sceNpUnregisterStateCallbackForToolkit"),
)
# Stubs this edit leaves as they are: sceNpUnregisterPlusEventCallback already answers as AnyPS5 does (0, Export.cpp:1056)
# and stays registered both ways; the two NIDs libNet.cpp's live table also registers (sceNpUnregisterStateCallback,
# sceNpUnregisterNpReachabilityStateCallback) are already registered only when off (tbn, tld0405-notes.md risk 1).
NPM_KEPT = ("xViqJdDgKl0", "mjjTXh+NHWY", "cRILAEvn+9M")
# NpTrophy (tbn): ConfigHasGroupFeature held on provenance (debt :28, the disassembly only); 62 throwing placeholders
# (debt :13-19, :34-38); SystemGetTrophyTitleIds absent from AnyPS5.
NPT_HELD = (
    ("cqGkYAN-gRw", "sceNpTrophyCaptureScreenshot"), ("lhE4XS9OJXs", "sceNpTrophyConfigGetTrophyDetails"),
    ("qJ3IvrOoXg0", "sceNpTrophyConfigGetTrophyFlagArray"), ("zDjF2G+6tI0", "sceNpTrophyConfigGetTrophyGroupArray"),
    ("7Kh86vJqtxw", "sceNpTrophyConfigGetTrophyGroupDetails"), ("ndLeNWExeZE", "sceNpTrophyConfigGetTrophySetInfo"),
    ("6EOfS5SDgoo", "sceNpTrophyConfigGetTrophySetInfoInGroup"),
    ("MW5ygoZqEBs", "sceNpTrophyConfigGetTrophySetVersion"),
    ("3tWKpNKn5+I", "sceNpTrophyConfigGetTrophyTitleDetails"), ("iqYfxC12sak", "sceNpTrophyConfigHasGroupFeature"),
    ("u9plkqa2e0k", "sceNpTrophyIntAbortHandle"), ("pE5yhroy9m0", "sceNpTrophyIntCheckNetSyncTitles"),
    ("edPIOFpEAvU", "sceNpTrophyIntCreateHandle"), ("DSh3EXpqAQ4", "sceNpTrophyIntDestroyHandle"),
    ("sng98qULzPA", "sceNpTrophyIntGetLocalTrophySummary"), ("t3CQzag7-zs", "sceNpTrophyIntGetProgress"),
    ("jF-mCgGuvbQ", "sceNpTrophyIntGetRunningTitle"), ("PeAyBjC5kp8", "sceNpTrophyIntGetRunningTitles"),
    ("PEo09Dkqv0o", "sceNpTrophyIntGetTrpIconByUri"), ("kF9zjnlAzIA", "sceNpTrophyIntNetSyncTitle"),
    ("UXiyfabxFNQ", "sceNpTrophyIntNetSyncTitles"), ("d9jpdPz5f-8", "sceNpTrophyShowTrophyList"),
    ("JzJdh-JLtu0", "sceNpTrophySystemAbortHandle"), ("z8RCP536GOM", "sceNpTrophySystemBuildGroupIconUri"),
    ("Rd2FBOQE094", "sceNpTrophySystemBuildNetTrophyIconUri"), ("Q182x0rT75I", "sceNpTrophySystemBuildTitleIconUri"),
    ("lGnm5Kg-zpA", "sceNpTrophySystemBuildTrophyIconUri"), ("20wAMbXP-u0", "sceNpTrophySystemCheckNetSyncTitles"),
    ("sKGFFY59ksY", "sceNpTrophySystemCheckRecoveryRequired"), ("JMSapEtDH9Q", "sceNpTrophySystemCloseStorage"),
    ("dk27olS4CEE", "sceNpTrophySystemCreateContext"), ("cBzXEdzVzvs", "sceNpTrophySystemCreateHandle"),
    ("NobVwD8qcQY", "sceNpTrophySystemDebugLockTrophy"), ("yXJlgXljItk", "sceNpTrophySystemDebugUnlockTrophy"),
    ("U0TOSinfuvw", "sceNpTrophySystemDestroyContext"), ("-LC9hudmD+Y", "sceNpTrophySystemDestroyHandle"),
    ("q6eAMucXIEM", "sceNpTrophySystemDestroyTrophyConfig"), ("OcllHFFcQkI", "sceNpTrophySystemGetGroupIcon"),
    ("tQ3tXfVZreU", "sceNpTrophySystemGetLocalTrophySummary"),
    ("g0dxBNTspC0", "sceNpTrophySystemGetNextTitleFileEntryStatus"), ("sJSDnJRJHhI", "sceNpTrophySystemGetProgress"),
    ("X47s4AamPGg", "sceNpTrophySystemGetTitleFileStatus"), ("7WPj4KCF3D8", "sceNpTrophySystemGetTitleIcon"),
    ("pzL+aAk0tQA", "sceNpTrophySystemGetTitleSyncStatus"), ("Ro4sI9xgYl4", "sceNpTrophySystemGetTrophyConfig"),
    ("7+OR1TU5QOA", "sceNpTrophySystemGetTrophyData"), ("aXhvf2OmbiE", "sceNpTrophySystemGetTrophyGroupData"),
    ("Rkt0bVyaa4Y", "sceNpTrophySystemGetTrophyIcon"), ("nXr5Rho8Bqk", "sceNpTrophySystemGetTrophyTitleData"),
    ("eV1rtLr+eys", "sceNpTrophySystemGetTrophyTitleIds"), ("SsGLKTfWfm0", "sceNpTrophySystemGetUserFileInfo"),
    ("XqLLsvl48kA", "sceNpTrophySystemGetUserFileStatus"), ("-qjm2fFE64M", "sceNpTrophySystemIsServerAvailable"),
    ("50BvYYzPTsY", "sceNpTrophySystemNetSyncTitle"), ("yDJ-r-8f4S4", "sceNpTrophySystemNetSyncTitles"),
    ("mWtsnHY8JZg", "sceNpTrophySystemOpenStorage"), ("tAxnXpzDgFw", "sceNpTrophySystemPerformRecovery"),
    ("tV18n8OcheI", "sceNpTrophySystemRemoveAll"), ("kV4DP0OTMNo", "sceNpTrophySystemRemoveTitleData"),
    ("lZSZoN8BstI", "sceNpTrophySystemRemoveUserData"), ("FJZW2oHUHFk", "Func_149656DA81D41C59"),
    ("n4AHGHb-pfY", "Func_9F80071876FFA5F6"), ("+O9vU1CpGZA", "Func_F8EF6F5350A91990"),
    ("+not13BEdVI", "Func_FA7A2DD770447552"),
)
assert (len(IME_HELD), len(NPM_HELD), len(NPT_HELD)) == (39, 4, 64)


def T(text):
    """C++ text written with a visible tab ("»") for each tab of the file's indentation, as ASCII bytes (LF units)."""
    return text.replace("»", "\t").encode("ascii")


def note(env, n):
    return (f"»// BC5 experiment 0405 (thb, series e7): with {env} on, the {n} held stubs below (no behaviour to port:\n"
            "»// AnyPS5 has none, or its only source is not usable) are not registered, so a title's import of one stays\n"
            "»// unresolved, as when this table was not loaded: the runtime linker's thunk answers 0 and journals it (exp\n"
            "»// 0327's \"[bc5] stubbed import called\"). Off, every NID is registered as today, in today's order.\n")


# rel, init, namespace, the init's switch read (the note goes after it), the off condition, switch, held, kept stubs,
# the switch helper whose use marks a function with behaviour
TABLES = (
    ("src/libs/libIme.cpp", "InitIme_1", "LibIme",
     "»(void)Bc5ImeItems(); // BC5 experiment 0405: reads KYTY_BC5_LOAD_IME once and prints its line at registration\n",
     "Bc5ImeItems() == 0", "KYTY_BC5_LOAD_IME", IME_HELD, (), "Bc5ImeItem("),
    ("src/libs/libNp.cpp", "InitNpManager_1", "NpManager",
     "»(void)Bc5NpmOn(); // BC5 experiment 0405 (tbn): reads KYTY_BC5_LOAD_NPMANAGER once, prints its line\n",
     "!Bc5NpmOn()", "KYTY_BC5_LOAD_NPMANAGER", NPM_HELD, NPM_KEPT, "Bc5NpmOn()"),
    ("src/libs/libNp.cpp", "InitNpTrophy_1", "NpTrophy",
     "»(void)Bc5NptOn(); // BC5 experiment 0405 (tbn): reads KYTY_BC5_LOAD_NPTROPHY once, prints its line\n",
     "!Bc5NptOn()", "KYTY_BC5_LOAD_NPTROPHY", NPT_HELD, (), "Bc5NptOn()"),
)
# The inits this script must leave byte for byte as they are (libNp.cpp's other tables; NpCommon has nothing held).
UNTOUCHED_INITS = {"src/libs/libNp.cpp": ("InitNpAuth_1", "InitNpCommon_1", "InitNpPartner_1", "InitNpParty_1",
                                          "InitNpSnsFacebookDialog_1", "InitNpTus_1")}
assert sorted({t[0] for t in TABLES}) == sorted(PINNED), "every unit has exactly one pinned md5"


def balance(b):
    return (b.count(b"{") - b.count(b"}"), b.count(b"(") - b.count(b")"), b.count(b"[") - b.count(b"]"))


def md5(b):
    return hashlib.md5(b).hexdigest()


def init_span(s, init):
    """[start, end) of LIB_DEFINE(<init>) { ... } (to its closing brace at column 0)."""
    head = f"LIB_DEFINE({init}) {{\n".encode("ascii")
    assert s.count(head) == 1, ("the init", init, s.count(head))
    a = s.index(head)
    b = s.index(b"\n}\n", a) + 3
    return a, b


def registrations(s, init):
    """Each LIB_FUNC of the init, in order: (nid, function)."""
    a, b = init_span(s, init)
    return re.findall(rb'LIB_FUNC\("([^"]+)", \w+::(\w+)\);', s[a:b])


def held_edit(cond, env, ns, nid, fn):
    old = f"»LIB_FUNC(\"{nid}\", {ns}::{fn});\n"
    new = (f"»if ({cond}) {{ // BC5 experiment 0405 (thb): held, registered only when {env} is off\n"
           f"»»LIB_FUNC(\"{nid}\", {ns}::{fn});\n»}}\n")
    return old, new


def edit_unit(rel, s):
    for m in MARKS:
        assert m not in s, ("the unit has the edit already", rel, m)
    assert b"\r" not in s, ("a CR in an LF unit", rel)
    out = s
    done = []
    for trel, init, ns, read, cond, env, held, kept, sw in TABLES:
        if trel != rel:
            continue
        # The namespace's own text before its init: each held function is a stub with no switch use, and the held
        # list is exactly the init's stubs with no switch use, less the kept ones.
        a, b = init_span(s, init)
        ns_head = f"namespace {ns} {{\n".encode("ascii")
        ns_at = s.rindex(ns_head, 0, a)
        region = s[ns_at:a]
        stubs = []
        for nid, fn in registrations(s, init):
            nid, fn = nid.decode(), fn.decode()
            m = re.search(rb"static int KYTY_SYSV_ABI " + fn.encode() + rb"\(([^)]*)\) \{\n(.*?)\n\}\n", region, re.S)
            assert m is not None, ("a registered function is not defined in its namespace", rel, fn)
            if sw.encode() not in m.group(2):
                stubs.append((nid, fn, m))
        listed = {nid for nid, _ in held}
        for nid, fn, m in stubs:
            assert nid in listed or nid in kept, ("a stub with no behaviour is neither held nor kept", rel, nid, fn)
        for nid, fn in held:
            m = [x for x in stubs if x[0] == nid]
            assert len(m) == 1 and m[0][1] == fn, ("a held NID is not a stub of this init", rel, nid, fn)
            body = m[0][2]
            assert body.group(1) == b"", ("a held stub takes arguments", rel, fn)
            assert re.fullmatch(rb"\tPRINT_NAME\(\);\n\treturn (OK|NP_NOT_SIGNED_IN);( // STUBBED)?", body.group(2)), \
                ("a held function has a body beyond today's stub", rel, fn, body.group(2)[:80])
        before = registrations(out, init)
        # The note, after the init's switch read.
        r = T(read)
        assert out.count(r) == 1, ("the switch read", rel, init, out.count(r))
        a, b = init_span(out, init)
        assert a < out.index(r) < b, ("the switch read is not inside its init", rel, init)
        n = r + T(note(env, len(held)))
        out = out.replace(r, n)
        done.append((r, n))
        # Each held LIB_FUNC line, wrapped.
        for nid, fn in held:
            o, n = (T(x) for x in held_edit(cond, env, ns, nid, fn))
            assert s.count(o) == 1 and out.count(o) == 1, ("a held line's anchor", rel, nid, s.count(o), out.count(o))
            a, b = init_span(out, init)
            assert a < out.index(o) < b, ("a held line is not inside its init", rel, init, nid)
            assert balance(o) == balance(n) == (0, 0, 0), ("the edit changes the balance", rel, nid)
            assert n.count(o.lstrip(b"\t")) == 1, ("a held line keeps its LIB_FUNC", rel, nid)
            out = out.replace(o, n)
            done.append((o, n))
        assert registrations(out, init) == before, ("the init's LIB_FUNC order changed", rel, init)
        assert out.count(f"held, registered only when {env} is off".encode()) == len(held), ("held count", rel, init)
    assert balance(out) == balance(s), ("the unit's balance changed", rel, balance(s), balance(out))
    for init in UNTOUCHED_INITS.get(rel, ()):
        a, b = init_span(s, init)
        c, d = init_span(out, init)
        assert s[a:b] == out[c:d], ("an init outside this edit changed", rel, init)
    # Undo the edits on the output (last first): the input must come back byte for byte.
    back = out
    for o, n in reversed(done):
        assert back.count(n) == 1, ("undo", rel, n[:60])
        back = back.replace(n, o)
    assert back == s, ("undoing the edits does not give the input back", rel)
    for o, n in done:
        n.decode("ascii")
    assert b"\r" not in out, ("a CR in the LF unit", rel)
    assert out.startswith(b"\xef\xbb\xbf") == s.startswith(b"\xef\xbb\xbf"), ("the BOM changed", rel)
    return out


def main():
    assert len(sys.argv) == 3, __doc__
    root, outdir = sys.argv[1], sys.argv[2]
    assert os.path.abspath(root) != os.path.abspath(outdir), "the out dir must not be the tree"
    outs = []
    for rel in PINNED:
        with open(os.path.join(root, rel), "rb") as f:
            s = f.read()
        for m in MARKS:
            assert m not in s, ("refused: the unit has the edit already", rel, m.decode())
        assert md5(s) == PINNED[rel], ("refused: not the pinned input", rel, md5(s), PINNED[rel])
        out = edit_unit(rel, s)
        print(f"# in:  {rel} {md5(s)}  ({len(s)} bytes, LF)", file=sys.stderr)
        outs.append((rel, out))
    for rel, out in outs:  # written only when both are done
        dst = os.path.join(outdir, rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        with open(dst, "wb") as f:
            f.write(out)
        print(f"{rel} {md5(out)}")


if __name__ == "__main__":
    main()
