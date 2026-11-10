#!/usr/bin/env python3
"""BC5 experiment 0405 (series e7 of experiment 0401), tag "tbd": exp 0405 decision 4 ("=> B => B": the tables that are
compiled but never loaded are ported first, then loaded, each behind its own switch), dead-table batch 2, four library
units of the e7 input tree (= e6's sources; these four are the base tree's files), each behind a switch that is off by
default and read once (off is today's path exactly). Libs::InitAll loads each table when its switch is on (libs.cpp,
loader agent "tl2", not edited here). With the switch on, a table does not register its held stubs (AnyPS5 has no
behaviour for them): their imports stay unresolved, as today, so the runtime linker's thunk keeps answering 0 and
journaling them (exp 0327's "[bc5] stubbed import called"); off, every NID is registered as today. libRemotePlay.cpp is
not edited and gets no switch (the top session, 2026-11-04: AnyPS5 implements none of its 39, nothing to port):
  src/libs/libInvitationDialog.cpp   KYTY_BC5_LOAD_INVITATIONDIALOG   Libs::LibInvitationDialog::InitInvitationDialog_1
      AnyPS5 libSceInvitationDialog/Export.cpp:15-114: Initialize, Terminate, Open, Close, GetResult (OpenA, GetResultA held)
  src/libs/libWebBrowserDialog.cpp   KYTY_BC5_LOAD_WEBBROWSERDIALOG   Libs::LibWebBrowserDialog::InitWebBrowserDialog_1
      AnyPS5 libSceWebBrowserDialog/Export.cpp:34-154: Open, OpenForPredeterminedContent, Close, UpdateStatus, GetResult,
      SetCookie, ResetCookie (the NOT_INITIALIZED answers held: Initialize/Terminate are libNet.cpp's, which keeps no state)
  src/libs/libSharePlay.cpp          KYTY_BC5_LOAD_SHAREPLAY          Libs::LibSharePlay::InitSharePlay_1
      AnyPS5 libSceSharePlay/Export.cpp:34-42,56-64: GetCurrentConnectionInfo, GetCurrentConnectionInfoA
  src/libs/libGameLiveStreaming.cpp  KYTY_BC5_LOAD_GAMELIVESTREAMING  Libs::LibGameLiveStreaming::InitGameLiveStreaming_1
      AnyPS5 libSceGameLiveStreaming/Export.cpp:14-38,59-85,135-222,234-239: 13 calls (7 already match, 25 held)
Every input's md5 is pinned in PINNED below (one dict, so the top session can re-pin it when it chains scripts) and
asserted; a unit that has the edit already is refused; every anchor must occur exactly once; every edit keeps braces,
parentheses and brackets balanced; the inserted text is ASCII; line ends stay as they are (all four are LF with a UTF-8
BOM). After editing, the script undoes its own edits on the output and asserts that this gives the input back byte for
byte. Only the four units are written, and only when all four are done. Prints "<relpath> <md5>" per written file.
Notes: tbd0405-notes.md; CPU test: tbd0405.cpp.
usage: mktbd0405.py <tree root in> <out dir>"""
import hashlib
import os
import sys

PINNED = {  # input md5 of each unit this script edits (the e7 input tree; all four are the base tree's files)
    "src/libs/libInvitationDialog.cpp": "204a5daeebb100a131c034edb8e58e87",
    "src/libs/libWebBrowserDialog.cpp": "af36a12a0bc234f83e5c85a76d4b283d",
    "src/libs/libSharePlay.cpp": "d6ecb7874b00ee29d9275d78d8087191",
    "src/libs/libGameLiveStreaming.cpp": "59e46b5d8452101a0f57257703cfa3a4",
}

MARKS = (b"experiment 0405", b"KYTY_BC5_LOAD_INVITATIONDIALOG", b"KYTY_BC5_LOAD_WEBBROWSERDIALOG",
         b"KYTY_BC5_LOAD_SHAREPLAY", b"KYTY_BC5_LOAD_GAMELIVESTREAMING", b"Bc5Invd", b"Bc5Wbd", b"Bc5Shp", b"Bc5Gls")

HELD_NOTE = ("// Held stubs are not registered while the switch is on: their imports stay unresolved, as today, so the runtime\n"
             "// linker's thunk answers 0 and journals them (exp 0327's \"[bc5] stubbed import called\"); off, every NID is\n"
             "// registered as today.\n")

SOURCE = "AnyPS5 (github.com/boykopovar/AnyPS5, GPL-2.0-only) @\n// 4f41f4c375f5abb487dbd184fbc150f31994d762"
LICENCE = "// AnyPS5's copyright remains with its authors; GPL-2.0 as the rest of this file (AnyPS5's part is GPL-2.0-only).\n"


def T(text, crlf=False):
    """C++ text written with a visible tab ("»") for each tab of the file's indentation, as ASCII bytes."""
    out = text.replace("»", "\t").encode("ascii")
    if crlf:
        assert b"\r" not in out
        out = out.replace(b"\n", b"\r\n")
    return out


def switch_fn(fn, env, word, items):
    """The switch reader: read once, one stderr line at registration or at the first call (env_flag.hpp's rule)."""
    return (f"// {env}, read once; the first call prints the switch's line.\n"
            f"static bool {fn}() {{\n"
            "»static const bool on = [] {\n"
            f"»»const char* e = std::getenv(\"{env}\");\n"
            "»»const bool  v = e != nullptr && e[0] != '\\0' && !(e[0] == '0' && e[1] == '\\0');\n"
            f"»»std::fputs(v ? \"[bc5] exp 0405: {word} port on (items: {items})\\n\"\n"
            f"»»             : \"[bc5] exp 0405: {word} port off\\n\",\n"
            "»»           stderr);\n"
            "»»std::fflush(stderr);\n"
            "»»return v;\n"
            "»}();\n"
            "»return on;\n"
            "}\n")


def registration(init, fn, env):
    return (f"LIB_DEFINE({init}) {{\n",
            f"LIB_DEFINE({init}) {{\n"
            f"»(void){fn}(); // BC5 experiment 0405: reads {env} once and prints its line at registration\n")


def held_registrations(fn, ns, held):
    """Each held stub's LIB_FUNC line, registered only when the switch is off (its own line, wrapped)."""
    return tuple((f"held {nid}", f"»LIB_FUNC(\"{nid}\", {ns}::{name});\n",
                  f"»if (!{fn}()) {{ // BC5 experiment 0405: held, registered only when off\n"
                  f"»»LIB_FUNC(\"{nid}\", {ns}::{name});\n»}}\n")
                 for nid, name in held)


