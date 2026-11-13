#!/usr/bin/env python3
"""BC5 experiment 0419, step 2: the launcher-only words move into the code.
  kDefaults gets the two words BOTH titles run with every day: BC5_DIRECT_CHAIN=2 (both launchers) and
  BC5_GC_MODE=direct (bc5-run.env, read by both launchers).
  A table per title id (title_defaults.inc) gets the second title's 45 constant words of play-pkg.sh 47426d8e; the
  title id is read at process start from the game directory's sce_sys/param.json (the --game argument).
Edits src/bc5/switch_defaults.hpp of candidate B's tree (md5 2f1316c6) in place.
usage: mkdefs0419.py <tree root> <title_defaults.inc>"""
import hashlib
import sys

root, inc = sys.argv[1:3]
p = root + "/src/bc5/switch_defaults.hpp"
s = open(p, encoding="utf-8", newline="").read()
t = open(inc, encoding="utf-8", newline="").read().replace("\r", "")
assert "\r" not in s and "exp 0419" not in s
assert hashlib.md5(s.encode()).hexdigest()[:8] == "2f1316c6", hashlib.md5(s.encode()).hexdigest()


def once(old, new):
    global s
    assert s.count(old) == 1, (old[:60], s.count(old))
    s = s.replace(old, new)


once("#include <cstdlib>\n#include <cstring>\n", "#include <cstdio>\n#include <cstdlib>\n#include <cstring>\n#include <string>\n")
once('    // B16: quiet journal and inherit-map caps\n    {"BC5_DIRECT_JOURNAL_QUIET", "1"},\n    {nullptr, nullptr}};\n',
     '    // B16: quiet journal and inherit-map caps\n    {"BC5_DIRECT_JOURNAL_QUIET", "1"},\n'
     '    // exp 0419: the two words both titles run with every day, until now only through a launcher or bc5-run.env\n'
     '    {"BC5_DIRECT_CHAIN", "2"}, // F224\n'
     '    {"BC5_GC_MODE", "direct"},\n'
     '    {nullptr, nullptr}};\n')
once("inline void Apply() {\n", t + "\ninline void Apply() {\n")
once("\tfor (const Default* d = kDefaults; d->name != nullptr; d++) {\n\t\tsetenv(d->name, d->value, 0);\n\t}\n}\n",
     "\tfor (const Default* d = kDefaults; d->name != nullptr; d++) {\n\t\tsetenv(d->name, d->value, 0);\n\t}\n"
     "\t// exp 0419: the title's own rows\n"
     '\tconst char* per = std::getenv("KYTY_BC5_TITLE_DEFAULTS");\n'
     '\tif (per != nullptr && std::strcmp(per, "0") == 0) return;\n'
     "\tconst std::string title = DetectTitle();\n"
     "\tint               took  = 0;\n"
     "\tconst int         rows  = title.empty() ? 0 : ApplyTitle(title, &took);\n"
     "\tif (rows != 0) {\n"
     '\t\tstd::fprintf(stderr, "[bc5] exp 0419: title %s: %d title defaults, %d taken, %d already set in the environment\\n", title.c_str(), rows, took,\n'
     "\t\t             rows - took);\n"
     "\t}\n}\n")
open(p, "w", encoding="utf-8", newline="\n").write(s)
print("switch_defaults.hpp -> %s" % hashlib.md5(s.encode()).hexdigest()[:8])
