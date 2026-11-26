#!/usr/bin/env python3
"""BC5 experiment 0405 (series e7 of experiment 0401), tag "tbp": exp 0405 decision 4 ("=> B => B", the dead KytyPlus tables
are ported first, then loaded, each behind its own switch), batch 2, four small Np tables. Two units:
  src/libs/libNp.cpp
    namespace NpPartner           (InitNpPartner_1,            4 NIDs)  KYTY_BC5_LOAD_NPPARTNER      3 ported, 1 held
    namespace NpParty             (InitNpParty_1,             26 NIDs)  KYTY_BC5_LOAD_NPPARTY       15 ported, 11 held
    namespace NpSnsFacebookDialog (InitNpSnsFacebookDialog_1,  1 NID)   KYTY_BC5_LOAD_NPSNSFACEBOOK  1 already matches
    The held stubs are registered only when the table's switch is off (the top session, 2026-11-04: when on, a title's
    call to them shows the loader's stubbed-import line, exp 0327). namespace NpAuth is NOT edited (its five go to libNet.cpp).
  src/libs/libNet.cpp
    namespace LibNpAuth (the live NpAuth table, InitNet_1_NpAuth): the dead NpAuth table's five (GetAuthorizationCode/A,
    GetIdToken/A, SetTimeout), next to the live request state (one owner), registered by InitNet_1_NpAuth only when
    KYTY_BC5_LOAD_NPAUTH is on. Off, the live table is today's eight NIDs, byte-identical functions.
Off (unset, empty or "0") every edited stub takes today's path (PRINT_NAME, then today's return); on, a ported stub calls the
port. Sources: AnyPS5 4f41f4c37 (GPL-2.0-only) and shadPS4 60c42b9 (GPL-2.0-or-later), cited in each block. In libNp.cpp
only: one line inserted right after "#include <optional>", and inside the three namespaces above a block after each
LIB_VERSION line, the ported stubs' parameter lists and one branch each, one line at the top of each LIB_DEFINE, and an
"if (!switch)" around each held stub's LIB_FUNC line. In libNet.cpp only, inside namespace LibNpAuth: a block before
LIB_DEFINE(InitNet_1_NpAuth) and an "if (switch)" group after its last LIB_FUNC line. NpAuth, NpCommon, NpManager, NpTrophy
and NpTus of libNp.cpp (agent tbt edits NpTus; the top session chains the scripts and re-pins PINS) and everything of
libNet.cpp outside LibNpAuth are byte-identical.
Every input md5 is pinned in PINS (one dict) and asserted; an input that has this edit already is refused; every anchor
must occur exactly once and lie inside its own namespace (the include line: before "namespace Libs {"); each edit keeps
braces, parentheses and brackets balanced; the inserted text is ASCII; line ends stay as they are (LF). After editing, the
script undoes its own edits on each output and asserts that this gives the input back byte for byte.
Prints "<relpath> <md5>" per output. Notes: tbp0405-notes.md; CPU test: tbp0405.cpp.
usage: mktbp0405.py <tree root in> <out dir>"""
import hashlib
import os
import sys

REL_NP = "src/libs/libNp.cpp"
REL_NET = "src/libs/libNet.cpp"
# The input md5 of every unit this script edits, in ONE dict: the top session re-pins it when it chains this script after
# another one (tbt's edit of namespace NpTus in libNp.cpp).
PINS = {
    REL_NP: "60ee3101064cad91445f59c60696a40e",   # tbt's output (mktbt0405.py) of the e7 input tree's 24e77826...
    REL_NET: "35773d6e769b85be74012a86c0f02e89",  # the e7 input tree: e5's output of the svc edit
}
MARKS = {
    REL_NP: (b"KYTY_BC5_LOAD_NPPARTNER", b"KYTY_BC5_LOAD_NPPARTY", b"KYTY_BC5_LOAD_NPSNSFACEBOOK", b"Bc5Tbp", b"(tbp)"),
    REL_NET: (b"KYTY_BC5_LOAD_NPAUTH", b"Bc5Tbp", b"(tbp)"),
}
NP_OTHERS = ("NpAuth", "NpCommon", "NpManager", "NpTrophy", "NpTus")


def T(text):
    """C++ text written with a visible tab ("»") for each tab of the file's indentation, as ASCII bytes."""
    return text.replace("»", "\t").encode("ascii")


