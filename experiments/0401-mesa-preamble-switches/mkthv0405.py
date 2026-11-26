#!/usr/bin/env python3
"""BC5 experiment 0405 (series e7 of experiment 0401), tag "thv": exp 0405 decision 4 ("=> B => B": the tables that are
compiled but never loaded are ported first, then loaded, each behind its own switch), batch 2, hardware group: three
tables in three units of the e7 input tree (= e6's sources), each ported for a console with no such device attached (no
host device is ever opened). Each switch is off by default and read once; off is today's path exactly. Libs::InitAll
loads each table when its switch is on (libs.cpp, the loader agent, not edited here):
  src/libs/libHmd.cpp        KYTY_BC5_LOAD_HMD        Libs::LibHmd::InitHmd_1              12 ported, 5 match, 120 held
  src/libs/libVrTracker.cpp  KYTY_BC5_LOAD_VRTRACKER  Libs::LibVrTracker::InitVrTracker_1  10 ported, 29 held
  src/libs/libMove.cpp       KYTY_BC5_LOAD_MOVE       Libs::LibMove::InitMove_1            11 ported
Held stubs (AnyPS5 does not implement them) are not registered while the table's switch is on, so a title's call shows
exp 0327's "stubbed import called" line; off, every NID is registered as today. No NID is added to any table.
Sources: AnyPS5 4f41f4c375f5abb487dbd184fbc150f31994d762 (GPL-2.0-only) and shadPS4 60c42b9 (GPL-2.0-or-later); each
inserted block names its files and lines. Each unit's input md5 is pinned in PINNED (one dict, so the top session can
re-pin it when it chains scripts) and asserted; a unit that has the edit already is refused; every anchor must occur
exactly once; every edit keeps braces, parentheses and brackets balanced; the inserted text is ASCII; line ends stay as
they are (all three units are LF with a UTF-8 BOM; libVrTracker.cpp has two blank lines after every line, and the
anchors match that byte for byte). After editing, the script undoes its own edits on the output and asserts that this
gives the input back byte for byte. Only the three units are written, and only when all three are done. Prints
"<relpath> <md5>" per written file.
Notes: thv0405-notes.md; CPU test: thv0405.cpp.
usage: mkthv0405.py <tree root in> <out dir>"""
import hashlib
import os
import re
import sys

PINNED = {  # input md5 of each unit (the e7 input tree; all three are base-tree files, not e5's or e6's)
    "src/libs/libHmd.cpp": "905036478f8f9336090248a532d0469f",
    "src/libs/libVrTracker.cpp": "ee30491baadb582db2df7a08cadc4ae9",
    "src/libs/libMove.cpp": "90b0765d8d601d7e7189e0b5064d180f",
}

MARKS = (b"experiment 0405", b"KYTY_BC5_LOAD_", b"Bc5Hmd", b"Bc5Vr", b"Bc5Move", b"bc5_on")


def T(text):
    """C++ text written with a visible tab ("\u00bb") for each tab of the file's indentation, as ASCII bytes."""
    return text.replace("\u00bb", "\t").encode("ascii")


def O(sep, *lines):
    """Original lines of a unit, each followed by the unit's own line separator ("\\n" or "\\n\\n\\n")."""
    return "".join(line + sep for line in lines)


def stub_edit(sep, name, params, gate):
    """A stub `static int KYTY_SYSV_ABI <name>() {` and its PRINT_NAME() line (in the unit's spacing): the stub now
    declares its parameters, and the gate lines follow PRINT_NAME(); today's `return OK; // STUBBED` stays after them."""
    old = O(sep, f"static int KYTY_SYSV_ABI {name}() {{", "\u00bbPRINT_NAME();")
    new = O(sep, f"static int KYTY_SYSV_ABI {name}({params}) {{", "\u00bbPRINT_NAME();") + gate
    return (name, old, new)


def gate(fn, var, call):
    return (f"\u00bbif ({fn}()) {{ // BC5 experiment 0405 ({var}); false when off\n"
            f"\u00bb\u00bbreturn {call};\n"
            "\u00bb}\n")


def on_line(fn, var, word, items):
    return (f"// {var}, read once; the first call prints the switch's line.\n"
            f"static bool {fn}() {{\n"
            "\u00bbstatic const bool on = [] {\n"
            f"\u00bb\u00bbconst char* e = std::getenv(\"{var}\");\n"
            "\u00bb\u00bbconst bool  v = e != nullptr && e[0] != '\\0' && !(e[0] == '0' && e[1] == '\\0');\n"
            f"\u00bb\u00bbstd::fputs(v ? \"[bc5] exp 0405: {word} port on (items: {items})\\n\"\n"
            f"\u00bb\u00bb             : \"[bc5] exp 0405: {word} port off\\n\",\n"
            "\u00bb\u00bb           stderr);\n"
            "\u00bb\u00bbstd::fflush(stderr);\n"
            "\u00bb\u00bbreturn v;\n"
            "\u00bb}();\n"
            "\u00bbreturn on;\n"
            "}\n")


def reg_edit(sep, init, fn, var):
    """A table with no held stub: the switch is read (and its line printed) at registration."""
    old = f"LIB_DEFINE({init}) {{" + sep
    new = old + f"\u00bb(void){fn}(); // BC5 experiment 0405: reads {var} once and prints its line at registration\n"
    return ("registration", old, new)


def reg_on_edit(sep, init, fn, var):
    """A table with held stubs: the switch, read once at registration, decides whether they are registered."""
    old = f"LIB_DEFINE({init}) {{" + sep
    new = old + (f"\u00bbconst bool bc5_on = {fn}(); // BC5 experiment 0405: reads {var} once, prints its line; the\n"
                 "\u00bb// held stubs below are registered only while it is off (on, exp 0327's \"stubbed import called\" shows a call)\n")
    return ("registration", old, new)


def held_runs(s, sep, init, ns, kept, n_held, n_runs):
    """The held LIB_FUNC lines of the input's LIB_DEFINE (every line whose NID is not in kept), grouped into runs of
    consecutive lines; each run is wrapped in `if (!bc5_on) { ... }`, its lines indented one tab more."""
    text = s.decode("utf-8-sig")
    head = f"LIB_DEFINE({init}) {{" + sep
    assert text.count(head) == 1, ("LIB_DEFINE", init)
    body = text[text.index(head) + len(head):]
    body = body[:body.index("}")]
    lines = [ln for ln in body.split(sep) if ln != ""]
    pat = re.compile(r'^\tLIB_FUNC\("([A-Za-z0-9+\-]{11})", ' + ns + r'::(\w+)\);$')
    parsed = []
    for ln in lines:
        m = pat.match(ln)
        assert m, ("an unexpected line in the LIB_DEFINE", init, ln)
        parsed.append((m.group(1), ln))
    nids = [n for n, _ in parsed]
    assert len(set(nids)) == len(nids), ("a NID twice", init)
    assert set(kept) <= set(nids), ("a kept NID is not in the table", init, set(kept) - set(nids))
    runs, cur = [], []
    for nid, ln in parsed:
        if nid in kept:
            if cur:
                runs.append(cur)
                cur = []
        else:
            cur.append(ln)
    if cur:
        runs.append(cur)
    assert sum(len(r) for r in runs) == n_held and len(runs) == n_runs, ("held runs", init, [len(r) for r in runs])
    edits = []
    for r in runs:
        old = "".join(ln + sep for ln in r)
        what = f"{len(r)} held stubs" if len(r) != 1 else "1 held stub"
        new = (f"\u00bbif (!bc5_on) {{ // BC5 experiment 0405: {what}, registered only while the switch is off\n"
               + "".join("\t" + ln + sep for ln in r) + "\u00bb}" + sep)
        edits.append(("held run " + r[0][11:22], old.replace("\t", "\u00bb"), new.replace("\t", "\u00bb")))
    return tuple(edits)


