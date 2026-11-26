#!/usr/bin/env python3
# BC5 experiment 0302: the resource-table descriptor check, diagnostic (a) — the table of a listed program's dispatch read
# at filter time (the CPU's view, before the submit) and compared at the fence timeout with the table as the probe reads
# it then. In src/libs/bc5LleAgc.cpp of the shared tree as integrated on the box (md5 5bccbb80: patch 0001 on main at
# 64179e6, exp 0272's probe in, exp 0277's breadcrumbs not in). No sync packets (exp 0300's part is left out), no refusal
# change (the backend archive is chosen at link time, build0302.sh).
#   Why: exp 0300 S2 / exp 0297 step 2 — the acb's last 0x11d03a4600 dispatch had user SGPRs 12-13 = 0x11e0fbff70, a
#   "table" straddling the page at 0x11e0fc0000 whose slot +0x60 read as a V# with base 0xb20407c00000, exactly the SQC
#   data fault address; the eleven dispatches before it had sane tables. The probe reads memory as it is at the timeout,
#   so it cannot say whether the title handed the GPU that pointer (wrong user data, or a table recycled before the
#   submit) or whether the table was overwritten between the submit and the GPU's read, or whether the GPU's mapping of
#   that page differs from the CPU's view (the supervisor's lead: the page boundary).
#   1. At filter time, for a dispatch (0x15 / 0x16) of a program in BC5_DIRECT_TABLE_PGM (hex list; default the 0x11d03a
#      family of F360) whose COMPUTE_USER_DATA_12/13 are set: the table address, whether its 160 bytes are mapped, which
#      mapping (index, va, size, shared/userptr, ro) covers its first and its last slot, and the 40 dwords of slots
#      +0x00..+0x90 — kept (the last 4096) for the probe. Journaled at once ("descriptor (exp 0302)") when the table is
#      unmapped, spans two mappings, or a slot's V# base is unmapped now (BAD SLOT); otherwise one line per 4096.
#   2. At the timeout, exp 0297 step 2's table dump (as exp 0300 built it, marker "table (exp 0302)") plus, for the table
#      of each listed dispatch, the comparison with its filter-time snapshot: every slot CHANGED since filter time is
#      printed with its old dwords, the submit number and the age; a summary line per table; "no filter-time snapshot"
#      when the probe's table address was never seen by the filter (the user data differ between the two readings).
#   3. Exp 0277's probe fix (the executed offsets forward into the rebuilt IB), as exp 0300 carried it.
# usage: patch0302.py <src root of the shared tree> <out dir>   (writes <out dir>/bc5LleAgc.cpp and <out dir>/patch_0302.diff;
#        the inputs are only read; every anchor must occur exactly the number of times given)
import difflib, hashlib, os, sys