# =====================================================================================================================
# src/libs/libInvitationDialog.cpp
# =====================================================================================================================
INV_ENV = "KYTY_BC5_LOAD_INVITATIONDIALOG"
INV_BLOCK_ANCHOR = "static int KYTY_SYSV_ABI sceInvitationDialogClose() {\n"
INV_BLOCK = r"""// ---- BC5 experiment 0405 (series e7 of experiment 0401), tag "tbd": KYTY_BC5_LOAD_INVITATIONDIALOG, libSceInvitationDialog ported ----
// Exp 0405 decision 4 (the tables compiled but never loaded): this table is ported first, then loaded by Libs::InitAll
// when KYTY_BC5_LOAD_INVITATIONDIALOG is on (libs.cpp, the loader agent "tl2"). No other table registers its 9 NIDs.
// Ported in adapted form from """ + SOURCE + r""", core/libs/prx/libSceInvitationDialog/Export.cpp:15-114,
// and its note docs/dev/debt/libSceInvitationDialog.md:6,13,17 (shadPS4's behaviour when its window is dismissed; "Not
// measured on a console"):
//   Initialize: ALREADY_INITIALIZED (0x80B80004) unless the status is none; it forgets the callback argument.
//   Terminate, Close: NOT_INITIALIZED (0x80B80003) while the status is none; Terminate goes back to none.
//   Open: ARG_NULL (0x80B8000D) for a null param; otherwise no window opens and no invitation is sent: the dialog is
//     finished at once (status 3) and keeps the param's callback argument.
//   GetResult: NOT_INITIALIZED, NOT_FINISHED (0x80B80005), ARG_NULL, in that order; then 0, with the callback argument,
//     error code 0, result USER_CANCELED (1) and a recipient count of 0 (when a recipient list is given).
// The param layout (144 bytes: size at 48, mode at 52, callback argument at 64) and the result layout (0x38 bytes:
// callback argument, error code, result, recipient list, 32 reserved bytes) are shadPS4's (GPL-2.0-or-later) @ 60c42b9,
// src/core/libraries/invitation_dialog/invitation_dialog.h:31-34,46-52,155-163.
// Already match (not edited): GetStatus and UpdateStatus return the status (UpdateStatus also finishes a running dialog,
// a status that only today's answers below leave). Today's answer is kept, with one catcher line on stderr, where AnyPS5
// throws (it has no answer): Open from a status that is neither initialized nor finished, or with a size other than 144
// or a mode other than send (1) / receive (2); Close of a dialog whose status is not none; GetResult with a non-zero
// reserved byte. Held: Initialize's NOT_SYSTEM_INITIALIZED (our sceCommonDialogInitialize, libs/dialog.cpp:31, keeps no
// state) and BUSY (AnyPS5's note :17: only this library takes the common dialog system, so it never gets BUSY); OpenA and
// GetResultA (AnyPS5 does not implement them). Not ported: AnyPS5's opt-in host notice on Open (host UI only).
// As in today's code, the status is a plain int: TODO(verify) a title that drives this dialog from two threads.
// KYTY_BC5_LOAD_INVITATIONDIALOG: unset, empty or "0" is off (today's answers); any other value is on. Read once; one
// stderr line at registration or at the first call.
""" + HELD_NOTE + LICENCE + r"""static constexpr int     BC5_INVD_ERROR_NOT_INITIALIZED     = static_cast<int>(0x80B80003u);
static constexpr int     BC5_INVD_ERROR_ALREADY_INITIALIZED = static_cast<int>(0x80B80004u);
static constexpr int     BC5_INVD_ERROR_NOT_FINISHED        = static_cast<int>(0x80B80005u);
static constexpr int     BC5_INVD_ERROR_ARG_NULL            = static_cast<int>(0x80B8000Du);
static constexpr int     BC5_INVD_STATUS_NONE               = 0;
static constexpr int     BC5_INVD_STATUS_INITIALIZED        = 1;
static constexpr int     BC5_INVD_STATUS_FINISHED           = 3;
static constexpr int32_t BC5_INVD_MODE_SEND                 = 1;
static constexpr int32_t BC5_INVD_MODE_RECV                 = 2;
static constexpr int32_t BC5_INVD_RESULT_USER_CANCELED      = 1;

struct Bc5InvdOpenParam {
»uint8_t     common_base[48]; // the common dialog's base parameter (not read here)
»uint32_t    size;            // sizeof(Bc5InvdOpenParam)
»int32_t     mode;            // send 1, receive 2
»int32_t     user_id;
»uint32_t    padding;
»void*       callback_arg;
»const void* data;
»uint8_t     reserved[64];
};

struct Bc5InvdResult {
»void*     callback_arg;
»int32_t   error_code;
»int32_t   result;
»uint32_t* recipients; // a count, then up to 16 online ids; only the count is written here
»uint8_t   reserved[32];
};

static_assert(sizeof(Bc5InvdOpenParam) == 144 && offsetof(Bc5InvdOpenParam, mode) == 52 &&
              offsetof(Bc5InvdOpenParam, callback_arg) == 64);
static_assert(sizeof(Bc5InvdResult) == 0x38 && offsetof(Bc5InvdResult, recipients) == 0x10);

static void* g_bc5_invd_callback_arg = nullptr; // the callback argument of the last Open (switch on)

""" + switch_fn("Bc5InvdOn", INV_ENV, "invitationdialog",
                "Initialize Terminate Open Close GetResult; OpenA GetResultA held, not registered") + r"""
// One stderr line per call site, the first time: a case AnyPS5 throws for (it has no answer), where today's answer is kept.
static void Bc5InvdNoAnswer(std::atomic<bool>* printed, const char* call, const char* what) {
»if (!printed->exchange(true)) {
»»std::fprintf(stderr, "[bc5] exp 0405: invitationdialog %s: AnyPS5 has no answer for %s; today's answer kept\n", call,
»»             what);
»»std::fflush(stderr);
»}
}

static int Bc5InvdInitialize() {
»if (g_status != BC5_INVD_STATUS_NONE) {
»»return BC5_INVD_ERROR_ALREADY_INITIALIZED;
»}
»g_status                = BC5_INVD_STATUS_INITIALIZED;
»g_bc5_invd_callback_arg = nullptr;
»return OK;
}

static int Bc5InvdTerminate() {
»if (g_status == BC5_INVD_STATUS_NONE) {
»»return BC5_INVD_ERROR_NOT_INITIALIZED;
»}
»g_status                = BC5_INVD_STATUS_NONE;
»g_bc5_invd_callback_arg = nullptr;
»return OK;
}

// Open: true with *answer where AnyPS5 answers; false where it throws (today's path then runs).
static bool Bc5InvdOpen(const void* param_in, int* answer) {
»static std::atomic<bool> printed_status {false};
»static std::atomic<bool> printed_param {false};
»if (g_status != BC5_INVD_STATUS_INITIALIZED && g_status != BC5_INVD_STATUS_FINISHED) {
»»Bc5InvdNoAnswer(&printed_status, "Open", "a dialog that is neither initialized nor finished");
»»return false;
»}
»if (param_in == nullptr) {
»»*answer = BC5_INVD_ERROR_ARG_NULL;
»»return true;
»}
»const auto* param = static_cast<const Bc5InvdOpenParam*>(param_in);
»if (param->size != sizeof(Bc5InvdOpenParam) || (param->mode != BC5_INVD_MODE_SEND && param->mode != BC5_INVD_MODE_RECV)) {
»»Bc5InvdNoAnswer(&printed_param, "Open", "a param size other than 144 or a mode other than send or receive");
»»return false;
»}
»g_bc5_invd_callback_arg = param->callback_arg;
»g_status                = BC5_INVD_STATUS_FINISHED; // no window: finished at once, as if the user had cancelled
»*answer                 = OK;
»return true;
}

// Close: NOT_INITIALIZED while none; false for any other status, where AnyPS5 throws (today's path then runs).
static bool Bc5InvdClose(int* answer) {
»static std::atomic<bool> printed {false};
»if (g_status == BC5_INVD_STATUS_NONE) {
»»*answer = BC5_INVD_ERROR_NOT_INITIALIZED;
»»return true;
»}
»Bc5InvdNoAnswer(&printed, "Close", "closing a dialog that is not running");
»return false;
}

// GetResult: true with *answer where AnyPS5 answers; false for a non-zero reserved byte, where it throws.
static bool Bc5InvdGetResult(void* result_in, int* answer) {
»static std::atomic<bool> printed {false};
»if (g_status == BC5_INVD_STATUS_NONE) {
»»*answer = BC5_INVD_ERROR_NOT_INITIALIZED;
»»return true;
»}
»if (g_status != BC5_INVD_STATUS_FINISHED) {
»»*answer = BC5_INVD_ERROR_NOT_FINISHED;
»»return true;
»}
»if (result_in == nullptr) {
»»*answer = BC5_INVD_ERROR_ARG_NULL;
»»return true;
»}
»auto* result = static_cast<Bc5InvdResult*>(result_in);
»for (const uint8_t b: result->reserved) {
»»if (b != 0) {
»»»Bc5InvdNoAnswer(&printed, "GetResult", "a non-zero reserved byte in the result");
»»»return false;
»»}
»}
»result->callback_arg = g_bc5_invd_callback_arg;
»result->error_code   = OK;
»result->result       = BC5_INVD_RESULT_USER_CANCELED;
»if (result->recipients != nullptr) {
»»*result->recipients = 0; // no invitation was sent
»}
»*answer = OK;
»return true;
}
// ---- end of BC5 experiment 0405 (KYTY_BC5_LOAD_INVITATIONDIALOG) ----

"""

INV_GATE = "»if (Bc5InvdOn()) { // BC5 experiment 0405 (KYTY_BC5_LOAD_INVITATIONDIALOG); false when off\n"


def inv_fallback(call):
    return (INV_GATE + "»»int answer = OK;\n"
            f"»»if ({call}) {{ // false: AnyPS5 has no answer; today's answer below\n"
            "»»»return answer;\n»»}\n»}\n")