# =====================================================================================================================
# src/libs/libHmd.cpp (LF, one line per line)
# =====================================================================================================================
H = "\n"
HMD_ITEMS = ("Initialize Initialize315 Terminate Open Close GetDeviceInformation GetDeviceInformationByHandle "
             "InternalGetDeviceStatus GetFieldOfView Get2DEyeOffset GetInertialSensorData GetAssyError; 120 held, not registered")
HMD_KEPT = ("6biw1XHTSqQ", "BWY-qKM5hxE", "Yx+CuF11D3Q", "thDt9upZlp8", "1pxQfif1rkE", "NPQwYFqi0bs", "rU3HK9Q0r8o",
            "K4KnH0QkT2c", "s-J66ar9g50", "PPCqsD8B5uM", "d2g5Ij7EUzo", "z-RMILqP6tE",  # the 12 ported
            "1PNiQR-7L6k", "GwFVF2KkIT4", "LWQpWHOSUvk", "YiIVBPLxmfE", "LMlWs+oKHTg")  # the 5 that already match
HMD_BLOCK = r"""// ---- BC5 experiment 0405 (series e7 of experiment 0401), tag "thv": KYTY_BC5_LOAD_HMD, libSceHmd ported ----
// Exp 0405 decision 4 (the tables compiled but never loaded): this table is ported first, then loaded by Libs::InitAll when
// KYTY_BC5_LOAD_HMD is on (libs.cpp, the loader agent). No live table registers libSceHmd. In adapted form from AnyPS5
// (github.com/boykopovar/AnyPS5, GPL-2.0-only) @ 4f41f4c375f5abb487dbd184fbc150f31994d762,
// core/libs/prx/libSceHmd/Export.cpp:22-29, 81-130, 324-329, 384-386, 408-414, 436-440, 552-559, 827-832 and Hmd.hpp:11-51,
// a console with no headset attached (note docs/dev/debt/libSceHmd.md:5, :11-12: the answers follow shadPS4 with no
// headset; not measured on a PS5), and shadPS4 (GPL-2.0-or-later) @ 60c42b9, src/core/libraries/hmd/hmd.cpp:19-216,
// 418-426, 518-536, 568-572, hmd.h:15-60, hmd_error.h:6-27 and system/userservice.h:22-23 (the codes, the parameter lists,
// the device information's 32 bytes, the invalid and system users). No host device is opened.
//   Initialize and Initialize315(param): ALREADY_INITIALIZED 0x81110001 when initialized; PARAMETER_NULL 0x81110008 for a
//   null param; UNSUPPORTED_FEATURE 0x81110016 when its first field (a pointer) is set (AnyPS5's answer; shadPS4 sets up
//   distortion with it instead; TODO(verify)); else 0. Terminate: 0, or NOT_INITIALIZED 0x81110002.
//   Open(user, type, index, param): NOT_INITIALIZED; PARAMETER_INVALID 0x81110009 for a type or index other than 0, a
//   param, or the invalid (-1) or system (0xFF) user; else DEVICE_DISCONNECTED 0x81110004: no handle is ever issued.
//   Close, GetDeviceInformationByHandle, Get2DEyeOffset and GetInertialSensorData: HANDLE_INVALID 0x81110003 once
//   initialized, else NOT_INITIALIZED; nothing written. GetFieldOfView: PARAMETER_NULL for a null output first, then the
//   same. GetAssyError: PARAMETER_NULL, then DEVICE_DISCONNECTED once initialized, else NOT_INITIALIZED.
//   GetDeviceInformation(info): PARAMETER_NULL, NOT_INITIALIZED, else 32 bytes: status 2 (not detected), user -1, zeros.
//   InternalGetDeviceStatus(status): PARAMETER_NULL, else status 2 (32 bits) and 0, initialized or not.
//   InternalMmapIsConnect and the four InternalIs*Vr2d queries already give AnyPS5's answer (0, false; note :12).
// Held: the other 120 NIDs: AnyPS5 does not implement them (it throws). With the switch on they are not registered (a
// title's call shows exp 0327's "stubbed import called" line); off, they are registered as today (0).
// KYTY_BC5_LOAD_HMD: unset, empty or "0" is off (today's stubs: 0, nothing written); any other value is on. Read once;
// one stderr line at registration or at the first call.
// AnyPS5's copyright remains with its authors; GPL-2.0 as the rest of this file (AnyPS5's part is GPL-2.0-only).
static constexpr int      BC5_HMD_ERROR_ALREADY_INITIALIZED = static_cast<int>(0x81110001u);
static constexpr int      BC5_HMD_ERROR_NOT_INITIALIZED     = static_cast<int>(0x81110002u);
static constexpr int      BC5_HMD_ERROR_HANDLE_INVALID      = static_cast<int>(0x81110003u);
static constexpr int      BC5_HMD_ERROR_DEVICE_DISCONNECTED = static_cast<int>(0x81110004u);
static constexpr int      BC5_HMD_ERROR_PARAMETER_NULL      = static_cast<int>(0x81110008u);
static constexpr int      BC5_HMD_ERROR_PARAMETER_INVALID   = static_cast<int>(0x81110009u);
static constexpr int      BC5_HMD_ERROR_UNSUPPORTED_FEATURE = static_cast<int>(0x81110016u);
static constexpr uint32_t BC5_HMD_STATUS_NOT_DETECTED       = 2;    // 0 ready, 1 not ready, 2 not detected
static constexpr int32_t  BC5_HMD_USER_INVALID              = -1;   // the invalid user
static constexpr int32_t  BC5_HMD_USER_SYSTEM               = 0xFF; // the system user
static constexpr size_t   BC5_HMD_DEVICE_INFO_SIZE          = 32;   // status, user, then 24 bytes this port leaves 0

""" + on_line("Bc5HmdOn", "KYTY_BC5_LOAD_HMD", "hmd", HMD_ITEMS) + r"""
static std::atomic<bool>& Bc5HmdInitialized() {
»static std::atomic<bool> initialized {false};
»return initialized;
}

static int Bc5HmdInitialize(const void* param) {
»if (Bc5HmdInitialized().load()) {
»»return BC5_HMD_ERROR_ALREADY_INITIALIZED;
»}
»if (param == nullptr) {
»»return BC5_HMD_ERROR_PARAMETER_NULL;
»}
»uint64_t first = 0; // the parameter's first field, a pointer a title leaves null
»std::memcpy(&first, param, sizeof(first));
»if (first != 0) {
»»return BC5_HMD_ERROR_UNSUPPORTED_FEATURE;
»}
»return Bc5HmdInitialized().exchange(true) ? BC5_HMD_ERROR_ALREADY_INITIALIZED : OK;
}

static int Bc5HmdTerminate() {
»return Bc5HmdInitialized().exchange(false) ? OK : BC5_HMD_ERROR_NOT_INITIALIZED;
}

static int Bc5HmdOpen(int32_t user_id, int32_t type, int32_t index, const void* param) {
»if (!Bc5HmdInitialized().load()) {
»»return BC5_HMD_ERROR_NOT_INITIALIZED;
»}
»if (type != 0 || index != 0 || param != nullptr || user_id == BC5_HMD_USER_INVALID || user_id == BC5_HMD_USER_SYSTEM) {
»»return BC5_HMD_ERROR_PARAMETER_INVALID;
»}
»return BC5_HMD_ERROR_DEVICE_DISCONNECTED; // no headset: no handle is issued
}

// The calls that take a headset handle: none is ever issued (Bc5HmdOpen), so none is valid.
static int Bc5HmdNoHandle() {
»return Bc5HmdInitialized().load() ? BC5_HMD_ERROR_HANDLE_INVALID : BC5_HMD_ERROR_NOT_INITIALIZED;
}

static int Bc5HmdGetDeviceInformation(void* info) {
»if (info == nullptr) {
»»return BC5_HMD_ERROR_PARAMETER_NULL;
»}
»if (!Bc5HmdInitialized().load()) {
»»return BC5_HMD_ERROR_NOT_INITIALIZED;
»}
»uint8_t        out[BC5_HMD_DEVICE_INFO_SIZE] = {};
»const uint32_t status                        = BC5_HMD_STATUS_NOT_DETECTED;
»const int32_t  user                          = BC5_HMD_USER_INVALID;
»std::memcpy(out, &status, sizeof(status));
»std::memcpy(out + sizeof(status), &user, sizeof(user));
»std::memcpy(info, out, sizeof(out));
»return OK;
}

static int Bc5HmdGetDeviceStatus(void* status) {
»if (status == nullptr) {
»»return BC5_HMD_ERROR_PARAMETER_NULL;
»}
»const uint32_t value = BC5_HMD_STATUS_NOT_DETECTED;
»std::memcpy(status, &value, sizeof(value));
»return OK;
}

static int Bc5HmdGetFieldOfView(const void* field_of_view) {
»if (field_of_view == nullptr) {
»»return BC5_HMD_ERROR_PARAMETER_NULL;
»}
»return Bc5HmdNoHandle();
}

static int Bc5HmdGetAssyError(const void* data) {
»if (data == nullptr) {
»»return BC5_HMD_ERROR_PARAMETER_NULL;
»}
»return Bc5HmdInitialized().load() ? BC5_HMD_ERROR_DEVICE_DISCONNECTED : BC5_HMD_ERROR_NOT_INITIALIZED;
}
// ---- end of BC5 experiment 0405 (KYTY_BC5_LOAD_HMD) ----

"""
HMD_V = "KYTY_BC5_LOAD_HMD"
HMD_STUBS = (
    ("sceHmdClose", "int32_t /*handle*/", "Bc5HmdNoHandle()"),
    ("sceHmdGet2DEyeOffset", "int32_t /*handle*/, void* /*left*/, void* /*right*/", "Bc5HmdNoHandle()"),
    ("sceHmdGetAssyError", "void* data", "Bc5HmdGetAssyError(data)"),
    ("sceHmdGetDeviceInformation", "void* info", "Bc5HmdGetDeviceInformation(info)"),
    ("sceHmdGetDeviceInformationByHandle", "int32_t /*handle*/, void* /*info*/", "Bc5HmdNoHandle()"),
    ("sceHmdGetFieldOfView", "int32_t /*handle*/, void* field_of_view", "Bc5HmdGetFieldOfView(field_of_view)"),
    ("sceHmdGetInertialSensorData", "int32_t /*handle*/, void* /*data*/, uint32_t /*count*/", "Bc5HmdNoHandle()"),
    ("sceHmdInitialize", "const void* param", "Bc5HmdInitialize(param)"),
    ("sceHmdInitialize315", "const void* param", "Bc5HmdInitialize(param)"),
    ("sceHmdInternalGetDeviceStatus", "void* status", "Bc5HmdGetDeviceStatus(status)"),
    ("sceHmdOpen", "int32_t user_id, int32_t type, int32_t index, const void* param", "Bc5HmdOpen(user_id, type, index, param)"),
    ("sceHmdTerminate", "", "Bc5HmdTerminate()"),
)