EDITS = {
    'src/libs/bc5LleAgc.cpp': [
        # 1. File scope, before the probe: the snapshot, its store, the list and three helpers.
        ('''static void timeout_probe(const uint32_t* sub_ib, uint32_t sub_n, const char* kind, uint64_t n, const std::vector<uint32_t>* ran, const std::vector<GeProbeSlot>* gep = nullptr) {
''', 1, '''// Experiment 0302: the resource table of a listed program's dispatch, read at filter time (the CPU's view, before the
// submit) and kept for the timeout probe to compare with the table as it reads then. Keyed by the table's address and
// the program (each dispatch has its own table; offsets differ between the original and a rebuilt IB).
struct TableSnap {
	uint64_t pgm = 0, table = 0, submit = 0;
	double   t = 0;
	uint32_t slots[40] = {};
	bool     covered = false;          // the 160 bytes mapped at filter time
	int      map_lo = -1, map_hi = -1; // the mappings covering the first and the last slot (indices into sorted_mappings)
};
static std::mutex            g_tsnap_m;
static std::deque<TableSnap> g_tsnaps; // the last 4096
static double tsnap_now() {
	timespec ts {};
	clock_gettime(CLOCK_MONOTONIC, &ts);
	return static_cast<double>(ts.tv_sec) + static_cast<double>(ts.tv_nsec) * 1e-9;
}
static const std::set<uint64_t>& table_pgm_list() { // BC5_DIRECT_TABLE_PGM, hex list; default the 0x11d03a family (F360)
	static const std::set<uint64_t> s = [] {
		std::set<uint64_t> r;
		if (const char* e = std::getenv("BC5_DIRECT_TABLE_PGM"); e != nullptr) {
			for (const char* p = e; *p != 0;) {
				char*          end = nullptr;
				const uint64_t v   = std::strtoull(p, &end, 16);
				if (end == p) { p++; continue; }
				r.insert(v);
				p = end;
			}
		} else {
			r = {0x11d03a2000ull, 0x11d03a3400ull, 0x11d03a3500ull, 0x11d03a4600ull, 0x11d039f000ull, 0x11d03a0700ull};
		}
		return r;
	}();
	return s;
}
static int tsnap_map_index(const std::vector<bc5::direct::Mapping>& maps, uint64_t a) { // the mapping holding a, or -1 (sorted by va)
	auto it = std::upper_bound(maps.begin(), maps.end(), a, [](uint64_t v, const bc5::direct::Mapping& m) { return v < m.va; });
	if (it == maps.begin()) return -1;
	--it;
	return a >= it->va && a < it->va + it->size ? static_cast<int>(it - maps.begin()) : -1;
}
static void tsnap_map_desc(const std::vector<bc5::direct::Mapping>& maps, int i, char* out, size_t cap) {
	if (i < 0 || static_cast<size_t>(i) >= maps.size()) { std::snprintf(out, cap, "none"); return; }
	const auto& m = maps[static_cast<size_t>(i)];
	std::snprintf(out, cap, "#%d 0x%" PRIx64 "+0x%" PRIx64 "%s%s", i, m.va, m.size, m.shared ? " shared" : " userptr", m.readonly ? " ro" : "");
}
static void tsnap_vsharp(char* out, size_t cap, const uint32_t* d) { // gfx10 buffer resource: base[47:0], stride = dword 1 bits 29:16, num_records (LLVM AMDGPUUsage, TODO(verify))
	const uint64_t base   = d[0] | (static_cast<uint64_t>(d[1] & 0xffffu) << 32u);
	const uint32_t stride = (d[1] >> 16u) & 0x3fffu;
	std::snprintf(out, cap, "%08x %08x %08x %08x -> base 0x%" PRIx64 " stride %u records %u", d[0], d[1], d[2], d[3], base, stride, d[2]);
}
static void timeout_probe(const uint32_t* sub_ib, uint32_t sub_n, const char* kind, uint64_t n, const std::vector<uint32_t>* ran, const std::vector<GeProbeSlot>* gep = nullptr) {
'''),
        # 2. Exp 0277's probe fix: the declaration beside the rebuild's state.
        ('''	std::vector<uint32_t> mec_positions;         // offsets of its compute-form DISPATCH_INDIRECT
''', 1, '''	std::vector<uint32_t> mec_positions;         // offsets of its compute-form DISPATCH_INDIRECT
	std::vector<uint32_t> probe_old_to_new;       // experiment 0277's probe fix, carried by 0302: the timeout probe reads the rebuilt IB, so its executed offsets go forward again
'''),
        # 3. Filter time: the snapshot, after the skip lists and the ray-tracing-off drop (those `continue` past this point).
        ('''			if (type == 3 && (op == 0x2c || op == 0x38) && len >= 10 && ib[q + 5] > 65536u) { // experiment 0054
''', 1, '''			// Experiment 0302: a listed program's dispatch (BC5_DIRECT_TABLE_PGM; default the 0x11d03a family of F360): its
			// resource table at user SGPRs 12-13 (COMPUTE_USER_DATA_12/13 as this buffer or its LOAD tables set them), slots
			// +0x00..+0x90, read now — the CPU's view before the submit — and kept for the timeout probe, which reads the
			// same slots then (exp 0297 step 2). Journaled at once when the table is unmapped, spans two mappings (the
			// supervisor's lead: 0x11e0fbff70 straddled a page) or a slot's V# base is unmapped now — the title handed the
			// GPU a bad descriptor (exp 0300 S2: the fault address sat in slot +0x60 of the last 0x11d03a4600's table).
			if (type == 3 && (op == 0x15 || op == 0x16) && pgm != 0 && table_pgm_list().count(pgm) != 0 && (ud[12] != 0 || ud[13] != 0)) {
				TableSnap s;
				s.pgm     = pgm;
				s.submit  = g_submits.load();
				s.t       = tsnap_now();
				s.table   = static_cast<uint64_t>(ud[12]) | (static_cast<uint64_t>(ud[13] & 0xffffu) << 32u);
				s.covered = covered_sorted(*maps_p, s.table, 0xa0);
				s.map_lo  = tsnap_map_index(*maps_p, s.table);
				s.map_hi  = tsnap_map_index(*maps_p, s.table + 0x9cu);
				if (s.covered) {
					const auto* t = reinterpret_cast<const volatile uint32_t*>(s.table);
					for (int k = 0; k < 40; k++) s.slots[k] = t[k];
				}
				int bad = -1;
				if (s.covered) {
					for (int k = 0; k < 10 && bad < 0; k++) {
						const uint64_t b = s.slots[4 * k] | (static_cast<uint64_t>(s.slots[4 * k + 1] & 0xffffu) << 32u);
						if (b != 0 && !covered_sorted(*maps_p, b, 4)) bad = k;
					}
				}
				static std::atomic<uint64_t> n_snap {0}, n_loud {0};
				const uint64_t ns   = n_snap++;
				const bool     loud = !s.covered || bad >= 0 || s.map_lo != s.map_hi;
				if ((loud && n_loud++ < 256) || (ns & 0xfffu) == 0) {
					char ml[96], mh[96], bs[240] = "";
					tsnap_map_desc(*maps_p, s.map_lo, ml, sizeof(ml));
					tsnap_map_desc(*maps_p, s.map_hi, mh, sizeof(mh));
					if (bad >= 0) {
						char vs[160];
						tsnap_vsharp(vs, sizeof(vs), s.slots + 4 * bad);
						std::snprintf(bs, sizeof(bs), " BAD SLOT +0x%02x: %s (base not mapped now)", bad * 16, vs);
					}
					journal("descriptor (exp 0302): %s dispatch op %02x at %u of 0x%" PRIx64 " before #%" PRIu64 ": table 0x%" PRIx64 " %s, mapping %s / +0x9c %s%s%s (%" PRIu64 " snapshots)\\n", kind, op, q, pgm, s.submit,
					        s.table, s.covered ? "mapped" : "NOT MAPPED", ml, mh, s.map_lo != s.map_hi ? " SPANS TWO MAPPINGS" : "", bs, ns + 1);
				}
				std::lock_guard<std::mutex> lk(g_tsnap_m);
				g_tsnaps.push_back(s);
				if (g_tsnaps.size() > 4096) g_tsnaps.pop_front();
			}
			if (type == 3 && (op == 0x2c || op == 0x38) && len >= 10 && ib[q + 5] > 65536u) { // experiment 0054
'''),
        # 4-7. Exp 0277's probe fix.
        ('''			sub_ib = mec_ib.data();
			sub_n  = static_cast<uint32_t>(mec_ib.size());
''', 1, '''			sub_ib = mec_ib.data();
			sub_n  = static_cast<uint32_t>(mec_ib.size());
			probe_old_to_new.swap(old_to_new); // experiment 0277's probe fix (exp 0302)
'''),
        ('''	auto r = g_dev->submit(std::span<const uint32_t>(sub_ib, sub_n), opt, 2'000'000'000ull, with_gds, qring);
	mec_back(r.executed_offsets);
''', 1, '''	auto probe_ran = [&probe_old_to_new](const std::vector<uint32_t>& offsets) { // experiment 0277's probe fix (exp 0302)
		if (probe_old_to_new.empty()) return offsets;
		std::vector<uint32_t> fwd;
		fwd.reserve(offsets.size());
		for (const uint32_t o: offsets) {
			if (o < probe_old_to_new.size() && probe_old_to_new[o] != ~0u) fwd.push_back(probe_old_to_new[o]);
		}
		return fwd;
	};
	auto r = g_dev->submit(std::span<const uint32_t>(sub_ib, sub_n), opt, 2'000'000'000ull, with_gds, qring);
	mec_back(r.executed_offsets);
'''),
        ('''	if (r.timed_out) timeout_probe(sub_ib, sub_n, kind, g_submits.load(), &r.executed_offsets); // experiment 0160
''', 1, '''	if (r.timed_out) { // experiment 0160; experiment 0277's probe fix (exp 0302): the executed offsets in the rebuilt IB
		const std::vector<uint32_t> ran_new = probe_ran(r.executed_offsets);
		timeout_probe(sub_ib, sub_n, kind, g_submits.load(), &ran_new);
	}
'''),
        ('''it.job.ran_copy = r.executed_offsets; } // experiment 0160
''', 1, '''it.job.ran_copy = probe_ran(r.executed_offsets); } // experiment 0160 (0277's probe fix, exp 0302: in the rebuilt IB)
'''),
        # 8. The probe: exp 0297 step 2's table dump (as exp 0300 built it) with the filter-time comparison.
        ('''					n_disp++;
				}
				if (op == 0x11 || op == 0x26 || op == 0x13 || op == 0x2a''', 1, '''					// Experiment 0297 step 2 as exp 0300 built it, plus exp 0302's comparison: for a dispatch of a listed program
					// (table_pgm_list), the resource table at user SGPRs 12-13 (SH 0x24c/0x24d as this buffer or its LOAD tables set
					// them): slots +0x00..+0x90 as V#s (gfx10 buffer resource, TODO(verify) the field positions), the V# chained from
					// slot +0x80's buffer at +0x680 (0x11d03a4600's store descriptor), each extent against BC5_DIRECT_PROBE_LABEL=<hex>
					// when set, whether a base is unmapped — and each slot against its filter-time snapshot (the same table address and
					// program, the CPU's view before the submit): CHANGED slots with their old dwords, or "no filter-time snapshot".
					// Read-only; at most 96 tables a process.
					{
						static const uint64_t        probe_label = std::getenv("BC5_DIRECT_PROBE_LABEL") != nullptr ? std::strtoull(std::getenv("BC5_DIRECT_PROBE_LABEL"), nullptr, 16) : 0;
						static std::atomic<uint32_t> n_tables {0};
						const uint64_t               pg = (static_cast<uint64_t>(pl) | (static_cast<uint64_t>(ph & 0xffu) << 32u)) << 8u;
						if (pl != 0xffffffffu && table_pgm_list().count(pg) != 0 && n_tables++ < 96) {
							const uint32_t u12 = g(st_sh, 0x24cu), u13 = g(st_sh, 0x24du), rsrc2 = g(st_sh, 0x213u);
							const uint64_t tb  = (u12 == 0xffffffffu || u13 == 0xffffffffu) ? 0 : (static_cast<uint64_t>(u12) | (static_cast<uint64_t>(u13 & 0xffffu) << 32u));
							TableSnap snap;
							bool      have_snap = false;
							if (tb != 0) {
								std::lock_guard<std::mutex> lk(g_tsnap_m);
								for (auto it = g_tsnaps.rbegin(); it != g_tsnaps.rend(); ++it) {
									if (it->table == tb && it->pgm == pg) { snap = *it; have_snap = true; break; }
								}
							}
							char ml[96] = "?", mh[96] = "?", nl[96], nh[96];
							if (have_snap) { tsnap_map_desc(*pm, snap.map_lo, ml, sizeof(ml)); tsnap_map_desc(*pm, snap.map_hi, mh, sizeof(mh)); }
							tsnap_map_desc(*pm, tsnap_map_index(*pm, tb), nl, sizeof(nl));
							tsnap_map_desc(*pm, tsnap_map_index(*pm, tb + 0x9cu), nh, sizeof(nh));
							journal("timeout probe: table (exp 0302): dispatch op %02x at %u of 0x%" PRIx64 ": user sgpr 12-13 %08x %08x -> table 0x%" PRIx64 " (%smapped; mapping now %s / +0x9c %s), rsrc2 %08x (%u user sgprs)%s; %s\\n", op, q, pg, u12, u13, tb,
							        tb != 0 && covered_sorted(*pm, tb, 0xa0) ? "" : "not ", nl, nh, rsrc2, rsrc2 == 0xffffffffu ? 0u : (rsrc2 >> 1u) & 0x1fu, probe_label != 0 ? "" : ", no BC5_DIRECT_PROBE_LABEL",
							        have_snap ? "filter-time snapshot found" : "NO FILTER-TIME SNAPSHOT of this table address (the user data differ between the two readings)");
							if (have_snap) {
								journal("timeout probe: table (exp 0302):   snapshot before #%" PRIu64 ", %.3f s ago: table %s then, mapping %s / +0x9c %s%s\\n", snap.submit, tsnap_now() - snap.t, snap.covered ? "mapped" : "NOT MAPPED", ml, mh,
								        snap.map_lo != snap.map_hi ? " (SPANNED TWO MAPPINGS)" : "");
							}
							auto vsharp = [&](const char* what, uint64_t at) -> uint64_t {
								if (!covered_sorted(*pm, at, 16)) {
									journal("timeout probe: table (exp 0302): %s at 0x%" PRIx64 ": not mapped\\n", what, at);
									return 0;
								}
								const auto*    d  = reinterpret_cast<const volatile uint32_t*>(at);
								const uint32_t d0 = d[0], d1 = d[1], d2 = d[2], d3 = d[3];
								const uint64_t base   = d0 | (static_cast<uint64_t>(d1 & 0xffffu) << 32u);
								const uint32_t stride = (d1 >> 16u) & 0x3fffu;
								const uint64_t bytes  = stride != 0 ? static_cast<uint64_t>(d2) * stride : d2;
								const bool     covers = probe_label != 0 && base <= probe_label && probe_label + 4 <= base + bytes;
								journal("timeout probe: table (exp 0302): %s at 0x%" PRIx64 ": %08x %08x %08x %08x -> base 0x%" PRIx64 " stride %u records %u = %" PRIu64 " bytes [0x%" PRIx64 ", 0x%" PRIx64 ")%s%s\\n", what, at, d0, d1, d2, d3,
								        base, stride, d2, bytes, base, base + bytes, covers ? " COVERS THE LABEL" : "", base != 0 && !covered_sorted(*pm, base, 4) ? ", BASE NOT MAPPED" : "");
								return base;
							};
							if (tb != 0) {
								uint32_t n_same = 0, n_changed = 0;
								for (uint32_t s = 0; s <= 0x90u; s += 0x10u) {
									char what[32];
									std::snprintf(what, sizeof(what), "slot +0x%02x", s);
									const uint64_t b = vsharp(what, tb + s);
									if (have_snap && snap.covered && covered_sorted(*pm, tb + s, 16)) {
										const auto*     d = reinterpret_cast<const volatile uint32_t*>(tb + s);
										const uint32_t* o = snap.slots + s / 4;
										if (d[0] == o[0] && d[1] == o[1] && d[2] == o[2] && d[3] == o[3]) n_same++;
										else {
											n_changed++;
											journal("timeout probe: table (exp 0302):   slot +0x%02x CHANGED since filter time: then %08x %08x %08x %08x\\n", s, o[0], o[1], o[2], o[3]);
										}
									}
									if (s == 0x80u && b != 0) vsharp("slot +0x80 -> +0x680 (the store V#)", b + 0x680u);
								}
								if (have_snap && snap.covered) journal("timeout probe: table (exp 0302):   %u slots unchanged, %u CHANGED since filter time\\n", n_same, n_changed);
							}
						}
					}
					n_disp++;
				}
				if (op == 0x11 || op == 0x26 || op == 0x13 || op == 0x2a'''),
    ],
}


