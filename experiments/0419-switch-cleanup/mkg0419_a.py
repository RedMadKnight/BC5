#!/usr/bin/env python3
"""BC5 experiment 0419, candidate G, step a: exp 0416's two ports that measured as "does nothing" go with their code
(approved by the maintainer on 2026-11-13): KYTY_BC5_SEMA_TARGETED_WAKE (kernel/semaphore.cpp) and
KYTY_BC5_EVENT_COALESCE_SAME (graphics/host_gpu/renderer/sync.cpp). What stays is the code as it ran with the word
unset: every waiter on the semaphore's shared condition variable, a broadcast on each signal; every trigger pushed.
usage: mkg0419_a.py <src dir>"""
import sys
from ed0419g import File

src = sys.argv[1]

f = File(src + "/kernel/semaphore.cpp")
f.sub("\t\tCommon::CondVar* own_cond = nullptr; // BC5 KYTY_BC5_SEMA_TARGETED_WAKE: this waiter's own condition variable\n", "")
f.cut("// BC5 (exp 0414's list, item 5; the idea is KytyPS5 a0268f1 ", "\treturn on;\n}\n\n")
f.sub("\t\t\tif (waiter->own_cond != nullptr) {\n\t\t\t\twaiter->own_cond->Signal();\n\t\t\t}\n", "", n=3)
f.sub("\tif (!Bc5SemaTargetedWake()) {\n\t\tm_cond_var.SignalAll();\n\t}\n", "\tm_cond_var.SignalAll();\n")
f.sub("\tCommon::CondVar* cond = &m_cond_var;\n"
      "\tif (Bc5SemaTargetedWake()) {\n"
      "\t\tstatic thread_local Common::CondVar own; // a thread waits on one semaphore at a time\n"
      "\t\twaiter.own_cond = &own;\n"
      "\t\tcond            = &own;\n"
      "\t}\n", "")
f.sub("\t\t\tcond->WaitFor(&m_mutex, SIGNAL_APC_POLL_MICROS);\n", "\t\t\tm_cond_var.WaitFor(&m_mutex, SIGNAL_APC_POLL_MICROS);\n")
f.sub("\t\t\tcond->WaitFor(&m_mutex, micros - elapsed);\n", "\t\t\tm_cond_var.WaitFor(&m_mutex, micros - elapsed);\n")
f.gone("TARGETED_WAKE", "own_cond", "Bc5SemaTargetedWake", "cond->")
f.save()

f = File(src + "/graphics/host_gpu/renderer/sync.cpp")
f.cut("// BC5 (exp 0414's list, item 1b; the idea is KytyPS5 c86d31b ", "\treturn on;\n}\n\n")
f.sub("\t\tif (Bc5EopCoalesceSame()) {\n"
      "\t\t\tauto& newest = event->pending_events.empty() ? event->event : event->pending_events.back();\n"
      "\t\t\tif (newest.data == triggered_event.data) {\n"
      "\t\t\t\tnewest.fflags++;\n"
      "\t\t\t\treturn;\n"
      "\t\t\t}\n"
      "\t\t}\n", "")
f.gone("COALESCE_SAME", "Bc5EopCoalesceSame")
f.save()
