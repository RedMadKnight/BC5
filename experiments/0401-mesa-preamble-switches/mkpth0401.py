#!/usr/bin/env python3
"""BC5 experiment 0401 series e4, KYTY_BC5_PTHREAD_FIXES (exp 0402's survey, Top 10 row 3): the console's rwlock reader
preference for a thread that holds a read lock, in src/kernel/pthread.cpp. FreeBSD 11.4 libthr (thr_rwlock.c) passes
URWLOCK_PREFER_READER on a read lock while the calling thread holds any read lock (curthread->rdlock_count), so waiting
writers do not hold it back; AnyPS5 (boykopovar/AnyPS5, GPL-2.0-only) 45a8b80a5 honours that flag in its _umtx_op and
its HLE locks keep the same count (core/libs/prx/libkernel/Pthread/src/Rwlock.cpp @ 4f41f4c37, readLocksHeld). Our
file applies the rule only to a reader of the same lock. This tree has no _umtx_op, so no code of the commit is taken;
the rule is adapted: a per-thread count of read locks, kept and used only with the switch on. AnyPS5's four other
commits of the survey row (4ed0f9f91, 372f0f6c6, 83b1015c4, 16375634e) are not ported: their defects cannot occur in
this file's design (pth0401-notes.md).
Switch KYTY_BC5_PTHREAD_FIXES: on when set, non-empty and not "0" (F767's reading), read once. Off (unset or "0") is
today's code path: the same admission test and no count; the only addition is one stderr line at the first read lock.
Edits main 029e0d6b's tree (KytyPlus f266548 + patch 0001): src/kernel/pthread.cpp only (md5 11cef59e on the shared
builds' tree, CRLF line endings; an LF copy is handled too). Each anchor must occur exactly once; a tree that has the
edit already is refused. Prints "<md5>  <relpath>" for each output.
usage: mkpth0401.py <tree root in> <out dir>"""
import hashlib
import os
import sys

REL = "src/kernel/pthread.cpp"
IN_MD5 = "11cef59e0ff15f650eba98bb11f91bce"  # the shared builds' pthread.cpp (CRLF)
MARK = b"KYTY_BC5_PTHREAD_FIXES"

# Anchors and texts are written with LF here and converted to the file's line ending.
INCLUDE_OLD = b"#include <cstring>\n"
INCLUDE_NEW = b"#include <cstring>\n#include <cstdlib> // experiment 0401 series e4: std::getenv\n"

