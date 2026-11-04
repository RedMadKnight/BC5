#!/usr/bin/env python3
"""BC5 experiment 0401 series e5, exp 0405's thread synchronisation and semaphore ports (thr0405-notes.md):
src/kernel/pthread.cpp and src/kernel/semaphore.cpp, two switches.

KYTY_BC5_THREAD_SYNC_FIXES (pthread.cpp), parts:
  kk06      notify under the internal lock: mutex unlock, cond signal/broadcast/signalto, the guest-signal wake
            (KytyPS5 dfec14a src/kernel/pthread.cpp:506-525, 1404-1413, 2765-2771; GPL-2.0)
  kk03      a statically initialised rwlock (handle NULL): Destroy returns OK without creating it, Timedrdlock and
            Timedwrlock create it on first use; an unused static condition variable is destroyed with OK
            (KytyPS5 4592e4c, dfec14a src/kernel/pthread.cpp:2288-2299, 2469-2501; GPL-2.0)
  signalto  scePthreadCondSignalto: ESRCH for a handle that is not a live thread, EPERM for a thread not waiting
            (AnyPS5 0a5c3be28, core/libs/prx/libkernel/Pthread/src/Cond.cpp:258-268 @ 4f41f4c37; GPL-2.0-only)
  x87       a new guest thread starts with the x87 control word 0x037f
            (AnyPS5 8b626e307, core/libs/prx/libkernel/Pthread/src/Thread.cpp:65, 891 @ 4f41f4c37; GPL-2.0-only)
  kk07      PthreadGetprio, PthreadSetprio and PthreadCancel return ESRCH for a joined thread
            (KytyPS5 dfec14a src/kernel/pthread.cpp:3410-3413, 3518-3520, 3534-3537; GPL-2.0)
KYTY_BC5_SEMA_FIXES (semaphore.cpp), parts:
  attr      sceKernelCreateSema accepts the attributes 0x100-0x102 (AnyPS5 58295ef07, Semaphore.cpp:25-34)
  signal    sceKernelSignalSema: a count of 0 or less is EINVAL, an overflow-safe room check (AnyPS5 Semaphore.cpp:55-64)
Each switch: unset, empty or "0" is off (today's code path exactly); any other value turns all its parts on, unless it
names parts (comma-separated): then only those. Read once; one stderr line each ("[bc5] exp 0405: thread sync ..." at the
Pthread subsystem's init, "[bc5] exp 0405: sema ..." at the first semaphore call that reads it).

Input: the e5 input tree (KytyPlus f266548 + patch 0001 + e4's private units): pthread.cpp is e4's private unit 0363847b
(mkpth0401.py, KYTY_BC5_PTHREAD_FIXES, kept intact), semaphore.cpp the base tree's c9c4aaf5. Both inputs' md5s are
asserted; each anchor must occur exactly once; an input that has the edit already is refused; the edits only insert lines
(checked: every input line is kept in order); line endings (CRLF) are kept; the output is ASCII. Prints "<relpath> <md5>"
for each output.
usage: mkthr0405.py <tree root in> <out dir>"""
import difflib
import hashlib
import os
import sys

PTH = "src/kernel/pthread.cpp"
SEM = "src/kernel/semaphore.cpp"
IN_MD5 = {
    PTH: "0363847bd540883467dee22797475031",  # e4's private pthread.cpp (mkpth0401.py output), CRLF
    SEM: "c9c4aaf56492434eb84dc6e899260ae8",  # the base tree's semaphore.cpp, CRLF
}
MARKS = (b"experiment 0405", b"KYTY_BC5_THREAD_SYNC_FIXES", b"KYTY_BC5_SEMA_FIXES", b"Bc5ThreadSync", b"Bc5Sema")
E4_MARK = b"experiment 0401 series e4"  # e4's KYTY_BC5_PTHREAD_FIXES lines: their count must not change


def T(text):
    """C++ text written with a visible tab ("»") for each tab of the file's indentation, as ASCII bytes."""
    assert "\t" not in text, "write tabs as »"
    return text.replace("»", "\t").encode("ascii")


# ======================================== src/kernel/pthread.cpp ========================================================

