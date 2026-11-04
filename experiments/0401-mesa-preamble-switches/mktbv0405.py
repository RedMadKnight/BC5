#!/usr/bin/env python3
"""BC5 experiment 0405 (series e7 of experiment 0401), tag "tbv": exp 0405 decision 4 ("=> B => B": the tables that are
compiled but never loaded are ported first, then loaded, each behind its own switch), batch 2, seven CPU-only library
tables in six units of the e7 input tree (= e6's sources). Each switch is off by default and read once; off is today's
path exactly. Libs::InitAll loads each table when its switch is on (libs.cpp, tag "tl2", not edited here):
  src/libs/libVoice.cpp          KYTY_BC5_LOAD_VOICE           Libs::LibVoice::InitVoice_1
  src/libs/libScreenShot.cpp     KYTY_BC5_LOAD_SCREENSHOT      Libs::LibScreenShot::InitScreenShot_1
  src/libs/libDiscMap.cpp        KYTY_BC5_LOAD_DISCMAP         Libs::LibDiscMap::InitDiscMap_1
  src/libs/libUlobjmgr.cpp       KYTY_BC5_LOAD_ULOBJMGR        Libs::LibUlobjmgr::InitUlobjmgr_1
  src/libs/libCompanion.cpp      KYTY_BC5_LOAD_COMPANIONHTTPD  Libs::CompanionHttpd::InitCompanionHttpd_1
                                 KYTY_BC5_LOAD_COMPANIONUTIL   Libs::CompanionUtil::InitCompanionUtil_1
  src/libs/libVideoRecording.cpp KYTY_BC5_LOAD_VIDEORECORDING  Libs::LibVideoRecording::InitVideoRecording_1
Sources: AnyPS5 4f41f4c375f5abb487dbd184fbc150f31994d762 (GPL-2.0-only) and shadPS4 60c42b9 (GPL-2.0-or-later); each
inserted block names its files and lines. No NID is added to or removed from any table. Each unit's input md5 is pinned in
PINNED (one dict, so the top session can re-pin it when it chains scripts) and asserted; a unit that has the edit already
is refused; every anchor must occur exactly once; every edit keeps braces, parentheses and brackets balanced; the inserted
text is ASCII; line ends stay as they are (all six units are LF with a UTF-8 BOM; libCompanion.cpp has a blank line after
every line, libDiscMap.cpp, libUlobjmgr.cpp and libVideoRecording.cpp two; the anchors match them byte for byte). After
editing, the script undoes its own edits on the output and asserts that this gives the input back byte for byte. Only the
six units are written, and only when all six are done. Prints "<relpath> <md5>" per written file.
Notes: tbv0405-notes.md; CPU test: tbv0405.cpp.
usage: mktbv0405.py <tree root in> <out dir>"""
import hashlib
import os
import sys

PINNED = {  # input md5 of each unit (the e7 input tree; all six are base-tree files, not e5's or e6's)
    "src/libs/libVoice.cpp": "5f63709dbf1028ceaf7784d6a070f64e",
    "src/libs/libScreenShot.cpp": "cb913d120daa27f0d35702edeee71b19",
    "src/libs/libDiscMap.cpp": "e4d975b8a55da8aed19281d7c6d17b33",
    "src/libs/libUlobjmgr.cpp": "b85eafd0de28af091302a8aeeeb323c1",
    "src/libs/libCompanion.cpp": "cf8ad7a647a84ba04964eb0adfe2ab02",
    "src/libs/libVideoRecording.cpp": "e8f90a3574dcae417df52f1802515f4d",
}

MARKS = (b"experiment 0405", b"KYTY_BC5_LOAD_", b"Bc5Voice", b"Bc5ScreenShot", b"Bc5DiscMap", b"Bc5Ulobjmgr",
         b"Bc5Httpd", b"Bc5CompanionUtil", b"Bc5VideoRecording")


def T(text):
    """C++ text written with a visible tab ("\u00bb") for each tab of the file's indentation, as ASCII bytes."""
    return text.replace("\u00bb", "\t").encode("ascii")


def O(sep, *lines):
    """Original lines of a unit, each followed by the unit's own line separator ("\\n", "\\n\\n" or "\\n\\n\\n")."""
    return "".join(line + sep for line in lines)


def stub_edit(sep, what, old_sig, new_sig, gate_lines):
    """A stub: its signature line and PRINT_NAME() line (in the unit's spacing); the gate lines follow PRINT_NAME()."""
    old = O(sep, old_sig, "\u00bbPRINT_NAME();")
    new = O(sep, new_sig, "\u00bbPRINT_NAME();") + gate_lines
    return (what, old, new)


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
    old = f"LIB_DEFINE({init}) {{" + sep
    new = old + f"\u00bb(void){fn}(); // BC5 experiment 0405: reads {var} once and prints its line at registration\n"
    return ("registration", old, new)


