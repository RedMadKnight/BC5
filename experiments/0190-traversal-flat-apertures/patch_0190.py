import sys
# BC5 experiment 0190: the second title's ray-traced-reflection traversals push their per-lane BVH stack with FLAT
# stores addressed through the console's fixed apertures (high dwords 0x80000000 LDS / 0x70000000 private); amdgpu's
# graphics VMIDs have them at 0x2000... / 0x1000..., so each push takes a memory violation and the wave is halted.
# BC5_DIRECT_FLAT_APERTURE=1 (or a comma list of program addresses in hex) rewrites the two constants in the title's
# code, in place, before the program's first dispatch. Off by default (D16). Applies on top of patch 0001 + 0189{,b,c}.
root = sys.argv[1]


def patch(path, pairs):
    b = open(path, "rb").read()
    for old, new in pairs:
        done = False
        for nl in (b"\n", b"\r\n"):
            o = old.replace(b"\n", nl); n = new.replace(b"\n", nl)
            if b.count(n) == 1:  # the new text keeps the old anchor, so look for it first
                print("already:", old[:60]); done = True; break
            if b.count(o) == 1:
                b = b.replace(o, n); print("ok:", old[:60]); done = True; break
        assert done, ("not found", old[:80])
    open(path, "wb").write(b)


lle = root + "/src/libs/bc5LleAgc.cpp"
patch(lle, [
(b"""static void submit_one(const uint32_t* ib, uint32_t num_dwords, const char* kind, bool from_header) {
""", b"""// Experiment 0190 (BC5_DIRECT_FLAT_APERTURE=1, or a comma list of program addresses in hex): the second
// title's ray-traced-reflection traversals push their per-lane BVH stack with FLAT stores whose address
// high dword comes from two constants, the console's apertures: s_brev_b32 sN, 1 (0x80000000, LDS) and the
// literal of v_med3_u32 vD, sN, 0x70000000, <packed stack pointer> (0x70000000, private; the median picks
// the LDS one while the pointer's high half is negative). They pop it with ds_read_b32 / scratch_load_dword.
// Under amdgpu the graphics VMIDs' apertures are 0x2000'0000'0000'0000 (LDS) and 0x1000'0000'0000'0000
// (private) (Linux gmc_v10_0.c gmc_v10_0_early_init; gfx_v10_0.c, the SH_MEM_BASES loop; the waves' own
// src_shared_base / src_private_base read 0x2000 / 0x1000, exp 0190), so a push leaves both apertures, the
// wave takes a memory violation (SQ_WAVE_TRAPSTS EXCP bit 8) and is halted (SQ_WAVE_STATUS FATAL_HALT):
// its dispatch never ends, the "endless traversal" of F113-F248. This rewrites in place, in the title's
// code before the program's first dispatch, each such literal to 0x10000000 and the s_brev_b32 operand 1
// to 4 (0x20000000): the same median with the host's apertures. Off by default (D16).
// Encodings: llvm-mc -triple=amdgcn -mcpu=gfx1013 -show-encoding.
static void flat_aperture_fix(uint64_t pgm, const std::vector<bc5::direct::Mapping>& maps) {
	struct Cfg {
		bool               on = false, all = false;
		std::set<uint64_t> list;
	};
	static const Cfg cfg = [] {
		Cfg         c;
		const char* e = std::getenv("BC5_DIRECT_FLAT_APERTURE");
		if (e == nullptr || *e == 0 || std::strcmp(e, "0") == 0) return c;
		c.on = true;
		if (std::strcmp(e, "1") == 0 || std::strcmp(e, "all") == 0) {
			c.all = true;
			return c;
		}
		for (const char* q = e; *q != 0;) {
			char*          end = nullptr;
			const uint64_t x   = std::strtoull(q, &end, 16);
			if (end == q) break;
			c.list.insert(x);
			q = (*end == ',') ? end + 1 : end;
		}
		return c;
	}();
	if (!cfg.on || pgm == 0 || (!cfg.all && cfg.list.count(pgm) == 0)) return;
	thread_local uint64_t last = 0;
	if (pgm == last) return;
	last = pgm;
	static std::mutex         m;
	static std::set<uint64_t> seen;
	std::lock_guard           lk(m);
	if (!seen.insert(pgm).second) return;
	uint32_t n = 0x10000 / 4; // the 64 KiB window shader_dump copies, as far as it is mapped
	while (n >= 0x400 && !covered_sorted(maps, pgm, static_cast<uint64_t>(n) * 4)) n -= 0x400;
	if (n < 0x400) return;
	auto*    w   = reinterpret_cast<volatile uint32_t*>(pgm);
	uint32_t end = 0;
	while (end < n && w[end] != 0xBF810000u) end++; // up to the program's s_endpgm
	uint32_t sites = 0, brevs = 0;
	for (uint32_t k = 0; k + 2 < end; k++) {
		const uint32_t d0 = w[k], d1 = w[k + 1], s = d1 & 0x1ffu;
		// v_med3_u32 (VOP3, no modifiers) with src1 the literal 0x70000000 and src0 an SGPR
		if ((d0 & 0xffffff00u) != 0xD5590000u || ((d1 >> 9u) & 0x1ffu) != 0xffu || w[k + 2] != 0x70000000u || s > 105u) continue;
		// the s_brev_b32 s<src0>, 1 that makes its LDS half, up to 1,024 dwords before
		uint32_t at = 0;
		for (uint32_t j = k; j-- > 0 && k - j <= 1024u;) {
			if (w[j] == (0xBE800B81u | (s << 16u)) || w[j] == (0xBE800B84u | (s << 16u))) {
				at = j + 1;
				break;
			}
		}
		if (at == 0) continue;
		if (w[at - 1] != (0xBE800B84u | (s << 16u))) {
			w[at - 1] = 0xBE800B84u | (s << 16u); // s_brev_b32 s<src0>, 4 = 0x20000000
			brevs++;
		}
		w[k + 2] = 0x10000000u;
		sites++;
		k += 2;
	}
	std::atomic_thread_fence(std::memory_order_seq_cst);
	if (sites != 0)
		journal("flat aperture: program 0x%" PRIx64 ": %u stack pushes (%u s_brev_b32) now address the host's LDS/private apertures\\n", pgm, sites, brevs);
}

static void submit_one(const uint32_t* ib, uint32_t num_dwords, const char* kind, bool from_header) {
"""),
(b"""			// Experiment 0059: BC5_DIRECT_SKIP_PGM=<hex list> drops every dispatch (DISPATCH_DIRECT and both
""", b"""			if (type == 3 && (op == 0x15 || op == 0x16)) flat_aperture_fix(pgm, *maps_p); // experiment 0190
			// Experiment 0059: BC5_DIRECT_SKIP_PGM=<hex list> drops every dispatch (DISPATCH_DIRECT and both
"""),
])
