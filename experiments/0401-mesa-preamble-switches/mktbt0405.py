#!/usr/bin/env python3
"""BC5 experiment 0405 (series e7 of experiment 0401), tag "tbt": exp 0405 decision 4 ("=> B => B", the dead KytyPlus tables
are ported first, then loaded, each behind its own switch), batch 2, the NpTus table of src/libs/libNp.cpp:
  namespace NpTus  (InitNpTus_1, 142 NIDs)  KYTY_BC5_LOAD_NPTUS  136 ported, 6 held (AnyPS5 does not implement them;
                                                                 not registered when on)
  item switch KYTY_BC5_NPTUS_FRIENDS_RUN (default off, acts only with KYTY_BC5_LOAD_NPTUS on): the checks a firmware 13.42
  emulator run measured (AnyPS5's debt note) for the A and cross-save friends calls, sceNpTusGetDataForCrossSaveVUser and
  sceNpTusDeleteMultiSlotDataVUser, in place of AnyPS5's code.
The same switch name makes libs.cpp (agent tl2) load the table. Off (unset, empty or "0") every stub takes today's path
(PRINT_NAME, then today's return NP_NOT_SIGNED_IN) and all 142 NIDs are registered as today; on, the stub calls the port.
Source: AnyPS5 4f41f4c37 (GPL-2.0-only), core/libs/prx/libSceNpTus/Export.cpp, whose debt note names shadPS4
(GPL-2.0-or-later) for the signatures and checks; cited in the block. Only the namespace NpTus of libNp.cpp is edited: one
block after its LIB_VERSION line, the 136 stubs' parameter lists and one branch each, two lines in its LIB_DEFINE, and the 6
held stubs' registration lines (in 4 runs) put under `if (!Bc5NtuOn())`. No include is added (the input has every header
the block uses).
Everything outside `namespace NpTus { ... } // namespace NpTus` stays byte for byte as it is, so agent tbp's edits of the
other namespaces of the same file can be chained before or after this script (the top session re-pins the md5 in PINS).
The input md5 is pinned and asserted; an input that has the edit already is refused; every anchor must occur exactly once and
lie inside the namespace; each edit keeps braces, parentheses and brackets balanced; the inserted text is ASCII; line ends
stay LF (the file's UTF-8 BOM is kept). After editing, the script undoes its own edits on the output and asserts that this
gives the input back byte for byte.
Prints "<relpath> <md5>". Notes: tbt0405-notes.md; CPU test: tbt0405.cpp.
usage: mktbt0405.py <tree root in> <out dir>"""
import hashlib
import os
import sys

# The pinned inputs, one entry per unit this script edits (the top session re-pins here when it chains scripts).
PINS = {
    "src/libs/libNp.cpp": "24e778261495abcd5a069396f14b28b4",  # e6's output (mktbn0405.py), the e7 input tree
}
REL = "src/libs/libNp.cpp"
MARKS = (b"KYTY_BC5_LOAD_NPTUS", b"Bc5Ntu", b"(tbt)")
NS = b"NpTus"


def T(text):
    """C++ text written with a visible tab ("»") for each tab of the file's indentation, as ASCII bytes."""
    return text.replace("»", "\t").encode("ascii")