INV_EDITS = (
    ("includes", "#include <common/abi.h>\n",
     "#include <common/abi.h>\n"
     "\n"
     "#include <atomic> // BC5 experiment 0405 (KYTY_BC5_LOAD_INVITATIONDIALOG): these includes\n"
     "#include <cstddef>\n"
     "#include <cstdint>\n"
     "#include <cstdio>\n"
     "#include <cstdlib>\n"),
    ("Close", "static int KYTY_SYSV_ABI sceInvitationDialogClose() {\n»PRINT_NAME();\n",
     "static int KYTY_SYSV_ABI sceInvitationDialogClose() {\n»PRINT_NAME();\n" + inv_fallback("Bc5InvdClose(&answer)")),
    ("GetResult", "static int KYTY_SYSV_ABI sceInvitationDialogGetResult() {\n\n\n»PRINT_NAME();\n",
     "static int KYTY_SYSV_ABI sceInvitationDialogGetResult(void* result) {\n\n\n»PRINT_NAME();\n" +
     inv_fallback("Bc5InvdGetResult(result, &answer)")),
    ("Initialize", "static int KYTY_SYSV_ABI sceInvitationDialogInitialize() {\n»PRINT_NAME();\n",
     "static int KYTY_SYSV_ABI sceInvitationDialogInitialize() {\n»PRINT_NAME();\n" + INV_GATE +
     "»»return Bc5InvdInitialize();\n»}\n"),
    ("Open", "static int KYTY_SYSV_ABI sceInvitationDialogOpen() {\n»PRINT_NAME();\n",
     "static int KYTY_SYSV_ABI sceInvitationDialogOpen(const void* param) {\n»PRINT_NAME();\n" +
     inv_fallback("Bc5InvdOpen(param, &answer)")),
    ("Terminate", "static int KYTY_SYSV_ABI sceInvitationDialogTerminate() {\n»PRINT_NAME();\n",
     "static int KYTY_SYSV_ABI sceInvitationDialogTerminate() {\n»PRINT_NAME();\n" + INV_GATE +
     "»»return Bc5InvdTerminate();\n»}\n"),
    ("registration",) + registration("InitInvitationDialog_1", "Bc5InvdOn", INV_ENV),
) + held_registrations("Bc5InvdOn", "LibInvitationDialog", (
    ("WuuUhuKOxwQ", "sceInvitationDialogGetResultA"), ("sAxbHhAWMXM", "sceInvitationDialogOpenA")))
INV_BEFORE = ("#include <common/abi.h>\n", "static int g_status = 0;\n")
INV_AFTER = ("static int KYTY_SYSV_ABI sceInvitationDialogTerminate() {\n", "LIB_DEFINE(InitInvitationDialog_1) {\n")
INV_USES = (("Bc5InvdOn()", 9), ("Bc5InvdNoAnswer(", 5), ("Bc5InvdInitialize(", 2), ("Bc5InvdTerminate(", 2),
            ("Bc5InvdOpen(", 2), ("Bc5InvdClose(", 2), ("Bc5InvdGetResult(", 2), ("g_bc5_invd_callback_arg", 5),
            ("TODO(verify)", 1), ("static int KYTY_SYSV_ABI ", 9), ("LIB_FUNC(", 9))

