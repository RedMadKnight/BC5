#!/usr/bin/env python3
"""BC5 experiment 0412, tags tl412 and dc412 (README section 89), both default off, catchers only:
  BC5_TIMEOUT_LAYOUT=1  at a timeout, before the long probe: <capture dir>/timeout-layout-<job>-<kind>.txt with every
                        dispatch of the timed-out buffer (program, initiator, groups, how often dc412 saw it) and,
                        for every address its user data may hold, the view it lies in (name, eager / lazy / by data,
                        chunk imported or not, GPU mapping or not); fsync'd; then the whole view list; fsync'd again,
                        and the directory. Written first because the kernel may be crashed 0.2 s later (arm n8F8).
  BC5_DISPATCH_COUNT=1  every submitted buffer's dispatches are counted by program, initiator and kind; every 60 s
                        the 300 rarest go to the journal.
The walk and the counter are dw0412.inc (CPU test dw0412.cpp). Nothing here changes a buffer or a mapping.
Input: a main unit with tag ph412 (mkph0412.py's output, 4a8d5211). Every anchor exactly once.
usage: mkdw0412.py <bc5LleAgc.cpp in> <bc5LleAgc.cpp out>"""
import hashlib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

DW_GLUE = rb'''// Experiment 0412 (tags tl412, dc412): the host's part of dw0412.inc.
static std::mutex     g_dc412_mutex;
static dw412::Counter g_dc412;
static bool dw412_read_table(const std::vector<bc5::direct::Mapping>& maps, uint64_t a, uint32_t pairs, std::vector<uint32_t>& out) {
	if (!covered_sorted(maps, a, static_cast<uint64_t>(pairs) * 8)) return false;
	const auto* t = reinterpret_cast<const volatile uint32_t*>(a);
	out.resize(2ull * pairs);
	for (uint32_t k = 0; k < 2 * pairs; k++) out[k] = t[k];
	return true;
}
static void dc412_count(const uint32_t* ib, uint32_t n) {
	if (!dw412::dc_on() || ib == nullptr || n == 0 || !g_dev) return;
	const auto      pm = g_dev->sorted_mappings();
	const double    t  = timing_now();
	std::lock_guard lock(g_dc412_mutex);
	dw412::walk(
	    ib, n, [&](uint64_t a, uint32_t p, std::vector<uint32_t>& o) { return dw412_read_table(*pm, a, p, o); }, [&](const dw412::Dispatch& d) { g_dc412.add(d, t); });
	static double last = 0;
	if (t - last < 60.0) return;
	last = t;
	journal("dispatch count (exp 0412, tag dc412): t %.1f s: %" PRIu64 " dispatches so far, %zu kinds (program, initiator, direct or indirect), %" PRIu64 " with no program set in their buffer; the 300 rarest follow\n", t,
	        g_dc412.dispatches, g_dc412.m.size(), g_dc412.unknown_program);
	g_dc412.report(300, [&](const dw412::Key& k, const dw412::Val& v) {
		journal("dispatch count (exp 0412, tag dc412): program 0x%" PRIx64 " initiator 0x%x %s: %" PRIu64 " times, %" PRIu64 " groups, first t %.1f s, last t %.1f s\n", k.program, k.initiator,
		        k.op == 0x16u ? "indirect" : "direct", v.n, v.groups, v.first_t, v.last_t);
	});
}
static void tl412_record(const uint32_t* ib, uint32_t n, const char* kind, uint64_t job) {
	if (!dw412::tl_on() || ib == nullptr || n == 0 || g_dump_dir.empty() || !g_dev) return;
	const double t0 = timing_now();
	char         name[512];
	std::snprintf(name, sizeof(name), "%s/timeout-layout-%08" PRIu64 "-%.8s.txt", g_dump_dir.c_str(), job, kind);
	FILE* f = std::fopen(name, "w");
	if (f == nullptr) return;
	const auto pm = g_dev->sorted_mappings();
	struct VRef {
		uint64_t     va, end;
		int          kind;
		const DView* v;
	};
	std::vector<std::shared_ptr<const DViews>> keep;
	std::vector<VRef>                          vr;
	for (auto& S: g_d) {
		if (dstate_fd(S) < 0) continue;
		keep.push_back(direct_views(S));
		for (const auto& v: keep.back()->v) vr.push_back(VRef {v.va, v.va + v.size, S.kind, &v});
	}
	std::sort(vr.begin(), vr.end(), [](const VRef& a, const VRef& b) { return a.va < b.va; });
	auto find = [&](uint64_t a) -> const VRef* {
		auto it = std::upper_bound(vr.begin(), vr.end(), a, [](uint64_t x, const VRef& r) { return x < r.va; });
		for (int back = 0; back < 8 && it != vr.begin(); back++) { // views are not nested deeper than this (aliases)
			--it;
			if (a < it->end) return &*it;
		}
		return nullptr;
	};
	std::fprintf(f, "# exp 0412 (tag tl412): the dispatches of the timed-out %s #%" PRIu64 " (%u dwords), t %.3f s; written before the probe\n", kind, job, n, t0);
	std::fprintf(f, "# per dispatch: offset, kind, program, initiator (bit 15 CS_W32_EN), groups, times dc412 counted it before (-1: dc412 off)\n");
	std::fprintf(f, "# per address its user data may hold (b: buffer reading, t: texture reading): the view, E eager / L lazy / D by data, the address into the view, its 2 MiB chunk imported or not, a GPU mapping there or not\n");
	uint32_t   n_disp = 0;
	const bool whole  = dw412::walk(
	    ib, n, [&](uint64_t a, uint32_t p, std::vector<uint32_t>& o) { return dw412_read_table(*pm, a, p, o); },
	    [&](const dw412::Dispatch& d) {
		    n_disp++;
		    long long seen = -1;
		    if (dw412::dc_on()) {
			    std::lock_guard lock(g_dc412_mutex);
			    seen = static_cast<long long>(g_dc412.seen(d));
		    }
		    char grid[64] = "?";
		    if (d.groups_known) std::snprintf(grid, sizeof(grid), "%u x %u x %u", d.gx, d.gy, d.gz);
		    else std::snprintf(grid, sizeof(grid), "arguments at 0x%" PRIx64, d.args);
		    std::fprintf(f, "dispatch at %u %s program %s0x%" PRIx64 " initiator 0x%x groups %s seen %lld\n", d.at, d.op == 0x16u ? "indirect" : "direct", d.program_known ? "" : "(not set in this buffer) ", d.program,
		                 d.initiator, grid, seen);
		    dw412::candidates(d, [&](uint32_t k, char form, uint64_t a) {
			    const VRef* r = find(a);
			    if (r == nullptr) return;
			    const DView&   v        = *r->v;
			    const bool     imported = direct_covered_end(g_d[r->kind], (v.off + (a - v.va)) & ~(kDChunk - 1)) != 0;
			    const bool     mapped   = covered_sorted(*pm, a & ~0xfffull, 4);
			    std::fprintf(f, "  ud%u %c 0x%" PRIx64 ": \"%s\" (%s file) %s, 0x%" PRIx64 " into the view 0x%" PRIx64 "+0x%" PRIx64 ", chunk %s, GPU mapping %s\n", k, form, a, v.name.c_str(),
			                 r->kind == 0 ? "direct" : "private", v.eager ? "E" : (v.lazy ? "L" : "D"), a - v.va, v.va, v.size, imported ? "imported" : "NOT imported", mapped ? "yes" : "NO");
			    if (form != 'b' || !mapped || !covered_sorted(*pm, a, 64)) return;
			    // the second level (README section 90): the first 16 dwords there, and the views of what they may hold
			    dw412::Dispatch in;
			    const auto*     w = reinterpret_cast<const volatile uint32_t*>(a);
			    for (int j = 0; j < 16; j++) in.ud[j] = w[j];
			    in.ud_known = 0xffffu;
			    std::fprintf(f, "    its first 16 dwords:");
			    for (int j = 0; j < 16; j++) std::fprintf(f, " %08x", in.ud[j]);
			    std::fprintf(f, "\n");
			    dw412::candidates(in, [&](uint32_t k2, char form2, uint64_t a2) {
				    const VRef* r2 = find(a2);
				    if (r2 == nullptr) return;
				    const DView& v2   = *r2->v;
				    const bool   imp2 = direct_covered_end(g_d[r2->kind], (v2.off + (a2 - v2.va)) & ~(kDChunk - 1)) != 0;
				    std::fprintf(f, "    -> dword %u %c 0x%" PRIx64 ": \"%s\" (%s file) %s, chunk %s, GPU mapping %s\n", k2, form2, a2, v2.name.c_str(), r2->kind == 0 ? "direct" : "private",
				                 v2.eager ? "E" : (v2.lazy ? "L" : "D"), imp2 ? "imported" : "NOT imported", covered_sorted(*pm, a2 & ~0xfffull, 4) ? "yes" : "NO");
			    });
		    });
	    });
	std::fprintf(f, "# %u dispatches%s; this part took %.1f ms\n", n_disp, whole ? "" : "; the walk STOPPED at a packet running past the end", (timing_now() - t0) * 1000.0);
	std::fflush(f);
	fsync(fileno(f)); // the part that matters is on the disk now
	std::fprintf(f, "# every view: file (0 direct, 1 private) va size file_offset flags(E eager, L lazy, D by data) name\n");
	for (const auto& r: vr) std::fprintf(f, "%d 0x%" PRIx64 " 0x%" PRIx64 " 0x%" PRIx64 " %s %s\n", r.kind, r.v->va, r.v->size, r.v->off, r.v->eager ? "E" : (r.v->lazy ? "L" : "D"), r.v->name.c_str());
	std::fflush(f);
	fsync(fileno(f));
	std::fclose(f);
	if (const int dfd = ::open(g_dump_dir.c_str(), O_RDONLY | O_DIRECTORY | O_CLOEXEC); dfd >= 0) {
		fsync(dfd);
		::close(dfd);
	}
	journal("timeout layout (exp 0412, tag tl412): %u dispatches of %s #%" PRIu64 " and %zu views written and synced in %.1f ms: %s\n", n_disp, kind, job, vr.size(), (timing_now() - t0) * 1000.0, name);
}
'''