def hmd_edits(s):
    return ((("includes", "#include <common/abi.h>" + H,
              "#include <common/abi.h>" + H + H +
              "#include <atomic> // BC5 experiment 0405 (KYTY_BC5_LOAD_HMD): these includes\n"
              "#include <cstddef>\n"
              "#include <cstdint>\n"
              "#include <cstdio>\n"
              "#include <cstdlib>\n"
              "#include <cstring>\n"),)
            + tuple(stub_edit(H, n, p, gate("Bc5HmdOn", HMD_V, c)) for n, p, c in HMD_STUBS)
            + (reg_on_edit(H, "InitHmd_1", "Bc5HmdOn", HMD_V),)
            + held_runs(s, H, "InitHmd_1", "LibHmd", HMD_KEPT, 120, 5))


HMD_BLOCKS = (("static int KYTY_SYSV_ABI sceHmdClose() {" + H, HMD_BLOCK),)
HMD_USES = (("Bc5HmdOn()", 14), ("Bc5HmdNoHandle()", 6), ("LIB_FUNC(", 137), ("// STUBBED", 137), ("if (!bc5_on)", 5),
            ("TODO(verify)", 1))

# =====================================================================================================================
# src/libs/libVrTracker.cpp (LF, two blank lines after every line)
# =====================================================================================================================
VS = "\n\n\n"
VR_ITEMS = ("QueryMemory Init Term RegisterDevice RegisterDevice2 RegisterDeviceInternal UnregisterDevice Recalibrate "
            "SetDurationUntilStatusNotTracking GpuWaitAndCpuProcess; 29 held, not registered")
VR_KEPT = ("24kDA+A0Ox0", "ARhgpXvwoR0", "QkRl7pART9M", "K7yhYrsIBPc", "EUCaQtXXYNI", "sIh8GwcevaQ", "ufexf4aNiwg",
           "qBjnR0HtMYI", "IBv4P3q1pQ0", "Q8skQqEwn5c")
