import sys
# BC5 experiment 0189: the GPU-side leads of 2026-10-21 for the second title's geometry-engine reads at
# address 0 (F208), docs/ports/related-projects-review.md section 7. Applied to ~/src/KytyPlus (patch 0001).
#  - diagnostics: BC5_GC_IOCTL_TRACE=1 (the /dev/gc requests of the title's own libSceAgcDriver),
#    BC5_DIRECT_REG_CENSUS=1 (draws by the tessellation / GE_PC_ALLOC state in force, ring register writes)
#  - behaviour, off by default: BC5_DIRECT_TF_DEFAULT=1 (+ _SIZE, BC5_DIRECT_HS_OFFCHIP), BC5_DIRECT_OFFCHIP_SECOND=1,
#    BC5_DIRECT_GE_PC_ALLOC=<hex>|radv
#  - fix: the one-register SET_UCONFIG_REG packets of the TF ring prefix had COUNT 0 (exp 0160)
#  - HLE GraphicsDriverGetTFRing / GetHsOffchipParam
#  - the timeout probe printed GE_STEREO_CNTL (0x25f) as pc_alloc; now both
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
# --- globals, ioctl trace, default ring allocation (namespace Bc5Gc) ---
(b"""static bool gc_log_few(int* counter, int limit = 8) {
	return g_gc_verbose || (*counter)++ < limit;
}
""", b"""static bool gc_log_few(int* counter, int limit = 8) {
	return g_gc_verbose || (*counter)++ < limit;
}
// Experiment 0189 (diagnostic): BC5_GC_IOCTL_TRACE=1 writes the first 8 calls of each /dev/gc request code to
// stderr ("[bc5-gc-trace]") with the bytes the caller passed in: what the title's own libSceAgcDriver (LLE, from
// the module pack) asks of the console's kernel, e.g. for the rings that kernel sets up and the host does not.
static void ioctl_trace(uint64_t request, const void* argp) {
	static const bool on = BC5_DIAG_ENV("BC5_GC_IOCTL_TRACE") != nullptr;
	if (!on) return;
	static std::mutex               m;
	static std::map<uint64_t, int> seen;
	std::lock_guard                 lk(m);
	const int                       n = seen[request]++;
	if (n >= 8) return;
	// _IOC: size bits 29:16, 0x80000000 = the caller passes data in, 0x40000000 = the kernel writes it back.
	const uint32_t size = (static_cast<uint32_t>(request) >> 16u) & 0x1fffu;
	const bool     in   = (request & 0x80000000u) != 0;
	const bool     out  = (request & 0x40000000u) != 0;
	std::fprintf(stderr, "[bc5-gc-trace] ioctl 0x%08" PRIx64 " (size %u, %s%s) call %d:", request, size, in ? "in" : "", out ? "out" : "", n + 1);
	if (in && argp != nullptr) {
		const auto* w = static_cast<const uint32_t*>(argp);
		for (uint32_t i = 0; i < size / 4 && i < 64; i++) std::fprintf(stderr, " %08x", w[i]);
	}
	std::fprintf(stderr, "\\n");
}
// Experiment 0189 (behaviour, off by default): BC5_DIRECT_TF_DEFAULT=1 gives the geometry engine a
// tessellation-factor ring when the title gave the host none (the console's system has one before a title sets
// its own: AnyPS5 core/libs/prx/libSceAgcDriver/State/src/Configuration.cpp:12-15 @ 27c88a8, base 0xff0000000,
// 128 KiB). 256 KiB of guest flexible memory ("Bc5TfRing"), at 0xff0000000 where free, else anywhere, mapped
// at the driver's first /dev/gc request; Direct::tf_ring_prefix programs it once the direct path has mapped it.
// BC5_DIRECT_TF_DEFAULT_SIZE=<hex bytes> is the ring size programmed (default 0x20000, at most 0x3fffc).
static constexpr uint64_t    kTfDefaultBytes = 0x40000;
static std::atomic<uint64_t> g_tf_default_va {0};
static bool tf_default_on() {
	static const bool v = [] {
		const char* e = std::getenv("BC5_DIRECT_TF_DEFAULT");
		return e != nullptr && *e != 0 && std::strcmp(e, "0") != 0;
	}();
	return v;
}
static uint32_t tf_default_size() {
	static const uint32_t v = [] {
		const char*         e = std::getenv("BC5_DIRECT_TF_DEFAULT_SIZE");
		const unsigned long s = e != nullptr ? std::strtoul(e, nullptr, 16) : 0x20000ul;
		return static_cast<uint32_t>(std::min<unsigned long>(s == 0 ? 0x20000ul : s, 0x3fffcul) & ~3ul);
	}();
	return v;
}
static void tf_default_alloc() {
	static std::once_flag once;
	if (!tf_default_on()) return;
	std::call_once(once, [] {
		void* a = reinterpret_cast<void*>(0xff0000000ull);
		int   r = LibKernel::Memory::KernelMapNamedFlexibleMemory(&a, kTfDefaultBytes, 0x33, static_cast<int>(GUEST_MAP_FIXED | 0x80u), "Bc5TfRing"); // CPU+GPU rw; fixed, no overwrite
		if (r != 0) {
			a = nullptr;
			r = LibKernel::Memory::KernelMapNamedFlexibleMemory(&a, kTfDefaultBytes, 0x33, 0, "Bc5TfRing");
		}
		if (r == 0 && a != nullptr) {
			std::memset(a, 0, kTfDefaultBytes);
			g_tf_default_va = reinterpret_cast<uint64_t>(a);
		}
		std::fprintf(stderr, "bc5-direct: default TF ring (exp 0189): %s at %p, 0x%" PRIx64 " bytes, ring size 0x%x (%d)\\n", r == 0 ? "ok" : "FAILED", a, kTfDefaultBytes, tf_default_size(), r);
	});
}
// For the HLE GraphicsDriverGetTFRing (agc.cpp): the host's default ring, 0 when BC5_DIRECT_TF_DEFAULT is off.
extern "C" uint64_t Bc5TfDefaultRing(uint32_t* size) {
	tf_default_alloc();
	const uint64_t va = g_tf_default_va.load();
	if (size != nullptr) *size = va != 0 ? tf_default_size() : 0;
	return va;
}
"""),
# --- gc_ioctl: trace, and the default ring at the first request ---
(b"""static int gc_ioctl(uint64_t request, void* argp) {
	switch (request) {
		case 0xc004812e: { // ps5: capability/flag query; RPCSX answers unk=0, flag=0
			auto* a = static_cast<uint16_t*>(argp);
""", b"""static int gc_ioctl(uint64_t request, void* argp) {
	ioctl_trace(request, argp); // experiment 0189
	switch (request) {
		case 0xc004812e: { // ps5: capability/flag query; RPCSX answers unk=0, flag=0
			tf_default_alloc(); // experiment 0189 (BC5_DIRECT_TF_DEFAULT=1; the driver's first request)
			auto* a = static_cast<uint16_t*>(argp);
"""),
# --- the prefix: default ring, offchip from the second value, GE_PC_ALLOC, and the COUNT fix ---
(b"""extern "C" void Bc5TfRingState(uint64_t* base, uint32_t* size, uint64_t* offchip0, uint64_t* offchip1, uint64_t* offchip2);
static void tf_ring_prefix(std::vector<uint32_t>& p) {
	static const bool off = std::getenv("BC5_DIRECT_NO_TF_RING") != nullptr;
	if (off) return;
	uint64_t base = 0, o0 = 0, o1 = 0, o2 = 0;
	uint32_t size = 0;
	Bc5TfRingState(&base, &size, &o0, &o1, &o2);
""", b"""extern "C" void Bc5TfRingState(uint64_t* base, uint32_t* size, uint64_t* offchip0, uint64_t* offchip1, uint64_t* offchip2);
// Experiment 0189, behaviour switches, all off by default (docs/ports/related-projects-review.md section 7):
// - BC5_DIRECT_TF_DEFAULT=1: when the title gave the host no ring, the host's default ring (Bc5Gc::tf_default_alloc)
//   once the direct path has mapped it, size BC5_DIRECT_TF_DEFAULT_SIZE; the first such prefix starts with
//   VS_PARTIAL_FLUSH + VGT_FLUSH (RADV does both before it sets ring registers: Mesa src/amd/vulkan/radv_queue.c
//   :1048-1052 and the event encoding of src/amd/common/ac_cmdbuf.h:372-381 @ 0866ae7; event types 15 and 36 in the
//   gfx10 register JSON). VGT_HS_OFFCHIP_PARAM is then left as it is unless BC5_DIRECT_HS_OFFCHIP=<hex> gives the
//   register value (gfx10.1: OFFCHIP_BUFFERING bits 0-8 = workgroups - 1, OFFCHIP_GRANULARITY bits 9-10, 0 = 8K
//   dwords; RADV on the BC-250 sizes its offchip ring for 96 workgroups of 32 KiB, i.e. 0x5f).
// - BC5_DIRECT_OFFCHIP_SECOND=1: VGT_HS_OFFCHIP_PARAM from GraphicsDriverSetHsOffchipParam's second value instead
//   of its first (ps5-vulkan native/tess_offchip_lease.h:27-44 @ e6d3c3f, GPL-3.0, read for the idea only: the
//   first is 0, the second the buffering in 32-KiB blocks minus one).
// - BC5_DIRECT_GE_PC_ALLOC=<hex>|radv: GE_PC_ALLOC (uconfig 0x260 = 0x30980 in the gfx10 register JSON; 0x25f is
//   GE_STEREO_CNTL) in every prefix; radv = 0x1ff, RADV's value for an NGG stage with late alloc on gfx1013
//   (OVERSUB_EN | NUM_PC_LINES(1024 / 4 - 1): radv_shader.c:1764, ac_gpu_info.c:1345-1352 @ 0866ae7). The title's
//   own LOAD_UCONFIG_REG_INDEX table also carries 0x260 and runs after the prefix; BC5_DIRECT_UCONFIG_FORCE=260:<v>
//   keeps a value past it.
static uint32_t ge_pc_alloc() {
	static const uint32_t v = [] {
		const char* e = std::getenv("BC5_DIRECT_GE_PC_ALLOC");
		if (e == nullptr || *e == 0) return 0u;
		if (std::strcmp(e, "radv") == 0) return 0x1ffu;
		return static_cast<uint32_t>(std::strtoul(e, nullptr, 16));
	}();
	return v;
}
static bool hs_offchip_force(uint32_t* v) {
	static const long long f = [] {
		const char* e = std::getenv("BC5_DIRECT_HS_OFFCHIP");
		return e != nullptr && *e != 0 ? static_cast<long long>(std::strtoul(e, nullptr, 16) & 0xffffffffu) : -1ll;
	}();
	if (f < 0) return false;
	*v = static_cast<uint32_t>(f);
	return true;
}
static void tf_ring_prefix(std::vector<uint32_t>& p) {
	if (const uint32_t pc = ge_pc_alloc(); pc != 0) p.insert(p.end(), {0xC0017900u, 0x260u, pc}); // GE_PC_ALLOC (exp 0189)
	static const bool off = std::getenv("BC5_DIRECT_NO_TF_RING") != nullptr;
	if (off) return;
	uint64_t base = 0, o0 = 0, o1 = 0, o2 = 0;
	uint32_t size = 0;
	Bc5TfRingState(&base, &size, &o0, &o1, &o2);
	static const bool second = std::getenv("BC5_DIRECT_OFFCHIP_SECOND") != nullptr;
"""),
(b"""		base = std::get<0>(forced);
		size = std::get<1>(forced);
		o0   = std::get<2>(forced);
	}
	if (base == 0 || size == 0) return;
	static std::atomic<uint64_t> n {0};
	if ((n++ & 0xffffu) == 0) journal("tf ring: base 0x%" PRIx64 " size 0x%x offchip 0x%" PRIx64 " 0x%" PRIx64 " 0x%" PRIx64 " (%" PRIu64 " prefixes)\\n", base, size, o0, o1, o2, n.load());
	const uint32_t size_dw = static_cast<uint32_t>(std::min<uint64_t>(size / 4, 0xffffu));
	p.insert(p.end(), {0xC0027900u, 0x24eu, size_dw, static_cast<uint32_t>(o0)});          // VGT_TF_RING_SIZE, VGT_HS_OFFCHIP_PARAM
	p.insert(p.end(), {0xC0007900u, 0x250u, static_cast<uint32_t>(base >> 8u)});           // VGT_TF_MEMORY_BASE
	p.insert(p.end(), {0xC0007900u, 0x261u, static_cast<uint32_t>(base >> 40u) & 0xffu});  // VGT_TF_MEMORY_BASE_HI
}
""", b"""		base = std::get<0>(forced);
		size = std::get<1>(forced);
		o0   = std::get<2>(forced);
	}
	uint32_t   off_v        = static_cast<uint32_t>(second ? o1 : o0);
	bool       write_off    = true;
	bool       host_default = false;
	if ((base == 0 || size == 0) && tf_default_on()) { // experiment 0189
		const uint64_t       va = g_tf_default_va.load();
		static std::atomic<bool> told {false};
		const auto           pm = va != 0 && g_dev ? g_dev->sorted_mappings() : nullptr;
		if (pm != nullptr && covered_sorted(*pm, va, kTfDefaultBytes)) {
			base         = va;
			size         = tf_default_size();
			host_default = true;
			write_off    = hs_offchip_force(&off_v);
		} else if (!told.exchange(true)) {
			journal("tf ring (exp 0189): default ring at 0x%" PRIx64 " not mapped yet, not programmed\\n", va);
		}
	}
	if (base == 0 || size == 0) return;
	static std::atomic<uint64_t> n {0};
	if ((n++ & 0xffffu) == 0) journal("tf ring: base 0x%" PRIx64 " size 0x%x offchip 0x%" PRIx64 " 0x%" PRIx64 " 0x%" PRIx64 " -> VGT_HS_OFFCHIP_PARAM %s0x%x%s (%" PRIu64 " prefixes)\\n", base, size, o0, o1, o2, write_off ? "" : "untouched, not ", off_v, host_default ? ", host default ring" : "", n.load());
	const uint32_t size_dw = static_cast<uint32_t>(std::min<uint64_t>(size / 4, 0xffffu));
	if (host_default) {
		static std::atomic<bool> flushed {false};
		if (!flushed.exchange(true)) p.insert(p.end(), {0xC0004600u, 0x40fu, 0xC0004600u, 0x24u}); // EVENT_WRITE VS_PARTIAL_FLUSH (index 4), VGT_FLUSH (index 0)
	}
	if (write_off) p.insert(p.end(), {0xC0027900u, 0x24eu, size_dw, off_v}); // VGT_TF_RING_SIZE, VGT_HS_OFFCHIP_PARAM
	else p.insert(p.end(), {0xC0017900u, 0x24eu, size_dw});                  // VGT_TF_RING_SIZE
	// Experiment 0189: one register = COUNT 1 (PKT3 COUNT is the body's dwords minus one). Exp 0160 wrote 0xC0007900
	// here: an offset without a value, the CP wrote nothing, and the value dword read as a type-0 header that the
	// filter dropped with the next dwords (run 770 programmed no base and cut the title's first packet).
	p.insert(p.end(), {0xC0017900u, 0x250u, static_cast<uint32_t>(base >> 8u)});           // VGT_TF_MEMORY_BASE
	p.insert(p.end(), {0xC0017900u, 0x261u, static_cast<uint32_t>(base >> 40u) & 0xffu});  // VGT_TF_MEMORY_BASE_HI
}
"""),
# --- timeout probe: GE_STEREO_CNTL was printed as pc_alloc ---
(b"""0x25b (GE_CNTL), 0x25f (GE_PC_ALLOC); SH 0x88/0x89""",
 b"""0x25b (GE_CNTL), 0x25f (GE_STEREO_CNTL), 0x260 (GE_PC_ALLOC; until exp 0189 0x25f was printed as pc_alloc); SH 0x88/0x89"""),