def once(s, old, new):
    assert s.count(old) == 1, (s.count(old), old[:70])
    return s.replace(old, new)


def body_of(name, ns):
    inc = open(os.path.join(HERE, name), "rb").read()
    assert b"\r" not in inc
    body = inc[inc.index(b"namespace " + ns + b" {"):]
    assert body.rstrip().endswith(b"} // namespace " + ns) and b"#include" not in body
    return body


def main():
    assert len(sys.argv) == 3 and sys.argv[1] != sys.argv[2], __doc__
    s = open(sys.argv[1], "rb").read()
    assert b"\r" not in s and b"tag ph412" in s and b"tag tl412" not in s, "refused: not a unit with ph412, or already edited"
    DW_GLUE.decode("ascii")
    a = b"static void timeout_probe(const uint32_t* sub_ib, uint32_t sub_n, const char* kind, uint64_t n, const std::vector<uint32_t>* ran, const std::vector<GeProbeSlot>* gep = nullptr) {\n"
    s = once(s, a, b"// Experiment 0412 (tags tl412, dc412): dw0412.inc, the dispatches of a command buffer.\n" + body_of("dw0412.inc", b"dw412") + DW_GLUE + a
             + b"\ttl412_record(sub_ib, sub_n, kind, n); // exp 0412 (tag tl412): first, before the probe's own files\n")
    a = b"\tconst uint64_t n = g_submits.fetch_add(1);\n\t// Crash journal:"
    s = once(s, a, b"\tdc412_count(ib, num_dwords); // exp 0412 (tag dc412)\n" + a)
    open(sys.argv[2], "wb").write(s)
    print(f"bc5LleAgc.cpp {hashlib.md5(s).hexdigest()}")


if __name__ == "__main__":
    main()
