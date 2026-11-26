#!/usr/bin/env python3
"""BC5 experiment 0405 (series e6 of experiment 0401), tag "tbn": exp 0405 decision 4 ("=> B => B", the dead KytyPlus tables
are ported first, then loaded, each behind its own switch), batch 1, the three CPU-only Np tables of src/libs/libNp.cpp:
  namespace NpCommon   (InitNpCommon_1,  28 NIDs)  KYTY_BC5_LOAD_NPCOMMON   28 ported
  namespace NpManager  (InitNpManager_1, 27 NIDs)  KYTY_BC5_LOAD_NPMANAGER  20 ported, 1 already matches, 4 held, 2 live
                                                   (the 2 NIDs libNet.cpp also registers are not registered when on)
  namespace NpTrophy   (InitNpTrophy_1,  87 NIDs)  KYTY_BC5_LOAD_NPTROPHY   23 ported, 64 held
The same switch names make libs.cpp (agent tld) load the table. Off (unset, empty or "0") every stub takes today's path
(PRINT_NAME, then today's return); on, the stub calls the port. Sources: AnyPS5 4f41f4c37 (GPL-2.0-only) and shadPS4 60c42b9
(GPL-2.0-or-later), cited in each block. Only libNp.cpp is edited: three blocks (each after its namespace's LIB_VERSION
line), the stubs' parameter lists and one branch each, one line in each LIB_DEFINE, and includes. The other tables of the
file (NpAuth, NpPartner, NpParty, NpSnsFacebookDialog, NpTus) are not touched.
The input md5 is pinned and asserted; an input that has the edit already is refused; every anchor must occur exactly once;
each edit keeps braces, parentheses and brackets balanced; the inserted text is ASCII; line ends stay LF. After editing, the
script undoes its own edits on the output and asserts that this gives the input back byte for byte.
Prints "<relpath> <md5>". Notes: tbn0405-notes.md; CPU test: tbn0405.cpp.
usage: mktbn0405.py <tree root in> <out dir>"""
import hashlib
import os
import sys

REL = "src/libs/libNp.cpp"
PIN = "a2c5facee2708bed1556383b0f5bbdca"  # KytyPlus f266548 + patch 0001 (not changed by e4/e5)
MARKS = (b"experiment 0405", b"KYTY_BC5_LOAD_NPCOMMON", b"KYTY_BC5_LOAD_NPMANAGER", b"KYTY_BC5_LOAD_NPTROPHY", b"Bc5Npc",
         b"Bc5Npm", b"Bc5Npt")


def T(text):
    """C++ text written with a visible tab ("»") for each tab of the file's indentation, as ASCII bytes."""
    return text.replace("»", "\t").encode("ascii")


INCLUDES_OLD = "#include <common/abi.h>\n"
INCLUDES_NEW = r"""#include <common/abi.h>

// BC5 experiment 0405 (series e6 of experiment 0401, tag tbn): what the ports of NpCommon, NpManager and NpTrophy use.
#include "kernel/fileSystem.h"
#include "kernel/pthread.h"
#include "libs/network.h"

#include <bit>
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <map>
#include <mutex>
#include <optional>
#include <set>
#include <string>
"""