# =====================================================================================================================
# src/libs/libWebBrowserDialog.cpp
# =====================================================================================================================
WBD_ENV = "KYTY_BC5_LOAD_WEBBROWSERDIALOG"
WBD_BLOCK_ANCHOR = "static int KYTY_SYSV_ABI sceWebBrowserDialogClose() {\n"
WBD_BLOCK = r"""// ---- BC5 experiment 0405 (series e7 of experiment 0401), tag "tbd": KYTY_BC5_LOAD_WEBBROWSERDIALOG, libSceWebBrowserDialog ported ----
// Exp 0405 decision 4 (the tables compiled but never loaded): this table is ported first, then loaded by Libs::InitAll
// when KYTY_BC5_LOAD_WEBBROWSERDIALOG is on (libs.cpp, the loader agent "tl2"). No other table registers its 12 NIDs.
// Ported in adapted form from """ + SOURCE + r""", core/libs/prx/libSceWebBrowserDialog/Export.cpp:34-154
// (the layouts: core/libs/prx/libSceCommonDialog/CommonDialog.hpp:207-234, include/Api.hpp:6-16), and its note
// docs/dev/debt/libSceWebBrowserDialog.md:6-7:
//   Open, OpenForPredeterminedContent: no browser is shown; the dialog is finished at once (status 3) and marked open.
//     OpenForPredeterminedContent first checks its allow list (424 bytes: the size at 0; twenty optional address pointers
//     from 8, each of 1-255 characters, at least one; 256 reserved bytes from 168, all zero): ARG_NULL (0x80B8000D) for
//     no list, PARAMETER (0x80B8000A) for a bad one; then ARG_NULL for a null param. Open: ARG_NULL for a null param.
//   UpdateStatus: returns the status; a finished dialog is no longer marked open.
//   Close: no longer marked open; NOT_RUNNING (0x80B8000B) unless running.
//   GetResult: ARG_NULL; PARAMETER for a non-zero reserved byte (16-255) or, when the extended result pointer (at 8) is
//     set, an extended size (at 0) other than 2096 or a non-zero byte at 2060-2063 or 2076-2095; NOT_FINISHED
//     (0x80B80005) unless finished; then 0, with the result USER_CANCELED (1) at 0. AnyPS5 does not say where these
//     layouts and checks come from: TODO(verify).
//   SetCookie, ResetCookie: there is no cookie store: they check and return 0. INVALID_STATE (0x80B80006) while marked
//     open; ARG_NULL; PARAMETER for a size (at 0) other than 280 / 264, a non-zero reserved byte (24-279 / 8-263) or, for
//     SetCookie, an address (pointer at 8) not of 1-0x7FF characters or a cookie (pointer at 16) not of 1-0xFFF. SetCookie
//     checks the open mark before the null param, ResetCookie after it. Note :7, quoted: "Both calls check their
//     parameters in the same order and with the same codes as the PS5 13.60 module" (a module reading: exp 0405
//     decision 1, accepted).
// Split state: Initialize (jqb7HntFQFc) and Terminate (ocHtyBwHfys) are the live table's (libNet.cpp:4240-4261), which
// keeps no state, so this file cannot tell none (0) from initialized (1). Held: every NOT_INITIALIZED (0x80B80003) answer;
// status 0 is answered as initialized (a title that called Initialize first). GetStatus and UpdateStatus still give 0
// there (AnyPS5: 1). After the live Terminate the status here stays as it was (AnyPS5: 0), and the open mark stays until
// UpdateStatus or Close clears it. Not ported: Open's BUSY for a running dialog (nothing sets running while on, and
// AnyPS5's value 0x80B80007 is shadPS4's RESULT_NONE, src/core/libraries/system/commondialog.h:34 @ 60c42b9:
// TODO(verify)); AnyPS5's opt-in host notice on Open (host UI only).
// Already match (not edited): GetStatus returns the status. Held (AnyPS5 does not implement them): GetEvent, Navigate,
// SetZoom, Func_F2BE042771625F8C.
// KYTY_BC5_LOAD_WEBBROWSERDIALOG: unset, empty or "0" is off (today's answers); any other value is on. Read once; one
// stderr line at registration or at the first call.
""" + HELD_NOTE + LICENCE + r"""static constexpr int      BC5_WBD_ERROR_NOT_FINISHED       = static_cast<int>(0x80B80005u);
static constexpr int      BC5_WBD_ERROR_INVALID_STATE      = static_cast<int>(0x80B80006u);
static constexpr int      BC5_WBD_ERROR_PARAMETER          = static_cast<int>(0x80B8000Au);
static constexpr int      BC5_WBD_ERROR_NOT_RUNNING        = static_cast<int>(0x80B8000Bu);
static constexpr int      BC5_WBD_ERROR_ARG_NULL           = static_cast<int>(0x80B8000Du);
static constexpr int      BC5_WBD_STATUS_RUNNING           = 2;
static constexpr int      BC5_WBD_STATUS_FINISHED          = 3;
static constexpr int32_t  BC5_WBD_RESULT_USER_CANCELED     = 1;
static constexpr size_t   BC5_WBD_RESULT_EXTENDED_AT       = 8;    // the result: the optional extended result pointer
static constexpr size_t   BC5_WBD_RESULT_RESERVED_AT       = 16;   // ... reserved bytes up to its end
static constexpr size_t   BC5_WBD_RESULT_SIZE              = 256;
static constexpr uint64_t BC5_WBD_EXTENDED_SIZE            = 2096; // the extended result: its size, at 0
static constexpr size_t   BC5_WBD_EXTENDED_RESERVED_A_AT   = 2060; // ... reserved bytes 2060-2063
static constexpr size_t   BC5_WBD_EXTENDED_RESERVED_A_END  = 2064;
static constexpr size_t   BC5_WBD_EXTENDED_RESERVED_B_AT   = 2076; // ... reserved bytes 2076-2095
static constexpr uint64_t BC5_WBD_COOKIE_PARAM_SIZE        = 280;  // size at 0, address at 8, cookie at 16, reserved
static constexpr size_t   BC5_WBD_COOKIE_ADDRESS_AT        = 8;
static constexpr size_t   BC5_WBD_COOKIE_TEXT_AT           = 16;
static constexpr size_t   BC5_WBD_COOKIE_RESERVED_AT       = 24;
static constexpr size_t   BC5_WBD_COOKIE_ADDRESS_LIMIT     = 0x800;
static constexpr size_t   BC5_WBD_COOKIE_TEXT_LIMIT        = 0x1000;
static constexpr uint64_t BC5_WBD_RESET_COOKIE_PARAM_SIZE  = 264;  // size at 0, reserved
static constexpr size_t   BC5_WBD_RESET_COOKIE_RESERVED_AT = 8;
static constexpr uint64_t BC5_WBD_ALLOW_LIST_SIZE          = 424;  // size at 0, address pointers from 8, reserved
static constexpr size_t   BC5_WBD_ALLOW_LIST_ADDRESSES_AT  = 8;
static constexpr size_t   BC5_WBD_ALLOW_LIST_ADDRESSES     = 20;
static constexpr size_t   BC5_WBD_ALLOW_LIST_RESERVED_AT   = 168;
static constexpr size_t   BC5_WBD_ALLOW_ADDRESS_LIMIT      = 256;

static std::atomic<bool> g_bc5_wbd_open {false}; // the open mark: set by an Open, cleared by Close or a finished update

""" + switch_fn("Bc5WbdOn", WBD_ENV, "webbrowserdialog",
                "Open OpenForPredeterminedContent Close UpdateStatus GetResult SetCookie ResetCookie; "
                "NOT_INITIALIZED held: split state; GetEvent Navigate SetZoom F2BE held, not registered") + r"""
static uint64_t Bc5WbdWord(const void* base, size_t at) {
»uint64_t v = 0;
»std::memcpy(&v, static_cast<const uint8_t*>(base) + at, sizeof(v));
»return v;
}

static const char* Bc5WbdPointer(const void* base, size_t at) {
»const char* p = nullptr;
»std::memcpy(&p, static_cast<const uint8_t*>(base) + at, sizeof(p));
»return p;
}

static bool Bc5WbdZero(const void* base, size_t from, size_t to) {
»const auto* p = static_cast<const uint8_t*>(base);
»for (size_t i = from; i < to; i++) {
»»if (p[i] != 0) {
»»»return false;
»»}
»}
»return true;
}

// 1 to limit-1 characters before the terminator.
static bool Bc5WbdLengthWithin(const char* text, size_t limit) {
»if (text == nullptr) {
»»return false;
»}
»size_t n = 0;
»while (n < limit && text[n] != '\0') {
»»n++;
»}
»return n != 0 && n < limit;
}

static int Bc5WbdOpen(const void* param) {
»if (param == nullptr) {
»»return BC5_WBD_ERROR_ARG_NULL;
»}
»g_status       = BC5_WBD_STATUS_FINISHED; // no browser: finished at once, as if the user had cancelled
»g_bc5_wbd_open = true;
»return OK;
}

static int Bc5WbdOpenForPredeterminedContent(const void* param, const void* allow_list) {
»if (allow_list == nullptr) {
»»return BC5_WBD_ERROR_ARG_NULL;
»}
»if (Bc5WbdWord(allow_list, 0) != BC5_WBD_ALLOW_LIST_SIZE) {
»»return BC5_WBD_ERROR_PARAMETER;
»}
»bool any = false;
»for (size_t i = 0; i < BC5_WBD_ALLOW_LIST_ADDRESSES; i++) {
»»const char* address = Bc5WbdPointer(allow_list, BC5_WBD_ALLOW_LIST_ADDRESSES_AT + i * sizeof(void*));
»»if (address == nullptr) {
»»»continue;
»»}
»»any = true;
»»if (!Bc5WbdLengthWithin(address, BC5_WBD_ALLOW_ADDRESS_LIMIT)) {
»»»return BC5_WBD_ERROR_PARAMETER;
»»}
»}
»if (!any || !Bc5WbdZero(allow_list, BC5_WBD_ALLOW_LIST_RESERVED_AT, BC5_WBD_ALLOW_LIST_SIZE)) {
»»return BC5_WBD_ERROR_PARAMETER;
»}
»return Bc5WbdOpen(param);
}

static int Bc5WbdClose() {
»g_bc5_wbd_open = false;
»if (g_status != BC5_WBD_STATUS_RUNNING) {
»»return BC5_WBD_ERROR_NOT_RUNNING;
»}
»g_status = BC5_WBD_STATUS_FINISHED;
»return OK;
}

static int Bc5WbdUpdateStatus() {
»const int status = g_status;
»if (status == BC5_WBD_STATUS_FINISHED) {
»»g_bc5_wbd_open = false;
»}
»return status;
}

static int Bc5WbdGetResult(void* result) {
»if (result == nullptr) {
»»return BC5_WBD_ERROR_ARG_NULL;
»}
»if (!Bc5WbdZero(result, BC5_WBD_RESULT_RESERVED_AT, BC5_WBD_RESULT_SIZE)) {
»»return BC5_WBD_ERROR_PARAMETER;
»}
»const char* extended = Bc5WbdPointer(result, BC5_WBD_RESULT_EXTENDED_AT);
»if (extended != nullptr &&
»    (Bc5WbdWord(extended, 0) != BC5_WBD_EXTENDED_SIZE ||
»     !Bc5WbdZero(extended, BC5_WBD_EXTENDED_RESERVED_A_AT, BC5_WBD_EXTENDED_RESERVED_A_END) ||
»     !Bc5WbdZero(extended, BC5_WBD_EXTENDED_RESERVED_B_AT, BC5_WBD_EXTENDED_SIZE))) {
»»return BC5_WBD_ERROR_PARAMETER;
»}
»if (g_status != BC5_WBD_STATUS_FINISHED) {
»»return BC5_WBD_ERROR_NOT_FINISHED;
»}
»const int32_t cancelled = BC5_WBD_RESULT_USER_CANCELED;
»std::memcpy(result, &cancelled, sizeof(cancelled));
»return OK;
}

static int Bc5WbdSetCookie(const void* param) {
»if (g_bc5_wbd_open) {
»»return BC5_WBD_ERROR_INVALID_STATE;
»}
»if (param == nullptr) {
»»return BC5_WBD_ERROR_ARG_NULL;
»}
»if (Bc5WbdWord(param, 0) != BC5_WBD_COOKIE_PARAM_SIZE ||
»    !Bc5WbdLengthWithin(Bc5WbdPointer(param, BC5_WBD_COOKIE_ADDRESS_AT), BC5_WBD_COOKIE_ADDRESS_LIMIT) ||
»    !Bc5WbdLengthWithin(Bc5WbdPointer(param, BC5_WBD_COOKIE_TEXT_AT), BC5_WBD_COOKIE_TEXT_LIMIT) ||
»    !Bc5WbdZero(param, BC5_WBD_COOKIE_RESERVED_AT, BC5_WBD_COOKIE_PARAM_SIZE)) {
»»return BC5_WBD_ERROR_PARAMETER;
»}
»return OK; // no cookie store
}

static int Bc5WbdResetCookie(const void* param) {
»if (param == nullptr) {
»»return BC5_WBD_ERROR_ARG_NULL;
»}
»if (g_bc5_wbd_open) {
»»return BC5_WBD_ERROR_INVALID_STATE;
»}
»if (Bc5WbdWord(param, 0) != BC5_WBD_RESET_COOKIE_PARAM_SIZE ||
»    !Bc5WbdZero(param, BC5_WBD_RESET_COOKIE_RESERVED_AT, BC5_WBD_RESET_COOKIE_PARAM_SIZE)) {
»»return BC5_WBD_ERROR_PARAMETER;
»}
»return OK; // no cookie store
}
// ---- end of BC5 experiment 0405 (KYTY_BC5_LOAD_WEBBROWSERDIALOG) ----

"""