BLOCK_ANCHOR = b"static PthreadRwlockPrivate::Reader* RwlockFindReader(PthreadRwlock rwlock, Pthread thread) {\n"
BLOCK = b"""// ---- experiment 0401 series e4: rwlock reader preference for a thread that holds a read lock --------------------------
// The console's rule as FreeBSD 11.4 libthr has it (lib/libthr/thread/thr_rwlock.c @ release/11.4.0:
// rwlock_rdlock_common and _pthread_rwlock_tryrdlock pass URWLOCK_PREFER_READER while curthread->rdlock_count is not 0,
// and _pthread_rwlock_unlock counts a read unlock down; thr_umtx.h _thr_rwlock_tryrdlock then refuses such a reader only
// for a write owner, not for waiting writers): a thread that holds a read lock on any rwlock takes a read lock past
// waiting writers, so two readers that each wait behind the other lock's queued writer cannot deadlock. This file
// applied it only to a reader of the same lock (already_reader). After AnyPS5 (boykopovar/AnyPS5, GPL-2.0-only)
// 45a8b80a5 "fix(libkernel): honour URWLOCK_PREFER_READER passed with RW_RDLOCK as the console does" (its _umtx_op in
// core/libs/prx/libkernel/SyncOnAddress/src/SyncOnAddress.cpp; this tree has no _umtx_op, so none of the commit's code
// is taken) and the readLocksHeld count of its HLE locks (core/libs/prx/libkernel/Pthread/src/Rwlock.cpp @ 4f41f4c37,
// lines 44-57 and 166), adapted: a per-thread count of the read locks held, kept in RwlockLockCooperative,
// PthreadRwlockTryrdlock and PthreadRwlockUnlock. Switch KYTY_BC5_PTHREAD_FIXES: on when set, non-empty and not "0",
// read once; unset or "0" (the default) is today's code path: no count, today's admission test. AnyPS5's other four
// libkernel commits of exp 0402's row 3 (4ed0f9f91, 372f0f6c6, 83b1015c4, 16375634e) are not ported: their defects
// cannot occur here, where one mutex per lock guards all of its state (experiment 0401, pth0401-notes.md). AnyPS5's
// copyright remains with its authors; GPL-2.0-only, as the rest of this file.
static bool Bc5PthreadFixesOn() {
	static const bool on = [] {
		const char* e     = std::getenv("KYTY_BC5_PTHREAD_FIXES");
		const bool  value = e != nullptr && e[0] != '\\0' && std::strcmp(e, "0") != 0;
		std::fprintf(stderr, "[bc5] exp 0401: pthread fixes %s (%s)\\n", value ? "on" : "off",
		             value ? "rwlock: a thread that holds any read lock reads past waiting writers, AnyPS5 45a8b80a5, libthr rdlock_count"
		                   : "rwlock: today's rule, only a reader of the same lock reads past waiting writers");
		return value;
	}();
	return on;
}

static thread_local uint32_t g_bc5_read_locks_held = 0; // this thread's read locks; counted only with the switch on

static bool Bc5HoldsAReadLock() {
	return Bc5PthreadFixesOn() && g_bc5_read_locks_held != 0;
}

static void Bc5ReadLockTaken() {
	if (Bc5PthreadFixesOn()) {
		g_bc5_read_locks_held++;
	}
}

static void Bc5ReadLockReleased() {
	if (Bc5PthreadFixesOn() && g_bc5_read_locks_held != 0) {
		g_bc5_read_locks_held--;
	}
}
// ---- end of experiment 0401 series e4's block ----------------------------------------------------------------------

"""

# RwlockLockCooperative, the read side (Rdlock, Timedrdlock: exp 0327's timed rwlocks, and the posix entry points).
COOP_OLD = b"""\t\t\t\tconst bool already_reader = (RwlockFindReader(rwlock, self) != nullptr);
\t\t\t\tif ((rwlock->writer == nullptr &&
\t\t\t\t     (rwlock->waiting_writers == 0 || already_reader)) ||
\t\t\t\t    rwlock->writer == self) {
\t\t\t\t\tRwlockAddReader(rwlock, self);
\t\t\t\t\treturn OK;
\t\t\t\t}
"""
COOP_NEW = b"""\t\t\t\t// Experiment 0401 series e4 (KYTY_BC5_PTHREAD_FIXES): with the switch on, a thread that holds a read lock on any
\t\t\t\t// rwlock also reads past waiting writers (libthr's rdlock_count rule); off, Bc5HoldsAReadLock() is false.
\t\t\t\tconst bool already_reader = (RwlockFindReader(rwlock, self) != nullptr) || Bc5HoldsAReadLock();
\t\t\t\tif ((rwlock->writer == nullptr &&
\t\t\t\t     (rwlock->waiting_writers == 0 || already_reader)) ||
\t\t\t\t    rwlock->writer == self) {
\t\t\t\t\tRwlockAddReader(rwlock, self);
\t\t\t\t\tBc5ReadLockTaken(); // experiment 0401 series e4
\t\t\t\t\treturn OK;
\t\t\t\t}
"""