def on_fn(name, switch, item, items):
    """The switch reader: read once (a function-local static), env_flag.hpp's rule, one stderr line."""
    return f"""static bool {name}() {{
»static const bool on = [] {{
»»const char* e = std::getenv("{switch}");
»»const bool  v = e != nullptr && e[0] != '\\0' && std::strcmp(e, "0") != 0;
»»std::fprintf(stderr, "%s\\n",
»»             v ? "[bc5] exp 0405: {item} port on (items: {items})"
»»               : "[bc5] exp 0405: {item} port off");
»»std::fflush(stderr);
»»return v;
»}}();
»return on;
}}
"""


INCLUDE_OLD = "#include <optional>\n"
INCLUDE_NEW = ("#include <optional>\n"
               "#include <atomic> // BC5 experiment 0405 (series e7 of experiment 0401, tag tbp): the NpParty and NpPartner001 flags\n")

# =====================================================================================================================
# libNp.cpp: NpPartner001
# =====================================================================================================================
PARTNER_ANCHOR = 'LIB_VERSION("libSceNpPartner001", 1, "libSceNpPartner001", 1, 1);\n'
PARTNER_BLOCK = r"""
// ---- BC5 experiment 0405 (series e7 of experiment 0401), tag tbp: KYTY_BC5_LOAD_NPPARTNER, the NpPartner001 table's port ----
// Exp 0405 decision 4: this table is loaded behind KYTY_BC5_LOAD_NPPARTNER (libs.cpp). Unset, empty or "0" is off: every
// stub below takes today's path (PRINT_NAME, return OK). On, three of its four exports answer as AnyPS5
// (github.com/boykopovar/AnyPS5, GPL-2.0-only) @ 4f41f4c375f5abb487dbd184fbc150f31994d762,
// core/libs/prx/libSceNpPartner001/Export.cpp:9-33: Initialize and Terminate set and clear a flag without contacting a
// server, and sceNpHasEAAccessSubscription(user, result) writes false (no subscription) and gives 0. Where AnyPS5 throws
// (Terminate or HasEAAccessSubscription before Initialize, a null result) the answers are shadPS4's
// (github.com/shadps4-emu/shadPS4, GPL-2.0-or-later) @ 60c42b9, src/core/libraries/np/np_partner.cpp:17-59 and
// np_partner_error.h:8-9: 0x819D0001 (not initialized) and 0x819D0002 (invalid argument), PS4 values whose PS5 values are
// unverified (AnyPS5 docs/dev/debt/libSceNpPartner001.md:10-11; TODO(verify)); a second Initialize gives 0, as in
// shadPS4. Nothing here is measured on a console. Held: pQfYTZHznMc (sceNpHasEAAccessSubscriptionAbortRequest), a
// placeholder in AnyPS5 (debt :5: its name, signature and behaviour are unverified there). On, InitNpPartner_1 does not
// register it, so a title's call shows the loader's stubbed-import line; off, it is registered as today.
// AnyPS5's and shadPS4's copyrights remain with their authors; GPL-2.0 as the rest of this file.
""" + on_fn("Bc5TbpPartnerOn", "KYTY_BC5_LOAD_NPPARTNER", "nppartner", "init subscription") + r"""
constexpr int BC5_TBP_PARTNER_NOT_INITIALIZED  = static_cast<int>(0x819D0001u);
constexpr int BC5_TBP_PARTNER_INVALID_ARGUMENT = static_cast<int>(0x819D0002u);

static std::atomic<bool> g_bc5_tbp_partner_up {false};

static int Bc5TbpPartnerInitialize() {
»g_bc5_tbp_partner_up = true;
»return OK;
}

static int Bc5TbpPartnerTerminate() {
»return g_bc5_tbp_partner_up.exchange(false) ? OK : BC5_TBP_PARTNER_NOT_INITIALIZED;
}

static int Bc5TbpPartnerHasSubscription(bool* result) {
»if (!g_bc5_tbp_partner_up) {
»»return BC5_TBP_PARTNER_NOT_INITIALIZED;
»}
»if (result == nullptr) {
»»return BC5_TBP_PARTNER_INVALID_ARGUMENT;
»}
»*result = false; // no EA Access server: never a subscription
»return OK;
}
// ---- end of BC5 experiment 0405 (tbp) NpPartner001 block ----
"""

PARTNER_STUBS = (
    ("sceNpEAAccessTerminate", "", "Bc5TbpPartnerTerminate()"),
    ("sceNpEAAccessInitialize", "", "Bc5TbpPartnerInitialize()"),
    ("sceNpHasEAAccessSubscription", "int user_id, bool* result",
     "(static_cast<void>(user_id), Bc5TbpPartnerHasSubscription(result))"),
)
PARTNER_HELD = (("pQfYTZHznMc", "sceNpHasEAAccessSubscriptionAbortRequest"),)

