#!/usr/bin/env python3
r"""BC5 experiment 0419, phase 2 (after the night series; base: the test build T, patch fec3d656): the first batch of
cuts, prepared on the laptop on 2026-11-14 and NOT compiled. Each step is independent of the others and touches its own
lines, so that a step whose compile fails on the box can be left out and the rest built in the same round:
    mkp2_0419.py <tree root>                 all steps
    mkp2_0419.py <tree root> bo eop delay    only the named ones
Steps (the two deletions are the top session's verdicts of 2026-11-14):
  bo     BC5_DIRECT_MAX_BO_MIB deleted with its four lines (the largest import is the module's limit, as when unset)
  eop    BC5_R3_SUBMIT_EOP_EVENT: the read goes, `submit_eop` stays false (its code is cut with the R3 block later)
  delay  KYTY_BC5_LOAD_DELAY (option gone since E): `load_stat::delay` becomes an empty inline, `delay_ns_of` goes
  flip   KYTY_BC5_MIN_FLIP_RATE (option gone since E): `Bc5MinFlipRate` goes; the flip interval is the title's own rate,
         still never below 0
  mem    KYTY_BC5_MEMORY_FROM_PARAM (option gone since E): the alternative sizing goes (its constants, three functions,
         the saved "today's total"); the init line keeps its text with "off"
Every edit must match exactly once."""
import os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ed0419g import File

root = sys.argv[1]
steps = sys.argv[2:] or ["bo", "eop", "delay", "flip", "mem"]
P = lambda *a: os.path.join(root, "src", *a)

if "bo" in steps or "eop" in steps:
    f = File(P("libs", "bc5LleAgc.cpp"))
    if "bo" in steps:
        f.cut('\tif (const char* e = std::getenv("BC5_DIRECT_MAX_BO_MIB"); e != nullptr && e[0] != 0) {',
              'the largest import is %lu MiB\\n", e, mb);\n\t}\n')
        f.gone("BC5_DIRECT_MAX_BO_MIB")
    if "eop" in steps:
        f.sub('\t\tv.submit_eop = take("BC5_R3_SUBMIT_EOP_EVENT");\n',
              "\t\tv.submit_eop = false; /* exp 0419: option removed (the walk never reaches its path) */\n")
        f.gone('"BC5_R3_SUBMIT_EOP_EVENT"')
    f.save()

if "delay" in steps:
    f = File(P("bc5", "load_stat.hpp"))
    f.cut("// The busy delay of KYTY_BC5_LOAD_DELAY=<cause>:<us> for cause c, 0 when none. At most 100,000 us.\n",
          "\twhile (now_ns() - t0 < ns) cpu_relax();\n}\n",
          "// exp 0419 phase 2: KYTY_BC5_LOAD_DELAY is gone (a diagnostic of exp 0415); the call sites stay and cost nothing.\n"
          "inline void delay(unsigned) {}\n")
    f.gone("delay_ns_of")
    f.save()

if "flip" in steps:
    f = File(P("graphics", "presentation", "videoOut.cpp"))
    f.cut("// BC5 (experiment 0183): KYTY_BC5_MIN_FLIP_RATE=<0..2> is the least flip rate in force whatever\n",
          "\t}();\n\treturn v;\n}\n\n")
    f.sub("\tconst int interval = std::max(cfg.flip_rate, Bc5MinFlipRate()) + 1;\n",
          "\tconst int interval = std::max(cfg.flip_rate, 0) + 1; // exp 0419 phase 2: KYTY_BC5_MIN_FLIP_RATE is gone\n")
    f.gone("Bc5MinFlipRate")
    f.save()

if "mem" in steps:
    f = File(P("kernel", "memory.cpp"))
    f.cut("// Experiment 0401 series e: direct and flexible memory sized from param.json, after KytyPS5 09753bf",
          "\treturn (BC5_GUEST_MEMORY_BUDGET - BC5_RESERVED_CACHE_SIZE - overhead) & ~(0x4000ull - 1ull);\n}\n\n")
    f.sub("\t\t\tg_bc5_today_total = target; // experiment 0401 series e\n"
          "\t\t\tif (Bc5MemoryFromParamOn()) {\n\t\t\t\ttarget = Bc5MemoryFromParamTotal();\n\t\t\t}\n", "")
    f.sub("\t\tconst bool         on     = Bc5MemoryFromParamOn();\n", "")
    f.sub('\t\t             on ? "on" : "off", total / mib,', '\t\t             "off", total / mib,')
    f.cut("\t\tif (on) {\n\t\t\tstd::fprintf(stderr, \"; today's total would be", "\t\t}\n")
    f.gone("Bc5MemoryFromParam", "g_bc5_today_total", "BC5_GUEST_MEMORY_BUDGET", "BC5_RESERVED_CACHE_SIZE", "BC5_INCLUDED_TABLE_MEMORY", "Bc5TableOverhead")
    f.save()
