"""Exp 0413 (PRIVATE diagnostic, never for a shared build): at a guest access violation, with BC5_0413_CRASH_WALK=1, log
the guest frame chain (rbp, return address) and the 64 bytes before each return address (the call site).
Input: src/loader/runtimeLinker.cpp of the a2ab53c7 tree (md5 aba94c24). usage: mkwalk0413.py <in> <out>"""
import hashlib
import sys

s = open(sys.argv[1], "rb").read()
assert hashlib.md5(s).hexdigest().startswith("aba94c24"), hashlib.md5(s).hexdigest()
A = b"\t\tif (info->exception_address == 0x000000090064364e &&\n"
assert s.count(A) == 1
W = (b"\t\t// BC5 exp 0413 (private diagnostic, BC5_0413_CRASH_WALK=1): the guest frame chain and each call site's bytes.\n"
     b"\t\tif (const char* w0413 = std::getenv(\"BC5_0413_CRASH_WALK\"); w0413 != nullptr && w0413[0] == '1') {\n"
     b"\t\t\tuint64_t fp = info->rbp;\n"
     b"\t\t\tfor (int k = 0; k < 24 && IsDumpableRange(fp, 16); k++) {\n"
     b"\t\t\t\tconst auto*    fr  = reinterpret_cast<const uint64_t*>(fp);\n"
     b"\t\t\t\tconst uint64_t ret = fr[1];\n"
     b"\t\t\t\tBc5CrashLog(\"0413 frame %d: rbp 0x%016\" PRIx64 \" ret 0x%016\" PRIx64 \"\\n\", k, fp, ret);\n"
     b"\t\t\t\tif (ret >= 48 && IsDumpableRange(ret - 48, 64)) {\n"
     b"\t\t\t\t\tconst auto* c = reinterpret_cast<const uint8_t*>(ret - 48);\n"
     b"\t\t\t\t\tchar        line[64 * 3 + 1];\n"
     b"\t\t\t\t\tfor (int i = 0; i < 64; i++) snprintf(line + i * 3, 4, \"%02x \", c[i]);\n"
     b"\t\t\t\t\tBc5CrashLog(\"0413 frame %d code at ret-48: %s\\n\", k, line);\n"
     b"\t\t\t\t}\n"
     b"\t\t\t\tif (fr[0] <= fp) break;\n"
     b"\t\t\t\tfp = fr[0];\n"
     b"\t\t\t}\n"
     b"\t\t\tif (IsDumpableRange(info->exception_address - 0x60, 0x80)) {\n"
     b"\t\t\t\tconst auto* c = reinterpret_cast<const uint8_t*>(info->exception_address - 0x60);\n"
     b"\t\t\t\tfor (int r = 0; r < 4; r++) {\n"
     b"\t\t\t\t\tchar line[32 * 3 + 1];\n"
     b"\t\t\t\t\tfor (int i = 0; i < 32; i++) snprintf(line + i * 3, 4, \"%02x \", c[r * 32 + i]);\n"
     b"\t\t\t\t\tBc5CrashLog(\"0413 fault-0x60+%02x: %s\\n\", r * 32, line);\n"
     b"\t\t\t\t}\n"
     b"\t\t\t}\n"
     b"\t\t}\n")
s = s.replace(A, W + A)
open(sys.argv[2], "wb").write(s)
print(hashlib.md5(s).hexdigest())