# =====================================================================================================================
# src/libs/libVoice.cpp (LF, one line per line)
# =====================================================================================================================
V = "\n"
VOICE_ITEMS = "VADSetVersion GetResourceInfo-check; 8 held, split state with libAudio.cpp"
VOICE_BLOCK = r"""// ---- BC5 experiment 0405 (series e7 of experiment 0401), tag "tbv": KYTY_BC5_LOAD_VOICE, libSceVoice ported ----
// Exp 0405 decision 4 (the tables compiled but never loaded): this table is ported first, then loaded by Libs::InitAll when
// KYTY_BC5_LOAD_VOICE is on (libs.cpp, tag "tl2"). Split state: libSceVoice's other 16 calls are the live table
// (libs/libAudio.cpp InitAudio_1_Voice, the same key "Voice": Init, Start, Stop, End, CreatePort, DeletePort and the
// port calls). Its port table and started flag are static in that file, and it keeps no initialized flag: its Init never
// fails and no live call answers "not initialized". So here the library counts as initialized, and only what needs no
// port and no initialization mode is ported. In adapted form from AnyPS5 (github.com/boykopovar/AnyPS5, GPL-2.0-only) @
// 4f41f4c375f5abb487dbd184fbc150f31994d762, core/libs/prx/libSceVoice/Export.cpp:
//   sceVoiceVADSetVersion (:491-493): versions 0 and 1 give 0, any other INVALID_ARGUMENT 0x804E0805. Its note
//     docs/dev/debt/libSceVoice.md:14: the rule follows shadPS4; shadPS4 (GPL-2.0-or-later) @ 60c42b9,
//     src/core/libraries/voice/voice.cpp:556-563 and voice_error.h:9, gives the same.
//   sceVoiceGetResourceInfo (:374-378), its check only: a null info gives INVALID_ARGUMENT. The four limits it writes
//     depend on the initialization mode, which the live sceVoiceInit drops (libAudio.cpp VoiceInit): held, so a non-null
//     info keeps today's answer (0, nothing written).
// Held (today's 0, nothing written), split state: InitHQ (the live Init's twin: it would reset the live port table),
// PausePort, ResumePort, ResetPort, GetMuteFlag, SetMuteFlag, SetBitRate and UpdatePort (each needs the live port table;
// SetBitRate and UpdatePort also change the bitrate and volume that the live GetBitRate and GetVolume report).
// Today's answer already (0): PausePortAll, ResumePortAll and SetMuteFlagAll (their only other answer is "not
// initialized"; the all-mute flag is read only by the held GetMuteFlag), and VADAdjustment (it stores two values that
// nothing reads).
// KYTY_BC5_LOAD_VOICE: unset, empty or "0" is off (today's stubs: 0, nothing written); any other value is on. Read once;
// one stderr line at registration or at the first call.
// AnyPS5's copyright remains with its authors; GPL-2.0 as the rest of this file (AnyPS5's part is GPL-2.0-only).
static constexpr int BC5_VOICE_ERROR_ARGUMENT_INVALID = static_cast<int>(0x804E0805u);

""" + on_line("Bc5VoiceOn", "KYTY_BC5_LOAD_VOICE", "voice", VOICE_ITEMS) + r"""
static int Bc5VoiceVadSetVersion(int32_t version) {
»return (version == 0 || version == 1) ? OK : BC5_VOICE_ERROR_ARGUMENT_INVALID;
}

// sceVoiceGetResourceInfo's check; OK means that today's answer follows (the limits are held).
static int Bc5VoiceResourceInfoCheck(const void* info) {
»return info == nullptr ? BC5_VOICE_ERROR_ARGUMENT_INVALID : OK;
}
// ---- end of BC5 experiment 0405 (KYTY_BC5_LOAD_VOICE) ----

"""
VOICE_GATE = "\u00bbif (Bc5VoiceOn()) { // BC5 experiment 0405 (KYTY_BC5_LOAD_VOICE); false when off\n"
VOICE_EDITS = (
    ("includes", "#include <common/abi.h>\n",
     "#include <common/abi.h>\n"
     "\n"
     "#include <cstdint> // BC5 experiment 0405 (KYTY_BC5_LOAD_VOICE): these includes\n"
     "#include <cstdio>\n"
     "#include <cstdlib>\n"),
    stub_edit(V, "GetResourceInfo", "static int KYTY_SYSV_ABI sceVoiceGetResourceInfo() {",
              "static int KYTY_SYSV_ABI sceVoiceGetResourceInfo(void* info) {",
              "\u00bbif (Bc5VoiceOn()) { // BC5 experiment 0405 (KYTY_BC5_LOAD_VOICE); false when off. The limits are held:\n"
              "\u00bb\u00bbconst int checked = Bc5VoiceResourceInfoCheck(info); // when it passes, today's answer below\n"
              "\u00bb\u00bbif (checked != OK) {\n"
              "\u00bb\u00bb\u00bbreturn checked;\n"
              "\u00bb\u00bb}\n"
              "\u00bb}\n"),
    stub_edit(V, "VADSetVersion", "static int KYTY_SYSV_ABI sceVoiceVADSetVersion() {",
              "static int KYTY_SYSV_ABI sceVoiceVADSetVersion(int32_t version) {",
              VOICE_GATE + "\u00bb\u00bbreturn Bc5VoiceVadSetVersion(version);\n\u00bb}\n"),
    reg_edit(V, "InitVoice_1", "Bc5VoiceOn", "KYTY_BC5_LOAD_VOICE"),
)
VOICE_BLOCKS = (("static int KYTY_SYSV_ABI sceVoiceGetMuteFlag() {" + V, VOICE_BLOCK),)
VOICE_USES = (("Bc5VoiceOn()", 4), ("Bc5VoiceVadSetVersion(", 2), ("Bc5VoiceResourceInfoCheck(", 2), ("LIB_FUNC(", 14),
              ("// STUBBED", 14))