# =====================================================================================================================
# libNp.cpp: NpParty
# =====================================================================================================================
PARTY_ANCHOR = 'LIB_VERSION("libSceNpParty", 1, "libSceNpParty", 1, 1);\n'
PARTY_BLOCK = r"""
// ---- BC5 experiment 0405 (series e7 of experiment 0401), tag tbp: KYTY_BC5_LOAD_NPPARTY, the NpParty table's port ----
// Exp 0405 decision 4: this table is loaded behind KYTY_BC5_LOAD_NPPARTY (libs.cpp). Unset, empty or "0" is off: every
// stub below takes today's path (PRINT_NAME, return 0x80550005). On, the 15 exports AnyPS5 implements answer as AnyPS5
// (github.com/boykopovar/AnyPS5, GPL-2.0-only) @ 4f41f4c375f5abb487dbd184fbc150f31994d762,
// core/libs/prx/libSceNpParty/Export.cpp:8-38, 50-76, 83-87, 94-99, 111-119, 126-128 and 145-148; the user is never in a
// party:
//  - Initialize (its parameter is required) and Terminate set and clear a flag; before Initialize and after Terminate
//    every other call gives NOT_INITIALIZED first;
//  - GetState writes the 16-bit state 2 (not in a party); GetStateAsUserA refuses user -1, then answers as GetState;
//  - the id, member and send calls give NOT_IN_PARTY and write nothing (a null output gives INVALID_ARGUMENT);
//  - the handlers are accepted and never called, as no party event can happen.
// The error values 0x80552502-0x80552506 and the state value 2 are shadPS4's (github.com/shadps4-emu/shadPS4,
// GPL-2.0-or-later) @ 60c42b9, src/core/libraries/np/np_error.h:404-408 and np_party.h:14-17 (PS4). AnyPS5's
// docs/dev/debt/libSceNpParty.md:5-6 says the NOT_INITIALIZED order and the user -1 answer follow a run of firmware
// 13.42's module under an emulator (github.com/boykopovar/AnyPS5/pull/12948): a firmware run, accepted by the maintainer's
// decision 1 of 2026-11-04. Nothing is measured on a PS5 (TODO(verify)). Held: the 11 exports AnyPS5 leaves unimplemented
// (Create, CreateA, GetStateAsUser, GetVoiceChatPriority, Join, Leave, RegisterPrivateHandler, SetVoiceChatPriority,
// ShowInvitationList, ShowInvitationListA, UnregisterPrivateHandler). On, InitNpParty_1 does not register them, so a
// title's call shows the loader's stubbed-import line; off, they are registered as today (0x80550005).
// AnyPS5's and shadPS4's copyrights remain with their authors; GPL-2.0 as the rest of this file.
""" + on_fn("Bc5TbpPartyOn", "KYTY_BC5_LOAD_NPPARTY", "npparty", "init state members handler message") + r"""
constexpr int      BC5_TBP_PARTY_ALREADY_INITIALIZED = static_cast<int>(0x80552502u);
constexpr int      BC5_TBP_PARTY_NOT_INITIALIZED     = static_cast<int>(0x80552503u);
constexpr int      BC5_TBP_PARTY_INVALID_ARGUMENT    = static_cast<int>(0x80552504u);
constexpr int      BC5_TBP_PARTY_NOT_IN_PARTY        = static_cast<int>(0x80552506u);
constexpr uint16_t BC5_TBP_PARTY_STATE_NOT_IN_PARTY  = 2;

static std::atomic<bool> g_bc5_tbp_party_up {false};

static int Bc5TbpPartyInitialize(const void* param) {
»if (param == nullptr) {
»»return BC5_TBP_PARTY_INVALID_ARGUMENT;
»}
»bool was_up = false;
»return g_bc5_tbp_party_up.compare_exchange_strong(was_up, true) ? OK : BC5_TBP_PARTY_ALREADY_INITIALIZED;
}

static int Bc5TbpPartyTerminate() {
»return g_bc5_tbp_party_up.exchange(false) ? OK : BC5_TBP_PARTY_NOT_INITIALIZED;
}

static int Bc5TbpPartyCheckCallback() {
»return g_bc5_tbp_party_up ? OK : BC5_TBP_PARTY_NOT_INITIALIZED;
}

static int Bc5TbpPartyGetState(uint16_t* state) {
»if (!g_bc5_tbp_party_up) {
»»return BC5_TBP_PARTY_NOT_INITIALIZED;
»}
»if (state == nullptr) {
»»return BC5_TBP_PARTY_INVALID_ARGUMENT;
»}
»*state = BC5_TBP_PARTY_STATE_NOT_IN_PARTY;
»return OK;
}

static int Bc5TbpPartyGetStateAsUser(int32_t user_id, uint16_t* state) {
»if (!g_bc5_tbp_party_up) {
»»return BC5_TBP_PARTY_NOT_INITIALIZED;
»}
»if (user_id == -1) {
»»return BC5_TBP_PARTY_INVALID_ARGUMENT;
»}
»return Bc5TbpPartyGetState(state);
}

// The id, member and send calls: never in a party, so there is nothing to write.
static int Bc5TbpPartyNotInParty(const void* out) {
»if (!g_bc5_tbp_party_up) {
»»return BC5_TBP_PARTY_NOT_INITIALIZED;
»}
»return out == nullptr ? BC5_TBP_PARTY_INVALID_ARGUMENT : BC5_TBP_PARTY_NOT_IN_PARTY;
}

// The handlers are kept nowhere: no party event can happen, so none is ever called.
static int Bc5TbpPartyRegisterHandler(const void* handlers) {
»if (!g_bc5_tbp_party_up) {
»»return BC5_TBP_PARTY_NOT_INITIALIZED;
»}
»return handlers == nullptr ? BC5_TBP_PARTY_INVALID_ARGUMENT : OK;
}
// ---- end of BC5 experiment 0405 (tbp) NpParty block ----
"""

