#!/usr/bin/env python3
"""BC5 experiment 0405 (series e7 of experiment 0401), tag "tbp": exp 0405 decision 4 ("=> B => B", the dead KytyPlus tables
are ported first, then loaded, each behind its own switch), batch 2, four small Np tables of src/libs/libNp.cpp:
  namespace NpAuth              (InitNpAuth_1,              5 NIDs)  KYTY_BC5_LOAD_NPAUTH         1 ported (SetTimeout's
                                                                     argument checks), 4 held (request state is libNet.cpp's)
  namespace NpPartner           (InitNpPartner_1,           4 NIDs)  KYTY_BC5_LOAD_NPPARTNER      3 ported, 1 held
  namespace NpParty             (InitNpParty_1,            26 NIDs)  KYTY_BC5_LOAD_NPPARTY       15 ported, 11 held
  namespace NpSnsFacebookDialog (InitNpSnsFacebookDialog_1, 1 NID)   KYTY_BC5_LOAD_NPSNSFACEBOOK  1 already matches
The same switch names make libs.cpp (agent tl2) load the table. Off (unset, empty or "0") every stub takes today's path
(PRINT_NAME, then today's return); on, a ported stub calls the port. Sources: AnyPS5 4f41f4c37 (GPL-2.0-only) and shadPS4
60c42b9 (GPL-2.0-or-later), cited in each block. Only libNp.cpp is edited, and in it only: one line inserted right after
"#include <optional>", and inside the four namespaces above a block after each LIB_VERSION line, the ported stubs'
parameter lists and one branch each, and one line at the top of each LIB_DEFINE. NpCommon, NpManager, NpTrophy and NpTus
(agent tbt edits NpTus in parallel; the top session chains the two scripts and re-pins PINS) are not touched.
The input md5 is pinned (PINS) and asserted; an input that has this edit already is refused; every anchor must occur
exactly once and lie inside its own namespace (the include line: before "namespace Libs {"); each edit keeps braces,
parentheses and brackets balanced; the inserted text is ASCII; line ends stay as they are (LF). After editing, the script
undoes its own edits on the output and asserts that this gives the input back byte for byte, and that every namespace
other than the four is byte-identical.
Prints "<relpath> <md5>". Notes: tbp0405-notes.md; CPU test: tbp0405.cpp.
usage: mktbp0405.py <tree root in> <out dir>"""
import hashlib
import os
import sys

REL = "src/libs/libNp.cpp"
# The input md5 of every unit this script edits, in ONE dict: the top session re-pins it when it chains this script after
# another one (tbt's edit of namespace NpTus in the same file).
PINS = {
    REL: "eb3bfe9d56f0fcdddf29199846f46fb5",  # chained after tbt (mktbt0405.py) on the e7 input tree (e6's tbn output 24e778261495abcd5a069396f14b28b4)
}
MARKS = (b"KYTY_BC5_LOAD_NPAUTH", b"KYTY_BC5_LOAD_NPPARTNER", b"KYTY_BC5_LOAD_NPPARTY", b"KYTY_BC5_LOAD_NPSNSFACEBOOK",
         b"Bc5Tbp", b"(tbp)")
