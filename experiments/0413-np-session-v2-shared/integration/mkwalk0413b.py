"""Exp 0413 (PRIVATE diagnostic): mkwalk0413.py's crash walk plus the key and the table of ASTRO BOT's lookup at
eboot+0x29930a: frame 1's r14 (the key; saved by the faulting function at rsp+0x50) and rbx (the entry after the match;
saved by the wrapper at rsp+0x78). Prints the key string and the 24-byte entries from 12 before to 2 after, with the
strings their +0x08 and +0x18 fields point to. Input: mkwalk0413.py's output (md5 25a5caca). usage: mkwalk0413b.py <in> <out>"""
import hashlib
import sys

s = open(sys.argv[1], "rb").read()
assert hashlib.md5(s).hexdigest().startswith("25a5caca"), hashlib.md5(s).hexdigest()
A = b"\t\t\tif (IsDumpableRange(info->exception_address - 0x60, 0x80)) {\n"
assert s.count(A) == 1
W = (b"\t\t\tauto str0413 = [](uint64_t a) -> std::string {\n"
     b"\t\t\t\tstd::string out;\n"
     b"\t\t\t\tfor (uint64_t i = 0; i < 160 && IsDumpableRange(a + i, 1); i++) {\n"
     b"\t\t\t\t\tconst char ch = *reinterpret_cast<const char*>(a + i);\n"
     b"\t\t\t\t\tif (ch == 0) break;\n"
     b"\t\t\t\t\tout += (ch >= 32 && ch < 127) ? ch : '?';\n"
     b"\t\t\t\t}\n"
     b"\t\t\t\treturn out;\n"
     b"\t\t\t};\n"
     b"\t\t\tif (IsDumpableRange(info->rsp, 0x80)) {\n"
     b"\t\t\t\tconst auto*    sp  = reinterpret_cast<const uint64_t*>(info->rsp);\n"
     b"\t\t\t\tconst uint64_t key = sp[10], ent = sp[15];\n"
     b"\t\t\t\tBc5CrashLog(\"0413 key 0x%016\" PRIx64 \" [%s] entry 0x%016\" PRIx64 \"\\n\", key, str0413(key).c_str(), ent);\n"
     b"\t\t\t\tfor (int e = -12; e <= 2; e++) {\n"
     b"\t\t\t\t\tconst uint64_t a = ent + static_cast<int64_t>(e) * 0x18;\n"
     b"\t\t\t\t\tif (!IsDumpableRange(a, 0x20)) continue;\n"
     b"\t\t\t\t\tconst auto* q = reinterpret_cast<const uint64_t*>(a);\n"
     b"\t\t\t\t\tBc5CrashLog(\"0413 entry %+d at 0x%016\" PRIx64 \": %016\" PRIx64 \" %016\" PRIx64 \" %016\" PRIx64 \" %016\" PRIx64 \" [+8: %s] [+18: %s]\\n\", e, a, q[0], q[1], q[2], q[3], str0413(q[1]).c_str(), str0413(q[3]).c_str());\n"
     b"\t\t\t\t}\n"
     b"\t\t\t}\n")
s = s.replace(A, W + A)
open(sys.argv[2], "wb").write(s)
print(hashlib.md5(s).hexdigest())
