# BC5 exp 0439: cut state_prefix() out of the generated private unit for test_sp0439.cpp.
#   python3 -I mksp0439.py <bc5LleAgc.cpp> <out .inc>
import sys

s = open(sys.argv[1], encoding="utf-8").read()
a = s.index("static const uint32_t* state_prefix(const uint32_t* ib, uint32_t upto, uint32_t* out_dwords) {")
b = s.index("\n}\n", a) + 3
open(sys.argv[2], "w", encoding="utf-8").write(s[a:b])
print("extracted", b - a, "chars")