MINE = ("NpAuth", "NpPartner", "NpParty", "NpSnsFacebookDialog")
OTHERS = ("NpCommon", "NpManager", "NpTrophy", "NpTus")


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
# NpAuth
# =====================================================================================================================
AUTH_ANCHOR = 'LIB_VERSION("libSceNpAuth", 1, "libSceNpAuth", 1, 1);\n'
AUTH_BLOCK = r"""
// ---- BC5 experiment 0405 (series e7 of experiment 0401), tag tbp: KYTY_BC5_LOAD_NPAUTH, the NpAuth table's port ----
// Exp 0405 decision 4 ("=> B => B", 2026-11-04): this table is compiled but Libs::InitAll never loaded it; it is ported
// first, then loaded behind KYTY_BC5_LOAD_NPAUTH (libs.cpp). Unset, empty or "0" is off: every stub below takes today's
// path. On:
//  - sceNpAuthSetTimeout checks its arguments as AnyPS5 (github.com/boykopovar/AnyPS5, GPL-2.0-only) @
//    4f41f4c375f5abb487dbd184fbc150f31994d762, core/libs/prx/libSceNpAuth/Export.cpp:137-143, and shadPS4
//    (github.com/shadps4-emu/shadPS4, GPL-2.0-or-later) @ 60c42b9, src/core/libraries/np/np_auth/np_auth.cpp:201-219 do,
//    before any request is looked up: a negative retry count, all five values 0, a resolve timeout under 1 s, or a
//    connect, send or receive timeout under 10 s (0 means "no effect") give 0x80550301 (shadPS4 np_error.h:58). Neither
//    project measured this on a console (AnyPS5 docs/dev/debt/libSceNpAuth.md:5,11; TODO(verify)). Valid values give
//    today's 0: AnyPS5 keeps them for a transport that does not exist (debt :11), and nothing here would read them.
//  - Held, today's answer kept: SetTimeout's request lookup (AnyPS5 :144-146, 0x80550306 for an unknown request) and the
//    four getters GetAuthorizationCode/A and GetIdToken/A (AnyPS5 :115-121 and :162-168, which forward to :80-113). Their
//    request comes from the live sceNpAuthCreateRequest / CreateAsyncRequest (libNet.cpp, namespace LibNpAuth), whose
//    state is static to that file: this file cannot read it, and an answer made without it could leave a live
//    asynchronous request that its poll never sees started.
// AnyPS5's and shadPS4's copyrights remain with their authors; GPL-2.0 as the rest of this file.
""" + on_fn("Bc5TbpAuthOn", "KYTY_BC5_LOAD_NPAUTH", "npauth", "settimeout-arguments") + r"""
constexpr int      BC5_TBP_AUTH_INVALID_ARGUMENT  = static_cast<int>(0x80550301u);
constexpr uint32_t BC5_TBP_AUTH_RESOLVE_MIN_USEC  = 1000000;  // 1 s
constexpr uint32_t BC5_TBP_AUTH_TRANSFER_MIN_USEC = 10000000; // 10 s

// 0 leaves a timeout as it is; any other value must reach its minimum.
static bool Bc5TbpAuthTimeoutOk(uint32_t usec, uint32_t min_usec) {
»return usec == 0 || usec >= min_usec;
}

static int Bc5TbpAuthSetTimeout(int32_t retries, uint32_t resolve_usec, uint32_t connect_usec, uint32_t send_usec,
                                uint32_t receive_usec) {
»if (retries < 0 || (retries == 0 && resolve_usec == 0 && connect_usec == 0 && send_usec == 0 && receive_usec == 0)) {
»»return BC5_TBP_AUTH_INVALID_ARGUMENT;
»}
»if (!Bc5TbpAuthTimeoutOk(resolve_usec, BC5_TBP_AUTH_RESOLVE_MIN_USEC) ||
»    !Bc5TbpAuthTimeoutOk(connect_usec, BC5_TBP_AUTH_TRANSFER_MIN_USEC) ||
»    !Bc5TbpAuthTimeoutOk(send_usec, BC5_TBP_AUTH_TRANSFER_MIN_USEC) ||
»    !Bc5TbpAuthTimeoutOk(receive_usec, BC5_TBP_AUTH_TRANSFER_MIN_USEC)) {
»»return BC5_TBP_AUTH_INVALID_ARGUMENT;
»}
»return OK; // the request lookup is held (see above): today's answer
}
// ---- end of BC5 experiment 0405 (tbp) NpAuth block ----
"""

AUTH_STUBS = (
    ("sceNpAuthSetTimeout",
     "int req_id, int32_t resolve_retry, uint32_t resolve_timeout, uint32_t connect_timeout, uint32_t send_timeout, "
     "uint32_t receive_timeout",
     "(static_cast<void>(req_id),\n»»        Bc5TbpAuthSetTimeout(resolve_retry, resolve_timeout, connect_timeout, send_timeout, receive_timeout))"),
)

# =====================================================================================================================
# NpPartner001
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
// shadPS4. Nothing here is measured on a console. Held, today's 0 kept: pQfYTZHznMc
// (sceNpHasEAAccessSubscriptionAbortRequest), a placeholder in AnyPS5 (debt :5: its name, signature and behaviour are
// unverified there).
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

# =====================================================================================================================
# NpParty
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
// decision 1 of 2026-11-04. Nothing is measured on a PS5 (TODO(verify)). Held, today's 0x80550005 kept: the 11 exports
// AnyPS5 leaves unimplemented (Create, CreateA, GetStateAsUser, GetVoiceChatPriority, Join, Leave,
// RegisterPrivateHandler, SetVoiceChatPriority, ShowInvitationList, ShowInvitationListA, UnregisterPrivateHandler).
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

# =====================================================================================================================
# NpSnsFacebookDialog
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

TABLES = (
    # namespace, switch, on() name, block anchor, block, stubs, LIB_DEFINE, NIDs the table registers
    ("NpAuth", "KYTY_BC5_LOAD_NPAUTH", "Bc5TbpAuthOn", AUTH_ANCHOR, AUTH_BLOCK, AUTH_STUBS, "InitNpAuth_1", 5),
    ("NpPartner", "KYTY_BC5_LOAD_NPPARTNER", "Bc5TbpPartnerOn", PARTNER_ANCHOR, PARTNER_BLOCK, PARTNER_STUBS,
     "InitNpPartner_1", 4),
    ("NpParty", "KYTY_BC5_LOAD_NPPARTY", "Bc5TbpPartyOn", PARTY_ANCHOR, PARTY_BLOCK, PARTY_STUBS, "InitNpParty_1", 26),
    ("NpSnsFacebookDialog", "KYTY_BC5_LOAD_NPSNSFACEBOOK", "Bc5TbpFacebookOn", FB_ANCHOR, FB_BLOCK, (),
     "InitNpSnsFacebookDialog_1", 1),
)
EXPECT_PORTED = {"NpAuth": 1, "NpPartner": 3, "NpParty": 15, "NpSnsFacebookDialog": 0}


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