# =====================================================================================================================
# src/libs/libScreenShot.cpp (LF, one line per line; its stubs return 0, the unit has no libs/errno.h)
# =====================================================================================================================
SS = "\n"
SCREENSHOT_ITEMS = "Disable Enable IsDisabled SetOverlayImage SetOverlayImageWithOrigin"
SCREENSHOT_BLOCK = r"""// ---- BC5 experiment 0405 (series e7 of experiment 0401), tag "tbv": KYTY_BC5_LOAD_SCREENSHOT, libSceScreenShot ported --
// Exp 0405 decision 4 (the tables compiled but never loaded): this table is ported first, then loaded by Libs::InitAll when
// KYTY_BC5_LOAD_SCREENSHOT is on (libs.cpp, tag "tl2"). No live table registers libSceScreenShot. In adapted form from
// AnyPS5 (github.com/boykopovar/AnyPS5, GPL-2.0-only) @ 4f41f4c375f5abb487dbd184fbc150f31994d762,
// core/libs/prx/libSceScreenShot/Export.cpp:12-86 (commit f2bdca611: the checks "as the PS5 module does", "in the module's
// order", a reading of the PS5 module: exp 0405 decision 1) and its note docs/dev/debt/libSceScreenShot.md:5-7:
//   Disable and Enable set and clear one process-wide flag and return 0. IsDisabled(id, out) gives ERROR_ARGUMENT
//   0x80BE0001 for id -1 or a null out, else writes the flag (1 or 0) as a 32-bit value and returns 0. AnyPS5's
//   ERROR_ARGUMENT for a non-null unmapped out is its host-safety fallback (note :7) and is not ported.
//   SetOverlayImage(path, x, y) and SetOverlayImageWithOrigin(path, x, y, origin), in this order: origin 1 to 9; a
//   non-null path, x 0-1919 and y 0-1079 (0-3839 and 0-2159 for a title built with SDK 3.50 or later); a path shorter than
//   1024 bytes (each of these else ERROR_ARGUMENT); a file the kernel opens and that is not a directory (else
//   ERROR_OVERLAY_FILE 0x80BE0003); a size from 1 byte to 2 MiB, 8 MiB for SDK 3.50 or later (else ERROR_OVERLAY_SIZE
//   0x80BE000E); then 0. The image is not kept: no screenshots are taken (note :6). The file is opened through our kernel
//   (KernelOpen, KernelFstat, KernelClose), as AnyPS5 opens it through its own. The SDK version is the one our
//   sceKernelGetCompiledSdkVersion gives (libs/bc5LleAgc.cpp, exp 0336: the process parameter's u64 at +0x10, its high
//   half, else its low half, when within 0x01000000-0x1FFFFFFF; else 0x0A000000); AnyPS5 reads the 32 bits at +0x10.
//   TODO(verify): the SDK field.
//   EnableNotification and DisableNotification already give AnyPS5's answer (0, note :5).
// Held (today's 0): Capture, GetAppInfo, GetDrcParam, IsVshScreenCaptureDisabled, SetParam, SetDrcParam, and
// ScreenShotDummy (AS45QoYHjc4): AnyPS5 does not implement them (note :11-12).
// KYTY_BC5_LOAD_SCREENSHOT: unset, empty or "0" is off (today's stubs: 0, nothing written); any other value is on. Read
// once; one stderr line at registration or at the first call.
// AnyPS5's copyright remains with its authors; GPL-2.0 as the rest of this file (AnyPS5's part is GPL-2.0-only).
static constexpr int      BC5_SCREENSHOT_ERROR_ARGUMENT     = static_cast<int>(0x80BE0001u);
static constexpr int      BC5_SCREENSHOT_ERROR_OVERLAY_FILE = static_cast<int>(0x80BE0003u);
static constexpr int      BC5_SCREENSHOT_ERROR_OVERLAY_SIZE = static_cast<int>(0x80BE000Eu);
static constexpr uint32_t BC5_SCREENSHOT_LARGE_SDK          = 0x03500000u; // SDK 3.50
static constexpr size_t   BC5_SCREENSHOT_PATH_MAX           = 0x400;       // a path is shorter than this
static constexpr int      BC5_SCREENSHOT_TYPE_MASK          = 0xF000;      // st_mode's file type
static constexpr int      BC5_SCREENSHOT_TYPE_DIRECTORY     = 0x4000;

""" + on_line("Bc5ScreenShotOn", "KYTY_BC5_LOAD_SCREENSHOT", "screenshot", SCREENSHOT_ITEMS) + r"""
// The process-wide flag that Disable sets and Enable clears.
static std::atomic<bool>& Bc5ScreenShotDisabled() {
»static std::atomic<bool> disabled {false};
»return disabled;
}

static int Bc5ScreenShotSetDisabled(bool disabled) {
»Bc5ScreenShotDisabled().store(disabled);
»return 0;
}

static int Bc5ScreenShotIsDisabled(int id, int32_t* is_disabled) {
»if (id == -1 || is_disabled == nullptr) {
»»return BC5_SCREENSHOT_ERROR_ARGUMENT;
»}
»*is_disabled = Bc5ScreenShotDisabled().load() ? 1 : 0;
»return 0;
}

// The title's SDK version, as our sceKernelGetCompiledSdkVersion gives it (libs/bc5LleAgc.cpp, exp 0336), read once.
static uint32_t Bc5ScreenShotSdkVersion() {
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

static int Bc5ScreenShotSetOverlay(const char* path, int x, int y) {
»const bool    large    = Bc5ScreenShotSdkVersion() >= BC5_SCREENSHOT_LARGE_SDK;
»const int     max_x    = large ? 3839 : 1919;
»const int     max_y    = large ? 2159 : 1079;
»const int64_t max_size = (large ? int64_t {8} : int64_t {2}) * 1024 * 1024;
»if (path == nullptr || x < 0 || x > max_x || y < 0 || y > max_y) {
»»return BC5_SCREENSHOT_ERROR_ARGUMENT;
»}
»size_t length = 0;
»while (length < BC5_SCREENSHOT_PATH_MAX && path[length] != '\0') {
»»length++;
»}
»if (length >= BC5_SCREENSHOT_PATH_MAX) {
»»return BC5_SCREENSHOT_ERROR_ARGUMENT;
»}
»const int fd = LibKernel::FileSystem::KernelOpen(path, 0, 0); // read only
»if (fd < 0) {
»»return BC5_SCREENSHOT_ERROR_OVERLAY_FILE;
»}
»LibKernel::FileSystem::FileStat st {};
»int                             result = BC5_SCREENSHOT_ERROR_OVERLAY_FILE;
»if (LibKernel::FileSystem::KernelFstat(fd, &st) == 0 && (st.st_mode & BC5_SCREENSHOT_TYPE_MASK) != BC5_SCREENSHOT_TYPE_DIRECTORY) {
»»result = (st.st_size > 0 && st.st_size <= max_size) ? 0 : BC5_SCREENSHOT_ERROR_OVERLAY_SIZE;
»}
»(void)LibKernel::FileSystem::KernelClose(fd);
»return result;
}

static int Bc5ScreenShotSetOverlayWithOrigin(const char* path, int x, int y, int origin) {
»if (origin < 1 || origin > 9) {
»»return BC5_SCREENSHOT_ERROR_ARGUMENT;
»}
»return Bc5ScreenShotSetOverlay(path, x, y);
}
// ---- end of BC5 experiment 0405 (KYTY_BC5_LOAD_SCREENSHOT) ----

"""
SCREENSHOT_GATE = "\u00bbif (Bc5ScreenShotOn()) { // BC5 experiment 0405 (KYTY_BC5_LOAD_SCREENSHOT); false when off\n"
SCREENSHOT_EDITS = (
    ("includes", "#include <common/abi.h>\n",
     "#include <common/abi.h>\n"
     "\n"
     "#include \"kernel/fileSystem.h\" // BC5 experiment 0405 (KYTY_BC5_LOAD_SCREENSHOT): these includes and Bc5ProcParam\n"
     "\n"
     "#include <atomic>\n"
     "#include <cstddef>\n"
     "#include <cstdint>\n"
     "#include <cstdio>\n"
     "#include <cstdlib>\n"
     "#include <cstring>\n"
     "\n"
     "namespace Loader {\n"
     "uint64_t Bc5ProcParam(); // loader/runtimeLinker.cpp: the program's process parameter, as libs/bc5LleAgc.cpp has it\n"
     "} // namespace Loader\n"),
    stub_edit(SS, "Disable", "static int KYTY_SYSV_ABI sceScreenShotDisable() {", "static int KYTY_SYSV_ABI sceScreenShotDisable() {",
              SCREENSHOT_GATE + "\u00bb\u00bbreturn Bc5ScreenShotSetDisabled(true);\n\u00bb}\n"),
    stub_edit(SS, "Enable", "static int KYTY_SYSV_ABI sceScreenShotEnable() {", "static int KYTY_SYSV_ABI sceScreenShotEnable() {",
              SCREENSHOT_GATE + "\u00bb\u00bbreturn Bc5ScreenShotSetDisabled(false);\n\u00bb}\n"),
    stub_edit(SS, "IsDisabled", "static int KYTY_SYSV_ABI sceScreenShotIsDisabled() {",
              "static int KYTY_SYSV_ABI sceScreenShotIsDisabled(int id, int32_t* is_disabled) {",
              SCREENSHOT_GATE + "\u00bb\u00bbreturn Bc5ScreenShotIsDisabled(id, is_disabled);\n\u00bb}\n"),
    stub_edit(SS, "SetOverlayImage", "static int KYTY_SYSV_ABI sceScreenShotSetOverlayImage() {",
              "static int KYTY_SYSV_ABI sceScreenShotSetOverlayImage(const char* path, int offset_x, int offset_y) {",
              SCREENSHOT_GATE + "\u00bb\u00bbreturn Bc5ScreenShotSetOverlay(path, offset_x, offset_y);\n\u00bb}\n"),
    stub_edit(SS, "SetOverlayImageWithOrigin", "static int KYTY_SYSV_ABI sceScreenShotSetOverlayImageWithOrigin() {",
              "static int KYTY_SYSV_ABI sceScreenShotSetOverlayImageWithOrigin(const char* path, int offset_x, int offset_y,\n"
              "                                                               int origin) {",
              SCREENSHOT_GATE + "\u00bb\u00bbreturn Bc5ScreenShotSetOverlayWithOrigin(path, offset_x, offset_y, origin);\n\u00bb}\n"),
    reg_edit(SS, "InitScreenShot_1", "Bc5ScreenShotOn", "KYTY_BC5_LOAD_SCREENSHOT"),
)
SCREENSHOT_BLOCKS = (("static int KYTY_SYSV_ABI ScreenShotDummy() {" + SS, SCREENSHOT_BLOCK),)
SCREENSHOT_USES = (("Bc5ScreenShotOn()", 7), ("Bc5ScreenShotDisabled()", 3), ("Bc5ScreenShotSetDisabled(", 3),
                   ("Bc5ScreenShotIsDisabled(", 2), ("Bc5ScreenShotSetOverlay(", 3), ("Bc5ScreenShotSetOverlayWithOrigin(", 2),
                   ("Bc5ScreenShotSdkVersion()", 2), ("Bc5ProcParam()", 2), ("LIB_FUNC(", 14), ("TODO(verify)", 1))