VR_BLOCK = r"""// ---- BC5 experiment 0405 (series e7 of experiment 0401), tag "thv": KYTY_BC5_LOAD_VRTRACKER, libSceVrTracker ported ----
// Exp 0405 decision 4 (the tables compiled but never loaded): this table is ported first, then loaded by Libs::InitAll when
// KYTY_BC5_LOAD_VRTRACKER is on (libs.cpp, the loader agent). No live table registers libSceVrTracker. In adapted form from
// AnyPS5 (github.com/boykopovar/AnyPS5, GPL-2.0-only) @ 4f41f4c375f5abb487dbd184fbc150f31994d762,
// core/libs/prx/libSceVrTracker/Export.cpp:32-70, 94-109, 126-128, 133-170, 187-190 and 211-226 (note
// docs/dev/debt/libSceVrTracker.md:13: the calls follow shadPS4, a PS4 implementation, not measured on a PS5), and
// shadPS4 (GPL-2.0-or-later) @ 60c42b9, src/core/libraries/vr_tracker/vr_tracker.cpp:31-204, 257-265, 273-316,
// 334-346, 444-476, vr_tracker.h:16-41 and 146-201, vr_tracker_error.h:6-26 (the codes, sizes, parameter layouts and
// device types) and video_core/amdgpu/liverpool.h:36-37 (7 compute pipes a title may name, 8 queues each). No camera,
// headset or host device is opened, and nothing is submitted to the GPU.
//   QueryMemory(param, result): ARGUMENT_INVALID 0x81260806 for a null param or result, a size other than 0x40, a
//   profile other than 0 or 100, or a calibration mode out of range (headset manual only; pad, Move, gun manual or
//   automatic); else the six sizes and alignments are written at result +4 (onion 0x400000, twice that with automatic
//   Move calibration; garlic 0x3000000; work 0x1000000; each aligned to 0x10000), 0. No init needed.
//   Init(param): ALREADY_INITIALIZED 0x81260802; ARGUMENT_INVALID for a null param, a size other than 0x80, a null
//   memory block, a size or alignment other than QueryMemory's, a GPU pipe or queue out of range, or a bad calibration;
//   else 0. The memory blocks are not looked up. A 144-byte param: AnyPS5 has no answer (it throws): today's 0 is kept and
//   the tracker counts as initialized for the ported calls, one catcher line. TODO(verify).
//   AnyPS5 compares the pipe and queue signed (a negative one passes); its note says the checks follow shadPS4, whose
//   unsigned compare refuses it: shadPS4's is taken. TODO(verify).
//   Term: 0, or NOT_INIT 0x81260801; the registered handles are kept (as AnyPS5 and shadPS4 do).
//   RegisterDevice, RegisterDevice2(type, handle), RegisterDeviceInternal(type, handle, option, variant): NOT_INIT;
//   ARGUMENT_INVALID for a type outside 0-3 or an option above 4; DEVICE_ALREADY_REGISTERED 0x81260804 when the type has a
//   handle; else the handle is kept for the type, 0. UnregisterDevice(handle): NOT_INIT; ARGUMENT_INVALID for a negative
//   or unknown handle; else 0. Recalibrate(param): NOT_INIT; ARGUMENT_INVALID (null, a size other than 0x20, a type above
//   3); DEVICE_NOT_REGISTERED 0x81260803 for the headset (none is attached) or a type with no handle; else 0.
//   SetDurationUntilStatusNotTracking(type, frames): NOT_INIT; ARGUMENT_INVALID for a type outside 0-3; else 0.
//   GpuWaitAndCpuProcess: NOT_EXECUTE_GPU_SUBMIT 0x81260815 once initialized (no camera frame, no GPU submission), else
//   NOT_INIT.
// Held: the other 29 NIDs: AnyPS5 does not implement them (it throws). With the switch on they are not registered (a
// title's call shows exp 0327's "stubbed import called" line); off, they are registered as today (0).
// KYTY_BC5_LOAD_VRTRACKER: unset, empty or "0" is off (today's stubs: 0, nothing written); any other value is on. Read
// once; one stderr line at registration or at the first call.
// AnyPS5's copyright remains with its authors; GPL-2.0 as the rest of this file (AnyPS5's part is GPL-2.0-only).
static constexpr int      BC5_VR_ERROR_NOT_INIT                  = static_cast<int>(0x81260801u);
static constexpr int      BC5_VR_ERROR_ALREADY_INITIALIZED       = static_cast<int>(0x81260802u);
static constexpr int      BC5_VR_ERROR_DEVICE_NOT_REGISTERED     = static_cast<int>(0x81260803u);
static constexpr int      BC5_VR_ERROR_DEVICE_ALREADY_REGISTERED = static_cast<int>(0x81260804u);
static constexpr int      BC5_VR_ERROR_ARGUMENT_INVALID          = static_cast<int>(0x81260806u);
static constexpr int      BC5_VR_ERROR_NOT_EXECUTE_GPU_SUBMIT    = static_cast<int>(0x81260815u);
static constexpr uint32_t BC5_VR_ALIGNMENT                       = 0x10000;
static constexpr uint32_t BC5_VR_ONION_SIZE                      = 0x400000; // twice this with automatic Move calibration
static constexpr uint32_t BC5_VR_GARLIC_SIZE                     = 0x3000000;
static constexpr uint32_t BC5_VR_WORK_SIZE                       = 0x1000000;
static constexpr uint32_t BC5_VR_PIPES                           = 7; // the pipes a title may name
static constexpr uint32_t BC5_VR_QUEUES                          = 8; // queues per pipe
static constexpr uint32_t BC5_VR_DEVICE_HEADSET                  = 0; // device types: 0 headset, 1 pad, 2 Move, 3 gun
static constexpr uint32_t BC5_VR_DEVICE_LAST                     = 3;
static constexpr int32_t  BC5_VR_OPTION_LAST                     = 4; // RegisterDeviceInternal's third argument
static constexpr uint32_t BC5_VR_MANUAL                          = 0; // calibration modes
static constexpr uint32_t BC5_VR_AUTOMATIC                       = 1;
static constexpr uint32_t BC5_VR_PROFILE_A                       = 0; // the two profiles
static constexpr uint32_t BC5_VR_PROFILE_B                       = 100;
static constexpr uint32_t BC5_VR_INIT_SIZE_LARGE                 = 144; // AnyPS5 does not implement this size

// The parameter layouts (shadPS4 vr_tracker.h:146-201), in our own names.
struct Bc5VrCalibration {
»uint32_t headset;
»uint32_t pad;
»uint32_t move;
»uint32_t gun;
»uint32_t reserved[4];
};

struct Bc5VrQueryParam {
»uint32_t         size;
»uint32_t         profile;
»uint32_t         reserved[6];
»Bc5VrCalibration calibration;
};

struct Bc5VrQueryResult {
»uint32_t size;
»uint32_t onion_size;
»uint32_t onion_alignment;
»uint32_t garlic_size;
»uint32_t garlic_alignment;
»uint32_t work_size;
»uint32_t work_alignment;
»uint32_t reserved[9];
};

struct Bc5VrInitParam {
»uint32_t         size;
»uint32_t         profile;
»uint32_t         execution_mode;
»int32_t          thread_priority[4]; // headset, pad, Move, gun
»int32_t          reserved;
»uint64_t         cpu_mask;
»Bc5VrCalibration calibration;
»uint64_t         onion;
»uint32_t         onion_size;
»uint32_t         onion_alignment;
»uint64_t         garlic;
»uint32_t         garlic_size;
»uint32_t         garlic_alignment;
»uint64_t         work;
»uint32_t         work_size;
»uint32_t         work_alignment;
»int32_t          gpu_pipe;
»int32_t          gpu_queue;
};

struct Bc5VrRecalibrateParam {
»uint32_t size;
»uint32_t device_type;
»uint32_t calibration_type;
»uint32_t reserved[5];
};

static_assert(sizeof(Bc5VrCalibration) == 0x20 && sizeof(Bc5VrQueryParam) == 0x40 && sizeof(Bc5VrQueryResult) == 0x40);
static_assert(offsetof(Bc5VrQueryParam, calibration) == 0x20 && offsetof(Bc5VrQueryResult, onion_size) == 4);
static_assert(sizeof(Bc5VrInitParam) == 0x80 && offsetof(Bc5VrInitParam, calibration) == 0x28);
static_assert(offsetof(Bc5VrInitParam, onion) == 0x48 && offsetof(Bc5VrInitParam, garlic) == 0x58);
static_assert(offsetof(Bc5VrInitParam, work) == 0x68 && offsetof(Bc5VrInitParam, gpu_pipe) == 0x78);
static_assert(sizeof(Bc5VrRecalibrateParam) == 0x20);

""" + on_line("Bc5VrOn", "KYTY_BC5_LOAD_VRTRACKER", "vrtracker", VR_ITEMS) + r"""
struct Bc5VrState {
»std::atomic<bool> initialized {false};
»std::mutex        mutex;                                                // guards devices
»int32_t           devices[BC5_VR_DEVICE_LAST + 1] = {-1, -1, -1, -1}; // the handle registered per device type
»std::atomic<bool> large_init_seen {false};
};

static Bc5VrState& Bc5Vr() {
»static Bc5VrState state;
»return state;
}

static bool Bc5VrCalibrationValid(const Bc5VrCalibration& c) {
»return c.headset <= BC5_VR_MANUAL && c.pad <= BC5_VR_AUTOMATIC && c.move <= BC5_VR_AUTOMATIC && c.gun <= BC5_VR_AUTOMATIC;
}

static uint32_t Bc5VrOnionSize(const Bc5VrCalibration& c) {
»return c.move == BC5_VR_AUTOMATIC ? BC5_VR_ONION_SIZE * 2 : BC5_VR_ONION_SIZE;
}

// A parameter's first field, its size; read before anything else, as the library does.
static uint32_t Bc5VrSize(const void* param) {
»uint32_t size = 0;
»std::memcpy(&size, param, sizeof(size));
»return size;
}

static int Bc5VrQueryMemory(const void* param, void* result) {
»if (param == nullptr || result == nullptr || Bc5VrSize(param) != sizeof(Bc5VrQueryParam)) {
»»return BC5_VR_ERROR_ARGUMENT_INVALID;
»}
»Bc5VrQueryParam in {};
»std::memcpy(&in, param, sizeof(in));
»if ((in.profile != BC5_VR_PROFILE_A && in.profile != BC5_VR_PROFILE_B) || !Bc5VrCalibrationValid(in.calibration)) {
»»return BC5_VR_ERROR_ARGUMENT_INVALID;
»}
»const uint32_t sizes[6] = {Bc5VrOnionSize(in.calibration), BC5_VR_ALIGNMENT, BC5_VR_GARLIC_SIZE,
»                           BC5_VR_ALIGNMENT,                BC5_VR_WORK_SIZE, BC5_VR_ALIGNMENT};
»std::memcpy(static_cast<uint8_t*>(result) + offsetof(Bc5VrQueryResult, onion_size), sizes, sizeof(sizes));
»return OK;
}

static int Bc5VrInit(const void* param) {
»auto& vr       = Bc5Vr();
»bool  expected = false;
»if (vr.initialized.load()) {
»»return BC5_VR_ERROR_ALREADY_INITIALIZED;
»}
»if (param != nullptr && Bc5VrSize(param) == BC5_VR_INIT_SIZE_LARGE) {
»»if (!vr.large_init_seen.exchange(true)) {
»»»std::fputs("[bc5] exp 0405: vrtracker Init with a 144-byte parameter: AnyPS5 has no answer; today's 0 kept, the "
»»»           "tracker marked initialized for the ported calls\n",
»»»           stderr);
»»»std::fflush(stderr);
»»}
»»return vr.initialized.compare_exchange_strong(expected, true) ? OK : BC5_VR_ERROR_ALREADY_INITIALIZED;
»}
»if (param == nullptr || Bc5VrSize(param) != sizeof(Bc5VrInitParam)) {
»»return BC5_VR_ERROR_ARGUMENT_INVALID;
»}
»Bc5VrInitParam in {};
»std::memcpy(&in, param, sizeof(in));
»if (in.garlic == 0 || in.garlic_alignment != BC5_VR_ALIGNMENT || in.garlic_size != BC5_VR_GARLIC_SIZE || in.onion == 0 ||
»    in.onion_alignment != BC5_VR_ALIGNMENT || in.onion_size != Bc5VrOnionSize(in.calibration) || in.work == 0 ||
»    in.work_alignment != BC5_VR_ALIGNMENT || in.work_size != BC5_VR_WORK_SIZE ||
»    static_cast<uint32_t>(in.gpu_pipe) >= BC5_VR_PIPES || static_cast<uint32_t>(in.gpu_queue) >= BC5_VR_QUEUES ||
»    !Bc5VrCalibrationValid(in.calibration)) {
»»return BC5_VR_ERROR_ARGUMENT_INVALID;
»}
»return vr.initialized.compare_exchange_strong(expected, true) ? OK : BC5_VR_ERROR_ALREADY_INITIALIZED;
}

static int Bc5VrTerm() {
»bool expected = true;
»return Bc5Vr().initialized.compare_exchange_strong(expected, false) ? OK : BC5_VR_ERROR_NOT_INIT;
}

static int Bc5VrRegister(int32_t device_type, int32_t handle, int32_t option) {
»auto& vr = Bc5Vr();
»if (!vr.initialized.load()) {
»»return BC5_VR_ERROR_NOT_INIT;
»}
»const auto type = static_cast<uint32_t>(device_type);
»if (type > BC5_VR_DEVICE_LAST || option > BC5_VR_OPTION_LAST) {
»»return BC5_VR_ERROR_ARGUMENT_INVALID;
»}
»std::lock_guard<std::mutex> lock(vr.mutex);
»if (vr.devices[type] != -1) {
»»return BC5_VR_ERROR_DEVICE_ALREADY_REGISTERED;
»}
»vr.devices[type] = handle;
»return OK;
}

static int Bc5VrUnregister(int32_t handle) {
»auto& vr = Bc5Vr();
»if (!vr.initialized.load()) {
»»return BC5_VR_ERROR_NOT_INIT;
»}
»if (handle < 0) {
»»return BC5_VR_ERROR_ARGUMENT_INVALID;
»}
»std::lock_guard<std::mutex> lock(vr.mutex);
»for (auto& registered: vr.devices) {
»»if (registered == handle) {
»»»registered = -1;
»»»return OK;
»»}
»}
»return BC5_VR_ERROR_ARGUMENT_INVALID;
}

static int Bc5VrRecalibrate(const void* param) {
»auto& vr = Bc5Vr();
»if (!vr.initialized.load()) {
»»return BC5_VR_ERROR_NOT_INIT;
»}
»if (param == nullptr || Bc5VrSize(param) != sizeof(Bc5VrRecalibrateParam)) {
»»return BC5_VR_ERROR_ARGUMENT_INVALID;
»}
»Bc5VrRecalibrateParam in {};
»std::memcpy(&in, param, sizeof(in));
»if (in.device_type > BC5_VR_DEVICE_LAST) {
»»return BC5_VR_ERROR_ARGUMENT_INVALID;
»}
»if (in.device_type == BC5_VR_DEVICE_HEADSET) {
»»return BC5_VR_ERROR_DEVICE_NOT_REGISTERED; // no headset is attached
»}
»std::lock_guard<std::mutex> lock(vr.mutex);
»return vr.devices[in.device_type] == -1 ? BC5_VR_ERROR_DEVICE_NOT_REGISTERED : OK;
}

static int Bc5VrSetDuration(int32_t device_type) {
»if (!Bc5Vr().initialized.load()) {
»»return BC5_VR_ERROR_NOT_INIT;
»}
»return static_cast<uint32_t>(device_type) > BC5_VR_DEVICE_LAST ? BC5_VR_ERROR_ARGUMENT_INVALID : OK;
}

static int Bc5VrGpuWaitAndCpuProcess() {
»return Bc5Vr().initialized.load() ? BC5_VR_ERROR_NOT_EXECUTE_GPU_SUBMIT : BC5_VR_ERROR_NOT_INIT;
}
// ---- end of BC5 experiment 0405 (KYTY_BC5_LOAD_VRTRACKER) ----

"""
VR_V = "KYTY_BC5_LOAD_VRTRACKER"
VR_STUBS = (
    ("sceVrTrackerRegisterDevice2", "int32_t device_type, int32_t handle", "Bc5VrRegister(device_type, handle, -1)"),
    ("sceVrTrackerGpuWaitAndCpuProcess", "", "Bc5VrGpuWaitAndCpuProcess()"),
    ("sceVrTrackerInit", "const void* param", "Bc5VrInit(param)"),
    ("sceVrTrackerQueryMemory", "const void* param, void* result", "Bc5VrQueryMemory(param, result)"),
    ("sceVrTrackerRecalibrate", "const void* param", "Bc5VrRecalibrate(param)"),
    ("sceVrTrackerRegisterDevice", "int32_t device_type, int32_t handle", "Bc5VrRegister(device_type, handle, -1)"),
    ("sceVrTrackerRegisterDeviceInternal", "int32_t device_type, int32_t handle, int32_t option, int32_t /*variant*/",
     "Bc5VrRegister(device_type, handle, option)"),
    ("sceVrTrackerSetDurationUntilStatusNotTracking", "int32_t device_type, uint32_t /*camera_frames*/",
     "Bc5VrSetDuration(device_type)"),
    ("sceVrTrackerTerm", "", "Bc5VrTerm()"),
    ("sceVrTrackerUnregisterDevice", "int32_t handle", "Bc5VrUnregister(handle)"),
)


