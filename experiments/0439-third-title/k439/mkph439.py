# BC5 exp 0439 (tag ph439; the top session's order of 11-23 after the mode-3 slot): the graphics buffer's hold for its
# open piece waits. Run after mkpw439.py in prep439d.sh:   python3 -I mkph439.py <unit in> <unit out>
#
# What the console does there: the GFX CP walks the dcb's chained IBs in order and, at a WAIT_REG_MEM on memory, stalls
# the graphics queue until the label meets the compare (PM4 WAIT_REG_MEM, Mesa sid.h PKT3_WAIT_REG_MEM 0x3c; exp 0439's
# frame captures: ~20 such waits per GFX frame on labels the acbs release on the compute queues); the compute queues
# run beside it and release the label. Nothing on the console holds the buffer on the CPU, and nothing drops the wait.
# Here mode 3 (pw439) keeps such a wait only when its writer is already in the kernel; the mode-3 slot measured ~19
# per frame with no submitted writer at filter time (all on the GFX ring), dropped, and the black character unchanged.
# The writer is then work another thread submits a moment later (exp 0428 iteration 6 measured the same for root waits:
# the ring thread's acb arrives within the poll).
#
# The form (BC5_0439_PIECE_HOLD, on unless "0", acts only with BC5_0439_PIECE_WAITS=3, normal and lean): exactly the
# treatment exp 0428 (SPLIT_LATE=3) gives a dcb's root wait, applied to its piece waits, before the buffer goes:
#   - in submit_split, for a dcb on the game thread with the acb rings on and the device not wedged, the pieces are
#     collected as the backend's filter will see them (bc5::ib_chain::collect) and their open waits found
#     (pw0439.hpp: not written earlier in the same piece, not written anywhere in the job);
#   - if one is neither met nor proven by a submitted writer (the mode-3 hook's answer), the thread's held chain goes
#     first (chain_flush, ADR 0010: the writer may wait for those earlier buffers), then the waits are polled every
#     20 us: each ends when the hook proves it (the GPU keeps it, as the console's CP does) or memory meets it;
#   - cycle: the ring thread is blocked (g_unready_label) on a label this job writes: the writer cannot come before
#     this buffer; the hold ends and the remaining waits are dropped as today (exp 0132's cycle rule, as for root waits);
#   - bound: 8 ms for the whole buffer (exp 0428's bound); the remaining waits are dropped as today. Each cycle and
#     each timeout is journaled (the first 64 with label and pending writes); none is silent;
#   - the hook is asked again at filter time, so a wait proven during the hold is kept by the filter.
# No title, no learned list: the decision reads only this buffer, the host's pending-write table and memory.
# Counts (normal build): per 64 flips, per frame: open waits held, proven (and the mean/max wait in us, and the writer's
# ring), met, cycles, timeouts; the hold's total time per frame.
import sys

src, dst = sys.argv[1], sys.argv[2]
s = open(src, encoding='utf-8', newline='').read()


def rep(tag, a, b):
    global s
    assert s.count(a) == 1, (tag, s.count(a))
    s = s.replace(a, b)


rep('include', '#include "bc5/sr0439b.hpp" // exp 0439 (tag sr439b): the frame-dump catcher\n',
    '#include "bc5/sr0439b.hpp" // exp 0439 (tag sr439b): the frame-dump catcher\n#include "bc5/pw0439.hpp" // exp 0439 (tag ph439): the open piece waits\n')

