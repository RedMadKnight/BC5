#!/usr/bin/env python3
"""BC5 experiment 0419, candidate G, step c: the three words that are dead on one ring go with their code
(launcher-words.md; the top session: "martwe trzy mozesz kasowac"): BC5_DIRECT_CROSS_RING_WAITS, BC5_DIRECT_RING_DEPS,
BC5_DIRECT_TWO_RING_WAIT_MS. Every job is on the GFX ring since exp 0342 (BC5_DIRECT_COMPUTE_RING is unset at process
start by F's kIgnored), so `two_rings` was always false and ring_will_satisfy's rings were always equal.
With the block goes hold_keep_wait (ADR 0013), which only that block called: nothing puts a condition into a held
chain any more, so its holder thread (hold_thread), hold_chain_held and the holder's mutex and condition variable go
too; hold_release and hold_stats are still called by the chain code (they find nothing held) and stay. The backend's set_ring_deps stays in direct.hpp (its default is 0).
usage: mkg0419_c.py <src dir>"""
import sys
from ed0419g import File

src = sys.argv[1]
f = File(src + "/libs/bc5LleAgc.cpp")
f.cut("// Experiment 0129 (ADR 0009): BC5_DIRECT_RING_DEPS orders the two rings through the kernel's\n", "\treturn 3;\n}\n")
f.sub("\tg_dev->set_ring_deps(ring_deps_env());\n", "")
f.sub("\t\tif (g_dev) g_dev->set_ring_deps(ring_deps_env());\n", "")
f.cut("// ADR 0009, waits steps 2 and 3 (BC5_DIRECT_CROSS_RING_WAITS; experiments only, maintainer present):\n",
      "\t\treturn std::strcmp(e, \"all\") == 0 ? 2 : 1;\n\t}();\n\treturn v;\n}\n\n")
f.sub("\tif (last->ring != ring && !(cross_ring_waits() == 2 || (cross_ring_waits() == 1 && ring != bc5::direct::kGfxRing))) return false;\n",
      "\tif (last->ring != ring) return false; // one ring since exp 0342: never taken (exp 0419, candidate G)\n")
f.cut("\t\t\t\t\t// Experiment 0132 (ADR 0009, BC5_DIRECT_CROSS_RING_WAITS=all with the compute ring): a wait given\n",
      "\t\t\t\t\t\t// not served: as before (given up below, after the usual limit)\n\t\t\t\t\t}\n")
f.cut("// Keeps a game-thread wait in the held chain: with a condition, unless the held chain writes its label itself.\n",
      "\tg_hold_cv.notify_one();\n\treturn true;\n}\n")
f.sub("static bool hold_chain_held() {\n\tChainSlot&      s = g_chain_tl;\n\tstd::lock_guard lk(s.mu);\n\treturn !s.hold.empty();\n}\nstatic void hold_thread();\n", "")
f.cut("// The holder: submits each held chain once its conditions are met (chain_submit's gate decides).\nstatic void hold_thread() {\n",
      "\t\tstd::unique_lock lk(g_hold_mu);\n\t\tg_hold_cv.wait_for(lk, std::chrono::milliseconds(50));\n\t}\n}\n")
f.sub("static std::mutex              g_hold_mu;\nstatic std::condition_variable g_hold_cv;\n", "")
f.cut("static void hold_stats(bool force) {\n", "\t\t\tstatic_cast<double>(g_hold_ns_max.load()) / 1e6, g_hold_inner.load());\n}\n")
f.sub("static std::atomic<uint64_t>   g_hold_n {0}, g_hold_writer {0}, g_hold_sat {0}, g_hold_lost {0}, g_hold_inner {0}, g_hold_ns_sum {0}, g_hold_ns_max {0};\n",
      "static std::atomic<uint64_t>   g_hold_writer {0}, g_hold_sat {0}, g_hold_lost {0}, g_hold_ns_sum {0}, g_hold_ns_max {0};\n")
f.gone("hold_stats", "g_hold_n ", "g_hold_n.", "g_hold_n+", "g_hold_inner")
f.gone("CROSS_RING_WAITS", "RING_DEPS", "TWO_RING_WAIT_MS", "cross_ring_waits", "ring_deps_env", "two_rings", "hold_keep_wait(", "hold_thread", "hold_chain_held", "g_hold_cv", "g_hold_mu")
f.save()

f = File(src + "/bc5/switch_defaults.hpp")
f.cut('    {BC5_T2, "BC5_DIRECT_CROSS_RING_WAITS", "all"},', "\n")
f.cut('    {BC5_T2, "BC5_DIRECT_RING_DEPS", "dcb"},', "\n")
f.cut('    {BC5_T2, "BC5_DIRECT_TWO_RING_WAIT_MS", "4"},', "\n")
f.save()
