# BC5 experiment 0439 (tag dc439): the private units from the shared tree's (patch 9889b06a) bc5LleAgc.cpp and
# videoOut.cpp. Every replacement must match exactly once.
#   python mk439.py <dir with the two originals> <out dir>
import sys

src, dst = sys.argv[1], sys.argv[2]


def rep(s, a, b, n=1):
    c = s.count(a)
    assert c == n, (a[:90], c)
    return s.replace(a, b)


GLUE = r'''
// ---- BC5 experiment 0439 (tag dc439): the third title's DCC display buffers (dcc-present-design.md) ----
// BC5_DIRECT_DCC_PRESENT (read in the lean build too): unset/0 off; 1 L1, log only: the GFX ring's context registers
// followed by a host state_stack::Tracker over every GFX job, the CB_COLORn block whose BASE is a registered compressed
// video-out surface remembered, logged at its flips; 2 L1 + D: at the title's flip of such a surface, after a drain,
// one host-built GFX job decompresses it in place (CB_DCC_DECOMPRESS, bc5/dc0439.hpp), a drain again, and the
// present reads it as uncompressed (bc5_dc439_plain).
namespace dc439 {
static int mode() {
	static const int v = [] {
		const char* e = std::getenv("BC5_DIRECT_DCC_PRESENT");
		const int   m = e != nullptr ? std::atoi(e) : 0;
		std::fprintf(stderr, "[bc5] exp 0439 (tag dc439): BC5_DIRECT_DCC_PRESENT=%d (0 off, 1 log, 2 decompress at the flip)\n", m);
		return m;
	}();
	return v;
}
struct Surface {
	int      index = -1;
	uint64_t data = 0, meta = 0, fmt = 0;
	uint32_t w = 0, h = 0, dcc = 0;
	bc5::dc439::Block block;         // as the title last set it, at a GFX job
	uint64_t          block_job = 0; // the tracked GFX job that set it
	uint64_t          flips = 0, done = 0, failed = 0, no_block = 0, logged = 0;
	bool              plain = false; // decompressed for the flip in flight
};
static std::mutex                g_mu;
static std::vector<Surface>      g_surf;
static bc5::state_stack::Tracker g_tracker;
static std::vector<uint32_t>     g_io;
static uint64_t                  g_jobs = 0;
static std::atomic<bool>         g_any {false};
static bool                      g_code_ok = false;
static uint64_t                  g_vs_va = 0, g_ps_va = 0;
} // namespace dc439

static void dc439_track(const uint32_t* ib, uint32_t n, const bc5::policy::FilterOptions& opt) {
	if (dc439::mode() == 0 || !dc439::g_any.load(std::memory_order_relaxed) || ib == nullptr || n == 0) return;
	std::lock_guard lk(dc439::g_mu);
	dc439::g_io.assign(ib, ib + n);
	bc5::state_stack::Stats st;
	dc439::g_tracker.apply_in_place(std::span<const uint32_t>(ib, n), dc439::g_io, opt.mapped, st);
	dc439::g_jobs++;
	const auto& c = dc439::g_tracker.context();
	for (auto& s: dc439::g_surf) {
		const auto b = bc5::dc439::find(c.value, c.valid, s.data);
		if (!b.valid) continue;
		s.block     = b;
		s.block_job = dc439::g_jobs;
	}
}

static void dc439_log(const dc439::Surface& s, const char* what) {
	const auto& b = s.block;
	std::fprintf(stderr,
	             "[bc5] exp 0439 (tag dc439): t %.3f s %s: index %d surface 0x%" PRIx64 " meta 0x%" PRIx64 " %ux%u dcc 0x%x; flips %" PRIu64 " done %" PRIu64 " failed %" PRIu64 " no-block %" PRIu64 "; "
	             "block %s (job %" PRIu64 " of %" PRIu64 "): MRT %u BASE 0x%" PRIx64 " DCC_BASE 0x%" PRIx64 " (%s the registered metadata) VIEW 0x%08x INFO 0x%08x (DCC_ENABLE %d, FORMAT %u, COMPRESSION %u, FAST_CLEAR %u) "
	             "ATTRIB 0x%08x DCC_CONTROL 0x%08x ATTRIB2 0x%08x ATTRIB3 0x%08x (SW_MODE %u, META_LINEAR %d, DCC_PIPE_ALIGNED %d) CMASK 0x%08x FMASK 0x%08x CB_DCC_CONTROL %s0x%08x\n",
	             timing_now(), what, s.index, s.data, s.meta, s.w, s.h, s.dcc, s.flips, s.done, s.failed, s.no_block, b.valid ? "found" : "NOT FOUND", s.block_job, dc439::g_jobs, b.mrt, b.base(), b.dcc_base(),
	             b.dcc_base() == s.meta ? "equals" : "DIFFERS FROM", b.c[3], b.c[4], b.dcc_enable() ? 1 : 0, (b.c[4] >> 2) & 0x1fu, (b.c[4] >> 14) & 1u, (b.c[4] >> 13) & 1u, b.c[5], b.c[6], b.attrib2, b.attrib3, b.sw_mode(),
	             b.meta_linear() ? 1 : 0, b.dcc_pipe_aligned() ? 1 : 0, b.c[7], b.c[9], b.cb_dcc_control_valid ? "" : "(unset) ", b.cb_dcc_control);
}

// The title flips buffer `index`: in mode 2, a registered compressed surface is decompressed in place first.
static void dc439_flip(int index) {
	const int m = dc439::mode();
	if (m == 0 || !dc439::g_any.load()) return;
	dc439::Surface s;
	{
		std::lock_guard lk(dc439::g_mu);
		auto it = std::find_if(dc439::g_surf.begin(), dc439::g_surf.end(), [index](const dc439::Surface& x) { return x.index == index; });
		if (it == dc439::g_surf.end()) return;
		it->flips++;
		it->plain = false;
		if (it->logged < 8 || (it->flips & 1023u) == 0) {
			it->logged++;
			dc439_log(*it, "flip");
		}
		s = *it;
	}
	if (m < 2) return;
	if (!s.block.valid || !s.block.dcc_enable() || s.block.dcc_base() != s.meta) {
		std::lock_guard lk(dc439::g_mu);
		for (auto& x: dc439::g_surf)
			if (x.index == index && x.no_block++ < 8) dc439_log(x, "NOT decompressed (no matching DCC block)");
		return;
	}
	if (!dc439::g_code_ok) {
		auto* code = static_cast<volatile uint32_t*>(g_dev ? g_dev->code_area() : nullptr);
		if (code == nullptr) return;
		constexpr uint64_t kOff = 7ull << 20; // the code area's last MiB; exp 0137/0141 use its start and +4 MiB
		for (size_t k = 0; k < bc5::dc439::kVs.size(); k++) code[kOff / 4 + k] = bc5::dc439::kVs[k];
		for (size_t k = 0; k < bc5::dc439::kPs.size(); k++) code[(kOff + 256) / 4 + k] = bc5::dc439::kPs[k];
		std::atomic_thread_fence(std::memory_order_seq_cst);
		dc439::g_vs_va   = bc5::direct::Device::kCodeVa + kOff;
		dc439::g_ps_va   = bc5::direct::Device::kCodeVa + kOff + 256;
		dc439::g_code_ok = true;
		std::fprintf(stderr, "[bc5] exp 0439 (tag dc439): decompress programs at 0x%" PRIx64 " (VS) and 0x%" PRIx64 " (PS)\n", dc439::g_vs_va, dc439::g_ps_va);
	}
	static std::vector<uint32_t> ib; // kept until the drain below
	ib = bc5::dc439::build(s.block, s.w, s.h, dc439::g_vs_va, dc439::g_ps_va);
	const double t0 = timing_now();
	drain(); // the frame's jobs on every ring are done: the surface holds the title's last write
	const double   t1        = timing_now();
	const uint64_t ok_before = g_ok.load();
	submit_now(ib.data(), static_cast<uint32_t>(ib.size()), "dc439", bc5::direct::kGfxRing, nullptr);
	drain();
	const double t2 = timing_now();
	const bool   ok = g_dev && !g_dev->wedged() && g_ok.load() > ok_before;
	std::lock_guard lk(dc439::g_mu);
	for (auto& x: dc439::g_surf) {
		if (x.index != index) continue;
		x.plain = ok;
		if (ok) x.done++;
		else x.failed++;
		if (x.done + x.failed <= 4 || !ok || ((x.done + x.failed) & 1023u) == 0) {
			std::fprintf(stderr, "[bc5] exp 0439 (tag dc439): t %.3f s decompress of index %d (0x%" PRIx64 ", %zu dwords): %s; drain before %.2f ms, the job and its drain %.2f ms\n", t2, index, x.data, ib.size(),
			             ok ? "OK" : "FAILED", (t1 - t0) * 1e3, (t2 - t1) * 1e3);
		}
	}
}
'''