ANCHOR = 'LIB_VERSION("libSceNpTus", 1, "libSceNpTus", 1, 1);\n'
BLOCK = r"""
// ---- BC5 experiment 0405 (series e7 of experiment 0401), tag tbt: KYTY_BC5_LOAD_NPTUS, the NpTus table's port ----
// Exp 0405 decision 4 ("=> B => B", 2026-11-04): this table is compiled but Libs::InitAll never loaded it; it is ported
// first, then loaded behind KYTY_BC5_LOAD_NPTUS (libs.cpp, agent tl2). Unset, empty or "0" is off: every stub below takes
// today's path (PRINT_NAME, return NP_NOT_SIGNED_IN). On, 136 of the 142 exports answer as AnyPS5
// (github.com/boykopovar/AnyPS5, GPL-2.0-only) @ 4f41f4c375f5abb487dbd184fbc150f31994d762,
// core/libs/prx/libSceNpTus/Export.cpp:
//  - 10-34 (the error codes and limits: 32 title contexts, 256 requests, 64 slots, 101 users, 100 friends, TSS slots 0 to
//    15, a TSS small storage of at most 64 KiB), 36-137 (the request record; the slot-list, friends-option and empty-name
//    checks; a request that starts and finishes at once; the title-context table that TUS and TSS share), 141-183, 222-230,
//    247-249 and 1055-1057 (title contexts, requests, abort, poll, wait), 185-1089 (the 63 *Async calls: their argument
//    checks in AnyPS5's order, then a request that finishes with SCE_NP_ERROR_SIGNED_OUT, or ABORTED once the request was
//    aborted; and the 63 blocking forms: the same checks, then that result).
//  - Its debt note docs/dev/debt/libSceNpTus.md: the signatures, the checks, their order and the community error codes follow
//    shadPS4 (github.com/shadps4-emu/shadPS4, GPL-2.0-or-later; checked here against 60c42b9:
//    src/core/libraries/np/np_tus/np_tus.cpp:122-168, np_tus.h:48-82, np_error.h:15,105-125, np_types.h:29-33), and fpPS4
//    for the context and request calls; none of it is measured on a console. There is no PSN: no request reaches a server,
//    and no output (variables, data, statuses, hits, content length) is ever written. sceNpTssGetDataAsync's data-status size
//    0x18 is shadPS4's (np_tus.h:48-52, np_tus.cpp:4871); AnyPS5's commit dbc28c0a9 calls its check "measured", its note
//    says "not measured on a console": TODO(verify).
//  - The checks that an emulator run of firmware 13.42's module measured (debt note, AnyPS5 PR 10675), which AnyPS5's code
//    does not apply, are here behind their own item switch, KYTY_BC5_NPTUS_FRIENDS_RUN, default off (Bc5NtuRunOn below).
// Held: the 6 exports AnyPS5 does not implement (sceNpTssGetStorage, sceNpTssGetStorageAsync, sceNpTusSetThreadParam,
// sceNpTusCreateTitleCtx, sceNpTusSetTimeout, sceNpTusChangeModeForOtherSaveDataOwners) keep today's stub, and with the
// switch on InitNpTus_1 does not register them, so the loader reports them as stubbed imports (the top session, e7).
// TUS keeps its own title contexts and request ids and reads no NpManager or NpCommon state: a context made for a user does
// not ask whether that user is signed in (AnyPS5; shadPS4 asks sceNpGetNpId first). Signed out is 0x80550006, as network.cpp
// and AnyPS5 answer; the off path keeps today's NP_NOT_SIGNED_IN (0x80550005).
// AnyPS5's and shadPS4's copyrights remain with their authors; GPL-2.0 as the rest of this file.
static bool Bc5NtuOn() {
»static const bool on = [] {
»»const char* e = std::getenv("KYTY_BC5_LOAD_NPTUS");
»»const bool  v = e != nullptr && e[0] != '\0' && std::strcmp(e, "0") != 0;
»»std::fprintf(stderr, "%s\n",
»»             v ? "[bc5] exp 0405: nptus port on (items: context request abort poll wait slots variable data status "
»»                 "friends users tss)"
»»               : "[bc5] exp 0405: nptus port off");
»»std::fflush(stderr);
»»return v;
»}();
»return on;
}

// The item switch KYTY_BC5_NPTUS_FRIENDS_RUN: default off, read once, and it acts only when KYTY_BC5_LOAD_NPTUS is on. On,
// these calls check as an emulator run of firmware 13.42's libSceNpTus did, as AnyPS5's debt note
// docs/dev/debt/libSceNpTus.md reports it ("Friends, cross-save and virtual-user argument checks", AnyPS5 PR 10675; the
// maintainer's decision 1 of 2026-11-04 accepts values from firmware runs), in place of AnyPS5's shadPS4-based code:
//  - the A and cross-save friends calls: an option of another size is INVALID_ARGUMENT, a start rank of 0 is taken. Kept
//    as AnyPS5 (the run leaves them unknown here): the array-size check (0x80550714 unless arrayLen entries; the note gives
//    no entry size) and zeroing the array for SDK 5.50 and later (no compiled SDK version is reachable in this file);
//  - sceNpTusGetDataForCrossSaveVUser and its Async form: only a data-status size of 0x1F0 or 0x210 is taken, and a null
//    status or an empty name is taken. The run names no code for another size: INVALID_ALIGNMENT here, the code AnyPS5 and
//    shadPS4 give a wrong structure size, TODO(verify); it sits where AnyPS5 checks the status;
//  - sceNpTusDeleteMultiSlotDataVUser and its Async form: a null or an empty user and arrayLen -1 are taken, 0 is
//    INVALID_ARGUMENT. Kept as AnyPS5 (not in the run): null slot ids, other negative lengths, the option, too many slots,
//    negative slot ids. What follows for a null user is unknown: offline the request finishes signed out, as every request.
static bool Bc5NtuRunOn() {
»static const bool on = [] {
»»const char* e   = std::getenv("KYTY_BC5_NPTUS_FRIENDS_RUN");
»»const bool  set = e != nullptr && e[0] != '\0' && std::strcmp(e, "0") != 0;
»»const bool  v   = set && Bc5NtuOn();
»»std::fprintf(stderr, "%s\n",
»»             v     ? "[bc5] exp 0405: nptus friends run on (items: friends-option friends-rank cross-save-status "
»»                     "delete-user delete-count)"
»»             : set ? "[bc5] exp 0405: nptus friends run off (the nptus port is off)"
»»                   : "[bc5] exp 0405: nptus friends run off");
»»std::fflush(stderr);
»»return v;
»}();
»return on;
}

constexpr int      BC5_NTU_SIGNED_OUT        = static_cast<int>(0x80550006u);
constexpr int      BC5_NTU_INVALID_ARGUMENT  = static_cast<int>(0x80550704u);
constexpr int      BC5_NTU_TOO_MANY_OBJECTS  = static_cast<int>(0x80550706u);
constexpr int      BC5_NTU_ABORTED           = static_cast<int>(0x80550707u);
constexpr int      BC5_NTU_INSUFFICIENT      = static_cast<int>(0x8055070Cu);
constexpr int      BC5_NTU_INVALID_ID        = static_cast<int>(0x8055070Eu);
constexpr int      BC5_NTU_INVALID_TYPE      = static_cast<int>(0x80550711u);
constexpr int      BC5_NTU_INVALID_ALIGNMENT = static_cast<int>(0x80550714u);
constexpr int      BC5_NTU_TOO_MANY_SLOTS    = static_cast<int>(0x80550718u);
constexpr int      BC5_NTU_TOO_MANY_USERS    = static_cast<int>(0x80550719u);
constexpr int      BC5_NTU_POLL_RUNNING      = 1;
constexpr size_t   BC5_NTU_MAX_CONTEXTS      = 32;
constexpr size_t   BC5_NTU_MAX_REQUESTS      = 256;
constexpr int      BC5_NTU_MAX_SLOTS         = 64;
constexpr int      BC5_NTU_MAX_USERS         = 101;
constexpr int      BC5_NTU_MAX_FRIENDS       = 100;
constexpr int32_t  BC5_NTU_TSS_LAST_SLOT     = 15;
constexpr uint64_t BC5_NTU_TSS_MAX_SIZE      = 64u * 1024u;
constexpr uint32_t BC5_NTU_NO_SERVICE_LABEL  = 0xFFFFFFFFu;
constexpr size_t   BC5_NTU_NAME_STRIDE       = 20;   // an online id: 16 characters, a terminator, 3 bytes of padding
constexpr uint64_t BC5_NTU_FRIENDS_OPT_SIZE  = 0x18; // its size, then pointers to a start rank and to the hits
constexpr uint64_t BC5_NTU_TSS_OPT_SIZE      = 0x20; // its size, then pointers to an offset, a last byte and a condition
constexpr uint64_t BC5_NTU_TSS_STATUS_SIZE   = 0x18; // a time, a status, a content length
constexpr uint64_t BC5_NTU_RUN_STATUS_SHORT  = 0x1F0; // the 13.42 run: the two data-status sizes it takes
constexpr uint64_t BC5_NTU_RUN_STATUS_LONG   = 0x210;
constexpr int32_t  BC5_NTU_SORT_FIRST        = 1;    // the friends calls' sort orders start at 1
constexpr int32_t  BC5_NTU_STATUS_SORT_LAST  = 2;    // data statuses: by date, two ways
constexpr int32_t  BC5_NTU_VALUE_SORT_LAST   = 4;    // variables: by date or by value, two ways each
constexpr int32_t  BC5_NTU_OP_FIRST          = 1;    // try-and-set: the six comparisons, 1 to 6
constexpr int32_t  BC5_NTU_OP_LAST           = 6;

struct Bc5NtuRequest {
»int  context = 0;
»bool started = false;
»bool aborted = false;
»int  result  = 0;
};

struct Bc5NtuState {
»std::mutex                   mutex;
»std::set<int>                contexts;
»std::map<int, Bc5NtuRequest> requests;
»int                          next_context = 1;
»int                          next_request = 1;
};

static Bc5NtuState& Bc5Ntu() {
»static auto* s = new Bc5NtuState; // never destroyed: guest threads may call late
»return *s;
}

// Title contexts: one table for the TUS and TSS, NpId and user forms (AnyPS5 :128-145, 222-230, 1055-1057).
static int Bc5NtuNewContext() {
»auto&           st = Bc5Ntu();
»std::lock_guard lock(st.mutex);
»if (st.contexts.size() >= BC5_NTU_MAX_CONTEXTS) {
»»return BC5_NTU_TOO_MANY_OBJECTS;
»}
»const int id = st.next_context++;
»st.contexts.insert(id);
»return id;
}

static int Bc5NtuNewContextNpId(uint32_t service_label, const void* np_id) {
»if (np_id == nullptr) {
»»return BC5_NTU_INSUFFICIENT;
»}
»if (service_label == BC5_NTU_NO_SERVICE_LABEL) {
»»return BC5_NTU_INVALID_ARGUMENT;
»}
»return Bc5NtuNewContext();
}

static int Bc5NtuDeleteContext(int context) {
»auto&           st = Bc5Ntu();
»std::lock_guard lock(st.mutex);
»if (st.contexts.erase(context) == 0) {
»»return BC5_NTU_INVALID_ID;
»}
»for (auto it = st.requests.begin(); it != st.requests.end();) { // the context's requests go with it
»»if (it->second.context == context) {
»»»it = st.requests.erase(it);
»»} else {
»»»++it;
»»}
»}
»return 0;
}

// Requests (AnyPS5 :147-183, 247-249).
static int Bc5NtuNewRequest(int context) {
»auto&           st = Bc5Ntu();
»std::lock_guard lock(st.mutex);
»if (st.contexts.count(context) == 0) {
»»return BC5_NTU_INVALID_ID;
»}
»if (st.requests.size() >= BC5_NTU_MAX_REQUESTS) {
»»return BC5_NTU_TOO_MANY_OBJECTS;
»}
»Bc5NtuRequest request;
»request.context = context;
»const int id    = st.next_request++;
»st.requests[id] = request;
»return id;
}

static int Bc5NtuDeleteRequest(int request) {
»auto&           st = Bc5Ntu();
»std::lock_guard lock(st.mutex);
»return st.requests.erase(request) != 0 ? 0 : BC5_NTU_INVALID_ID;
}

static int Bc5NtuAbort(int request) { // an abort stays: every later start of the request finishes ABORTED
»auto&           st = Bc5Ntu();
»std::lock_guard lock(st.mutex);
»const auto      it = st.requests.find(request);
»if (it == st.requests.end()) {
»»return BC5_NTU_INVALID_ID;
»}
»it->second.aborted = true;
»return 0;
}

static int Bc5NtuPoll(int request, int* result) {
»auto&           st = Bc5Ntu();
»std::lock_guard lock(st.mutex);
»const auto      it = st.requests.find(request);
»if (it == st.requests.end()) {
»»return BC5_NTU_INVALID_ID;
»}
»if (!it->second.started) {
»»return BC5_NTU_POLL_RUNNING;
»}
»if (result != nullptr) {
»»*result = it->second.result;
»}
»return 0;
}

static int Bc5NtuWait(int request, int* result) {
»auto&           st = Bc5Ntu();
»std::lock_guard lock(st.mutex);
»const auto      it = st.requests.find(request);
»if (it == st.requests.end()) {
»»return BC5_NTU_INVALID_ID;
»}
»if (!it->second.started) {
»»return BC5_NTU_INVALID_ARGUMENT;
»}
»if (result != nullptr) {
»»*result = it->second.result;
»}
»return 0;
}

// An *Async call: its argument check first (0: passed), then the request starts and finishes at once, signed out, or
// aborted once the request was aborted (AnyPS5 :103-110).
static int Bc5NtuStart(int request, int check) {
»if (check != 0) {
»»return check;
»}
»auto&           st = Bc5Ntu();
»std::lock_guard lock(st.mutex);
»const auto      it = st.requests.find(request);
»if (it == st.requests.end()) {
»»return BC5_NTU_INVALID_ID;
»}
»it->second.started = true;
»it->second.result  = it->second.aborted ? BC5_NTU_ABORTED : BC5_NTU_SIGNED_OUT;
»return 0;
}

// A blocking call: its *Async form, then the request's result (AnyPS5 :112-126).
static int Bc5NtuBlock(int request, int check) {
»const int started = Bc5NtuStart(request, check);
»if (started < 0) {
»»return started;
»}
»int       result = 0;
»const int waited = Bc5NtuWait(request, &result);
»return waited != 0 ? waited : result;
}

// An online id whose first character is 0 names nobody (AnyPS5 :99-101).
static bool Bc5NtuNoName(const void* name) {
»return static_cast<const char*>(name)[0] == '\0';
}

static bool Bc5NtuNegativeSlot(const int32_t* slot_ids, int count) {
»for (int i = 0; i < count; i++) {
»»if (slot_ids[i] < 0) {
»»»return true;
»»}
»}
»return false;
}

// The slot list of the multi-slot calls (AnyPS5 :50-63).
static int Bc5NtuSlotList(const int32_t* slot_ids, int count, const void* option) {
»if (slot_ids == nullptr) {
»»return BC5_NTU_INSUFFICIENT;
»}
»if (count < 1 || option != nullptr) {
»»return BC5_NTU_INVALID_ARGUMENT;
»}
»if (count > BC5_NTU_MAX_SLOTS) {
»»return BC5_NTU_TOO_MANY_SLOTS;
»}
»return Bc5NtuNegativeSlot(slot_ids, count) ? BC5_NTU_INVALID_ARGUMENT : 0;
}

static int Bc5NtuSlotListNeeded(const int32_t* slot_ids, int count, const void* option) {
»if (slot_ids == nullptr || count < 1) {
»»return BC5_NTU_INSUFFICIENT;
»}
»return Bc5NtuSlotList(slot_ids, count, option);
}

// Multi-slot variables, get and set, the NpId, account and cross-save forms: the target is not checked (AnyPS5 :185-198,
// 255-261, 283-289, 311-316).
static int Bc5NtuSlotValues(const int32_t* slot_ids, const void* values, int count, const void* option) {
»if (values == nullptr) {
»»return BC5_NTU_INSUFFICIENT;
»}
»return Bc5NtuSlotList(slot_ids, count, option);
}

// ... their virtual-user forms (AnyPS5 :263-277, 295-301, 318-323); the VUser get form also needs a slot (need_slots).
static int Bc5NtuSlotValuesUser(const void* user, const int32_t* slot_ids, const void* values, int count, const void* option,
»                               bool need_slots) {
»if (user == nullptr || values == nullptr) {
»»return BC5_NTU_INSUFFICIENT;
»}
»const int slots = need_slots ? Bc5NtuSlotListNeeded(slot_ids, count, option) : Bc5NtuSlotList(slot_ids, count, option);
»if (slots != 0) {
»»return slots;
»}
»return Bc5NtuNoName(user) ? BC5_NTU_INVALID_ARGUMENT : 0;
}

// Multi-slot delete of variables and data, the NpId and virtual-user forms (AnyPS5 :329-355, 520-526); the account forms
// are Bc5NtuSlotList alone (:200-204, 511-518).
static int Bc5NtuSlotDelete(const void* target, const int32_t* slot_ids, int count, const void* option, bool by_name) {
»if (target == nullptr) {
»»return BC5_NTU_INSUFFICIENT;
»}
»const int slots = Bc5NtuSlotListNeeded(slot_ids, count, option);
»if (slots != 0) {
»»return slots;
»}
»return by_name && Bc5NtuNoName(target) ? BC5_NTU_INVALID_ARGUMENT : 0;
}

// Add and get (AnyPS5 :206-215, 454-509): each form checks in its own order.
static int Bc5NtuAddAccount(int32_t slot_id, const void* out, const void* option) {
»if (out == nullptr) {
»»return BC5_NTU_INSUFFICIENT;
»}
»return slot_id < 0 || option != nullptr ? BC5_NTU_INVALID_ARGUMENT : 0;
}

static int Bc5NtuAddCrossSave(int32_t slot_id, const void* out, const void* option) {
»if (option != nullptr || slot_id < 0) {
»»return BC5_NTU_INVALID_ARGUMENT;
»}
»return out == nullptr ? BC5_NTU_INSUFFICIENT : 0;
}

static int Bc5NtuAddNpId(int32_t slot_id, const void* out, const void* option) {
»if (option != nullptr) {
»»return BC5_NTU_INVALID_ARGUMENT;
»}
»if (out == nullptr) {
»»return BC5_NTU_INSUFFICIENT;
»}
»return slot_id < 0 ? BC5_NTU_INVALID_ARGUMENT : 0;
}

// option_first: the VUser form; the AVUser and cross-save VUser forms check the user and the output first.
static int Bc5NtuAddUser(const void* user, int32_t slot_id, const void* out, const void* option, bool option_first) {
»if (option_first && option != nullptr) {
»»return BC5_NTU_INVALID_ARGUMENT;
»}
»if (user == nullptr || out == nullptr) {
»»return BC5_NTU_INSUFFICIENT;
»}
»if (option != nullptr || slot_id < 0) {
»»return BC5_NTU_INVALID_ARGUMENT;
»}
»return Bc5NtuNoName(user) ? BC5_NTU_INVALID_ARGUMENT : 0;
}

// Get data (AnyPS5 :371-378, 528-575): the cross-save forms check the slot together with the option, the others after the
// data status.
static int Bc5NtuDataGet(const void* user, bool by_name, int32_t slot_id, const void* status, uint64_t status_size,
»                        const void* option, bool cross_save) {
»if (option != nullptr || (cross_save && slot_id < 0)) {
»»return BC5_NTU_INVALID_ARGUMENT;
»}
»if ((by_name && user == nullptr) || status == nullptr || status_size == 0) {
»»return BC5_NTU_INSUFFICIENT;
»}
»if (slot_id < 0) {
»»return BC5_NTU_INVALID_ARGUMENT;
»}
»return by_name && Bc5NtuNoName(user) ? BC5_NTU_INVALID_ARGUMENT : 0;
}

// Friends' variables and data statuses (AnyPS5 :65-84, 384-430, 577-595): the plain forms refuse any option; the A and
// cross-save forms read one (size 0x18; a start rank of 0 is refused) and never write its hits.
static int Bc5NtuFriends(int32_t slot_id, int32_t sort_type, int32_t last_sort, const void* array, int count,
»                        const void* option, bool option_read) {
»if (array == nullptr) {
»»return BC5_NTU_INSUFFICIENT;
»}
»if ((!option_read && option != nullptr) || count < 1 || slot_id < 0) {
»»return BC5_NTU_INVALID_ARGUMENT;
»}
»if (count > BC5_NTU_MAX_FRIENDS) {
»»return BC5_NTU_TOO_MANY_USERS;
»}
»if (sort_type < BC5_NTU_SORT_FIRST || sort_type > last_sort) {
»»return BC5_NTU_INVALID_ARGUMENT;
»}
»if (option == nullptr) {
»»return 0;
»}
»uint64_t        size  = 0;
»const uint32_t* start = nullptr;
»std::memcpy(&size, option, sizeof(size));
»std::memcpy(&start, static_cast<const uint8_t*>(option) + 8, sizeof(start));
»if (size != BC5_NTU_FRIENDS_OPT_SIZE) {
»»return Bc5NtuRunOn() ? BC5_NTU_INVALID_ARGUMENT : BC5_NTU_INVALID_ALIGNMENT; // the 13.42 run: INVALID_ARGUMENT
»}
»if (Bc5NtuRunOn()) {
»»return 0; // the 13.42 run takes a start rank of 0
»}
»return start != nullptr && *start == 0 ? BC5_NTU_INVALID_ARGUMENT : 0;
}

// sceNpTusGetDataForCrossSaveVUser and its Async form: AnyPS5's checks, or with KYTY_BC5_NPTUS_FRIENDS_RUN the 13.42 run's.
static int Bc5NtuDataGetCrossSaveUser(const void* user, int32_t slot_id, const void* status, uint64_t status_size,
»                                     const void* option) {
»if (!Bc5NtuRunOn()) {
»»return Bc5NtuDataGet(user, true, slot_id, status, status_size, option, true);
»}
»if (option != nullptr || slot_id < 0) { // AnyPS5 (the run reports nothing else here)
»»return BC5_NTU_INVALID_ARGUMENT;
»}
»if (user == nullptr) { // AnyPS5 (the run takes a null status and an empty name, not a null user)
»»return BC5_NTU_INSUFFICIENT;
»}
»if (status_size != BC5_NTU_RUN_STATUS_SHORT && status_size != BC5_NTU_RUN_STATUS_LONG) {
»»return BC5_NTU_INVALID_ALIGNMENT; // TODO(verify): the run names no code for another size
»}
»return 0;
}

// sceNpTusDeleteMultiSlotDataVUser and its Async form: AnyPS5's checks, or with KYTY_BC5_NPTUS_FRIENDS_RUN the 13.42 run's.
static int Bc5NtuSlotDeleteDataUser(const void* user, const int32_t* slot_ids, int count, const void* option) {
»if (!Bc5NtuRunOn()) {
»»return Bc5NtuSlotDelete(user, slot_ids, count, option, true);
»}
»if (slot_ids == nullptr) { // AnyPS5
»»return BC5_NTU_INSUFFICIENT;
»}
»if (count == 0) { // the run
»»return BC5_NTU_INVALID_ARGUMENT;
»}
»if (count < -1) { // AnyPS5's answer: the run tried -1 only
»»return BC5_NTU_INSUFFICIENT;
»}
»if (option != nullptr) { // AnyPS5
»»return BC5_NTU_INVALID_ARGUMENT;
»}
»if (count > BC5_NTU_MAX_SLOTS) { // AnyPS5
»»return BC5_NTU_TOO_MANY_SLOTS;
»}
»return Bc5NtuNegativeSlot(slot_ids, count) ? BC5_NTU_INVALID_ARGUMENT : 0; // AnyPS5; a null or empty user is taken
}

// Multi-slot data statuses, the account and AVUser forms (AnyPS5 :597-615, 626-644).
static int Bc5NtuSlotStatus(const void* user, bool by_name, const int32_t* slot_ids, const void* statuses, int count,
»                           const void* option) {
»if ((by_name && user == nullptr) || slot_ids == nullptr || statuses == nullptr) {
»»return BC5_NTU_INSUFFICIENT;
»}
»if (option != nullptr || count < 1) {
»»return BC5_NTU_INVALID_ARGUMENT;
»}
»if (count > BC5_NTU_MAX_SLOTS) {
»»return BC5_NTU_TOO_MANY_SLOTS;
»}
»if (Bc5NtuNegativeSlot(slot_ids, count)) {
»»return BC5_NTU_INVALID_ARGUMENT;
»}
»return by_name && Bc5NtuNoName(user) ? BC5_NTU_INVALID_ARGUMENT : 0;
}

// ... the NpId and VUser forms: no slot is INSUFFICIENT_ARGUMENT, too many is TOO_MANY_NPID (AnyPS5 :617-624, 646-654;
// shadPS4's difference, debt note).
static int Bc5NtuSlotStatusNpId(const void* target, bool by_name, const int32_t* slot_ids, const void* statuses, int count,
»                               const void* option) {
»if (target == nullptr || slot_ids == nullptr || statuses == nullptr || count < 1) {
»»return BC5_NTU_INSUFFICIENT;
»}
»if (option != nullptr) {
»»return BC5_NTU_INVALID_ARGUMENT;
»}
»if (count > BC5_NTU_MAX_SLOTS) {
»»return BC5_NTU_TOO_MANY_USERS;
»}
»if (Bc5NtuNegativeSlot(slot_ids, count)) {
»»return BC5_NTU_INVALID_ARGUMENT;
»}
»return by_name && Bc5NtuNoName(target) ? BC5_NTU_INVALID_ARGUMENT : 0;
}

// Several users' variables and data statuses (AnyPS5 :656-772): the NpId and VUser forms answer no user with
// INSUFFICIENT_ARGUMENT (need_count), the others with INVALID_ARGUMENT; the virtual-user forms refuse an empty name among
// the first count.
static int Bc5NtuUsers(const void* targets, int32_t slot_id, const void* array, int count, const void* option, bool by_name,
»                      bool need_count) {
»if (targets == nullptr || array == nullptr || (need_count && count < 1)) {
»»return BC5_NTU_INSUFFICIENT;
»}
»if (option != nullptr || count < 1 || slot_id < 0) {
»»return BC5_NTU_INVALID_ARGUMENT;
»}
»if (count > BC5_NTU_MAX_USERS) {
»»return BC5_NTU_TOO_MANY_USERS;
»}
»if (by_name) {
»»for (int i = 0; i < count; i++) {
»»»if (Bc5NtuNoName(static_cast<const uint8_t*>(targets) + static_cast<size_t>(i) * BC5_NTU_NAME_STRIDE)) {
»»»»return BC5_NTU_INVALID_ARGUMENT;
»»»}
»»}
»}
»return 0;
}

// Set data (AnyPS5 :774-820).
static int Bc5NtuDataSet(const void* user, bool by_name, int32_t slot_id, uint64_t total_size, uint64_t send_size,
»                        const void* data, const void* option) {
»if (option != nullptr) {
»»return BC5_NTU_INVALID_ARGUMENT;
»}
»if ((by_name && user == nullptr) || data == nullptr || send_size == 0) {
»»return BC5_NTU_INSUFFICIENT;
»}
»if (slot_id < 0 || send_size > total_size) {
»»return BC5_NTU_INVALID_ARGUMENT;
»}
»return by_name && Bc5NtuNoName(user) ? BC5_NTU_INVALID_ARGUMENT : 0;
}

// Try and set (AnyPS5 :822-897): an operation outside 1 to 6 is INVALID_TYPE in the account, AVUser and cross-save forms,
// INVALID_ARGUMENT in the NpId and VUser forms (bad_op; shadPS4's difference, debt note).
static int Bc5NtuTrySet(const void* target, bool need_target, bool by_name, int32_t slot_id, int32_t op_type,
»                       const void* result_variable, const void* option, int bad_op) {
»if ((need_target && target == nullptr) || result_variable == nullptr) {
»»return BC5_NTU_INSUFFICIENT;
»}
»if (option != nullptr || slot_id < 0) {
»»return BC5_NTU_INVALID_ARGUMENT;
»}
»if (op_type < BC5_NTU_OP_FIRST || op_type > BC5_NTU_OP_LAST) {
»»return bad_op;
»}
»return by_name && Bc5NtuNoName(target) ? BC5_NTU_INVALID_ARGUMENT : 0;
}

// TSS data (AnyPS5 :432-440): the option's size, then the data status's size (a null status is taken), then the slot.
static int Bc5NtuTssData(int32_t slot_id, const void* status, uint64_t status_size, const void* option) {
»if (option != nullptr) {
»»uint64_t size = 0;
»»std::memcpy(&size, option, sizeof(size));
»»if (size != BC5_NTU_TSS_OPT_SIZE) {
»»»return BC5_NTU_INVALID_ALIGNMENT;
»»}
»}
»if (status != nullptr && status_size != BC5_NTU_TSS_STATUS_SIZE) {
»»return BC5_NTU_INVALID_ALIGNMENT;
»}
»if (slot_id < 0 || slot_id > BC5_NTU_TSS_LAST_SLOT) {
»»return BC5_NTU_INVALID_ARGUMENT;
»}
»return 0;
}

// TSS small storage (AnyPS5 :446-452).
static int Bc5NtuTssSmall(uint64_t max_size, const void* option) {
»return option != nullptr || max_size > BC5_NTU_TSS_MAX_SIZE ? BC5_NTU_INVALID_ARGUMENT : 0;
}
// ---- end of BC5 experiment 0405 (tbt) NpTus block ----
"""

