# BC5 exp 0439 (tag bk439): the bake kit's generator. It applies the bake set of exp 0439, and nothing else, to the
# originals of patch 589ef163 (bc5LleAgc.cpp md5 ed489aca99adacbdd449cf460417dc4c, videoOut.cpp) and to KytyPlus
# src/bc5/switch_defaults.hpp (the box copy had md5 48ae1cd69dba47709a8da22b14984b47). No diagnostics: no histogram,
# dump, scan, copy or no-drain mode, and no log line except one start-up line per switch (compiled out in lean) and a line
# on a FAILED decompress pass (kept in lean: a failure must stay visible).
#   ib439  BC5_DIRECT_IB_CHAIN          soft CP: a chained IB (bit 20 of the size dword) runs at the caller's depth and ends
#                                       the caller's buffer (the chain cut; README item 26)
#   fl439  BC5_DIRECT_IB_CHAIN_FLAT     backend: a top-level chain laid out flat (direct439-on-eacf8d2a.diff, not touched here)
#   ae439  BC5_DIRECT_AGC_EOP_IDENT     soft CP: end-of-pipe interrupts with the AGC idents (F890; README items 23, 36; sources
#                                       in bc5/dc0439.hpp: compute 0x20 + slot - 1, graphics 0; data (INT_CTXID << 16) | ident)
#   mw439  BC5_DIRECT_EAGER_GPU_WRITE   a direct view mapped with GPU write is imported whole (README items 8, 11)
#   dc439  BC5_DIRECT_DCC_PRESENT=2     the DCC display surface decompressed in place at its flip (F891; README items 10-14,
#                                       38-40; bc5/dc0439.hpp build with CB_SHADER_MASK 0xf)
# Defaults (switch_defaults.hpp): IB_CHAIN, IB_CHAIN_FLAT, AGC_EOP_IDENT and FLAT_APERTURE (moved from TITLE2's row) go into kSoft (every title, NAME=0 turns one
# off); DCC_PRESENT=2 and EAGER_GPU_WRITE=1 go into kTitleDefaults for BC5_T3 "TITLE3". The code's readers stay "on only
# when the word is 1" (DCC_PRESENT: "2"), the tables set the words; ib_chain.hpp is left as it is.
# The unit needs bc5/dc0439.hpp, bc5/ib_chain.hpp and bc5/state_stack.hpp on its include path: dc0439.hpp (beside this
# script) is copied into <out dir> for that.
# For lean the backend's exp 0439 fprintf lines must be guarded (#ifndef BC5_LEAN) or removed; they are NOT edited here
# (backend/src/direct.cpp after direct439-on-eacf8d2a.diff, line numbers of this worktree):
#   ~1177 "bc5-direct: exp 0439 (tag fl439): %s job of %zu dwords at %p laid out flat: ..."
#   ~1183 "bc5-direct: exp 0439 (tag fl439): %s job of %zu dwords at %p NOT laid out flat (%s): ..."
#   ~1433 "bc5-direct: exp 0439 (tag ib439): submit of %zu dwords at %p refused: ..."  (a refusal: may stay, as a failure)
#   ~1446 "bc5-direct: exp 0439 (tag ib439): submit #%llu with chains: ..."
#   ~1573 "bc5-direct: exp 0439 (tag ib439): submit of %zu dwords at %p: %zu INDIRECT_BUFFER packets NOP-ed ..."
# Usage: python mkbk439.py <orig dir with bc5LleAgc.cpp and videoOut.cpp> <switch_defaults.hpp> <out dir>
import hashlib
import os
import re
import shutil
import sys

orig, sdh, out = sys.argv[1], sys.argv[2], sys.argv[3]


def rd(path):
    t = open(path, 'rb').read().decode('utf-8')
    assert '\r' not in t, path + ': CRLF'
    return t


def wr(path, t):
    open(path, 'wb').write(t.encode('utf-8'))


def rep(t, a, b):
    c = t.count(a)
    assert c == 1, (a[:90], c)
    return t.replace(a, b)


