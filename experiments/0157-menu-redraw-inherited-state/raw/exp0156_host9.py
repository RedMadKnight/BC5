#!/usr/bin/env python3
# Experiment 0157, ninth step: the register tables of a matched (UI) buffer are journaled: for each
# LOAD_*_REG(_INDEX) packet its offset in the buffer, the table address, and (for pair tables of up to 64
# pairs) the (register offset, value) pairs; longer tables only the count.
p = "/home/kjaniszewski/src/KytyPlus/src/libs/bc5LleAgc.cpp"
s = open(p, encoding="utf-8", newline="").read()


def rep(a, b):
    global s
    assert s.count(a) == 1, (s.count(a), a[:80])
    s = s.replace(a, b)


rep("""							} else if (lop == 0x9f || lop == 0x63 || lop == 0x64) {
								const bool     pairs = (ib[i + 3] >> 31u) != 0;
								const uint32_t n     = ib[i + 4] & 0x3fffu;
								const uint64_t bytes = static_cast<uint64_t>(n) * (pairs ? 8u : 4u);
								if (n != 0 && n <= 1024 && read(base, bytes) != nullptr) bc5_range_remember(ib, buf_no, i, "reg table", base, bytes);
							}""",
    """							} else if (lop == 0x9f || lop == 0x63 || lop == 0x64) {
								const bool     pairs = (ib[i + 3] >> 31u) != 0;
								const uint32_t n     = ib[i + 4] & 0x3fffu;
								const uint64_t bytes = static_cast<uint64_t>(n) * (pairs ? 8u : 4u);
								if (n != 0 && n <= 1024 && read(base, bytes) != nullptr) {
									bc5_range_remember(ib, buf_no, i, "reg table", base, bytes);
									// Experiment 0157: the table's pairs (offset:value), up to 64; dword 1 and 3 of the packet too.
									const auto* tv = reinterpret_cast<const uint32_t*>(base);
									char        pb[1400] = {};
									int         pw       = 0;
									if (pairs)
										for (uint32_t q = 0; q < n && q < 64 && pw < 1300; q++) pw += std::snprintf(pb + pw, sizeof(pb) - static_cast<size_t>(pw), " %x:%08x", tv[2 * q] & 0xffffu, tv[2 * q + 1]);
									journal("load table buf %u at %u: op %02x dw1 %08x dw3 %08x %s x%u at %010" PRIx64 ":%s%s\\n", buf_no, i, lop, ib[i + 1], ib[i + 3], pairs ? "pairs" : "span", n, base, pb,
									        n > 64 ? " ..." : "");
								}
							}""")

open(p, "w", encoding="utf-8", newline="").write(s)
print("ok")