def vr_edits(s):
    return ((("includes", "#include <common/abi.h>\n",
              "#include <common/abi.h>\n"
              "\n"
              "#include <atomic> // BC5 experiment 0405 (KYTY_BC5_LOAD_VRTRACKER): these includes\n"
              "#include <cstddef>\n"
              "#include <cstdint>\n"
              "#include <cstdio>\n"
              "#include <cstdlib>\n"
              "#include <cstring>\n"
              "#include <mutex>\n"),)
            + tuple(stub_edit(VS, n, p, gate("Bc5VrOn", VR_V, c)) for n, p, c in VR_STUBS)
            + (reg_on_edit(VS, "InitVrTracker_1", "Bc5VrOn", VR_V),)
            + held_runs(s, VS, "InitVrTracker_1", "LibVrTracker", VR_KEPT, 29, 5))


VR_BLOCKS = (("static int KYTY_SYSV_ABI sceVrTrackerRegisterDevice2() {" + VS, VR_BLOCK),)
VR_USES = (("Bc5VrOn()", 12), ("Bc5VrRegister(", 4), ("LIB_FUNC(", 39), ("// STUBBED", 39), ("if (!bc5_on)", 5),
           ("TODO(verify)", 2))

# =====================================================================================================================
# src/libs/libMove.cpp (LF, one line per line)
# =====================================================================================================================
M = "\n"
MOVE_ITEMS = ("Init Term Open Close GetDeviceInfo GetExtensionPortInfo ReadStateLatest ReadStateRecent SetVibration "
              "SetLightSphere ResetLightSphere")
