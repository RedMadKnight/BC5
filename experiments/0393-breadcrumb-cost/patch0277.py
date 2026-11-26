#!/usr/bin/env python3
# BC5 experiment 0277: breadcrumbs (BC5_DIRECT_BREADCRUMBS=1 or 2; off by default, D16). A one-file change of the shared
# tree's bc5LleAgc.cpp after exp 0272's integration (md5 a2a2c2df).
#
# With the switch, submit_now's rebuild (experiment 0038's, which copies an IB, inserts packets, grows the IB's own
# COND_EXEC counts and maps offsets both ways) also runs for every IB with a dispatch. Around each dispatch that goes to
# the GPU it inserts two writes to a slot of a host buffer the GPU sees:
#   - in front, a WRITE_DATA of an id (with a DISPATCH_DIRECT's group counts): written when the CP reaches the dispatch;
#   - behind, a RELEASE_MEM BOTTOM_OF_PIPE_TS of the same id: written when all the work before it is done.
# With 2, a DISPATCH_INDIRECT's three counts are also copied from its arguments in front of it (three COPY_DATA). Each of
# those makes the ME wait for a read, hence the second level. The compute-queue form names the arguments' address; the
# GFX form is an offset from the SET_BASE index 1 base, as the rebuild and the probe read them.
# No WR_CONFIRM: nothing on the GPU waits for these writes. The slots (2^20 of 32 bytes) are a sealed memfd, imported and
# mapped like the host's scratch (import_memfd / map_shared, ADR 0006), at the same address in the CPU and the GPU, and
# mapped again after a device reopen. A host table keeps each id's submission, title offset, opcode and program.
#
# At a fence timeout the probe journals, for the timed-out buffer (its breadcrumbs found in the IB by their address):
#   - how many the CP reached and how many were done;
#   - the first dispatch reached and not done (the one the ring is stuck behind, or an earlier one still running);
#   - the last reached and the first not reached;
#   - for every ring, the oldest breadcrumb reached and not done.
# Every 10 s the journal gets the count inserted, the rate, and a health check: of the 4,096 breadcrumbs that followed
# the previous line, how many were reached and done.
#
# Two fixes to the probe, which reads the rebuilt IB:
#   - its executed offsets are mapped forward to the rebuilt IB (they were the title's offsets, so its "ran" and
#     "DROPPED" marks were wrong whenever the rebuild ran, i.e. only with BC5_DIRECT_MEC_INDIRECT so far);
#   - the breadcrumbs are left out of its label writes.
# Breadcrumbs in a COND_EXEC range that the insertions would overflow are left out before any rebuilt compute dispatch is
# dropped. Without the switch the rebuild runs only as before, and the GPU stream is unchanged.
#
# Packet fields:
#   - WRITE_DATA DST_SEL 5 (bits 11:8) as the backend's indirect_check.cpp writes it;
#   - RELEASE_MEM event 0x28, EVENT_INDEX 5, DATA_SEL 1 (bits 31:29) as the backend's direct-selftest step 3 writes it
#     (experiment 0129: written on compute ring 0; TODO(verify) on the GFX ring, which the health line checks);
#   - COPY_DATA SRC_SEL 1 (memory, bits 3:0) and DST_SEL 5: TODO(verify) against Mesa src/amd/common/sid.h
#     (COPY_DATA_SRC_MEM) before the build.
# Each anchor must occur exactly once.
# usage: patch0277.py <shared bc5LleAgc.cpp, md5 a2a2c2df> <out .cpp> <out .diff>   (the input is only read)
import difflib, hashlib, sys

IN_MD5 = 'a2a2c2df5e7017eee69d6b12f374e099'

