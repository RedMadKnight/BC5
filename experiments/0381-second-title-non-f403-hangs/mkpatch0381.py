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


rep('#include "bc5/zero_skip.hpp" // experiment 0379\n',
    '#include "bc5/zero_skip.hpp" // experiment 0379\n#include "bc5/acb_restore.hpp" // experiment 0381\n')

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
		static size_t                last_missing = static_cast<size_t>(-1);
		const uint64_t               k = n_re++;
		std::vector<uint32_t>        missing;
		size_t                       touched = 0, unreadable = 0;
		{
			std::lock_guard<std::mutex> lock(g_acb_touched_mtx);
			missing    = g_acb_touched.missing(t_fs_before);
			touched    = g_acb_touched.count();
			unreadable = g_acb_touched.unreadable();
			if (missing.size() == last_missing) missing.clear();
			else last_missing = missing.size();
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

open(sys.argv[2], "wb").write(s.encode("utf-8"))
print("ok")
