import hashlib, sys
s = open(sys.argv[1], "rb").read()
def rep(a, b, n=1):
    global s
    assert s.count(a) == n, (a[:50], s.count(a))
    s = s.replace(a, b)
rep(b"static Thr0413          g_thr0413[256];\n", b"static Thr0413*         g_thr0413 = nullptr; // mapped at the fault: no static data\n")
rep(b"\tint n = 0;\n\tchar comm[256][32];\n\tchar sysc[256][160];\n\tchar stat[256][64];\n",
    b"\tint n = 0;\n"
    b"\tvoid* m0413 = mmap(nullptr, 1 << 20, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);\n"
    b"\tif (m0413 == MAP_FAILED) return;\n"
    b"\tg_thr0413 = static_cast<Thr0413*>(m0413);\n"
    b"\tauto* comm = reinterpret_cast<char (*)[32]>(static_cast<char*>(m0413) + (256 << 10));\n"
    b"\tauto* sysc = reinterpret_cast<char (*)[160]>(static_cast<char*>(m0413) + (384 << 10));\n"
    b"\tauto* stat = reinterpret_cast<char (*)[64]>(static_cast<char*>(m0413) + (512 << 10));\n")
rep(b"\t\tThr0413ReadFile(path, comm[n], sizeof(comm[n]));\n", b"\t\tThr0413ReadFile(path, comm[n], 32);\n")
rep(b"\t\tThr0413ReadFile(path, sysc[n], sizeof(sysc[n]));\n", b"\t\tThr0413ReadFile(path, sysc[n], 160);\n")
rep(b"\t\tstd::snprintf(stat[n], sizeof(stat[n]), ", b"\t\tstd::snprintf(stat[n], 64, ")
rep(b"#include <sys/syscall.h>\n", b"#include <sys/mman.h>\n#include <sys/syscall.h>\n")
open(sys.argv[2], "wb").write(s)
print(hashlib.md5(s).hexdigest())