MOVE_BLOCK = r"""// ---- BC5 experiment 0405 (series e7 of experiment 0401), tag "thv": KYTY_BC5_LOAD_MOVE, libSceMove ported ----
// Exp 0405 decision 4 (the tables compiled but never loaded): this table is ported first, then loaded by Libs::InitAll when
// KYTY_BC5_LOAD_MOVE is on (libs.cpp, the loader agent). No live table registers libSceMove. In adapted form from AnyPS5
// (github.com/boykopovar/AnyPS5, GPL-2.0-only) @ 4f41f4c375f5abb487dbd184fbc150f31994d762,
// core/libs/prx/libSceMove/Export.cpp:14-125, a console with no PS Move controller (note docs/dev/debt/libSceMove.md:5-7:
// "the native module confirms" the initialization errors, the answer 1 with nothing written, INVALID_HANDLE and the order
// initialization, then arguments, then handle; and the SDK rule of ReadStateRecent: a reading of the console module, exp
// 0405 decision 1), and shadPS4 (GPL-2.0-or-later) @ 60c42b9, src/core/libraries/move/move.cpp:15-121 and
// move_error.h:8-16 (the codes, the handle numbers and the parameter lists). No host device is opened.
//   Init: ALREADY_INIT 0x80EE0002 when initialized, else 0. Term: NOT_INIT 0x80EE0001 when not, else 0; every open handle
//   is closed (the handle numbers go on counting).
//   Open(user, type, index): NOT_INIT; ALREADY_OPENED 0x80EE0007 for a type and index already open; else a new handle,
//   0x30B0100 and then every 0x100 (shadPS4 move.cpp:30-33). Only the initial user is ported (1000, our UserService's
//   GetInitialUser, libs/libUserService.cpp:161-169); another user's answer is not known (AnyPS5 throws): today's 0, no
//   handle opened, one catcher line. TODO(verify). The console's limit of eight slots (note :6) is not implemented by
//   AnyPS5 and not ported.
//   Close(handle): NOT_INIT; 0 for an open handle, else INVALID_HANDLE 0x80EE0004.
//   GetDeviceInfo, GetExtensionPortInfo, ReadStateLatest(handle, out) and ReadStateRecent(handle, time, out, count):
//   NOT_INIT, then INVALID_ARG 0x80EE0003 (a null out; for ReadStateRecent a negative time, a null count, or a null out
//   from SDK 0x04000000 on), then INVALID_HANDLE, else 1 (no controller connected) with nothing written.
//   SetVibration(handle, motor) and SetLightSphere(handle, red, green, blue): NOT_INIT, INVALID_HANDLE, else 1.
//   ResetLightSphere(handle): NOT_INIT, INVALID_HANDLE, else 0 (no controller ioctl is made; note :5).
//   The SDK version is the one our sceKernelGetCompiledSdkVersion gives (libs/bc5LleAgc.cpp, exp 0336: the process
//   parameter's u64 at +0x10, its high half, else its low half, when within 0x01000000-0x1FFFFFFF; else 0x0A000000);
//   AnyPS5 reads the 32 bits at +0x10. TODO(verify): the SDK field.
// KYTY_BC5_LOAD_MOVE: unset, empty or "0" is off (today's stubs: 0, nothing written); any other value is on. Read once;
// one stderr line at registration or at the first call.
// AnyPS5's copyright remains with its authors; GPL-2.0 as the rest of this file (AnyPS5's part is GPL-2.0-only).
static constexpr int      BC5_MOVE_NO_CONTROLLER          = 1;
static constexpr int      BC5_MOVE_ERROR_NOT_INIT         = static_cast<int>(0x80EE0001u);
static constexpr int      BC5_MOVE_ERROR_ALREADY_INIT     = static_cast<int>(0x80EE0002u);
static constexpr int      BC5_MOVE_ERROR_INVALID_ARG      = static_cast<int>(0x80EE0003u);
static constexpr int      BC5_MOVE_ERROR_INVALID_HANDLE   = static_cast<int>(0x80EE0004u);
static constexpr int      BC5_MOVE_ERROR_ALREADY_OPENED   = static_cast<int>(0x80EE0007u);
static constexpr uint32_t BC5_MOVE_FIRST_HANDLE           = 0x30B0100u;
static constexpr uint32_t BC5_MOVE_HANDLE_STEP            = 0x100u;
static constexpr int32_t  BC5_MOVE_INITIAL_USER           = 1000;        // libs/libUserService.cpp: GetInitialUser
static constexpr uint32_t BC5_MOVE_LAST_SDK_NULL_ALLOWED  = 0x03FFFFFFu; // ReadStateRecent's null out up to this SDK

""" + on_line("Bc5MoveOn", "KYTY_BC5_LOAD_MOVE", "move", MOVE_ITEMS) + r"""
// The title's SDK version, as our sceKernelGetCompiledSdkVersion gives it (libs/bc5LleAgc.cpp, exp 0336), read once.
static uint32_t Bc5MoveSdkVersion() {
»static const uint32_t v = [] {
»»uint32_t       out  = 0x0A000000u;
»»const uint64_t pp   = Loader::Bc5ProcParam();
»»uint64_t       size = 0;
»»uint64_t       sdk  = 0;
»»if (pp != 0) {
»»»std::memcpy(&size, reinterpret_cast<const void*>(pp), 8);
»»»if (size >= 0x18) {
»»»»std::memcpy(&sdk, reinterpret_cast<const void*>(pp + 0x10), 8);
»»»}
»»}
»»const auto hi   = static_cast<uint32_t>(sdk >> 32u);
»»const auto lo   = static_cast<uint32_t>(sdk);
»»const auto cand = hi != 0 ? hi : lo;
»»if (cand >= 0x01000000u && cand < 0x20000000u) {
»»»out = cand;
»»}
»»return out;
»}();
»return v;
}

struct Bc5MoveSlot {
»int32_t type;
»int32_t index;
};

struct Bc5MoveState {
»std::mutex                               mutex;
»bool                                     initialized = false;
»uint32_t                                 next_handle = BC5_MOVE_FIRST_HANDLE;
»std::unordered_map<int32_t, Bc5MoveSlot> open; // handle -> its type and index
»bool                                     other_user_seen = false;
};

static Bc5MoveState& Bc5Move() {
»static Bc5MoveState state;
»return state;
}

static int Bc5MoveInit() {
»auto&                       m = Bc5Move();
»std::lock_guard<std::mutex> lock(m.mutex);
»if (m.initialized) {
»»return BC5_MOVE_ERROR_ALREADY_INIT;
»}
»m.initialized = true;
»return OK;
}

static int Bc5MoveTerm() {
»auto&                       m = Bc5Move();
»std::lock_guard<std::mutex> lock(m.mutex);
»if (!m.initialized) {
»»return BC5_MOVE_ERROR_NOT_INIT;
»}
»m.initialized = false;
»m.open.clear();
»return OK;
}

static int Bc5MoveOpen(int32_t user_id, int32_t type, int32_t index) {
»auto&                       m = Bc5Move();
»std::lock_guard<std::mutex> lock(m.mutex);
»if (!m.initialized) {
»»return BC5_MOVE_ERROR_NOT_INIT;
»}
»if (user_id != BC5_MOVE_INITIAL_USER) { // AnyPS5 has no answer for another user: today's 0, no handle opened
»»if (!m.other_user_seen) {
»»»m.other_user_seen = true;
»»»std::fputs("[bc5] exp 0405: move Open for a user other than the initial user: AnyPS5 has no answer; today's 0 kept, "
»»»           "no handle opened\n",
»»»           stderr);
»»»std::fflush(stderr);
»»}
»»return OK;
»}
»for (const auto& entry: m.open) {
»»if (entry.second.type == type && entry.second.index == index) {
»»»return BC5_MOVE_ERROR_ALREADY_OPENED;
»»}
»}
»const auto handle = static_cast<int32_t>(m.next_handle);
»m.next_handle += BC5_MOVE_HANDLE_STEP;
»m.open.emplace(handle, Bc5MoveSlot {type, index});
»return handle;
}

static int Bc5MoveClose(int32_t handle) {
»auto&                       m = Bc5Move();
»std::lock_guard<std::mutex> lock(m.mutex);
»if (!m.initialized) {
»»return BC5_MOVE_ERROR_NOT_INIT;
»}
»return m.open.erase(handle) != 0 ? OK : BC5_MOVE_ERROR_INVALID_HANDLE;
}

// Initialization, then the arguments, then the handle (note :5).
static int Bc5MoveCheck(int32_t handle, bool arguments_valid) {
»auto&                       m = Bc5Move();
»std::lock_guard<std::mutex> lock(m.mutex);
»if (!m.initialized) {
»»return BC5_MOVE_ERROR_NOT_INIT;
»}
»if (!arguments_valid) {
»»return BC5_MOVE_ERROR_INVALID_ARG;
»}
»return m.open.count(handle) != 0 ? OK : BC5_MOVE_ERROR_INVALID_HANDLE;
}

static int Bc5MoveQuery(int32_t handle, const void* out) {
»const int r = Bc5MoveCheck(handle, out != nullptr);
»return r != OK ? r : BC5_MOVE_NO_CONTROLLER;
}

static int Bc5MoveReadRecent(int32_t handle, int64_t time, const void* out, const int32_t* count) {
»const bool out_valid = out != nullptr || Bc5MoveSdkVersion() <= BC5_MOVE_LAST_SDK_NULL_ALLOWED;
»const int  r         = Bc5MoveCheck(handle, time >= 0 && out_valid && count != nullptr);
»return r != OK ? r : BC5_MOVE_NO_CONTROLLER;
}

static int Bc5MoveOutput(int32_t handle) {
»const int r = Bc5MoveCheck(handle, true);
»return r != OK ? r : BC5_MOVE_NO_CONTROLLER;
}
// ---- end of BC5 experiment 0405 (KYTY_BC5_LOAD_MOVE) ----

"""
MOVE_V = "KYTY_BC5_LOAD_MOVE"
MOVE_STUBS = (
    ("sceMoveInit", "", "Bc5MoveInit()"),
    ("sceMoveOpen", "int32_t user_id, int32_t type, int32_t index", "Bc5MoveOpen(user_id, type, index)"),
    ("sceMoveGetDeviceInfo", "int32_t handle, void* info", "Bc5MoveQuery(handle, info)"),
    ("sceMoveReadStateLatest", "int32_t handle, void* data", "Bc5MoveQuery(handle, data)"),
    ("sceMoveReadStateRecent", "int32_t handle, int64_t time, void* data, int32_t* count",
     "Bc5MoveReadRecent(handle, time, data, count)"),
    ("sceMoveGetExtensionPortInfo", "int32_t handle, void* info", "Bc5MoveQuery(handle, info)"),
    ("sceMoveSetVibration", "int32_t handle, uint8_t /*motor*/", "Bc5MoveOutput(handle)"),
    ("sceMoveSetLightSphere", "int32_t handle, uint8_t /*red*/, uint8_t /*green*/, uint8_t /*blue*/", "Bc5MoveOutput(handle)"),
    ("sceMoveResetLightSphere", "int32_t handle", "Bc5MoveCheck(handle, true)"),
    ("sceMoveClose", "int32_t handle", "Bc5MoveClose(handle)"),
    ("sceMoveTerm", "", "Bc5MoveTerm()"),
)