def main():
    if len(sys.argv) != 3:
        print('usage: patch0302.py <src root> <out dir>')
        sys.exit(2)
    root, out = sys.argv[1], sys.argv[2]
    os.makedirs(out, exist_ok=True)
    diff = []
    for rel, edits in EDITS.items():
        path = os.path.join(root, rel)
        src = open(path, encoding='utf-8').read()
        print(f'{rel}: md5 {hashlib.md5(src.encode("utf-8")).hexdigest()[:8]} in')
        dst = src
        for k, (old, n, new) in enumerate(edits, 1):
            c = dst.count(old)
            if c != n:
                print(f'{rel}: edit {k}: anchor found {c} times, expected {n}:\n{old}')
                sys.exit(1)
            dst = dst.replace(old, new)
        target = os.path.join(out, os.path.basename(rel))
        open(target, 'w', encoding='utf-8', newline='\n').write(dst)
        diff += difflib.unified_diff(src.splitlines(True), dst.splitlines(True), 'a/' + rel, 'b/' + rel)
        print(f'{rel}: {len(edits)} edits -> {target}, md5 {hashlib.md5(dst.encode("utf-8")).hexdigest()[:8]} out')
    open(os.path.join(out, 'patch_0302.diff'), 'w', encoding='utf-8', newline='\n').write(''.join(diff))
    print(f'patch_0302.diff: {sum(1 for l in diff if l.startswith("+") and not l.startswith("+++"))} added lines')


if __name__ == '__main__':
    main()