# =====================================================================================================================
# src/libs/libDiscMap.cpp (LF, two blank lines after every line)
# =====================================================================================================================
DM = "\n\n\n"
DISCMAP_ITEMS = "IsRequestOnHDD ioKMruft1ek"
DISCMAP_BLOCK = r"""// ---- BC5 experiment 0405 (series e7 of experiment 0401), tag "tbv": KYTY_BC5_LOAD_DISCMAP, libSceDiscMap ported ----
// Exp 0405 decision 4 (the tables compiled but never loaded): this table is ported first, then loaded by Libs::InitAll when
// KYTY_BC5_LOAD_DISCMAP is on (libs.cpp, tag "tl2"). No live table registers libSceDiscMap. In adapted form from AnyPS5
// (github.com/boykopovar/AnyPS5, GPL-2.0-only) @ 4f41f4c375f5abb487dbd184fbc150f31994d762,
// core/libs/prx/libSceDiscMap/Export.cpp:8-33 (commits 716d81186, 31935cc85): sceDiscMapIsRequestOnHDD (lbQKqsERhtE) and
// ioKMruft1ek (Func_8A828CAEE7EDD5E9 here) return NO_BITMAP_INFO 0x81100004 before reading any argument and write
// nothing, the console library's answer while it has no disc bitmap loaded. Its note docs/dev/debt/libSceDiscMap.md:5
// ("the confirmed no-bitmap path"; "The supplied module confirms" the argument widths: a reading of the module, exp 0405
// decision 1). shadPS4 (GPL-2.0-or-later) @ 60c42b9, src/core/libraries/disc_map/disc_map.cpp:16-18 and 28-31 and
// disc_map_codes.h:9, gives the same.
// Held (today's 0): sceDiscMapGetPackageSize (fl1eoDnwQ4s), fJgP+wqifno and 5+vOlukvkfg: AnyPS5 does not implement them
// (note :9, :13).
// KYTY_BC5_LOAD_DISCMAP: unset, empty or "0" is off (today's stubs: 0, nothing written); any other value is on. Read once;
// one stderr line at registration or at the first call.
// AnyPS5's copyright remains with its authors; GPL-2.0 as the rest of this file (AnyPS5's part is GPL-2.0-only).
static constexpr int BC5_DISC_MAP_ERROR_NO_BITMAP_INFO = static_cast<int>(0x81100004u);

""" + on_line("Bc5DiscMapOn", "KYTY_BC5_LOAD_DISCMAP", "discmap", DISCMAP_ITEMS) + r"""// ---- end of BC5 experiment 0405 (KYTY_BC5_LOAD_DISCMAP) ----

"""
DISCMAP_GATE = ("\u00bbif (Bc5DiscMapOn()) { // BC5 experiment 0405 (KYTY_BC5_LOAD_DISCMAP); false when off\n"
                "\u00bb\u00bbreturn BC5_DISC_MAP_ERROR_NO_BITMAP_INFO; // no argument read, nothing written\n"
                "\u00bb}\n")
DISCMAP_EDITS = (
    ("includes", "#include <common/abi.h>" + DM,
     "#include <common/abi.h>" + DM +
     "#include <cstdint> // BC5 experiment 0405 (KYTY_BC5_LOAD_DISCMAP): these includes\n"
     "#include <cstdio>\n"
     "#include <cstdlib>" + DM),
    stub_edit(DM, "IsRequestOnHDD", "static int KYTY_SYSV_ABI sceDiscMapIsRequestOnHDD() {",
              "static int KYTY_SYSV_ABI sceDiscMapIsRequestOnHDD(const char* /*path*/, int64_t /*offset*/, int64_t /*size*/,\n"
              "                                                  int32_t* /*on_hdd*/) {",
              DISCMAP_GATE),
    stub_edit(DM, "ioKMruft1ek", "static int KYTY_SYSV_ABI Func_8A828CAEE7EDD5E9() {",
              "static int KYTY_SYSV_ABI Func_8A828CAEE7EDD5E9(const char* /*path*/, int64_t /*offset*/, int64_t /*size*/,\n"
              "                                               uint64_t* /*bitmap*/, uint64_t* /*first_block*/,\n"
              "                                               uint64_t* /*block_count*/) {",
              DISCMAP_GATE),
    reg_edit(DM, "InitDiscMap_1", "Bc5DiscMapOn", "KYTY_BC5_LOAD_DISCMAP"),
)
DISCMAP_BLOCKS = (("static int KYTY_SYSV_ABI sceDiscMapGetPackageSize() {" + DM, DISCMAP_BLOCK),)
DISCMAP_USES = (("Bc5DiscMapOn()", 4), ("BC5_DISC_MAP_ERROR_NO_BITMAP_INFO", 3), ("LIB_FUNC(", 5), ("// STUBBED", 5))