# ---------------------------------------------------------------------------------------------------------------------
# The stubs: (name, parameter list, the call the switch makes).
# ---------------------------------------------------------------------------------------------------------------------
NPID_UNUSED = "const void* /*target_np_id*/"
NPID = "const void* target_np_id"
ACCOUNT = "uint64_t /*target_account_id*/"
USER = "const void* target_user"


def pair(base, params, check):
    """The *Async form starts the request; the blocking form starts it and returns its result."""
    return [(base + "Async", params, f"Bc5NtuStart(req_id, {check})"),
            (base, params, f"Bc5NtuBlock(req_id, {check})")]


def p_slot_get(t):
    return f"int req_id, {t}, const int32_t* slot_ids, void* variables, uint64_t /*variables_size*/, int count, void* option"


def p_slot_set(t):
    return f"int req_id, {t}, const int32_t* slot_ids, const int64_t* values, int count, void* option"


def p_slot_delete(t):
    return f"int req_id, {t}, const int32_t* slot_ids, int count, void* option"


def p_add(t):
    return (f"int req_id, {t}, int32_t slot_id, int64_t /*value*/, const void* /*last_author*/, const void* /*last_date*/, "
            f"void* out, uint64_t /*out_size*/, void* option")


def p_data_get(t):
    return (f"int req_id, {t}, int32_t slot_id, void* status, uint64_t status_size, void* /*data*/, "
            f"uint64_t /*recv_size*/, void* option")


