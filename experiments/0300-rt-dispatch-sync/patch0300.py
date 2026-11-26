#!/usr/bin/env python3
# BC5 experiment 0300: a sync packet behind every dispatch of the ray-tracing build families, and (exp 0297 step 2)
# the resource-table dump in the timeout probe. Both in src/libs/bc5LleAgc.cpp of the shared tree as integrated on the
# box (md5 5bccbb80: patch 0001 on main at 64179e6, exp 0272's probe in, exp 0277's breadcrumbs not in).
#   1. KYTY_BC5_RT_SYNC_PGM=<hex list> (as BC5_DIRECT_SKIP_PGM's): a dispatch (DISPATCH_DIRECT 0x15 or DISPATCH_INDIRECT
#      0x16, either form) of a listed program that goes to the GPU gets one packet behind it in the rebuilt IB
#      (exp 0038's rebuild, ADR 0010 section A; it already grows the IB's own COND_EXEC counts around insertions and
#      maps offsets both ways): EVENT_WRITE CS_PARTIAL_FLUSH (event 7, EVENT_INDEX 4: tools/bc5-agc/regdb/gfx10.json,
#      Mesa sid.h V_028A90_CS_PARTIAL_FLUSH; the console's own compute IBs carry it between dependent dispatches,
#      backend/src/direct.cpp), or with KYTY_BC5_RT_SYNC=eop the data-less RELEASE_MEM BOTTOM_OF_PIPE_TS (event 40,
#      EVENT_INDEX 5, DATA_SEL 0 — the shape exp 0277's done mark had, without the write; policy.cpp passes it,
#      address 0 is normal). Dispatches the host drops get none. Without the list the GPU stream is unchanged: the
#      rebuild runs only for BC5_DIRECT_MEC_INDIRECT, as before (the compute-form conversion stays tied to it).
#      Why: exp 0294 S1 — exp 0277's per-dispatch end-of-pipe release behind every dispatch hid the F332/F360 hang
#      for 600 s of the S6N route; this is that effect alone, on the build families alone, with nothing written.
#   2. The probe (BC5_DIRECT_TIMEOUT_PROBE=1, at a fence timeout): for a dispatch of a program in
#      BC5_DIRECT_PROBE_TABLE_PGM (hex list; default the 0x11d03a family of F360: 0x11d03a2000, 3400, 3500, 4600,
#      0x11d039f000, 0x11d03a0700), the resource table at user SGPRs 12-13 (COMPUTE_USER_DATA_12/13, SH 0x24c/0x24d as
#      the buffer or its LOAD tables set them), its slots +0x00..+0x90 read as V#s, the V# chained from slot +0x80's
#      buffer at +0x680 (0x11d03a4600's store descriptor, exp 0297 step 1), each extent against
#      BC5_DIRECT_PROBE_LABEL=<hex> when set, and whether a base is unmapped. Read-only, host side, no packet added.
# usage: patch0300.py <src root of the shared tree> <out dir>   (writes <out dir>/bc5LleAgc.cpp and <out dir>/patch_0300.diff;
#        the inputs are only read; every anchor must occur exactly the number of times given)
import difflib, hashlib, os, sys