WBD_GATE = "»if (Bc5WbdOn()) { // BC5 experiment 0405 (KYTY_BC5_LOAD_WEBBROWSERDIALOG); false when off\n"


def wbd_gate(call):
    return WBD_GATE + f"»»return {call};\n»}}\n"


WBD_EDITS = (
    ("includes", "#include <common/abi.h>\n",
     "#include <common/abi.h>\n"
     "\n"
     "#include <atomic> // BC5 experiment 0405 (KYTY_BC5_LOAD_WEBBROWSERDIALOG): these includes\n"
     "#include <cstddef>\n"
     "#include <cstdint>\n"
     "#include <cstdio>\n"
     "#include <cstdlib>\n"
     "#include <cstring>\n"),
    ("Close", "static int KYTY_SYSV_ABI sceWebBrowserDialogClose() {\n»PRINT_NAME();\n",
     "static int KYTY_SYSV_ABI sceWebBrowserDialogClose() {\n»PRINT_NAME();\n" + wbd_gate("Bc5WbdClose()")),
    ("GetResult", "static int KYTY_SYSV_ABI sceWebBrowserDialogGetResult() {\n\n\n»PRINT_NAME();\n",
     "static int KYTY_SYSV_ABI sceWebBrowserDialogGetResult(void* result) {\n\n\n»PRINT_NAME();\n" +
     wbd_gate("Bc5WbdGetResult(result)")),
    ("Open", "static int KYTY_SYSV_ABI sceWebBrowserDialogOpen() {\n»PRINT_NAME();\n",
     "static int KYTY_SYSV_ABI sceWebBrowserDialogOpen(const void* param) {\n»PRINT_NAME();\n" +
     wbd_gate("Bc5WbdOpen(param)")),
    ("OpenForPredeterminedContent", "static int KYTY_SYSV_ABI sceWebBrowserDialogOpenForPredeterminedContent() {\n»PRINT_NAME();\n",
     "static int KYTY_SYSV_ABI sceWebBrowserDialogOpenForPredeterminedContent(const void* param, const void* allow_list) {\n"
     "»PRINT_NAME();\n" + wbd_gate("Bc5WbdOpenForPredeterminedContent(param, allow_list)")),
    ("ResetCookie", "static int KYTY_SYSV_ABI sceWebBrowserDialogResetCookie() {\n\n\n»PRINT_NAME();\n",
     "static int KYTY_SYSV_ABI sceWebBrowserDialogResetCookie(const void* param) {\n\n\n»PRINT_NAME();\n" +
     wbd_gate("Bc5WbdResetCookie(param)")),
    ("SetCookie", "static int KYTY_SYSV_ABI sceWebBrowserDialogSetCookie() {\n\n\n»PRINT_NAME();\n",
     "static int KYTY_SYSV_ABI sceWebBrowserDialogSetCookie(const void* param) {\n\n\n»PRINT_NAME();\n" +
     wbd_gate("Bc5WbdSetCookie(param)")),
    ("UpdateStatus", "static int KYTY_SYSV_ABI sceWebBrowserDialogUpdateStatus() {\n»PRINT_NAME();\n",
     "static int KYTY_SYSV_ABI sceWebBrowserDialogUpdateStatus() {\n»PRINT_NAME();\n" + wbd_gate("Bc5WbdUpdateStatus()")),
    ("registration",) + registration("InitWebBrowserDialog_1", "Bc5WbdOn", WBD_ENV),
) + held_registrations("Bc5WbdOn", "LibWebBrowserDialog", (
    ("Wit4LjeoeX4", "sceWebBrowserDialogGetEvent"), ("uYELOMVnmNQ", "sceWebBrowserDialogNavigate"),
    ("RLhKBOoNyXY", "sceWebBrowserDialogSetZoom"), ("8r4EJ3FiX4w", "Func_F2BE042771625F8C")))
WBD_BEFORE = ("#include <common/abi.h>\n", "static int g_status = 0;\n")
WBD_AFTER = ("static int KYTY_SYSV_ABI sceWebBrowserDialogUpdateStatus() {\n", "LIB_DEFINE(InitWebBrowserDialog_1) {\n")
WBD_USES = (("Bc5WbdOn()", 13), ("Bc5WbdOpen(", 3), ("Bc5WbdOpenForPredeterminedContent(", 2), ("Bc5WbdClose(", 2),
            ("Bc5WbdUpdateStatus(", 2), ("Bc5WbdGetResult(", 2), ("Bc5WbdSetCookie(", 2), ("Bc5WbdResetCookie(", 2),
            ("Bc5WbdWord(", 5), ("Bc5WbdPointer(", 5), ("Bc5WbdZero(", 7), ("Bc5WbdLengthWithin(", 4),
            ("g_bc5_wbd_open", 6), ("TODO(verify)", 2), ("static int KYTY_SYSV_ABI ", 12), ("LIB_FUNC(", 12))

# =====================================================================================================================
# src/libs/libSharePlay.cpp
# =====================================================================================================================
SHP_ENV = "KYTY_BC5_LOAD_SHAREPLAY"
SHP_BLOCK_ANCHOR = "static int KYTY_SYSV_ABI sceSharePlayCrashDaemon() {\n"
SHP_BLOCK = r"""// ---- BC5 experiment 0405 (series e7 of experiment 0401), tag "tbd": KYTY_BC5_LOAD_SHAREPLAY, libSceSharePlay ported ----
// Exp 0405 decision 4 (the tables compiled but never loaded): this table is ported first, then loaded by Libs::InitAll
// when KYTY_BC5_LOAD_SHAREPLAY is on (libs.cpp, the loader agent "tl2"). No other table registers its 22 NIDs.
// Ported in adapted form from """ + SOURCE + r""", core/libs/prx/libSceSharePlay/Export.cpp:34-42,56-64
// (the layouts: core/libs/SceTypes.hpp:1496-1515), and its note docs/dev/debt/libSceSharePlay.md:13-14: with no Share
// Play session, GetCurrentConnectionInfoA clears its 72-byte info and sets both user ids (at 64 and 68) to -1, and
// GetCurrentConnectionInfo does the same for its 56-byte info (user ids at 48 and 52; the layout of shadPS4's
// shareplay.h); a null info gives INVALID_ARGS (0x810E0001). Note :13, quoted: "the native module confirms a 72-byte
// result, initial zero fields and both user IDs -1" (exp 0405 decision 1, accepted); its commit 0d2eeb87e: KytyPS5 and
// fpPS4 agree on the layout and the error code.
// Split state: Initialize (isruqthpYcw) and Terminate (UaLjloJinow) are the live table's (libNet.cpp:4288-4313), which
// keeps no state. Held: the NOT_INITIALIZED (0x810E0004) answer AnyPS5 gives before Initialize; the info is filled as for
// an initialized library. Held (AnyPS5 does not implement them; NotifyOpenQuickMenu is not in it): the other 20 calls.
// KYTY_BC5_LOAD_SHAREPLAY: unset, empty or "0" is off (today's answers); any other value is on. Read once; one stderr
// line at registration or at the first call.
""" + HELD_NOTE + LICENCE + r"""static constexpr int     BC5_SHP_ERROR_INVALID_ARGS = static_cast<int>(0x810E0001u);
static constexpr int32_t BC5_SHP_USER_ID_NONE       = -1;
static constexpr size_t  BC5_SHP_INFO_SIZE          = 56; // the host's and the visitor's user ids at 48 and 52
static constexpr size_t  BC5_SHP_INFO_USERS_AT      = 48;
static constexpr size_t  BC5_SHP_INFO_A_SIZE        = 72; // with the two account ids; the user ids at 64 and 68
static constexpr size_t  BC5_SHP_INFO_A_USERS_AT    = 64;

""" + switch_fn("Bc5ShpOn", SHP_ENV, "shareplay",
                "GetCurrentConnectionInfo GetCurrentConnectionInfoA; NOT_INITIALIZED held: split state; "
                "20 held, not registered") + r"""
// No Share Play session: every field zero, both user ids none.
static int Bc5ShpConnectionInfo(void* info, size_t size, size_t users_at) {
»if (info == nullptr) {
»»return BC5_SHP_ERROR_INVALID_ARGS;
»}
»auto* p = static_cast<uint8_t*>(info);
»std::memset(p, 0, size);
»const int32_t none = BC5_SHP_USER_ID_NONE;
»std::memcpy(p + users_at, &none, sizeof(none));
»std::memcpy(p + users_at + sizeof(none), &none, sizeof(none));
»return OK;
}
// ---- end of BC5 experiment 0405 (KYTY_BC5_LOAD_SHAREPLAY) ----

"""