P_FRIENDS = ("int req_id, int32_t slot_id, int32_t /*include_self*/, int32_t sort_type, void* array, uint64_t /*array_size*/, "
             "int count, void* option")


def p_slot_status(t):
    return f"int req_id, {t}, const int32_t* slot_ids, void* statuses, uint64_t /*statuses_size*/, int count, void* option"


P_USERS = "int req_id, const void* targets, int32_t slot_id, void* array, uint64_t /*array_size*/, int count, void* option"


def p_data_set(t):
    return (f"int req_id, {t}, int32_t slot_id, uint64_t total_size, uint64_t send_size, const void* data, "
            f"const void* /*info*/, uint64_t /*info_size*/, const void* /*last_author*/, const void* /*last_date*/, "
            f"void* option")


def p_try_set(t):
    return (f"int req_id, {t}, int32_t slot_id, int32_t op_type, int64_t /*value*/, const int64_t* /*compare_value*/, "
            f"const void* /*last_author*/, const void* /*last_date*/, void* result_variable, uint64_t /*result_size*/, "
            f"void* option")


P_TSS_DATA = ("int req_id, int32_t slot_id, void* status, uint64_t status_size, void* /*data*/, uint64_t /*recv_size*/, "
              "const void* option")
P_TSS_SMALL = "int req_id, void* /*data*/, uint64_t max_size, uint64_t* /*content_length*/, void* option"

