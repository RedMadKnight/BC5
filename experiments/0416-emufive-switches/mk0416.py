#!/usr/bin/env python3
"""BC5: two ideas of KytyPS5 (GPL-2.0; read in exp 0414 through EmuFive's pin 589bd14) written into our host as
default-off switches. Our own code; the two KytyPS5 commits are the source of the idea and are named in the comments.

  sync       src/graphics/host_gpu/renderer/sync.cpp (md5 06c1349c): KYTY_BC5_EVENT_COALESCE_SAME=1. An EOP trigger for
             an event that is still unread, whose data equals the newest unread entry's, only counts on that entry
             (fflags) instead of adding an entry (KytyPS5 c86d31b). A different data value queues as before, so no
             distinct value is lost; KYTY_BC5_EVENT_PENDING_CAP stays the bound behind it.
  semaphore  src/kernel/semaphore.cpp (md5 3aa9c8b4): KYTY_BC5_SEMA_TARGETED_WAKE=1. Each waiter of a kernel semaphore
             sleeps on its own condition variable and a signal wakes only the waiters it hands counts to (KytyPS5
             a0268f1), instead of broadcasting on the semaphore's one condition variable (F451's convoy, exp 0358).
usage: mk0416.py sync|semaphore <in> <out>"""
import hashlib
import sys

T = b"\t"


def one(s, a, b):
    assert s.count(a) == 1, a[:70]
    return s.replace(a, b)


def sync(s):
    assert hashlib.md5(s).hexdigest().startswith("06c1349c"), hashlib.md5(s).hexdigest()
    head = b"static void EopEventTriggerFunc(LibKernel::EventQueue::KernelEqueueEvent* event,\n"
    helper = (b"// BC5 (exp 0414's list, item 1b; the idea is KytyPS5 c86d31b \"coalesce repeated GPU interrupts with the same data\"):\n"
              b"// with KYTY_BC5_EVENT_COALESCE_SAME=1 a trigger for a still unread event whose data equals the newest unread entry's\n"
              b"// only counts on that entry. Unset, empty and \"0\" are off: the code below runs as before.\n"
              b"static bool Bc5EopCoalesceSame() {\n"
              b"\tstatic const bool on = [] {\n"
              b"\t\tconst char* e = std::getenv(\"KYTY_BC5_EVENT_COALESCE_SAME\");\n"
              b"\t\tconst bool  v = e != nullptr && e[0] != '\\0' && std::strcmp(e, \"0\") != 0;\n"
              b"\t\tif (v) {\n"
              b"\t\t\tstd::fprintf(stderr, \"[bc5] KYTY_BC5_EVENT_COALESCE_SAME on: a repeated EOP trigger with the same data counts on the newest unread entry\\n\");\n"
              b"\t\t}\n"
              b"\t\treturn v;\n"
              b"\t}();\n"
              b"\treturn on;\n"
              b"}\n\n")
    s = one(s, head, helper + head)
    a = (b"\tif (event->triggered) {\n"
         b"\t\tLibKernel::EventQueue::KernelEventPendingPush(event, triggered_event); // exp 0412 (tag ev412): KYTY_BC5_EVENT_PEN")
    b = (b"\tif (event->triggered) {\n"
         b"\t\tif (Bc5EopCoalesceSame()) {\n"
         b"\t\t\tauto& newest = event->pending_events.empty() ? event->event : event->pending_events.back();\n"
         b"\t\t\tif (newest.data == triggered_event.data) {\n"
         b"\t\t\t\tnewest.fflags++;\n"
         b"\t\t\t\treturn;\n"
         b"\t\t\t}\n"
         b"\t\t}\n"
         b"\t\tLibKernel::EventQueue::KernelEventPendingPush(event, triggered_event); // exp 0412 (tag ev412): KYTY_BC5_EVENT_PEN")
    s = one(s, a, b)
    for inc in (b"#include <cstdio>\n", b"#include <cstdlib>\n"):
        if inc not in s:
            s = one(s, b"#include <cstring>\n", inc + b"#include <cstring>\n")
    return s


def semaphore(s):
    assert hashlib.md5(s).hexdigest().startswith("3aa9c8b4"), hashlib.md5(s).hexdigest()
    # this unit has CRLF line ends throughout (826 of 826): edited as LF, written back as CRLF
    assert s.count(b"\r\n") == s.count(b"\n") == s.count(b"\r")
    s = s.replace(b"\r\n", b"\n")
    return semaphore_lf(s).replace(b"\n", b"\r\n")