SHP_GATE = "»if (Bc5ShpOn()) { // BC5 experiment 0405 (KYTY_BC5_LOAD_SHAREPLAY); false when off\n"
SHP_EDITS = (
    ("includes", "#include <common/abi.h>\n",
     "#include <common/abi.h>\n"
     "\n"
     "#include <cstddef> // BC5 experiment 0405 (KYTY_BC5_LOAD_SHAREPLAY): these includes\n"
     "#include <cstdint>\n"
     "#include <cstdio>\n"
     "#include <cstdlib>\n"
     "#include <cstring>\n"),
    ("GetCurrentConnectionInfo", "static int KYTY_SYSV_ABI sceSharePlayGetCurrentConnectionInfo() {\n»PRINT_NAME();\n",
     "static int KYTY_SYSV_ABI sceSharePlayGetCurrentConnectionInfo(void* info) {\n»PRINT_NAME();\n" + SHP_GATE +
     "»»return Bc5ShpConnectionInfo(info, BC5_SHP_INFO_SIZE, BC5_SHP_INFO_USERS_AT);\n»}\n"),
    ("GetCurrentConnectionInfoA", "static int KYTY_SYSV_ABI sceSharePlayGetCurrentConnectionInfoA() {\n»PRINT_NAME();\n",
     "static int KYTY_SYSV_ABI sceSharePlayGetCurrentConnectionInfoA(void* info) {\n»PRINT_NAME();\n" + SHP_GATE +
     "»»return Bc5ShpConnectionInfo(info, BC5_SHP_INFO_A_SIZE, BC5_SHP_INFO_A_USERS_AT);\n»}\n"),
    ("registration",) + registration("InitSharePlay_1", "Bc5ShpOn", SHP_ENV),
) + held_registrations("Bc5ShpOn", "LibSharePlay", (
    ("ggnCfalLU-8", "sceSharePlayCrashDaemon"), ("vUMkWXQff3w", "sceSharePlayGetCurrentInfo"),
    ("Md7Mdkr8LBc", "sceSharePlayGetEvent"), ("9zwJpai7jGc", "sceSharePlayNotifyDialogOpen"),
    ("VUW2V9cUTP4", "sceSharePlayNotifyForceCloseForCdlg"), ("XL0WwUJoQPg", "sceSharePlayNotifyOpenQuickMenu"),
    ("6-1fKaa5HlY", "sceSharePlayResumeScreenForCdlg"), ("U28jAuLHj6c", "sceSharePlayServerLock"),
    ("3Oaux9ITEtY", "sceSharePlayServerUnLock"), ("QZy+KmyqKPU", "sceSharePlaySetMode"),
    ("co2NCj--pnc", "sceSharePlaySetProhibition"), ("KADsbjNCgPo", "sceSharePlaySetProhibitionModeWithAppId"),
    ("-F6NddfUsa4", "sceSharePlayStartStandby"), ("rWVNHNnEx6g", "sceSharePlayStartStreaming"),
    ("zEDkUWLVwFI", "sceSharePlayStopStandby"), ("aGlema+JxUU", "sceSharePlayStopStreaming"),
    ("LpPA6mprZ8Q", "Func_2E93C0EA6A6B67C4"), ("wcI2co2I4Xc", "Func_C1C236728D88E177"),
    ("6egMR0eB8RU", "Func_E9E80C474781F115"), ("891hmdoV7UQ", "Func_F3DD6199DA15ED44")))
SHP_BEFORE = ("#include <common/abi.h>\n", "LIB_VERSION(\"libSceSharePlay\", 1, \"libSceSharePlay\", 1, 1);\n")
SHP_AFTER = ("static int KYTY_SYSV_ABI sceSharePlayGetCurrentConnectionInfoA() {\n", "LIB_DEFINE(InitSharePlay_1) {\n")
SHP_USES = (("Bc5ShpOn()", 24), ("Bc5ShpConnectionInfo(", 3), ("static int KYTY_SYSV_ABI ", 22), ("LIB_FUNC(", 22))