# ---- the switch and the parts' constants, before CondAddWaiter (after the object structs; before every user) ---------
P_BLOCK_ANCHOR = T("static void CondAddWaiter(PthreadCondPrivate* cond, Pthread thread) {\n")
P_BLOCK = T(r"""// ---- experiment 0405 (series e5): thread synchronisation fixes, KYTY_BC5_THREAD_SYNC_FIXES ------------------------
// Exp 0405's port research (README top-32 rows 6, 10, 28, 31; raw/r2-kyty-sharpemu.md KK06, KK03 + SK11, KK07;
// raw/r1-anyps5.md #7, #14), adapted to this file; no upstream code is copied. Five parts:
// - "kk06": a mutex unlock (NativeMutexUnlock), a condition variable signal, broadcast and signalto, and the guest-signal
//   wake (PthreadWakeForSignal) notify while they still hold the object's internal lock. They notified after releasing
//   it, so a woken thread could return and destroy the object (or free the memory that holds its handle) first; the
//   notify then touched freed memory, or the handle the destroy had set to NULL. The rule of KytyPS5
//   (github.com/KytyPS5/KytyPS5, GPL-2.0) dfec14a src/kernel/pthread.cpp:506-525 (the comment at 523: notify while
//   holding cond->m "so the selected waiter cannot exit and be freed first"), 1404-1413 and 2765-2771; their waiter
//   queues differ from ours, only the rule is taken.
// - "kk03": a statically initialised rwlock (handle NULL): Destroy returns OK without creating it (KytyPS5 4592e4c,
//   dfec14a src/kernel/pthread.cpp:2288-2299), Timedrdlock and Timedwrlock create it on first use, as Rdlock, Wrlock and
//   the try locks already do (KytyPS5 dfec14a src/kernel/pthread.cpp:2469-2501; exp 0405's SK11 row). Both stopped the
//   emulator (EXIT_NOT_IMPLEMENTED) on legal calls. Extended, as exp 0405's KK03 row proposes, to PthreadCondDestroy: an
//   unused static condition variable is destroyed with OK. Without the switch a double destroy stops the emulator; with
//   it, it returns OK (a destroyed object's handle is NULL as a static one's is). TODO(verify) on a console.
// - "signalto": scePthreadCondSignalto returns ESRCH for a handle that is not a live thread and EPERM for a live thread
//   that is not waiting on the condition variable; it returned OK. The order of AnyPS5 (github.com/boykopovar/AnyPS5,
//   GPL-2.0-only) 0a5c3be28, core/libs/prx/libkernel/Pthread/src/Cond.cpp:258-268 @ 4f41f4c37, measured there on a PS5
//   (firmware 13.60, their docs/dev/debt/libkernel.md:345). Live here: a thread of the pool that has neither finished
//   nor been joined, the main thread, or the caller. The handle is only compared, never dereferenced.
// - "x87": a new guest thread starts with the x87 control word 0x037f (64-bit precision, every exception masked), the
//   FreeBSD thread start state, whatever word its creator uses (the host thread inherits the creator's). AnyPS5 8b626e307,
//   core/libs/prx/libkernel/Pthread/src/Thread.cpp:65, 891 @ 4f41f4c37; shadPS4 (GPL-2.0-or-later) 60c42b9
//   src/core/thread.cpp:23, 71 loads the same word. FreeBSD's own source of the value (__INITIAL_FPUCW__ and
//   cpu_copy_thread in sys/amd64, cited by AnyPS5's docs/dev/debt/libkernel.md) is not on disk here: TODO(verify). MXCSR
//   is not touched (shadPS4 also loads 0x9fc0 there, FreeBSD's default is 0x1f80: not ported).
// - "kk07": PthreadGetprio, PthreadSetprio and PthreadCancel return ESRCH for a joined thread; they used its stale host
//   handle (Setprio could renice a reused host thread id). KytyPS5 dfec14a src/kernel/pthread.cpp:3410-3413, 3518-3520,
//   3534-3537.
// KYTY_BC5_THREAD_SYNC_FIXES: unset, empty or "0" is off (today's code path exactly); any other value turns all five on,
// unless it names parts (comma-separated "kk06", "kk03", "signalto", "x87", "kk07"): then only those. Read once; one
// stderr line at the Pthread subsystem's init. The projects' copyright remains with their authors; GPL-2.0 as this file.
static constexpr uint32_t BC5_THR_FIX_KK06             = 1u;
static constexpr uint32_t BC5_THR_FIX_KK03             = 2u;
static constexpr uint32_t BC5_THR_FIX_SIGNALTO         = 4u;
static constexpr uint32_t BC5_THR_FIX_X87              = 8u;
static constexpr uint32_t BC5_THR_FIX_KK07             = 16u;
static constexpr uint32_t BC5_THR_FIX_ALL              = 31u;
static constexpr uint16_t BC5_GUEST_THREAD_FPU_CONTROL = 0x037f; // AnyPS5 Thread.cpp:65, shadPS4 thread.cpp:23

struct Bc5ThreadSyncPart {
»const char* name;
»uint32_t    part;
};
static constexpr Bc5ThreadSyncPart BC5_THR_PARTS[] = {{"kk06", BC5_THR_FIX_KK06},
                                                      {"kk03", BC5_THR_FIX_KK03},
                                                      {"signalto", BC5_THR_FIX_SIGNALTO},
                                                      {"x87", BC5_THR_FIX_X87},
                                                      {"kk07", BC5_THR_FIX_KK07}};

static uint32_t Bc5ThreadSyncParse(const char* e) {
»if (e == nullptr || e[0] == '\0' || std::strcmp(e, "0") == 0) {
»»return 0;
»}
»uint32_t    parts = 0;
»const char* p     = e;
»for (;;) {
»»const char*  comma = std::strchr(p, ',');
»»const size_t n     = comma != nullptr ? static_cast<size_t>(comma - p) : std::strlen(p);
»»for (const auto& k: BC5_THR_PARTS) {
»»»if (std::strlen(k.name) == n && std::strncmp(p, k.name, n) == 0) {
»»»»parts |= k.part;
»»»}
»»}
»»if (comma == nullptr) {
»»»break;
»»}
»»p = comma + 1;
»}
»return parts != 0 ? parts : BC5_THR_FIX_ALL;
}

// The parts of KYTY_BC5_THREAD_SYNC_FIXES that are on (0: off), read once.
static uint32_t Bc5ThreadSyncFixes() {
»static const uint32_t parts = [] {
»»const uint32_t p = Bc5ThreadSyncParse(std::getenv("KYTY_BC5_THREAD_SYNC_FIXES"));
»»if (p == 0) {
»»»std::fprintf(stderr, "[bc5] exp 0405: thread sync off\n");
»»} else {
»»»std::string items;
»»»for (const auto& k: BC5_THR_PARTS) {
»»»»if ((p & k.part) != 0) {
»»»»»items += (items.empty() ? "" : ",");
»»»»»items += k.name;
»»»»}
»»»}
»»»std::fprintf(stderr, "[bc5] exp 0405: thread sync on (items: %s)\n", items.c_str());
»»}
»»std::fflush(stderr);
»»return p;
»}();
»return parts;
}

static bool Bc5ThreadSyncFix(uint32_t part) {
»return (Bc5ThreadSyncFixes() & part) != 0;
}
// ---- end of experiment 0405's switch block ------------------------------------------------------------------------

""")