raw = open(os.path.join(orig, 'bc5LleAgc.cpp'), 'rb').read()
assert hashlib.md5(raw).hexdigest() == 'ed489aca99adacbdd449cf460417dc4c', 'not the 589ef163 bc5LleAgc.cpp'
s = raw.decode('utf-8')
assert '\r' not in s

# ---- includes (all inside #if defined(KYTY_BC5_DIRECT)) ----
s = rep(s, '#include "bc5/direct.hpp"\n', '#include "bc5/direct.hpp"\n'
        '#include "bc5/ib_chain.hpp"    // exp 0439 (tag ib439)\n'
        '#include "bc5/state_stack.hpp" // exp 0439 (tag dc439): the GFX ring\'s context, followed on the host\n'
        '#include "bc5/dc0439.hpp"      // exp 0439 (tag dc439): the DCC display buffers\n')

# ---- ib439 (soft CP) ----
s = rep(s, r'''static void indirect_buffer(const uint32_t* p, int depth) {
	const uint64_t a    = addr64(p[1], p[2], 0xffu);
	const uint32_t size = p[3] & 0xfffffu;
	if (a == 0 || size == 0 || depth >= 4) {
		return;
	}
	dump_cb(depth == 0 ? "ib1" : "ib2", reinterpret_cast<const uint32_t*>(a), size);
	execute(reinterpret_cast<const uint32_t*>(a), size, depth + 1);
}''', r'''static thread_local uint32_t t_ib439_budget = 0; // exp 0439 (tag ib439): the walk budget against a chain cycle
static thread_local int      t_ib439_nest   = 0;
// exp 0439 (tag ib439, BC5_DIRECT_IB_CHAIN=1, set by switch_defaults.hpp kSoft): a chained IB (bit 20 of the size dword)
// runs at the caller's depth and ends the caller's buffer; calls keep the depth limit (bc5/ib_chain.hpp, sources there).
// True when a chain was followed.
static bool indirect_buffer(const uint32_t* p, int depth) {
	const uint64_t a     = addr64(p[1], p[2], 0xffu);
	const uint32_t size  = p[3] & 0xfffffu;
	const bool     rule  = bc5::ib_chain::enabled();
	const bool     chain = rule && bc5::ib_chain::is_chain(p[3]);
	if (a == 0 || size == 0 || (depth >= 4 && !chain)) {
		return false;
	}
	if (t_ib439_nest++ == 0) t_ib439_budget = static_cast<uint32_t>(bc5::ib_chain::kMaxChainPieces + bc5::ib_chain::kMaxCallPieces);
	if (rule && t_ib439_budget-- == 0) {
		t_ib439_nest--;
		return chain;
	}
	dump_cb(depth == 0 ? "ib1" : "ib2", reinterpret_cast<const uint32_t*>(a), size);
	execute(reinterpret_cast<const uint32_t*>(a), size, bc5::ib_chain::child_depth(depth, p[3], rule));
	t_ib439_nest--;
	return chain;
}''')
s = rep(s, '''				case IT_INDIRECT_BUFFER_CNST: indirect_buffer(p, depth); break;''', '''				case IT_INDIRECT_BUFFER_CNST:
					if (indirect_buffer(p, depth)) return; // exp 0439 (tag ib439): a chain ends this buffer
					break;''')