BLOCK = r'''// Experiment 0277 (diagnostic, BC5_DIRECT_BREADCRUMBS=1 or 2; off by default): breadcrumbs. Around every dispatch that
// goes to the GPU, submit_now's rebuild (experiment 0038's: it copies the IB, grows the IB's own COND_EXEC counts around
// what it inserts and maps offsets both ways) inserts two writes to a slot of a buffer the GPU and the host share: in
// front, a WRITE_DATA of an id (with a DISPATCH_DIRECT's group counts), written when the CP reaches the dispatch; behind
// it, a RELEASE_MEM BOTTOM_OF_PIPE_TS of the same id, written when the work before it is done. With 2, the three counts
// of a DISPATCH_INDIRECT are also copied from its arguments in front of it (COPY_DATA; each makes the ME wait for a read).
// A host table keeps each id's submission, title offset, opcode and program. At a fence timeout the probe names the
// buffer's first dispatch that was reached and not done, which the ring is stuck behind (experiments 0265, 0275, F336:
// hangs inside runs of up to hundreds of dispatches with no barrier between them, which the probe and the coredump could
// not tell apart). No WR_CONFIRM: nothing on the GPU waits for these writes. Fields: WRITE_DATA DST_SEL 5 (bits 11:8) as
// the backend's indirect_check.cpp writes it; RELEASE_MEM event 0x28, EVENT_INDEX 5, DATA_SEL 1 (bits 31:29) as the
// backend's direct-selftest step 3 writes it (experiment 0129: written on compute ring 0; TODO(verify) on the GFX ring,
// which the health line checks); COPY_DATA SRC_SEL 1 (memory, bits 3:0), DST_SEL 5: TODO(verify) against Mesa
// src/amd/common/sid.h (COPY_DATA_SRC_MEM).
struct BcEntry {
	uint64_t id      = 0;
	uint64_t sub     = 0;
	uint64_t pgm     = 0;
	uint32_t old_off = 0;
	uint32_t epoch   = 0; // the device it was submitted to (a reopen ends the jobs of the old one)
	uint8_t  op      = 0;
	uint8_t  counts  = 0; // 0 none, 1 from the packet, 2 copied from the arguments
	int8_t   ring    = 0;
	char     kind[5] = {};
};
struct BcPending {
	uint32_t old_off = 0, new_at = 0;  // the dispatch's offset in the IB; where its breadcrumb starts in the rebuilt one
	uint64_t pgm     = 0;
	uint8_t  op = 0, counts = 0;
	uint32_t wd_addr = 0, rm_addr = 0; // the address dwords of the WRITE_DATA and of the RELEASE_MEM (the id 2 after)
	uint32_t cd_dst[3] {0, 0, 0};      // the COPY_DATA destination dwords (0: none)
};
static constexpr uint32_t    kBcSlots = 1u << 20u;                                     // 32 bytes each: reached id, x, y, z, done id
static constexpr uint64_t    kBcBytes = static_cast<uint64_t>(kBcSlots) * 32u + 4096u; // and a page: the filter checks 8 bytes at an operand
static volatile uint32_t*    g_bc     = nullptr;
static int                   g_bc_fd  = -1;
static std::atomic<uint32_t> g_bc_id {0};    // the slot buffer's import on the current device (a reopen clears it)
static std::atomic<uint32_t> g_bc_epoch {0}; // counts the reopens
static std::vector<BcEntry>  g_bc_tab;
static std::mutex            g_bc_mutex; // the table
static std::atomic<uint64_t> g_bc_next {1}, g_bc_inserted {0};
static int breadcrumbs_level() {
	static const int v = [] {
		const char* e = BC5_DIAG_ENV("BC5_DIRECT_BREADCRUMBS");
		return e == nullptr || *e == 0 || *e == '0' ? 0 : (*e == '2' ? 2 : 1);
	}();
	return v;
}
// The slot buffer: a sealed memfd at the same address in the host and the GPU, imported and mapped as the scratch is
// (ADR 0006; the mapping sync leaves shared mappings alone), and again after a device reopen.
static bool bc_ready() {
	if (breadcrumbs_level() == 0 || !g_dev) return false;
	if (g_bc_id.load() != 0) return true;
	static std::mutex mu;
	static bool       dead = false;
	std::lock_guard   lk(mu);
	if (g_bc_id.load() != 0) return true;
	if (dead) return false;
	if (g_bc == nullptr) {
		g_bc_fd = memfd_create("bc5-breadcrumbs", MFD_CLOEXEC | MFD_ALLOW_SEALING);
		void* p = MAP_FAILED;
		if (g_bc_fd >= 0 && ftruncate(g_bc_fd, static_cast<off_t>(kBcBytes)) == 0 && fcntl(g_bc_fd, F_ADD_SEALS, F_SEAL_SHRINK) == 0) p = mmap(nullptr, kBcBytes, PROT_READ | PROT_WRITE, MAP_SHARED, g_bc_fd, 0);
		if (p == MAP_FAILED) {
			journal("breadcrumbs (exp 0277): no slot buffer; off\n");
			dead = true;
			return false;
		}
		std::lock_guard tl(g_bc_mutex);
		g_bc_tab.assign(kBcSlots, BcEntry {});
		g_bc = static_cast<volatile uint32_t*>(p);
	}
	const uint32_t id = g_dev->import_memfd(g_bc_fd, 0, kBcBytes);
	if (id == 0 || !g_dev->map_shared(id, 0, kBcBytes, reinterpret_cast<uint64_t>(g_bc))) {
		journal("breadcrumbs (exp 0277): the slot buffer could not be mapped at 0x%" PRIx64 "; off\n", reinterpret_cast<uint64_t>(g_bc));
		dead = true;
		return false;
	}
	g_bc_id = id;
	journal("breadcrumbs (exp 0277): level %d, %u slots at 0x%" PRIx64 " (device %u)\n", breadcrumbs_level(), kBcSlots, reinterpret_cast<uint64_t>(g_bc), g_bc_epoch.load());
	return true;
}
// The packets in front of a dispatch (the addresses and the id are left 0 for bc_commit).
static void bc_emit(std::vector<uint32_t>& out, std::vector<BcPending>& pend, uint32_t old_off, uint32_t op, const uint32_t* dims, uint64_t args, uint64_t pgm) {
	BcPending b;
	b.old_off = old_off;
	b.new_at  = static_cast<uint32_t>(out.size());
	b.op      = static_cast<uint8_t>(op);
	b.pgm     = pgm;
	if (op == 0x16 && args != 0 && breadcrumbs_level() >= 2) {
		for (uint32_t k = 0; k < 3; k++) { // COPY_DATA memory -> memory, 32 bits: the counts as the ME reads them
			const uint64_t s = args + 4u * k;
			out.insert(out.end(), {0xC0044000u, 0x00000501u, static_cast<uint32_t>(s), static_cast<uint32_t>(s >> 32u) & 0xffffu});
			b.cd_dst[k] = static_cast<uint32_t>(out.size());
			out.insert(out.end(), {0u, 0u});
		}
		b.counts = 2;
	}
	if (op == 0x15 && dims != nullptr) {
		out.insert(out.end(), {0xC0063700u, 0x00000500u}); // WRITE_DATA to memory: the id and the counts
		b.wd_addr = static_cast<uint32_t>(out.size());
		out.insert(out.end(), {0u, 0u, 0u, dims[0], dims[1], dims[2]});
		b.counts = 1;
	} else {
		out.insert(out.end(), {0xC0033700u, 0x00000500u}); // WRITE_DATA to memory: the id
		b.wd_addr = static_cast<uint32_t>(out.size());
		out.insert(out.end(), {0u, 0u, 0u});
	}
	pend.push_back(b);
}
// The packet behind it: RELEASE_MEM BOTTOM_OF_PIPE_TS, EVENT_INDEX 5, DATA_SEL 1 (32 bits of data), INT_SEL 0.
static void bc_emit_done(std::vector<uint32_t>& out, BcPending& b) {
	out.insert(out.end(), {0xC0064900u, 0x28u | (5u << 8u), 1u << 29u});
	b.rm_addr = static_cast<uint32_t>(out.size());
	out.insert(out.end(), {0u, 0u, 0u, 0u, 0u});
}
// Gives a rebuilt IB's breadcrumbs their ids and slots, fills in the addresses and records them in the table. Every 10 s:
// the count, the rate, and how many of the breadcrumbs that followed the previous line the GPU reached and finished.
static void bc_commit(std::vector<uint32_t>& out, const std::vector<BcPending>& pend, uint64_t sub, const char* kind, int ring) {
	const uint64_t  first = g_bc_next.fetch_add(pend.size());
	const uint64_t  base  = reinterpret_cast<uint64_t>(g_bc);
	const auto      put   = [&out](uint32_t at, uint64_t a) {
		out[at]     = static_cast<uint32_t>(a);
		out[at + 1] = static_cast<uint32_t>(a >> 32u) & 0xffffu;
	};
	std::lock_guard lk(g_bc_mutex);
	for (size_t i = 0; i < pend.size(); i++) {
		const BcPending& b    = pend[i];
		const uint64_t   id   = first + i;
		const uint32_t   slot = static_cast<uint32_t>(id % kBcSlots);
		const uint64_t   va   = base + static_cast<uint64_t>(slot) * 32u;
		put(b.wd_addr, va);
		out[b.wd_addr + 2] = static_cast<uint32_t>(id);
		for (uint32_t k = 0; k < 3; k++) {
			if (b.cd_dst[k] != 0) put(b.cd_dst[k], va + 4u + 4u * k);
		}
		if (b.rm_addr != 0) {
			put(b.rm_addr, va + 16u);
			out[b.rm_addr + 2] = static_cast<uint32_t>(id);
		}
		volatile uint32_t* s = g_bc + static_cast<size_t>(slot) * 8u;
		for (uint32_t k = 0; k < 8; k++) s[k] = 0; // not reached, not done: the GPU writes the ids
		BcEntry& e = g_bc_tab[slot];
		e.id       = id;
		e.sub      = sub;
		e.pgm      = b.pgm;
		e.old_off  = b.old_off;
		e.epoch    = g_bc_epoch.load();
		e.op       = b.op;
		e.counts   = b.counts;
		e.ring     = static_cast<int8_t>(ring);
		std::snprintf(e.kind, sizeof(e.kind), "%.4s", kind);
	}
	g_bc_inserted += pend.size();
	static double   last_s = -1.0;
	static uint64_t last_n = 0, sample = 0;
	const double    t = timing_now();
	if (last_s < 0.0 || t >= last_s + 10.0) {
		uint32_t n = 0, got = 0, fin = 0;
		for (uint64_t id = sample; sample != 0 && id < sample + 4096u && id < first; id++) {
			const uint32_t slot = static_cast<uint32_t>(id % kBcSlots);
			if (g_bc_tab[slot].id != id) continue;
			const volatile uint32_t* s = g_bc + static_cast<size_t>(slot) * 8u;
			n++;
			if (s[0] == static_cast<uint32_t>(id)) got++;
			if (s[4] == static_cast<uint32_t>(id)) fin++;
		}
		const uint64_t total = g_bc_inserted.load();
		journal("breadcrumbs (exp 0277): %" PRIu64 " inserted, %.0f a second; of %u that followed the previous line, %u reached and %u done\n", total,
		        last_s < 0.0 || t <= last_s ? 0.0 : static_cast<double>(total - last_n) / (t - last_s), n, got, fin);
		last_s = t;
		last_n = total;
		sample = first + pend.size();
	}
}
// Whether a packet is one of the breadcrumbs' writes (the timeout probe leaves them out of the title's label writes).
static bool bc_crumb(const uint32_t* w, uint32_t len) {
	if (g_bc == nullptr || (w[0] >> 30u) != 3) return false;
	const uint32_t op = (w[0] >> 8u) & 0xffu;
	uint32_t       lo = 0;
	if (op == 0x37 && len >= 5 && w[1] == 0x00000500u) lo = 2;
	else if (op == 0x49 && len >= 8 && w[1] == (0x28u | (5u << 8u)) && w[2] == (1u << 29u)) lo = 3;
	else return false;
	const uint64_t a = w[lo] | (static_cast<uint64_t>(w[lo + 1] & 0xffffu) << 32u), base = reinterpret_cast<uint64_t>(g_bc);
	return a >= base && a < base + static_cast<uint64_t>(kBcSlots) * 32u;
}
// The timeout probe's part. The breadcrumbs of the buffer that timed out (found in it by their address): how many the CP
// reached and how many are done, and the first dispatch reached and not done (a RELEASE_MEM BOTTOM_OF_PIPE_TS waits for
// all the work before it, so the ring is stuck behind that dispatch or an earlier one still running); then, from the
// table, every ring's oldest breadcrumb reached and not done on this device.
static void bc_report(const uint32_t* ib, uint32_t num, const std::vector<uint32_t>* ran) {
	if (g_bc == nullptr) return;
	struct Crumb {
		uint32_t at = 0, disp = ~0u, slot = 0, id = 0;
	};
	std::vector<Crumb> c;
	const uint64_t     base = reinterpret_cast<uint64_t>(g_bc);
	for (uint32_t q = 0; q < num;) {
		const uint32_t h   = ib[q];
		uint32_t       len = 1;
		if ((h >> 30u) == 3 || (h >> 30u) == 0) { const uint32_t k = (h >> 16u) & 0x3fffu; len = k == 0x3fffu ? 1 : k + 2; }
		if (q + len > num) break;
		const uint32_t op = (h >> 30u) == 3 ? (h >> 8u) & 0xffu : 0;
		if (op == 0x37 && bc_crumb(ib + q, len)) {
			Crumb k;
			k.at   = q;
			k.slot = static_cast<uint32_t>(((ib[q + 2] | (static_cast<uint64_t>(ib[q + 3] & 0xffffu) << 32u)) - base) / 32u);
			k.id   = ib[q + 4];
			c.push_back(k);
		} else if ((op == 0x15 || op == 0x16) && !c.empty() && c.back().disp == ~0u) {
			c.back().disp = q;
		}
		q += len;
	}
	std::lock_guard lk(g_bc_mutex);
	const auto      reached = [](const Crumb& k) { return g_bc[static_cast<size_t>(k.slot) * 8u] == k.id; };
	const auto      done    = [](const Crumb& k) { return g_bc[static_cast<size_t>(k.slot) * 8u + 4u] == k.id; };
	if (!c.empty()) {
		size_t n_reached = 0, n_done = 0, n_open = 0, last = SIZE_MAX, stuck = SIZE_MAX;
		for (size_t i = 0; i < c.size(); i++) {
			if (reached(c[i])) {
				n_reached++;
				last = i;
				if (!done(c[i])) {
					n_open++;
					if (stuck == SIZE_MAX) stuck = i;
				}
			}
			if (done(c[i])) n_done++;
		}
		const BcEntry& e0 = g_bc_tab[c[0].slot];
		const bool     k0 = static_cast<uint32_t>(e0.id) == c[0].id;
		journal("timeout probe: breadcrumbs (exp 0277) of #%" PRIu64 " %s: %zu in the buffer, %zu reached by the CP, %zu done, %zu reached and not done\n", k0 ? e0.sub : uint64_t {0},
		        k0 ? e0.kind : "?", c.size(), n_reached, n_done, n_open);
		const auto line = [&](size_t i, const char* what) {
			const Crumb&             k     = c[i];
			const volatile uint32_t* s     = g_bc + static_cast<size_t>(k.slot) * 8u;
			const BcEntry&           e     = g_bc_tab[k.slot];
			const bool               known = static_cast<uint32_t>(e.id) == k.id;
			char                     grid[64] = "";
			if (known && e.counts != 0) std::snprintf(grid, sizeof(grid), ", groups %u x %u x %u", s[1], s[2], s[3]);
			const bool dropped = ran != nullptr && k.disp != ~0u && !std::binary_search(ran->begin(), ran->end(), k.disp);
			journal("timeout probe:   %s: op %02x at %u (title offset %d), program 0x%" PRIx64 "%s; %s, %s%s\n", what, k.disp != ~0u ? (ib[k.disp] >> 8u) & 0xffu : 0u, k.disp,
			        known ? static_cast<int>(e.old_off) : -1, known ? e.pgm : uint64_t {0}, grid, reached(k) ? "reached" : "not reached", done(k) ? "done" : "not done",
			        dropped ? "; the dispatch DROPPED by the filter" : "");
		};
		if (stuck != SIZE_MAX) {
			for (size_t i = stuck >= 3 ? stuck - 3 : 0; i < stuck; i++) line(i, "before it");
			line(stuck, "the first reached and not done");
			for (size_t i = stuck + 1; i < c.size() && i <= stuck + 3; i++) line(i, "after it");
		} else if (n_reached != 0) {
			journal("timeout probe:   every dispatch the CP reached is done: the ring stopped outside them\n");
		}
		if (last != SIZE_MAX && (stuck == SIZE_MAX || last > stuck + 3)) line(last, "the last reached");
		const size_t next = last == SIZE_MAX ? 0 : last + 1;
		if (next < c.size() && (stuck == SIZE_MAX || next > stuck + 3)) line(next, "the first not reached after it");
	}
	struct Oldest {
		const BcEntry* e = nullptr;
		uint32_t       n = 0;
	};
	Oldest         r[16];
	const uint32_t epoch = g_bc_epoch.load();
	for (uint32_t slot = 0; slot < kBcSlots && !g_bc_tab.empty(); slot++) {
		const BcEntry& e = g_bc_tab[slot];
		if (e.id == 0 || e.epoch != epoch) continue;
		const volatile uint32_t* s = g_bc + static_cast<size_t>(slot) * 8u;
		if (s[0] != static_cast<uint32_t>(e.id) || s[4] == static_cast<uint32_t>(e.id)) continue;
		Oldest& o = r[(e.ring + 1) & 15];
		o.n++;
		if (o.e == nullptr || e.id < o.e->id) o.e = &e;
	}
	for (int i = 0; i < 16; i++) {
		if (r[i].e == nullptr) continue;
		journal("timeout probe:   ring %d: %u breadcrumbs reached and not done; the oldest: #%" PRIu64 " %s op %02x at title offset %u, program 0x%" PRIx64 "\n", i - 1, r[i].n, r[i].e->sub, r[i].e->kind,
		        static_cast<unsigned>(r[i].e->op), r[i].e->old_off, r[i].e->pgm);
	}
}
'''