# ---- the switch's line at the Pthread subsystem's init --------------------------------------------------------------
P_INIT_OLD = T("»Common::CondVar::SetWaitPollCallback(KernelDispatchPendingSignalForCurrentThread);\n")
P_INIT_NEW = T("""»Common::CondVar::SetWaitPollCallback(KernelDispatchPendingSignalForCurrentThread);
»(void)Bc5ThreadSyncFixes(); // experiment 0405: KYTY_BC5_THREAD_SYNC_FIXES's one stderr line, at init
""")

# ---- kk06: PthreadWakeForSignal --------------------------------------------------------------------------------------
P_WAKE_OLD = T("»»notify = (thread->waiting_cond == cond);\n")
P_WAKE_NEW = T("""»»notify = (thread->waiting_cond == cond);
»»if (Bc5ThreadSyncFix(BC5_THR_FIX_KK06) && notify) { // experiment 0405 kk06: notify while cond->m is held
»»»cond->cv.notify_all();
»»»notify = false;
»»}
""")

# ---- kk06: NativeMutexUnlock -----------------------------------------------------------------------------------------
P_UNLOCK_OLD = T("""»mutex->owner = nullptr;
»mutex->count = 0;
»lock.unlock();
»mutex->cv.notify_one();
""")
P_UNLOCK_NEW = T("""»mutex->owner = nullptr;
»mutex->count = 0;
»if (Bc5ThreadSyncFix(BC5_THR_FIX_KK06)) { // experiment 0405 kk06: wake a waiter while mutex->m is held
»»mutex->cv.notify_one();
»»return OK; // `lock` releases mutex->m after the notify
»}
»lock.unlock();
»mutex->cv.notify_one();
""")