PARTY_STUBS = (
    ("sceNpPartyCheckCallback", "", "Bc5TbpPartyCheckCallback()"),
    ("sceNpPartyGetId", "void* party_id", "Bc5TbpPartyNotInParty(party_id)"),
    ("sceNpPartyGetMemberInfo", "uint16_t member, void* info", "(static_cast<void>(member), Bc5TbpPartyNotInParty(info))"),
    ("sceNpPartyGetMemberInfoA", "uint16_t member, void* info", "(static_cast<void>(member), Bc5TbpPartyNotInParty(info))"),
    ("sceNpPartyGetMembers", "void* members", "Bc5TbpPartyNotInParty(members)"),
    ("sceNpPartyGetMembersA", "void* members", "Bc5TbpPartyNotInParty(members)"),
    ("sceNpPartyGetMemberSessionInfo", "uint16_t member, void* info",
     "(static_cast<void>(member), Bc5TbpPartyNotInParty(info))"),
    ("sceNpPartyGetMemberVoiceInfo", "uint16_t member, uint16_t other, uint8_t* voice",
     "(static_cast<void>(member), static_cast<void>(other), Bc5TbpPartyNotInParty(voice))"),
    ("sceNpPartyGetState", "uint16_t* state", "Bc5TbpPartyGetState(state)"),
    ("sceNpPartyGetStateAsUserA", "int32_t user_id, uint16_t* state", "Bc5TbpPartyGetStateAsUser(user_id, state)"),
    ("sceNpPartyInitialize", "const void* param", "Bc5TbpPartyInitialize(param)"),
    ("sceNpPartyRegisterHandler", "const void* handlers, void* user_arg",
     "(static_cast<void>(user_arg), Bc5TbpPartyRegisterHandler(handlers))"),
    ("sceNpPartyRegisterHandlerA", "const void* handlers, void* user_arg",
     "(static_cast<void>(user_arg), Bc5TbpPartyRegisterHandler(handlers))"),
    ("sceNpPartySendBinaryMessage", "const void* message", "Bc5TbpPartyNotInParty(message)"),
    ("sceNpPartyTerminate", "", "Bc5TbpPartyTerminate()"),
)
PARTY_HELD = (
    ("nOZRy-slBoA", "sceNpPartyCreate"),
    ("XQSUbbnpPBA", "sceNpPartyCreateA"),
    ("o7grRhiGHYI", "sceNpPartyGetStateAsUser"),
    ("-lc6XZnQXvM", "sceNpPartyGetVoiceChatPriority"),
    ("RXNCDw2GDEg", "sceNpPartyJoin"),
    ("J8jAi-tfJHc", "sceNpPartyLeave"),
    ("zo4G5WWYpKg", "sceNpPartyRegisterPrivateHandler"),
    ("nazKyHygHhY", "sceNpPartySetVoiceChatPriority"),
    ("-MFiL7hEnPE", "sceNpPartyShowInvitationList"),
    ("yARHEYLajs0", "sceNpPartyShowInvitationListA"),
    ("zQ7gIvt11Pc", "sceNpPartyUnregisterPrivateHandler"),
)

