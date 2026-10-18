#!/usr/bin/env python3
# Experiment 0157, eleventh step: BC5_DIRECT_PREFIX_ALL=1 puts the full tracked register state (CLEAR_STATE,
# then every context/SH/uconfig register the title has set so far, as the pieces' prefix does) in front of
# every graphics-queue buffer, so that no register the title leaves to the hardware's previous state can
# come from another process's work on the ring. Also: the tracked context registers are journaled with
# the 10 s "piece check" summary (the registers the title never sets are absent from that list).
p = "/home/kjaniszewski/src/KytyPlus/src/libs/bc5LleAgc.cpp"
s = open(p, encoding="utf-8", newline="").read()


def rep(a, b, count=1):
    global s
    assert s.count(a) == count, (s.count(a), a[:80])
    s = s.replace(a, b)


rep("""static std::atomic<uint64_t> g_full_pieces {0}, g_full_ok {0}, g_full_failed {0};
static thread_local bool                     t_fs_valid = false;
static thread_local bc5::full_state::Tracker t_fs_before;""",
    """static std::atomic<uint64_t> g_full_pieces {0}, g_full_ok {0}, g_full_failed {0};
static thread_local bool                     t_fs_valid = false;
static thread_local bc5::full_state::Tracker t_fs_before;
// Experiment 0157: BC5_DIRECT_PREFIX_ALL=1, the full-state prefix in front of every graphics buffer.
static bool prefix_all() {
	static const bool v = std::getenv("BC5_DIRECT_PREFIX_ALL") != nullptr;
	return v;
}""")

rep("""	std::vector<uint32_t>                   full_prefix; // BC5_DIRECT_PIECES_FULL: the prefix of the piece at start
	bool                                    full_used = false;""",
    """	std::vector<uint32_t>                   full_prefix; // BC5_DIRECT_PIECES_FULL: the prefix of the piece at start
	bool                                    full_used = false;
	if (prefix_all() && std::strcmp(kind, "dcb") == 0 && g_stage != Stage::MapOnly) { // experiment 0157
		full_prefix = prefix_of(t_fs_before);
		full_used   = !full_prefix.empty();
	}""")

rep("""							if (start > 0 && !full_prefix.empty()) submit_prefixed(full_prefix, ib + start, i - start, false);
							else submit_one(ib + start, i - start, kind, from_header && start == 0);
							full_prefix = prefix_of(*dry);
							start       = i;
							full_used   = true;
							split       = true;""",
    """							if ((start > 0 || prefix_all()) && !full_prefix.empty()) submit_prefixed(full_prefix, ib + start, i - start, false);
							else submit_one(ib + start, i - start, kind, from_header && start == 0);
							full_prefix = prefix_of(*dry);
							start       = i;
							full_used   = true;
							split       = true;""")

rep("""						if (start > 0 && !full_prefix.empty()) submit_prefixed(full_prefix, ib + start, i - start, false);
						else submit_one(ib + start, i - start, kind, from_header && start == 0);
						full_prefix = prefix_of(*dry);
						const uint32_t head_from = start;""",
    """						if ((start > 0 || prefix_all()) && !full_prefix.empty()) submit_prefixed(full_prefix, ib + start, i - start, false);
						else submit_one(ib + start, i - start, kind, from_header && start == 0);
						full_prefix = prefix_of(*dry);
						const uint32_t head_from = start;""")

rep("""	if (start > 0 && full_used) {
		submit_prefixed(full_prefix, ib + start, num_dwords - start, false);
		return;
	}""",
    """	if ((start > 0 || prefix_all()) && full_used && !full_prefix.empty()) {
		submit_prefixed(full_prefix, ib + start, num_dwords - start, false);
		return;
	}""")

# the tracker must run, and the before-state be kept, for every graphics buffer
rep("""	if (!pieces_dry() && !pieces_full() && draw_journal.second == 0) return;
	// Experiment 0157: BC5_DIRECT_DRAW_JOURNAL_ACB=1""",
    """	if (!pieces_dry() && !pieces_full() && draw_journal.second == 0 && !prefix_all()) return;
	// Experiment 0157: BC5_DIRECT_DRAW_JOURNAL_ACB=1""")

rep("""		if (t_fs_valid) t_fs_before = tracker;
		if (!waits.empty()) with_waits++;""",
    """		if (t_fs_valid || prefix_all()) t_fs_before = tracker;
		if (!waits.empty()) with_waits++;""")

# the tracked context registers with the summary
rep("""		journal("piece check: %" PRIu64 " graphics buffers, %" PRIu64 " with waits; tracked config %zu context %zu sh %zu uconfig %zu; tables %" PRIu64""",
    """		{ // experiment 0157: every context register the tracker holds (the title's state so far)
			std::string line = "tracked context:";
			for (uint32_t o = 0; o < 0x400u; o++) {
				uint32_t v = 0;
				if (tracker.get(bc5::full_state::Context, o, v)) {
					char b[24];
					std::snprintf(b, sizeof(b), " %x:%08x", o, v);
					line += b;
				}
			}
			journal("%s\\n", line.c_str());
		}
		journal("piece check: %" PRIu64 " graphics buffers, %" PRIu64 " with waits; tracked config %zu context %zu sh %zu uconfig %zu; tables %" PRIu64""")

open(p, "w", encoding="utf-8", newline="").write(s)
print("ok")