# =====================================================================================================================
# NpCommon
# =====================================================================================================================
NPC_ANCHOR = 'LIB_VERSION("libSceNpCommon", 1, "libSceNpCommon", 1, 1);\n'
NPC_BLOCK = r"""
// ---- BC5 experiment 0405 (series e6 of experiment 0401), tag tbn: KYTY_BC5_LOAD_NPCOMMON, the NpCommon table's port ----
// Exp 0405 decision 4 ("=> B => B", 2026-11-04): this table is compiled but Libs::InitAll never loaded it; it is ported
// first, then loaded behind KYTY_BC5_LOAD_NPCOMMON (libs.cpp). Unset, empty or "0" is off: every stub below takes today's
// path (PRINT_NAME, return OK). On, all 28 exports answer as:
//  - AnyPS5 (github.com/boykopovar/AnyPS5, GPL-2.0-only) @ 4f41f4c375f5abb487dbd184fbc150f31994d762,
//    core/libs/prx/libSceNpCommon/Export.cpp:40-81 (online id and NpId compares, platform type, online id check), 83-157
//    (the mutex, lightweight mutex, condition and join wrappers: EBUSY and ETIMEDOUT mapped to the NP errors), 159-165
//    (sceNpGetSystemClockUsec, commit 0a520ced9: a null destination is refused). Its debt note
//    docs/dev/debt/libSceNpCommon.md:36-38 names shadPS4 as the source of these and says none is measured on a console.
//  - AnyPS5 Export.cpp:167-175 (sceNpGetSdkVersion: clear 8 bytes, then write the system software version as major.minor),
//    commit 30933ef0c; debt :39 says it was "read from its disassembly and an emulator run" of firmware 13.42
//    (github.com/boykopovar/AnyPS5/pull/13684): a firmware run, accepted by the maintainer's decision 1 of 2026-11-04. The
//    version is our kernel's answer, 0x0A600000 (10.60, libs/bc5LleAgc.cpp GetProsperoSystemSwVersion); a null buffer is
//    left alone (host safety; the firmware writes without a check).
//  - shadPS4 (github.com/shadps4-emu/shadPS4, GPL-2.0-or-later) @ 60c42b9, src/core/libraries/np/np_common.cpp:23-30 and
//    np_common.h:25-39 (callout context and entry layout), 46-93 (the callout worker), 95-117 (sceNpCmpNpId), 276-318
//    (sceNpCreateThread), 405-555 (the callout exports). AnyPS5 has these seven in Runtime.cpp, which follows a firmware
//    disassembly (commit 736ee67ca); that code is not used. From AnyPS5 only two host-side choices are taken: 702d85e0b (a
//    queued callout is looked for before it is written) and 22d478c78 (a context is not terminated from one of its own
//    callouts: refused here with a stderr line, where AnyPS5 throws). sceNpCreateThread applies an explicit FIFO priority
//    whenever one is given, as AnyPS5's debt :50 does; shadPS4 does so only for a compiled SDK version >= 0x2500000
//    (TODO(verify) for titles built with an older SDK). A null callout context is refused with 0x80550003 (host safety).
// Adapted to our kernel (kernel/pthread.h: LibKernel::Pthread*). AnyPS5's and shadPS4's copyrights remain with their
// authors; GPL-2.0 as the rest of this file.
static bool Bc5NpcOn() {
»static const bool on = [] {
»»const char* e = std::getenv("KYTY_BC5_LOAD_NPCOMMON");
»»const bool  v = e != nullptr && e[0] != '\0' && std::strcmp(e, "0") != 0;
»»std::fprintf(stderr, "%s\n",
»»             v ? "[bc5] exp 0405: npcommon port on (items: ids mutex cond thread clock sdkversion callout)"
»»               : "[bc5] exp 0405: npcommon port off");
»»std::fflush(stderr);
»»return v;
»}();
»return on;
}

constexpr int    BC5_NPC_INVALID_ARGUMENT  = static_cast<int>(0x80550003u);
constexpr int    BC5_NPC_INVALID_PLATFORM  = static_cast<int>(0x80550004u);
constexpr int    BC5_NPC_NOT_MATCH         = static_cast<int>(0x80550609u);
constexpr int    BC5_NPC_CALLOUT_NOT_INIT  = static_cast<int>(0x80558001u);
constexpr int    BC5_NPC_CALLOUT_ALREADY   = static_cast<int>(0x80558002u);
constexpr int    BC5_NPC_CALLOUT_DUPLICATE = static_cast<int>(0x80558006u);
constexpr int    BC5_NPC_LW_COND_TIMEDOUT  = static_cast<int>(0x8055800Bu);
constexpr int    BC5_NPC_LW_MUTEX_BUSY     = static_cast<int>(0x8055800Fu);
constexpr size_t BC5_NPC_ONLINE_ID_MAX     = 16;

// An online id (16 characters, a terminator, 3 bytes of padding) and an NpId (online id, 8 option bytes, 8 reserved).
struct Bc5NpcOnlineId {
»char data[16];
»char term;
»char dummy[3];
};
struct Bc5NpcNpId {
»Bc5NpcOnlineId handle;
»uint8_t        opt[8];
»uint8_t        reserved[8];
};
static_assert(sizeof(Bc5NpcOnlineId) == 20 && sizeof(Bc5NpcNpId) == 36);

static int Bc5NpcCompareBytes(const uint8_t* a, const uint8_t* b, size_t n) {
»for (size_t i = 0; i < n; i++) {
»»if (a[i] != b[i]) {
»»»return a[i] < b[i] ? -1 : 1;
»»}
»}
»return 0;
}

static int Bc5NpcCmpOnlineId(const Bc5NpcOnlineId* a, const Bc5NpcOnlineId* b) {
»if (a == nullptr || b == nullptr) {
»»return BC5_NPC_INVALID_ARGUMENT;
»}
»return std::strncmp(a->data, b->data, BC5_NPC_ONLINE_ID_MAX) != 0 ? BC5_NPC_NOT_MATCH : OK;
}

static int Bc5NpcCmpNpId(const Bc5NpcNpId* a, const Bc5NpcNpId* b) {
»if (a == nullptr || b == nullptr) {
»»return BC5_NPC_INVALID_ARGUMENT;
»}
»if (std::strncmp(a->handle.data, b->handle.data, BC5_NPC_ONLINE_ID_MAX) != 0 || std::memcmp(a->opt, b->opt, 8) != 0 ||
»    std::memcmp(a->reserved, b->reserved, 8) != 0) {
»»return BC5_NPC_NOT_MATCH;
»}
»return OK;
}

static int Bc5NpcCmpNpIdInOrder(const Bc5NpcNpId* a, const Bc5NpcNpId* b, int32_t* order) {
»if (a == nullptr || b == nullptr || order == nullptr) {
»»return BC5_NPC_INVALID_ARGUMENT;
»}
»int c = std::strncmp(a->handle.data, b->handle.data, BC5_NPC_ONLINE_ID_MAX);
»if (c == 0) {
»»c = Bc5NpcCompareBytes(a->opt, b->opt, 8);
»}
»if (c == 0) {
»»c = Bc5NpcCompareBytes(a->reserved, b->reserved, 8);
»}
»*order = c < 0 ? -1 : (c > 0 ? 1 : 0);
»return OK;
}

static int Bc5NpcGetPlatformType(const Bc5NpcNpId* id) {
»if (id == nullptr) {
»»return BC5_NPC_INVALID_ARGUMENT;
»}
»if (id->opt[4] == 0) {
»»return 0;
»}
»uint32_t tag = 0;
»std::memcpy(&tag, id->opt + 4, sizeof(tag));
»switch (tag) {
»»case 0x00337370u: return 1; // "ps3"
»»case 0x32707370u: return 2; // "psp2"
»»case 0x00347370u: return 3; // "ps4"
»»default: return BC5_NPC_INVALID_PLATFORM;
»}
}

static int Bc5NpcIntIsValidOnlineId(const Bc5NpcOnlineId* id) {
»if (id == nullptr || id->term != 0) {
»»return 0;
»}
»size_t length = 0;
»while (length < BC5_NPC_ONLINE_ID_MAX && id->data[length] != 0) {
»»length++;
»}
»if (length < 3) {
»»return 0;
»}
»auto alnum = [](char ch) {
»»return (ch >= '0' && ch <= '9') || (ch >= 'a' && ch <= 'z') || (ch >= 'A' && ch <= 'Z');
»};
»if (!alnum(id->data[0])) {
»»return 0;
»}
»for (size_t i = 1; i < length; i++) {
»»if (!alnum(id->data[i]) && id->data[i] != '_' && id->data[i] != '-') {
»»»return 0;
»»}
»}
»return 1;
}

static int Bc5NpcMutexInit(LibKernel::PthreadMutex* mutex, const char* name, uint64_t flags) {
»LibKernel::PthreadMutexattr attr = nullptr;
»int                         r    = LibKernel::PthreadMutexattrInit(&attr);
»if (r != OK) {
»»return r;
»}
»if ((flags & 1u) != 0) {
»»r = LibKernel::PthreadMutexattrSettype(&attr, 2); // recursive (kernel/pthread.cpp KERNEL_PTHREAD_MUTEX_RECURSIVE)
»}
»if (r == OK) {
»»r = LibKernel::PthreadMutexInit(mutex, &attr, name);
»}
»LibKernel::PthreadMutexattrDestroy(&attr);
»return r;
}

static int Bc5NpcMutexTryLock(LibKernel::PthreadMutex* mutex) {
»const int r = LibKernel::PthreadMutexTrylock(mutex);
»return r == LibKernel::KERNEL_ERROR_EBUSY ? BC5_NPC_LW_MUTEX_BUSY : r;
}

static int Bc5NpcCondInit(LibKernel::PthreadCond* cond, const char* name) {
»LibKernel::PthreadCondattr attr = nullptr;
»int                        r    = LibKernel::PthreadCondattrInit(&attr);
»if (r != OK) {
»»return r;
»}
»r = LibKernel::PthreadCondInit(cond, &attr, name);
»LibKernel::PthreadCondattrDestroy(&attr);
»return r;
}

static int Bc5NpcCondTimedwait(LibKernel::PthreadCond* cond, LibKernel::PthreadMutex* mutex, uint32_t usec) {
»if (usec == 0) {
»»return LibKernel::PthreadCondWait(cond, mutex);
»}
»const int r = LibKernel::PthreadCondTimedwait(cond, mutex, usec);
»return r == LibKernel::KERNEL_ERROR_ETIMEDOUT ? BC5_NPC_LW_COND_TIMEDOUT : r;
}

static int Bc5NpcGetSystemClockUsec(int64_t* usec) {
»if (usec == nullptr) {
»»return BC5_NPC_INVALID_ARGUMENT;
»}
»LibKernel::KernelTimespec now {};
»const int                 r = LibKernel::KernelClockGettime(4, &now); // CLOCK_MONOTONIC
»if (r == OK) {
»»*usec = now.tv_sec * 1000000 + now.tv_nsec / 1000;
»}
»return r;
}

static int Bc5NpcGetSdkVersion(char* version) {
»if (version == nullptr) {
»»return OK;
»}
»std::memset(version, 0, 8);
»const uint32_t hex = 0x0A600000u; // our kernel's system software version (10.60)
»std::snprintf(version, 8, "%u.%02u", ((hex >> 24u) & 0xFu) + (hex >> 28u) * 10u,
»              ((hex >> 16u) & 0xFu) + ((hex >> 20u) & 0xFu) * 10u);
»return OK;
}

static int Bc5NpcCreateThread(LibKernel::Pthread* thread, LibKernel::pthread_entry_func_t entry, void* arg, int priority,
»                             uint64_t stack_size, uint64_t affinity, const char* name) {
»LibKernel::PthreadAttr attr = nullptr;
»int                    r    = LibKernel::PthreadAttrInit(&attr);
»if (r < 0) {
»»return r;
»}
»r = LibKernel::PthreadAttrSetstacksize(&attr, static_cast<size_t>(stack_size));
»if (r >= 0 && priority != 0) {
»»r = LibKernel::PthreadAttrSetinheritsched(&attr, 0); // explicit
»»if (r >= 0) {
»»»r = LibKernel::PthreadAttrSetschedpolicy(&attr, 1); // FIFO
»»}
»»if (r >= 0) {
»»»LibKernel::KernelSchedParam param {};
»»»param.sched_priority = priority;
»»»r                    = LibKernel::PthreadAttrSetschedparam(&attr, &param);
»»}
»}
»if (r >= 0 && affinity != 0) {
»»r = LibKernel::PthreadAttrSetaffinity(&attr, affinity);
»}
»if (r >= 0) {
»»r = LibKernel::PthreadCreate(thread, &attr, entry, arg, name);
»}
»LibKernel::PthreadAttrDestroy(&attr);
»return r;
}

using Bc5NpcCalloutHandler = KYTY_SYSV_ABI void (*)(void*);

// A callout (the guest's memory, 0x20 bytes) and a callout context (0x28 bytes), as shadPS4 lays them out.
struct Bc5NpcCallout {
»Bc5NpcCallout*       next;
»Bc5NpcCalloutHandler handler;
»int64_t              deadline_usec;
»void*                arg;
};
struct Bc5NpcCalloutCtx {
»LibKernel::Pthread      thread;
»LibKernel::PthreadMutex mutex;
»LibKernel::PthreadCond  cond;
»int32_t                 active;
»int32_t                 stop_requested;
»Bc5NpcCallout*          head;
};
static_assert(sizeof(Bc5NpcCallout) == 0x20 && offsetof(Bc5NpcCallout, deadline_usec) == 0x10);
static_assert(sizeof(Bc5NpcCalloutCtx) == 0x28 && offsetof(Bc5NpcCalloutCtx, active) == 0x18 &&
              offsetof(Bc5NpcCalloutCtx, head) == 0x20);

static KYTY_SYSV_ABI void* Bc5NpcCalloutWorker(void* arg) {
»auto* ctx = static_cast<Bc5NpcCalloutCtx*>(arg);
»LibKernel::PthreadMutexLock(&ctx->mutex);
»for (;;) {
»»int64_t now = 0;
»»Bc5NpcGetSystemClockUsec(&now);
»»Bc5NpcCallout* e         = ctx->head;
»»uint32_t       wait_usec = 0;
»»if (e == nullptr) {
»»»if (ctx->stop_requested > 0) {
»»»»break;
»»»}
»»} else {
»»»const auto deadline = static_cast<uint64_t>(e->deadline_usec);
»»»const auto t        = static_cast<uint64_t>(now);
»»»if (deadline <= t) {
»»»»ctx->head = e->next;
»»»»LibKernel::PthreadMutexUnlock(&ctx->mutex);
»»»»if (e->handler != nullptr) {
»»»»»e->handler(e->arg);
»»»»}
»»»»LibKernel::PthreadMutexLock(&ctx->mutex);
»»»»continue;
»»»}
»»»if (ctx->stop_requested > 0) {
»»»»break;
»»»}
»»»const uint64_t remaining = deadline - t;
»»»wait_usec                = static_cast<uint32_t>(remaining > 0xffffffffull ? 0xffffffffull : remaining);
»»}
»»Bc5NpcCondTimedwait(&ctx->cond, &ctx->mutex, wait_usec);
»»if (ctx->stop_requested > 0) {
»»»break;
»»}
»}
»LibKernel::PthreadMutexUnlock(&ctx->mutex);
»return nullptr;
}

static int Bc5NpcCalloutInitCtx(Bc5NpcCalloutCtx* ctx, const char* name, uint64_t stack_size, int priority,
»                               uint64_t affinity) {
»if (ctx == nullptr) {
»»return BC5_NPC_INVALID_ARGUMENT;
»}
»if (ctx->active >= 1) {
»»return BC5_NPC_CALLOUT_ALREADY;
»}
»ctx->stop_requested = 0;
»ctx->head           = nullptr;
»int r               = Bc5NpcMutexInit(&ctx->mutex, name, 1);
»if (r < 0) {
»»return r;
»}
»r = Bc5NpcCondInit(&ctx->cond, name);
»if (r >= 0) {
»»r = Bc5NpcCreateThread(&ctx->thread, Bc5NpcCalloutWorker, ctx, priority, stack_size, affinity, name);
»»if (r >= 0) {
»»»ctx->active = 1;
»»»return OK;
»»}
»»LibKernel::PthreadCondDestroy(&ctx->cond);
»}
»LibKernel::PthreadMutexDestroy(&ctx->mutex);
»return r;
}

static int Bc5NpcCalloutStartOnCtx64(Bc5NpcCalloutCtx* ctx, Bc5NpcCallout* callout, int64_t usec,
»                                    Bc5NpcCalloutHandler handler, void* arg) {
»if (ctx == nullptr) {
»»return BC5_NPC_INVALID_ARGUMENT;
»}
»if (ctx->active == 0) {
»»return BC5_NPC_CALLOUT_NOT_INIT;
»}
»int64_t now = 0;
»Bc5NpcGetSystemClockUsec(&now);
»LibKernel::PthreadMutexLock(&ctx->mutex);
»for (const Bc5NpcCallout* c = ctx->head; c != nullptr; c = c->next) {
»»if (c == callout) { // AnyPS5 702d85e0b: a queued callout is left as it is
»»»LibKernel::PthreadMutexUnlock(&ctx->mutex);
»»»return BC5_NPC_CALLOUT_DUPLICATE;
»»}
»}
»callout->next          = nullptr;
»callout->handler       = handler;
»callout->arg           = arg;
»callout->deadline_usec = now + usec;
»Bc5NpcCallout** link   = &ctx->head;
»while (*link != nullptr && (*link)->deadline_usec < callout->deadline_usec) {
»»link = &(*link)->next;
»}
»callout->next = *link;
»*link         = callout;
»LibKernel::PthreadCondSignal(&ctx->cond);
»LibKernel::PthreadMutexUnlock(&ctx->mutex);
»return OK;
}

static int Bc5NpcCalloutStopOnCtx(Bc5NpcCalloutCtx* ctx, Bc5NpcCallout* callout, int32_t* removed) {
»if (ctx == nullptr) {
»»return BC5_NPC_INVALID_ARGUMENT;
»}
»if (ctx->active == 0) {
»»return BC5_NPC_CALLOUT_NOT_INIT;
»}
»LibKernel::PthreadMutexLock(&ctx->mutex);
»int32_t         found = 0;
»Bc5NpcCallout** link  = &ctx->head;
»for (; *link != nullptr; link = &(*link)->next) {
»»if (*link == callout) {
»»»*link = callout->next;
»»»found = 1;
»»»break;
»»}
»}
»if (removed != nullptr) {
»»*removed = found;
»}
»LibKernel::PthreadMutexUnlock(&ctx->mutex);
»return OK;
}

static int Bc5NpcCalloutTermCtx(Bc5NpcCalloutCtx* ctx) {
»if (ctx == nullptr || ctx->active == 0) {
»»return OK;
»}
»if (LibKernel::PthreadSelfOrNull() == ctx->thread) { // AnyPS5 22d478c78: its worker cannot join itself
»»std::fprintf(stderr, "[bc5] exp 0405: npcommon sceNpCalloutTermCtx from the context's own callout: refused, context kept\n");
»»std::fflush(stderr);
»»return OK;
»}
»LibKernel::PthreadMutexLock(&ctx->mutex);
»ctx->stop_requested = 1;
»LibKernel::PthreadCondSignal(&ctx->cond);
»LibKernel::PthreadMutexUnlock(&ctx->mutex);
»LibKernel::PthreadJoin(ctx->thread, nullptr);
»LibKernel::PthreadCondDestroy(&ctx->cond);
»LibKernel::PthreadMutexDestroy(&ctx->mutex);
»ctx->active = 0;
»return OK;
}
// ---- end of BC5 experiment 0405 (tbn) NpCommon block ----
"""

