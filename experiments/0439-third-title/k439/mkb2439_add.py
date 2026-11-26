# BC5 exp 0439, bake 2 (tag b2439): the unit and header edits added to mkbk439.py's set, imported by mkb2439.py after
# mkbk439's edits ran on s (bc5LleAgc.cpp) and before the header is written. Every edit exactly once; no log line
# except one start-up line per switch, compiled out in lean.
#   pc439  BC5_DIRECT_PREFIX_CHAINS   the system prefix also for a dcb that draws only in chained or called pieces (F901)
#   cw439  BC5_DIRECT_CHAIN_WRITERS   register_label_writes for a job's chained and called pieces too (F899; bc5/cw0439.hpp)
#   lw439  BC5_DIRECT_WAIT_MS         the host's completion bound (fence wait and submit bound), 100..60000 ms, default 2000
#   fw439  (no word)                  the umr watchdog's wait start per completion thread, the oldest decides (a watchdog bug)


def apply_unit(s, rep):
    s = rep(s, '#include "bc5/state_stack.hpp" // exp 0439 (tag dc439): the GFX ring\'s context, followed on the host\n',
            '#include "bc5/state_stack.hpp" // exp 0439 (tag dc439): the GFX ring\'s context, followed on the host\n'
            '#include "bc5/cw0439.hpp"      // exp 0439 (tag cw439): the chain-following writer scan\n')
    # ---- pc439 ----
    s = rep(s, '''static std::vector<uint32_t> sx_prefix(const bc5::full_state::Tracker& t) {''', r'''// exp 0439 (tag pc439, BC5_DIRECT_PREFIX_CHAINS=1, set by switch_defaults.hpp kSoft; F901): the draw test that gates the
// system prefix (experiment 0157, mode 2 "draws") reads the top level only; a dcb that draws only in chained or called
// pieces (the third title's frames) got no TF ring, offchip, start-state or GS-ring rows. The test also walks the chain.
static bool pc439_on() {
	static const bool v = [] {
		const char* e  = std::getenv("BC5_DIRECT_PREFIX_CHAINS");
		const bool  on = e != nullptr && e[0] == '1' && e[1] == 0;
#ifndef BC5_LEAN
		std::fprintf(stderr, "[bc5] exp 0439 (tag pc439): BC5_DIRECT_PREFIX_CHAINS=%d\n", on ? 1 : 0);
#endif
		return on;
	}();
	return v;
}
static bool pc439_chain_draw(const uint32_t* ib, uint32_t num_dwords) {
	const auto pm = g_dev ? g_dev->sorted_mappings() : nullptr;
	if (pm == nullptr) return false;
	const auto cr = bc5::ib_chain::collect(ib, num_dwords, [&pm](uint64_t a, uint64_t b) { return covered_sorted(*pm, a, b); }, true);
	for (size_t k = 1; k < cr.pieces.size(); k++)
		if (ib_has_draw(cr.pieces[k].src, cr.pieces[k].n)) return true;
	return false;
}
static std::vector<uint32_t> sx_prefix(const bc5::full_state::Tracker& t) {''')
    s = rep(s, '''	if (prefix_all() && std::strcmp(kind, "dcb") == 0 && (prefix_mode() == 1 || ib_has_draw(ib, num_dwords))) { // experiment 0157''',
            '''	if (prefix_all() && std::strcmp(kind, "dcb") == 0 && (prefix_mode() == 1 || ib_has_draw(ib, num_dwords) || (pc439_on() && pc439_chain_draw(ib, num_dwords)))) { // experiment 0157; exp 0439 (tag pc439)''')
    # ---- cw439 ----
    s = rep(s, '''		register_label_writes(ib, num_dwords, r.executed_offsets, r.seq_no, r.ring); // experiment 0055
''', r'''		register_label_writes(ib, num_dwords, r.executed_offsets, r.seq_no, r.ring); // experiment 0055
		{ // exp 0439 (tag cw439, BC5_DIRECT_CHAIN_WRITERS=1, set by switch_defaults.hpp kSoft; F899): the job's chained and
		  // called pieces registered too, under the same seq and ring (bc5/cw0439.hpp)
			static const bool cw439 = [] {
				const char* e = std::getenv("BC5_DIRECT_CHAIN_WRITERS");
				const bool  v = e != nullptr && e[0] == '1' && e[1] == 0;
#ifndef BC5_LEAN
				std::fprintf(stderr, "[bc5] exp 0439 (tag cw439): BC5_DIRECT_CHAIN_WRITERS=%d\n", v ? 1 : 0);
#endif
				return v;
			}();
			if (cw439 && g_dev) {
				const auto mp = g_dev->sorted_mappings();
				bc5::cw439::each_piece(ib, num_dwords, [&mp](uint64_t a, uint64_t b) { return covered_sorted(*mp, a, b); },
				                       [&](const uint32_t* src, uint32_t pn, const std::vector<uint32_t>& st) { register_label_writes(src, pn, st, r.seq_no, r.ring); });
			}
		}
''')
    # ---- lw439 ----
    s = rep(s, '''// Experiment 0058: the kernel resets the gfx ring ~2 s after a job hangs on it''', r'''// exp 0439 (tag lw439): BC5_DIRECT_WAIT_MS=<ms> (100..60000, default 2000): the host's completion bound, the job
// finisher's fence wait and the bound of the submits, so that with a longer kernel bound (amdgpu.lockup_timeout) the
// kernel decides, not the host. Anything else keeps 2000.
static uint64_t lw439_wait_ns() {
	static const uint64_t v = [] {
		uint64_t ms = 2000;
		if (const char* e = std::getenv("BC5_DIRECT_WAIT_MS"); e != nullptr && *e != 0) {
			char*          end = nullptr;
			const uint64_t x   = std::strtoull(e, &end, 10);
			if (end != nullptr && *end == 0 && x >= 100 && x <= 60000) ms = x;
		}
#ifndef BC5_LEAN
		if (ms != 2000) std::fprintf(stderr, "[bc5] exp 0439 (tag lw439): completion bound %" PRIu64 " ms\n", ms);
#endif
		return ms * 1'000'000ull;
	}();
	return v;
}
// exp 0439 (tag fw439): each completion thread's wait start; the watchdog takes the oldest (one global, set by every
// thread at its wait, measured whichever ring began a wait last: a compute ring's fresh job hid a hung GFX dcb)
static std::atomic<uint64_t> g_fw439[16] = {};
static void fw439_set(int index, uint64_t v) {
	if (index >= 0 && index < 16) g_fw439[index] = v;
}
static uint64_t fw439_oldest() {
	uint64_t m = 0;
	for (const auto& a: g_fw439) {
		const uint64_t x = a.load();
		if (x != 0 && (m == 0 || x < m)) m = x;
	}
	return m;
}
// Experiment 0058: the kernel resets the gfx ring ~2 s after a job hangs on it''')
    s = rep(s, '''				static constexpr uint64_t fence_ns = 2'000'000'000ull;''', '''				const uint64_t fence_ns = lw439_wait_ns(); // exp 0439 (tag lw439): was 2 s''')
    s = rep(s, '''		r = g_dev->submit(std::span<const uint32_t>(sub_ib, sub_n), opt, 2'000'000'000ull, true, qring, unlock_dev);''',
            '''		r = g_dev->submit(std::span<const uint32_t>(sub_ib, sub_n), opt, lw439_wait_ns(), true, qring, unlock_dev); // exp 0439 (tag lw439)''')
    s = rep(s, '''		r = g_dev->submit(std::span<const uint32_t>(sub_ib, sub_n), opt, 2'000'000'000ull, true, qring);
''', '''		r = g_dev->submit(std::span<const uint32_t>(sub_ib, sub_n), opt, lw439_wait_ns(), true, qring); // exp 0439 (tag lw439)
''')
    s = rep(s, '''		r       = g_dev->submit(std::span<const uint32_t>(sub_ib, sub_n), opt, 2'000'000'000ull, true, qring);''',
            '''		r       = g_dev->submit(std::span<const uint32_t>(sub_ib, sub_n), opt, lw439_wait_ns(), true, qring); // exp 0439 (tag lw439)''')
    # ---- fw439 ----
    s = rep(s, '''				const uint64_t t0 = g_fence_wait_since.load();''', '''				const uint64_t t0 = fw439_oldest(); // exp 0439 (tag fw439): the oldest wait of any completion thread''')
    s = rep(s, '''					while (g_fence_wait_since.load() == t0) std::this_thread::sleep_for(std::chrono::milliseconds(20));''',
            '''					while (fw439_oldest() == t0) std::this_thread::sleep_for(std::chrono::milliseconds(20)); // exp 0439 (tag fw439)''')
    s = rep(s, '''				g_fence_wait_since = j.queued_ns != 0 ? j.queued_ns : SoftCp::now_ns(); // from the job's submission: the kernel resets ~2 s after it hangs''',
            '''				g_fence_wait_since = j.queued_ns != 0 ? j.queued_ns : SoftCp::now_ns(); // from the job's submission: the kernel resets ~2 s after it hangs
				fw439_set(index, g_fence_wait_since.load()); // exp 0439 (tag fw439)''')
    s = rep(s, '''				g_fence_wait_since = 0;
''', '''				g_fence_wait_since = 0;
				fw439_set(index, 0); // exp 0439 (tag fw439)
''')
    # ---- exp 0438's two items for the next bake (exp 0444's mkb2_0438.py at 57b322fc; tags r438h, kept438) ----
    s = rep(s, '''static void r438_begin(const uint32_t* s1, uint32_t n1, const uint32_t* s2, uint32_t n2) {\n\tif (!r438_on()) return;\n''',
            '''static void r438_begin(const uint32_t* s1, uint32_t n1, const uint32_t* s2, uint32_t n2) {\n\tif (!r438_on() || !g_async) return; // exp 0438 (r438h): sync mode registers no pending write, so nothing early\n''')
    s = rep(s, '''#ifndef BC5_LEAN\n\tg_r438o_trims++;\n\tg_r438o_kept += kept;\n#endif\n''',
            '''#ifndef BC5_LEAN\n\tg_r438o_trims++;\n\tg_r438o_kept += kept;\n#else\n\t(void)kept; // exp 0438 (kept438): its counter is compiled out in lean\n#endif\n''')
    return s


