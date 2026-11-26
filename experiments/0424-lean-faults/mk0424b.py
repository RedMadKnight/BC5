#!/usr/bin/env python3
r"""BC5 experiment 0424, the corrected catcher (tag aq424q), the top session's GO of 2026-11-15 (after the re-check).
    mk0424b.py <tree root>
Applies to mk0424.py's unit (md5 11e0de65) and replaces the first catcher (aq424c), which read the title's 4-dword
compute-queue DISPATCH_INDIRECT as the GFX form against a stale SET_BASE (README, "1. The catcher compared against the
wrong address"). The fix aq424 (BC5_DIRECT_ACB_QUEUE_STATE) stays as it is, off by default. Normal build only
(#ifndef BC5_LEAN); the lean build is not rebuilt.

For every DISPATCH_INDIRECT 0x16 of the BVH refit 0x909939900, the argument's high half is dword 2 & 0xffff for the
4-dword compute form (the address the host's mec rebuild uses), or (SET_BASE 1 + dword 1) >> 32 for the 3-dword form.
It is compared with COMPUTE_USER_DATA_5 (SH 0x245) low 16 bits in two views:
- ring: in submit_now under g_dev_mutex (the order the GPU gets the buffers); each 0x245 write is put to its writer:
  the guest queue of the chain segment (aq424_note's ranges of acb parts), the host prefix in front of a part, or a
  buffer that is no acb part (a dcb or a host buffer);
- queue: per guest queue (t_queue_idx), a shadow that only that queue's own acb parts update (acb_cs_track's two call
  sites, every acb part whatever the switch), with each mismatch split into carried (from an earlier part) or set in
  the same part.
Counts: match, MISMATCH, unknown (USER_DATA_5 not known: never written, or LOAD_SH_REG(_INDEX) 0x5f/0x63 or
INDIRECT_BUFFER 0x3f since, which are not followed; or the argument high not known). One stderr line at most every
10 s, with the first mismatch since the previous line in each view (the queues involved).
Every edit must match exactly once."""
import hashlib, sys
from pathlib import Path

p = Path(sys.argv[1]) / "src" / "libs" / "bc5LleAgc.cpp"
b = p.read_bytes()
assert hashlib.md5(b).hexdigest()[:8] == "11e0de65", "the unit is not 11e0de65"
s = b.decode("utf-8")
assert "tag aq424q" not in s


def sub(old, new):
    global s
    assert s.count(old) == 1, ("not exactly once", old[:80], s.count(old))
    s = s.replace(old, new)


# 1. forward declarations, before acb_cs_prefix_on
sub("static bool acb_cs_prefix_on() {\n\tstatic const bool        on = aq424_on();",
    "#ifndef BC5_LEAN\n"
    "static void aq424_note(const uint32_t* part, uint32_t n);  // exp 0424 (tag aq424q): an acb part's range and guest queue\n"
    "static void aq424_queue(const uint32_t* part, uint32_t n); // exp 0424 (tag aq424q): the queue view\n"
    "#endif\n"
    "static bool acb_cs_prefix_on() {\n\tstatic const bool        on = aq424_on();")

# 2. every acb part's range and queue, before it is submitted (both callers call acb_cs_prefix first; inherit mode 0)
sub("static std::vector<uint32_t> acb_cs_prefix(const uint32_t* part, uint32_t n) {\n",
    "static std::vector<uint32_t> acb_cs_prefix(const uint32_t* part, uint32_t n) {\n"
    "#ifndef BC5_LEAN\n\taq424_note(part, n); // exp 0424 (tag aq424q), whatever the switch\n#endif\n")

# 3. the queue view, after each acb part (both call sites), whatever the switch
sub("static void acb_cs_track(const uint32_t* part, uint32_t n) {\n",
    "static void acb_cs_track(const uint32_t* part, uint32_t n) {\n"
    "#ifndef BC5_LEAN\n\taq424_queue(part, n); // exp 0424 (tag aq424q), whatever the switch\n#endif\n")