# =====================================================================================================================
# libNp.cpp: NpSnsFacebookDialog
# =====================================================================================================================
FB_ANCHOR = 'LIB_VERSION("libSceNpSnsFacebookDialog", 1, "libSceNpSnsFacebookDialog", 1, 1);\n'
FB_BLOCK = r"""
// ---- BC5 experiment 0405 (series e7 of experiment 0401), tag tbp: KYTY_BC5_LOAD_NPSNSFACEBOOK, the NpSnsFacebookDialog table ----
// Exp 0405 decision 4: this table is loaded behind KYTY_BC5_LOAD_NPSNSFACEBOOK (libs.cpp). Its one export already answers
// as AnyPS5 (github.com/boykopovar/AnyPS5, GPL-2.0-only) @ 4f41f4c375f5abb487dbd184fbc150f31994d762,
// core/libs/prx/libSceNpSnsFacebookDialog/Export.cpp:23 and 45-47: sceNpSnsFacebookDialogUpdateStatus returns the
// dialog's status, which starts at "none" (0). Only Initialize, Open, Close and Terminate move it, and no table of this
// tree registers them, so the status cannot leave 0 and today's "return OK" (0) is that answer. Nothing is changed; the
// switch only prints its line when the table is loaded.
""" + on_fn("Bc5TbpFacebookOn", "KYTY_BC5_LOAD_NPSNSFACEBOOK", "npsnsfacebook", "none, UpdateStatus already matches") + r"""// ---- end of BC5 experiment 0405 (tbp) NpSnsFacebookDialog block ----
"""

NP_TABLES = (
    # namespace, switch, on() name, block anchor, block, stubs, held (nid, name), LIB_DEFINE, NIDs the table registers
    ("NpPartner", "KYTY_BC5_LOAD_NPPARTNER", "Bc5TbpPartnerOn", PARTNER_ANCHOR, PARTNER_BLOCK, PARTNER_STUBS, PARTNER_HELD,
     "InitNpPartner_1", 4),
    ("NpParty", "KYTY_BC5_LOAD_NPPARTY", "Bc5TbpPartyOn", PARTY_ANCHOR, PARTY_BLOCK, PARTY_STUBS, PARTY_HELD,
     "InitNpParty_1", 26),
    ("NpSnsFacebookDialog", "KYTY_BC5_LOAD_NPSNSFACEBOOK", "Bc5TbpFacebookOn", FB_ANCHOR, FB_BLOCK, (), (),
     "InitNpSnsFacebookDialog_1", 1),
)
EXPECT = {"NpPartner": (3, 1), "NpParty": (15, 11), "NpSnsFacebookDialog": (0, 0)}  # ported, held

