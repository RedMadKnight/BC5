#!/usr/bin/env python3
"""BC5 experiment 0405 (series e6 of experiment 0401), tag "pad": three groups of scePad calls that src/libs/libPad.cpp did
not register (a title that imports them gets the loader's stub today: 0, nothing written), registered behind one switch
that is off by default and read once (off: not registered, today's path exactly):
  KYTY_BC5_FW_PAD  items  infotype   scePadGetInfoByPortType                       (exp 0405 R1 C.tsv row b94b3fa32)
                          argchecks  twelve calls' argument and state checks       (row 3b404f65e)
                          queries    five DualShock-4/Leonardo-only queries         (row 2f9581050)
The maintainer cleared b94b3fa32 and 3b404f65e on 2026-11-04 ("tak, przepisac tak JIT"): written from the behaviour of
AnyPS5's GPL-2.0-only code only, with this file's own names, structure and comments, citing AnyPS5's code (path:lines,
commit) and nothing else. 2f9581050 is a decision-1 row (a firmware run) that became small once the pad's init state is
kept here.
A value naming items ("infotype,queries") turns on only those; any other non-empty value but "0" turns on all of them.
The input md5 is pinned and asserted; a unit that has the edit already is refused; every anchor must occur exactly once;
every edit keeps braces, parentheses and brackets balanced; the inserted text is ASCII; LF stays LF. After editing, the
script undoes its own edits on the output and asserts that this gives the input back byte for byte. Prints
"<relpath> <md5>". Notes: pad0405-notes.md; CPU test: pad0405.cpp.
usage: mkpad0405.py <tree root in> <out dir>"""
import hashlib
import os
import sys

MARKS = (b"KYTY_BC5_FW_PAD", b"Bc5FwPad", b"BC5_FW_PAD_")


def T(text):
    """C++ text written with a visible tab ("»") for each tab of the file's indentation, as ASCII bytes."""
    return text.replace("»", "\t").encode("ascii")


ANYPS5 = "AnyPS5 (github.com/boykopovar/AnyPS5, GPL-2.0-only) @ 4f41f4c375f5abb487dbd184fbc150f31994d762"

