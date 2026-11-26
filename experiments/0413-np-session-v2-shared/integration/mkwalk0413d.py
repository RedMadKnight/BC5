"""Exp 0413 (PRIVATE diagnostic): mkwalk0413c.py's stub lines, now following up to four hops (jmp rel32 e9, jmp [rip+d]
ff 25, movabs rax imm64 48 b8 .. then jmp rax ff e0, movabs r11 49 bb .. then jmp r11 41 ff e3) and printing every hop's
first 16 bytes and the last address's dladdr name. Input: mkwalk0413c.py's output (md5 d91b163e). usage: <in> <out>"""
import hashlib
import sys

s = open(sys.argv[1], "rb").read()
assert hashlib.md5(s).hexdigest().startswith("d91b163e"), hashlib.md5(s).hexdigest()
a = s.index(b"\t\t\tfor (const uint64_t stub: {uint64_t {0x9074b62e0}, uint64_t {0x90001d750}}) {\n")
b = s.index(b"\t\t\tif (IsDumpableRange(info->exception_address - 0x60, 0x80)) {\n")
W = (b"\t\t\tfor (const uint64_t stub: {uint64_t {0x9074b62e0}, uint64_t {0x90001d750}}) {\n"
     b"\t\t\t\tuint64_t at = stub;\n"
     b"\t\t\t\tfor (int hop = 0; hop < 5 && at != 0 && IsDumpableRange(at, 16); hop++) {\n"
     b"\t\t\t\t\tconst auto* c = reinterpret_cast<const uint8_t*>(at);\n"
     b"\t\t\t\t\tchar        hex[16 * 3 + 1];\n"
     b"\t\t\t\t\tfor (int i = 0; i < 16; i++) snprintf(hex + i * 3, 4, \"%02x \", c[i]);\n"
     b"\t\t\t\t\tDl_info     di {};\n"
     b"\t\t\t\t\tconst bool  named = dladdr(reinterpret_cast<void*>(at), &di) != 0 && di.dli_sname != nullptr;\n"
     b"\t\t\t\t\tBc5CrashLog(\"0413 stub 0x%016\" PRIx64 \" hop %d at 0x%016\" PRIx64 \": %s %s\\n\", stub, hop, at, hex, named ? di.dli_sname : \"\");\n"
     b"\t\t\t\t\tuint64_t next = 0;\n"
     b"\t\t\t\t\tif (c[0] == 0xe9) {\n"
     b"\t\t\t\t\t\tint32_t d;\n"
     b"\t\t\t\t\t\tstd::memcpy(&d, c + 1, 4);\n"
     b"\t\t\t\t\t\tnext = at + 5 + static_cast<int64_t>(d);\n"
     b"\t\t\t\t\t} else if (c[0] == 0xff && c[1] == 0x25) {\n"
     b"\t\t\t\t\t\tint32_t d;\n"
     b"\t\t\t\t\t\tstd::memcpy(&d, c + 2, 4);\n"
     b"\t\t\t\t\t\tconst uint64_t slot = at + 6 + static_cast<int64_t>(d);\n"
     b"\t\t\t\t\t\tif (IsDumpableRange(slot, 8)) next = *reinterpret_cast<const uint64_t*>(slot);\n"
     b"\t\t\t\t\t} else if ((c[0] == 0x48 && c[1] == 0xb8) || (c[0] == 0x49 && c[1] == 0xbb)) {\n"
     b"\t\t\t\t\t\tstd::memcpy(&next, c + 2, 8);\n"
     b"\t\t\t\t\t}\n"
     b"\t\t\t\t\tif (next == 0 || next == at) break;\n"
     b"\t\t\t\t\tif (!IsDumpableRange(next, 16)) {\n"
     b"\t\t\t\t\t\tDl_info dj {};\n"
     b"\t\t\t\t\t\tconst bool nj = dladdr(reinterpret_cast<void*>(next), &dj) != 0;\n"
     b"\t\t\t\t\t\tBc5CrashLog(\"0413 stub 0x%016\" PRIx64 \" -> host 0x%016\" PRIx64 \" %s (base 0x%016\" PRIx64 \")\\n\", stub, next,\n"
     b"\t\t\t\t\t\t            nj && dj.dli_sname != nullptr ? dj.dli_sname : \"?\", nj ? reinterpret_cast<uint64_t>(dj.dli_fbase) : 0);\n"
     b"\t\t\t\t\t\tbreak;\n"
     b"\t\t\t\t\t}\n"
     b"\t\t\t\t\tat = next;\n"
     b"\t\t\t\t}\n"
     b"\t\t\t}\n")
s = s[:a] + W + s[b:]
open(sys.argv[2], "wb").write(s)
print(hashlib.md5(s).hexdigest())