SLOTS = "slot_ids, count, option"
STUBS = [
    # title contexts, requests, abort, poll, wait (AnyPS5 :141-183, 222-230, 247-249, 1055-1057)
    ("sceNpTssCreateNpTitleCtx", "uint32_t service_label, const void* np_id", "Bc5NtuNewContextNpId(service_label, np_id)"),
    ("sceNpTusCreateNpTitleCtx", "uint32_t service_label, const void* np_id", "Bc5NtuNewContextNpId(service_label, np_id)"),
    ("sceNpTssCreateNpTitleCtxA", "uint32_t /*service_label*/, int /*user_id*/", "Bc5NtuNewContext()"),
    ("sceNpTusCreateNpTitleCtxA", "uint32_t /*service_label*/, int /*user_id*/", "Bc5NtuNewContext()"),
    ("sceNpTusCreateRequest", "int title_ctx_id", "Bc5NtuNewRequest(title_ctx_id)"),
    ("sceNpTusDeleteNpTitleCtx", "int title_ctx_id", "Bc5NtuDeleteContext(title_ctx_id)"),
    ("sceNpTusDeleteRequest", "int req_id", "Bc5NtuDeleteRequest(req_id)"),
    ("sceNpTusAbortRequest", "int req_id", "Bc5NtuAbort(req_id)"),
    ("sceNpTusPollAsync", "int req_id, int* result", "Bc5NtuPoll(req_id, result)"),
    ("sceNpTusWaitAsync", "int req_id, int* result", "Bc5NtuWait(req_id, result)"),
]
# multi-slot variables: get
STUBS += pair("sceNpTusGetMultiSlotVariable", p_slot_get(NPID_UNUSED), f"Bc5NtuSlotValues(slot_ids, variables, count, option)")
STUBS += pair("sceNpTusGetMultiSlotVariableA", p_slot_get(ACCOUNT), f"Bc5NtuSlotValues(slot_ids, variables, count, option)")
STUBS += pair("sceNpTusGetMultiSlotVariableForCrossSave", p_slot_get(ACCOUNT),
              f"Bc5NtuSlotValues(slot_ids, variables, count, option)")