# =====================================================================================================================
# libNet.cpp: namespace LibNpAuth, the live NpAuth table
# =====================================================================================================================
NET_ANCHOR = "LIB_DEFINE(InitNet_1_NpAuth) {\n"
NET_BLOCK = r"""// ---- BC5 experiment 0405 (series e7 of experiment 0401), tag tbp: KYTY_BC5_LOAD_NPAUTH, the dead NpAuth table's five ----
// Exp 0405 decision 4: libNp.cpp's NpAuth table (sceNpAuthGetAuthorizationCode/A, sceNpAuthGetIdToken/A,
// sceNpAuthSetTimeout), which Libs::InitAll never loaded, is ported here, next to this table's request state, so that the
// state has one owner. InitNet_1_NpAuth registers the five only when KYTY_BC5_LOAD_NPAUTH is on; unset, empty or "0" is
// off: today's eight NIDs and nothing else. libNp.cpp's NpAuth table stays unloaded in both states, so no NID is
// registered twice. On, they answer as AnyPS5 (github.com/boykopovar/AnyPS5, GPL-2.0-only) @
// 4f41f4c375f5abb487dbd184fbc150f31994d762, core/libs/prx/libSceNpAuth/Export.cpp:
//  - :115-121 and :162-168: GetAuthorizationCode/A and GetIdToken/A forward to the V3 calls (NpAuthGetAuthorizationCodeV3
//    and NpAuthGetIdTokenV3 above, unchanged), after V3's own null check (:82, :99: a null parameter or output gives
//    0x80550301 before any request is looked up); the plain GetAuthorizationCode passes no issuer (AnyPS5's
//    three-argument form). AnyPS5's docs/dev/debt/libSceNpAuth.md:5 names shadPS4 (github.com/shadps4-emu/shadPS4,
//    GPL-2.0-or-later) @ f68923f, src/core/libraries/np/np_auth/np_auth.cpp:189-199 and 375-383, as the source: the A
//    forms differ from V3 only in a version flag.
//  - :137-150: SetTimeout checks its arguments first (also shadPS4 @ 60c42b9, np_auth.cpp:201-219): a negative retry
//    count, all five values 0, a resolve timeout under 1 s, or a connect, send or receive timeout under 10 s (0 means "no
//    effect") give 0x80550301; then an unknown request gives 0x80550306; else 0. The values are not kept: nothing would
//    read them (AnyPS5 keeps them for a transport that does not exist, debt :11).
// Nothing here is measured on a console (TODO(verify)). AnyPS5's and shadPS4's copyrights remain with their authors;
// GPL-2.0 as the rest of this file.
""" + on_fn("Bc5TbpAuthOn", "KYTY_BC5_LOAD_NPAUTH", "npauth", "getters settimeout") + r"""
static int KYTY_SYSV_ABI NpAuthGetAuthorizationCode(int req_id, const void* param, void* auth_code) {
»PRINT_NAME();
»if (param == nullptr || auth_code == nullptr) {
»»return NP_AUTH_ERROR_INVALID_ARGUMENT;
»}
»return NpAuthGetAuthorizationCodeV3(req_id, param, auth_code, nullptr);
}

static int KYTY_SYSV_ABI NpAuthGetAuthorizationCodeA(int req_id, const void* param, void* auth_code, int* issuer_id) {
»PRINT_NAME();
»if (param == nullptr || auth_code == nullptr) {
»»return NP_AUTH_ERROR_INVALID_ARGUMENT;
»}
»return NpAuthGetAuthorizationCodeV3(req_id, param, auth_code, issuer_id);
}

static int KYTY_SYSV_ABI NpAuthGetIdToken(int req_id, const void* param, void* id_token) {
»PRINT_NAME();
»if (param == nullptr || id_token == nullptr) {
»»return NP_AUTH_ERROR_INVALID_ARGUMENT;
»}
»return NpAuthGetIdTokenV3(req_id, param, id_token);
}

static int KYTY_SYSV_ABI NpAuthGetIdTokenA(int req_id, const void* param, void* id_token) {
»PRINT_NAME();
»if (param == nullptr || id_token == nullptr) {
»»return NP_AUTH_ERROR_INVALID_ARGUMENT;
»}
»return NpAuthGetIdTokenV3(req_id, param, id_token);
}

// 0 leaves a timeout as it is; any other value must reach its minimum (1 s to resolve, 10 s for the others).
static bool Bc5TbpAuthTimeoutOk(uint32_t usec, uint32_t min_usec) {
»return usec == 0 || usec >= min_usec;
}

static int KYTY_SYSV_ABI NpAuthSetTimeout(int req_id, int32_t resolve_retry, uint32_t resolve_timeout,
                                          uint32_t connect_timeout, uint32_t send_timeout, uint32_t receive_timeout) {
»PRINT_NAME();
»constexpr uint32_t resolve_min  = 1000000;
»constexpr uint32_t transfer_min = 10000000;
»if (resolve_retry < 0 || (resolve_retry == 0 && resolve_timeout == 0 && connect_timeout == 0 && send_timeout == 0 &&
»                          receive_timeout == 0)) {
»»return NP_AUTH_ERROR_INVALID_ARGUMENT;
»}
»if (!Bc5TbpAuthTimeoutOk(resolve_timeout, resolve_min) || !Bc5TbpAuthTimeoutOk(connect_timeout, transfer_min) ||
»    !Bc5TbpAuthTimeoutOk(send_timeout, transfer_min) || !Bc5TbpAuthTimeoutOk(receive_timeout, transfer_min)) {
»»return NP_AUTH_ERROR_INVALID_ARGUMENT;
»}
»std::scoped_lock lock(g_np_auth_request_mutex);
»return np_auth_find_request(req_id) == nullptr ? NP_AUTH_ERROR_REQUEST_NOT_FOUND : 0;
}
// ---- end of BC5 experiment 0405 (tbp) NpAuth block ----

"""
NET_LAST_OLD = '»LIB_FUNC("RdsFVsgSpZY", LibNpAuth::NpAuthGetIdTokenV3);\n'
NET_LAST_NEW = ('»LIB_FUNC("RdsFVsgSpZY", LibNpAuth::NpAuthGetIdTokenV3);\n'
                '»if (Bc5TbpAuthOn()) { // BC5 experiment 0405 (tbp): libNp.cpp\'s dead NpAuth table, here with the request state\n'
                '»»LIB_FUNC("KxGkOrQJTqY", LibNpAuth::NpAuthGetAuthorizationCode);\n'
                '»»LIB_FUNC("qAUXQ9GdWp8", LibNpAuth::NpAuthGetAuthorizationCodeA);\n'
                '»»LIB_FUNC("uaB-LoJqHis", LibNpAuth::NpAuthGetIdToken);\n'
                '»»LIB_FUNC("CocbHVIKPE8", LibNpAuth::NpAuthGetIdTokenA);\n'
                '»»LIB_FUNC("PM3IZCw-7m0", LibNpAuth::NpAuthSetTimeout);\n'
                '»}\n')