# the rows for every title at kSoft's end (after mkbk439's four), and the two second-title rows that move there
SOFT_ROWS = [
    ('BC5_DIRECT_DMA_SYNC', '1', 'exp 0050 for every title since exp 0439 bake 2 (moved from TITLE2; F104/F107)'),
    ('BC5_DIRECT_DMA_SYNC_MEC', '1', 'exp 0439 (ds439 D): the same wait on the compute rings'),
    ('BC5_DIRECT_DMA_SYNC_LABEL', '1', 'exp 0439 (ds439 D2): before a label write and at a buffer\'s end'),
    ('BC5_DIRECT_PREFIX_CHAINS', '1', 'exp 0439 (pc439, F901): the system prefix for dcbs that draw only in chained pieces'),
    ('BC5_DIRECT_CHAIN_WRITERS', '1', 'exp 0439 (cw439, F899): label writers registered in chained and called pieces'),
    ('KYTY_BC5_AT9_DMC', '1', 'exp 0439 (dm439, F892): ATRAC9 DMC configs (sync 0x30) through vgmstream'),
    ('BC5_DIRECT_EAGER_GPU_WRITE', '1', 'exp 0439 (mw439): a direct view mapped with GPU write imported whole at the map call, every title (11-23, the top session; =0 turns it off)'),
    ('BC5_DIRECT_DCC_PRESENT', '2','exp 0439 (dc439, F891): a DCC display surface decompressed in place at its flip, every title (11-23, the top session; =0 turns it off)'),
]
MOVED_FROM_T2 = ['BC5_DIRECT_DMA_SYNC']