# ---- ae439 (soft CP) ----
s = rep(s, '''static void release_mem(const uint32_t* p, uint32_t payload, bool write) {''', r'''static thread_local uint32_t t_ae439_slot = 0; // exp 0439 (tag ae439): the replayed compute queue's slot, 0 = graphics
// exp 0439 (tag ae439, BC5_DIRECT_AGC_EOP_IDENT=1, set by switch_defaults.hpp kSoft; F890): end-of-pipe interrupts with
// the AGC idents (bc5/dc0439.hpp agc_eop_ident / agc_eop_data, sources there). Off: the PS4-style fire_eop as before.
static bool ae439_on() {
	static const bool v = [] {
		const char* e  = std::getenv("BC5_DIRECT_AGC_EOP_IDENT");
		const bool  on = e != nullptr && e[0] == '1' && e[1] == 0;
#ifndef BC5_LEAN
		std::fprintf(stderr, "[bc5] exp 0439 (tag ae439): BC5_DIRECT_AGC_EOP_IDENT=%d\n", on ? 1 : 0);
#endif
		return on;
	}();
	return v;
}
static void ae439_fire(uint32_t ctxid) {
	const uint32_t ident = t_ae439_slot != 0 ? 0x20u + t_ae439_slot - 1u : 0u;
	const uint64_t data  = (static_cast<uint64_t>(ctxid) << 16u) | ident;
	std::vector<EqRegistration> eqs;
	{
		std::lock_guard lock(g_eq_mutex);
		eqs = g_eqs;
	}
	for (const auto& r: eqs) {
		if (r.ident != static_cast<int>(ident)) continue;
		Libs::LibKernel::EventQueue::KernelTriggerEvent(r.eq, static_cast<uintptr_t>(r.ident), Libs::LibKernel::EventQueue::KERNEL_EVFILT_GRAPHICS, reinterpret_cast<void*>(data));
	}
}

static void release_mem(const uint32_t* p, uint32_t payload, bool write) {''')
s = rep(s, '''	(void)payload;
	if (write) write_timestamp_or_data(data_sel, a, lo, hi);
	if (int_sel != 0) {
		fire_eop(lo | (static_cast<uint64_t>(hi) << 32u));
	}
}''', '''	if (write) write_timestamp_or_data(data_sel, a, lo, hi);
	if (ae439_on()) { // exp 0439 (tag ae439): INT_SEL read as 3 bits (bits 26:24), the context id in dword 7
		if (((data_cntl >> 24u) & 7u) != 0) ae439_fire(payload >= 7 ? p[7] : 0u);
		return;
	}
	if (int_sel != 0) {
		fire_eop(lo | (static_cast<uint64_t>(hi) << 32u));
	}
}''')
s = rep(s, '''	if (write) write_timestamp_or_data(data_sel, a, p[4], p[5]);
	if (int_sel != 0) {
		fire_eop(p[4] | (static_cast<uint64_t>(p[5]) << 32u));''', '''	if (write) write_timestamp_or_data(data_sel, a, p[4], p[5]);
	if (ae439_on()) { // exp 0439 (tag ae439): EVENT_WRITE_EOP carries no context id: 0
		if (int_sel != 0) ae439_fire(0u);
		return;
	}
	if (int_sel != 0) {
		fire_eop(p[4] | (static_cast<uint64_t>(p[5]) << 32u));''')
s = rep(s, '''							t_compute_ring = (qq.a == 2); // TODO(bc5): which engine is compute is a guess''', '''							t_compute_ring = (qq.a == 2); // TODO(bc5): which engine is compute is a guess
							t_ae439_slot   = qq.d;        // exp 0439 (tag ae439): every registered queue is a compute queue here''')
s = rep(s, '''							t_compute_ring = false;
						}''', '''							t_compute_ring = false;
							t_ae439_slot   = 0;
						}''')

# ---- mw439, the map rule ----
MW = r'''// exp 0439 (tag mw439, BC5_DIRECT_EAGER_GPU_WRITE=1, set for TITLE3 by switch_defaults.hpp kTitleDefaults): a view of
// direct memory whose map call gave GPU write (KytyPlus PROT_GPU_WRITE 0x20, the protection the title passed;
// TODO(verify) the bit's meaning against a public source, the evidence is exp 0439 run n4's map log) is imported whole, as
// the eager names are: the GPU writes it from the map call on, the CPU may never (the third title's 3.4 GB view at
// 0x5000000000, fault records 20261121-113617/-114357). A by-data name (bd412) still wins.
static bool mw439_on() {
	static const bool v = [] {
		const char* e  = std::getenv("BC5_DIRECT_EAGER_GPU_WRITE");
		const bool  on = e != nullptr && e[0] == '1' && e[1] == 0;
#ifndef BC5_LEAN
		std::fprintf(stderr, "[bc5] exp 0439 (tag mw439): BC5_DIRECT_EAGER_GPU_WRITE=%d (1: GPU-writable direct views eager)\n", on ? 1 : 0);
#endif
		return on;
	}();
	return v;
}
static bool mw439_eager(int prot, const char* name) {
	return mw439_on() && (prot & 0x20) != 0 && !bd412_name(name);
}

'''
a = 'static std::vector<DView> direct_views_build(const DState& S) {\n'
s = rep(s, a, MW + a)
a = ('\t\tLibs::LibKernel::Memory::Bc5ForEachMappedRange(nullptr, &v, [](uint64_t start, uint64_t size, uint64_t offset, int type, int, const char* name, void* p) {\n'
     '\t\t\tif (type == 0 && size != 0) static_cast<std::vector<DView>*>(p)->push_back({start, size, offset, name != nullptr ? name : "", ls415_name_class(name, false), ls415_name_class(name, true)});\n')
