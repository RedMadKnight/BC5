#!/usr/bin/env python3
"""BC5 experiment 0419, the candidate after F ("G"), step 1: the library ports are built in.
The maintainer, 2026-11-13: "Porty bibliotek systemowych => wbudowane, ale uruchamiane tylko jezeli gra bedzie wolac".
Input: candidate F's tree (src/). 22 words leave:
  the 20 KYTY_BC5_LOAD_* of batch 2 (19 rows of libs.cpp's table and NPAUTH), KYTY_BC5_VOICE_PORTS,
  KYTY_BC5_NPTUS_FRIENDS_RUN.
What changes: each unit's switch function returns true and reads nothing; libs.cpp registers batch 2's rows always;
libUsbd's eager parse of the allow list at registration goes (the list is read at its users, on the first call).
KYTY_BC5_USBD_ALLOW stays (a list of devices, default empty). Batch 1's six words (ZLIB, JPEG, IME, NPCOMMON,
NPMANAGER, NPTROPHY) are NOT touched: they are the second title's rows.
Registration only adds records to the host's symbol database; nothing of a library runs before a title calls it
(ports-analysis.md). The `if (Bc5...On())` branches inside the units stay as they are in this step (constant now);
cutting the dead stub paths is a later, mechanical step.
usage: mklibs0419g.py <src dir>      edits in place, bytes, line endings kept"""
import re, sys

src = sys.argv[1]
WORDS = {  # word: file under libs/
    "KYTY_BC5_LOAD_NPTUS": "libNp.cpp", "KYTY_BC5_LOAD_NPPARTY": "libNp.cpp", "KYTY_BC5_LOAD_NPPARTNER": "libNp.cpp",
    "KYTY_BC5_LOAD_NPSNSFACEBOOK": "libNp.cpp", "KYTY_BC5_LOAD_VOICE": "libVoice.cpp",
    "KYTY_BC5_LOAD_SCREENSHOT": "libScreenShot.cpp", "KYTY_BC5_LOAD_DISCMAP": "libDiscMap.cpp",
    "KYTY_BC5_LOAD_ULOBJMGR": "libUlobjmgr.cpp", "KYTY_BC5_LOAD_COMPANIONHTTPD": "libCompanion.cpp",
    "KYTY_BC5_LOAD_COMPANIONUTIL": "libCompanion.cpp", "KYTY_BC5_LOAD_INVITATIONDIALOG": "libInvitationDialog.cpp",
    "KYTY_BC5_LOAD_WEBBROWSERDIALOG": "libWebBrowserDialog.cpp", "KYTY_BC5_LOAD_SHAREPLAY": "libSharePlay.cpp",
    "KYTY_BC5_LOAD_GAMELIVESTREAMING": "libGameLiveStreaming.cpp", "KYTY_BC5_LOAD_CAMERA": "libCamera.cpp",
    "KYTY_BC5_LOAD_USBD": "libUsbd.cpp", "KYTY_BC5_LOAD_HMD": "libHmd.cpp", "KYTY_BC5_LOAD_VRTRACKER": "libVrTracker.cpp",
    "KYTY_BC5_LOAD_MOVE": "libMove.cpp", "KYTY_BC5_LOAD_NPAUTH": "libNet.cpp",
    "KYTY_BC5_VOICE_PORTS": "libAudio.cpp", "KYTY_BC5_NPTUS_FRIENDS_RUN": "libNp.cpp",
}
assert len(WORDS) == 22
EXTRA = [("KYTY_BC5_VOICE_PORTS", "libVoice.cpp")]  # libVoice.cpp's own reader of the same word


def rd(p):
    return open(p, "rb").read()


def switch_const(b, word, name_out):
    """the one `static bool NAME() {` whose body reads `word` -> return true"""
    key = b'std::getenv("' + word.encode() + b'")'
    assert b.count(key) == 1, (word, b.count(key))
    at = b.index(key)
    heads = [m for m in re.finditer(rb"^static bool (\w+)\(\) \{\r?$", b[:at], re.M)]
    assert heads, word
    h = heads[-1]
    nl = b"\r\n" if b[h.end() - 2:h.end() + 1].find(b"\r") >= 0 or b[h.end():h.end() + 2] == b"\r\n" else b"\n"
    end = b.index(nl + b"}" + nl, at)
    body = b[h.start():end + len(nl) + 1]
    assert body.count(b"static bool ") == 1 and body.count(b"static const bool on = [] {") == 1, word
    assert b"return on;" in body
    name = h.group(1)
    new = (b"static bool " + name + b"() { // exp 0419 (candidate G): built in; the word " + word.encode() + b" is gone" + nl +
           b"\treturn true;" + nl + b"}")
    name_out.append((word, name.decode()))
    return b[:h.start()] + new + b[end + len(nl) + 1:]


names = []
files = {}
for word, f in list(WORDS.items()) + EXTRA:
    p = src + "/libs/" + f
    b = files.get(p) or rd(p)
    files[p] = switch_const(b, word, names)

# libUsbd.cpp: no parse of the allow list at registration
p = src + "/libs/libUsbd.cpp"
b = files[p]
m = re.search(rb"\tif \(Bc5UsbOn\(\)\) \{ // BC5 experiment 0405 \(tus\)[^\r\n]*\r?\n\t\t\(void\)Bc5UsbAllowList\(\);\r?\n\t\}\r?\n", b)
assert m and len(re.findall(rb"\(void\)Bc5UsbAllowList\(\);", b)) == 1
nl = b"\r\n" if b"\r\n" in m.group(0) else b"\n"
b = b[:m.start()] + b"\t// exp 0419 (candidate G): nothing runs at registration; the allow list is read by its first user" + nl + b[m.end():]
files[p] = b

# libs.cpp: batch 2's 19 rows are registered always, their words are gone
p = src + "/libs/libs.cpp"
b = rd(p)
rows = [w for w, f in WORDS.items() if w.startswith("KYTY_BC5_LOAD_") and w != "KYTY_BC5_LOAD_NPAUTH"]
assert len(rows) == 19
for w in rows:
    a = b'    {"' + w.encode() + b'", "'
    assert b.count(a) == 1, w
    b = b.replace(a, b'    {nullptr, "')
a = b"\t\t\tconst char* e = std::getenv(TABLES[i].env);"
assert b.count(a) == 1
b = b.replace(a, b'\t\t\tconst char* e = TABLES[i].env == nullptr ? "1" : std::getenv(TABLES[i].env); // exp 0419 (candidate G): no word = built in')
a = b"\tconst char* env;  // the switch"
assert b.count(a) == 1
b = b.replace(a, b"\tconst char* env;  // the switch; nullptr: built in, registered always (exp 0419, candidate G)")
files[p] = b

for p, b in files.items():
    open(p, "wb").write(b)
for w in WORDS:
    for p, b in files.items():
        left = b.count(b'getenv("' + w.encode() + b'")')
        assert left == 0, (w, p)
print("mklibs0419g ok: %d switch functions made constant in %d files: %s" % (len(names), len(files), " ".join(n for _, n in names)))
