#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0
"""BC5 experiment 0438 (tag o438): the records item "which wait, who wakes it", normal build only, off unless
BC5_0438_OUTSIDE=1 (o438.hpp). Applies the spans and the signal marks to patch bb04219b's tree files (LF, md5s pinned)
and writes them, with o438.hpp as src/kernel/o438.hpp, under OUT_ROOT (the build's source copy):
    mko438.py TREE_ROOT OUT_ROOT
Each mark is one line inserted after the opening brace of the named function (found by its signature's start, which
must occur once). Waits (a scoped span): KernelWaitSema, sem_wait / sem_reltimedwait_np / sem_timedwait, PthreadSemWait
/ PthreadSemTimedwait, KernelWaitEventFlag, PthreadMutexLock / PthreadMutexTimedlock, PthreadCondWait /
PthreadCondTimedwait, KernelWaitEqueue, KernelUsleep, KernelNanosleep, KernelSyncOnAddressWait / 8 / 16 / 32 / 64,
PthreadJoin, PthreadYield. Signals (the waker's tid for the object): KernelSignalSema, sem_post, PthreadSemPost,
KernelSetEventFlag, PthreadMutexUnlock, PthreadCondSignal / Broadcast / Signalto, KernelTriggerEvent,
KernelTriggerUserEvent, KernelSyncOnAddressWake. The flip: after videoOut's Bc5FpsCount() call.
"""
import hashlib
import os
import sys