s = rep(s, a, '\t\tLibs::LibKernel::Memory::Bc5ForEachMappedRange(nullptr, &v, [](uint64_t start, uint64_t size, uint64_t offset, int type, int prot, const char* name, void* p) {\n'
        '\t\t\tif (type == 0 && size != 0) {\n'
        '\t\t\t\tconst bool gw = mw439_eager(prot, name); // exp 0439 (tag mw439)\n'
        '\t\t\t\tstatic_cast<std::vector<DView>*>(p)->push_back({start, size, offset, name != nullptr ? name : "", ls415_name_class(name, false) && !gw, ls415_name_class(name, true) || gw});\n'
        '\t\t\t}\n')

# ---- dc439, the DCC present ----
a = 'static void submit_now(const uint32_t* ib, uint32_t num_dwords, const char* kind, int ring, const Chain* chain);\n'
s = rep(s, a, a + 'static void dc439_track(const uint32_t* ib, uint32_t n, const bc5::policy::FilterOptions& opt, int ring); // exp 0439 (tag dc439)\n')
a = '\tconst uint64_t ls_t3 = SoftCp::now_ns(); // experiment 0415 (ls415c)\n\tbc5::direct::SubmitResult r;\n'
s = rep(s, a, '\tconst uint64_t ls_t3 = SoftCp::now_ns(); // experiment 0415 (ls415c)\n'
        '\tdc439_track(sub_ib, sub_n, opt, qring); // exp 0439 (tag dc439): before the job, under the device lock\n'
        '\tbc5::direct::SubmitResult r;\n')