# ---- kk06: PthreadCondBroadcast --------------------------------------------------------------------------------------
P_BCAST_OLD = T("""»»»CondClearWaiters(*cond);
»»»notify = true;
»»}
""")
P_BCAST_NEW = T("""»»»CondClearWaiters(*cond);
»»»notify = true;
»»}
»»if (Bc5ThreadSyncFix(BC5_THR_FIX_KK06) && notify) { // experiment 0405 kk06: notify while (*cond)->m is held
»»»(*cond)->cv.notify_all();
»»»notify = false;
»»}
""")

# ---- kk06: PthreadCondSignal -----------------------------------------------------------------------------------------
P_SIGNAL_OLD = T("»»notify = CondWakeWaiter(*cond, nullptr);\n")
P_SIGNAL_NEW = T("""»»notify = CondWakeWaiter(*cond, nullptr);
»»if (Bc5ThreadSyncFix(BC5_THR_FIX_KK06) && notify) { // experiment 0405 kk06: notify while (*cond)->m is held
»»»(*cond)->cv.notify_all();
»»»notify = false;
»»}
""")

# ---- kk06 and signalto: PthreadCondSignalto --------------------------------------------------------------------------
P_SIGNALTO_OLD = T("""»int  result = 0;
»bool notify = false;
»{
»»std::lock_guard lock((*cond)->m);
»»notify = CondWakeWaiter(*cond, thread);
»}
»if (notify) {
»»(*cond)->cv.notify_all();
»}
""")
P_SIGNALTO_NEW = T("""»int  result = 0;
»bool notify = false;
»bool bc5_woke = false; // experiment 0405 signalto: the target was waiting and is woken
»{
»»std::lock_guard lock((*cond)->m);
»»notify = CondWakeWaiter(*cond, thread);
»»bc5_woke = notify; // experiment 0405 signalto
»»if (Bc5ThreadSyncFix(BC5_THR_FIX_KK06) && notify) { // experiment 0405 kk06: notify while (*cond)->m is held
»»»(*cond)->cv.notify_all();
»»»notify = false;
»»}
»}
»if (notify) {
»»(*cond)->cv.notify_all();
»}
»if (Bc5ThreadSyncFix(BC5_THR_FIX_SIGNALTO) && !bc5_woke) { // experiment 0405 signalto: ESRCH or EPERM, not OK
»»return Bc5SignaltoNotWaiting(thread);
»}
""")

# ---- signalto: PthreadPool::Bc5IsLive and the answer for a target that was not waiting -------------------------------
P_POOL_OLD = T("""»void FreeDetachedThreads();

private:
»std::vector<Pthread> m_threads;
""")
P_POOL_NEW = T("""»void FreeDetachedThreads();
»bool Bc5IsLive(Pthread thread); // experiment 0405 signalto: a pool thread neither finished nor joined

private:
»std::vector<Pthread> m_threads;
""")
P_LIVE_ANCHOR = T("bool PthreadKeys::Create(int* key, pthread_key_destructor_func_t destructor) {\n")
P_LIVE = T(r"""// ---- experiment 0405 (series e5) "signalto", KYTY_BC5_THREAD_SYNC_FIXES (the block before CondAddWaiter) -----------
// A thread of the pool is live until it has finished (almost_done, set by CleanupThread) or been joined (free). Used only
// with the switch on.
bool PthreadPool::Bc5IsLive(Pthread thread) {
»Common::LockGuard lock(m_mutex);

»for (auto* p: m_threads) {
»»if (p == thread) {
»»»return !p->free && !p->almost_done;
»»}
»}
»return false;
}

// scePthreadCondSignalto's answer when the target was not waiting on the condition variable: EPERM for a live thread,
// ESRCH for any other handle (AnyPS5 0a5c3be28, core/libs/prx/libkernel/Pthread/src/Cond.cpp:258-268 @ 4f41f4c37; a
// finished, unjoined thread gets ESRCH there too). The handle is only compared, never dereferenced.
static int Bc5SignaltoNotWaiting(Pthread thread) {
»const bool live = (thread == g_pthread_self || thread == g_pthread_main ||
»                   g_pthread_context->GetPthreadPool()->Bc5IsLive(thread));
»return live ? KERNEL_ERROR_EPERM : KERNEL_ERROR_ESRCH;
}
// ---- end of experiment 0405's signalto block ----------------------------------------------------------------------

""")