# (stub name, new parameter list, port call)
NPC_STUBS = (
    ("sceNpCmpNpId", "const Bc5NpcNpId* np_id1, const Bc5NpcNpId* np_id2", "Bc5NpcCmpNpId(np_id1, np_id2)"),
    ("sceNpCmpNpIdInOrder", "const Bc5NpcNpId* np_id1, const Bc5NpcNpId* np_id2, int32_t* order",
     "Bc5NpcCmpNpIdInOrder(np_id1, np_id2, order)"),
    ("sceNpCmpOnlineId", "const Bc5NpcOnlineId* online_id1, const Bc5NpcOnlineId* online_id2",
     "Bc5NpcCmpOnlineId(online_id1, online_id2)"),
    ("sceNpCondDestroy", "LibKernel::PthreadCond* cond", "LibKernel::PthreadCondDestroy(cond)"),
    ("sceNpCalloutInitCtx",
     "Bc5NpcCalloutCtx* ctx, const char* name, uint64_t stack_size, int priority, uint64_t affinity",
     "Bc5NpcCalloutInitCtx(ctx, name, stack_size, priority, affinity)"),
    ("sceNpCalloutTermCtx", "Bc5NpcCalloutCtx* ctx", "Bc5NpcCalloutTermCtx(ctx)"),
    ("sceNpLwMutexLock", "LibKernel::PthreadMutex* mutex", "LibKernel::PthreadMutexLock(mutex)"),
    ("sceNpLwMutexInit", "LibKernel::PthreadMutex* mutex, const char* name, uint64_t flags",
     "Bc5NpcMutexInit(mutex, name, flags)"),
    ("sceNpLwMutexDestroy", "LibKernel::PthreadMutex* mutex", "LibKernel::PthreadMutexDestroy(mutex)"),
    ("sceNpLwMutexUnlock", "LibKernel::PthreadMutex* mutex", "LibKernel::PthreadMutexUnlock(mutex)"),
    ("sceNpMutexTryLock", "LibKernel::PthreadMutex* mutex", "Bc5NpcMutexTryLock(mutex)"),
    ("sceNpJoinThread", "LibKernel::Pthread thread, void** value", "LibKernel::PthreadJoin(thread, value)"),
    ("sceNpCalloutStartOnCtx",
     "Bc5NpcCalloutCtx* ctx, Bc5NpcCallout* callout, uint32_t usec, Bc5NpcCalloutHandler handler, void* arg",
     "Bc5NpcCalloutStartOnCtx64(ctx, callout, static_cast<int64_t>(usec), handler, arg)"),
    ("sceNpCreateThread",
     "LibKernel::Pthread* thread, LibKernel::pthread_entry_func_t entry, void* arg, int priority, uint64_t stack_size, "
     "uint64_t affinity, const char* name",
     "Bc5NpcCreateThread(thread, entry, arg, priority, stack_size, affinity, name)"),
    ("sceNpIntIsValidOnlineId", "const Bc5NpcOnlineId* online_id", "Bc5NpcIntIsValidOnlineId(online_id)"),
    ("sceNpLwMutexTryLock", "LibKernel::PthreadMutex* mutex", "Bc5NpcMutexTryLock(mutex)"),
    ("sceNpCalloutStopOnCtx", "Bc5NpcCalloutCtx* ctx, Bc5NpcCallout* callout, int32_t* removed",
     "Bc5NpcCalloutStopOnCtx(ctx, callout, removed)"),
    ("sceNpMutexDestroy", "LibKernel::PthreadMutex* mutex", "LibKernel::PthreadMutexDestroy(mutex)"),
    ("sceNpCalloutStartOnCtx64",
     "Bc5NpcCalloutCtx* ctx, Bc5NpcCallout* callout, int64_t usec, Bc5NpcCalloutHandler handler, void* arg",
     "Bc5NpcCalloutStartOnCtx64(ctx, callout, usec, handler, arg)"),
    ("sceNpMutexUnlock", "LibKernel::PthreadMutex* mutex", "LibKernel::PthreadMutexUnlock(mutex)"),
    ("sceNpGetSystemClockUsec", "int64_t* usec", "Bc5NpcGetSystemClockUsec(usec)"),
    ("sceNpCondInit", "LibKernel::PthreadCond* cond, const char* name, uint64_t flags",
     "(static_cast<void>(flags), Bc5NpcCondInit(cond, name))"),
    ("sceNpMutexLock", "LibKernel::PthreadMutex* mutex", "LibKernel::PthreadMutexLock(mutex)"),
    ("sceNpGetPlatformType", "const Bc5NpcNpId* np_id", "Bc5NpcGetPlatformType(np_id)"),
    ("sceNpCondTimedwait", "LibKernel::PthreadCond* cond, LibKernel::PthreadMutex* mutex, uint32_t usec",
     "Bc5NpcCondTimedwait(cond, mutex, usec)"),
    ("sceNpMutexInit", "LibKernel::PthreadMutex* mutex, const char* name, uint64_t flags",
     "Bc5NpcMutexInit(mutex, name, flags)"),
    ("sceNpCondSignal", "LibKernel::PthreadCond* cond", "LibKernel::PthreadCondSignal(cond)"),
    ("sceNpGetSdkVersion", "char* version", "Bc5NpcGetSdkVersion(version)"),
)