GLUE = r'''
// ---- BC5 exp 0439 (tag dc439): the third title's DCC display buffers (dcc-present-design.md; F891) ----
// BC5_DIRECT_DCC_PRESENT=2 (set for TITLE3 by switch_defaults.hpp kTitleDefaults; any other value: off). The GFX ring's
// context registers are followed by a host state_stack::Tracker over every GFX job, and the CB_COLORn block whose BASE is
// a registered compressed video-out surface is remembered: from the job's draws (bc5/dc0439.hpp walk_draws), else from the
// context at the job's end. At the title's flip of such a surface, after a drain, one host-built GFX job decompresses it
// in place (CB_DCC_DECOMPRESS, bc5/dc0439.hpp build), a drain again, and the present reads it as uncompressed
// (bc5_dc439_plain). Keys all 0xFF, or all 0x00 with an all-zero surface: plain with no pass.
namespace dc439 {
static int mode() {
	static const int v = [] {
		const char* e = std::getenv("BC5_DIRECT_DCC_PRESENT");
		const int   m = e != nullptr && e[0] == '2' && e[1] == 0 ? 2 : 0;
#ifndef BC5_LEAN
		std::fprintf(stderr, "[bc5] exp 0439 (tag dc439): BC5_DIRECT_DCC_PRESENT=%d (0 off, 2 decompress at the flip)\n", m);
#endif
		return m;
	}();
	return v;
}
struct Surface {
	int               index = -1;
	uint64_t          data = 0, meta = 0;
	uint32_t          w = 0, h = 0;
	bc5::dc439::Block block;         // as the title last set it, at a GFX job
	uint64_t          draws = 0;     // draws into it seen: a block from a draw wins over the job-end context
	bool              plain = false; // decompressed (or found plain) for the flip in flight
	uint64_t          flip_seq = 0;  // the order of its last flip (indices sharing a buffer: the latest decides)
};
static std::mutex                g_mu;
static std::vector<Surface>      g_surf;
static bc5::state_stack::Tracker g_tracker;
static std::vector<uint32_t>     g_io;
static std::atomic<bool>         g_any {false};
static bool                      g_code_ok = false;
static uint64_t                  g_vs_va = 0, g_ps_va = 0;
static uint64_t                  g_flip_seq = 0;
} // namespace dc439

static void dc439_track(const uint32_t* ib, uint32_t n, const bc5::policy::FilterOptions& opt, int ring) {
	if (dc439::mode() == 0 || !dc439::g_any.load(std::memory_order_relaxed) || ring != bc5::direct::kGfxRing || ib == nullptr || n == 0) return;
	std::lock_guard lk(dc439::g_mu);
	auto readable = [&opt](uint64_t a, uint64_t b) { return opt.mapped && opt.mapped(a, b); };
	{ // the per-draw catcher, from the tracker's context at the job's start
		static bc5::dc439::Ctx cx;
		const auto&            c0 = dc439::g_tracker.context();
		for (uint32_t r = 0; r < 0x400; r++) {
			cx.value[r] = c0.value[r];
			cx.valid[r] = c0.valid.test(r);
		}
		std::vector<uint64_t>        addrs;
		std::vector<bc5::dc439::Hit> hits(dc439::g_surf.size());
		for (const auto& s: dc439::g_surf) addrs.push_back(s.data);
		bc5::dc439::walk_draws(ib, n, cx, addrs, hits, readable);
		for (size_t k = 0; k < dc439::g_surf.size(); k++) {
			auto& s = dc439::g_surf[k];
			if (hits[k].draws == 0) continue;
			s.block = hits[k].block;
			s.draws += hits[k].draws;
		}
	}
	dc439::g_io.assign(ib, ib + n);
	bc5::state_stack::Stats st;
	dc439::g_tracker.apply_in_place(std::span<const uint32_t>(ib, n), dc439::g_io, opt.mapped, st);
	const auto& c = dc439::g_tracker.context();
	for (auto& s: dc439::g_surf) {
		if (s.draws != 0) continue; // a block from a draw wins over the job-end context
		const auto b = bc5::dc439::find(c.value, c.valid, s.data);
		if (b.valid) s.block = b;
	}
}

// The title flips buffer `index`: a registered compressed surface is decompressed in place first.
static void dc439_flip(int index) {
	if (dc439::mode() != 2 || !dc439::g_any.load()) return;
	dc439::Surface s;
	{
		std::lock_guard lk(dc439::g_mu);
		auto it = std::find_if(dc439::g_surf.begin(), dc439::g_surf.end(), [index](const dc439::Surface& x) { return x.index == index; });
		if (it == dc439::g_surf.end()) return;
		it->plain    = false;
		it->flip_seq = ++dc439::g_flip_seq;
		s            = *it;
	}
	{ // the keys first. Mesa 0866ae7085c1 src/amd/common/ac_descriptors.h: 0xFF DCC_UNCOMPRESSED, 0x00 DCC_CLEAR_0000
	  // ("all bits are 0"); one key byte per 256 B (MAX_UNCOMPRESSED 256B)
		const uint64_t keys = static_cast<uint64_t>(s.w) * s.h * 4u / 256u;
		const auto*    meta = reinterpret_cast<const volatile uint8_t*>(s.meta);
		uint64_t       n00 = 0, nff = 0;
		for (uint64_t k = 0; k < keys; k++) {
			const uint8_t v = meta[k];
			n00 += v == 0x00;
			nff += v == 0xFF;
		}
		bool plain = nff == keys;
		if (!plain && n00 == keys) { // a cleared surface nothing drew into yet (exp 0439 p1b)
			const auto*    px = reinterpret_cast<const volatile uint64_t*>(s.data);
			const uint64_t nq = static_cast<uint64_t>(s.w) * s.h * 4u / 8u;
			uint64_t       nz = 0;
			for (uint64_t k = 0; k < nq && nz == 0; k++) nz += px[k] != 0;
			plain = nz == 0;
		}
		if (plain) {
			std::lock_guard lk(dc439::g_mu);
			for (auto& x: dc439::g_surf)
				if (x.index == index) x.plain = true;
			return;
		}
	}
	// the colour target's own registers are what the GPU used: a block whose BASE is the surface and whose DCC is on (its
	// DCC_BASE may differ from the registered metadata: the registered metadata - 0x28000 for this title)
	if (!s.block.valid || !s.block.dcc_enable() || s.block.base() != s.data) return; // no matching block: presented as before
	if (!dc439::g_code_ok) {
		auto* code = static_cast<volatile uint32_t*>(g_dev ? g_dev->code_area() : nullptr);
		if (code == nullptr) {
			static std::atomic<bool> said {false};
			if (!said.exchange(true)) std::fprintf(stderr, "[bc5] exp 0439 (tag dc439): decompress FAILED: no code area for its programs; the present reads the surface compressed\n");
			return;
		}
		constexpr uint64_t kOff = 7ull << 20; // the code area's last MiB; exp 0137/0141 use its start and +4 MiB
		for (size_t k = 0; k < bc5::dc439::kVs.size(); k++) code[kOff / 4 + k] = bc5::dc439::kVs[k];
		for (size_t k = 0; k < bc5::dc439::kPs.size(); k++) code[(kOff + 256) / 4 + k] = bc5::dc439::kPs[k];
		std::atomic_thread_fence(std::memory_order_seq_cst);
		dc439::g_vs_va   = bc5::direct::Device::kCodeVa + kOff;
		dc439::g_ps_va   = bc5::direct::Device::kCodeVa + kOff + 256;
		dc439::g_code_ok = true;
	}
	static std::vector<uint32_t> ib; // kept until the drain below
	ib = bc5::dc439::build(s.block, s.w, s.h, dc439::g_vs_va, dc439::g_ps_va); // CB_SHADER_MASK 0xf (dc0439.hpp, items 38-40)
	drain(); // the frame's jobs on every ring are done: the surface holds the title's last write
	const uint64_t ok_before = g_ok.load();
	submit_now(ib.data(), static_cast<uint32_t>(ib.size()), "dc439", bc5::direct::kGfxRing, nullptr);
	drain();
	const bool ok = g_dev && !g_dev->wedged() && g_ok.load() > ok_before;
	{
		std::lock_guard lk(dc439::g_mu);
		for (auto& x: dc439::g_surf)
			if (x.index == index) x.plain = ok;
	}
	if (!ok) {
		static std::atomic<uint64_t> n_failed {0};
		const uint64_t               k = n_failed++;
		if (k < 16 || (k & 1023u) == 0)
			std::fprintf(stderr, "[bc5] exp 0439 (tag dc439): decompress of index %d (surface 0x%" PRIx64 ") FAILED (%" PRIu64 " failed so far); the present reads it compressed\n", index, s.data, k + 1);
	}
}
'''
a = '#else\nstatic void init_once() {}\nstatic void submit(const uint32_t*, uint32_t, const char*) {}\n'
s = rep(s, a, GLUE + '#else\nstatic void dc439_flip(int) {}\nstatic void init_once() {}\nstatic void submit(const uint32_t*, uint32_t, const char*) {}\n')
a = ('\t\tLOGF("[bc5-gc] VideoOutSubmitEopFlip(%d, %d, %d, 0x%" PRIx64 ", %p)\\n", handle, index,\n'
     '\t\t     flip_mode, flip_arg, unk);\n\t}\n')
