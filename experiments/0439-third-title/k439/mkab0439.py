# BC5 exp 0439 (tag ab439): cut ab439_scan and ab439_wait out of the generated private unit for test_ab0439.cpp.
#   python3 -I mkab0439.py <bc5LleAgc.cpp> <out .inc> [plant]
# "plant": a chain treated as a call (it counts a level and meets the 3-level limit); test case 2 must then FAIL.
import sys

src, out = sys.argv[1], sys.argv[2]
s = open(src, encoding="utf-8").read()
a = s.index("static std::atomic<uint64_t> g_ab439_found")
b = s.index("static bool acb_ready(const uint32_t* ib, uint32_t num_dwords) {")
t = s[a:b]
assert "ab439_scan" in t and "ab439_wait" in t
if len(sys.argv) > 3 and sys.argv[3] == "plant":
    for k, v in (("chain ? depth : depth + 1", "depth + 1"), ("(chain || depth < 3)", "depth < 3")):
        assert t.count(k) == 1, k
        t = t.replace(k, v)
open(out, "w", encoding="utf-8").write(t)
print("extracted", len(t), "chars")