TREE, OUT = sys.argv[1], sys.argv[2]
HERE = os.path.dirname(os.path.abspath(__file__))
PIN = {
    'src/kernel/semaphore.cpp': '35a449f0daaa3c83a2a76643176c336b',
    'src/kernel/eventFlag.cpp': 'f745bc8eaec5551a8214bf9b128ed8f6',
    'src/kernel/pthread.cpp': '65d198f128d3c086458ea495c640b9fa',
    'src/kernel/eventQueue.cpp': '3c0b776d6d11f5331c78a204c59fb6ca',
    'src/libs/libKernel.cpp': '3eb71c6cad5f1fc598dbb7fc1b773754',
    'src/graphics/presentation/videoOut.cpp': '6785425ea472815fc85713cec6cc5630',
}
W, S = 'BC5_O438_WAIT', 'BC5_O438_SIGNAL'
MARKS = {
    'src/kernel/semaphore.cpp': [
        ('int KYTY_SYSV_ABI KernelWaitSema(KernelSema sem,', W + '(kWaitSema, sem);'),
        ('int KYTY_SYSV_ABI KernelSignalSema(KernelSema sem,', S + '(sem);'),
        ('int KYTY_SYSV_ABI sem_wait(void* sem)', W + '(kPosixSemWait, sem);'),
        ('int KYTY_SYSV_ABI sem_reltimedwait_np(void* sem,', W + '(kPosixSemWait, sem);'),
        ('int KYTY_SYSV_ABI sem_timedwait(void* sem,', W + '(kPosixSemWait, sem);'),
        ('int KYTY_SYSV_ABI sem_post(void* sem)', S + '(sem);'),
        ('int KYTY_SYSV_ABI PthreadSemWait(void* sem)', W + '(kPthreadSemWait, sem);'),
        ('int KYTY_SYSV_ABI PthreadSemTimedwait(void* sem,', W + '(kPthreadSemWait, sem);'),
        ('int KYTY_SYSV_ABI PthreadSemPost(void* sem)', S + '(sem);'),
    ],
    'src/kernel/eventFlag.cpp': [
        ('int KYTY_SYSV_ABI KernelWaitEventFlag(KernelEventFlag ef,', W + '(kWaitEventFlag, ef);'),
        ('int KYTY_SYSV_ABI KernelSetEventFlag(KernelEventFlag ef,', S + '(ef);'),
    ],
    'src/kernel/pthread.cpp': [
        ('int KYTY_SYSV_ABI PthreadMutexLock(PthreadMutex* mutex)', W + '(kMutexLock, mutex);'),
        ('int KYTY_SYSV_ABI PthreadMutexTimedlock(PthreadMutex* mutex,', W + '(kMutexLock, mutex);'),
        ('int KYTY_SYSV_ABI PthreadMutexUnlock(PthreadMutex* mutex)', S + '(mutex);'),
        ('int KYTY_SYSV_ABI PthreadCondBroadcast(PthreadCond* cond)', S + '(cond);'),
        ('int KYTY_SYSV_ABI PthreadCondSignal(PthreadCond* cond)', S + '(cond);'),
        ('int KYTY_SYSV_ABI PthreadCondSignalto(PthreadCond* cond,', S + '(cond);'),
        ('int KYTY_SYSV_ABI PthreadCondTimedwait(PthreadCond* cond,', W + '(kCondWait, cond);'),
        ('int KYTY_SYSV_ABI PthreadCondWait(PthreadCond* cond,', W + '(kCondWait, cond);'),
        ('int KYTY_SYSV_ABI PthreadJoin(Pthread thread,', W + '(kJoin, nullptr);'),
        ('void KYTY_SYSV_ABI PthreadYield()', W + '(kYield, nullptr);'),
        ('int KYTY_SYSV_ABI KernelUsleep(KernelUseconds microseconds)', W + '(kUsleep, nullptr);'),
        ('int KYTY_SYSV_ABI KernelNanosleep(const KernelTimespec* rqtp,', W + '(kNanosleep, nullptr);'),
    ],
    'src/kernel/eventQueue.cpp': [
        ('int KYTY_SYSV_ABI KernelTriggerEvent(KernelEqueue eq,', S + '(eq);'),
        ('int KYTY_SYSV_ABI KernelWaitEqueue(KernelEqueue eq,', W + '(kWaitEqueue, eq);'),
        ('int KYTY_SYSV_ABI KernelTriggerUserEvent(KernelEqueue eq,', S + '(eq);'),
    ],
    'src/libs/libKernel.cpp': [
        ('int KYTY_SYSV_ABI KernelSyncOnAddressWait(volatile uint32_t* address,', W + '(kSyncOnAddressWait, address);'),
        ('int KYTY_SYSV_ABI KernelSyncOnAddressWait32(volatile uint32_t* address,', W + '(kSyncOnAddressWait, address);'),
        ('int KYTY_SYSV_ABI KernelSyncOnAddressWait64(volatile uint64_t* address,', W + '(kSyncOnAddressWait, address);'),
        ('int KYTY_SYSV_ABI KernelSyncOnAddressWake(volatile void* address,', S + '(address);'),
        ('int KYTY_SYSV_ABI KernelSyncOnAddressWait8(volatile uint8_t* address,', W + '(kSyncOnAddressWait, address);'),
        ('int KYTY_SYSV_ABI KernelSyncOnAddressWait16(volatile uint16_t* address,', W + '(kSyncOnAddressWait, address);'),
    ],
}
for rel, want in PIN.items():
    b = open(os.path.join(TREE, rel), 'rb').read()
    got = hashlib.md5(b).hexdigest()
    assert got == want, f'{rel}: {got}, not {want}'
    s = b.decode('utf-8')
    assert '\r' not in s
    # the header, after the file's first quoted include
    i = s.index('#include "')
    j = s.index('\n', i) + 1
    s = s[:j] + '#include "kernel/o438.hpp" // exp 0438 (tag o438): records, normal build only, off unless BC5_0438_OUTSIDE=1\n' + s[j:]
    n = 0
    for sig, mark in MARKS.get(rel, []):
        assert s.count(sig) == 1, f'{rel}: {s.count(sig)} x {sig}'
        a = s.index(sig)
        brace = s.index('{\n', a)
        assert ';' not in s[a:brace], f'{rel}: a declaration, not the definition: {sig}'
        s = s[:brace + 2] + '\t' + mark + ' // exp 0438 (tag o438)\n' + s[brace + 2:]
        n += 1
    if rel.endswith('videoOut.cpp'):
        f = '\tBc5FpsCount(); // experiment 0172\n'
        assert s.count(f) == 1
        s = s.replace(f, f + '\tBC5_O438_FLIP(); // exp 0438 (tag o438)\n')
        n += 1
    out = os.path.join(OUT, rel)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    data = s.encode('utf-8')
    open(out, 'wb').write(data)
    print(f'{rel}: {n} marks, {hashlib.md5(data).hexdigest()}')
h = open(os.path.join(HERE, 'o438.hpp'), 'rb').read()
os.makedirs(os.path.join(OUT, 'src/kernel'), exist_ok=True)
open(os.path.join(OUT, 'src/kernel/o438.hpp'), 'wb').write(h)
print('src/kernel/o438.hpp', hashlib.md5(h).hexdigest())