# ---- kk03: PthreadRwlockDestroy, PthreadRwlockTimedrdlock, PthreadRwlockTimedwrlock, PthreadCondDestroy -------------
P_RWDESTROY_OLD = T("""int KYTY_SYSV_ABI PthreadRwlockDestroy(PthreadRwlock* rwlock) {
»PRINT_NAME();

»if (rwlock == nullptr) {
»»return KERNEL_ERROR_EINVAL;
»}

»EXIT_NOT_IMPLEMENTED(*rwlock == nullptr);
""")
P_RWDESTROY_NEW = T("""int KYTY_SYSV_ABI PthreadRwlockDestroy(PthreadRwlock* rwlock) {
»PRINT_NAME();

»if (rwlock == nullptr) {
»»return KERNEL_ERROR_EINVAL;
»}

»// Experiment 0405 kk03 (KYTY_BC5_THREAD_SYNC_FIXES): a statically initialised lock that was never used has nothing to
»// free (KytyPS5 4592e4c, dfec14a src/kernel/pthread.cpp:2295-2298).
»if (Bc5ThreadSyncFix(BC5_THR_FIX_KK03) && *rwlock == nullptr) {
»»return OK;
»}
»EXIT_NOT_IMPLEMENTED(*rwlock == nullptr);
""")

KK03_CREATE = """»// Experiment 0405 kk03 (KYTY_BC5_THREAD_SYNC_FIXES): a statically initialised lock is created on first use, as
»// PthreadRwlockRdlock does (KytyPS5 dfec14a src/kernel/pthread.cpp:2469-2501).
»if (Bc5ThreadSyncFix(BC5_THR_FIX_KK03)) {
»»rwlock = static_cast<PthreadRwlock*>(
»»    g_pthread_context->GetPthreadStaticObjects()->CreateObject(rwlock, PthreadStaticObject::Type::Rwlock));
»}
"""


def timed_pair(fn):
    head = """int KYTY_SYSV_ABI %s(PthreadRwlock* rwlock, KernelUseconds usec) {
»PRINT_NAME();

»if (rwlock == nullptr) {
»»return KERNEL_ERROR_EINVAL;
»}

""" % fn
    tail = "»EXIT_NOT_IMPLEMENTED(*rwlock == nullptr);\n"
    return T(head + tail), T(head + KK03_CREATE + tail)


P_TIMEDRD_OLD, P_TIMEDRD_NEW = timed_pair("PthreadRwlockTimedrdlock")
P_TIMEDWR_OLD, P_TIMEDWR_NEW = timed_pair("PthreadRwlockTimedwrlock")

P_CDESTROY_OLD = T("""int KYTY_SYSV_ABI PthreadCondDestroy(PthreadCond* cond) {
»PRINT_NAME();

»if (cond == nullptr) {
»»return KERNEL_ERROR_EINVAL;
»}

»EXIT_NOT_IMPLEMENTED(*cond == nullptr);
""")
P_CDESTROY_NEW = T("""int KYTY_SYSV_ABI PthreadCondDestroy(PthreadCond* cond) {
»PRINT_NAME();

»if (cond == nullptr) {
»»return KERNEL_ERROR_EINVAL;
»}

»// Experiment 0405 kk03 (KYTY_BC5_THREAD_SYNC_FIXES): a statically initialised condition variable that was never used
»// has nothing to free, as for a rwlock (exp 0405's KK03 row extends KytyPS5 4592e4c to it).
»if (Bc5ThreadSyncFix(BC5_THR_FIX_KK03) && *cond == nullptr) {
»»return OK;
»}
»EXIT_NOT_IMPLEMENTED(*cond == nullptr);
""")

# ---- x87: RunThread --------------------------------------------------------------------------------------------------
P_RUN_OLD = T("""static void* RunThread(void* arg) {
»auto* thread = static_cast<Pthread>(arg);
»void* ret    = nullptr;
""")
P_RUN_NEW = T("""static void* RunThread(void* arg) {
»auto* thread = static_cast<Pthread>(arg);
»void* ret    = nullptr;

#if defined(__x86_64__) || defined(_M_X64)
»// Experiment 0405 x87 (KYTY_BC5_THREAD_SYNC_FIXES): the FreeBSD thread start state of the x87 control word, 0x037f,
»// before any guest code (AnyPS5 8b626e307, Thread.cpp:891); off, the thread keeps the word its creator had.
»if (Bc5ThreadSyncFix(BC5_THR_FIX_X87)) {
»»const uint16_t bc5_fpu_control = BC5_GUEST_THREAD_FPU_CONTROL;
»»asm volatile("fldcw %0" : : "m"(bc5_fpu_control));
»}
#endif
""")