EDITS = {
    'src/libs/bc5LleAgc.cpp': [
        # 1. The IB-level state, beside the rebuild's.
        ('''	std::vector<uint32_t> mec_positions;         // offsets of its compute-form DISPATCH_INDIRECT
''', 1, '''	std::vector<uint32_t> mec_positions;         // offsets of its compute-form DISPATCH_INDIRECT
	bool                  rt_sync_ib = false;     // experiment 0300: the IB has dispatches that get a sync packet behind them
	std::vector<uint32_t> rt_sync_positions;     // experiment 0300: their offsets, ascending (the filter walks the IB once)
	std::vector<uint32_t> probe_old_to_new;       // experiment 0277's probe fix, carried by 0300: the timeout probe reads the rebuilt IB, so its executed offsets go forward again
'''),
        # 2. The filter records the listed dispatches that reach this point (the skip lists and the ray-tracing-off
        #    drop have taken theirs out with `continue` above; the indirect checks below may still drop one, and the
        #    rebuild looks at the drop list before inserting).
        ('''			if (type == 3 && (op == 0x2c || op == 0x38) && len >= 10 && ib[q + 5] > 65536u) { // experiment 0054
''', 1, '''			// Experiment 0300: a dispatch of a listed program (KYTY_BC5_RT_SYNC_PGM, a hex list as the other
			// lists) gets a sync packet behind it in the rebuilt IB (with the rebuild below): EVENT_WRITE
			// CS_PARTIAL_FLUSH by default, the data-less RELEASE_MEM BOTTOM_OF_PIPE_TS with KYTY_BC5_RT_SYNC=eop.
			// A dispatch the host drops gets none. Without the list nothing changes.
			{
				static const std::set<uint64_t> rt_sync = pgm_list("KYTY_BC5_RT_SYNC_PGM");
				if (!rt_sync.empty() && type == 3 && (op == 0x15 || op == 0x16) && rt_sync.count(pgm) != 0) {
					rt_sync_positions.push_back(q);
					static std::atomic<uint64_t> n_listed {0};
					if ((n_listed++ & 0xfffu) == 0) journal("  rt sync (exp 0300): %s dispatch op %02x at %u of 0x%" PRIx64 " listed (%" PRIu64 " so far)\\n", kind, op, q, pgm, n_listed.load());
				}
			}
			if (type == 3 && (op == 0x2c || op == 0x38) && len >= 10 && ib[q + 5] > 65536u) { // experiment 0054
'''),
        # 3. The trigger: the rebuild also runs for an IB with listed dispatches.
        ('''		if (!mec_hi.empty() && mec_on) mec_expand_ib = true;
''', 1, '''		if (!mec_hi.empty() && mec_on) mec_expand_ib = true;
		if (!rt_sync_positions.empty()) rt_sync_ib = true; // experiment 0300
'''),
        # 4. The rebuild's entry: the packet's choice, once; the count.
        ('''	if (mec_expand_ib) {
''', 1, '''	// Experiment 0300: the rebuild also carries the sync packets (rt_sync_positions). The compute-form conversion
	// stays tied to mec_expand_ib (BC5_DIRECT_MEC_INDIRECT), so an IB rebuilt for the sync packets alone keeps its
	// dispatches as they are, on either ring.
	static const bool            rt_sync_eop = [] { const char* e = std::getenv("KYTY_BC5_RT_SYNC"); return e != nullptr && std::strcmp(e, "eop") == 0; }();
	static std::atomic<uint64_t> rt_sync_n {0};
	if (mec_expand_ib || rt_sync_ib) {
'''),
        # 5. The compute-form conversion only when the rebuild runs for it.
        ('''				const bool is_mec  = (h >> 30u) == 3 && ((h >> 8u) & 0xffu) == 0x16 && len == 4 && !dropped;
''', 1, '''				const bool is_mec  = mec_expand_ib && (h >> 30u) == 3 && ((h >> 8u) & 0xffu) == 0x16 && len == 4 && !dropped; // experiment 0300: mec_expand_ib &&
'''),
        # 6. Room for the insertions.
        ('''			mec_ib.reserve(num_dwords + 5 * mec_positions.size());
''', 1, '''			mec_ib.reserve(num_dwords + 5 * mec_positions.size() + 8 * rt_sync_positions.size()); // experiment 0300: + the sync packets
'''),
        # 7. The insertion, behind the dispatch (rebuilt or copied), inside the rebuild loop.
        ('''					mec_ib.insert(mec_ib.end(), ib + q, ib + q + len);
				}
				q += len;
''', 1, '''					mec_ib.insert(mec_ib.end(), ib + q, ib + q + len);
				}
				if (rt_sync_ib && !dropped && std::binary_search(rt_sync_positions.begin(), rt_sync_positions.end(), q)) { // experiment 0300
					if (rt_sync_eop) mec_ib.insert(mec_ib.end(), {0xC0064900u, 0x28u | (5u << 8u), 0u, 0u, 0u, 0u, 0u, 0u}); // RELEASE_MEM BOTTOM_OF_PIPE_TS, EVENT_INDEX 5, DATA_SEL 0, INT_SEL 0
					else mec_ib.insert(mec_ib.end(), {0xC0004600u, 0x7u | (4u << 8u)});                                  // EVENT_WRITE CS_PARTIAL_FLUSH, EVENT_INDEX 4
					if (attempt == 0 && (rt_sync_n++ & 0xfffu) == 0) {
						journal("rt sync (exp 0300): %s %u dwords: %s behind the dispatch at %u (%" PRIu64 " inserted so far)\\n", kind, num_dwords, rt_sync_eop ? "RELEASE_MEM BOTTOM_OF_PIPE_TS" : "CS_PARTIAL_FLUSH", q, rt_sync_n.load());
					}
				}
				q += len;
'''),
        # 8-11. Exp 0277's probe fix, needed now that the rebuild runs for more IBs than BC5_DIRECT_MEC_INDIRECT's: the
        #    probe walks the rebuilt IB, so the executed offsets (mapped back to the original by mec_back) go forward
        #    again for it; without this every packet of a rebuilt IB behind the first insertion read "DROPPED".
        ('''			sub_ib = mec_ib.data();
			sub_n  = static_cast<uint32_t>(mec_ib.size());
''', 1, '''			sub_ib = mec_ib.data();
			sub_n  = static_cast<uint32_t>(mec_ib.size());
			probe_old_to_new.swap(old_to_new); // experiment 0277's probe fix (exp 0300)
'''),
        ('''	auto r = g_dev->submit(std::span<const uint32_t>(sub_ib, sub_n), opt, 2'000'000'000ull, with_gds, qring);
	mec_back(r.executed_offsets);
''', 1, '''	auto probe_ran = [&probe_old_to_new](const std::vector<uint32_t>& offsets) { // experiment 0277's probe fix (exp 0300)
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
''', 1, '''	if (r.timed_out) { // experiment 0160; experiment 0277's probe fix (exp 0300): the executed offsets in the rebuilt IB
		const std::vector<uint32_t> ran_new = probe_ran(r.executed_offsets);
		timeout_probe(sub_ib, sub_n, kind, g_submits.load(), &ran_new);
	}
'''),
        ('''it.job.ran_copy = r.executed_offsets; } // experiment 0160
''', 1, '''it.job.ran_copy = probe_ran(r.executed_offsets); } // experiment 0160 (0277's probe fix, exp 0300: in the rebuilt IB)
'''),
        # 12. The probe (exp 0297 step 2): the resource table of the listed programs' dispatches, at the timeout.
        ('''					n_disp++;
				}
				if (op == 0x11 || op == 0x26 || op == 0x13 || op == 0x2a''', 1, '''					// Experiment 0297 step 2 (built with exp 0300): for a dispatch of a listed program (BC5_DIRECT_PROBE_TABLE_PGM,
					// hex list; default the 0x11d03a family of F360), the resource table at user SGPRs 12-13 (COMPUTE_USER_DATA_12/13,
					// SH 0x24c/0x24d, as this buffer or its LOAD tables set them; the programs read it as s[12:13], exp 0297 step 1):
					// slots +0x00..+0x90 as V#s — gfx10 buffer resource: dword 0 base[31:0], dword 1 base[47:32] | stride[29:16],
					// dword 2 num_records (in units of the stride when it is non-zero, else bytes), dword 3 the selects and format
					// (LLVM AMDGPUUsage "Buffer Resource Descriptor", TODO(verify) the field positions against the gfx10 table) —
					// then the V# chained from slot +0x80's buffer at +0x680 (0x11d03a4600's store descriptor), each extent against
					// BC5_DIRECT_PROBE_LABEL=<hex> when set, and whether a base is unmapped. COMPUTE_PGM_RSRC2 (SH 0x213) gives the
					// user SGPR count in bits 5:1 (Mesa gfx10 register JSON, TODO(verify)). Read-only; at most 96 tables a process.
					{
						static const std::set<uint64_t> probe_pgm = [] {
							std::set<uint64_t> s;
							if (const char* e = std::getenv("BC5_DIRECT_PROBE_TABLE_PGM"); e != nullptr) {
								for (const char* p = e; *p != 0;) {
									char*          end = nullptr;
									const uint64_t v   = std::strtoull(p, &end, 16);
									if (end == p) { p++; continue; }
									s.insert(v);
									p = end;
								}
							} else {
								s = {0x11d03a2000ull, 0x11d03a3400ull, 0x11d03a3500ull, 0x11d03a4600ull, 0x11d039f000ull, 0x11d03a0700ull};
							}
							return s;
						}();
						static const uint64_t        probe_label = std::getenv("BC5_DIRECT_PROBE_LABEL") != nullptr ? std::strtoull(std::getenv("BC5_DIRECT_PROBE_LABEL"), nullptr, 16) : 0;
						static std::atomic<uint32_t> n_tables {0};
						const uint64_t               pg = (static_cast<uint64_t>(pl) | (static_cast<uint64_t>(ph & 0xffu) << 32u)) << 8u;
						if (pl != 0xffffffffu && probe_pgm.count(pg) != 0 && n_tables++ < 96) {
							const uint32_t u12 = g(st_sh, 0x24cu), u13 = g(st_sh, 0x24du), rsrc2 = g(st_sh, 0x213u);
							const uint64_t tb  = (u12 == 0xffffffffu || u13 == 0xffffffffu) ? 0 : (static_cast<uint64_t>(u12) | (static_cast<uint64_t>(u13 & 0xffffu) << 32u));
							journal("timeout probe: table (exp 0297): dispatch op %02x at %u of 0x%" PRIx64 ": user sgpr 12-13 %08x %08x -> table 0x%" PRIx64 " (%smapped), rsrc2 %08x (%u user sgprs)%s\\n", op, q, pg, u12, u13, tb,
							        tb != 0 && covered_sorted(*pm, tb, 0xa0) ? "" : "not ", rsrc2, rsrc2 == 0xffffffffu ? 0u : (rsrc2 >> 1u) & 0x1fu, probe_label != 0 ? "" : ", no BC5_DIRECT_PROBE_LABEL");
							auto vsharp = [&](const char* what, uint64_t at) -> uint64_t {
								if (!covered_sorted(*pm, at, 16)) {
									journal("timeout probe: table (exp 0297): %s at 0x%" PRIx64 ": not mapped\\n", what, at);
									return 0;
								}
								const auto*    d  = reinterpret_cast<const volatile uint32_t*>(at);
								const uint32_t d0 = d[0], d1 = d[1], d2 = d[2], d3 = d[3];
								const uint64_t base   = d0 | (static_cast<uint64_t>(d1 & 0xffffu) << 32u);
								const uint32_t stride = (d1 >> 16u) & 0x3fffu;
								const uint64_t bytes  = stride != 0 ? static_cast<uint64_t>(d2) * stride : d2;
								const bool     covers = probe_label != 0 && base <= probe_label && probe_label + 4 <= base + bytes;
								journal("timeout probe: table (exp 0297): %s at 0x%" PRIx64 ": %08x %08x %08x %08x -> base 0x%" PRIx64 " stride %u records %u = %" PRIu64 " bytes [0x%" PRIx64 ", 0x%" PRIx64 ")%s%s\\n", what, at, d0, d1, d2, d3,
								        base, stride, d2, bytes, base, base + bytes, covers ? " COVERS THE LABEL" : "", base != 0 && !covered_sorted(*pm, base, 4) ? ", BASE NOT MAPPED" : "");
								return base;
							};
							if (tb != 0) {
								for (uint32_t s = 0; s <= 0x90u; s += 0x10u) {
									char what[32];
									std::snprintf(what, sizeof(what), "slot +0x%02x", s);
									const uint64_t b = vsharp(what, tb + s);
									if (s == 0x80u && b != 0) vsharp("slot +0x80 -> +0x680 (the store V#)", b + 0x680u);
								}
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
        print('usage: patch0300.py <src root> <out dir>')
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
    open(os.path.join(out, 'patch_0300.diff'), 'w', encoding='utf-8', newline='\n').write(''.join(diff))
    print(f'patch_0300.diff: {sum(1 for l in diff if l.startswith("+") and not l.startswith("+++"))} added lines')


if __name__ == '__main__':
    main()
