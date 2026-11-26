#!/usr/bin/env python3
# BC5 exp 0381: apply the BC5_DIRECT_ACB_STATE_RESTORE edits to a copy of bc5LleAgc.cpp (patch 0001's unit + exp 0379's
# diff, md5 e62113a5). The committed result is patch0381-bc5LleAgc.diff; this script is how it was made.
# usage: python mkpatch0381.py <in.cpp> <out.cpp>
import sys

s = open(sys.argv[1], "rb").read().decode("utf-8")


def rep(old, new):
    global s
    assert s.count(old) == 1, (s.count(old), old[:60])
    s = s.replace(old, new)


# The anchor: exp 0379's unit has the zero-skip include, patch 0001 on main does not.
anchor = '#include "bc5/zero_skip.hpp" // experiment 0379\n' if 'bc5/zero_skip.hpp' in s else '#include "bc5/full_state.hpp"\n'
rep(anchor, anchor + '#include "bc5/acb_restore.hpp" // experiment 0381\n')

rep("static bool ib_has_draw(const uint32_t* ib, uint32_t num_dwords) {\n",
    """// Experiment 0381 (F679): BC5_DIRECT_ACB_STATE_RESTORE=1: in front of every graphics buffer that dispatches (or calls
// an IB2) and gets no other prefix, the graphics queue's tracked compute registers (bc5::acb_restore::runs, the CS
// prefix's range without COMPUTE_VMID), in the buffer's own chain segment. With BC5_DIRECT_COMPUTE_RING=-1 the title's
// compute buffers share the GFX ring's COMPUTE_* registers; a graphics buffer that inherits them (its table sets the
// program, so cs_inherit_at finds nothing) ran with an acb's USER_DATA_0 and faulted at 0x860xxxxxxxx. The restore
// stands at the dcb and not after the acb because the ring order is the ring thread's: the tracker here is ahead of the
// ring, and any job can run between an acb and the next dcb. Off by default (D16).
static int acb_restore_mode() {
	static const int v = [] {
		const char* e = std::getenv("BC5_DIRECT_ACB_STATE_RESTORE");
		return e == nullptr || *e == 0 || std::strcmp(e, "0") == 0 ? 0 : 1;
	}();
	return v;
}
static std::mutex                 g_acb_touched_mtx;
static bc5::acb_restore::Touched  g_acb_touched; // the compute SH registers the title's acbs write
static void acb_touched_note(const uint32_t* ib, uint32_t num_dwords) {
	std::shared_ptr<const std::vector<bc5::direct::Mapping>> maps = g_dev->sorted_mappings();
	const auto read = [&maps](uint64_t a, uint64_t bytes) -> const uint32_t* {
		return covered_sorted(*maps, a, bytes) ? reinterpret_cast<const uint32_t*>(a) : nullptr;
	};
	std::lock_guard<std::mutex> lock(g_acb_touched_mtx);
	g_acb_touched.scan(std::span<const uint32_t>(ib, num_dwords), read);
}
static bool ib_has_draw(const uint32_t* ib, uint32_t num_dwords) {
""")

rep("""static void submit_split(const uint32_t* ib, uint32_t num_dwords, const char* kind, bool from_header) {
	t_wait_given_up = false;
	t_keep_waits.clear();
""", """static void submit_split(const uint32_t* ib, uint32_t num_dwords, const char* kind, bool from_header) {
	t_wait_given_up = false;
	t_keep_waits.clear();
	if (acb_restore_mode() != 0 && std::strncmp(kind, "acb", 3) == 0 && g_dev) acb_touched_note(ib, num_dwords); // experiment 0381
	// Experiment 0381 (J4, a diagnostic): BC5_DIRECT_CHAIN_BREAK_AT=<dwords> ends the chain in front of a title graphics
	// buffer of exactly that size, so that it heads a job and an acb can land in front of it. It changes the order
	// only; absent from the lean build.
	{
		static const uint32_t break_at = [] {
			const char* e = BC5_DIAG_ENV("BC5_DIRECT_CHAIN_BREAK_AT");
			return e != nullptr ? static_cast<uint32_t>(std::strtoul(e, nullptr, 10)) : 0u;
		}();
		if (break_at != 0 && num_dwords == break_at && std::strcmp(kind, "dcb") == 0) {
			static std::atomic<uint64_t> n_break {0};
			chain_flush(7);
			journal("chain break (exp 0381): t %.3f s, in front of a dcb of %u dwords (%" PRIu64 " so far)\\n", timing_now(), num_dwords, ++n_break);
		}
	}
""")