# ---- kk07: PthreadCancel, PthreadGetprio, PthreadSetprio -------------------------------------------------------------
KK07 = """»if (Bc5ThreadSyncFix(BC5_THR_FIX_KK07) && thread->free) { // experiment 0405 kk07: a joined thread (KytyPS5 dfec14a)
»»return KERNEL_ERROR_ESRCH;
»}
"""


def kk07_pair(sig, null_err):
    head = """int KYTY_SYSV_ABI %s {
»PRINT_NAME();

»if (thread == nullptr) {
»»return %s;
»}
""" % (sig, null_err)
    return T(head), T(head + KK07)


P_CANCEL_OLD, P_CANCEL_NEW = kk07_pair("PthreadCancel(Pthread thread)", "KERNEL_ERROR_EINVAL")
P_GETPRIO_OLD, P_GETPRIO_NEW = kk07_pair("PthreadGetprio(Pthread thread, int* prio)", "KERNEL_ERROR_ESRCH")
P_SETPRIO_OLD, P_SETPRIO_NEW = kk07_pair("PthreadSetprio(Pthread thread, int prio)", "KERNEL_ERROR_ESRCH")

PTH_EDITS = (
    ("the switch block before CondAddWaiter", P_BLOCK_ANCHOR, P_BLOCK + P_BLOCK_ANCHOR),
    ("the Pthread subsystem's init", P_INIT_OLD, P_INIT_NEW),
    ("kk06 PthreadWakeForSignal", P_WAKE_OLD, P_WAKE_NEW),
    ("kk06 NativeMutexUnlock", P_UNLOCK_OLD, P_UNLOCK_NEW),
    ("kk06 PthreadCondBroadcast", P_BCAST_OLD, P_BCAST_NEW),
    ("kk06 PthreadCondSignal", P_SIGNAL_OLD, P_SIGNAL_NEW),
    ("kk06 + signalto PthreadCondSignalto", P_SIGNALTO_OLD, P_SIGNALTO_NEW),
    ("signalto PthreadPool's declaration", P_POOL_OLD, P_POOL_NEW),
    ("signalto Bc5IsLive before PthreadKeys::Create", P_LIVE_ANCHOR, P_LIVE + P_LIVE_ANCHOR),
    ("kk03 PthreadRwlockDestroy", P_RWDESTROY_OLD, P_RWDESTROY_NEW),
    ("kk03 PthreadRwlockTimedrdlock", P_TIMEDRD_OLD, P_TIMEDRD_NEW),
    ("kk03 PthreadRwlockTimedwrlock", P_TIMEDWR_OLD, P_TIMEDWR_NEW),
    ("kk03 PthreadCondDestroy", P_CDESTROY_OLD, P_CDESTROY_NEW),
    ("x87 RunThread", P_RUN_OLD, P_RUN_NEW),
    ("kk07 PthreadCancel", P_CANCEL_OLD, P_CANCEL_NEW),
    ("kk07 PthreadGetprio", P_GETPRIO_OLD, P_GETPRIO_NEW),
    ("kk07 PthreadSetprio", P_SETPRIO_OLD, P_SETPRIO_NEW),
)

# ======================================== src/kernel/semaphore.cpp ======================================================

S_INC_OLD = T("#include <cstdlib>\n")
S_INC_NEW = T("""#include <cstdlib>
#include <cstdio>  // experiment 0405: std::fprintf
#include <cstring> // experiment 0405: std::strcmp, std::strchr
""")