BLOCK_ANCHOR = "LIB_DEFINE(InitPad_1) {\n"
BLOCK = (r"""// ---- BC5 experiment 0405 (series e6 of experiment 0401): KYTY_BC5_FW_PAD ----
// scePad calls this file did not register: a title that imports one gets the loader's stub today (0, nothing written).
// With an item on, each is registered here and answers the checks that """ + ANYPS5 + r""",
// core/libs/prx/libScePad/Export.cpp makes for it, in the same order. Written from that code's behaviour only, with this
// file's own names and structure; outputs are untyped where the checks do not need their layout.
//   "infotype"  scePadGetInfoByPortType(type, out), Export.cpp:1014-1019 (commit b94b3fa32): a null output is refused
//               first (INVALID_ARG), then a call before scePadInit (NOT_INITIALIZED), then a port type other than 0 or 2
//               (INVALID_ARG).
//   "argchecks" twelve calls, Export.cpp:562-566, 573-578, 589-594, 636-646, 683-688, 710-715, 997-1012, 1148-1153,
//               1208-1212, 1229-1235 (commit 3b404f65e). Before scePadInit: NOT_INITIALIZED (scePadGetIdleCount: 0;
//               scePadReadStateExt has no such check). Then: a null output is INVALID_ARG (DeviceInfo, Capability,
//               VersionInfo, ExtensionUnitInfo, ActiveTime, DeviceId); ControllerIdleCount refuses handle 0 or a null
//               count (INVALID_ARG); ReadHistory needs a byte size of 0x960 and OpenExt2 a parameter size of 0x10 with a
//               parameter (INVALID_ARG); ActiveTime writes 0 to its output and DeviceId -1 to its output once the output
//               is there, and DeviceId then refuses an unknown handle (INVALID_HANDLE); ReadStateExt refuses an unknown
//               handle (INVALID_HANDLE), then a null output (INVALID_ARG), as this host's scePadReadState does.
//               Past these checks AnyPS5 stops (the answer would come from the pad driver, which it does not model);
//               here such a call answers what the loader's stub answered before, 0 with nothing more written, and the
//               first 8 such calls get a stderr line. TODO(verify): the answers past the checks.
//   "queries"   scePadGetMotionTimerUnit, GetMotionSensorPosition, GetSphereRadius, GetBluetoothAddress and
//               ParseUniqueDataLeonardo, Export.cpp:81-85, 899-905, 1054-1078, 1101-1106 (commit 2f9581050; the
//               maintainer's decision 1: a firmware 13.42 run): the one DualSense this host reports has none of these, so
//               after NOT_INITIALIZED / INVALID_ARG / INVALID_HANDLE checks they answer DEVICE_NOT_CONNECTED (0x80920007)
//               without writing, except that MotionTimerUnit writes 0.0 before its handle check, and
//               ParseUniqueDataLeonardo clears 0x18 bytes of its output and answers INVALID_HANDLE. SphereRadius answers
//               only a special-port handle; this host opens every port type on the player's one handle, so it answers
//               INVALID_HANDLE for every handle here.
// "Initialised": scePadInit was called; with any item on this file registers scePadInit through Bc5FwPadInit, which
// records it and calls Controller::PadInit as before. "Known handle": this host's handles 1 to 4
// (Controller::ControllerIndexFromHandle), which every pad call here accepts; the host keeps no closed state.
// KYTY_BC5_FW_PAD: unset, empty or "0" is off (nothing registered: today's path exactly); any other value turns every
// item on, unless it names items (comma-separated "infotype", "argchecks", "queries"). Read once; one stderr line at
// registration, on or off.
// AnyPS5's copyright remains with its authors; GPL-2.0 as the rest of this file.
static constexpr uint32_t BC5_FW_PAD_INFOTYPE  = 1u;
static constexpr uint32_t BC5_FW_PAD_ARGCHECKS = 2u;
static constexpr uint32_t BC5_FW_PAD_QUERIES   = 4u;

static constexpr int Bc5FwPadInvalidArg      = static_cast<int>(0x80920001u);
static constexpr int Bc5FwPadInvalidHandle   = static_cast<int>(0x80920003u);
static constexpr int Bc5FwPadNotInitialized  = static_cast<int>(0x80920005u);
static constexpr int Bc5FwPadNotConnected    = static_cast<int>(0x80920007u);
static constexpr uint32_t Bc5FwPadHistoryBytes   = 0x960u; // scePadReadHistory's byte size (Export.cpp:1231)
static constexpr int      Bc5FwPadOpenExt2Bytes  = 0x10;   // scePadOpenExt2's parameter size (Export.cpp:591)
static constexpr size_t   Bc5FwPadLeonardoBytes  = 0x18;   // what ParseUniqueDataLeonardo clears (Export.cpp:86, 903)

static uint32_t Bc5FwPadParse(const char* e) {
»if (e == nullptr || e[0] == '\0' || std::strcmp(e, "0") == 0) {
»»return 0;
»}
»static const char* const names[] = {"infotype", "argchecks", "queries"}; // bit i is names[i]
»uint32_t                 parts   = 0;
»const char*              p       = e;
»for (;;) {
»»const char*  comma = std::strchr(p, ',');
»»const size_t n     = comma != nullptr ? static_cast<size_t>(comma - p) : std::strlen(p);
»»for (uint32_t i = 0; i < 3; i++) {
»»»if (n == std::strlen(names[i]) && std::strncmp(p, names[i], n) == 0) {
»»»»parts |= 1u << i;
»»»}
»»}
»»if (comma == nullptr) {
»»»break;
»»}
»»p = comma + 1;
»}
»return parts != 0 ? parts : 7u; // every item
}

// The items of KYTY_BC5_FW_PAD that are on (0: off), read once; the first call (this library's registration) prints the
// switch's one stderr line, on or off.
static uint32_t Bc5FwPadItems() {
»static const uint32_t parts = [] {
»»const uint32_t p = Bc5FwPadParse(std::getenv("KYTY_BC5_FW_PAD"));
»»if (p == 0) {
»»»std::fprintf(stderr, "[bc5] exp 0405: fw pad off\n");
»»} else {
»»»std::fprintf(stderr, "[bc5] exp 0405: fw pad on (items:%s%s%s)\n", (p & BC5_FW_PAD_INFOTYPE) != 0 ? " infotype" : "",
»»»             (p & BC5_FW_PAD_ARGCHECKS) != 0 ? " argchecks" : "", (p & BC5_FW_PAD_QUERIES) != 0 ? " queries" : "");
»»}
»»std::fflush(stderr);
»»return p;
»}();
»return parts;
}

static std::atomic<bool> g_bc5_fw_pad_initialized {false}; // scePadInit was called (only kept with an item on)

static int KYTY_SYSV_ABI Bc5FwPadInit() {
»const int result = Controller::PadInit();
»if (result == OK) {
»»g_bc5_fw_pad_initialized.store(true);
»}
»return result;
}

static bool Bc5FwPadReady() {
»return g_bc5_fw_pad_initialized.load();
}

static bool Bc5FwPadKnown(int handle) {
»return Controller::ControllerIndexFromHandle(handle) >= 0;
}

// Past its checks: the answer the loader's stub gave before (0, nothing more written); a stderr line for the first 8.
static int Bc5FwPadPastChecks(const char* call) {
»static std::atomic<uint32_t> told {0};
»if (told.fetch_add(1, std::memory_order_relaxed) < 8) {
»»std::fprintf(stderr, "[bc5] exp 0405: fw pad %s past its checks -> 0, nothing written (not modelled)\n", call);
»»std::fflush(stderr);
»}
»return OK;
}

// "infotype"
static int KYTY_SYSV_ABI Bc5FwPadPortInfoByType(int port_type, void* info) {
»PRINT_NAME();
»if (info == nullptr) {
»»return Bc5FwPadInvalidArg;
»}
»if (!Bc5FwPadReady()) {
»»return Bc5FwPadNotInitialized;
»}
»if (port_type != 0 && port_type != 2) {
»»return Bc5FwPadInvalidArg;
»}
»return Bc5FwPadPastChecks("GetInfoByPortType");
}

// "argchecks": calls whose only checks are the init state and a null output.
static int Bc5FwPadInitAndOutput(const void* out, const char* call) {
»if (!Bc5FwPadReady()) {
»»return Bc5FwPadNotInitialized;
»}
»if (out == nullptr) {
»»return Bc5FwPadInvalidArg;
»}
»return Bc5FwPadPastChecks(call);
}

static int KYTY_SYSV_ABI Bc5FwPadDeviceInfo([[maybe_unused]] int device_id, void* info) {
»PRINT_NAME();
»return Bc5FwPadInitAndOutput(info, "GetDeviceInfo");
}

static int KYTY_SYSV_ABI Bc5FwPadCapability([[maybe_unused]] int device_id, uint32_t* capability) {
»PRINT_NAME();
»return Bc5FwPadInitAndOutput(capability, "GetCapability");
}

static int KYTY_SYSV_ABI Bc5FwPadVersionInfo([[maybe_unused]] int handle, void* info) {
»PRINT_NAME();
»return Bc5FwPadInitAndOutput(info, "GetVersionInfo");
}

static int KYTY_SYSV_ABI Bc5FwPadExtensionUnitInfo([[maybe_unused]] int handle, void* info) {
»PRINT_NAME();
»return Bc5FwPadInitAndOutput(info, "GetExtensionUnitInfo");
}

static uint64_t KYTY_SYSV_ABI Bc5FwPadIdleCount([[maybe_unused]] int user_id) {
»PRINT_NAME();
»if (!Bc5FwPadReady()) {
»»return 0;
»}
»return static_cast<uint64_t>(Bc5FwPadPastChecks("GetIdleCount"));
}

static int KYTY_SYSV_ABI Bc5FwPadControllerIdleCount(int handle, uint64_t* count) {
»PRINT_NAME();
»if (!Bc5FwPadReady()) {
»»return Bc5FwPadNotInitialized;
»}
»if (handle == 0 || count == nullptr) {
»»return Bc5FwPadInvalidArg;
»}
»return Bc5FwPadPastChecks("GetControllerIdleCount");
}

static int KYTY_SYSV_ABI Bc5FwPadActiveTime([[maybe_unused]] int handle, [[maybe_unused]] int type, uint64_t* active_time) {
»PRINT_NAME();
»if (!Bc5FwPadReady()) {
»»return Bc5FwPadNotInitialized;
»}
»if (active_time == nullptr) {
»»return Bc5FwPadInvalidArg;
»}
»*active_time = 0;
»return Bc5FwPadPastChecks("GetActiveTime");
}

static int KYTY_SYSV_ABI Bc5FwPadPs4BcVibrationMode([[maybe_unused]] uint8_t mode) {
»PRINT_NAME();
»if (!Bc5FwPadReady()) {
»»return Bc5FwPadNotInitialized;
»}
»return Bc5FwPadPastChecks("SetPS4BcVibrationMode");
}

static int KYTY_SYSV_ABI Bc5FwPadHistory([[maybe_unused]] int handle, [[maybe_unused]] void* data, uint32_t size) {
»PRINT_NAME();
»if (!Bc5FwPadReady()) {
»»return Bc5FwPadNotInitialized;
»}
»if (size != Bc5FwPadHistoryBytes) {
»»return Bc5FwPadInvalidArg;
»}
»return Bc5FwPadPastChecks("ReadHistory");
}

static int KYTY_SYSV_ABI Bc5FwPadOpenExt2([[maybe_unused]] int user_id, int param_size, const void* param) {
»PRINT_NAME();
»if (!Bc5FwPadReady()) {
»»return Bc5FwPadNotInitialized;
»}
»if (param_size != Bc5FwPadOpenExt2Bytes || param == nullptr) {
»»return Bc5FwPadInvalidArg;
»}
»return Bc5FwPadPastChecks("OpenExt2");
}

static int KYTY_SYSV_ABI Bc5FwPadReadStateExt(int handle, void* data) {
»PRINT_NAME();
»if (!Bc5FwPadKnown(handle)) {
»»return Bc5FwPadInvalidHandle;
»}
»if (data == nullptr) {
»»return Bc5FwPadInvalidArg;
»}
»return Bc5FwPadPastChecks("ReadStateExt");
}

static int KYTY_SYSV_ABI Bc5FwPadDeviceId(int handle, int32_t* device_id) {
»PRINT_NAME();
»if (!Bc5FwPadReady()) {
»»return Bc5FwPadNotInitialized;
»}
»if (device_id == nullptr) {
»»return Bc5FwPadInvalidArg;
»}
»*device_id = -1;
»if (!Bc5FwPadKnown(handle)) {
»»return Bc5FwPadInvalidHandle;
»}
»return Bc5FwPadPastChecks("GetDeviceId");
}

// "queries"
static int KYTY_SYSV_ABI Bc5FwPadMotionTimerUnit(int handle, float* unit) {
»PRINT_NAME();
»if (!Bc5FwPadReady()) {
»»return Bc5FwPadNotInitialized;
»}
»if (unit == nullptr) {
»»return Bc5FwPadInvalidArg;
»}
»*unit = 0.0f;
»return Bc5FwPadKnown(handle) ? Bc5FwPadNotConnected : Bc5FwPadInvalidHandle;
}

static int KYTY_SYSV_ABI Bc5FwPadMotionSensorPosition(int handle, void* position) {
»PRINT_NAME();
»if (!Bc5FwPadReady()) {
»»return Bc5FwPadNotInitialized;
»}
»if (position == nullptr) {
»»return Bc5FwPadInvalidArg;
»}
»return Bc5FwPadKnown(handle) ? Bc5FwPadNotConnected : Bc5FwPadInvalidHandle;
}

static int KYTY_SYSV_ABI Bc5FwPadSphereRadius([[maybe_unused]] int handle, float* radius) {
»PRINT_NAME();
»if (!Bc5FwPadReady()) {
»»return Bc5FwPadNotInitialized;
»}
»if (radius == nullptr) {
»»return Bc5FwPadInvalidArg;
»}
»return Bc5FwPadInvalidHandle; // no special-port handle here (see above)
}

static int KYTY_SYSV_ABI Bc5FwPadBluetoothAddress(int handle, uint64_t* address) {
»PRINT_NAME();
»if (!Bc5FwPadReady()) {
»»return Bc5FwPadNotInitialized;
»}
»if (address == nullptr) {
»»return Bc5FwPadInvalidArg;
»}
»return Bc5FwPadKnown(handle) ? Bc5FwPadNotConnected : Bc5FwPadInvalidHandle;
}

static int KYTY_SYSV_ABI Bc5FwPadLeonardoUniqueData([[maybe_unused]] int handle, const void* data, void* unique_data) {
»PRINT_NAME();
»if (!Bc5FwPadReady()) {
»»return Bc5FwPadNotInitialized;
»}
»if (data == nullptr || unique_data == nullptr) {
»»return Bc5FwPadInvalidArg;
»}
»std::memset(unique_data, 0, Bc5FwPadLeonardoBytes);
»return Bc5FwPadInvalidHandle; // the DualSense is not the Access controller
}
// ---- end of experiment 0405's fw pad block ----

""")

