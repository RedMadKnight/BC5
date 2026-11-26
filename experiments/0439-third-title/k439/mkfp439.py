#!/usr/bin/env python3
# BC5 exp 0439 (tag fp439): experiment 0190's flat-aperture rewrite (F249) for every program however it is bound
# (bc5/fp0439.hpp): SET_SH_REG, LOAD_SH_REG and LOAD_SH_REG_INDEX, at the top level and in every chained or called
# piece, on every queue submit_now takes (graphics and compute), at DISPATCH_DIRECT and DISPATCH_INDIRECT.
#   - It rides on BC5_DIRECT_FLAT_APERTURE (unchanged, every title). BC5_DIRECT_FLAT_APERTURE_PIECES=0 turns the new
#     reach off for an A/B; anything else leaves it on. No program list, nothing learned.
#   - Cost: flat_aperture_fix's cache is keyed by program address and checked by identity (bc5::fp439::ident, the first
#     eight dwords) and by its rewritten sites still holding 0x10000000; per dispatch after a program's first sight:
#     the thread's last program compared (8 + sites dword reads), else one map lookup under the mutex. The walk decodes
#     each piece's packet headers once per submit, as the import scans already do (ip439).
#   - Journal: one line per program at its first rewrite, with how it was bound; and, every 4096 submits and at the
#     first, the dispatches whose program was not known (none set in the buffer) or followed an unreadable table.
# Before the submit, so the GPU runs the rewritten code.
# Usage: python mkfp439.py IN.cpp OUT.cpp (every anchor exactly once)
import sys

src, dst = sys.argv[1], sys.argv[2]
s = open(src, 'rb').read().decode('utf-8', 'surrogateescape')
assert '\r' not in s and 'fp439' not in s


def rep(a, b):
    global s
    assert s.count(a) == 1, (a[:70], s.count(a))
    s = s.replace(a, b)


# the include after ib_chain.hpp's (the private unit and the bake unit space its comment differently)
INC = [ln for ln in s.split('\n') if ln.startswith('#include "bc5/ib_chain.hpp"') and 'tag ib439' in ln]
assert len(INC) == 1, INC
rep(INC[0] + '\n', INC[0] + '\n#include "bc5/fp0439.hpp" // exp 0439 (tag fp439): the flat-aperture rewrite for every program\n')
# ---- flat_aperture_fix: the bound-via argument and the identity cache ----
rep('static void flat_aperture_fix(uint64_t pgm, const bc5::direct::MappingIndex& maps) {',
    'static void flat_aperture_fix(uint64_t pgm, const bc5::direct::MappingIndex& maps, const char* via = "the top level") { // exp 0439 (tag fp439): via')
rep('''	thread_local uint64_t last = 0;
	if (pgm == last) return;
	last = pgm;
	static std::mutex         m;
	static std::set<uint64_t> seen;
	std::lock_guard           lk(m);
	if (!seen.insert(pgm).second) return;
''', '''	// exp 0439 (tag fp439): cached by address, checked by identity and by the rewritten sites (a program replaced or
	// reloaded at the same address is scanned again); was: by address only, so a reload kept the console's apertures
	struct Seen {
		uint64_t              id = 0;
		std::vector<uint32_t> lits;
	};
	auto*                              w     = reinterpret_cast<volatile uint32_t*>(pgm);
	const auto                         whole = [&w](const std::vector<uint32_t>& l) {
		for (const uint32_t k : l)
			if (w[k] != 0x10000000u) return false;
		return true;
	};
	thread_local uint64_t              t_last = 0, t_id = 0;
	thread_local std::vector<uint32_t> t_lits;
	if (pgm == t_last && bc5::fp439::ident(w) == t_id && whole(t_lits)) return;
	static std::mutex                        m;
	static std::unordered_map<uint64_t, Seen> seen;
	std::lock_guard                          lk(m);
	if (const auto it = seen.find(pgm); it != seen.end() && bc5::fp439::ident(w) == it->second.id && whole(it->second.lits)) {
		t_last = pgm, t_id = it->second.id, t_lits = it->second.lits;
		return;
	}
	std::vector<uint32_t> lits;
''')
rep('''	auto*    w   = reinterpret_cast<volatile uint32_t*>(pgm);
	uint32_t end = 0;
	while (end < n && w[end] != 0xBF810000u) end++; // up to the program's s_endpgm''',
    '''	uint32_t end = 0;
	while (end < n && w[end] != 0xBF810000u) end++; // up to the program's s_endpgm''')