def edits_for(ns, switch, on, stubs, define):
    out = []
    for name, params, call in stubs:
        old = f"static int KYTY_SYSV_ABI {name}() {{\n»PRINT_NAME();\n"
        new = (f"static int KYTY_SYSV_ABI {name}({params}) {{\n»PRINT_NAME();\n"
               f"»if ({on}()) {{ // BC5 experiment 0405 (tbp): the port, {switch}\n"
               f"»»return {call};\n»}}\n")
        out.append((ns, name, old, new))
    out.append((ns, define, f"LIB_DEFINE({define}) {{\n",
                f"LIB_DEFINE({define}) {{\n»(void){on}(); // BC5 experiment 0405 (tbp): reads {switch} once, prints its line\n"))
    return out


def edit(s):
    for m in MARKS:
        assert m not in s, ("refused: the unit has the edit already", m.decode())
    assert b"\r" not in s, "a CR in the LF unit"
    out = s
    done = []  # (old bytes, new bytes) in order, for the undo check

    def apply(old, new, what, ns=None):
        nonlocal out
        o, n = T(old), T(new)
        assert out.count(o) == 1, ("anchor", what, out.count(o))
        if ns is not None:  # the anchor lies inside its namespace (checked on the current text)
            a, z = namespace_span(out, ns)
            assert a < out.index(o) < z, ("anchor outside its namespace", what, ns)
        else:  # the include line: before the file's namespace
            assert out.index(o) < out.index(b"namespace Libs {\n"), ("include anchor not in the include block", what)
        assert balance(o) == balance(n), ("the edit changes the balance", what, balance(o), balance(n))
        out = out.replace(o, n)
        done.append((o, n))

    apply(INCLUDE_OLD, INCLUDE_NEW, "includes")
    for ns, switch, on, anchor, block, stubs, define, nids in TABLES:
        a, z = namespace_span(s, ns)
        assert s[a:z].count(b"LIB_FUNC(") == nids, (ns, "LIB_FUNC count", s[a:z].count(b"LIB_FUNC("), nids)
        assert balance(T(block)) == (0, 0, 0), ("the block is not balanced", ns, balance(T(block)))
        assert len(stubs) == EXPECT_PORTED[ns], (ns, len(stubs))
        apply(anchor, anchor + block, f"{ns} block", ns)
        for ns2, name, old, new in edits_for(ns, switch, on, stubs, define):
            apply(old, new, f"{ns2} {name}", ns2)
        want = len(stubs) + 2  # the stubs, the definition, the LIB_DEFINE line
        assert out.count(T(f"{on}()")) == want, (ns, "switch uses", out.count(T(f"{on}()")), want)
        a, z = namespace_span(out, ns)
        assert out[a:z].count(b"LIB_FUNC(") == nids, (ns, "LIB_FUNC count after", out[a:z].count(b"LIB_FUNC("), nids)
        # The switch's name: in the block, in each ported stub's comment and in the LIB_DEFINE line's comment.
        assert out.count(switch.encode()) == block.count(switch) + len(stubs) + 1, (ns, "switch name count")
    assert balance(out) == balance(s), ("the unit's balance changed", balance(s), balance(out))
    # The other tables are byte for byte the same.
    for other in OTHERS:
        a0, z0 = namespace_span(s, other)
        a1, z1 = namespace_span(out, other)
        assert s[a0:z0] == out[a1:z1], ("another table changed", other)
    # Undo (last first): the input must come back byte for byte.
    back = out
    for o, n in reversed(done):
        assert back.count(n) == 1, ("undo", n[:60])
        back = back.replace(n, o)
    assert back == s, "undoing the edits does not give the input back"
    for o, n in done:
        n.decode("ascii")
    assert b"\r" not in out
    return out


def main():
    assert len(sys.argv) == 3, __doc__
    root, outdir = sys.argv[1], sys.argv[2]
    assert os.path.abspath(root) != os.path.abspath(outdir), "the out dir must not be the tree"
    with open(os.path.join(root, REL), "rb") as f:
        s = f.read()
    for m in MARKS:
        assert m not in s, ("refused: the unit has the edit already", REL, m.decode())
    assert md5(s) == PINS[REL], ("refused: not the pinned input", REL, md5(s), PINS[REL])
    out = edit(s)
    print(f"# in:  {REL} {md5(s)}  ({len(s)} bytes, LF)", file=sys.stderr)
    dst = os.path.join(outdir, REL)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    with open(dst, "wb") as f:
        f.write(out)
    print(f"{REL} {md5(out)}")


if __name__ == "__main__":
    main()