EDITS = (
    ("include <atomic>",
     "#include <cstdio>\n#include <cstdlib>\n#include <cstring>\n\nnamespace Libs {\n",
     "#include <atomic> // BC5 experiment 0405 (KYTY_BC5_FW_PAD)\n#include <cstdio>\n#include <cstdlib>\n#include <cstring>\n"
     "\nnamespace Libs {\n"),
    ("registration: scePadInit",
     "»LIB_FUNC(\"hv1luiJrqQM\", Controller::PadInit);\n",
     "»if (Bc5FwPadItems() != 0) { // BC5 experiment 0405 (KYTY_BC5_FW_PAD): scePadInit also records the init state\n"
     "»»LIB_FUNC(\"hv1luiJrqQM\", Bc5FwPadInit);\n»} else {\n"
     "»»LIB_FUNC(\"hv1luiJrqQM\", Controller::PadInit);\n»}\n"),
    ("registration: the items",
     "»LIB_FUNC(\"n3kSX62fgNo\", PadUnknownN3kSX62fgNo);\n}\n",
     "»LIB_FUNC(\"n3kSX62fgNo\", PadUnknownN3kSX62fgNo);\n"
     "»if ((Bc5FwPadItems() & BC5_FW_PAD_INFOTYPE) != 0) { // BC5 experiment 0405 (KYTY_BC5_FW_PAD \"infotype\")\n"
     "»»LIB_FUNC(\"4x5Im8pr0-4\", Bc5FwPadPortInfoByType); // scePadGetInfoByPortType\n»}\n"
     "»if ((Bc5FwPadItems() & BC5_FW_PAD_ARGCHECKS) != 0) { // BC5 experiment 0405 (KYTY_BC5_FW_PAD \"argchecks\")\n"
     "»»LIB_FUNC(\"4rS5zG7RFaM\", Bc5FwPadDeviceInfo);          // scePadGetDeviceInfo\n"
     "»»LIB_FUNC(\"qtasqbvwgV4\", Bc5FwPadCapability);          // scePadGetCapability\n"
     "»»LIB_FUNC(\"QuOaoOcSOw0\", Bc5FwPadVersionInfo);         // scePadGetVersionInfo\n"
     "»»LIB_FUNC(\"kiA9bZhbnAg\", Bc5FwPadIdleCount);           // scePadGetIdleCount\n"
     "»»LIB_FUNC(\"UxPKyWeAT7Y\", Bc5FwPadControllerIdleCount); // scePadGetControllerIdleCount\n"
     "»»LIB_FUNC(\"k0RJXTO3SbQ\", Bc5FwPadActiveTime);          // scePadGetActiveTime\n"
     "»»LIB_FUNC(\"B8Rwqqw5Ejw\", Bc5FwPadPs4BcVibrationMode);  // scePadSetPS4BcVibrationMode\n"
     "»»LIB_FUNC(\"1DmZjZAuzEM\", Bc5FwPadExtensionUnitInfo);   // scePadGetExtensionUnitInfo\n"
     "»»LIB_FUNC(\"3u4M8ck9vJM\", Bc5FwPadHistory);             // scePadReadHistory\n"
     "»»LIB_FUNC(\"71E9e6n+2R8\", Bc5FwPadOpenExt2);            // scePadOpenExt2\n"
     "»»LIB_FUNC(\"5Wf4q349s+Q\", Bc5FwPadReadStateExt);        // scePadReadStateExt\n"
     "»»LIB_FUNC(\"hDgisSGkOgw\", Bc5FwPadDeviceId);            // scePadGetDeviceId\n»}\n"
     "»if ((Bc5FwPadItems() & BC5_FW_PAD_QUERIES) != 0) { // BC5 experiment 0405 (KYTY_BC5_FW_PAD \"queries\")\n"
     "»»LIB_FUNC(\"k4+nDV9vbT0\", Bc5FwPadMotionTimerUnit);      // scePadGetMotionTimerUnit\n"
     "»»LIB_FUNC(\"WPIB7zBWxVE\", Bc5FwPadMotionSensorPosition); // scePadGetMotionSensorPosition\n"
     "»»LIB_FUNC(\"do-JDWX+zRs\", Bc5FwPadSphereRadius);         // scePadGetSphereRadius\n"
     "»»LIB_FUNC(\"Q66U8FdrMaw\", Bc5FwPadBluetoothAddress);     // scePadGetBluetoothAddress\n"
     "»»LIB_FUNC(\"d3Q+WyyvihI\", Bc5FwPadLeonardoUniqueData);   // scePadParseUniqueDataLeonardo\n»}\n"
     "}\n"),
)
BEFORE = ("#include \"libs/controller.h\"\n", "static int KYTY_SYSV_ABI PadClose(int handle) {\n")
AFTER = ("namespace LibMouse {",)
USES = (("Bc5FwPadItems()", 5), ("Bc5FwPadParse(", 2), ("Bc5FwPadPastChecks(", 11), ("Bc5FwPadReady()", 15),
        ("Bc5FwPadKnown(", 6), ("Bc5FwPadInitAndOutput(", 5), ("Bc5FwPadInit)", 1), ("g_bc5_fw_pad_initialized", 3),
        ("LIB_FUNC(\"", 52))