(b"""ninst %08x ge_cntl %08x pc_alloc %08x | gs""", b"""ninst %08x ge_cntl %08x stereo %08x pc_alloc %08x | gs"""),
(b"""g(st_uc, 0x25b), g(st_uc, 0x25f),""", b"""g(st_uc, 0x25b), g(st_uc, 0x25f), g(st_uc, 0x260),"""),
# --- register census ---
(b"""static void pkt_stats(const uint32_t* ib, uint32_t num_dwords, const char* kind) {
""", b"""// Experiment 0189 (diagnostic, CPU only): BC5_DIRECT_REG_CENSUS=1 follows, in every buffer the host submits (with
// its prefix, before the filter), the registers of the 2026-10-21 GPU leads as the packets set them --
// SET_CONTEXT_REG(_INDEX), SET_UCONFIG_REG(_INDEX), and the (offset, value) tables of LOAD_CONTEXT_REG_INDEX /
// LOAD_UCONFIG_REG_INDEX as they read now -- and counts the draws by the values in force: VGT_SHADER_STAGES_EN
// (context 0x2d5; LS_EN bits 0-1, HS_EN bit 2), with HS on also VGT_LS_HS_CONFIG (0x2d6) and VGT_TF_PARAM (0x2db),
// GE_PC_ALLOC (uconfig 0x260) and GE_STEREO_CNTL (0x25f); and every value written to VGT_ESGS/GSVS_RING_SIZE,
// VGT_TF_RING_SIZE, VGT_HS_OFFCHIP_PARAM, VGT_TF_MEMORY_BASE(_HI), GE_PC_ALLOC (uconfig 0x240, 0x241, 0x24e, 0x24f,
// 0x250, 0x261, 0x260). Offsets and fields: Mesa's gfx10 register JSON (tools/bc5-agc/regdb). ffffffff = not set
// in that buffer. The counts since the start go to stderr every 60 s ("reg census"). Nested IBs are not followed.
static void reg_census(const uint32_t* ib, uint32_t num_dwords, const char* kind, const std::vector<bc5::direct::Mapping>& maps) {
	static const bool on = BC5_DIAG_ENV("BC5_DIRECT_REG_CENSUS") != nullptr;
	if (!on) return;
	using Key = std::array<uint32_t, 8>;
	std::vector<Key> found;
	const uint32_t   kc     = static_cast<uint32_t>(static_cast<unsigned char>(kind[0]));
	uint32_t         stages = ~0u, lshs = ~0u, tfp = ~0u, pca = ~0u, stereo = ~0u;
	auto             ctx    = [&](uint32_t r, uint32_t v) {
        if (r == 0x2d5) stages = v;
        else if (r == 0x2d6) lshs = v;
        else if (r == 0x2db) tfp = v;
	};
	auto uc = [&](uint32_t r, uint32_t v, uint32_t how) {
		if (r == 0x260) pca = v;
		else if (r == 0x25f) stereo = v;
		if (r == 0x240 || r == 0x241 || r == 0x24e || r == 0x24f || r == 0x250 || r == 0x261 || r == 0x260) found.push_back({1u, kc, how, r, v, 0u, 0u, 0u});
	};
	auto table = [&](const uint32_t* pk, uint32_t ln, bool context) {
		if (ln < 5 || (pk[3] >> 31u) == 0) return;
		const uint64_t ta = (pk[1] & ~3u) | (static_cast<uint64_t>(pk[2] & 0xffffu) << 32u);
		const uint32_t tn = pk[4] & 0x3fffu;
		if (ta == 0 || tn == 0 || tn > 4096 || !covered_sorted(maps, ta, static_cast<uint64_t>(tn) * 8)) return;
		const auto* t = reinterpret_cast<const volatile uint32_t*>(ta);
		for (uint32_t k = 0; k < tn; k++) {
			if (context) ctx(t[2 * k] & 0xffffu, t[2 * k + 1]);
			else uc(t[2 * k] & 0xffffu, t[2 * k + 1], 'l');
		}
	};
	for (uint32_t q = 0; q < num_dwords;) {
		const uint32_t h = ib[q], type = h >> 30u;
		uint32_t       len = 1;
		if (type == 3 || type == 0) { const uint32_t c = (h >> 16u) & 0x3fffu; len = c == 0x3fffu ? 1 : c + 2; }
		if (q + len > num_dwords) break;
		if (type == 3) {
			const uint32_t op = (h >> 8u) & 0xffu;
			if ((op == 0x69 || op == 0x6a) && len >= 3) {
				const uint32_t first = ib[q + 1] & 0xffffu;
				for (uint32_t k = 0; k + 2 < len; k++) ctx(first + k, ib[q + 2 + k]);
			} else if ((op == 0x79 || op == 0x7a) && len >= 3) {
				const uint32_t first = ib[q + 1] & 0xffffu;
				for (uint32_t k = 0; k + 2 < len; k++) uc(first + k, ib[q + 2 + k], 's');
			} else if (op == 0x9f) {
				table(ib + q, len, true);
			} else if (op == 0x64) {
				table(ib + q, len, false);
			} else if (op == 0x2d || op == 0x27 || op == 0x35 || op == 0x38 || op == 0x24 || op == 0x25 || op == 0x2c) {
				const bool hs = stages != ~0u && (stages & 0x7u) != 0;
				found.push_back({0u, kc, op, stages, hs ? lshs : 0u, hs ? tfp : 0u, pca, stereo});
			}
		}
		q += len;
	}
	static std::mutex             m;
	static std::map<Key, uint64_t> counts;
	static uint64_t               t_last = 0, bufs = 0;
	std::lock_guard               lk(m);
	bufs++;
	for (const auto& k: found) counts[k]++;
	const uint64_t now = SoftCp::now_ns();
	if (t_last == 0) t_last = now;
	if (now - t_last < 60'000'000'000ull) return;
	t_last = now;
	std::fprintf(stderr, "reg census: %" PRIu64 " buffers, %zu keys\\n", bufs, counts.size());
	for (const auto& [k, c]: counts) {
		if (k[0] == 0) std::fprintf(stderr, "reg census: %c draws op %02x stages %08x ls_hs %08x tf_param %08x pc_alloc %08x stereo %08x: %" PRIu64 "\\n", static_cast<char>(k[1]), k[2], k[3], k[4], k[5], k[6], k[7], c);
		else std::fprintf(stderr, "reg census: %c %s uc 0x%03x = %08x: %" PRIu64 "\\n", static_cast<char>(k[1]), k[2] == 's' ? "set" : "load", k[3], k[4], c);
	}
}

static void pkt_stats(const uint32_t* ib, uint32_t num_dwords, const char* kind) {
"""),
(b"""	shader_dump(ib, num_dwords, *maps_p); // experiment 0049
""", b"""	shader_dump(ib, num_dwords, *maps_p); // experiment 0049
	reg_census(ib, num_dwords, kind, *maps_p); // experiment 0189
"""),
])