def move_edits(s):
    return ((("includes", "#include <common/abi.h>" + M,
              "#include <common/abi.h>" + M + M +
              "#include <cstdint> // BC5 experiment 0405 (KYTY_BC5_LOAD_MOVE): these includes and Bc5ProcParam\n"
              "#include <cstdio>\n"
              "#include <cstdlib>\n"
              "#include <cstring>\n"
              "#include <mutex>\n"
              "#include <unordered_map>\n"
              "\n"
              "namespace Loader {\n"
              "uint64_t Bc5ProcParam(); // loader/runtimeLinker.cpp: the program's process parameter, as libs/bc5LleAgc.cpp has it\n"
              "} // namespace Loader\n"),)
            + tuple(stub_edit(M, n, p, gate("Bc5MoveOn", MOVE_V, c)) for n, p, c in MOVE_STUBS)
            + (reg_edit(M, "InitMove_1", "Bc5MoveOn", MOVE_V),))


MOVE_BLOCKS = (("static int KYTY_SYSV_ABI sceMoveInit() {" + M, MOVE_BLOCK),)
MOVE_USES = (("Bc5MoveOn()", 13), ("Bc5MoveCheck(", 5), ("Bc5MoveQuery(", 4), ("Bc5ProcParam()", 2), ("LIB_FUNC(", 11),
             ("// STUBBED", 11), ("TODO(verify)", 2))