S_BLOCK_ANCHOR = T("KernelSemaPrivate::~KernelSemaPrivate() {\n")
S_BLOCK = T(r"""// ---- experiment 0405 (series e5): semaphore argument checks, KYTY_BC5_SEMA_FIXES ---------------------------------
// Exp 0405's top-32 row 28 (raw/r1-anyps5.md #8, with raw/r2-kyty-sharpemu.md SK09), adapted; no upstream code is
// copied. After AnyPS5 (github.com/boykopovar/AnyPS5, GPL-2.0-only) 58295ef07,
// core/libs/prx/libkernel/Semaphore/src/Semaphore.cpp:25-34 and 55-64 @ 4f41f4c37, whose values a payload process on a
// PS5 (firmware 13.60) measured (AnyPS5 docs/dev/debt/libkernel.md:5 and 91, citing prosper
// tests/data/console_oracle/kernel.golden.tsv L10-23 @ 3ea5cb9). Two parts:
// - "attr": sceKernelCreateSema accepts the attributes 0x100, 0x101 and 0x102 (their effect is unknown there: the 0x100
//   bit is ignored, the low two bits still choose the queue order); 3, 0x103 and every other bit still give EINVAL. It
//   refused everything above 2.
// - "signal": sceKernelSignalSema with a count of 0 or less gives EINVAL (a negative count lowered the count, 0 was OK),
//   and the room check cannot overflow (m_count > m_max_count - signal_count, as AnyPS5 Semaphore.cpp:64 and sharpemu
//   514d766 KernelSemaphoreCompatExports.cs:388 compare; m_count + signal_count wrapped for a huge count).
// Not parts: a poll of 0 or above the maximum already gives EINVAL (KernelSemaPrivate::Wait's need check); a null output
// pointer to sceKernelCreateSema still stops the emulator (the console faults there, AnyPS5's debt note).
// KYTY_BC5_SEMA_FIXES: unset, empty or "0" is off (today's code path exactly); any other value turns both on, unless it
// names parts (comma-separated "attr", "signal"): then only those. Read once; one stderr line at the first create or
// signal. AnyPS5's copyright remains with its authors; GPL-2.0 as this file.
static constexpr uint32_t BC5_SEMA_FIX_ATTR   = 1u;
static constexpr uint32_t BC5_SEMA_FIX_SIGNAL = 2u;

static uint32_t Bc5SemaFixesParse(const char* e) {
»if (e == nullptr || e[0] == '\0' || std::strcmp(e, "0") == 0) {
»»return 0;
»}
»uint32_t    parts = 0;
»const char* p     = e;
»for (;;) {
»»const char*  comma = std::strchr(p, ',');
»»const size_t n     = comma != nullptr ? static_cast<size_t>(comma - p) : std::strlen(p);
»»if (n == 4 && std::strncmp(p, "attr", n) == 0) {
»»»parts |= BC5_SEMA_FIX_ATTR;
»»} else if (n == 6 && std::strncmp(p, "signal", n) == 0) {
»»»parts |= BC5_SEMA_FIX_SIGNAL;
»»}
»»if (comma == nullptr) {
»»»break;
»»}
»»p = comma + 1;
»}
»return parts != 0 ? parts : (BC5_SEMA_FIX_ATTR | BC5_SEMA_FIX_SIGNAL);
}

// The parts of KYTY_BC5_SEMA_FIXES that are on (0: off), read once.
static uint32_t Bc5SemaFixes() {
»static const uint32_t parts = [] {
»»const uint32_t p = Bc5SemaFixesParse(std::getenv("KYTY_BC5_SEMA_FIXES"));
»»if (p == 0) {
»»»std::fprintf(stderr, "[bc5] exp 0405: sema off\n");
»»} else {
»»»std::fprintf(stderr, "[bc5] exp 0405: sema on (items: %s%s%s)\n", (p & BC5_SEMA_FIX_ATTR) != 0 ? "attr" : "",
»»»             p == (BC5_SEMA_FIX_ATTR | BC5_SEMA_FIX_SIGNAL) ? "," : "", (p & BC5_SEMA_FIX_SIGNAL) != 0 ? "signal" : "");
»»}
»»std::fflush(stderr);
»»return p;
»}();
»return parts;
}

static bool Bc5SemaFix(uint32_t part) {
»return (Bc5SemaFixes() & part) != 0;
}
// ---- end of experiment 0405's block -------------------------------------------------------------------------------

""")

S_ROOM_OLD = T("""»if (m_count + signal_count > m_max_count) {
»»return Result::InvalCount;
»}
""")
S_ROOM_NEW = T("""»// Experiment 0405 "signal" (KYTY_BC5_SEMA_FIXES): a room check that cannot overflow (AnyPS5 Semaphore.cpp:64).
»if (Bc5SemaFix(BC5_SEMA_FIX_SIGNAL) && (signal_count <= 0 || m_count > m_max_count - signal_count)) {
»»return Result::InvalCount;
»}
»if (m_count + signal_count > m_max_count) {
»»return Result::InvalCount;
»}
""")

