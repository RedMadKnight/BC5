#!/usr/bin/env python3
"""BC5 experiment 0419, candidate G, step f: the backend (backend/src/direct.cpp, exp 0412's form-6 file, md5 28100ce5).
The four hang-hunt words of exp 0380 that the records themselves discard lose their option (FIRST PHASE: the reads go,
the fields keep their defaults, the code in indirect_check stays until it is cut with its Catch2 tests):
  BC5_DIRECT_GPU_CHECK_ZERO   F548: "Not built on the box, not run on the GPU"; its hypothesis neither supported nor refuted
  BC5_DIRECT_GPU_CHECK_YZ     F556: "would not have caught 12:12"
  BC5_DIRECT_FORCE_START_000  F564: the class hung again with it on
  BC5_DIRECT_ARGS_COPY        F568: "The copy alone must not be used"
NOT touched here: BC5_DIRECT_ARGS_WB, _ARGS_FLUSH, _ARGS_FLUSH_DRAWS (and in the unit _FL_SERIAL, _FL_VGT_FLUSH): fix
candidates for hang classes that are OPEN in HANDOFF (F403, F813) and that never had their run; the maintainer's
"usunac z kodem" was given on a plan that called those classes gone (undecided-plan.md, the correction). With `all` as
the second argument they go too (the second phase of the same decision, once he has confirmed it knowing that).
usage: mkg0419_f.py <direct.cpp> [all]"""
import sys
from ed0419g import File

f = File(sys.argv[1])
allw = len(sys.argv) > 2 and sys.argv[2] == "all"
f.cut('    if (const char *e = std::getenv("BC5_DIRECT_GPU_CHECK_ZERO");', "    }\n")
f.cut('    if (const char *e = std::getenv("BC5_DIRECT_ARGS_COPY");', "    }\n")
f.cut('    if (indirect_check::parse_yz_limit(std::getenv("BC5_DIRECT_GPU_CHECK_YZ"), d->impl_->yz)) {', "    }\n")
f.cut('    if (const char *e = std::getenv("BC5_DIRECT_FORCE_START_000");', "    }\n")
f.gone('getenv("BC5_DIRECT_GPU_CHECK_ZERO")', 'getenv("BC5_DIRECT_ARGS_COPY")', 'getenv("BC5_DIRECT_GPU_CHECK_YZ")', 'getenv("BC5_DIRECT_FORCE_START_000")')
if allw:
    f.cut('    if (const char *e = std::getenv("BC5_DIRECT_ARGS_WB");', "    }\n")
    f.cut('    if (const char *e = std::getenv("BC5_DIRECT_ARGS_FLUSH");', "    }\n")
    f.cut('    if (const char *e = std::getenv("BC5_DIRECT_ARGS_FLUSH_DRAWS");', "    }\n")
    f.gone('getenv("BC5_DIRECT_ARGS_WB")', 'getenv("BC5_DIRECT_ARGS_FLUSH")', 'getenv("BC5_DIRECT_ARGS_FLUSH_DRAWS")')
f.save()