# 4. the catcher itself, in place of aq424c
a = s.index("// Experiment 0424 (tag aq424c): the catcher of the BVH refit's pointer.")
end_mark = "aq424_on() ? \"ON\" : \"off\", g_aq424_parts.load(), g_aq424_none.load());\n\t}\n}\n#endif\n"
assert s.count(end_mark) == 1
e = s.index(end_mark) + len(end_mark)
NEW = r'''// Experiment 0424 addendum (tag aq424q): the corrected catcher of the BVH refit's pointer (normal build only). The title's
// acbs send DISPATCH_INDIRECT 0x16 in the compute-queue form, 4 dwords with the argument address in dwords 1-2; the
// host's mec rebuild in submit_now turns it into SET_BASE 1 + the GFX form after this point (the first catcher, aq424c,
// read it as the GFX form against a stale base). The argument's high half: dword 2 & 0xffff (4 dwords), or
// (SET_BASE 1 + dword 1) >> 32 (3 dwords). COMPUTE_USER_DATA_5 (SH 0x245) is compared with it in two views: the ring
// (submit_now, under g_dev_mutex; each write's writer is its chain segment's guest queue, the host prefix in front of a
// part, or a buffer that is no acb part) and the queue (per guest queue, from that queue's own acb parts only).
// LOAD_SH_REG(_INDEX) 0x5f/0x63 and INDIRECT_BUFFER 0x3f are not followed: unknown. One stderr line at most every 10 s.
static constexpr uint64_t kAq424Refit = 0x909939900ull;
static uint64_t           aq424_pgm(uint32_t lo, uint32_t hi) { return (static_cast<uint64_t>(lo) | (static_cast<uint64_t>(hi & 0xffu) << 32u)) << 8u; }
static int64_t            aq424_arg_hi(const uint32_t* p, uint32_t len, uint64_t base1) { // -1: not known
	if (len == 4) return static_cast<int64_t>(p[2] & 0xffffu);
	if (len == 3 && base1 != 0) return static_cast<int64_t>((base1 + p[1]) >> 32u);
	return -1;
}
struct Aq424Counts {
	uint64_t n = 0, match = 0, mis = 0, unk = 0;
};
struct Aq424Queue {
	bool     ud5_known = false, pgm_known = false;
	uint32_t ud5 = 0, pgm_lo = 0, pgm_hi = 0;
};
static std::mutex                                     g_aq424q_mu; // the parts map and the queue view; taken under g_dev_mutex, never the other way
static std::map<uintptr_t, std::pair<uintptr_t, int>> g_aq424_part_q; // acb part start -> (end, guest queue)
static std::map<int, Aq424Queue>                      g_aq424_q;
static Aq424Counts                                    g_aq424q_c;
static uint64_t                                       g_aq424q_carried = 0, g_aq424q_inpart = 0;
static int                                            g_aq424q_first_q = -9;
static bool                                           g_aq424q_first_carried = false;
static uint32_t                                       g_aq424q_first_ud5 = 0, g_aq424q_first_hi = 0;
static void aq424_note(const uint32_t* part, uint32_t n) {
	if (part == nullptr || n == 0) return;
	std::lock_guard lk(g_aq424q_mu);
	if (g_aq424_part_q.size() > 8192) g_aq424_part_q.clear();
	g_aq424_part_q[reinterpret_cast<uintptr_t>(part)] = {reinterpret_cast<uintptr_t>(part + n), t_queue_idx};
}
static int aq424_queue_of(const uint32_t* src) { // under g_aq424q_mu; -2 host-built, -1 no acb part
	if (src == nullptr) return -2;
	const uintptr_t a  = reinterpret_cast<uintptr_t>(src);
	auto            it = g_aq424_part_q.upper_bound(a);
	if (it == g_aq424_part_q.begin()) return -1;
	--it;
	return a < it->second.first ? it->second.second : -1;
}
static void aq424_queue(const uint32_t* part, uint32_t n) {
	if (part == nullptr || n == 0) return;
	std::lock_guard lk(g_aq424q_mu);
	Aq424Queue&     q       = g_aq424_q[t_queue_idx];
	bool            in_part = false;
	for (uint32_t i = 0; i < n;) {
		const uint32_t h = part[i], type = h >> 30u;
		uint32_t       len = 1;
		if (type == 3 || type == 0) { const uint32_t c = (h >> 16u) & 0x3fffu; len = c == 0x3fffu ? 1 : c + 2; }
		if (i + len > n) break;
		if (type == 3) {
			const uint32_t  op = (h >> 8u) & 0xffu;
			const uint32_t* p  = part + i;
			if ((op == 0x76 || op == 0x9b) && len >= 3) {
				const uint32_t o = p[1] & 0xffffu;
				for (uint32_t k = 0; k + 2 < len; k++) {
					const uint32_t reg = o + k, v = p[2 + k];
					if (reg == 0x245u) { q.ud5 = v; q.ud5_known = true; in_part = true; }
					else if (reg == 0x20cu) { q.pgm_lo = v; q.pgm_known = true; }
					else if (reg == 0x20du) q.pgm_hi = v;
				}
			} else if (op == 0x5f || op == 0x63 || op == 0x3f) {
				q.ud5_known = q.pgm_known = false;
			} else if (op == 0x16 && q.pgm_known && aq424_pgm(q.pgm_lo, q.pgm_hi) == kAq424Refit) {
				g_aq424q_c.n++;
				const int64_t hi = aq424_arg_hi(p, len, 0);
				if (!q.ud5_known || hi < 0) g_aq424q_c.unk++;
				else if ((q.ud5 & 0xffffu) == static_cast<uint32_t>(hi)) g_aq424q_c.match++;
				else {
					g_aq424q_c.mis++;
					(in_part ? g_aq424q_inpart : g_aq424q_carried)++;
					if (g_aq424q_first_q == -9) {
						g_aq424q_first_q       = t_queue_idx;
						g_aq424q_first_carried = !in_part;
						g_aq424q_first_ud5     = q.ud5;
						g_aq424q_first_hi      = static_cast<uint32_t>(hi);
					}
				}
			}
		}
		i += len;
	}
}
struct Aq424Ring {
	bool     ud5_known = false, pgm_known = false, ud5_prefix = false;
	uint32_t ud5 = 0, pgm_lo = 0, pgm_hi = 0;
	int      ud5_by = -3;
	uint64_t base1  = 0;
};
static std::map<int, Aq424Ring> g_aq424_ring;
static Aq424Counts              g_aq424r_c;
static uint64_t                 g_aq424r_same = 0, g_aq424r_other = 0, g_aq424r_prefix = 0, g_aq424r_nonacb = 0, g_aq424_last_ns = 0;
static int                      g_aq424r_first_q = -9, g_aq424r_first_by = -9;
static bool                     g_aq424r_first_prefix = false;
static uint32_t                 g_aq424r_first_ud5 = 0, g_aq424r_first_hi = 0;
static void aq424_catch(const uint32_t* ib, uint32_t n, int ring, const Chain* chain) {
	Aq424Ring&      r = g_aq424_ring[ring];
	std::lock_guard lk(g_aq424q_mu);
	size_t          si = 0;
	// the guest queue of the chain segment that holds dword i (-1 no acb part, -2 host-built, -3 no chain), and
	// whether i lies in the host prefix laid in front of it
	const auto who = [&](uint32_t i, bool* prefix) -> int {
		*prefix = false;
		if (chain == nullptr || chain->segs.empty()) return -3;
		while (si + 1 < chain->segs.size() && chain->segs[si + 1].off <= i) si++;
		const ChainSeg& sg = chain->segs[si];
		*prefix            = i < sg.off + sg.prefix;
		return aq424_queue_of(sg.src);
	};
	for (uint32_t i = 0; i < n;) {
		const uint32_t h = ib[i], type = h >> 30u;
		uint32_t       len = 1;
		if (type == 3 || type == 0) { const uint32_t c = (h >> 16u) & 0x3fffu; len = c == 0x3fffu ? 1 : c + 2; }
		if (i + len > n) break;
		if (type == 3) {
			const uint32_t  op = (h >> 8u) & 0xffu;
			const uint32_t* p  = ib + i;
			if ((op == 0x76 || op == 0x9b) && len >= 3) {
				const uint32_t o = p[1] & 0xffffu;
				for (uint32_t k = 0; k + 2 < len; k++) {
					const uint32_t reg = o + k, v = p[2 + k];
					if (reg == 0x245u) { r.ud5 = v; r.ud5_known = true; r.ud5_by = who(i, &r.ud5_prefix); }
					else if (reg == 0x20cu) { r.pgm_lo = v; r.pgm_known = true; }
					else if (reg == 0x20du) r.pgm_hi = v;
				}
			} else if (op == 0x5f || op == 0x63 || op == 0x3f) {
				r.ud5_known = r.pgm_known = false;
			} else if (op == 0x11 && len >= 4 && (p[1] & 0xfu) == 1u) {
				r.base1 = (p[2] & ~3u) | (static_cast<uint64_t>(p[3] & 0xffffu) << 32u);
			} else if (op == 0x16 && r.pgm_known && aq424_pgm(r.pgm_lo, r.pgm_hi) == kAq424Refit) {
				g_aq424r_c.n++;
				const int64_t hi = aq424_arg_hi(p, len, r.base1);
				if (!r.ud5_known || hi < 0) g_aq424r_c.unk++;
				else if ((r.ud5 & 0xffffu) == static_cast<uint32_t>(hi)) g_aq424r_c.match++;
				else {
					g_aq424r_c.mis++;
					bool      pf = false;
					const int q  = who(i, &pf);
					if (r.ud5_prefix) g_aq424r_prefix++;
					else if (r.ud5_by < 0) g_aq424r_nonacb++;
					else (r.ud5_by == q ? g_aq424r_same : g_aq424r_other)++;
					if (g_aq424r_first_q == -9) {
						g_aq424r_first_q      = q;
						g_aq424r_first_by     = r.ud5_by;
						g_aq424r_first_prefix = r.ud5_prefix;
						g_aq424r_first_ud5    = r.ud5;
						g_aq424r_first_hi     = static_cast<uint32_t>(hi);
					}
				}
			}
		}
		i += len;
	}
	const uint64_t now = SoftCp::now_ns();
	if ((g_aq424r_c.n != 0 || g_aq424q_c.n != 0) && now - g_aq424_last_ns >= 10000000000ull) {
		g_aq424_last_ns = now;
		std::fprintf(stderr,
		             "[bc5] exp 0424 (tag aq424q): t %.1f s: refit 0x909939900 RING view: dispatches %" PRIu64 ", USER_DATA_5 low 16 = argument high %" PRIu64
		             ", MISMATCH %" PRIu64 " (written by: the same queue %" PRIu64 ", another queue %" PRIu64 ", a host prefix %" PRIu64 ", no acb part %" PRIu64
		             "), unknown %" PRIu64 "; first mismatch since the last line: refit queue %d, USER_DATA_5 %08x written by queue %d%s, argument high %x. "
		             "QUEUE view: dispatches %" PRIu64 ", match %" PRIu64 ", MISMATCH %" PRIu64 " (carried %" PRIu64 ", set in the part %" PRIu64 "), unknown %" PRIu64
		             "; first mismatch since the last line: queue %d, USER_DATA_5 %08x (%s), argument high %x. acb queue state %s, %" PRIu64 " parts given it\n",
		             timing_now(), g_aq424r_c.n, g_aq424r_c.match, g_aq424r_c.mis, g_aq424r_same, g_aq424r_other, g_aq424r_prefix, g_aq424r_nonacb, g_aq424r_c.unk,
		             g_aq424r_first_q, g_aq424r_first_ud5, g_aq424r_first_by, g_aq424r_first_prefix ? " (its host prefix)" : "", g_aq424r_first_hi,
		             g_aq424q_c.n, g_aq424q_c.match, g_aq424q_c.mis, g_aq424q_carried, g_aq424q_inpart, g_aq424q_c.unk,
		             g_aq424q_first_q, g_aq424q_first_ud5, g_aq424q_first_carried ? "carried" : "set in the part", g_aq424q_first_hi,
		             aq424_on() ? "ON" : "off", g_aq424_parts.load());
		g_aq424r_first_q = g_aq424q_first_q = -9; // the next line's sample
	}
}
#endif
'''
s = s[:a] + NEW + s[e:]

# 5. the call, with the chain
sub("\taq424_catch(ib, num_dwords, ring); // exp 0424 (tag aq424c): the refit's USER_DATA_5 against its argument address\n",
    "\taq424_catch(ib, num_dwords, ring, chain); // exp 0424 (tag aq424q): the refit's USER_DATA_5 against its argument address\n")
assert "tag aq424c" not in s
p.write_bytes(s.encode("utf-8"))
print("mk0424b: 11e0de65 ->", hashlib.md5(s.encode("utf-8")).hexdigest()[:8])