# =====================================================================================================================
# src/libs/libGameLiveStreaming.cpp
# =====================================================================================================================
GLS_ENV = "KYTY_BC5_LOAD_GAMELIVESTREAMING"
GLS_BLOCK_ANCHOR = "static int KYTY_SYSV_ABI sceGameLiveStreamingStartDebugBroadcast() {\n"
GLS_BLOCK = r"""// ---- BC5 experiment 0405 (series e7 of experiment 0401), tag "tbd": KYTY_BC5_LOAD_GAMELIVESTREAMING, libSceGameLiveStreaming ported ----
// Exp 0405 decision 4 (the tables compiled but never loaded): this table is ported first, then loaded by Libs::InitAll
// when KYTY_BC5_LOAD_GAMELIVESTREAMING is on (libs.cpp, the loader agent "tl2"). No other table registers its 45 NIDs.
// Ported in adapted form from """ + SOURCE + r""",
// core/libs/prx/libSceGameLiveStreaming/Export.cpp:14-38,59-85,135-222,234-239 (the layouts: include/Api.hpp:9-61), and
// its note docs/dev/debt/libSceGameLiveStreaming.md (each a module run or reading: exp 0405 decision 1, accepted):
//   :7  GetCurrentStatus2: the 72-byte status is cleared and its user id (at 0) set to -1: nothing on air. Quoted: "the
//       supplied module confirms the 72-byte layout and inactive status" (the layout is shadPS4's, GPL-2.0-or-later @
//       60c42b9, src/core/libraries/game_live_streaming/gamelivestreaming.h:22-31).
//   :8  GetProgramInfo: quoted, "the PS5 13.60 module clears the 0x134C-byte program info ... and returns 0x80A00002 for
//       a null pointer"; nothing is broadcast here, so it stays zero.
//   :17 ScreenInitializeSeparateModeParameter: quoted, "read from its disassembly and run natively on x86-64": a null
//       pointer gives 0x80A00002, otherwise bytes 0-67 are cleared; it does not need Initialize.
//   :12 the setting, feedback and message calls; quoted, their checks "come from a report on #9524 that ran each function
//       of the firmware 13.42 module with the service call stubbed": INVALID_ARGUMENT (0x80A00002) for a null pointer, a
//       feedback type outside 1-3, a string longer than 240 (metadata), 720 (preset description), 45 (invitation session
//       id) or 360 (social message) characters, more than 16 spoiler tags or 5 preset commands, or a non-zero byte in
//       the 31-byte tail of a 224-byte spoiler tag (from 193), of a 228-byte preset command (from 197) or of the camera
//       frame setting (from 9); otherwise 0, storing nothing; the message queries report no messages. Quoted: "The order
//       between argument checks, the camera setting size and the other struct fields are not measured": TODO(verify).
// Split state: Initialize (kvYEw2lBndk) and Terminate (9yK6Fk8mKOQ) are the live table's (libNet.cpp:4263-4286), which
// keeps no state. Held: the NOT_INITIALIZED (0x80A00004) answer AnyPS5 gives before Initialize; every call answers as
// for an initialized library. Already match for an initialized library (not edited: 0, nothing stored):
// PermitLiveStreaming, SetMaxBitrate, EnableSocialFeedback, PermitServerSideRecording, ClearSpoilerTag,
// ClearPresetSocialFeedbackCommands, EnableLiveStreaming (which AnyPS5 throws for before Initialize). Held (AnyPS5 does
// not implement them): the other 25 calls, GetCurrentStatus among them.
// KYTY_BC5_LOAD_GAMELIVESTREAMING: unset, empty or "0" is off (today's answers); any other value is on. Read once; one
// stderr line at registration or at the first call.
""" + HELD_NOTE + LICENCE + r"""static constexpr int     BC5_GLS_ERROR_INVALID_ARGUMENT        = static_cast<int>(0x80A00002u);
static constexpr int32_t BC5_GLS_USER_ID_NONE                  = -1;
static constexpr size_t  BC5_GLS_STATUS2_SIZE                  = 72;     // the user id at 0, the rest zero
static constexpr size_t  BC5_GLS_PROGRAM_INFO_SIZE             = 0x134C; // all zero: nothing is broadcast
static constexpr size_t  BC5_GLS_SEPARATE_MODE_PARAMETER_SIZE  = 68;
static constexpr int     BC5_GLS_FEEDBACK_TYPE_FIRST           = 1;
static constexpr int     BC5_GLS_FEEDBACK_TYPE_LAST            = 3;
static constexpr size_t  BC5_GLS_METADATA_MAX                  = 240; // characters before the terminator
static constexpr size_t  BC5_GLS_DESCRIPTION_MAX               = 720;
static constexpr size_t  BC5_GLS_SESSION_ID_MAX                = 45;
static constexpr size_t  BC5_GLS_MESSAGE_MAX                   = 360;
static constexpr size_t  BC5_GLS_SPOILER_TAGS_MAX              = 16;
static constexpr size_t  BC5_GLS_SPOILER_TAG_SIZE              = 224; // a zero tail from 193
static constexpr size_t  BC5_GLS_SPOILER_TAG_TAIL              = 193;
static constexpr size_t  BC5_GLS_PRESET_COMMANDS_MAX           = 5;
static constexpr size_t  BC5_GLS_PRESET_COMMAND_SIZE           = 228; // a zero tail from 197
static constexpr size_t  BC5_GLS_PRESET_COMMAND_TAIL           = 197;
static constexpr size_t  BC5_GLS_CAMERA_SETTING_SIZE           = 40;  // a zero tail from 9: TODO(verify) the size
static constexpr size_t  BC5_GLS_CAMERA_SETTING_TAIL           = 9;

""" + switch_fn("Bc5GlsOn", GLS_ENV, "gamelivestreaming",
                "GetCurrentStatus2 GetProgramInfo ScreenInitializeSeparateModeParameter and 10 argument checks; "
                "NOT_INITIALIZED held: split state; 7 match; 25 held, not registered") + r"""
static int Bc5GlsGetCurrentStatus2(void* status) {
»if (status == nullptr) {
»»return BC5_GLS_ERROR_INVALID_ARGUMENT;
»}
»std::memset(status, 0, BC5_GLS_STATUS2_SIZE);
»const int32_t none = BC5_GLS_USER_ID_NONE;
»std::memcpy(status, &none, sizeof(none)); // the user id, at 0
»return OK;
}

// GetProgramInfo and ScreenInitializeSeparateModeParameter: the first size bytes cleared.
static int Bc5GlsClear(void* out, size_t size) {
»if (out == nullptr) {
»»return BC5_GLS_ERROR_INVALID_ARGUMENT;
»}
»std::memset(out, 0, size);
»return OK;
}

static int Bc5GlsCheckFeedbackType(int type) {
»return (type >= BC5_GLS_FEEDBACK_TYPE_FIRST && type <= BC5_GLS_FEEDBACK_TYPE_LAST) ? OK : BC5_GLS_ERROR_INVALID_ARGUMENT;
}

static int Bc5GlsFeedbackCount(int type, uint32_t* count) {
»if (count == nullptr || Bc5GlsCheckFeedbackType(type) != OK) {
»»return BC5_GLS_ERROR_INVALID_ARGUMENT;
»}
»*count = 0; // nothing on air, no messages
»return OK;
}

static int Bc5GlsFeedbackMessages(int type, const void* messages, size_t* acquired) {
»if (messages == nullptr || acquired == nullptr || Bc5GlsCheckFeedbackType(type) != OK) {
»»return BC5_GLS_ERROR_INVALID_ARGUMENT;
»}
»*acquired = 0;
»return OK;
}

// A string of at most max characters before its terminator.
static int Bc5GlsCheckText(const char* text, size_t max) {
»if (text == nullptr) {
»»return BC5_GLS_ERROR_INVALID_ARGUMENT;
»}
»for (size_t i = 0; i <= max; i++) {
»»if (text[i] == '\0') {
»»»return OK;
»»}
»}
»return BC5_GLS_ERROR_INVALID_ARGUMENT;
}

// count entries of size bytes, at most max_count, each with zero bytes from tail to its end.
static int Bc5GlsCheckEntries(const void* entries, size_t count, size_t max_count, size_t size, size_t tail) {
»if (entries == nullptr || count > max_count) {
»»return BC5_GLS_ERROR_INVALID_ARGUMENT;
»}
»const auto* p = static_cast<const uint8_t*>(entries);
»for (size_t i = 0; i < count; i++) {
»»for (size_t k = tail; k < size; k++) {
»»»if (p[i * size + k] != 0) {
»»»»return BC5_GLS_ERROR_INVALID_ARGUMENT;
»»»}
»»}
»}
»return OK;
}
// ---- end of BC5 experiment 0405 (KYTY_BC5_LOAD_GAMELIVESTREAMING) ----

"""

GLS_GATE = "»if (Bc5GlsOn()) { // BC5 experiment 0405 (KYTY_BC5_LOAD_GAMELIVESTREAMING); false when off\n"
GLS_PORTS = (  # name, parameters, the port's call
    ("GetCurrentStatus2", "void* status", "Bc5GlsGetCurrentStatus2(status)"),
    ("GetProgramInfo", "void* info", "Bc5GlsClear(info, BC5_GLS_PROGRAM_INFO_SIZE)"),
    ("ScreenInitializeSeparateModeParameter", "void* parameter",
     "Bc5GlsClear(parameter, BC5_GLS_SEPARATE_MODE_PARAMETER_SIZE)"),
    ("GetSocialFeedbackMessagesCount", "int type, uint32_t* count", "Bc5GlsFeedbackCount(type, count)"),
    ("GetSocialFeedbackMessages", "int type, size_t /*capacity*/, void* messages, size_t* acquired",
     "Bc5GlsFeedbackMessages(type, messages, acquired)"),
    ("SetMetadata", "const char* metadata", "Bc5GlsCheckText(metadata, BC5_GLS_METADATA_MAX)"),
    ("SetSpoilerTag", "size_t count, const void* tags",
     "Bc5GlsCheckEntries(tags, count, BC5_GLS_SPOILER_TAGS_MAX, BC5_GLS_SPOILER_TAG_SIZE, BC5_GLS_SPOILER_TAG_TAIL)"),
    ("SetPresetSocialFeedbackCommands", "size_t count, const void* commands",
     "Bc5GlsCheckEntries(commands, count, BC5_GLS_PRESET_COMMANDS_MAX, BC5_GLS_PRESET_COMMAND_SIZE,\n"
     "»»                          BC5_GLS_PRESET_COMMAND_TAIL)"),
    ("SetPresetSocialFeedbackCommandsDescription", "const char* description",
     "Bc5GlsCheckText(description, BC5_GLS_DESCRIPTION_MAX)"),
    ("ClearSocialFeedbackMessages", "int type", "Bc5GlsCheckFeedbackType(type)"),
    ("PostSocialMessage", "const char* message", "Bc5GlsCheckText(message, BC5_GLS_MESSAGE_MAX)"),
    ("SetCameraFrameSetting", "const void* setting",
     "Bc5GlsCheckEntries(setting, 1, 1, BC5_GLS_CAMERA_SETTING_SIZE, BC5_GLS_CAMERA_SETTING_TAIL)"),
    ("SetInvitationSessionId", "const char* session_id", "Bc5GlsCheckText(session_id, BC5_GLS_SESSION_ID_MAX)"),
)
GLS_EDITS = (
    ("includes", "#include <common/abi.h>\n",
     "#include <common/abi.h>\n"
     "\n"
     "#include <cstddef> // BC5 experiment 0405 (KYTY_BC5_LOAD_GAMELIVESTREAMING): these includes\n"
     "#include <cstdint>\n"
     "#include <cstdio>\n"
     "#include <cstdlib>\n"
     "#include <cstring>\n"),
) + tuple(
    (name, f"static int KYTY_SYSV_ABI sceGameLiveStreaming{name}() {{\n\n\n»PRINT_NAME();\n",
     f"static int KYTY_SYSV_ABI sceGameLiveStreaming{name}({params}) {{\n\n\n»PRINT_NAME();\n" + GLS_GATE +
     f"»»return {call};\n»}}\n")
    for name, params, call in GLS_PORTS) + (
    ("registration",) + registration("InitGameLiveStreaming_1", "Bc5GlsOn", GLS_ENV),
) + held_registrations("Bc5GlsOn", "LibGameLiveStreaming", tuple((nid, "sceGameLiveStreaming" + name) for nid, name in (
    ("caqgDl+V9qA", "StartDebugBroadcast"), ("0i8Lrllxwow", "StopDebugBroadcast"),
    ("NqkTzemliC0", "ApplySocialFeedbackMessageFilter"), ("PC4jq87+YQI", "CheckCallback"),
    ("aRSQNqbats4", "GetCurrentBroadcastScreenLayout"), ("CoPMx369EqM", "GetCurrentStatus"),
    ("ysWfX5PPbfc", "LaunchLiveViewer"), ("cvRCb7DTAig", "LaunchLiveViewerA"), ("nFP8qT9YXbo", "RegisterCallback"),
    ("b5RaMD2J0So", "ScreenCloseSeparateMode"), ("hBdd8n6kuvE", "ScreenConfigureSeparateMode"),
    ("uhCmn81s-mU", "ScreenInitialize"), ("iorzW0pKOiA", "ScreenOpenSeparateMode"), ("gDSvt78H3Oo", "ScreenSetMode"),
    ("HE93dr-5rx4", "ScreenTerminate"), ("TwuUzTKKeek", "SetDefaultServiceProviderPermission"),
    ("Gw6S4oqlY7E", "SetGuardAreas"), ("Sb5bAXyUt5c", "SetLinkCommentPreset"),
    ("mCoz3k3zPmA", "SetServiceProviderPermission"), ("MLvYI86FFAo", "SetStandbyScreenResource"),
    ("y0KkAydy9xE", "StartGenerateStandbyScreenResource"), ("Y1WxX7dPMCw", "StartSocialFeedbackMessageFiltering"),
    ("D7dg5QJ4FlE", "StopGenerateStandbyScreenResource"), ("bYuGUBuIsaY", "StopSocialFeedbackMessageFiltering"),
    ("5XHaH3kL+bA", "UnregisterCallback"))))