# =====================================================================================================================
# src/libs/libUlobjmgr.cpp (LF, two blank lines after every line)
# =====================================================================================================================
UL = "\n\n\n"
ULOBJMGR_ITEMS = "RegisterObject UnregisterObject"
ULOBJMGR_BLOCK = r"""// ---- BC5 experiment 0405 (series e7 of experiment 0401), tag "tbv": KYTY_BC5_LOAD_ULOBJMGR, ulobjmgr ported ----
// Exp 0405 decision 4 (the tables compiled but never loaded): this table is ported first, then loaded by Libs::InitAll when
// KYTY_BC5_LOAD_ULOBJMGR is on (libs.cpp, tag "tl2"). No live table registers ulobjmgr. In adapted form from AnyPS5
// (github.com/boykopovar/AnyPS5, GPL-2.0-only) @ 4f41f4c375f5abb487dbd184fbc150f31994d762,
// core/libs/prx/ulobjmgr/Export.cpp:10-33, which follows shadPS4 (GPL-2.0-or-later) @ 60c42b9,
// src/core/libraries/ulobjmgr/ulobjmgr.cpp:12-25 (note docs/dev/debt/ulobjmgr.md:5, :9: PS4 behaviour, not measured on a
// PS5):
//   _sceUlobjmgrRegisterObject(object, kind, id_out): a zero object, a zero kind or a null id_out gives the raw EINVAL
//   (22); otherwise id 0 is written and 0 returned. No object is registered.
//   _sceUlobjmgrUnregisterObject(id): an id of 0x4000 or more gives 22; otherwise 0. Nothing is released.
//   AnyPS5's EFAULT (14) for an unwritable id_out is its host-safety fallback (note :9) and is not ported.
//   TODO(verify): the PS5 signature and the raw errno answers.
// Held (today's 0): HZ9Q2c+4BU4 and SweJO7t3pkk: AnyPS5 does not implement them (note :13).
// KYTY_BC5_LOAD_ULOBJMGR: unset, empty or "0" is off (today's stubs: 0, nothing written); any other value is on. Read
// once; one stderr line at registration or at the first call.
// AnyPS5's copyright remains with its authors; GPL-2.0 as the rest of this file (AnyPS5's part is GPL-2.0-only).
static constexpr int      BC5_ULOBJMGR_EINVAL   = 22;
static constexpr uint32_t BC5_ULOBJMGR_ID_LIMIT = 0x4000;

""" + on_line("Bc5UlobjmgrOn", "KYTY_BC5_LOAD_ULOBJMGR", "ulobjmgr", ULOBJMGR_ITEMS) + r"""
static int Bc5UlobjmgrRegister(uint64_t object, int32_t kind, uint32_t* id_out) {
»if (object == 0 || kind == 0 || id_out == nullptr) {
»»return BC5_ULOBJMGR_EINVAL;
»}
»*id_out = 0;
»return OK;
}

static int Bc5UlobjmgrUnregister(uint32_t id) {
»return id >= BC5_ULOBJMGR_ID_LIMIT ? BC5_ULOBJMGR_EINVAL : OK;
}
// ---- end of BC5 experiment 0405 (KYTY_BC5_LOAD_ULOBJMGR) ----

"""
ULOBJMGR_GATE = "\u00bbif (Bc5UlobjmgrOn()) { // BC5 experiment 0405 (KYTY_BC5_LOAD_ULOBJMGR); false when off\n"
ULOBJMGR_EDITS = (
    ("includes", "#include <common/abi.h>" + UL,
     "#include <common/abi.h>" + UL +
     "#include <cstdint> // BC5 experiment 0405 (KYTY_BC5_LOAD_ULOBJMGR): these includes\n"
     "#include <cstdio>\n"
     "#include <cstdlib>" + UL),
    stub_edit(UL, "RegisterObject", "static int KYTY_SYSV_ABI _sceUlobjmgrRegisterObject() {",
              "static int KYTY_SYSV_ABI _sceUlobjmgrRegisterObject(uint64_t object, int32_t kind, uint32_t* id_out) {",
              ULOBJMGR_GATE + "\u00bb\u00bbreturn Bc5UlobjmgrRegister(object, kind, id_out);\n\u00bb}\n"),
    stub_edit(UL, "UnregisterObject", "static int KYTY_SYSV_ABI _sceUlobjmgrUnregisterObject() {",
              "static int KYTY_SYSV_ABI _sceUlobjmgrUnregisterObject(uint32_t id) {",
              ULOBJMGR_GATE + "\u00bb\u00bbreturn Bc5UlobjmgrUnregister(id);\n\u00bb}\n"),
    reg_edit(UL, "InitUlobjmgr_1", "Bc5UlobjmgrOn", "KYTY_BC5_LOAD_ULOBJMGR"),
)
ULOBJMGR_BLOCKS = (("static int KYTY_SYSV_ABI _sceUlobjmgrRegisterObject() {" + UL, ULOBJMGR_BLOCK),)
ULOBJMGR_USES = (("Bc5UlobjmgrOn()", 4), ("Bc5UlobjmgrRegister(", 2), ("Bc5UlobjmgrUnregister(", 2), ("LIB_FUNC(", 4),
                 ("TODO(verify)", 1))