# PthreadRwlockTryrdlock (libthr's _pthread_rwlock_tryrdlock takes the same flag).
TRY_OLD = b"""\t\tconst bool      already_reader = (RwlockFindReader(*rwlock, self) != nullptr);
\t\tif (((*rwlock)->writer == nullptr && ((*rwlock)->waiting_writers == 0 || already_reader)) ||
\t\t    (*rwlock)->writer == self) {
\t\t\tRwlockAddReader(*rwlock, self);
\t\t\treturn OK;
\t\t}
"""
TRY_NEW = b"""\t\t// Experiment 0401 series e4 (KYTY_BC5_PTHREAD_FIXES): as in RwlockLockCooperative; off, Bc5HoldsAReadLock() is false.
\t\tconst bool      already_reader = (RwlockFindReader(*rwlock, self) != nullptr) || Bc5HoldsAReadLock();
\t\tif (((*rwlock)->writer == nullptr && ((*rwlock)->waiting_writers == 0 || already_reader)) ||
\t\t    (*rwlock)->writer == self) {
\t\t\tRwlockAddReader(*rwlock, self);
\t\t\tBc5ReadLockTaken(); // experiment 0401 series e4
\t\t\treturn OK;
\t\t}
"""

# PthreadRwlockUnlock, a read unlock (libthr's _pthread_rwlock_unlock counts down only after a read unlock succeeded).
UNLOCK_OLD = b"""\t\tif (RwlockRemoveReader(*rwlock, self)) {
\t\t\t(*rwlock)->cv.notify_all();
"""
UNLOCK_NEW = b"""\t\tif (RwlockRemoveReader(*rwlock, self)) {
\t\t\tBc5ReadLockReleased(); // experiment 0401 series e4
\t\t\t(*rwlock)->cv.notify_all();
"""


def eol_of(s):
    crlf, lf = s.count(b"\r\n"), s.count(b"\n")
    assert crlf == 0 or crlf == lf, ("mixed line endings", crlf, lf)
    return b"\r\n" if crlf else b"\n"


def once(s, old, new, what, eol):
    old, new = old.replace(b"\n", eol), new.replace(b"\n", eol)
    assert s.count(old) == 1, (what, old[:80], s.count(old))
    return s.replace(old, new)


def edit_pthread(s):
    assert MARK not in s and b"Bc5HoldsAReadLock" not in s and b"experiment 0401 series e4" not in s, \
        "pthread.cpp has the edit already"
    assert b"#include <cstdlib>" not in s, "pthread.cpp includes <cstdlib> already: look again"
    eol = eol_of(s)
    s = once(s, INCLUDE_OLD, INCLUDE_NEW, "the includes", eol)
    s = once(s, BLOCK_ANCHOR, BLOCK + BLOCK_ANCHOR, "RwlockFindReader", eol)
    s = once(s, COOP_OLD, COOP_NEW, "RwlockLockCooperative's read side", eol)
    s = once(s, TRY_OLD, TRY_NEW, "PthreadRwlockTryrdlock", eol)
    s = once(s, UNLOCK_OLD, UNLOCK_NEW, "PthreadRwlockUnlock's read side", eol)
    # the helpers come before their first use, and each is used where it should be
    assert s.index(b"static bool Bc5HoldsAReadLock()") < s.index(b"|| Bc5HoldsAReadLock();")
    assert s.count(b"|| Bc5HoldsAReadLock();") == 2 and s.count(b"\tBc5ReadLockTaken(); // experiment 0401 series e4") == 2
    assert s.count(b"\tBc5ReadLockReleased(); // experiment 0401 series e4") == 1
    assert eol_of(s) == eol
    return s


FILES = ((REL, edit_pthread),)


def main():
    assert len(sys.argv) == 3, __doc__
    root, out = sys.argv[1], sys.argv[2]
    for rel, fn in FILES:
        with open(os.path.join(root, rel), "rb") as f:
            s = f.read()
        if rel == REL and hashlib.md5(s).hexdigest() != IN_MD5:
            print(f"mkpth0401: note: {rel} is not the shared builds' copy ({IN_MD5}); the anchors decide", file=sys.stderr)
        o = fn(s)
        p = os.path.join(out, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "wb") as f:
            f.write(o)
        print(f"{hashlib.md5(o).hexdigest()}  {rel}")


if __name__ == "__main__":
    main()