rep("""				full_prefix.swap(cs);
				full_used = cs_used = true;
			}
		}
	}
""", """				full_prefix.swap(cs);
				full_used = cs_used = true;
			}
		}
	}
	// Experiment 0381 (F679): the graphics queue's compute registers back after a merged acb. It takes the CS prefix's
	// path (full_prefix + cs_used): same segment, same pieces.
	if (!full_used && acb_restore_mode() != 0 && std::strcmp(kind, "dcb") == 0 && g_stage != Stage::MapOnly && g_dev &&
	    bc5::acb_restore::wants(std::span<const uint32_t>(ib, num_dwords))) {
		size_t                regs = 0;
		std::vector<uint32_t> re   = bc5::acb_restore::runs(t_fs_before, &regs);
		static std::atomic<uint64_t> n_re {0};
		static std::vector<uint32_t> last_missing {0xffffffffu}; // Codex review REVIEW-06-J2: the offsets, not their number
		const uint64_t               k = n_re++;
		std::vector<uint32_t>        missing;
		size_t                       touched = 0, unreadable = 0;
		{
			std::lock_guard<std::mutex> lock(g_acb_touched_mtx);
			missing    = g_acb_touched.missing(t_fs_before);
			touched    = g_acb_touched.count();
			unreadable = g_acb_touched.unreadable();
			if (missing == last_missing) missing.clear();
			else last_missing = missing;
		}
		if (k < 16 || (k & 0x3ffu) == 0 || !missing.empty()) {
			std::string names;
			for (size_t q = 0; q < missing.size() && q < 32; q++) {
				char one[16];
				std::snprintf(one, sizeof(one), " %x", missing[q]);
				names += one;
			}
			journal("acb state restore (exp 0381): t %.3f s dcb %u dwords, %zu registers in %zu dwords (%" PRIu64 " such buffers); acbs wrote %zu compute registers, %zu tables unreadable; not in the dcb state, left as they are:%s\\n",
			        timing_now(), num_dwords, regs, re.size(), k + 1, touched, unreadable, names.empty() ? " (no change)" : names.c_str());
		}
		if (!re.empty()) {
			full_prefix.swap(re);
			full_used = cs_used = true;
		}
	}
""")

rep("if (!pieces_dry() && !pieces_full() && draw_journal.second == 0 && !prefix_all() && cs_prefix_mode() == 0) return; // exp 0195: the compute prefix needs the tracker too",
    "if (!pieces_dry() && !pieces_full() && draw_journal.second == 0 && !prefix_all() && cs_prefix_mode() == 0 && acb_restore_mode() == 0) return; // exp 0195: the compute prefix needs the tracker too; exp 0381 too")
rep("if (t_fs_valid || prefix_all() || cs_prefix_mode() != 0) t_fs_before = tracker;",
    "if (t_fs_valid || prefix_all() || cs_prefix_mode() != 0 || acb_restore_mode() != 0) t_fs_before = tracker;")