S_CREATE_OLD = T("»if (name == nullptr || attr > 2 || init < 0 || max <= 0 || init > max) {\n")
S_CREATE_NEW = T("""»// Experiment 0405 "attr" (KYTY_BC5_SEMA_FIXES): 0x100, 0x101 and 0x102 are accepted, the 0x100 bit ignored; the low two
»// bits still choose the queue order (AnyPS5 58295ef07, Semaphore.cpp:30-33).
»if (Bc5SemaFix(BC5_SEMA_FIX_ATTR) && (attr & ~0x103u) == 0 && (attr & 3u) != 3u) {
»»attr &= 3u;
»}
»if (name == nullptr || attr > 2 || init < 0 || max <= 0 || init > max) {
""")

S_SIGNAL_OLD = T("""int KYTY_SYSV_ABI KernelSignalSema(KernelSema sem, int count) {
»if (sem == nullptr) {
»»return KERNEL_ERROR_ESRCH;
»}
""")
S_SIGNAL_NEW = T("""int KYTY_SYSV_ABI KernelSignalSema(KernelSema sem, int count) {
»if (sem == nullptr) {
»»return KERNEL_ERROR_ESRCH;
»}
»// Experiment 0405 "signal" (KYTY_BC5_SEMA_FIXES): a count of 0 or less is EINVAL (AnyPS5 Semaphore.cpp:59-61).
»if (Bc5SemaFix(BC5_SEMA_FIX_SIGNAL) && count <= 0) {
»»return KERNEL_ERROR_EINVAL;
»}
""")

SEM_EDITS = (
    ("the includes", S_INC_OLD, S_INC_NEW),
    ("the switch block before ~KernelSemaPrivate", S_BLOCK_ANCHOR, S_BLOCK + S_BLOCK_ANCHOR),
    ("signal KernelSemaPrivate::Signal's room check", S_ROOM_OLD, S_ROOM_NEW),
    ("attr KernelCreateSema", S_CREATE_OLD, S_CREATE_NEW),
    ("signal KernelSignalSema", S_SIGNAL_OLD, S_SIGNAL_NEW),
)

FILES = ((PTH, PTH_EDITS), (SEM, SEM_EDITS))


def eol_of(s):
    crlf, lf = s.count(b"\r\n"), s.count(b"\n")
    assert crlf == 0 or crlf == lf, ("mixed line endings", crlf, lf)
    return b"\r\n" if crlf else b"\n"


def balance(s):
    return tuple(s.count(c) for c in b"{}()[]")


def apply(rel, s, edits):
    for m in MARKS:
        assert m not in s, f"{rel} has the edit already ({m.decode()})"
    eol = eol_of(s)
    e4 = s.count(E4_MARK)
    out = s
    for what, old, new in edits:
        o, n = old.replace(b"\n", eol), new.replace(b"\n", eol)
        assert out.count(o) == 1, (rel, what, out.count(o))
        # each inserted text keeps its own braces and parentheses balanced
        ins = balance(n)
        ref = balance(o)
        d = [a - b for a, b in zip(ins, ref)]
        assert d[0] == d[1] and d[2] == d[3] and d[4] == d[5], (rel, what, d)
        out = out.replace(o, n)
    # only insertions: every input line is kept, in order
    a, b = s.split(eol), out.split(eol)
    for tag, *_ in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        assert tag in ("equal", "insert"), (rel, "an input line changed", tag)
    assert eol_of(out) == eol and out.count(E4_MARK) == e4, (rel, "line endings or e4's lines changed")
    out.decode("ascii")
    return out


def main():
    assert len(sys.argv) == 3, __doc__
    root, outdir = sys.argv[1], sys.argv[2]
    outs = []  # every input is checked and edited before anything is written
    for rel, edits in FILES:
        with open(os.path.join(root, rel), "rb") as f:
            s = f.read()
        for m in MARKS:
            if m in s:
                sys.exit(f"mkthr0405: {rel} has the edit already ({m.decode()}); refused, nothing written")
        got = hashlib.md5(s).hexdigest()
        assert got == IN_MD5[rel], f"{rel}: md5 {got}, not the pinned input {IN_MD5[rel]}; nothing written"
        outs.append((rel, apply(rel, s, edits)))
    for rel, out in outs:
        p = os.path.join(outdir, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "wb") as f:
            f.write(out)
        print(f"{rel} {hashlib.md5(out).hexdigest()}")


if __name__ == "__main__":
    main()