s = rep(s, a, a + '\tBc5Gc::Direct::dc439_flip(index); // exp 0439 (tag dc439): a compressed display buffer decompressed in place\n')

TAIL = r'''
// exp 0439 (tag dc439): called by VideoOut (videoOut.cpp) for a registered compressed buffer and at the present.
#if defined(KYTY_BC5_DIRECT)
extern "C" void bc5_dc439_register(int index, uint64_t data, uint64_t meta, uint32_t w, uint32_t h, uint32_t dcc, uint64_t fmt) {
	(void)dcc;
	(void)fmt;
	if (Libs::Bc5Gc::Direct::dc439::mode() == 0) return;
	std::lock_guard lk(Libs::Bc5Gc::Direct::dc439::g_mu);
	auto& v = Libs::Bc5Gc::Direct::dc439::g_surf;
	v.erase(std::remove_if(v.begin(), v.end(), [index](const Libs::Bc5Gc::Direct::dc439::Surface& x) { return x.index == index; }), v.end());
	Libs::Bc5Gc::Direct::dc439::Surface s;
	s.index = index;
	s.data  = data;
	s.meta  = meta;
	s.w     = w;
	s.h     = h;
	v.push_back(s);
	Libs::Bc5Gc::Direct::dc439::g_any = true;
}
extern "C" int bc5_dc439_plain(uint64_t data) {
	if (Libs::Bc5Gc::Direct::dc439::mode() != 2) return 0;
	std::lock_guard lk(Libs::Bc5Gc::Direct::dc439::g_mu);
	// several indices share one buffer (0, 2, 4 and 1, 3, 5 for the third title): the one flipped last decides
	const Libs::Bc5Gc::Direct::dc439::Surface* last = nullptr;
	for (const auto& x: Libs::Bc5Gc::Direct::dc439::g_surf)
		if (x.data == data && x.flip_seq != 0 && (last == nullptr || x.flip_seq > last->flip_seq)) last = &x;
	return last != nullptr && last->plain ? 1 : 0;
}
#else
extern "C" void bc5_dc439_register(int, uint64_t, uint64_t, uint32_t, uint32_t, uint32_t, uint64_t) {}
extern "C" int  bc5_dc439_plain(uint64_t) { return 0; }
#endif
'''
s += TAIL