# =====================================================================================================================
# NpManager
# =====================================================================================================================
NPM_ANCHOR = 'LIB_VERSION("libSceNpManager", 1, "libSceNpManager", 1, 1);\n'
NPM_BLOCK = r"""
// ---- BC5 experiment 0405 (series e6 of experiment 0401), tag tbn: KYTY_BC5_LOAD_NPMANAGER, the NpManager table's port ----
// Exp 0405 decision 4: this table is loaded behind KYTY_BC5_LOAD_NPMANAGER (libs.cpp), before the live NpManager table of
// libNet.cpp (InitNet_1_NpManager). The two NIDs that both register, mjjTXh+NHWY (sceNpUnregisterStateCallback) and
// cRILAEvn+9M (sceNpUnregisterNpReachabilityStateCallback), are not registered here when the switch is on: the loader's
// exact-key lookup (Find) would reach the live function, but its NID-only fallback (FindByNid) returns the first record,
// which would be this table's stub (exp 0405 e6, tld0405-notes.md risk 1). Off, InitNpManager_1 registers them as today.
// sceNpUnregisterPlusEventCallback (xViqJdDgKl0) stays here and answers 0, as AnyPS5 :1056 does; its live counterpart
// sceNpRegisterPlusEventCallback (GImICnh+boA, network.cpp) keeps no callback either, so the pair shares no state (risk 2).
// Unset, empty or "0" is off: every stub takes today's path. On, 20 exports answer as
// AnyPS5 (github.com/boykopovar/AnyPS5, GPL-2.0-only) @ 4f41f4c375f5abb487dbd184fbc150f31994d762,
// core/libs/prx/libSceNpManager/Export.cpp:302-327 (CheckNpAvailabilityA, GetAccountDateOfBirthA, GetAccountLanguageA,
// GetGamePresenceStatus/A, GetParentalControlInfoA), 412-416 (IsPlusMember), 809-864 (the PS4 forms GetAccountCountry,
// GetAccountDateOfBirth, GetAccountLanguage, GetParentalControlInfo, GetUserIdByOnlineId, CheckPlus, GetAccountId,
// SetGamePresenceOnline, and SetGamePresenceOnlineA, commit 72ccb10bd), 921-927 (WaitAsync), 993-1007 (SetTimeout),
// 1060-1063 (GetUserIdByAccountId), 1085-1087 (CheckCallbackForLib): no PSN account is signed in. Its debt note
// docs/dev/debt/libSceNpManager.md:167,174-175,183-189,195,197 names shadPS4 as the source of the signatures and checks and
// says none is measured on a console. Offline only: no network. Adapted to our host's NpManager (libs/network.cpp, the live
// table): a request id is one of its requests (NpCreateRequest); the A forms that AnyPS5 answers with its SignedOutRequest
// complete that request signed out through network.cpp's own path (NpCheckNpReachability: 0x80550006 for a synchronous
// request, 0 and a polled 0x80550006 for an asynchronous one; a request id <= 0 is 0x80550003, an unknown one 0x80550014),
// so a title sees one request model. Whether a request is live (SetTimeout, WaitAsync, SetGamePresenceOnline) is asked of
// network.cpp's NpPollAsync, which changes nothing. The signed-out error is 0x80550006, as network.cpp and AnyPS5 answer
// (this file's NP_NOT_SIGNED_IN, 0x80550005, stays for the off path; TODO(verify) above). sceNpCheckCallbackForLib runs
// network.cpp's sceNpCheckCallback. Not changed: sceNpUnregisterPlusEventCallback (already 0, as AnyPS5 :1056), and the four
// AnyPS5 keeps as throwing placeholders (RegisterGamePresenceCallbackA, UnregisterGamePresenceCallbackA,
// RegisterStateCallbackForToolkit, UnregisterStateCallbackForToolkit). AnyPS5's copyrights remain with its authors.
static bool Bc5NpmOn() {
»static const bool on = [] {
»»const char* e = std::getenv("KYTY_BC5_LOAD_NPMANAGER");
»»const bool  v = e != nullptr && e[0] != '\0' && std::strcmp(e, "0") != 0;
»»std::fprintf(stderr, "%s\n",
»»             v ? "[bc5] exp 0405: npmanager port on (items: account presence plus request timeout wait callback)"
»»               : "[bc5] exp 0405: npmanager port off");
»»std::fflush(stderr);
»»return v;
»}();
»return on;
}

constexpr int BC5_NPM_INVALID_ARGUMENT  = static_cast<int>(0x80550003u);
constexpr int BC5_NPM_SIGNED_OUT        = static_cast<int>(0x80550006u);
constexpr int BC5_NPM_USER_NOT_FOUND    = static_cast<int>(0x80550007u);
constexpr int BC5_NPM_REQUEST_NOT_FOUND = static_cast<int>(0x80550014u);
constexpr int BC5_NPM_USER_ID_INVALID   = -1;

// network.cpp's request answered signed out (AnyPS5's SignedOutRequest, on our request model).
static int Bc5NpmSignedOutRequest(int req_id, int user_id) {
»return Libs::Network::NpManager::NpCheckNpReachability(req_id, user_id);
}

// True when req_id is one of network.cpp's live requests; NpPollAsync changes nothing.
static bool Bc5NpmRequestLive(int req_id) {
»int result = 0;
»return Libs::Network::NpManager::NpPollAsync(req_id, &result) != BC5_NPM_REQUEST_NOT_FOUND;
}

static int Bc5NpmCheckNpAvailabilityA(int req_id, int user_id) {
»if (user_id == BC5_NPM_USER_ID_INVALID) {
»»return BC5_NPM_INVALID_ARGUMENT;
»}
»return Bc5NpmSignedOutRequest(req_id, user_id);
}

static int Bc5NpmCheckPlus(int req_id, const void* param, void* result) {
»if (req_id == 0 || param == nullptr || result == nullptr) {
»»return BC5_NPM_INVALID_ARGUMENT;
»}
»return BC5_NPM_SIGNED_OUT;
}

// The PS4 forms that take an online id: no account is known (USER_NOT_FOUND), nothing is written.
static int Bc5NpmUnknownOnlineId(const void* online_id, const void* out1, const void* out2) {
»if (online_id == nullptr || out1 == nullptr || out2 == nullptr) {
»»return BC5_NPM_INVALID_ARGUMENT;
»}
»return BC5_NPM_USER_NOT_FOUND;
}

// The A forms with a user id and outputs: refused for a null output or the invalid user, else the request signed out.
static int Bc5NpmUserRequest(int req_id, int user_id, const void* out1, const void* out2) {
»if (out1 == nullptr || out2 == nullptr || user_id == BC5_NPM_USER_ID_INVALID) {
»»return BC5_NPM_INVALID_ARGUMENT;
»}
»return Bc5NpmSignedOutRequest(req_id, user_id);
}

static int Bc5NpmSetTimeout(int req_id, int32_t resolve_retry, uint32_t resolve_timeout, uint32_t conn_timeout,
»                           uint32_t send_timeout, uint32_t recv_timeout) {
»auto below = [](uint32_t timeout, uint32_t minimum) { return timeout != 0 && timeout < minimum; };
»if (req_id <= 0 || resolve_retry < 0) {
»»return BC5_NPM_INVALID_ARGUMENT;
»}
»if (resolve_retry == 0 && resolve_timeout == 0 && conn_timeout == 0 && send_timeout == 0 && recv_timeout == 0) {
»»return BC5_NPM_INVALID_ARGUMENT;
»}
»if (below(resolve_timeout, 1000000u) || below(conn_timeout, 10000000u) || below(send_timeout, 10000000u) ||
»    below(recv_timeout, 10000000u)) {
»»return BC5_NPM_INVALID_ARGUMENT;
»}
»return Bc5NpmRequestLive(req_id) ? OK : BC5_NPM_REQUEST_NOT_FOUND;
}

static int Bc5NpmWaitAsync(int req_id, int* result) {
»if (result == nullptr) {
»»return BC5_NPM_INVALID_ARGUMENT;
»}
»if (!Bc5NpmRequestLive(req_id)) {
»»return BC5_NPM_REQUEST_NOT_FOUND;
»}
»*result = BC5_NPM_SIGNED_OUT;
»return OK;
}

static int Bc5NpmGetAccountDateOfBirthA(int user_id, void* date_of_birth) {
»if (date_of_birth == nullptr || user_id == BC5_NPM_USER_ID_INVALID) {
»»return BC5_NPM_INVALID_ARGUMENT;
»}
»return BC5_NPM_SIGNED_OUT;
}

static int Bc5NpmGetGamePresenceStatus(const void* who, bool is_user, int user_id, uint32_t* status) {
»if (status == nullptr || (!is_user && who == nullptr) || (is_user && user_id == BC5_NPM_USER_ID_INVALID)) {
»»return BC5_NPM_INVALID_ARGUMENT;
»}
»*status = 0; // offline
»return OK;
}

static int Bc5NpmSetGamePresenceOnline(int req_id, const void* online_id) {
»if (req_id == 0 || online_id == nullptr) {
»»return BC5_NPM_INVALID_ARGUMENT;
»}
»return Bc5NpmRequestLive(req_id) ? BC5_NPM_SIGNED_OUT : BC5_NPM_REQUEST_NOT_FOUND;
}

static int Bc5NpmIsPlusMember(bool* is_member) {
»if (is_member == nullptr) {
»»return BC5_NPM_INVALID_ARGUMENT;
»}
»*is_member = false;
»return OK;
}

// GetAccountId, GetUserIdByOnlineId (online id, output) and GetUserIdByAccountId (account id 0 refused): signed out.
static int Bc5NpmSignedOutLookup(bool key_ok, const void* out) {
»if (!key_ok || out == nullptr) {
»»return BC5_NPM_INVALID_ARGUMENT;
»}
»return BC5_NPM_SIGNED_OUT;
}
// ---- end of BC5 experiment 0405 (tbn) NpManager block ----
"""