# =====================================================================================================================
# src/libs/libCompanion.cpp (LF, one blank line after every line): two tables, two switches
# =====================================================================================================================
CP = "\n\n"
HTTPD_ITEMS = "OptParamInitialize Initialize Terminate RegisterRequestCallback UnregisterRequestCallback Start Stop GetEvent"
HTTPD_BLOCK = r"""// ---- BC5 experiment 0405 (series e7 of experiment 0401), tag "tbv": KYTY_BC5_LOAD_COMPANIONHTTPD, libSceCompanionHttpd --
// Exp 0405 decision 4 (the tables compiled but never loaded): this table is ported first, then loaded by Libs::InitAll when
// KYTY_BC5_LOAD_COMPANIONHTTPD is on (libs.cpp, tag "tl2"). No live table registers libSceCompanionHttpd. In adapted form
// from AnyPS5 (github.com/boykopovar/AnyPS5, GPL-2.0-only) @ 4f41f4c375f5abb487dbd184fbc150f31994d762,
// core/libs/prx/libSceCompanionHttpd/Export.cpp:9-109 (commit 346cafdb8) and its note
// docs/dev/debt/libSceCompanionHttpd.md:5, :11 (not measured on a console): the server's state with no companion device.
// The error codes are shadPS4's (GPL-2.0-or-later) @ 60c42b9, src/core/libraries/companion/companion_error.h:12-21, with
// ALREADY_REGISTERED 0x80E4000C (the header's 0x80E4000 is one digit short, note :11).
//   OptParamInitialize(opt): INVALID_PARAM 0x80E40004 for a null opt, else the 0x60-byte option block is cleared (titles
//     fill +0x08, +0x10 and +0x58 after it, note :5; the console's defaults are unknown: TODO(verify)).
//   Initialize(opt): INVALID_PARAM for a null opt (checked first), ALREADY_INITIALIZED 0x80E40007; no field is read.
//   Terminate(): NOT_INITIALIZED 0x80E40006; clears the state.
//   RegisterRequestCallback(function, argument): INVALID_PARAM for a null function (checked first), NOT_INITIALIZED,
//     ALREADY_REGISTERED; the callback is kept and never called: no companion device ever connects.
//   UnregisterRequestCallback(): NOT_INITIALIZED; drops the callback.
//   Start(): NOT_INITIALIZED, ALREADY_STARTED 0x80E4000A. Stop(): NOT_INITIALIZED, NOT_STARTED 0x80E4000B.
//   GetEvent(event): INVALID_PARAM for a null event (checked first), NOT_INITIALIZED, else NO_EVENT 0x80E40008 with
//     nothing written.
// Adapted where AnyPS5 throws (the console's answer is unknown), each TODO(verify) with a catcher line, once: Terminate of
// a started server stops it and terminates (0); Unregister with no callback keeps today's 0 and changes nothing.
// Held (no AnyPS5 behaviour, note :7; today's 0): Get2ndScreenStatus, GetUserId, Initialize2,
// RegisterRequestBodyReceptionCallback, RegisterRequestCallback2, UnregisterRequestBodyReceptionCallback. Initialize2 also
// marks the library initialized while the switch is on, so the ported calls do not refuse a title that initialized
// through it (a host choice, TODO(verify), with a catcher line once).
// AddHeader, SetStatus and SetBody already give AnyPS5's answer: 0, arguments untouched (shadPS4
// companion_httpd.cpp:12-15, 69-78 the same).
// KYTY_BC5_LOAD_COMPANIONHTTPD: unset, empty or "0" is off (today's stubs: 0, nothing written); any other value is on.
// Read once; one stderr line at registration or at the first call.
// AnyPS5's copyright remains with its authors; GPL-2.0 as the rest of this file (AnyPS5's part is GPL-2.0-only).
static constexpr int    BC5_HTTPD_ERROR_INVALID_PARAM       = static_cast<int>(0x80E40004u);
static constexpr int    BC5_HTTPD_ERROR_NOT_INITIALIZED     = static_cast<int>(0x80E40006u);
static constexpr int    BC5_HTTPD_ERROR_ALREADY_INITIALIZED = static_cast<int>(0x80E40007u);
static constexpr int    BC5_HTTPD_ERROR_NO_EVENT            = static_cast<int>(0x80E40008u);
static constexpr int    BC5_HTTPD_ERROR_ALREADY_STARTED     = static_cast<int>(0x80E4000Au);
static constexpr int    BC5_HTTPD_ERROR_NOT_STARTED         = static_cast<int>(0x80E4000Bu);
static constexpr int    BC5_HTTPD_ERROR_ALREADY_REGISTERED  = static_cast<int>(0x80E4000Cu);
static constexpr size_t BC5_HTTPD_OPT_PARAM_SIZE            = 0x60;

""" + on_line("Bc5HttpdOn", "KYTY_BC5_LOAD_COMPANIONHTTPD", "companionhttpd", HTTPD_ITEMS) + r"""
// A catcher line, printed once.
static void Bc5HttpdCatcher(std::atomic<bool>* said, const char* line) {
»if (!said->exchange(true)) {
»»std::fputs(line, stderr);
»»std::fflush(stderr);
»}
}

struct Bc5HttpdState {
»std::mutex  mutex;
»bool        initialized = false;
»bool        started     = false;
»const void* callback    = nullptr; // kept, never called: no companion device connects
»void*       argument    = nullptr;
};

// Never destroyed: a guest thread may still call while the process ends.
static Bc5HttpdState& Bc5Httpd() {
»static auto* state = new Bc5HttpdState;
»return *state;
}

static int Bc5HttpdOptParamInitialize(void* opt) {
»if (opt == nullptr) {
»»return BC5_HTTPD_ERROR_INVALID_PARAM;
»}
»std::memset(opt, 0, BC5_HTTPD_OPT_PARAM_SIZE); // the console's defaults are unknown: TODO(verify)
»return OK;
}

static int Bc5HttpdInitialize(const void* opt) {
»if (opt == nullptr) {
»»return BC5_HTTPD_ERROR_INVALID_PARAM;
»}
»auto&           h = Bc5Httpd();
»std::lock_guard lock(h.mutex);
»if (h.initialized) {
»»return BC5_HTTPD_ERROR_ALREADY_INITIALIZED;
»}
»h.initialized = true;
»return OK;
}

static int Bc5HttpdTerminate() {
»static std::atomic<bool> said {false};
»auto&                    h = Bc5Httpd();
»std::lock_guard          lock(h.mutex);
»if (!h.initialized) {
»»return BC5_HTTPD_ERROR_NOT_INITIALIZED;
»}
»if (h.started) { // AnyPS5 throws here: TODO(verify)
»»Bc5HttpdCatcher(&said, "[bc5] exp 0405: companionhttpd Terminate of a started server: AnyPS5 has no answer; stopped and "
»»                       "terminated, 0\n");
»}
»h.initialized = false;
»h.started     = false;
»h.callback    = nullptr;
»h.argument    = nullptr;
»return OK;
}

static int Bc5HttpdRegisterRequestCallback(const void* function, void* argument) {
»if (function == nullptr) {
»»return BC5_HTTPD_ERROR_INVALID_PARAM;
»}
»auto&           h = Bc5Httpd();
»std::lock_guard lock(h.mutex);
»if (!h.initialized) {
»»return BC5_HTTPD_ERROR_NOT_INITIALIZED;
»}
»if (h.callback != nullptr) {
»»return BC5_HTTPD_ERROR_ALREADY_REGISTERED;
»}
»h.callback = function;
»h.argument = argument;
»return OK;
}

static int Bc5HttpdUnregisterRequestCallback() {
»static std::atomic<bool> said {false};
»auto&                    h = Bc5Httpd();
»std::lock_guard          lock(h.mutex);
»if (!h.initialized) {
»»return BC5_HTTPD_ERROR_NOT_INITIALIZED;
»}
»if (h.callback == nullptr) { // AnyPS5 throws here: TODO(verify)
»»Bc5HttpdCatcher(&said, "[bc5] exp 0405: companionhttpd UnregisterRequestCallback with no callback: AnyPS5 has no "
»»                       "answer; today's 0 kept\n");
»»return OK;
»}
»h.callback = nullptr;
»h.argument = nullptr;
»return OK;
}

static int Bc5HttpdStart() {
»auto&           h = Bc5Httpd();
»std::lock_guard lock(h.mutex);
»if (!h.initialized) {
»»return BC5_HTTPD_ERROR_NOT_INITIALIZED;
»}
»if (h.started) {
»»return BC5_HTTPD_ERROR_ALREADY_STARTED;
»}
»h.started = true;
»return OK;
}

static int Bc5HttpdStop() {
»auto&           h = Bc5Httpd();
»std::lock_guard lock(h.mutex);
»if (!h.initialized) {
»»return BC5_HTTPD_ERROR_NOT_INITIALIZED;
»}
»if (!h.started) {
»»return BC5_HTTPD_ERROR_NOT_STARTED;
»}
»h.started = false;
»return OK;
}

static int Bc5HttpdGetEvent(const void* event) {
»if (event == nullptr) {
»»return BC5_HTTPD_ERROR_INVALID_PARAM;
»}
»auto&           h = Bc5Httpd();
»std::lock_guard lock(h.mutex);
»if (!h.initialized) {
»»return BC5_HTTPD_ERROR_NOT_INITIALIZED;
»}
»return BC5_HTTPD_ERROR_NO_EVENT; // no companion device connects: nothing is written
}

// Held sceCompanionHttpdInitialize2 (no AnyPS5 behaviour): today's 0, and the library is marked initialized so that the
// ported calls agree with it. A host choice: TODO(verify).
static int Bc5HttpdInitialize2Held() {
»static std::atomic<bool> said {false};
»Bc5HttpdCatcher(&said, "[bc5] exp 0405: companionhttpd Initialize2: AnyPS5 has no answer; today's 0 kept, the library "
»                       "marked initialized for the ported calls\n");
»auto&           h = Bc5Httpd();
»std::lock_guard lock(h.mutex);
»h.initialized = true;
»return OK;
}
// ---- end of BC5 experiment 0405 (KYTY_BC5_LOAD_COMPANIONHTTPD) ----

"""
HTTPD_GATE = "\u00bbif (Bc5HttpdOn()) { // BC5 experiment 0405 (KYTY_BC5_LOAD_COMPANIONHTTPD); false when off\n"


def httpd_edit(what, sig_old, sig_new, call):
    return stub_edit(CP, what, sig_old, sig_new, HTTPD_GATE + "\u00bb\u00bbreturn " + call + ";\n\u00bb}\n")