UNITS = (
    # rel, blocks (anchor, block), edits(input), the LIB_VERSION line (must come before the block), helper uses
    ("src/libs/libHmd.cpp", HMD_BLOCKS, hmd_edits, "LIB_VERSION(\"libSceHmd\", 1, \"libSceHmd\", 1, 1);", HMD_USES),
    ("src/libs/libVrTracker.cpp", VR_BLOCKS, vr_edits, "LIB_VERSION(\"libSceVrTracker\", 1, \"libSceVrTracker\", 1, 1);",
     VR_USES),
    ("src/libs/libMove.cpp", MOVE_BLOCKS, move_edits, "LIB_VERSION(\"libSceMove\", 1, \"libSceMove\", 1, 1);", MOVE_USES),
)


def balance(b):
    return (b.count(b"{") - b.count(b"}"), b.count(b"(") - b.count(b")"), b.count(b"[") - b.count(b"]"))


def md5(b):
    return hashlib.md5(b).hexdigest()


def registered(b):
    """The NIDs of the unit's LIB_DEFINE, as (nid, held-wrapped) in order."""
    text = b.decode("utf-8-sig")
    body = text[text.index("LIB_DEFINE("):]
    out, depth_held = [], False
    for ln in body.splitlines():
        if ln.startswith("\tif (!bc5_on) {"):
            depth_held = True
        elif ln == "\t}":
            depth_held = False
        m = re.search(r'LIB_FUNC\("([A-Za-z0-9+\-]{11})",', ln)
        if m:
            out.append((m.group(1), depth_held))
    return out


def edit_unit(rel, s, blocks, edits_of, version, uses):
    for m in MARKS:
        assert m not in s, ("refused: the unit has the edit already", rel, m.decode())
    assert b"\r" not in s, ("a CR in an LF unit", rel)
    assert s.startswith(b"\xef\xbb\xbf"), ("no UTF-8 BOM", rel)
    out = s
    placed = []
    vb = T(version)
    assert s.count(vb) == 1, ("LIB_VERSION", rel)
    for anchor, block in blocks:
        A, B = T(anchor), T(block)
        assert balance(B) == (0, 0, 0), ("a block is not balanced", rel, balance(B))
        assert s.count(A) == 1 and out.count(A) == 1, ("a block's anchor", rel, anchor[:60], s.count(A))
        out = out.replace(A, B + A)
        placed.append(B)
        assert out.index(B) > out.index(vb), ("the block is before the table's LIB_VERSION", rel)
        assert out.index(B) < out.index(b"LIB_DEFINE("), ("the block is after the LIB_DEFINE", rel)
    done = []
    for what, old, new in edits_of(s):
        o, n = T(old), T(new)
        assert out.count(o) == 1, ("anchor", rel, what, out.count(o))
        assert balance(o) == balance(n), ("the edit changes the balance", rel, what, balance(o), balance(n))
        out = out.replace(o, n)
        done.append((o, n))
    assert balance(out) == balance(s), ("the unit's balance changed", rel, balance(s), balance(out))
    for name, n in uses:
        c = out.count(name.encode("ascii"))
        assert c == n, ("helper uses", rel, name, c, n)
    # The registrations: the same NIDs in the same order as the input; none of them is held in the input.
    ri, ro = registered(s), registered(out)
    assert [n for n, _ in ri] == [n for n, _ in ro], ("the registered NIDs changed", rel)
    assert not any(h for _, h in ri), ("a held wrap in the input", rel)
    # Undo the edits on the output (last first), then the blocks: the input must come back byte for byte.
    back = out
    for o, n in reversed(done):
        assert back.count(n) == 1, ("undo", rel, n[:60])
        back = back.replace(n, o)
    for B in placed:
        assert back.count(B) == 1, ("undo block", rel)
        back = back.replace(B, b"")
    assert back == s, ("undoing the edits does not give the input back", rel)
    # The inserted text is ASCII, the line ends stay LF, the BOM stays.
    for B in placed:
        B.decode("ascii")
    for o, n in done:
        n.decode("ascii")
    assert b"\r" not in out, ("a CR in the LF unit", rel)
    assert out.startswith(b"\xef\xbb\xbf"), ("the BOM changed", rel)
    return out, ro


def main():
    assert len(sys.argv) == 3, __doc__
    root, outdir = sys.argv[1], sys.argv[2]
    assert os.path.abspath(root) != os.path.abspath(outdir), "the out dir must not be the tree"
    assert set(PINNED) == {u[0] for u in UNITS}
    outs = []
    for rel, blocks, edits_of, version, uses in UNITS:
        with open(os.path.join(root, rel), "rb") as f:
            s = f.read()
        for m in MARKS:
            assert m not in s, ("refused: the unit has the edit already", rel, m.decode())
        assert md5(s) == PINNED[rel], ("refused: not the pinned input", rel, md5(s), PINNED[rel])
        out, regs = edit_unit(rel, s, blocks, edits_of, version, uses)
        held = sum(1 for _, h in regs if h)
        print(f"# in:  {rel} {md5(s)}  ({len(s)} bytes, LF); {len(regs)} NIDs, {len(regs) - held} registered when on, "
              f"{held} held (registered only when off)", file=sys.stderr)
        outs.append((rel, out))
    for rel, out in outs:  # written only when all three are done
        dst = os.path.join(outdir, rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        with open(dst, "wb") as f:
            f.write(out)
        print(f"{rel} {md5(out)}")


if __name__ == "__main__":
    main()