NPM_STUBS = (
    ("sceNpCheckNpAvailabilityA", "int req_id, int user_id", "Bc5NpmCheckNpAvailabilityA(req_id, user_id)"),
    ("sceNpCheckPlus", "int req_id, const void* param, void* result", "Bc5NpmCheckPlus(req_id, param, result)"),
    ("sceNpGetAccountLanguage", "int req_id, const void* online_id, void* language",
     "(static_cast<void>(req_id), Bc5NpmUnknownOnlineId(online_id, language, language))"),
    ("sceNpGetAccountLanguageA", "int req_id, int user_id, void* language",
     "Bc5NpmUserRequest(req_id, user_id, language, language)"),
    ("sceNpGetParentalControlInfo", "int req_id, const void* online_id, int8_t* age, void* info",
     "(static_cast<void>(req_id), Bc5NpmUnknownOnlineId(online_id, age, info))"),
    ("sceNpGetParentalControlInfoA", "int req_id, int user_id, int8_t* age, void* info",
     "Bc5NpmUserRequest(req_id, user_id, age, info)"),
    ("sceNpSetTimeout",
     "int req_id, int32_t resolve_retry, uint32_t resolve_timeout, uint32_t conn_timeout, uint32_t send_timeout, "
     "uint32_t recv_timeout",
     "Bc5NpmSetTimeout(req_id, resolve_retry, resolve_timeout, conn_timeout, send_timeout, recv_timeout)"),
    ("sceNpWaitAsync", "int req_id, int* result", "Bc5NpmWaitAsync(req_id, result)"),
    ("sceNpGetAccountCountry", "const void* online_id, void* country_code",
     "Bc5NpmUnknownOnlineId(online_id, country_code, country_code)"),
    ("sceNpGetAccountDateOfBirth", "const void* online_id, void* date_of_birth",
     "Bc5NpmUnknownOnlineId(online_id, date_of_birth, date_of_birth)"),
    ("sceNpGetAccountDateOfBirthA", "int user_id, void* date_of_birth",
     "Bc5NpmGetAccountDateOfBirthA(user_id, date_of_birth)"),
    ("sceNpGetGamePresenceStatus", "const void* online_id, uint32_t* status",
     "Bc5NpmGetGamePresenceStatus(online_id, false, 0, status)"),
    ("sceNpGetGamePresenceStatusA", "int user_id, uint32_t* status",
     "Bc5NpmGetGamePresenceStatus(nullptr, true, user_id, status)"),
    ("sceNpSetGamePresenceOnline", "int req_id, const void* online_id, uint32_t presence",
     "(static_cast<void>(presence), Bc5NpmSetGamePresenceOnline(req_id, online_id))"),
    ("sceNpSetGamePresenceOnlineA", "int req_id, int user_id, uint32_t presence",
     "(static_cast<void>(presence), Bc5NpmCheckNpAvailabilityA(req_id, user_id))"),
    ("sceNpIsPlusMember", "int user_id, bool* is_member", "(static_cast<void>(user_id), Bc5NpmIsPlusMember(is_member))"),
    ("sceNpGetAccountId", "const void* online_id, uint64_t* account_id",
     "Bc5NpmSignedOutLookup(online_id != nullptr, account_id)"),
    ("sceNpGetUserIdByAccountId", "uint64_t account_id, int* user_id",
     "Bc5NpmSignedOutLookup(account_id != 0, user_id)"),
    ("sceNpGetUserIdByOnlineId", "const void* online_id, int* user_id",
     "Bc5NpmSignedOutLookup(online_id != nullptr, user_id)"),
    ("sceNpCheckCallbackForLib", "", "Libs::Network::NpManager::NpCheckCallback()"),
)