TAIL = r'''
// exp 0439 (tag dc439): called by VideoOut (videoOut.cpp) for a registered compressed buffer and at the present.
extern "C" void bc5_dc439_register(int index, uint64_t data, uint64_t meta, uint32_t w, uint32_t h, uint32_t dcc, uint64_t fmt) {
	if (Bc5Gc::Direct::dc439::mode() == 0) return;
	std::lock_guard lk(Bc5Gc::Direct::dc439::g_mu);
	auto& v = Bc5Gc::Direct::dc439::g_surf;
	v.erase(std::remove_if(v.begin(), v.end(), [index](const Bc5Gc::Direct::dc439::Surface& x) { return x.index == index; }), v.end());
	Bc5Gc::Direct::dc439::Surface s;
	s.index = index;
	s.data  = data;
	s.meta  = meta;
	s.w     = w;
	s.h     = h;
	s.dcc   = dcc;
	s.fmt   = fmt;
	v.push_back(s);
	Bc5Gc::Direct::dc439::g_any = true;
	std::fprintf(stderr, "[bc5] exp 0439 (tag dc439): registered compressed buffer index %d: data 0x%" PRIx64 " metadata 0x%" PRIx64 " %ux%u dcc_control 0x%x pixel_format 0x%016" PRIx64 "\n", index, data, meta, w, h, dcc, fmt);
}
extern "C" int bc5_dc439_plain(uint64_t data) {
	if (Bc5Gc::Direct::dc439::mode() < 2) return 0;
	std::lock_guard lk(Bc5Gc::Direct::dc439::g_mu);
	for (const auto& x: Bc5Gc::Direct::dc439::g_surf)
		if (x.data == data) return x.plain ? 1 : 0;
	return 0;
}
'''