A = '// ---- end of exp 0439 (tag pw439, mode 3)\n'
rep('hold', A, A + '''// ---- exp 0439 (tag ph439): the dcb's hold for its open piece waits (mkph439.py)
static bool ph439_on() {
	static const bool on = [] {
		const char* w = std::getenv("BC5_0439_PIECE_WAITS");
		const char* h = std::getenv("BC5_0439_PIECE_HOLD");
		const bool  v = w != nullptr && w[0] == '3' && w[1] == 0 && !(h != nullptr && h[0] == '0' && h[1] == 0);
		std::fprintf(stderr, "[bc5] exp 0439 (tag ph439): the dcb hold for open piece waits %s\\n", v ? "ON (BC5_0439_PIECE_HOLD=0 turns it off)" : "off");
		return v;
	}();
	return on;
}
static int ph439_writer_ring(uint64_t label) {
	std::unique_lock<std::mutex> lk(g_plw_mutex, std::defer_lock);
	if (!lk.try_lock()) return -9;
	const PendingLabelWrite* last = nullptr;
	for (const auto& w: g_plw)
		if (w.label == label && (w.seq & kR438Early) == 0 && (last == nullptr || w.order >= last->order)) last = &w;
	return last != nullptr ? last->ring : -9;
}
// [0] buffers held, [1] open waits held, [2] proven, [3] met, [4] cycles (waits dropped by them), [5] timeouts (waits),
// [6] ns waited for proven waits, [7] max ns of one, [8] ns the buffers were held, [9..13] writer ring -1 (gfx), 0..3
static std::atomic<uint64_t> g_ph439[14] = {};
static void ph439_hold(const uint32_t* ib, uint32_t num_dwords) {
	if (!ph439_on() || !on_game_thread() || w428_rings() == 0 || !g_dev || g_dev->wedged()) return;
	const auto pm = g_dev->sorted_mappings();
	if (pm == nullptr) return;
	const auto cr = bc5::ib_chain::collect(ib, num_dwords, [&pm](uint64_t a, uint64_t b) { return covered_sorted(*pm, a, b); }, true);
	if (cr.pieces.size() <= 1) return;
	std::vector<uint64_t> job;
	for (const auto& q: cr.pieces) bc5::pw439::labels_written(std::span<const uint32_t>(q.src, q.n), job);
	std::sort(job.begin(), job.end());
	struct W {
		const uint32_t* p;
		bool            is64;
		uint64_t        label;
	};
	std::vector<W> open;
	for (size_t k = 1; k < cr.pieces.size(); k++) {
		std::vector<bc5::pw439::OpenWait> ow;
		uint64_t                          same = 0;
		bc5::pw439::open_waits(std::span<const uint32_t>(cr.pieces[k].src, cr.pieces[k].n), ow, same);
		for (const auto& w: ow) {
			if (std::binary_search(job.begin(), job.end(), w.label)) continue; // the same job: the filter drops it (mode 3)
			const uint32_t* p = cr.pieces[k].src + w.off;
			const int       r = bc5_pw439_piece_wait(p, w.is64 ? 1 : 0, bc5::direct::kGfxRing);
			if (r == 1 || r == 2) continue; // already proven or met: the filter keeps it
			open.push_back({p, w.is64, w.label});
		}
	}
	if (open.empty()) return;
	chain_flush(1); // ADR 0010: the thread's earlier buffers go first (the writer may wait for them)
	const uint64_t t0 = SoftCp::now_ns();
	g_ph439[0]++;
	g_ph439[1] += open.size();
	size_t k = 0;
	int    end = 0; // 0 all served, 1 cycle, 2 timeout
	for (; k < open.size(); k++) {
		const W&       w  = open[k];
		const uint64_t tw = SoftCp::now_ns();
		for (;;) {
			const int r = bc5_pw439_piece_wait(w.p, w.is64 ? 1 : 0, bc5::direct::kGfxRing);
			if (r == 1 || r == 2) {
				const uint64_t d = SoftCp::now_ns() - tw;
				g_ph439[r == 1 ? 2 : 3]++;
				if (r == 1) {
					g_ph439[6] += d;
					for (uint64_t m = g_ph439[7].load(); d > m && !g_ph439[7].compare_exchange_weak(m, d);) {
					}
					const int ring = ph439_writer_ring(w.label);
					if (ring >= -1 && ring <= 3) g_ph439[10 + ring]++;
				}
				break;
			}
			const uint64_t blocked = g_unready_label.load();
			if (blocked != 0 && std::binary_search(job.begin(), job.end(), blocked)) {
				end = 1;
				break;
			}
			if (SoftCp::now_ns() - t0 >= 8'000'000ull) {
				end = 2;
				break;
			}
			std::this_thread::sleep_for(std::chrono::microseconds(20));
		}
		if (end != 0) break;
	}
	g_ph439[8] += SoftCp::now_ns() - t0;
	if (end != 0) {
		g_ph439[end == 1 ? 4 : 5] += open.size() - k;
#ifndef BC5_LEAN
		static std::atomic<uint32_t> n_said {0};
		if (n_said++ < 64) {
			char pend[160];
			describe_pending(open[k].label, pend, sizeof(pend));
			journal("ph439 (exp 0439): dcb %u dwords: the hold for %zu open piece waits ended by %s after %.2f ms at the wait on 0x%" PRIx64 " (%zu left, dropped as today): %s%s\\n", num_dwords, open.size(),
			        end == 1 ? "a cycle (the ring thread waits for a label this buffer writes)" : "the 8-ms bound", static_cast<double>(SoftCp::now_ns() - t0) / 1e6, open[k].label, open.size() - k, pend,
			        end == 1 ? "" : "; a bug to explain, not a fix");
		}
#endif
	}
}
#ifndef BC5_LEAN
static void ph439_flip() {
	if (!ph439_on()) return;
	static uint64_t flips = 0, last[14] = {};
	if ((++flips & 63u) != 0) return;
	uint64_t now[14];
	for (int k = 0; k < 14; k++) now[k] = g_ph439[k].load();
	uint64_t d[14];
	for (int k = 0; k < 14; k++) d[k] = now[k] - last[k];
	for (int k = 0; k < 14; k++) last[k] = now[k];
	journal("ph439 (exp 0439): flips %" PRIu64 ", per frame over the last 64: dcbs held %.2f, open piece waits held %.2f: proven by a submitted writer %.2f (mean %.1f us, max so far %.1f us; writer ring gfx %.2f, "
	        "0 %.2f, 1 %.2f, 2 %.2f, 3 %.2f), met %.2f, dropped by a cycle %.2f, dropped at the 8-ms bound %.2f; held %.3f ms per frame\\n",
	        flips, d[0] / 64.0, d[1] / 64.0, d[2] / 64.0, d[2] != 0 ? static_cast<double>(d[6]) / d[2] / 1e3 : 0.0, static_cast<double>(now[7]) / 1e3, d[9] / 64.0, d[10] / 64.0, d[11] / 64.0, d[12] / 64.0,
	        d[13] / 64.0, d[3] / 64.0, d[4] / 64.0, d[5] / 64.0, static_cast<double>(d[8]) / 64.0 / 1e6);
}
#else
static void ph439_flip() {}
#endif
// ---- end of exp 0439 (tag ph439)
''')

rep('flip', '	pw439_flip();  // exp 0439 (tag pw439, mode 3)\n', '	pw439_flip();  // exp 0439 (tag pw439, mode 3)\n	ph439_flip();  // exp 0439 (tag ph439)\n')

rep('call', '''static void submit_split(const uint32_t* ib, uint32_t num_dwords, const char* kind) {
	t_wait_given_up = false;
''', '''static void submit_split(const uint32_t* ib, uint32_t num_dwords, const char* kind) {
	if (std::strcmp(kind, "dcb") == 0) ph439_hold(ib, num_dwords); // exp 0439 (tag ph439): before the buffer goes
	t_wait_given_up = false;
''')
open(dst, 'w', encoding='utf-8', newline='').write(s)
print('mkph439:', dst)