# ---- videoOut.cpp ----
v = rd(os.path.join(orig, 'videoOut.cpp'))
a = 'extern "C" double Bc5OsdTitleFps(double* frame_ms) {'
v = rep(v, a, 'extern "C" void bc5_dc439_register(int index, uint64_t data, uint64_t meta, uint32_t w, uint32_t h, uint32_t dcc, uint64_t fmt); // exp 0439 (tag dc439)\n'
        'extern "C" int  bc5_dc439_plain(uint64_t data); // exp 0439 (tag dc439)\n' + a)
a = ('\t\tLOGF("\\tbuffers[%d] = %016" PRIx64 " metadata = %016" PRIx64 " dcc = %08" PRIx32 "\\n",\n'
     '\t\t     buffer_index_start + i, buffer.data_address, buffer.metadata_address,\n'
     '\t\t     attribute->dcc_control);\n')
v = rep(v, a, a + '\t\tif (category == VIDEO_OUT_BUFFER_ATTRIBUTE_CATEGORY_COMPRESSED) { // exp 0439 (tag dc439)\n'
        '\t\t\tbc5_dc439_register(buffer_index_start + i, buffer.data_address, buffer.metadata_address, attribute->width,\n'
        '\t\t\t                   attribute->height, attribute->dcc_control, attribute->pixel_format);\n\t\t}\n')
a = ('\t\tif (bc5_direct && source_info.data.Valid()) {\n'
     '\t\t\tLibKernel::Memory::InvalidateMemory(source_info.data.address, source_info.data.size);\n\t\t}\n')
v = rep(v, a, a + '\t\t// exp 0439 (tag dc439): a compressed surface decompressed in place at its flip is read as plain bytes.\n'
        '\t\tif (bc5_direct && source_info.metadata.compression != Graphics::VideoOutCompression::Uncompressed &&\n'
        '\t\t    bc5_dc439_plain(source_info.data.address) != 0) {\n'
        '\t\t\tsource_info.metadata = {};\n\t\t}\n')

# ---- switch_defaults.hpp ----
h = rd(sdh)
for w in ('"BC5_DIRECT_IB_CHAIN"', '"BC5_DIRECT_IB_CHAIN_FLAT"', '"BC5_DIRECT_AGC_EOP_IDENT"', '"BC5_DIRECT_DCC_PRESENT"',
          '"BC5_DIRECT_EAGER_GPU_WRITE"', 'BC5_T3'):
    assert h.count(w) == 0, w + ' is already in switch_defaults.hpp'