agc = root + "/src/libs/agc.cpp"
patch(agc, [
(b"""bool KYTY_SYSV_ABI GraphicsDriverIsCaptureInProgress() {
""", b"""// BC5 (experiment 0189): sceAgcDriverGetTFRing / sceAgcDriverGetHsOffchipParam (NIDs e-YMQ+2tj9M and r28hEh6cNH0,
// the NIDs of the names; signatures as AnyPS5 core/libs/prx/libSceAgcDriver/State/src/Configuration.cpp:38 and
// Unimplemented.cpp:53 @ 27c88a8): what the title set, else the host's default ring (BC5_DIRECT_TF_DEFAULT=1,
// bc5LleAgc.cpp). Not reached while a title runs its own libSceAgcDriver from the module pack (LLE), as both BC5
// titles do: their driver's calls go to /dev/gc instead (BC5_GC_IOCTL_TRACE=1).
extern "C" uint64_t Bc5TfDefaultRing(uint32_t* size);
int KYTY_SYSV_ABI GraphicsDriverGetTFRing(uint64_t* base, uint32_t* size) {
	PRINT_NAME();

	uint64_t b = g_tessellation_driver_state.tf_ring_base;
	uint32_t s = g_tessellation_driver_state.tf_ring_size;
	if (b == 0 || s == 0) {
		b = Bc5TfDefaultRing(&s);
	}
	if (base != nullptr) {
		*base = b;
	}
	if (size != nullptr) {
		*size = s;
	}
	std::fprintf(stderr, "[bc5-tess] GetTFRing -> base 0x%016" PRIx64 " size 0x%08" PRIx32 "\\n", b, s); // experiment 0189

	return OK;
}

int KYTY_SYSV_ABI GraphicsDriverGetHsOffchipParam(uint16_t* first, uint16_t* second) {
	PRINT_NAME();

	if (first != nullptr) {
		*first = static_cast<uint16_t>(g_tessellation_driver_state.hs_offchip_value0);
	}
	if (second != nullptr) {
		*second = static_cast<uint16_t>(g_tessellation_driver_state.hs_offchip_value1);
	}
	std::fprintf(stderr, "[bc5-tess] GetHsOffchipParam -> 0x%04" PRIx64 " 0x%04" PRIx64 "\\n", g_tessellation_driver_state.hs_offchip_value0 & 0xffffu,
	             g_tessellation_driver_state.hs_offchip_value1 & 0xffffu); // experiment 0189

	return OK;
}

bool KYTY_SYSV_ABI GraphicsDriverIsCaptureInProgress() {
"""),
])