GLS_BEFORE = ("#include <common/abi.h>\n",
              "LIB_VERSION(\"libSceGameLiveStreaming\", 1, \"libSceGameLiveStreaming\", 1, 1);\n")
GLS_AFTER = ("static int KYTY_SYSV_ABI sceGameLiveStreamingGetCurrentStatus2() {\n",
             "static int KYTY_SYSV_ABI sceGameLiveStreamingSetInvitationSessionId() {\n",
             "LIB_DEFINE(InitGameLiveStreaming_1) {\n")
GLS_USES = (("Bc5GlsOn()", 40), ("Bc5GlsGetCurrentStatus2(", 2), ("Bc5GlsClear(", 3), ("Bc5GlsCheckFeedbackType(", 4),
            ("Bc5GlsFeedbackCount(", 2), ("Bc5GlsFeedbackMessages(", 2), ("Bc5GlsCheckText(", 5),
            ("Bc5GlsCheckEntries(", 4), ("TODO(verify)", 2), ("static int KYTY_SYSV_ABI ", 45), ("LIB_FUNC(", 45))

UNITS = (
    # rel, crlf, block anchor, block, edits, defined-before, used-after, helper uses
    ("src/libs/libInvitationDialog.cpp", False, INV_BLOCK_ANCHOR, INV_BLOCK, INV_EDITS, INV_BEFORE, INV_AFTER, INV_USES),
    ("src/libs/libWebBrowserDialog.cpp", False, WBD_BLOCK_ANCHOR, WBD_BLOCK, WBD_EDITS, WBD_BEFORE, WBD_AFTER, WBD_USES),
    ("src/libs/libSharePlay.cpp", False, SHP_BLOCK_ANCHOR, SHP_BLOCK, SHP_EDITS, SHP_BEFORE, SHP_AFTER, SHP_USES),
    ("src/libs/libGameLiveStreaming.cpp", False, GLS_BLOCK_ANCHOR, GLS_BLOCK, GLS_EDITS, GLS_BEFORE, GLS_AFTER, GLS_USES),
)
assert sorted(u[0] for u in UNITS) == sorted(PINNED), "every unit has exactly one pinned md5"


def balance(b):
    return (b.count(b"{") - b.count(b"}"), b.count(b"(") - b.count(b")"), b.count(b"[") - b.count(b"]"))


def md5(b):
    return hashlib.md5(b).hexdigest()


def edit_unit(rel, s, crlf, anchor, block, edits, before, after, uses):
    for m in MARKS:
        assert m not in s, ("the unit has the edit already", rel, m)
    assert (b"\r\n" in s) == crlf, ("line ends are not the expected ones", rel)
    if not crlf:
        assert b"\r" not in s, ("a CR in an LF unit", rel)
    A = T(anchor, crlf)
    B = T(block, crlf)
    assert balance(B) == (0, 0, 0), ("the block is not balanced", rel, balance(B))
    assert s.count(A) == 1, ("the block's anchor", rel, s.count(A))
    at = s.index(A)
    for b in before:
        bb = T(b, crlf)
        assert s.count(bb) == 1 and s.index(bb) < at, ("must be defined before the block, once", rel, b[:70], s.count(bb))
    for b in after:
        bb = T(b, crlf)
        assert s.count(bb) == 1 and s.index(bb) > at, ("must come after the block, once", rel, b[:70], s.count(bb))
    out = s.replace(A, B + A)
    done = []
    for what, old, new in edits:
        o, n = T(old, crlf), T(new, crlf)
        assert out.count(o) == 1, ("anchor", rel, what, out.count(o))
        assert s.count(o) == 1, ("anchor in the input", rel, what, s.count(o))
        assert balance(o) == balance(n), ("the edit changes the balance", rel, what, balance(o), balance(n))
        assert what.startswith("held ") or n.startswith(o.split(b"(")[0]), ("an edit keeps its function's name", rel, what)
        assert not what.startswith("held ") or n.count(o.lstrip(b"\t")) == 1, ("a held line keeps its LIB_FUNC", rel, what)
        out = out.replace(o, n)
        done.append((o, n))
    assert balance(out) == balance(s), ("the unit's balance changed", rel, balance(s), balance(out))
    for name, n in uses:
        c = out.count(name.encode("ascii"))
        assert c == n, ("helper uses", rel, name, c, n)
    # Undo the edits on the output (last first) and the block: the input must come back byte for byte.
    back = out
    for o, n in reversed(done):
        assert back.count(n) == 1, ("undo", rel, n[:60])
        back = back.replace(n, o)
    assert back.count(B) == 1
    back = back.replace(B, b"")
    assert back == s, ("undoing the edits does not give the input back", rel)
    # The inserted text is ASCII.
    B.decode("ascii")
    for o, n in done:
        n.decode("ascii")
    if crlf:
        assert out.count(b"\n") == out.count(b"\r\n"), ("a bare LF in the CRLF unit", rel)
    else:
        assert b"\r" not in out, ("a CR in the LF unit", rel)
    assert out.startswith(b"\xef\xbb\xbf") == s.startswith(b"\xef\xbb\xbf"), ("the BOM changed", rel)
    return out


def main():
    assert len(sys.argv) == 3, __doc__
    root, outdir = sys.argv[1], sys.argv[2]
    assert os.path.abspath(root) != os.path.abspath(outdir), "the out dir must not be the tree"
    outs = []
    for rel, crlf, anchor, block, edits, before, after, uses in UNITS:
        with open(os.path.join(root, rel), "rb") as f:
            s = f.read()
        for m in MARKS:
            assert m not in s, ("refused: the unit has the edit already", rel, m.decode())
        assert md5(s) == PINNED[rel], ("refused: not the pinned input", rel, md5(s), PINNED[rel])
        out = edit_unit(rel, s, crlf, anchor, block, edits, before, after, uses)
        print(f"# in:  {rel} {md5(s)}  ({len(s)} bytes, {'CRLF' if crlf else 'LF'})", file=sys.stderr)
        outs.append((rel, out))
    for rel, out in outs:  # written only when all four are done
        dst = os.path.join(outdir, rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        with open(dst, "wb") as f:
            f.write(out)
        print(f"{rel} {md5(out)}")


if __name__ == "__main__":
    main()