# =====================================================================================================================
# NpTrophy
# =====================================================================================================================
NPT_ANCHOR = 'LIB_VERSION("libSceNpTrophy", 1, "libSceNpTrophy", 1, 1);\n'
NPT_BLOCK = r"""
// ---- BC5 experiment 0405 (series e6 of experiment 0401), tag tbn: KYTY_BC5_LOAD_NPTROPHY, the NpTrophy table's port ----
// Exp 0405 decision 4: this table is loaded behind KYTY_BC5_LOAD_NPTROPHY (libs.cpp). Unset, empty or "0" is off: every stub
// takes today's path. On, 23 of the 24 exports AnyPS5 implements answer as AnyPS5 (github.com/boykopovar/AnyPS5,
// GPL-2.0-only) @ 4f41f4c375f5abb487dbd184fbc150f31994d762, core/libs/prx/libSceNpTrophy/Export.cpp:
//  - 59-182 (contexts, handles, the trophy package reader, lookups, icons), 190-381 (CreateContext, DestroyContext,
//    CreateHandle, DestroyHandle, AbortHandle, RegisterContext, GetTrophyUnlockState, UnlockTrophy, GetGameIcon,
//    GetGroupIcon, GetTrophyIcon, GetGameInfo, GetGroupInfo, GetTrophyInfo); include/Api.hpp:5-74 and shadPS4
//    (GPL-2.0-or-later) @ 60c42b9 src/core/libraries/np/np_trophy.h:36-121 for the structure sizes and fields written.
//    Debt note docs/dev/debt/libSceNpTrophy.md:9 ("None of it is checked on a console": the trophy count is the number of
//    TROPnnn.PNG icons in /app0/sce_sys/trophy/trophyNN.trp, as TROPCONF.ESFM is encrypted; no platinum, platinumId -1; a
//    locked trophy's icon is TROPHY_NOT_UNLOCKED), :10 (AbortHandle: measured on a PS4 Pro, firmware 10.71: an aborted
//    handle answers 0x80551607 before the other checks), :32-34 (the game, group and trophy details).
//    Changed: unlocks are kept in memory only, per context, for the run (AnyPS5 writes _trophy/trophyNN.<user> in its
//    working directory; our tree has no trophy store, and the title's save data is never touched). AnyPS5 throws where a
//    group's trophies would be needed (GetGroupInfo of an existing group, GetTrophyInfo in a package with groups); here those
//    keep today's answer (0, nothing written) and print one stderr line each.
//  - 494-511 (NumInfoGetTotal, GroupArrayGetNum, SetInfoGetTrophyNum, SetInfoGetTrophyFlagArray), commits 34b21b0b3 and
//    85ff6817f; debt :28: firmware 13.42 "disassembly, the first four also run natively" (PR 12957): firmware runs,
//    accepted by decision 1 of 2026-11-04. A null argument answers 0 here (host safety; the module faults).
//    Held: ConfigHasGroupFeature (the fifth of that note, from the disassembly only; today's 0 kept).
//  - 573, 602, 606, 730, 734 (SystemDbgCtl, SystemGetDbgParam, SystemGetDbgParamInt, SystemSetDbgParam,
//    SystemSetDbgParamInt: 0x80551692 and nothing else); debt :5: firmware 13.42's module "run in an emulator" (PR 9874),
//    accepted by decision 1.
// Not changed: the other 64 exports of the table (AnyPS5 has no behaviour for them: placeholders that throw, or no export).
// AnyPS5's and shadPS4's copyrights remain with their authors.
static bool Bc5NptOn() {
»static const bool on = [] {
»»const char* e = std::getenv("KYTY_BC5_LOAD_NPTROPHY");
»»const bool  v = e != nullptr && e[0] != '\0' && std::strcmp(e, "0") != 0;
»»std::fprintf(stderr, "%s\n",
»»             v ? "[bc5] exp 0405: nptrophy port on (items: context handle register unlock info icon setinfo dbg)"
»»               : "[bc5] exp 0405: nptrophy port off");
»»std::fflush(stderr);
»»return v;
»}();
»return on;
}

constexpr int      BC5_NPT_INVALID_ARGUMENT    = static_cast<int>(0x80551604u);
constexpr int      BC5_NPT_INSUFFICIENT_BUFFER = static_cast<int>(0x80551605u);
constexpr int      BC5_NPT_ABORT               = static_cast<int>(0x80551607u);
constexpr int      BC5_NPT_INVALID_HANDLE      = static_cast<int>(0x80551608u);
constexpr int      BC5_NPT_INVALID_CONTEXT     = static_cast<int>(0x80551609u);
constexpr int      BC5_NPT_INVALID_TROPHY_ID   = static_cast<int>(0x8055160Au);
constexpr int      BC5_NPT_INVALID_GROUP_ID    = static_cast<int>(0x8055160Bu);
constexpr int      BC5_NPT_ALREADY_UNLOCKED    = static_cast<int>(0x8055160Cu);
constexpr int      BC5_NPT_NOT_REGISTERED      = static_cast<int>(0x8055160Fu);
constexpr int      BC5_NPT_ALREADY_REGISTERED  = static_cast<int>(0x80551610u);
constexpr int      BC5_NPT_CONTEXT_EXISTS      = static_cast<int>(0x80551613u);
constexpr int      BC5_NPT_ICON_NOT_FOUND      = static_cast<int>(0x80551614u);
constexpr int      BC5_NPT_INVALID_TRP         = static_cast<int>(0x80551616u);
constexpr int      BC5_NPT_NOT_UNLOCKED        = static_cast<int>(0x8055161Au);
constexpr int      BC5_NPT_CONF_NOT_INSTALLED  = static_cast<int>(0x80551626u);
constexpr int      BC5_NPT_DBG_ANSWER          = static_cast<int>(0x80551692u);
constexpr int      BC5_NPT_INVALID_ID          = -1;
constexpr int      BC5_NPT_NUM_MAX             = 128;
constexpr uint32_t BC5_NPT_TRP_MAGIC           = 0xdca24d00u;
constexpr size_t   BC5_NPT_TRP_HEADER          = 0x60;
constexpr size_t   BC5_NPT_TRP_ENTRY           = 0x40;

struct Bc5NptEntry {
»uint64_t offset;
»uint64_t size;
};
using Bc5NptEntries = std::map<std::string, Bc5NptEntry>;

struct Bc5NptContext {
»int                   user_id       = 0;
»uint32_t              service_label = 0;
»bool                  registered    = false;
»std::filesystem::path package;
»Bc5NptEntries         entries;
»int                   trophies = 0;
»std::set<int>         unlocked; // this run only
};

struct Bc5NptState {
»std::mutex                   mutex;
»std::map<int, Bc5NptContext> contexts;
»std::set<int>                handles;
»std::set<int>                aborted;
»int                          next_context = 1;
»int                          next_handle  = 1;
};

static Bc5NptState& Bc5Npt() {
»static auto* s = new Bc5NptState; // never destroyed: guest threads may call late
»return *s;
}

static uint32_t Bc5NptBe32(const uint8_t* b) {
»return (static_cast<uint32_t>(b[0]) << 24u) | (static_cast<uint32_t>(b[1]) << 16u) | (static_cast<uint32_t>(b[2]) << 8u) |
»       static_cast<uint32_t>(b[3]);
}

static uint64_t Bc5NptBe64(const uint8_t* b) {
»return (static_cast<uint64_t>(Bc5NptBe32(b)) << 32u) | Bc5NptBe32(b + 4);
}

// nullopt: the package cannot be opened; an empty map: not a trophy package (or a broken one).
static std::optional<Bc5NptEntries> Bc5NptReadPackage(const std::filesystem::path& path) {
»std::ifstream file(path, std::ios::binary | std::ios::ate);
»if (!file) {
»»return std::nullopt;
»}
»const auto    end = file.tellg();
»Bc5NptEntries none;
»if (end < static_cast<std::streamoff>(BC5_NPT_TRP_HEADER)) {
»»return none;
»}
»const auto file_size = static_cast<uint64_t>(end);
»file.seekg(0);
»uint8_t header[BC5_NPT_TRP_HEADER] = {};
»if (!file.read(reinterpret_cast<char*>(header), sizeof(header)) || Bc5NptBe32(header) != BC5_NPT_TRP_MAGIC) {
»»return none;
»}
»const uint32_t count = Bc5NptBe32(header + 0x10);
»if (Bc5NptBe32(header + 0x14) != BC5_NPT_TRP_ENTRY || count > (file_size - BC5_NPT_TRP_HEADER) / BC5_NPT_TRP_ENTRY) {
»»return none;
»}
»Bc5NptEntries entries;
»for (uint32_t i = 0; i < count; i++) {
»»uint8_t e[BC5_NPT_TRP_ENTRY] = {};
»»if (!file.read(reinterpret_cast<char*>(e), sizeof(e))) {
»»»return none;
»»}
»»size_t n = 0;
»»while (n < 32 && e[n] != 0) {
»»»n++;
»»}
»»const Bc5NptEntry contents {Bc5NptBe64(e + 32), Bc5NptBe64(e + 40)};
»»if (contents.offset > file_size || contents.size > file_size - contents.offset) {
»»»return none;
»»}
»»entries[std::string(reinterpret_cast<const char*>(e), n)] = contents;
»}
»return entries;
}

// Called with the state's mutex held.
static int Bc5NptLookup(int context_id, int handle, Bc5NptContext** context) {
»auto& s = Bc5Npt();
»if (context_id == BC5_NPT_INVALID_ID) {
»»return BC5_NPT_INVALID_CONTEXT;
»}
»if (handle == BC5_NPT_INVALID_ID) {
»»return BC5_NPT_INVALID_HANDLE;
»}
»const auto found = s.contexts.find(context_id);
»if (found == s.contexts.end()) {
»»return BC5_NPT_INVALID_CONTEXT;
»}
»if (s.handles.count(handle) == 0) {
»»return BC5_NPT_INVALID_HANDLE;
»}
»if (s.aborted.count(handle) != 0) {
»»return BC5_NPT_ABORT;
»}
»*context = &found->second;
»return OK;
}

// Lookup, then the registered check.
static int Bc5NptRegistered(int context_id, int handle, Bc5NptContext** context) {
»const int r = Bc5NptLookup(context_id, handle, context);
»if (r != OK) {
»»return r;
»}
»return (*context)->registered ? OK : BC5_NPT_NOT_REGISTERED;
}

static int Bc5NptCount(const Bc5NptContext& c, const char* format) { // consecutive TROPnnn.PNG / GRnnn.PNG icons
»int n = 0;
»for (int id = 0; id < BC5_NPT_NUM_MAX; id++) {
»»char icon[16];
»»std::snprintf(icon, sizeof(icon), format, id);
»»if (c.entries.count(icon) == 0) {
»»»break;
»»}
»»n = id + 1;
»}
»return n;
}

static uint32_t Bc5NptProgress(const Bc5NptContext& c) {
»return c.trophies == 0 ? 0u : static_cast<uint32_t>(c.unlocked.size() * 100u / static_cast<size_t>(c.trophies));
}

static int Bc5NptCopyIcon(const Bc5NptContext& c, const std::string& name, void* buffer, uint64_t* size) {
»const auto entry = c.entries.find(name);
»if (entry == c.entries.end()) {
»»return BC5_NPT_ICON_NOT_FOUND;
»}
»if (buffer == nullptr) {
»»*size = entry->second.size;
»»return OK;
»}
»if (*size < entry->second.size) {
»»return BC5_NPT_INSUFFICIENT_BUFFER;
»}
»std::ifstream file(c.package, std::ios::binary);
»file.seekg(static_cast<std::streamoff>(entry->second.offset));
»if (!file.read(static_cast<char*>(buffer), static_cast<std::streamsize>(entry->second.size))) {
»»return BC5_NPT_INVALID_TRP;
»}
»*size = entry->second.size;
»return OK;
}

static uint64_t Bc5NptSizeField(const void* p) {
»uint64_t v = 0;
»std::memcpy(&v, p, sizeof(v));
»return v;
}

// Clears a details or data structure after its size field and writes 32-bit fields at their offsets.
static void Bc5NptClear(void* p, size_t size) {
»std::memset(static_cast<uint8_t*>(p) + 8, 0, size - 8);
}
static void Bc5NptPut32(void* p, size_t offset, uint32_t v) {
»std::memcpy(static_cast<uint8_t*>(p) + offset, &v, sizeof(v));
}

static void Bc5NptTellOnce(bool* told, const char* what) {
»if (!*told) {
»»*told = true;
»»std::fprintf(stderr, "[bc5] exp 0405: nptrophy %s: AnyPS5 has no answer (the encrypted configuration lists a group's "
»»                     "trophies); today's 0 kept, nothing written\n",
»»             what);
»»std::fflush(stderr);
»}
}

static int Bc5NptCreateContext(int* context, int user_id, uint32_t service_label, uint64_t options) {
»if (context == nullptr || options != 0) {
»»return BC5_NPT_INVALID_ARGUMENT;
»}
»auto&           s = Bc5Npt();
»std::lock_guard lock(s.mutex);
»for (const auto& [id, existing]: s.contexts) {
»»if (existing.user_id == user_id && existing.service_label == service_label) {
»»»return BC5_NPT_CONTEXT_EXISTS;
»»}
»}
»const int id = s.next_context++;
»auto&     c  = s.contexts[id];
»c.user_id       = user_id;
»c.service_label = service_label;
»*context        = id;
»return OK;
}

static int Bc5NptDestroyContext(int context) {
»auto&           s = Bc5Npt();
»std::lock_guard lock(s.mutex);
»return s.contexts.erase(context) == 1 ? OK : BC5_NPT_INVALID_CONTEXT;
}

static int Bc5NptCreateHandle(int* handle) {
»if (handle == nullptr) {
»»return BC5_NPT_INVALID_ARGUMENT;
»}
»auto&           s = Bc5Npt();
»std::lock_guard lock(s.mutex);
»const int       id = s.next_handle++;
»s.handles.insert(id);
»*handle = id;
»return OK;
}

static int Bc5NptDestroyHandle(int handle) {
»auto&           s = Bc5Npt();
»std::lock_guard lock(s.mutex);
»s.aborted.erase(handle);
»return s.handles.erase(handle) == 1 ? OK : BC5_NPT_INVALID_HANDLE;
}

static int Bc5NptAbortHandle(int handle) {
»auto&           s = Bc5Npt();
»std::lock_guard lock(s.mutex);
»if (s.handles.count(handle) == 0) {
»»return BC5_NPT_INVALID_HANDLE;
»}
»s.aborted.insert(handle);
»return OK;
}

static int Bc5NptRegisterContext(int context_id, int handle, uint64_t options) {
»if (options != 0) {
»»return BC5_NPT_INVALID_ARGUMENT;
»}
»auto&           s = Bc5Npt();
»std::lock_guard lock(s.mutex);
»Bc5NptContext*  c = nullptr;
»if (const int r = Bc5NptLookup(context_id, handle, &c); r != OK) {
»»return r;
»}
»if (c->registered) {
»»return BC5_NPT_ALREADY_REGISTERED;
»}
»char name[64];
»std::snprintf(name, sizeof(name), "/app0/sce_sys/trophy/trophy%02u.trp", c->service_label);
»c->package         = LibKernel::FileSystem::GetRealFilename(name);
»const auto entries = Bc5NptReadPackage(c->package);
»if (!entries.has_value()) {
»»return BC5_NPT_CONF_NOT_INSTALLED;
»}
»if (entries->empty()) {
»»return BC5_NPT_INVALID_TRP;
»}
»c->entries    = *entries;
»c->trophies   = Bc5NptCount(*c, "TROP%03d.PNG");
»c->registered = true;
»return OK;
}

static int Bc5NptGetTrophyUnlockState(int context_id, int handle, uint32_t* flags, uint32_t* count) {
»if (flags == nullptr || count == nullptr) {
»»return BC5_NPT_INVALID_ARGUMENT;
»}
»auto&           s = Bc5Npt();
»std::lock_guard lock(s.mutex);
»Bc5NptContext*  c = nullptr;
»if (const int r = Bc5NptRegistered(context_id, handle, &c); r != OK) {
»»return r;
»}
»std::memset(flags, 0, BC5_NPT_NUM_MAX / 8);
»for (const int id: c->unlocked) {
»»flags[id >> 5] |= 1u << static_cast<uint32_t>(id & 31);
»}
»*count = static_cast<uint32_t>(c->trophies);
»return OK;
}

static int Bc5NptUnlockTrophy(int context_id, int handle, int trophy_id, int* platinum_id) {
»if (platinum_id == nullptr) {
»»return BC5_NPT_INVALID_ARGUMENT;
»}
»auto&           s = Bc5Npt();
»std::lock_guard lock(s.mutex);
»Bc5NptContext*  c = nullptr;
»if (const int r = Bc5NptRegistered(context_id, handle, &c); r != OK) {
»»return r;
»}
»if (trophy_id < 0 || trophy_id >= c->trophies) {
»»return BC5_NPT_INVALID_TROPHY_ID;
»}
»if (c->unlocked.count(trophy_id) != 0) {
»»return BC5_NPT_ALREADY_UNLOCKED;
»}
»c->unlocked.insert(trophy_id);
»*platinum_id = BC5_NPT_INVALID_ID;
»return OK;
}

// kind 0: the game icon, 1: a group's (id), 2: a trophy's (id).
static int Bc5NptGetIcon(int context_id, int handle, int kind, int id, void* buffer, uint64_t* size) {
»if (size == nullptr) {
»»return BC5_NPT_INVALID_ARGUMENT;
»}
»auto&           s = Bc5Npt();
»std::lock_guard lock(s.mutex);
»Bc5NptContext*  c = nullptr;
»if (const int r = Bc5NptRegistered(context_id, handle, &c); r != OK) {
»»return r;
»}
»char icon[16];
»if (kind == 0) {
»»std::snprintf(icon, sizeof(icon), "ICON0.PNG");
»} else if (kind == 1) {
»»if (id < 0) {
»»»return BC5_NPT_INVALID_GROUP_ID;
»»}
»»std::snprintf(icon, sizeof(icon), "GR%03d.PNG", id);
»} else {
»»if (id < 0 || id >= c->trophies) {
»»»return BC5_NPT_INVALID_TROPHY_ID;
»»}
»»if (c->unlocked.count(id) == 0) {
»»»return BC5_NPT_NOT_UNLOCKED;
»»}
»»std::snprintf(icon, sizeof(icon), "TROP%03d.PNG", id);
»}
»return Bc5NptCopyIcon(*c, icon, buffer, size);
}

// kind 0: the game (details 0x4a0, data 0x20), 1: a group (0x4a0, 0x28), 2: a trophy (0x498, 0x18).
static int Bc5NptGetInfo(int context_id, int handle, int kind, int id, void* details, void* data) {
»static const size_t details_size[3] = {0x4a0, 0x4a0, 0x498};
»static const size_t data_size[3]    = {0x20, 0x28, 0x18};
»static bool         told_group      = false;
»static bool         told_trophy     = false;
»if (details == nullptr && data == nullptr) {
»»return BC5_NPT_INVALID_ARGUMENT;
»}
»if ((details != nullptr && Bc5NptSizeField(details) != details_size[kind]) ||
»    (data != nullptr && Bc5NptSizeField(data) != data_size[kind])) {
»»return BC5_NPT_INVALID_ARGUMENT;
»}
»auto&           s = Bc5Npt();
»std::lock_guard lock(s.mutex);
»Bc5NptContext*  c = nullptr;
»if (const int r = Bc5NptRegistered(context_id, handle, &c); r != OK) {
»»return r;
»}
»const int      groups   = Bc5NptCount(*c, "GR%03d.PNG");
»const auto     unlocked = static_cast<uint32_t>(c->unlocked.size());
»const uint32_t progress = Bc5NptProgress(*c);
»if (kind == 1 && id != -1) { // only the base game group (-1) is answered
»»if (id < 0 || id >= groups) {
»»»return BC5_NPT_INVALID_GROUP_ID;
»»}
»»Bc5NptTellOnce(&told_group, "sceNpTrophyGetGroupInfo of a group");
»»return OK;
»}
»if (kind == 2) {
»»if (id < 0 || id >= c->trophies) {
»»»return BC5_NPT_INVALID_TROPHY_ID;
»»}
»»if (groups != 0) {
»»»Bc5NptTellOnce(&told_trophy, "sceNpTrophyGetTrophyInfo in a package with groups");
»»»return OK;
»»}
»}
»if (details != nullptr) {
»»Bc5NptClear(details, details_size[kind]);
»»if (kind == 0) {
»»»Bc5NptPut32(details, 0x08, static_cast<uint32_t>(groups));      // numGroups
»»»Bc5NptPut32(details, 0x0C, static_cast<uint32_t>(c->trophies)); // numTrophies
»»} else if (kind == 1) {
»»»Bc5NptPut32(details, 0x08, static_cast<uint32_t>(id));          // groupId (-1)
»»»Bc5NptPut32(details, 0x0C, static_cast<uint32_t>(c->trophies)); // numTrophies
»»} else {
»»»Bc5NptPut32(details, 0x08, static_cast<uint32_t>(id)); // trophyId
»»»Bc5NptPut32(details, 0x0C, 0);                        // trophyGrade: unknown
»»»Bc5NptPut32(details, 0x10, static_cast<uint32_t>(-1)); // groupId: the base game
»»}
»}
»if (data != nullptr) {
»»Bc5NptClear(data, data_size[kind]);
»»if (kind == 0) {
»»»Bc5NptPut32(data, 0x08, unlocked); // unlockedTrophies
»»»Bc5NptPut32(data, 0x1C, progress); // progressPercentage
»»} else if (kind == 1) {
»»»Bc5NptPut32(data, 0x08, static_cast<uint32_t>(id)); // groupId (-1)
»»»Bc5NptPut32(data, 0x0C, unlocked);                  // unlockedTrophies
»»»Bc5NptPut32(data, 0x20, progress);                  // progressPercentage
»»} else {
»»»Bc5NptPut32(data, 0x08, static_cast<uint32_t>(id));                         // trophyId
»»»static_cast<uint8_t*>(data)[0x0C] = c->unlocked.count(id) != 0 ? 1u : 0u; // unlocked
»»}
»}
»return OK;
}

static int Bc5NptNumInfoGetTotal(const uint32_t* num_info) {
»return num_info == nullptr ? 0 : static_cast<int>(num_info[0] + num_info[1] + num_info[2] + num_info[3]);
}

static int Bc5NptGroupArrayGetNum(const uint32_t* group_array) {
»return group_array == nullptr ? 0 : std::popcount(group_array[0]);
}

static int Bc5NptSetInfoGetTrophyNum(const uint8_t* set_info) {
»int count = 0;
»for (size_t i = 0; set_info != nullptr && i < 64; i++) {
»»count += std::popcount(set_info[i]);
»}
»return count;
}

static int Bc5NptSetInfoGetTrophyFlagArray(const uint8_t* set_info, uint8_t* flag_array) {
»if (set_info == nullptr || flag_array == nullptr) {
»»return 0;
»}
»int count = 0;
»for (size_t i = 0; i < 16; i++) {
»»flag_array[i] = static_cast<uint8_t>(set_info[i] | set_info[16 + i] | set_info[32 + i] | set_info[48 + i]);
»»count += std::popcount(flag_array[i]);
»}
»return count;
}
// ---- end of BC5 experiment 0405 (tbn) NpTrophy block ----
"""

