"""Exp 0413 (PRIVATE diagnostic): mkwalk0413b.py's dump plus the targets of the guest import stubs near the fault:
for each given stub address (a PLT `jmp [rip+disp]`), the host address it jumps to and dladdr's symbol for it.
Stubs: 0x9074b62e0 (called by frame 2 just before the lookup) and the lookup's compare 0x90001d750 (read as code).
Input: mkwalk0413b.py's output (md5 97ef39f8). usage: mkwalk0413c.py <in> <out>"""
import hashlib
import sys

s = open(sys.argv[1], "rb").read()
assert hashlib.md5(s).hexdigest().startswith("97ef39f8"), hashlib.md5(s).hexdigest()
A = b"\t\t\tif (IsDumpableRange(info->exception_address - 0x60, 0x80)) {\n"
assert s.count(A) == 1
W = (b"\t\t\tfor (const uint64_t stub: {uint64_t {0x9074b62e0}, uint64_t {0x90001d750}}) {\n"
     b"\t\t\t\tif (!IsDumpableRange(stub, 16)) continue;\n"
     b"\t\t\t\tconst auto* c = reinterpret_cast<const uint8_t*>(stub);\n"
     b"\t\t\t\tchar        hex[16 * 3 + 1];\n"
     b"\t\t\t\tfor (int i = 0; i < 16; i++) snprintf(hex + i * 3, 4, \"%02x \", c[i]);\n"
     b"\t\t\t\tuint64_t target = 0;\n"
     b"\t\t\t\tif (c[0] == 0xff && c[1] == 0x25) {\n"
     b"\t\t\t\t\tint32_t disp;\n"
     b"\t\t\t\t\tstd::memcpy(&disp, c + 2, 4);\n"
     b"\t\t\t\t\tconst uint64_t slot = stub + 6 + static_cast<int64_t>(disp);\n"
     b"\t\t\t\t\tif (IsDumpableRange(slot, 8)) target = *reinterpret_cast<const uint64_t*>(slot);\n"
     b"\t\t\t\t}\n"
     b"\t\t\t\tDl_info di {};\n"
     b"\t\t\t\tconst bool named = target != 0 && dladdr(reinterpret_cast<void*>(target), &di) != 0;\n"
     b"\t\t\t\tBc5CrashLog(\"0413 stub 0x%016\" PRIx64 \": %s-> 0x%016\" PRIx64 \" %s (base 0x%016\" PRIx64 \")\\n\", stub, hex, target,\n"
     b"\t\t\t\t            named && di.dli_sname != nullptr ? di.dli_sname : \"?\", named ? reinterpret_cast<uint64_t>(di.dli_fbase) : 0);\n"
     b"\t\t\t}\n")
s = s.replace(A, W + A)
open(sys.argv[2], "wb").write(s)
print(hashlib.md5(s).hexdigest())
