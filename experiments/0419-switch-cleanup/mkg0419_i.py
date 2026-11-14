#!/usr/bin/env python3
"""BC5 experiment 0419, step i (the test build T): the guardian's verdicts of 2026-11-14 (exp 0412 README section 95,
relayed by the top session) on the last three second-title words of its own:
  BC5_DIRECT_LAZY_RELEASE=30,eager + BC5_GUARD_SPLIT=1  -> always on, no option (turning them off costs 85-95 MiB)
  BC5_GUARD_FORGET=10                                   -> out (its effect is below the threshold)
Done in src/bc5/switch_defaults.hpp alone, so that no code path of either title changes blind:
  - the first two stay rows of the title they were measured on (the second title), but FORCED: the word is taken out
    of the environment at process start and the title's row sets it with overwrite. Another title runs without them,
    as today (they were never general defaults);
  - FORGET's row is gone and the word is unset at process start (kIgnored): its reader finds nothing, the code behind
    it is dead and is cut in phase 2 with the compiler at hand.
usage: mkg0419_i.py <src/bc5/switch_defaults.hpp>"""
import sys
from ed0419g import File

f = File(sys.argv[1])
f.gone("kTitleForced")
f.sub('    {BC5_T2, "BC5_GUARD_FORGET", "10"},\n', "")
f.sub('    "KYTY_BC5_SWITCH_DEFAULTS",     // removed with this change: a control is a build of the older patch\n',
      '    "KYTY_BC5_SWITCH_DEFAULTS",     // removed with this change: a control is a build of the older patch\n'
      '    "BC5_GUARD_FORGET",             // exp 0412 section 95: its effect is below the threshold; code cut in phase 2\n')
f.sub("// Applies the rows of `title`; returns how many rows the title has",
      "// exp 0419 step i (exp 0412 section 95): title rows that are forced. The word is unset at process start, so the\n"
      "// environment never decides it, and the title's row sets it with overwrite.\n"
      'inline constexpr const char* kTitleForced[] = {"BC5_DIRECT_LAZY_RELEASE", "BC5_GUARD_SPLIT", nullptr};\n'
      "inline bool TitleForced(const char* name) {\n"
      "\tfor (const char* const* n = kTitleForced; *n != nullptr; n++) {\n"
      "\t\tif (std::strcmp(*n, name) == 0) return true;\n"
      "\t}\n"
      "\treturn false;\n"
      "}\n\n"
      "// Applies the rows of `title`; returns how many rows the title has")
f.sub("\t\tif (std::getenv(d->name) == nullptr) (*took)++;\n\t\tsetenv(d->name, d->value, 0);\n",
      "\t\tif (std::getenv(d->name) == nullptr) (*took)++;\n\t\tsetenv(d->name, d->value, TitleForced(d->name) ? 1 : 0);\n")
f.sub("\tfor (const char* const* n = kIgnored; *n != nullptr; n++) {\n\t\tunsetenv(*n);\n\t}\n",
      "\tfor (const char* const* n = kIgnored; *n != nullptr; n++) {\n\t\tunsetenv(*n);\n\t}\n"
      "\tfor (const char* const* n = kTitleForced; *n != nullptr; n++) {\n\t\tunsetenv(*n);\n\t}\n")
f.save()