NPT_STUBS = (
    ("sceNpTrophyAbortHandle", "int handle", "Bc5NptAbortHandle(handle)"),
    ("sceNpTrophyCreateContext", "int* context, int user_id, uint32_t service_label, uint64_t options",
     "Bc5NptCreateContext(context, user_id, service_label, options)"),
    ("sceNpTrophyCreateHandle", "int* handle", "Bc5NptCreateHandle(handle)"),
    ("sceNpTrophyDestroyContext", "int context", "Bc5NptDestroyContext(context)"),
    ("sceNpTrophyDestroyHandle", "int handle", "Bc5NptDestroyHandle(handle)"),
    ("sceNpTrophyGetGameIcon", "int context, int handle, void* buffer, uint64_t* size",
     "Bc5NptGetIcon(context, handle, 0, 0, buffer, size)"),
    ("sceNpTrophyGetGameInfo", "int context, int handle, void* details, void* data",
     "Bc5NptGetInfo(context, handle, 0, 0, details, data)"),
    ("sceNpTrophyGetGroupIcon", "int context, int handle, int group_id, void* buffer, uint64_t* size",
     "Bc5NptGetIcon(context, handle, 1, group_id, buffer, size)"),
    ("sceNpTrophyGetGroupInfo", "int context, int handle, int group_id, void* details, void* data",
     "Bc5NptGetInfo(context, handle, 1, group_id, details, data)"),
    ("sceNpTrophyGetTrophyIcon", "int context, int handle, int trophy_id, void* buffer, uint64_t* size",
     "Bc5NptGetIcon(context, handle, 2, trophy_id, buffer, size)"),
    ("sceNpTrophyGetTrophyInfo", "int context, int handle, int trophy_id, void* details, void* data",
     "Bc5NptGetInfo(context, handle, 2, trophy_id, details, data)"),
    ("sceNpTrophyGetTrophyUnlockState", "int context, int handle, uint32_t* flags, uint32_t* count",
     "Bc5NptGetTrophyUnlockState(context, handle, flags, count)"),
    ("sceNpTrophyGroupArrayGetNum", "const uint32_t* group_array", "Bc5NptGroupArrayGetNum(group_array)"),
    ("sceNpTrophyNumInfoGetTotal", "const uint32_t* num_info", "Bc5NptNumInfoGetTotal(num_info)"),
    ("sceNpTrophyRegisterContext", "int context, int handle, uint64_t options",
     "Bc5NptRegisterContext(context, handle, options)"),
    ("sceNpTrophySetInfoGetTrophyFlagArray", "const uint8_t* set_info, uint8_t* flag_array",
     "Bc5NptSetInfoGetTrophyFlagArray(set_info, flag_array)"),
    ("sceNpTrophySetInfoGetTrophyNum", "const uint8_t* set_info", "Bc5NptSetInfoGetTrophyNum(set_info)"),
    ("sceNpTrophySystemDbgCtl", "", "BC5_NPT_DBG_ANSWER"),
    ("sceNpTrophySystemGetDbgParam", "", "BC5_NPT_DBG_ANSWER"),
    ("sceNpTrophySystemGetDbgParamInt", "", "BC5_NPT_DBG_ANSWER"),
    ("sceNpTrophySystemSetDbgParam", "", "BC5_NPT_DBG_ANSWER"),
    ("sceNpTrophySystemSetDbgParamInt", "", "BC5_NPT_DBG_ANSWER"),
    ("sceNpTrophyUnlockTrophy", "int context, int handle, int trophy_id, int* platinum_id",
     "Bc5NptUnlockTrophy(context, handle, trophy_id, platinum_id)"),
)