EDITS = [
    # 1. The breadcrumbs, at file scope before the GE probe (experiment 0160).
    ('''// Experiment 0160 (diagnostic): BC5_DIRECT_GE_PROBE=<min>:<max> — in every prefixed graphics buffer whose
''',
     BLOCK + '''// Experiment 0160 (diagnostic): BC5_DIRECT_GE_PROBE=<min>:<max> — in every prefixed graphics buffer whose
'''),
    # 2. A device reopen: the slot buffer is mapped again on the new device; the old one's breadcrumbs are no longer open.
    ('''\t\t\tg_scratch_id = 0;
''',
     '''\t\t\tg_scratch_id = 0;
\t\t\tg_bc_id      = 0; // experiment 0277: the breadcrumbs' buffer is mapped again on the new device
\t\t\tg_bc_epoch++;
'''),
    # 3. The timeout probe: the breadcrumbs are not the title's label writes.
    ('''\t\t\t\t} else if ((op == 0x49 && len >= 8) || (op == 0x47 && len >= 6) || (op == 0x37 && len >= 5)) { // experiment 0260: the label writes
''',
     '''\t\t\t\t} else if (((op == 0x49 && len >= 8) || (op == 0x47 && len >= 6) || (op == 0x37 && len >= 5)) && !bc_crumb(sub_ib + q, len)) { // experiment 0260: the label writes (0277: not the breadcrumbs)
'''),
    # 4. The timeout probe's breadcrumb lines, after its count line (exp 0272).
    ('''\t\t        n_waits, n_kept, n_writes, n_disp, n_ind, max_groups, max_at);
''',
     '''\t\t        n_waits, n_kept, n_writes, n_disp, n_ind, max_groups, max_at);
\t\tbc_report(sub_ib, sub_n, ran); // experiment 0277
'''),
    # 5. submit_now's scan: the base at the IB's start, whether it dispatches, and each dispatch's program.
    ('''\tbool                  mec_expand_ib = false; // experiment 0038: rebuild the IB with GFX-form dispatches
''',
     '''\tbool                  mec_expand_ib = false; // experiment 0038: rebuild the IB with GFX-form dispatches
\tuint64_t              bc_base1_in   = 0;     // experiment 0277: the SET_BASE index 1 base at the IB's start
\tbool                  bc_any        = false; // experiment 0277: the IB dispatches (and BC5_DIRECT_BREADCRUMBS is set)
\tstd::vector<std::pair<uint32_t, uint64_t>> bc_pgms; // experiment 0277: each dispatch's offset and program
'''),
    ('''\t\t\tstd::memcpy(ud, carried.ud, sizeof(ud));
\t\t}
''',
     '''\t\t\tstd::memcpy(ud, carried.ud, sizeof(ud));
\t\t}
\t\tbc_base1_in = base1; // experiment 0277
'''),
    ('''\t\t\tif (type == 3 && (op == 0x15 || op == 0x16)) flat_aperture_fix(pgm, *maps_p); // experiment 0190
''',
     '''\t\t\tif (type == 3 && (op == 0x15 || op == 0x16)) flat_aperture_fix(pgm, *maps_p); // experiment 0190
\t\t\tif (type == 3 && (op == 0x15 || op == 0x16) && breadcrumbs_level() != 0) { // experiment 0277: the dispatches and their programs
\t\t\t\tbc_any = true;
\t\t\t\tbc_pgms.emplace_back(q, pgm);
\t\t\t}
'''),
    # 6. The rebuild: also for the breadcrumbs.
    ('''\tstd::vector<uint32_t> mec_new_to_old;
''',
     '''\tstd::vector<uint32_t> mec_new_to_old;
\tstd::vector<uint32_t> probe_old_to_new; // experiment 0277: the timeout probe reads the rebuilt IB, so its executed offsets go forward again
'''),
    ('''\tif (mec_expand_ib) {
\t\tstd::vector<uint32_t> old_to_new(num_dwords + 1, ~0u);
\t\tfor (int attempt = 0; attempt < 64; attempt++) {
\t\t\tmec_ib.clear();
\t\t\tstd::fill(old_to_new.begin(), old_to_new.end(), ~0u);
\t\t\tmec_ib.reserve(num_dwords + 5 * mec_positions.size());
''',
     '''\tconst bool bc_on = bc_any && bc_ready(); // experiment 0277: the rebuild also carries the breadcrumbs
\tif (mec_expand_ib || bc_on) {
\t\tstd::vector<uint32_t>  old_to_new(num_dwords + 1, ~0u);
\t\tstd::vector<uint32_t>  bc_skip; // experiment 0277: dispatches left without breadcrumbs (a COND_EXEC range would overflow)
\t\tstd::vector<BcPending> bc_new;  // experiment 0277: this attempt's breadcrumbs
\t\tfor (int attempt = 0; attempt < 64; attempt++) {
\t\t\tmec_ib.clear();
\t\t\tbc_new.clear();
\t\t\tstd::fill(old_to_new.begin(), old_to_new.end(), ~0u);
\t\t\tmec_ib.reserve(num_dwords + 5 * mec_positions.size() + (bc_on ? 32 * bc_pgms.size() : 0));
\t\t\tuint64_t bc_base1 = bc_base1_in;
\t\t\tsize_t   bc_pi    = 0; // experiment 0277: the next entry of bc_pgms
\t\t\tstd::vector<uint32_t> drop_sorted(opt.drop_offsets.begin(), opt.drop_offsets.end()); // experiment 0277: searched for every packet, now in every IB with a dispatch
\t\t\tstd::sort(drop_sorted.begin(), drop_sorted.end());
'''),
    ('''\t\t\t\tconst bool dropped = std::find(opt.drop_offsets.begin(), opt.drop_offsets.end(), q) != opt.drop_offsets.end();
\t\t\t\tconst bool is_mec  = (h >> 30u) == 3 && ((h >> 8u) & 0xffu) == 0x16 && len == 4 && !dropped;
\t\t\t\tif (is_mec) {
''',
     '''\t\t\t\tconst bool     dropped = std::binary_search(drop_sorted.begin(), drop_sorted.end(), q);
\t\t\t\tconst bool     is_mec  = mec_expand_ib && (h >> 30u) == 3 && ((h >> 8u) & 0xffu) == 0x16 && len == 4 && !dropped;
\t\t\t\tconst uint32_t pop     = (h >> 30u) == 3 ? (h >> 8u) & 0xffu : 0; // experiment 0277
\t\t\t\tif (pop == 0x11 && len >= 4 && (ib[q + 1] & 0xfu) == 1) bc_base1 = (ib[q + 2] & ~3u) | (static_cast<uint64_t>(ib[q + 3] & 0xffffu) << 32u);
\t\t\t\tconst bool crumb = bc_on && (pop == 0x15 || pop == 0x16) && !dropped && std::find(bc_skip.begin(), bc_skip.end(), q) == bc_skip.end();
\t\t\t\tif (crumb) { // experiment 0277: in front of the dispatch (and of what experiment 0038 puts in front of it)
\t\t\t\t\twhile (bc_pi < bc_pgms.size() && bc_pgms[bc_pi].first < q) bc_pi++;
\t\t\t\t\tconst uint64_t prog = bc_pi < bc_pgms.size() && bc_pgms[bc_pi].first == q ? bc_pgms[bc_pi].second : 0;
\t\t\t\t\tuint64_t       args = 0; // the compute-queue form names its arguments; the GFX form is an offset from SET_BASE index 1
\t\t\t\t\tif (pop == 0x16 && len >= 4) args = (ib[q + 1] & ~3ull) | (static_cast<uint64_t>(ib[q + 2] & 0xffffu) << 32u);
\t\t\t\t\telse if (pop == 0x16 && len >= 2 && bc_base1 != 0) args = bc_base1 + ib[q + 1];
\t\t\t\t\tbc_emit(mec_ib, bc_new, q, pop, pop == 0x15 && len >= 4 ? ib + q + 1 : nullptr, args, prog);
\t\t\t\t}
\t\t\t\tif (is_mec) {
'''),
    ('''\t\t\t\t\tmec_ib.insert(mec_ib.end(), ib + q, ib + q + len);
\t\t\t\t}
\t\t\t\tq += len;
''',
     '''\t\t\t\t\tmec_ib.insert(mec_ib.end(), ib + q, ib + q + len);
\t\t\t\t}
\t\t\t\tif (crumb) bc_emit_done(mec_ib, bc_new.back()); // experiment 0277: behind the dispatch
\t\t\t\tq += len;
'''),
    ('''\t\t\t\t\tconst uint32_t at    = old_to_new[q];
\t\t\t\t\tconst uint32_t count = old_to_new[e] - (at + 5);
''',
     '''\t\t\t\t\tconst uint32_t at    = old_to_new[q];
\t\t\t\t\tuint32_t       end_at = old_to_new[e];
\t\t\t\t\tif (!bc_new.empty()) { // experiment 0277: the breadcrumb in front of the packet at the range's end is not in the range
\t\t\t\t\t\tconst auto b = std::lower_bound(bc_new.begin(), bc_new.end(), e, [](const BcPending& x, uint32_t v) { return x.old_off < v; });
\t\t\t\t\t\tif (b != bc_new.end() && b->old_off == e) end_at = b->new_at;
\t\t\t\t\t}
\t\t\t\t\tconst uint32_t count = end_at - (at + 5);
'''),
    ('''\t\t\tif (overflow.empty()) break;
\t\t\tuint32_t excluded = 0;
\t\t\tfor (const uint32_t m: mec_positions) {
''',
     '''\t\t\tif (overflow.empty()) break;
\t\t\tuint32_t excluded = 0;
\t\t\tfor (const BcPending& b: bc_new) { // experiment 0277: the breadcrumbs inside such a range go first
\t\t\t\tbool inside = false;
\t\t\t\tfor (const auto& [lo, hi]: overflow) inside = inside || (b.old_off >= lo && b.old_off < hi);
\t\t\t\tif (inside) {
\t\t\t\t\tbc_skip.push_back(b.old_off);
\t\t\t\t\texcluded++;
\t\t\t\t}
\t\t\t}
\t\t\tif (excluded != 0) {
\t\t\t\tstatic std::atomic<uint64_t> n_bc_over {0};
\t\t\t\tif ((n_bc_over++ & 0x3fu) == 0) journal("breadcrumbs (exp 0277): %s %u dwords: %u left out of COND_EXEC range(s) that would overflow (%" PRIu64 " so far)\\n", kind, num_dwords, excluded, n_bc_over.load());
\t\t\t\tcontinue;
\t\t\t}
\t\t\tfor (const uint32_t m: mec_positions) {
'''),
    ('''\t\t{
\t\t\tmec_new_to_old.assign(mec_ib.size(), ~0u);
''',
     '''\t\tif (!bc_new.empty()) bc_commit(mec_ib, bc_new, n, kind, qring); // experiment 0277
\t\t{
\t\t\tmec_new_to_old.assign(mec_ib.size(), ~0u);
'''),
    ('''\t\t\tsub_ib = mec_ib.data();
\t\t\tsub_n  = static_cast<uint32_t>(mec_ib.size());
''',
     '''\t\t\tsub_ib = mec_ib.data();
\t\t\tsub_n  = static_cast<uint32_t>(mec_ib.size());
\t\t\tprobe_old_to_new.swap(old_to_new); // experiment 0277
'''),
    # 7. The probe gets the executed offsets of the rebuilt IB it reads.
    ('''\tauto r = g_dev->submit(std::span<const uint32_t>(sub_ib, sub_n), opt, 2'000'000'000ull, with_gds, qring);
\tmec_back(r.executed_offsets);
''',
     '''\tauto probe_ran = [&probe_old_to_new](const std::vector<uint32_t>& offsets) { // experiment 0277
\t\tif (probe_old_to_new.empty()) return offsets;
\t\tstd::vector<uint32_t> fwd;
\t\tfwd.reserve(offsets.size());
\t\tfor (const uint32_t o: offsets) {
\t\t\tif (o < probe_old_to_new.size() && probe_old_to_new[o] != ~0u) fwd.push_back(probe_old_to_new[o]);
\t\t}
\t\treturn fwd;
\t};
\tauto r = g_dev->submit(std::span<const uint32_t>(sub_ib, sub_n), opt, 2'000'000'000ull, with_gds, qring);
\tmec_back(r.executed_offsets);
'''),
    ('''\tif (r.timed_out) timeout_probe(sub_ib, sub_n, kind, g_submits.load(), &r.executed_offsets); // experiment 0160
''',
     '''\tif (r.timed_out) { // experiment 0160; experiment 0277: the executed offsets in the rebuilt IB
\t\tconst std::vector<uint32_t> ran_new = probe_ran(r.executed_offsets);
\t\ttimeout_probe(sub_ib, sub_n, kind, g_submits.load(), &ran_new);
\t}
'''),
    ('''it.job.ran_copy = r.executed_offsets; } // experiment 0160
''',
     '''it.job.ran_copy = probe_ran(r.executed_offsets); } // experiment 0160 (0277: in the rebuilt IB)
'''),
]


def main():
    src_path, out_path, diff_path = sys.argv[1:4]
    raw = open(src_path, 'rb').read()
    md5 = hashlib.md5(raw).hexdigest()
    if md5 != IN_MD5:
        sys.exit(f"{src_path}: md5 {md5}, expected {IN_MD5} (the shared tree after exp 0272's integration)")
    text = raw.decode('utf-8')
    for k, (old, new) in enumerate(EDITS, 1):
        n = text.count(old)
        if n != 1:
            sys.exit(f'edit {k}: anchor found {n} times')
        text = text.replace(old, new)
    out = text.encode('utf-8')
    open(out_path, 'wb').write(out)
    diff = difflib.unified_diff(raw.decode('utf-8').splitlines(keepends=True), text.splitlines(keepends=True),
                                'a/src/libs/bc5LleAgc.cpp', 'b/src/libs/bc5LleAgc.cpp', n=3)
    open(diff_path, 'w', encoding='utf-8', newline='\n').write(''.join(diff))
    print(f'{out_path}: md5 {hashlib.md5(out).hexdigest()}, {len(EDITS)} edits')


if __name__ == '__main__':
    main()