k_soft = 'inline constexpr Default kSoft[] = {'
k_title = 'inline constexpr TitleDefault kTitleDefaults[] = {'
assert h.count(k_soft) == 1 and h.count(k_title) == 1
# the end of kSoft: its last row and the terminator, the indentation as found
ms = list(re.finditer(r'^([ \t]*)\{"BC5_DIRECT_ACB_SPLIT_LATE", "3"\},\n([ \t]*)\{nullptr, nullptr\}\};\n', h, re.M))
assert len(ms) == 1, ('kSoft end', len(ms))
m = ms[0]
assert h.index(k_soft) < m.start() and '{nullptr, nullptr}' not in h[h.index(k_soft):m.start()], 'the anchor is not the end of kSoft'
ind = m.group(1)
soft_rows = (ind + '{"BC5_DIRECT_IB_CHAIN", "1"},        // exp 0439 (ib439): a chained IB ends its caller\'s buffer at its depth (the chain cut, README item 26)\n'
             + ind + '{"BC5_DIRECT_IB_CHAIN_FLAT", "1"},   // exp 0439 (fl439): a top-level chain laid out flat (the flat compute chain, item 33)\n'
             + ind + '{"BC5_DIRECT_AGC_EOP_IDENT", "1"},   // exp 0439 (ae439, F890): end-of-pipe interrupts with the AGC idents (items 23, 36)\n'
             + ind + '{"BC5_DIRECT_FLAT_APERTURE", "1"},   // exp 0190 (F249) for every title since exp 0439 (F893): BVH stack pushes, by pattern (items 46-47)\n')
cut = m.start() + len(m.group(0).split('\n')[0]) + 1  # after the SPLIT_LATE row
h = h[:cut] + soft_rows + h[cut:]
# exp 0439: the second title's own FLAT_APERTURE row goes; kSoft carries the word for every title (same value: TITLE2 unchanged)
t2 = re.findall(r'^[ \t]*\{BC5_T2, "BC5_DIRECT_FLAT_APERTURE", "1"\},[^\n]*\n', h, re.M)
assert len(t2) == 1, ('the TITLE2 FLAT_APERTURE row', len(t2))
h = h.replace(t2[0], '')
a = '#define BC5_T2 "TITLE2"\n'
assert h.count(a) == 1 and h.index(a) < h.index(k_title), 'BC5_T2 define'
h = rep(h, a, a + '#define BC5_T3 "TITLE3" // exp 0439: the third title\n')
mt = re.search(re.escape(k_title) + r'\n(?:[ \t]*//[^\n]*\n)*([ \t]*)\{BC5_T', h) # comment lines may follow the header
assert mt is not None, 'kTitleDefaults: no row after its header'
ti = mt.group(1)
title_rows = (ti + '{BC5_T3, "BC5_DIRECT_DCC_PRESENT", "2"},     // exp 0439 (dc439, F891): the DCC display surface decompressed at its flip (items 10-14, 38-40)\n'
              + ti + '{BC5_T3, "BC5_DIRECT_EAGER_GPU_WRITE", "1"}, // exp 0439 (mw439): GPU-writable direct views imported whole (items 8, 11)\n')
h = rep(h, k_title + '\n', k_title + '\n' + title_rows)

# ---- output ----
for name, t in (('bc5LleAgc.cpp', s), ('videoOut.cpp', v), ('switch_defaults.hpp', h)):
    # no line ending inside a C string: a line whose quotes do not pair (ignoring escaped quotes and char literals)
    for ln, line in enumerate(t.split('\n'), 1):
        if 'exp 0439' not in line and '0439' not in line:
            continue
        code = re.sub(r"'(\\.|[^'\\])'", "''", line.split('//')[0] if line.count('"') == 0 else line)
        q = len(re.findall(r'(?<!\\)"', code))
        assert q % 2 == 0, (name, ln, line[:120])
os.makedirs(out, exist_ok=True)
wr(os.path.join(out, 'bc5LleAgc.cpp'), s)
wr(os.path.join(out, 'videoOut.cpp'), v)
wr(os.path.join(out, 'switch_defaults.hpp'), h)
shutil.copyfile(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'dc0439.hpp'), os.path.join(out, 'dc0439.hpp'))
print('bk439: written bc5LleAgc.cpp, videoOut.cpp, switch_defaults.hpp, dc0439.hpp to', out)