# NpManager's two NIDs that the live table (libNet.cpp InitNet_1_NpManager) registers too: kept out when the switch is on.
NPM_SHARED_OLD = ('»LIB_FUNC("mjjTXh+NHWY", NpManager::sceNpUnregisterStateCallback);\n'
                  '»LIB_FUNC("cRILAEvn+9M", NpManager::sceNpUnregisterNpReachabilityStateCallback);\n')
NPM_SHARED_NEW = ('»if (!Bc5NpmOn()) { // BC5 experiment 0405 (tbn): on, only the live table (libNet.cpp) registers these two NIDs\n'
                  '»»LIB_FUNC("mjjTXh+NHWY", NpManager::sceNpUnregisterStateCallback);\n'
                  '»»LIB_FUNC("cRILAEvn+9M", NpManager::sceNpUnregisterNpReachabilityStateCallback);\n'
                  '»}\n')

TABLES = (
    # namespace, switch, on() name, block anchor, block, stubs, LIB_DEFINE, extra edits (what, old, new)
    ("NpCommon", "KYTY_BC5_LOAD_NPCOMMON", "Bc5NpcOn", NPC_ANCHOR, NPC_BLOCK, NPC_STUBS, "InitNpCommon_1", ()),
    ("NpManager", "KYTY_BC5_LOAD_NPMANAGER", "Bc5NpmOn", NPM_ANCHOR, NPM_BLOCK, NPM_STUBS, "InitNpManager_1",
     (("shared NIDs", NPM_SHARED_OLD, NPM_SHARED_NEW),)),
    ("NpTrophy", "KYTY_BC5_LOAD_NPTROPHY", "Bc5NptOn", NPT_ANCHOR, NPT_BLOCK, NPT_STUBS, "InitNpTrophy_1", ()),
)
EXPECT_COUNTS = {"NpCommon": 28, "NpManager": 20, "NpTrophy": 23}


def balance(b):
    return (b.count(b"{") - b.count(b"}"), b.count(b"(") - b.count(b")"), b.count(b"[") - b.count(b"]"))


def md5(b):
    return hashlib.md5(b).hexdigest()


def namespace_span(s, ns):
    """Byte range of 'namespace <ns> {' ... '} // namespace <ns>' in s."""
    a = s.index(b"namespace " + ns.encode() + b" {\n")
    z = s.index(b"} // namespace " + ns.encode() + b"\n", a)
    return a, z


def edits_for(ns, switch, on, stubs, define):
    out = []
    for name, params, call in stubs:
        old = f"static int KYTY_SYSV_ABI {name}() {{\n»PRINT_NAME();\n"
        new = (f"static int KYTY_SYSV_ABI {name}({params}) {{\n»PRINT_NAME();\n"
               f"»if ({on}()) {{ // BC5 experiment 0405 (tbn): the port, {switch}\n"
               f"»»return {call};\n»}}\n")
        out.append((ns, name, old, new))
    out.append((ns, define, f"LIB_DEFINE({define}) {{\n",
                f"LIB_DEFINE({define}) {{\n»(void){on}(); // BC5 experiment 0405 (tbn): reads {switch} once, prints its line\n"))
    return out


def edit(s):
    for m in MARKS:
        assert m not in s, ("refused: the unit has the edit already", m.decode())
    assert b"\r" not in s, "a CR in the LF unit"
    spans = {ns: namespace_span(s, ns) for ns, *_ in TABLES}
    out = s
    done = []  # (old bytes, new bytes) in order, for the undo check

    def apply(old, new, what, ns=None):
        nonlocal out
        o, n = T(old), T(new)
        assert out.count(o) == 1, ("anchor", what, out.count(o))
        if ns is not None:  # the anchor lies inside its namespace (checked on the current text)
            a = out.index(b"namespace " + ns.encode() + b" {\n")
            z = out.index(b"} // namespace " + ns.encode() + b"\n", a)
            assert a < out.index(o) < z, ("anchor outside its namespace", what, ns)
        assert balance(o) == balance(n), ("the edit changes the balance", what, balance(o), balance(n))
        out = out.replace(o, n)
        done.append((o, n))

    apply(INCLUDES_OLD, INCLUDES_NEW, "includes")
    for ns, switch, on, anchor, block, stubs, define, extra in TABLES:
        assert balance(T(block)) == (0, 0, 0), ("the block is not balanced", ns, balance(T(block)))
        assert len(stubs) == EXPECT_COUNTS[ns], (ns, len(stubs))
        apply(anchor, anchor + block, f"{ns} block", ns)
        for ns2, name, old, new in edits_for(ns, switch, on, stubs, define):
            apply(old, new, f"{ns2} {name}", ns2)
        for what, old, new in extra:
            apply(old, new, f"{ns} {what}", ns)
        want = len(stubs) + 2 + len(extra)  # the stubs, the definition, the registration line, the extra edits
        assert out.count(T(f"{on}()")) == want, (ns, "switch uses", out.count(T(f"{on}()")), want)
    assert balance(out) == balance(s), ("the unit's balance changed", balance(s), balance(out))
    # The other tables are byte for byte the same.
    for other in (b"NpAuth", b"NpPartner", b"NpParty", b"NpSnsFacebookDialog", b"NpTus"):
        a0 = s.index(b"namespace " + other + b" {\n")
        z0 = s.index(b"} // namespace " + other + b"\n", a0)
        a1 = out.index(b"namespace " + other + b" {\n")
        z1 = out.index(b"} // namespace " + other + b"\n", a1)
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
    del spans
    return out


def main():
    assert len(sys.argv) == 3, __doc__
    root, outdir = sys.argv[1], sys.argv[2]
    assert os.path.abspath(root) != os.path.abspath(outdir), "the out dir must not be the tree"
    with open(os.path.join(root, REL), "rb") as f:
        s = f.read()
    for m in MARKS:
        assert m not in s, ("refused: the unit has the edit already", REL, m.decode())
    assert md5(s) == PIN, ("refused: not the pinned input", REL, md5(s), PIN)
    out = edit(s)
    print(f"# in:  {REL} {md5(s)}  ({len(s)} bytes, LF)", file=sys.stderr)
    dst = os.path.join(outdir, REL)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    with open(dst, "wb") as f:
        f.write(out)
    print(f"{REL} {md5(out)}")


if __name__ == "__main__":
    main()
