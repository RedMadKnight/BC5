"""Exp 0413: re-exec the binary's real path (readlink of /proc/self/exe), so the process keeps its name kyty_emulator."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import defaults as d  # noqa: E402

TREE, REPO, WORK = sys.argv[1], sys.argv[2], sys.argv[3]
d.TREE, d.REPO, d.WORK = TREE, REPO, WORK
d.PATCH = os.path.join(REPO, "backend", "kytyplus-patches", "0001-bc5-lle-agc.patch")
H = os.path.join(TREE, "src", "bc5", "switch_defaults.hpp")
s = open(H, "rb").read().decode()
OLD = '\texecve("/proc/self/exe", argv.data(), envp.data());\n'
NEW = ('\t// The real path, not /proc/self/exe: exec through that link would name the process "exe", and every\n'
       '\t// pgrep \'^kyty_emulator\' guard on the box would stop seeing it (exp 0413 run p2def).\n'
       '\tchar self[4096];\n'
       '\tconst ssize_t n = readlink("/proc/self/exe", self, sizeof(self) - 1);\n'
       '\tif (n <= 0) {\n'
       '\t\tstd::fprintf(stderr, "[bc5] switch defaults: no /proc/self/exe, going on without them\\n");\n'
       '\t\treturn;\n'
       '\t}\n'
       '\tself[n] = 0;\n'
       '\texecve(self, argv.data(), envp.data());\n')
assert s.count(OLD) == 1
s = s.replace(OLD, NEW)
s = s.replace("// /proc/self/exe again, once,", "// its own binary (the real path of /proc/self/exe) again, once,")
open(H, "wb").write(s.encode())
d.commit("int(0413): the defaults' re-exec runs the binary's real path, so the process keeps the name kyty_emulator\n\n"
         "exec through /proc/self/exe named the process \"exe\"; run p2def's harness then saw no emulator, and every\n"
         "pgrep '^kyty_emulator' guard on the box would miss it. readlink(/proc/self/exe) gives the path to exec.")
print("committed")