rep('''		w[k + 2] = 0x10000000u;
		sites++;''', '''		w[k + 2] = 0x10000000u;
		lits.push_back(k + 2); // exp 0439 (tag fp439)
		sites++;''')
rep('''	if (sites != 0)
		journal("flat aperture: program 0x%" PRIx64 ": %u stack pushes (%u s_brev_b32) now address the host's LDS/private apertures\\n", pgm, sites, brevs);
}''', '''	// exp 0439 (tag fp439): a literal already 0x10000000 (rewritten before) is a site too, for the cache's check
	for (uint32_t k = 0; k + 2 < end; k++)
		if ((w[k] & 0xffffff00u) == 0xD5590000u && ((w[k + 1] >> 9u) & 0x1ffu) == 0xffu && w[k + 2] == 0x10000000u && std::find(lits.begin(), lits.end(), k + 2) == lits.end()) lits.push_back(k + 2);
	Seen& e = seen[pgm];
	e.id = bc5::fp439::ident(w), e.lits = lits;
	t_last = pgm, t_id = e.id, t_lits = e.lits;
	if (sites != 0)
		journal("flat aperture: program 0x%" PRIx64 ": %u stack pushes (%u s_brev_b32) now address the host's LDS/private apertures, bound via %s\\n", pgm, sites, brevs, via);
}''')
# ---- the walk, in submit_now before the submit ----
rep('''	shader_dump(ib, num_dwords, *maps_p); // experiment 0049
''', '''	shader_dump(ib, num_dwords, *maps_p); // experiment 0049
	{ // exp 0439 (tag fp439): experiment 0190's rewrite for every dispatch's program, the buffer's top level and its
	  // chained and called pieces in order (bc5/fp0439.hpp); BC5_DIRECT_FLAT_APERTURE_PIECES=0 leaves only the
	  // top-level scan's call, as before
		static const bool fp439 = [] {
			const char* fa = std::getenv("BC5_DIRECT_FLAT_APERTURE");
			const char* e  = std::getenv("BC5_DIRECT_FLAT_APERTURE_PIECES");
			const bool  v  = fa != nullptr && *fa != 0 && std::strcmp(fa, "0") != 0 && !(e != nullptr && std::strcmp(e, "0") == 0);
#ifndef BC5_LEAN
			std::fprintf(stderr, "[bc5] exp 0439 (tag fp439): the flat-aperture rewrite reaches every piece: %d\\n", v ? 1 : 0);
#endif
			return v;
		}();
		if (fp439) {
			const auto            cov = [&maps_p](uint64_t a, uint64_t b) { return covered_sorted(*maps_p, a, b); };
			const auto            cr  = bc5::ib_chain::collect(ib, num_dwords, cov, true);
			bc5::fp439::State     st;
			bc5::fp439::Stats     ss;
			for (size_t k = 0; k < cr.pieces.size(); k++)
				bc5::fp439::walk(cr.pieces[k].src, static_cast<uint32_t>(cr.pieces[k].n), st, ss, cov, [&](uint64_t p, bc5::fp439::Via v) {
					if (p == 0) return;
					static const char* const names[4][2] = {{"nothing in this buffer, at the top level", "nothing in this buffer, in a piece"},
					                                        {"SET_SH_REG at the top level", "SET_SH_REG in a chained or called piece"},
					                                        {"LOAD_SH_REG at the top level", "LOAD_SH_REG in a chained or called piece"},
					                                        {"LOAD_SH_REG_INDEX at the top level", "LOAD_SH_REG_INDEX in a chained or called piece"}};
					flat_aperture_fix(p, *maps_p, names[static_cast<int>(v)][k == 0 ? 0 : 1]);
				});
			static std::atomic<uint64_t> n_sub {0}, n_disp {0}, n_none {0}, n_unread {0};
			n_disp += ss.dispatches, n_none += ss.no_pgm, n_unread += ss.after_unreadable;
			if ((n_sub++ & 0xfffu) == 0)
				journal("flat aperture (fp439): %" PRIu64 " submits, %" PRIu64 " dispatches, %" PRIu64 " with no program set in their buffer, %" PRIu64 " after an unreadable table\\n", n_sub.load(), n_disp.load(), n_none.load(), n_unread.load());
		}
	}
''')
open(dst, 'wb').write(s.encode('utf-8', 'surrogateescape'))
print('mkfp439: wrote', dst)