STUBS += pair("sceNpTusGetMultiSlotVariableVUser", p_slot_get(USER),
              f"Bc5NtuSlotValuesUser(target_user, slot_ids, variables, count, option, true)")
STUBS += pair("sceNpTusGetMultiSlotVariableAVUser", p_slot_get(USER),
              f"Bc5NtuSlotValuesUser(target_user, slot_ids, variables, count, option, false)")
STUBS += pair("sceNpTusGetMultiSlotVariableForCrossSaveVUser", p_slot_get(USER),
              f"Bc5NtuSlotValuesUser(target_user, slot_ids, variables, count, option, false)")
# multi-slot variables: set
STUBS += pair("sceNpTusSetMultiSlotVariable", p_slot_set(NPID_UNUSED), "Bc5NtuSlotValues(slot_ids, values, count, option)")
STUBS += pair("sceNpTusSetMultiSlotVariableA", p_slot_set(ACCOUNT), "Bc5NtuSlotValues(slot_ids, values, count, option)")
STUBS += pair("sceNpTusSetMultiSlotVariableVUser", p_slot_set(USER),
              "Bc5NtuSlotValuesUser(target_user, slot_ids, values, count, option, false)")
# multi-slot delete: variables and data
STUBS += pair("sceNpTusDeleteMultiSlotVariable", p_slot_delete(NPID), f"Bc5NtuSlotDelete(target_np_id, {SLOTS}, false)")
STUBS += pair("sceNpTusDeleteMultiSlotVariableA", p_slot_delete(ACCOUNT), f"Bc5NtuSlotList({SLOTS})")
STUBS += pair("sceNpTusDeleteMultiSlotVariableVUser", p_slot_delete(USER), f"Bc5NtuSlotDelete(target_user, {SLOTS}, true)")
STUBS += pair("sceNpTusDeleteMultiSlotData", p_slot_delete(NPID), f"Bc5NtuSlotDelete(target_np_id, {SLOTS}, false)")
STUBS += pair("sceNpTusDeleteMultiSlotDataA", p_slot_delete(ACCOUNT), f"Bc5NtuSlotList({SLOTS})")
STUBS += pair("sceNpTusDeleteMultiSlotDataVUser", p_slot_delete(USER), f"Bc5NtuSlotDeleteDataUser(target_user, {SLOTS})")
# add and get
STUBS += pair("sceNpTusAddAndGetVariable", p_add(NPID_UNUSED), "Bc5NtuAddNpId(slot_id, out, option)")
STUBS += pair("sceNpTusAddAndGetVariableA", p_add(ACCOUNT), "Bc5NtuAddAccount(slot_id, out, option)")
STUBS += pair("sceNpTusAddAndGetVariableForCrossSave", p_add(ACCOUNT), "Bc5NtuAddCrossSave(slot_id, out, option)")
STUBS += pair("sceNpTusAddAndGetVariableVUser", p_add(USER), "Bc5NtuAddUser(target_user, slot_id, out, option, true)")
STUBS += pair("sceNpTusAddAndGetVariableAVUser", p_add(USER), "Bc5NtuAddUser(target_user, slot_id, out, option, false)")
STUBS += pair("sceNpTusAddAndGetVariableForCrossSaveVUser", p_add(USER),
              "Bc5NtuAddUser(target_user, slot_id, out, option, false)")