NET_NIDS = ("KxGkOrQJTqY", "qAUXQ9GdWp8", "uaB-LoJqHis", "CocbHVIKPE8", "PM3IZCw-7m0")


def balance(b):
    return (b.count(b"{") - b.count(b"}"), b.count(b"(") - b.count(b")"), b.count(b"[") - b.count(b"]"))


def md5(b):
    return hashlib.md5(b).hexdigest()


def namespace_span(s, ns):
    """Byte range of 'namespace <ns> {' ... '} // namespace <ns>' in s; each must occur once."""
    head, tail = b"namespace " + ns.encode() + b" {\n", b"} // namespace " + ns.encode() + b"\n"
    assert s.count(head) == 1 and s.count(tail) == 1, ("namespace markers", ns, s.count(head), s.count(tail))
    a = s.index(head)
    z = s.index(tail, a)
    return a, z


class Editor:
    """Exact replacements on one unit, each asserted once and inside its namespace, kept for the undo check."""

    def __init__(self, s):
        assert b"\r" not in s, "a CR in the LF unit"
        self.s, self.out, self.done = s, s, []

    def apply(self, old, new, what, ns=None):
        o, n = T(old), T(new)
        assert self.out.count(o) == 1, ("anchor", what, self.out.count(o))
        if ns is not None:  # the anchor lies inside its namespace (checked on the current text)
            a, z = namespace_span(self.out, ns)
            assert a < self.out.index(o) < z, ("anchor outside its namespace", what, ns)
        else:  # the include line: before the file's namespace
            assert self.out.index(o) < self.out.index(b"namespace Libs {\n"), ("include anchor not in the include block", what)
        assert balance(o) == balance(n), ("the edit changes the balance", what, balance(o), balance(n))
        self.out = self.out.replace(o, n)
        self.done.append((o, n))

    def finish(self):
        assert balance(self.out) == balance(self.s), ("the unit's balance changed", balance(self.s), balance(self.out))
        back = self.out
        for o, n in reversed(self.done):  # undo, last first: the input must come back byte for byte
            assert back.count(n) == 1, ("undo", n[:60])
            back = back.replace(n, o)
        assert back == self.s, "undoing the edits does not give the input back"
        for o, n in self.done:
            n.decode("ascii")
        assert b"\r" not in self.out
        return self.out


