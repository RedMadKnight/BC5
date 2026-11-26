#!/usr/bin/env python3
"""BC5 experiment 0419, candidate G, step b: exp 0415's three fix candidates that measured as "does nothing" lose their
code (their options went in E/F): KYTY_BC5_MUTEX_SPIN_US, KYTY_BC5_RING_SPIN_US, KYTY_BC5_TIMERSLACK_NS; and the
doorbell poll's period is the constant 200 us (KYTY_BC5_RING_POLL_US). The counter column "mutex_spin_won" stays in
KYTY_BC5_LOAD_STAT's table (always 0) so that the file's format does not change.
usage: mkg0419_b.py <src dir>"""
import sys
from ed0419g import File

src = sys.argv[1]

f = File(src + "/bc5/load_stat.hpp")
f.sub("// Experiment 0415 (tag ls415): where a load's wall-clock time goes. One counter table shared by every unit, three\n"
      "// knobs that change a latency so that its place on a load's critical path can be measured, and three candidate fixes.\n",
      "// Experiment 0415 (tag ls415): where a load's wall-clock time goes. One counter table shared by every unit and one\n"
      "// knob that adds a delay so that a cause's place on a load's critical path can be measured. The doorbell poll's\n"
      "// period is the constant 200 us; the three fix candidates (ring spin, timer slack, mutex spin) measured as no gain\n"
      "// and were removed with their code in exp 0419 (candidate G).\n")
f.cut("//   KYTY_BC5_RING_POLL_US=<n>     the doorbell poll's sleep", "(200 today; the long-idle sleep stays 5 times it).\n")
f.cut("//   KYTY_BC5_RING_SPIN_US=<n>     fix candidate:", "//                                 thread sleeps on its condition variable. Lock order and ownership rules unchanged.\n")
f.sub("\tkMutexSpinWon,   // ... taken inside the spin window (KYTY_BC5_MUTEX_SPIN_US)\n",
      "\tkMutexSpinWon,   // always 0 since exp 0419 (the spin is gone); kept for the file's columns\n")
f.cut("inline uint64_t ring_poll_us() {\n", "inline void apply_timer_slack() {\n#if defined(__linux__)\n"
      "\tconst uint64_t ns = 0; /* exp 0419: option removed */\n"
      "\tif (ns != 0) prctl(PR_SET_TIMERSLACK, static_cast<unsigned long>(ns), 0, 0, 0);\n#endif\n}\n",
      "inline constexpr uint64_t kRingPollUs = 200; // the doorbell poll's sleep after a pass; the long-idle sleep is 5 times it\n")
f.gone("RING_POLL_US", "RING_SPIN_US", "TIMERSLACK", "MUTEX_SPIN_US", "ring_spin_ns", "mutex_spin_ns", "ring_poll_us")
f.save()

f = File(src + "/kernel/pthread.cpp")
f.sub("\t// Experiment 0415 (ls415): the count of locks and of contended ones with their wait; and, with\n"
      "\t// KYTY_BC5_MUTEX_SPIN_US, a held mutex is tried again for that long before the thread sleeps on the condition\n"
      "\t// variable (the console's adaptive mutexes spin; here every contention was a sleep and a wake). mutex->m is\n"
      "\t// released between tries; the owner field is read and written under it as before. Not for a try (timeout 0).\n",
      "\t// Experiment 0415 (ls415): the count of locks and of contended ones with their wait.\n")
f.cut("\tif (ls_contended && (timeout_us == nullptr || *timeout_us != 0)) {\n"
      "\t\tif (const uint64_t spin = bc5::load_stat::mutex_spin_ns(); spin != 0) {\n",
      "\t\t\t\tif (bc5::load_stat::now_ns() - t0 >= spin) break;\n\t\t\t}\n\t\t}\n\t}\n")
f.gone("mutex_spin_ns", "kMutexSpinWon", "MUTEX_SPIN")
f.save()

f = File(src + "/libs/bc5LleAgc.cpp")
f.sub("\t\t// Experiment 0415 (ls415): the poll's period is KYTY_BC5_RING_POLL_US (200, the long-idle sleep 5 times it: today's\n"
      "\t\t// 200 and 1000); with KYTY_BC5_RING_SPIN_US the doorbells are read again without a sleep for that long after a pass\n"
      "\t\t// that served packets. The counters say how many passes found work right after a sleep.\n"
      "\t\tstatic bool     ls_slept      = false;\n"
      "\t\tstatic uint64_t ls_spin_until = 0;\n",
      "\t\t// Experiment 0415 (ls415): the poll's period is 200 us, the long-idle sleep 5 times it. The counters say how many\n"
      "\t\t// passes found work right after a sleep.\n"
      "\t\tstatic bool ls_slept = false;\n")
f.sub("\t\t\tif (bc5::load_stat::ring_spin_ns() != 0) ls_spin_until = bc5::load_stat::now_ns() + bc5::load_stat::ring_spin_ns();\n", "")
f.sub("\t\tif (ls_spin_until != 0 && bc5::load_stat::now_ns() < ls_spin_until) {\n"
      "\t\t\tls_slept = false;\n"
      "\t\t\tfor (int k = 0; k < 16; k++) bc5::load_stat::cpu_relax();\n"
      "\t\t\tcontinue;\n"
      "\t\t}\n"
      "\t\tls_spin_until = 0;\n"
      "\t\tls_slept      = true;\n"
      "\t\tstd::this_thread::sleep_for(std::chrono::microseconds(idle_ticks > 1000 ? bc5::load_stat::ring_poll_us() * 5 : bc5::load_stat::ring_poll_us()));\n",
      "\t\tls_slept = true;\n"
      "\t\tstd::this_thread::sleep_for(std::chrono::microseconds(idle_ticks > 1000 ? bc5::load_stat::kRingPollUs * 5 : bc5::load_stat::kRingPollUs));\n")
f.gone("ring_spin_ns", "ring_poll_us", "ls_spin_until")
f.save()

f = File(src + "/main.cpp")
f.sub("\tbc5::load_stat::apply_timer_slack(); // experiment 0415 (ls415): KYTY_BC5_TIMERSLACK_NS, before any thread exists\n", "")
f.gone("apply_timer_slack")
f.save()