# get data
DG = "slot_id, status, status_size, option"
STUBS += pair("sceNpTusGetData", p_data_get(NPID_UNUSED), f"Bc5NtuDataGet(nullptr, false, {DG}, false)")
STUBS += pair("sceNpTusGetDataA", p_data_get(ACCOUNT), f"Bc5NtuDataGet(nullptr, false, {DG}, false)")
STUBS += pair("sceNpTusGetDataForCrossSave", p_data_get(ACCOUNT), f"Bc5NtuDataGet(nullptr, false, {DG}, true)")
STUBS += pair("sceNpTusGetDataVUser", p_data_get(USER), f"Bc5NtuDataGet(target_user, true, {DG}, false)")
STUBS += pair("sceNpTusGetDataAVUser", p_data_get(USER), f"Bc5NtuDataGet(target_user, true, {DG}, false)")
STUBS += pair("sceNpTusGetDataForCrossSaveVUser", p_data_get(USER), f"Bc5NtuDataGetCrossSaveUser(target_user, {DG})")
# friends
FR = "array, count, option"
STUBS += pair("sceNpTusGetFriendsDataStatus", P_FRIENDS,
              f"Bc5NtuFriends(slot_id, sort_type, BC5_NTU_STATUS_SORT_LAST, {FR}, false)")
STUBS += pair("sceNpTusGetFriendsVariable", P_FRIENDS, f"Bc5NtuFriends(slot_id, sort_type, BC5_NTU_VALUE_SORT_LAST, {FR}, false)")
STUBS += pair("sceNpTusGetFriendsDataStatusA", P_FRIENDS,
              f"Bc5NtuFriends(slot_id, sort_type, BC5_NTU_STATUS_SORT_LAST, {FR}, true)")
STUBS += pair("sceNpTusGetFriendsDataStatusForCrossSave", P_FRIENDS,
              f"Bc5NtuFriends(slot_id, sort_type, BC5_NTU_STATUS_SORT_LAST, {FR}, true)")
STUBS += pair("sceNpTusGetFriendsVariableA", P_FRIENDS, f"Bc5NtuFriends(slot_id, sort_type, BC5_NTU_VALUE_SORT_LAST, {FR}, true)")
STUBS += pair("sceNpTusGetFriendsVariableForCrossSave", P_FRIENDS,
              f"Bc5NtuFriends(slot_id, sort_type, BC5_NTU_VALUE_SORT_LAST, {FR}, true)")
# multi-slot data statuses
SS = "slot_ids, statuses, count, option"
STUBS += pair("sceNpTusGetMultiSlotDataStatus", p_slot_status(NPID), f"Bc5NtuSlotStatusNpId(target_np_id, false, {SS})")
STUBS += pair("sceNpTusGetMultiSlotDataStatusVUser", p_slot_status(USER), f"Bc5NtuSlotStatusNpId(target_user, true, {SS})")
STUBS += pair("sceNpTusGetMultiSlotDataStatusA", p_slot_status(ACCOUNT), f"Bc5NtuSlotStatus(nullptr, false, {SS})")
STUBS += pair("sceNpTusGetMultiSlotDataStatusForCrossSave", p_slot_status(ACCOUNT), f"Bc5NtuSlotStatus(nullptr, false, {SS})")
STUBS += pair("sceNpTusGetMultiSlotDataStatusAVUser", p_slot_status(USER), f"Bc5NtuSlotStatus(target_user, true, {SS})")
STUBS += pair("sceNpTusGetMultiSlotDataStatusForCrossSaveVUser", p_slot_status(USER),
              f"Bc5NtuSlotStatus(target_user, true, {SS})")
# several users
US = "targets, slot_id, array, count, option"
for base, by_name, need_count in (
        ("sceNpTusGetMultiUserDataStatus", "false", "true"),
        ("sceNpTusGetMultiUserDataStatusVUser", "true", "true"),
        ("sceNpTusGetMultiUserDataStatusA", "false", "false"),
        ("sceNpTusGetMultiUserDataStatusForCrossSave", "false", "false"),
        ("sceNpTusGetMultiUserDataStatusAVUser", "true", "false"),
        ("sceNpTusGetMultiUserDataStatusForCrossSaveVUser", "true", "false"),
        ("sceNpTusGetMultiUserVariable", "false", "true"),
        ("sceNpTusGetMultiUserVariableVUser", "true", "true"),
        ("sceNpTusGetMultiUserVariableA", "false", "false"),
        ("sceNpTusGetMultiUserVariableForCrossSave", "false", "false"),
        ("sceNpTusGetMultiUserVariableAVUser", "true", "false"),
        ("sceNpTusGetMultiUserVariableForCrossSaveVUser", "true", "false")):
    STUBS += pair(base, P_USERS, f"Bc5NtuUsers({US}, {by_name}, {need_count})")
# set data
DS = "slot_id, total_size, send_size, data, option"
STUBS += pair("sceNpTusSetData", p_data_set(NPID_UNUSED), f"Bc5NtuDataSet(nullptr, false, {DS})")
STUBS += pair("sceNpTusSetDataA", p_data_set(ACCOUNT), f"Bc5NtuDataSet(nullptr, false, {DS})")
STUBS += pair("sceNpTusSetDataVUser", p_data_set(USER), f"Bc5NtuDataSet(target_user, true, {DS})")
STUBS += pair("sceNpTusSetDataAVUser", p_data_set(USER), f"Bc5NtuDataSet(target_user, true, {DS})")
# try and set
TS = "slot_id, op_type, result_variable, option"
STUBS += pair("sceNpTusTryAndSetVariable", p_try_set(NPID),
              f"Bc5NtuTrySet(target_np_id, true, false, {TS}, BC5_NTU_INVALID_ARGUMENT)")
STUBS += pair("sceNpTusTryAndSetVariableVUser", p_try_set(USER),
              f"Bc5NtuTrySet(target_user, true, true, {TS}, BC5_NTU_INVALID_ARGUMENT)")
STUBS += pair("sceNpTusTryAndSetVariableA", p_try_set(ACCOUNT), f"Bc5NtuTrySet(nullptr, false, false, {TS}, BC5_NTU_INVALID_TYPE)")
STUBS += pair("sceNpTusTryAndSetVariableForCrossSave", p_try_set(ACCOUNT),
              f"Bc5NtuTrySet(nullptr, false, false, {TS}, BC5_NTU_INVALID_TYPE)")
STUBS += pair("sceNpTusTryAndSetVariableAVUser", p_try_set(USER),
              f"Bc5NtuTrySet(target_user, true, true, {TS}, BC5_NTU_INVALID_TYPE)")
STUBS += pair("sceNpTusTryAndSetVariableForCrossSaveVUser", p_try_set(USER),
              f"Bc5NtuTrySet(target_user, true, true, {TS}, BC5_NTU_INVALID_TYPE)")
# TSS
STUBS += pair("sceNpTssGetData", P_TSS_DATA, "Bc5NtuTssData(slot_id, status, status_size, option)")
STUBS += pair("sceNpTssGetSmallStorage", P_TSS_SMALL, "Bc5NtuTssSmall(max_size, option)")

# Kept as today (AnyPS5: NotImplemented placeholders, sweep kind "pending").
HELD = ("sceNpTssGetStorage", "sceNpTssGetStorageAsync", "sceNpTusChangeModeForOtherSaveDataOwners", "sceNpTusCreateTitleCtx",
        "sceNpTusSetThreadParam", "sceNpTusSetTimeout")