# Codex review REVIEW-06-J2: with the dispatch journal, the job and segment identity it lacked.
rep("""	if (chain != nullptr) { // ADR 0010: the kept waits were converted to chain offsets when the segment was appended
""", """	// Experiment 0381 (Codex review REVIEW-06-J2): the dispatch journal's offsets are the assembled chain's. With it, a
	// line per job (and the class of the job before it, in the host's submission order, not read from the ring), a line
	// per segment (its place, its prefix, and the USER_DATA_0 the emitted prefix really holds), and job, segment and
	// title-buffer offset on every dispatch line.
	uint64_t job0381 = 0;
	{
		static const bool dj = BC5_DIAG_ENV("BC5_DIRECT_DISPATCH_JOURNAL") != nullptr;
		if (dj) {
			static std::mutex  job_mtx;
			static uint64_t    n_job      = 0;
			static const char* prev_class = "none";
			const char*        prev       = nullptr;
			const bool         is_acb     = std::strncmp(kind, "acb", 3) == 0;
			{
				std::lock_guard<std::mutex> lock(job_mtx); // the id and the class are one step: the predecessor is job - 1
				job0381    = ++n_job;
				prev       = prev_class;
				prev_class = is_acb ? "acb" : "dcb";
			}
			// Codex's J4 review: what an acb leaves, after all its packets; "unknown" rather than a guess.
			char final_ud0[16] = "-";
			if (is_acb) {
				std::shared_ptr<const std::vector<bc5::direct::Mapping>> maps = g_dev->sorted_mappings();
				const auto read = [&maps](uint64_t a, uint64_t bytes) -> const uint32_t* {
					return covered_sorted(*maps, a, bytes) ? reinterpret_cast<const uint32_t*>(a) : nullptr;
				};
				uint32_t v = 0;
				const bc5::acb_restore::Final f = bc5::acb_restore::final_value(std::span<const uint32_t>(ib, num_dwords), bc5::acb_restore::kUserData0, read, v);
				if (f == bc5::acb_restore::Final::Known) std::snprintf(final_ud0, sizeof(final_ud0), "%08x", v);
				else std::snprintf(final_ud0, sizeof(final_ud0), "%s", f == bc5::acb_restore::Final::None ? "none" : "unknown");
			}
			const size_t seg_count = chain != nullptr ? chain->segs.size() : 0;
			journal("job %" PRIu64 " %s: %u dwords, %zu segments, ring %d, previous job %s %" PRIu64 ", final ud0 %s\\n", job0381, kind, num_dwords, seg_count, ring, prev, job0381 - 1, final_ud0);
			for (size_t k = 0; k < seg_count; k++) {
				const ChainSeg& sg = chain->segs[k];
				uint32_t        v  = 0;
				char            ud[16] = "none";
				if (sg.prefix != 0 && sg.off + sg.prefix <= num_dwords && bc5::acb_restore::sh_value(std::span<const uint32_t>(ib + sg.off, sg.prefix), bc5::acb_restore::kUserData0, v))
					std::snprintf(ud, sizeof(ud), "%08x", v);
				journal("  job %" PRIu64 " seg %zu: off %u prefix %u n %u prefix ud0 %s\\n", job0381, k, sg.off, sg.prefix, sg.n, ud);
			}
		}
	}
	if (chain != nullptr) { // ADR 0010: the kept waits were converted to chain offsets when the segment was appended
""")
rep("""				if (dj && type == 3 && (op == 0x15 || op == 0x16))
					journal("  %s dispatch op %02x at %u: pgm""", """				if (dj && type == 3 && (op == 0x15 || op == 0x16)) {
					const bc5::acb_restore::Where w0381 = bc5::acb_restore::locate(chain != nullptr ? std::span<const ChainSeg>(chain->segs) : std::span<const ChainSeg>(), q);
					journal("  %s dispatch op %02x at %u: pgm""")
rep(""" base1 0x%" PRIx64 " +0x%x len %u\\n", kind, op, q, pgm, ud[0]""", """ base1 0x%" PRIx64 " +0x%x len %u job %" PRIu64 " seg %d orig %u\\n", kind, op, q, pgm, ud[0]""")
rep("""op == 0x16 && len >= 2 ? ib[q + 1] : 0u, len); // experiment 0160: all user data and the indirect base""",
    """op == 0x16 && len >= 2 ? ib[q + 1] : 0u, len, job0381, w0381.seg, w0381.orig); // experiment 0160: all user data and the indirect base
				}""")

open(sys.argv[2], "wb").write(s.encode("utf-8"))
print("ok")