s = open(src + '/bc5LleAgc.cpp', encoding='utf-8', newline='').read()
s = rep(s, '#include "bc5/direct.hpp"\n',
        '#include "bc5/direct.hpp"\n'
        '#include "bc5/state_stack.hpp" // exp 0439 (tag dc439): the GFX ring\'s context, followed on the host\n'
        '#include "bc5/dc0439.hpp"      // exp 0439 (tag dc439): the DCC display buffers\n')
a = 'static void submit_now(const uint32_t* ib, uint32_t num_dwords, const char* kind, int ring, const Chain* chain);\n'
s = rep(s, a, a + 'static void dc439_track(const uint32_t* ib, uint32_t n, const bc5::policy::FilterOptions& opt); // exp 0439 (tag dc439)\n')
a = '\tconst uint64_t ls_t3 = SoftCp::now_ns(); // experiment 0415 (ls415c)\n\tbc5::direct::SubmitResult r;\n'
s = rep(s, a, '\tconst uint64_t ls_t3 = SoftCp::now_ns(); // experiment 0415 (ls415c)\n'
        '\tif (qring == bc5::direct::kGfxRing) dc439_track(sub_ib, sub_n, opt); // exp 0439 (tag dc439): before the job, under the device lock\n'
        '\tbc5::direct::SubmitResult r;\n')
a = '#else\nstatic void init_once() {}\nstatic void submit(const uint32_t*, uint32_t, const char*) {}\n'
s = rep(s, a, GLUE + '#else\nstatic void dc439_flip(int) {}\nstatic void init_once() {}\nstatic void submit(const uint32_t*, uint32_t, const char*) {}\n')
a = ('\t\tLOGF("[bc5-gc] VideoOutSubmitEopFlip(%d, %d, %d, 0x%" PRIx64 ", %p)\\n", handle, index,\n'
     '\t\t     flip_mode, flip_arg, unk);\n\t}\n')
s = rep(s, a, a + '\tBc5Gc::Direct::dc439_flip(index); // exp 0439 (tag dc439): a compressed display buffer decompressed in place (mode 2)\n')
s += TAIL
open(dst + '/bc5LleAgc.cpp', 'w', encoding='utf-8', newline='').write(s)

v = open(src + '/videoOut.cpp', encoding='utf-8', newline='').read()
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
open(dst + '/videoOut.cpp', 'w', encoding='utf-8', newline='').write(v)
print("ok")