UTIL_ITEMS = "GetEvent"
UTIL_BLOCK = r"""// ---- BC5 experiment 0405 (series e7 of experiment 0401), tag "tbv": KYTY_BC5_LOAD_COMPANIONUTIL, libSceCompanionUtil --
// Exp 0405 decision 4 (the tables compiled but never loaded): this table is ported first, then loaded by Libs::InitAll when
// KYTY_BC5_LOAD_COMPANIONUTIL is on (libs.cpp, tag "tl2"). No live table registers libSceCompanionUtil.
// sceCompanionUtilGetEvent returns NO_EVENT 0x80AD0008 and reads and writes nothing (no companion device connects):
// shadPS4 (GPL-2.0-or-later) @ 60c42b9, src/core/libraries/companion/companion_util.cpp:31-36 and companion_error.h:27.
// AnyPS5 (github.com/boykopovar/AnyPS5, GPL-2.0-only) @ 4f41f4c375f5abb487dbd184fbc150f31994d762,
// core/libs/prx/libSceCompanionUtil/Export.cpp:9-11, gives the same answer.
// GetRemoteOskEvent, Initialize, OptParamInitialize and Terminate already give AnyPS5's and shadPS4's answer (0).
// KYTY_BC5_LOAD_COMPANIONUTIL: unset, empty or "0" is off (today's stubs: 0, nothing written); any other value is on.
// Read once; one stderr line at registration or at the first call.
static constexpr int BC5_COMPANION_UTIL_NO_EVENT = static_cast<int>(0x80AD0008u);

""" + on_line("Bc5CompanionUtilOn", "KYTY_BC5_LOAD_COMPANIONUTIL", "companionutil", UTIL_ITEMS) + r"""// ---- end of BC5 experiment 0405 (KYTY_BC5_LOAD_COMPANIONUTIL) ----

"""
COMPANION_EDITS = (
    ("includes", "#include <common/abi.h>" + CP,
     "#include <common/abi.h>" + CP +
     "#include <atomic> // BC5 experiment 0405 (KYTY_BC5_LOAD_COMPANIONHTTPD, KYTY_BC5_LOAD_COMPANIONUTIL): these includes\n"
     "#include <cstddef>\n"
     "#include <cstdint>\n"
     "#include <cstdio>\n"
     "#include <cstdlib>\n"
     "#include <cstring>\n"
     "#include <mutex>" + CP),
    httpd_edit("GetEvent", "static int KYTY_SYSV_ABI sceCompanionHttpdGetEvent() {",
               "static int KYTY_SYSV_ABI sceCompanionHttpdGetEvent(void* event) {", "Bc5HttpdGetEvent(event)"),
    httpd_edit("Initialize", "static int KYTY_SYSV_ABI sceCompanionHttpdInitialize() {",
               "static int KYTY_SYSV_ABI sceCompanionHttpdInitialize(const void* opt) {", "Bc5HttpdInitialize(opt)"),
    httpd_edit("Initialize2", "static int KYTY_SYSV_ABI sceCompanionHttpdInitialize2() {",
               "static int KYTY_SYSV_ABI sceCompanionHttpdInitialize2() {", "Bc5HttpdInitialize2Held()"),
    httpd_edit("OptParamInitialize", "static int KYTY_SYSV_ABI sceCompanionHttpdOptParamInitialize() {",
               "static int KYTY_SYSV_ABI sceCompanionHttpdOptParamInitialize(void* opt) {", "Bc5HttpdOptParamInitialize(opt)"),
    httpd_edit("RegisterRequestCallback", "static int KYTY_SYSV_ABI sceCompanionHttpdRegisterRequestCallback() {",
               "static int KYTY_SYSV_ABI sceCompanionHttpdRegisterRequestCallback(const void* function, void* argument) {",
               "Bc5HttpdRegisterRequestCallback(function, argument)"),
    httpd_edit("Start", "static int KYTY_SYSV_ABI sceCompanionHttpdStart() {", "static int KYTY_SYSV_ABI sceCompanionHttpdStart() {",
               "Bc5HttpdStart()"),
    httpd_edit("Stop", "static int KYTY_SYSV_ABI sceCompanionHttpdStop() {", "static int KYTY_SYSV_ABI sceCompanionHttpdStop() {",
               "Bc5HttpdStop()"),
    httpd_edit("Terminate", "static int KYTY_SYSV_ABI sceCompanionHttpdTerminate() {",
               "static int KYTY_SYSV_ABI sceCompanionHttpdTerminate() {", "Bc5HttpdTerminate()"),
    httpd_edit("UnregisterRequestCallback", "static int KYTY_SYSV_ABI sceCompanionHttpdUnregisterRequestCallback() {",
               "static int KYTY_SYSV_ABI sceCompanionHttpdUnregisterRequestCallback() {", "Bc5HttpdUnregisterRequestCallback()"),
    reg_edit(CP, "InitCompanionHttpd_1", "Bc5HttpdOn", "KYTY_BC5_LOAD_COMPANIONHTTPD"),
    stub_edit(CP, "Util GetEvent", "static int KYTY_SYSV_ABI sceCompanionUtilGetEvent() {",
              "static int KYTY_SYSV_ABI sceCompanionUtilGetEvent(void* /*event*/) {",
              "\u00bbif (Bc5CompanionUtilOn()) { // BC5 experiment 0405 (KYTY_BC5_LOAD_COMPANIONUTIL); false when off\n"
              "\u00bb\u00bbreturn BC5_COMPANION_UTIL_NO_EVENT; // nothing read or written\n"
              "\u00bb}\n"),
    reg_edit(CP, "InitCompanionUtil_1", "Bc5CompanionUtilOn", "KYTY_BC5_LOAD_COMPANIONUTIL"),
)
COMPANION_BLOCKS = (("static int KYTY_SYSV_ABI sceCompanionHttpdAddHeader() {" + CP, HTTPD_BLOCK),
                    ("static int KYTY_SYSV_ABI sceCompanionUtilGetEvent() {" + CP, UTIL_BLOCK))
COMPANION_USES = (("Bc5HttpdOn()", 11), ("Bc5Httpd()", 9), ("Bc5HttpdCatcher(", 4), ("Bc5HttpdOptParamInitialize(", 2),
                  ("Bc5HttpdInitialize(", 2), ("Bc5HttpdTerminate(", 2), ("Bc5HttpdRegisterRequestCallback(", 2),
                  ("Bc5HttpdUnregisterRequestCallback(", 2), ("Bc5HttpdStart(", 2), ("Bc5HttpdStop(", 2),
                  ("Bc5HttpdGetEvent(", 2), ("Bc5HttpdInitialize2Held(", 2), ("Bc5CompanionUtilOn()", 3),
                  ("BC5_COMPANION_UTIL_NO_EVENT", 2), ("LIB_FUNC(", 22), ("TODO(verify)", 7))