agch = root + "/src/libs/agc.h"
patch(agch, [
(b"""bool KYTY_SYSV_ABI     GraphicsDriverIsCaptureInProgress();
""", b"""int KYTY_SYSV_ABI      GraphicsDriverGetTFRing(uint64_t* base, uint32_t* size);    // BC5 experiment 0189
int KYTY_SYSV_ABI      GraphicsDriverGetHsOffchipParam(uint16_t* first, uint16_t* second); // BC5 experiment 0189
bool KYTY_SYSV_ABI     GraphicsDriverIsCaptureInProgress();
"""),
])

lgd = root + "/src/libs/libGraphicsDriver.cpp"
patch(lgd, [
(b"""	LIB_FUNC("MM4IZSEYytQ", Gen5Driver::GraphicsDriverSetHsOffchipParam);
""", b"""	LIB_FUNC("MM4IZSEYytQ", Gen5Driver::GraphicsDriverSetHsOffchipParam);
	LIB_FUNC("e-YMQ+2tj9M", Gen5Driver::GraphicsDriverGetTFRing);         // BC5 experiment 0189: sceAgcDriverGetTFRing
	LIB_FUNC("r28hEh6cNH0", Gen5Driver::GraphicsDriverGetHsOffchipParam); // BC5 experiment 0189: sceAgcDriverGetHsOffchipParam
"""),
])
print("done")
