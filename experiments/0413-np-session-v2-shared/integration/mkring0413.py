"""Exp 0413 (PRIVATE diagnostic, never for a shared build): a static ring of the last 256 host library calls that pass
PRINT_NAME() (function name and thread), printed by the crash walk. No heap use, so the start's heap layout is untouched.
usage: mkring0413.py <libs.h in> <libs.h out> <runtimeLinker walk4 in> <runtimeLinker out>"""
import hashlib
import sys

h = open(sys.argv[1], "rb").read()
nl = b"\r\n" if b"\r\n" in h else b"\n"
A = b"#define PRINT_NAME()                                                                               \\" + nl + \
    b"\tif (PRINT_NAME_ENABLED) {                                                                      \\" + nl
assert h.count(A) == 1, h.count(A)
RING = (b"// exp 0413 private diagnostic: the last 256 PRINT_NAME() calls (name, thread), read by the crash walk." + nl +
        b"#include <atomic>" + nl + b"#include <pthread.h>" + nl +
        b"inline std::atomic<unsigned> g_bc5_ring0413_n {0};" + nl +
        b"inline const char*           g_bc5_ring0413_name[256];" + nl +
        b"inline unsigned long         g_bc5_ring0413_thread[256];" + nl +
        b"inline bool Bc5Ring0413(const char* name) {" + nl +
        b"\tconst unsigned i           = g_bc5_ring0413_n.fetch_add(1) & 255u;" + nl +
        b"\tg_bc5_ring0413_name[i]   = name;" + nl +
        b"\tg_bc5_ring0413_thread[i] = static_cast<unsigned long>(pthread_self());" + nl +
        b"\treturn true;" + nl + b"}" + nl + nl)
marker = b"// NOLINTNEXTLINE(cppcoreguidelines-macro-usage)" + nl + A
assert h.count(marker) == 1
NEWA = b"#define PRINT_NAME()                                                                               \\" + nl + \
       b"\tif (Bc5Ring0413(__func__) && PRINT_NAME_ENABLED) {                                             \\" + nl
h = h.replace(marker, RING + b"// NOLINTNEXTLINE(cppcoreguidelines-macro-usage)" + nl + NEWA)
open(sys.argv[2], "wb").write(h)

s = open(sys.argv[3], "rb").read()
assert hashlib.md5(s).hexdigest().startswith("08f8fd63"), hashlib.md5(s).hexdigest()
B = b"\t\t\tif (IsDumpableRange(info->exception_address - 0x60, 0x80)) {\n"
assert s.count(B) == 1
W = (b"\t\t\t{\n"
     b"\t\t\t\tconst unsigned      n0413  = g_bc5_ring0413_n.load();\n"
     b"\t\t\t\tconst unsigned long me0413 = static_cast<unsigned long>(pthread_self());\n"
     b"\t\t\t\tBc5CrashLog(\"0413 ring: %u calls so far, the faulting thread is %lx\\n\", n0413, me0413);\n"
     b"\t\t\t\tfor (unsigned k = n0413 > 200 ? n0413 - 200 : 0; k < n0413; k++) {\n"
     b"\t\t\t\t\tconst char* nm = g_bc5_ring0413_name[k & 255u];\n"
     b"\t\t\t\t\tBc5CrashLog(\"0413 ring %u: %s%s (thread %lx)\\n\", k, g_bc5_ring0413_thread[k & 255u] == me0413 ? \"* \" : \"  \", nm != nullptr ? nm : \"?\",\n"
     b"\t\t\t\t\t            g_bc5_ring0413_thread[k & 255u]);\n"
     b"\t\t\t\t}\n"
     b"\t\t\t}\n")
s = s.replace(B, W + B)
if b'#include "libs/libs.h"' not in s:
    inc = b'#include "loader/runtimeLinker.h"\n'
    assert s.count(inc) == 1, "no anchor include"
    s = s.replace(inc, inc + b'#include "libs/libs.h" // exp 0413 ring\n')
open(sys.argv[4], "wb").write(s)
print(hashlib.md5(h).hexdigest(), hashlib.md5(s).hexdigest())