EXPECT_PORTED = 136
EXPECT_TABLE = 142
SWITCH = "KYTY_BC5_LOAD_NPTUS"
RUN_SWITCH = "KYTY_BC5_NPTUS_FRIENDS_RUN"
ON = "Bc5NtuOn"
RUN_ON = "Bc5NtuRunOn"
DEFINE = "InitNpTus_1"
# The held stubs' registration lines, in runs of adjacent lines: with the switch on they are not registered.
HELD_GROUPS = (
    (("IVSbAEOxJ6I", "sceNpTssGetStorage"), ("k5NZIzggbuk", "sceNpTssGetStorageAsync")),
    (("wjNhItL2wzg", "sceNpTusChangeModeForOtherSaveDataOwners"),),
    (("hhy8+oecGac", "sceNpTusCreateTitleCtx"),),
    (("6GKDdRCFx8c", "sceNpTusSetThreadParam"), ("KMlHj+tgfdQ", "sceNpTusSetTimeout")),
)


def held_line(nid, name, indent):
    return f"{indent}LIB_FUNC(\"{nid}\", NpTus::{name});\n"


def balance(b):
    return (b.count(b"{") - b.count(b"}"), b.count(b"(") - b.count(b")"), b.count(b"[") - b.count(b"]"))


def md5(b):
    return hashlib.md5(b).hexdigest()


def span(s):
    """Byte range of 'namespace NpTus {' ... '} // namespace NpTus' in s."""
    a = s.index(b"namespace " + NS + b" {\n")
    z = s.index(b"} // namespace " + NS + b"\n", a)
    assert s.count(b"namespace " + NS + b" {\n") == 1 and s.count(b"} // namespace " + NS + b"\n") == 1
    return a, z


def edits():
    out = [("block", ANCHOR, ANCHOR + BLOCK)]
    for name, params, call in STUBS:
        old = f"static int KYTY_SYSV_ABI {name}() {{\n»PRINT_NAME();\n"
        new = (f"static int KYTY_SYSV_ABI {name}({params}) {{\n»PRINT_NAME();\n"
               f"»if ({ON}()) {{ // BC5 experiment 0405 (tbt): the port, {SWITCH}\n"
               f"»»return {call};\n»}}\n")
        out.append((name, old, new))
    out.append((DEFINE, f"LIB_DEFINE({DEFINE}) {{\n",
                f"LIB_DEFINE({DEFINE}) {{\n»(void){ON}(); // BC5 experiment 0405 (tbt): reads {SWITCH} once, prints its line\n"
                f"»(void){RUN_ON}(); // BC5 experiment 0405 (tbt): reads {RUN_SWITCH} once, prints its line\n"))
    for group in HELD_GROUPS:
        old = "".join(held_line(nid, name, "»") for nid, name in group)
        new = (f"»if (!{ON}()) {{ // BC5 experiment 0405 (tbt): held, not registered when on (a stubbed import)\n"
               + "".join(held_line(nid, name, "»»") for nid, name in group) + "»}\n")
        out.append(("held " + group[0][1], old, new))
    return out


def edit(s):
    for m in MARKS:
        assert m not in s, ("refused: the unit has the edit already", m.decode())
    assert b"\r" not in s, "a CR in the LF unit"
    names = [n for n, _, _ in STUBS]
    assert len(names) == len(set(names)) == EXPECT_PORTED, ("ported stubs", len(names), len(set(names)))
    assert not set(names) & set(HELD)
    a0, z0 = span(s)
    table = s[a0:z0]
    assert table.count(b"\tLIB_FUNC(") == EXPECT_TABLE, ("table size", table.count(b"\tLIB_FUNC("))
    for n in names + list(HELD):  # every name is one of today's stubs, with today's body
        assert table.count(T(f"static int KYTY_SYSV_ABI {n}() {{\n»PRINT_NAME();\n»return NP_NOT_SIGNED_IN;\n}}\n")) == 1, n
        assert table.count(T(f", NpTus::{n});\n")) == 1, ("registration", n)
    assert balance(T(BLOCK)) == (0, 0, 0), ("the block is not balanced", balance(T(BLOCK)))
    out = s
    done = []  # (old bytes, new bytes) in order, for the undo check
    for what, old, new in edits():
        o, n = T(old), T(new)
        assert out.count(o) == 1, ("anchor", what, out.count(o))
        a, z = span(out)
        assert a < out.index(o) < z, ("anchor outside the namespace", what)
        assert balance(o) == balance(n), ("the edit changes the balance", what, balance(o), balance(n))
        out = out.replace(o, n)
        done.append((o, n))
    assert sorted(name for g in HELD_GROUPS for _, name in g) == sorted(HELD)
    # Bc5NtuOn(): in the block (its definition and the run switch), the stubs, the LIB_DEFINE line, the held groups
    want = BLOCK.count(f"{ON}()") + EXPECT_PORTED + 1 + len(HELD_GROUPS)
    assert out.count(T(f"{ON}()")) == want, ("switch uses", out.count(T(f"{ON}()")), want)
    want = BLOCK.count(f"{RUN_ON}()") + 1  # the block (its definition and the three calls that use it), the LIB_DEFINE line
    assert out.count(T(f"{RUN_ON}()")) == want == 6, ("run switch uses", out.count(T(f"{RUN_ON}()")), want)
    want = BLOCK.count(SWITCH) + EXPECT_PORTED + 1  # the block, the stubs' comments, the LIB_DEFINE line's comment
    assert out.count(SWITCH.encode()) == want, ("switch name", out.count(SWITCH.encode()), want)
    assert balance(out) == balance(s), ("the unit's balance changed", balance(s), balance(out))
    # Everything outside the namespace is byte for byte the same.
    a1, z1 = span(out)
    assert s[:a0] == out[:a1], "the text before namespace NpTus changed"
    assert s[z0:] == out[z1:], "the text after namespace NpTus changed"
    # The held stubs and every registration line are as they were.
    for n in HELD:
        assert out.count(T(f"static int KYTY_SYSV_ABI {n}() {{\n»PRINT_NAME();\n»return NP_NOT_SIGNED_IN;\n}}\n")) == 1, n
    held_regs = [T(held_line(nid, name, "")).rstrip(b"\n") for g in HELD_GROUPS for nid, name in g]
    reg0 = [l for l in table.split(b"\n") if l.startswith(b"\tLIB_FUNC(")]
    reg1 = [l for l in out[a1:z1].split(b"\n") if l.startswith(b"\tLIB_FUNC(")]
    assert reg1 == [l for l in reg0 if l[1:] not in held_regs], "the ported stubs' registration lines changed"
    assert len(reg1) == EXPECT_PORTED
    for l in held_regs:  # each held line once, inside its `if (!Bc5NtuOn())` block
        assert out.count(b"\t\t" + l + b"\n") == 1 and out.count(l) == 1, l
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
    assert list(PINS) == [REL]
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