def edit_np(s):
    for m in MARKS[REL_NP]:
        assert m not in s, ("refused: the unit has the edit already", REL_NP, m.decode())
    e = Editor(s)
    e.apply(INCLUDE_OLD, INCLUDE_NEW, "includes")
    for ns, switch, on, anchor, block, stubs, held, define, nids in NP_TABLES:
        a, z = namespace_span(s, ns)
        assert s[a:z].count(b"LIB_FUNC(") == nids, (ns, "LIB_FUNC count", s[a:z].count(b"LIB_FUNC("), nids)
        assert balance(T(block)) == (0, 0, 0), ("the block is not balanced", ns, balance(T(block)))
        assert (len(stubs), len(held)) == EXPECT[ns], (ns, len(stubs), len(held))
        e.apply(anchor, anchor + block, f"{ns} block", ns)
        for name, params, call in stubs:
            e.apply(f"static int KYTY_SYSV_ABI {name}() {{\n»PRINT_NAME();\n",
                    f"static int KYTY_SYSV_ABI {name}({params}) {{\n»PRINT_NAME();\n"
                    f"»if ({on}()) {{ // BC5 experiment 0405 (tbp): the port, {switch}\n"
                    f"»»return {call};\n»}}\n", f"{ns} {name}", ns)
        e.apply(f"LIB_DEFINE({define}) {{\n",
                f"LIB_DEFINE({define}) {{\n»(void){on}(); // BC5 experiment 0405 (tbp): reads {switch} once, prints its line\n",
                f"{ns} {define}", ns)
        for nid, name in held:
            line = f'»LIB_FUNC("{nid}", {ns}::{name});\n'
            e.apply(line, f"»if (!{on}()) {{ // BC5 experiment 0405 (tbp): held, registered only when {switch} is off\n"
                          f"»{line}»}}\n", f"{ns} held {nid}", ns)
        want = len(stubs) + 2 + len(held)  # the stubs, the definition, the LIB_DEFINE line, the held registrations
        assert e.out.count(T(f"{on}()")) == want, (ns, "switch uses", e.out.count(T(f"{on}()")), want)
        a, z = namespace_span(e.out, ns)
        assert e.out[a:z].count(b"LIB_FUNC(") == nids, (ns, "LIB_FUNC count after", e.out[a:z].count(b"LIB_FUNC("), nids)
        # The switch's name: in the block, in each ported stub's and held line's comment and in the LIB_DEFINE line.
        assert e.out.count(switch.encode()) == block.count(switch) + len(stubs) + len(held) + 1, (ns, "switch name count")
    out = e.finish()
    for other in NP_OTHERS:  # the other tables are byte for byte the same
        a0, z0 = namespace_span(s, other)
        a1, z1 = namespace_span(out, other)
        assert s[a0:z0] == out[a1:z1], ("another table changed", other)
    return out


def edit_net(s):
    for m in MARKS[REL_NET]:
        assert m not in s, ("refused: the unit has the edit already", REL_NET, m.decode())
    for nid in NET_NIDS:  # today's libNet.cpp registers none of the five
        assert f'"{nid}"'.encode() not in s, ("libNet.cpp registers a dead NpAuth NID already", nid)
    e = Editor(s)
    a, z = namespace_span(s, "LibNpAuth")
    assert s[a:z].count(b"LIB_FUNC(") == 8, ("LibNpAuth LIB_FUNC count", s[a:z].count(b"LIB_FUNC("))
    assert balance(T(NET_BLOCK)) == (0, 0, 0), ("the block is not balanced", balance(T(NET_BLOCK)))
    e.apply(NET_ANCHOR, NET_BLOCK + NET_ANCHOR, "LibNpAuth block", "LibNpAuth")
    e.apply(NET_LAST_OLD, NET_LAST_NEW, "LibNpAuth registration", "LibNpAuth")
    out = e.finish()
    a1, z1 = namespace_span(out, "LibNpAuth")
    assert s[:a] == out[:a1] and s[z:] == out[z1:], "libNet.cpp changed outside namespace LibNpAuth"
    assert out[a1:z1].count(b"LIB_FUNC(") == 13, ("LibNpAuth LIB_FUNC count after", out[a1:z1].count(b"LIB_FUNC("))
    for nid in NET_NIDS:
        assert out.count(f'"{nid}"'.encode()) == 1, ("NID", nid)
    assert out.count(b"Bc5TbpAuthOn()") == 2, ("switch uses", out.count(b"Bc5TbpAuthOn()"))
    # The eight live functions' text is unchanged: everything before the block is the input's.
    assert out.startswith(s[: s.index(T(NET_ANCHOR))]), "the live functions changed"
    return out


EDITS = ((REL_NP, edit_np), (REL_NET, edit_net))


def main():
    assert len(sys.argv) == 3, __doc__
    root, outdir = sys.argv[1], sys.argv[2]
    assert os.path.abspath(root) != os.path.abspath(outdir), "the out dir must not be the tree"
    ins = {}
    for rel, _ in EDITS:  # every input is checked before anything is written
        with open(os.path.join(root, rel), "rb") as f:
            s = f.read()
        for m in MARKS[rel]:
            assert m not in s, ("refused: the unit has the edit already", rel, m.decode())
        assert md5(s) == PINS[rel], ("refused: not the pinned input", rel, md5(s), PINS[rel])
        ins[rel] = s
    outs = {rel: fn(ins[rel]) for rel, fn in EDITS}
    for rel, _ in EDITS:
        print(f"# in:  {rel} {md5(ins[rel])}  ({len(ins[rel])} bytes, LF)", file=sys.stderr)
        dst = os.path.join(outdir, rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        with open(dst, "wb") as f:
            f.write(outs[rel])
        print(f"{rel} {md5(outs[rel])}")


if __name__ == "__main__":
    main()
