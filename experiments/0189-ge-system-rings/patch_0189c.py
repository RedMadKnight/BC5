import sys
# BC5 experiment 0189, third step (diagnostic only): with the title's TF ring programmed (BC5_DIRECT_GC_TF_RING=1,
# runs R1/R2) the first buffer with tessellated draws times out. The timeout probe (BC5_DIRECT_TIMEOUT_PROBE=1)
# now also writes the TF ring as the GPU left it and the HS stage's user-data table, and prints the LS/HS
# program addresses in its per-draw state lines.
root = sys.argv[1]


def patch(path, pairs):
    b = open(path, "rb").read()
    for old, new in pairs:
        done = False
        for nl in (b"\n", b"\r\n"):
            o = old.replace(b"\n", nl); n = new.replace(b"\n", nl)
            if b.count(n) == 1 and b.count(o) == 0:
                print("already:", old[:60]); done = True; break
            if b.count(o) == 1:
                b = b.replace(o, n); print("ok:", old[:60]); done = True; break
        assert done, ("not found", old[:80])
    open(path, "wb").write(b)


lle = root + "/src/libs/bc5LleAgc.cpp"
patch(lle, [
(b"""		journal("timeout probe: %s %u dwords dumped to %s\\n", kind, sub_n, name);
""", b"""		journal("timeout probe: %s %u dwords dumped to %s\\n", kind, sub_n, name);
		// Experiment 0189: with the title's /dev/gc TF ring programmed, the ring as the GPU left it (<name>.tfring.bin,
		// with a count of its non-zero dwords), and for the first 4 SPI_SHADER_USER_DATA_ADDR_LO/HI_HS pairs the buffer
		// sets (SET_SH_REG sh 0x102/0x103, gfx10 register JSON; the merged LS-HS stage's s0/s1) 1 KiB there
		// (<name>.hsud-<k>.bin) and its first 48 dwords in the journal.
		if (gc_tf_ring_on() && g_gc_tf_base.load() != 0) {
			const uint64_t tb = g_gc_tf_base.load();
			const uint32_t ts = g_gc_tf_size.load() & ~3u;
			if (ts != 0 && covered_sorted(*pm, tb, ts)) {
				const auto* t  = reinterpret_cast<const volatile uint32_t*>(tb);
				uint32_t    nz = 0, first = ~0u, last = 0;
				std::vector<uint32_t> copy(ts / 4);
				for (uint32_t k = 0; k < ts / 4; k++) {
					copy[k] = t[k];
					if (copy[k] != 0) { nz++; if (first == ~0u) first = k; last = k; }
				}
				const std::string nm = std::string(name) + ".tfring.bin";
				if (FILE* f = std::fopen(nm.c_str(), "wb"); f != nullptr) { std::fwrite(copy.data(), 4, copy.size(), f); std::fclose(f); }
				char buf[700];
				rd(tb + (first == ~0u ? 0 : static_cast<uint64_t>(first) * 4), 48, buf, sizeof(buf));
				journal("timeout probe: TF ring 0x%" PRIx64 " +0x%x: %u non-zero dwords (dword %u..%u), from the first: %s\\n", tb, ts, nz, first, last, buf);
			}
		}
		{
			uint32_t lo = 0, nud = 0;
			bool     have_lo = false;
			for (uint32_t q = 0; q < sub_n && nud < 4;) {
				const uint32_t h = sub_ib[q], type = h >> 30u;
				uint32_t       len = 1;
				if (type == 3 || type == 0) { const uint32_t c = (h >> 16u) & 0x3fffu; len = c == 0x3fffu ? 1 : c + 2; }
				if (q + len > sub_n) break;
				const uint32_t op = (h >> 8u) & 0xffu;
				if (type == 3 && (op == 0x76 || op == 0x9b) && len >= 3) {
					const uint32_t first = sub_ib[q + 1] & 0xffffu;
					for (uint32_t k = 0; k + 2 < len && nud < 4; k++) {
						const uint32_t r = first + k, v = sub_ib[q + 2 + k];
						if (r == 0x102) { lo = v; have_lo = true; }
						if (r == 0x103 && have_lo) {
							const uint64_t a = (static_cast<uint64_t>(lo) | (static_cast<uint64_t>(v) << 32u)) & ~3ull;
							have_lo = false;
							if (a == 0 || !covered_sorted(*pm, a, 1024)) {
								journal("timeout probe: HS user data address 0x%" PRIx64 " at %u not mapped\\n", a, q);
								continue;
							}
							char nm[600];
							std::snprintf(nm, sizeof(nm), "%s.hsud-%u.bin", name, nud);
							if (FILE* f = std::fopen(nm, "wb"); f != nullptr) {
								std::vector<uint32_t> c(256);
								for (uint32_t i = 0; i < 256; i++) c[i] = reinterpret_cast<const volatile uint32_t*>(a)[i];
								std::fwrite(c.data(), 4, c.size(), f);
								std::fclose(f);
							}
							char buf[700];
							rd(a, 48, buf, sizeof(buf));
							journal("timeout probe: HS user data address set at %u: %s\\n", q, buf);
							nud++;
						}
					}
				}
				q += len;
			}
		}
"""),
(b"""| gs %08x%08x es %08x%08x ps %08x%08x cs %08x%08x",""", b"""| gs %08x%08x es %08x%08x ps %08x%08x cs %08x%08x ls %08x%08x hs %08x%08x","""),
(b"""g(st_sh, 0x20d), g(st_sh, 0x20c));""", b"""g(st_sh, 0x20d), g(st_sh, 0x20c), g(st_sh, 0x149), g(st_sh, 0x148), g(st_sh, 0x109), g(st_sh, 0x108)); // exp 0189: + SPI_SHADER_PGM_LO/HI_LS, _HS"""),
])
print("done")