# =====================================================================================================================
# src/libs/libVideoRecording.cpp (LF, two blank lines after every line): the switch and its line only, SetInfo held
# =====================================================================================================================
VR = "\n\n\n"
VIDEOREC_BLOCK = r"""// ---- BC5 experiment 0405 (series e7 of experiment 0401), tag "tbv": KYTY_BC5_LOAD_VIDEORECORDING ----
// Exp 0405 decision 4 (the tables compiled but never loaded): this table is loaded by Libs::InitAll when
// KYTY_BC5_LOAD_VIDEORECORDING is on (libs.cpp, tag "tl2"). No live table registers libSceVideoRecording. Nothing is
// ported: its one call, sceVideoRecordingSetInfo, is held (today's 0). AnyPS5 (github.com/boykopovar/AnyPS5,
// GPL-2.0-only) @ 4f41f4c375f5abb487dbd184fbc150f31994d762, core/libs/prx/libSceVideoRecordingP/Export.cpp:193-205
// (commit cf717cd80) answers by info selector, but its note docs/dev/debt/libSceVideoRecordingP.md:5 names no run, no
// measurement and no reading for those answers; the firmware 13.40 measurement of exp 0405 #33 (note :20, :22, commit
// a344e526e) covers Open, QueryMemSize, GetStatus, Start, Stop and Close, not SetInfo.
// KYTY_BC5_LOAD_VIDEORECORDING: unset, empty or "0" is off; any other value is on. Read once; one stderr line at
// registration.
""" + on_line("Bc5VideoRecordingOn", "KYTY_BC5_LOAD_VIDEORECORDING", "videorecording", "none; SetInfo held") + r"""// ---- end of BC5 experiment 0405 (KYTY_BC5_LOAD_VIDEORECORDING) ----

"""
VIDEOREC_EDITS = (
    ("includes", "#include <common/abi.h>" + VR,
     "#include <common/abi.h>" + VR +
     "#include <cstdio> // BC5 experiment 0405 (KYTY_BC5_LOAD_VIDEORECORDING): these includes\n"
     "#include <cstdlib>" + VR),
    reg_edit(VR, "InitVideoRecording_1", "Bc5VideoRecordingOn", "KYTY_BC5_LOAD_VIDEORECORDING"),
)
VIDEOREC_BLOCKS = (("static int KYTY_SYSV_ABI sceVideoRecordingSetInfo() {" + VR, VIDEOREC_BLOCK),)
VIDEOREC_USES = (("Bc5VideoRecordingOn()", 2), ("LIB_FUNC(", 1), ("// STUBBED", 1))

UNITS = (
    # rel, blocks (anchor, block), edits, the LIB_VERSION line (must come before every block), helper uses
    ("src/libs/libVoice.cpp", VOICE_BLOCKS, VOICE_EDITS, ("LIB_VERSION(\"libSceVoice\", 1, \"libSceVoice\", 1, 1);",), VOICE_USES),
    ("src/libs/libScreenShot.cpp", SCREENSHOT_BLOCKS, SCREENSHOT_EDITS,
     ("LIB_VERSION(\"libSceScreenShot\", 1, \"libSceScreenShot\", 1, 1);",), SCREENSHOT_USES),
    ("src/libs/libDiscMap.cpp", DISCMAP_BLOCKS, DISCMAP_EDITS, ("LIB_VERSION(\"libSceDiscMap\", 1, \"libSceDiscMap\", 1, 1);",),
     DISCMAP_USES),
    ("src/libs/libUlobjmgr.cpp", ULOBJMGR_BLOCKS, ULOBJMGR_EDITS, ("LIB_VERSION(\"ulobjmgr\", 1, \"ulobjmgr\", 1, 1);",),
     ULOBJMGR_USES),
    ("src/libs/libCompanion.cpp", COMPANION_BLOCKS, COMPANION_EDITS,
     ("LIB_VERSION(\"libSceCompanionHttpd\", 1, \"libSceCompanionHttpd\", 1, 1);",
      "LIB_VERSION(\"libSceCompanionUtil\", 1, \"libSceCompanionUtil\", 1, 1);"), COMPANION_USES),
    ("src/libs/libVideoRecording.cpp", VIDEOREC_BLOCKS, VIDEOREC_EDITS,
     ("LIB_VERSION(\"libSceVideoRecording\", 1, \"libSceVideoRecording\", 1, 1);",), VIDEOREC_USES),
)


def balance(b):
    return (b.count(b"{") - b.count(b"}"), b.count(b"(") - b.count(b")"), b.count(b"[") - b.count(b"]"))


def md5(b):
    return hashlib.md5(b).hexdigest()


def edit_unit(rel, s, blocks, edits, versions, uses):
    for m in MARKS:
        assert m not in s, ("refused: the unit has the edit already", rel, m.decode())
    assert b"\r" not in s, ("a CR in an LF unit", rel)
    assert s.startswith(b"\xef\xbb\xbf"), ("no UTF-8 BOM", rel)
    out = s
    placed = []
    for anchor, block in blocks:
        A, B = T(anchor), T(block)
        assert balance(B) == (0, 0, 0), ("a block is not balanced", rel, balance(B))
        assert s.count(A) == 1 and out.count(A) == 1, ("a block's anchor", rel, anchor[:60], s.count(A))
        out = out.replace(A, B + A)
        placed.append(B)
    # Each block lies after its table's LIB_VERSION line and before the next one (its own namespace).
    vpos = []
    for v in versions:
        vb = T(v)
        assert out.count(vb) == 1, ("LIB_VERSION", rel, v)
        vpos.append(out.index(vb))
    for i, B in enumerate(placed):
        at = out.index(B)
        assert at > vpos[i] and (i + 1 >= len(vpos) or at < vpos[i + 1]), ("a block is outside its namespace", rel, i)
    done = []
    for what, old, new in edits:
        o, n = T(old), T(new)
        assert out.count(o) == 1, ("anchor", rel, what, out.count(o))
        assert balance(o) == balance(n), ("the edit changes the balance", rel, what, balance(o), balance(n))
        out = out.replace(o, n)
        done.append((o, n))
    assert balance(out) == balance(s), ("the unit's balance changed", rel, balance(s), balance(out))
    for name, n in uses:
        c = out.count(name.encode("ascii"))
        assert c == n, ("helper uses", rel, name, c, n)
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
    return out


def main():
    assert len(sys.argv) == 3, __doc__
    root, outdir = sys.argv[1], sys.argv[2]
    assert os.path.abspath(root) != os.path.abspath(outdir), "the out dir must not be the tree"
    assert set(PINNED) == {u[0] for u in UNITS}
    outs = []
    for rel, blocks, edits, versions, uses in UNITS:
        with open(os.path.join(root, rel), "rb") as f:
            s = f.read()
        for m in MARKS:
            assert m not in s, ("refused: the unit has the edit already", rel, m.decode())
        assert md5(s) == PINNED[rel], ("refused: not the pinned input", rel, md5(s), PINNED[rel])
        out = edit_unit(rel, s, blocks, edits, versions, uses)
        print(f"# in:  {rel} {md5(s)}  ({len(s)} bytes, LF)", file=sys.stderr)
        outs.append((rel, out))
    for rel, out in outs:  # written only when all six are done
        dst = os.path.join(outdir, rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        with open(dst, "wb") as f:
            f.write(out)
        print(f"{rel} {md5(out)}")


if __name__ == "__main__":
    main()