def semaphore_lf(s):
    # the waiter knows its own condition variable (null: the semaphore's shared one)
    s = one(s, b"\t\tResult result     = Result::TimedOut;\n\t\tbool   ready      = false;\n\t};\n",
            b"\t\tResult result     = Result::TimedOut;\n\t\tbool   ready      = false;\n"
            b"\t\tCommon::CondVar* own_cond = nullptr; // BC5 KYTY_BC5_SEMA_TARGETED_WAKE: this waiter's own condition variable\n\t};\n")
    helper = (b"// BC5 (exp 0414's list, item 5; the idea is KytyPS5 a0268f1 \"a semaphore signal wakes only the waiters it hands counts\n"
              b"// to\"): with KYTY_BC5_SEMA_TARGETED_WAKE=1 each waiter sleeps on its own condition variable (one per thread) and is\n"
              b"// signalled when it is made ready; nothing is broadcast on the semaphore's shared one. Unset, empty and \"0\" are off.\n"
              b"static bool Bc5SemaTargetedWake() {\n"
              b"\tstatic const bool on = [] {\n"
              b"\t\tconst char* e = std::getenv(\"KYTY_BC5_SEMA_TARGETED_WAKE\");\n"
              b"\t\tconst bool  v = e != nullptr && e[0] != '\\0' && std::strcmp(e, \"0\") != 0;\n"
              b"\t\tif (v) {\n"
              b"\t\t\tstd::fprintf(stderr, \"[bc5] KYTY_BC5_SEMA_TARGETED_WAKE on: a semaphore signal wakes only the waiters it hands counts to\\n\");\n"
              b"\t\t}\n"
              b"\t\treturn v;\n"
              b"\t}();\n"
              b"\treturn on;\n"
              b"}\n\n")
    s = one(s, b"KernelSemaPrivate::~KernelSemaPrivate() {\n", helper + b"KernelSemaPrivate::~KernelSemaPrivate() {\n")
    # destructor and Cancel: every waiter made ready is signalled on its own variable
    for res in (b"Deleted", b"Canceled"):
        a = (b"\t\tif (!waiter->ready) {\n\t\t\twaiter->result = Result::" + res + b";\n\t\t\twaiter->ready  = true;\n\t\t}\n")
        b = (b"\t\tif (!waiter->ready) {\n\t\t\twaiter->result = Result::" + res + b";\n\t\t\twaiter->ready  = true;\n"
             b"\t\t\tif (waiter->own_cond != nullptr) {\n\t\t\t\twaiter->own_cond->Signal();\n\t\t\t}\n\t\t}\n")
        s = one(s, a, b)
    # Signal: no broadcast when the wake is targeted
    s = one(s, b"\tWakeWaiters();\n\n\tm_cond_var.SignalAll();\n",
            b"\tWakeWaiters();\n\n\tif (!Bc5SemaTargetedWake()) {\n\t\tm_cond_var.SignalAll();\n\t}\n")
    s = one(s, b"\t\t\tm_count -= waiter->need_count;\n\t\t\twaiter->result = Result::Ok;\n\t\t\twaiter->ready  = true;\n",
            b"\t\t\tm_count -= waiter->need_count;\n\t\t\twaiter->result = Result::Ok;\n\t\t\twaiter->ready  = true;\n"
            b"\t\t\tif (waiter->own_cond != nullptr) {\n\t\t\t\twaiter->own_cond->Signal();\n\t\t\t}\n")
    # Wait: sleep on the thread's own variable
    s = one(s, b"\twaiter.need_count = need_count;\n\tAddWaiter(&waiter);\n",
            b"\twaiter.need_count = need_count;\n"
            b"\tCommon::CondVar* cond = &m_cond_var;\n"
            b"\tif (Bc5SemaTargetedWake()) {\n"
            b"\t\tstatic thread_local Common::CondVar own; // a thread waits on one semaphore at a time\n"
            b"\t\twaiter.own_cond = &own;\n"
            b"\t\tcond            = &own;\n"
            b"\t}\n"
            b"\tAddWaiter(&waiter);\n")
    s = one(s, b"\t\tif (infinitely) {\n\t\t\tm_cond_var.WaitFor(&m_mutex, SIGNAL_APC_POLL_MICROS);\n\t\t} else {\n\t\t\tm_cond_var.WaitFor(&m_mutex, micros - elapsed);\n\t\t}\n\n\t\tm_mutex.Unlock();\n\t\tLibKernel::KernelDispatchPendingSignalForCurrentThread();",
            b"\t\tif (infinitely) {\n\t\t\tcond->WaitFor(&m_mutex, SIGNAL_APC_POLL_MICROS);\n\t\t} else {\n\t\t\tcond->WaitFor(&m_mutex, micros - elapsed);\n\t\t}\n\n\t\tm_mutex.Unlock();\n\t\tLibKernel::KernelDispatchPendingSignalForCurrentThread();")
    return s


if __name__ == "__main__":
    src = open(sys.argv[2], "rb").read()
    assert sys.argv[1] == "semaphore" or b"\r" not in src
    out = {"sync": sync, "semaphore": semaphore}[sys.argv[1]](src)
    open(sys.argv[3], "wb").write(out)
    print(hashlib.md5(out).hexdigest())