REL = "src/libs/libPad.cpp"
PINNED = "89a047a4f1ad39847bf76c15fa0d4c14"  # e5's libPad.cpp (E5-FILES.txt)


def balance(b):
    return (b.count(b"{") - b.count(b"}"), b.count(b"(") - b.count(b")"), b.count(b"[") - b.count(b"]"))


def md5(b):
    return hashlib.md5(b).hexdigest()


def edit(s):
    for m in MARKS:
        assert m not in s, ("the unit has the edit already", m)
    assert b"\r" not in s, "a CR in the LF unit"
    A, B = T(BLOCK_ANCHOR), T(BLOCK)
    assert balance(B) == (0, 0, 0), ("the block is not balanced", balance(B))
    assert s.count(A) == 1, ("the block's anchor", s.count(A))
    at = s.index(A)
    for b in BEFORE:
        bb = T(b)
        assert s.count(bb) == 1 and s.index(bb) < at, ("must be defined before the block, once", b, s.count(bb))
    for b in AFTER:
        bb = T(b)
        assert s.count(bb) == 1 and s.index(bb) > at, ("must come after the block, once", b, s.count(bb))
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
        assert c == n, ("helper uses", name, c, n)
    back = out
    for o, n in reversed(done):
        assert back.count(n) == 1, ("undo", n[:60])
        back = back.replace(n, o)
    assert back.count(B) == 1
    back = back.replace(B, b"")
    assert back == s, "undoing the edits does not give the input back"
    B.decode("ascii")
    for o, n in done:
        n.decode("ascii")
    assert b"\r" not in out, "a CR in the LF unit"
    # The inserted text cites AnyPS5's code only (the maintainer's rule for this group, as for decision 3's JIT item).
    for forbidden in (b"disassembl", b"FUN_", b"IDA", b"sprx", b"decompil"):
        assert forbidden not in B and all(forbidden not in n for _, n in done), ("a reference to a module reading", forbidden)
    return out


def main():
    assert len(sys.argv) == 3, __doc__
    root, outdir = sys.argv[1], sys.argv[2]
    assert os.path.abspath(root) != os.path.abspath(outdir), "the out dir must not be the tree"
    with open(os.path.join(root, REL), "rb") as f:
        s = f.read()
    for m in MARKS:
        assert m not in s, ("refused: the unit has the edit already", REL, m.decode())
    assert md5(s) == PINNED, ("refused: not the pinned input", REL, md5(s), PINNED)
    out = edit(s)
    print(f"# in:  {REL} {md5(s)}  ({len(s)} bytes, LF)", file=sys.stderr)
    dst = os.path.join(outdir, REL)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    with open(dst, "wb") as f:
        f.write(out)
    print(f"{REL} {md5(out)}")


if __name__ == "__main__":
    main()
