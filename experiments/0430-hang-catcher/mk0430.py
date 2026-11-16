#!/usr/bin/env python3
# BC5 experiment 0430 (tag dj430): the hang catchers, as anchored edits of the shared tree's unit.
#   python3 -I mk0430.py <dir>     edits <dir>/src/libs/bc5LleAgc.cpp in place
# The base is patch a8717e53's unit (md5 0cda79b5, the same file as exp 0428's swap). Every anchor must match exactly
# once, or nothing is written. Three switches, normal build only (BC5_DIAG_ENV, nullptr in the lean build):
#   BC5_0430_DJ=1        (b) per-ring in-memory dispatch journal, written to files at a stall, a timeout
#   BC5_0430_ARGS=1      (c) indirect dispatch arguments read at submit: garbage triples journaled ("args0430:")
#   BC5_0430_SNAP=1      (e) with each dump, 4 KiB at the user-data pointers and argument pages of the stalled submission
#   BC5_0430_WAVES_MS=n  (a) at a completion wait of n ms (>= 500), one `umr -O halt_waves -wa none` (the exact
#                            NOPASSWD line on the box) into the capture directory, at most 2 per run; dedicated runs only
#                            (F229: a halt at a stall that would have recovered is followed by a reset)
import hashlib
import sys

BASE_MD5 = "0cda79b5"
U = "src/libs/bc5LleAgc.cpp"

NS = r'''
// Experiment 0430 (tag dj430): catchers for the second title's GPU hangs, normal build only (BC5_DIAG_ENV). Diagnostics:
// nothing here drops, retries or recovers anything.
// (b) BC5_0430_DJ=1: per hardware ring (slot 0 the GFX ring, 1..kComputeRings the compute rings by libdrm index), the last
//     kN dispatches the host submitted: submission, kind, offset, op, program, COMPUTE_USER_DATA_0..15, an indirect
//     dispatch's argument address and the triple read at submit. Written to <capture dir>/dj0430-<k>.txt at a stall
//     (the watchdog below) and at a host timeout; at most 8 files per run.
// (c) BC5_0430_ARGS=1: an indirect dispatch whose triple at submit is over the host check's limit (65536 * 64 per axis or
//     as a product) is journaled ("args0430: ..."), the first 256 and then every 4096th, with ring, program and address.
//     Garbage at submit: written before the submit. Clean here and garbage in the timeout probe: a GPU writer in flight.
// (a) BC5_0430_WAVES_MS=<ms>: when a completion queue has waited that long for one job (from its submission), one
//     `sudo -n /usr/bin/umr -O halt_waves -wa none` (every wave of the GPU, no ring named; the exact line the box's sudoers
//     allows) into <capture dir>/waves0430-<k>.txt, synced; at most 2 per run, the journal first. Only in dedicated runs:
//     F229 and exp 0370 K2 (a halt at a 0.6-s stall that would have recovered was followed by a ring reset).
#include <sys/uio.h> // exp 0430 (d): process_vm_readv
namespace dj430 {
struct Rec {
	uint64_t n    = 0;
	uint64_t pgm  = 0;
	uint64_t args = 0;
	uint32_t ud[16] {};
	uint32_t v[3] {};
	uint32_t q     = 0;
	uint8_t  op    = 0;
	uint8_t  flags = 0; // 1 indirect, 2 garbage at submit, 4 arguments not readable
	char     kind[8] {};
};
constexpr uint32_t kSlots = bc5::direct::kComputeRings + 1;
constexpr uint32_t kN     = 4096;
inline bool        on() {
	static const bool v = BC5_DIAG_ENV("BC5_0430_DJ") != nullptr;
	return v;
}
inline bool args_on() {
	static const bool v = BC5_DIAG_ENV("BC5_0430_ARGS") != nullptr;
	return v;
}
inline uint64_t waves_ns() {
	static const uint64_t v = [] {
		const char* e = BC5_DIAG_ENV("BC5_0430_WAVES_MS");
		if (e == nullptr) return 0ull;
		const unsigned long long ms = std::strtoull(e, nullptr, 10);
		return ms < 500 ? 0ull : ms * 1'000'000ull;
	}();
	return v;
}
struct Ring {
	std::mutex       m;
	std::vector<Rec> r;
	uint64_t         total = 0;
};
inline Ring* rings() {
	static Ring a[kSlots];
	return a;
}
inline uint32_t slot(int qring) {
	return qring == bc5::direct::kGfxRing || qring < 0 ? 0u : 1u + static_cast<uint32_t>(qring) % bc5::direct::kComputeRings;
}
inline void commit(int qring, uint64_t n, std::vector<Rec>& recs) {
	if (recs.empty()) return;
	Ring&       g = rings()[slot(qring)];
	std::lock_guard lk(g.m);
	if (g.r.size() != kN) g.r.assign(kN, Rec {});
	for (Rec& x: recs) {
		x.n              = n;
		g.r[g.total % kN] = x;
		g.total++;
	}
	recs.clear();
}
inline bool snap_on();
inline void snap(int k, const std::vector<Rec>& last);
inline std::string out_dir() {
	return g_dump_dir.empty() ? std::string(std::getenv("HOME") ? std::getenv("HOME") : ".") + "/bc5-work" : g_dump_dir;
}
inline void dump(const char* why, uint64_t n, const char* kind) {
	if (!on()) return;
	static std::atomic<int> dumps {0};
	const int               k = dumps++;
	if (k >= 8) return;
	char name[640];
	std::snprintf(name, sizeof(name), "%s/dj0430-%d.txt", out_dir().c_str(), k);
	FILE* f = std::fopen(name, "w");
	if (f == nullptr) return;
	std::fprintf(f, "dj430 dump %d: %s, submission #%" PRIu64 " %s, t %.3f s; per ring the last %u dispatches the host submitted, oldest first\n", k, why, n, kind != nullptr ? kind : "-", timing_now(), kN);
	std::fprintf(f, "columns: #submission kind offset op pgm args x y z flags(1 indirect 2 garbage 4 unreadable) ud0..ud15\n");
	std::vector<Rec> last; // (e): the dispatches of submission n
	for (uint32_t s = 0; s < kSlots; s++) {
		Ring&       g = rings()[s];
		std::lock_guard lk(g.m);
		std::fprintf(f, "ring %s%u: %" PRIu64 " dispatches in all\n", s == 0 ? "gfx" : "compute ", s == 0 ? 0u : s - 1, g.total);
		if (g.r.size() != kN) continue;
		for (uint64_t i = g.total > kN ? g.total - kN : 0; i < g.total; i++) {
			const Rec& x = g.r[i % kN];
			if (x.n == n) last.push_back(x); // (e): the stalled submission's own dispatches
			std::fprintf(f, "#%" PRIu64 " %s %u %02x 0x%" PRIx64 " 0x%" PRIx64 " %u %u %u %u", x.n, x.kind, x.q, x.op, x.pgm, x.args, x.v[0], x.v[1], x.v[2], x.flags);
			for (uint32_t u = 0; u < 16; u++) std::fprintf(f, " %08x", x.ud[u]);
			std::fputc('\n', f);
		}
	}
	std::fflush(f);
	fsync(fileno(f));
	std::fclose(f);
	journal("dj430: %s: the dispatch journal written to %s\n", why, name);
	if (snap_on()) snap(k, last);
}
// (a) the wave reader is a helper shell spawned when the watchdog starts, while the GPU is healthy: a process forked at the
// stall blocks in its exec, because closing the close-on-exec DRM fd runs amdgpu's flush, which waits for the hung jobs
// (h430R2, 20:25:48.9: the child "bc5-dj430" in D state in drm_sched_entity_flush; no umr ran). At the stall one line goes
// down the pipe and the helper, which holds no DRM fd, runs the halt.
inline FILE*& helper() {
	static FILE* h = nullptr;
	return h;
}
inline void helper_start() {
	if (waves_ns() == 0 || helper() != nullptr) return;
	const std::string dir = out_dir();
	char              cmd[1400];
	std::snprintf(cmd, sizeof(cmd),
	              "while read k; do t0=$(date +%%s.%%N); "
	              "if [ -e /run/.containerenv ]; then distrobox-host-exec sudo -n /usr/bin/umr -O halt_waves -wa none; else sudo -n /usr/bin/umr -O halt_waves -wa none; fi > %s/waves0430-$k.txt 2>&1; "
	              "rc=$?; sync; echo \"waves $k rc $rc from $t0 to $(date +%%s.%%N)\" >> %s/waves0430.log; sync; done",
	              dir.c_str(), dir.c_str());
	helper() = popen(cmd, "w");
	journal("dj430: wave helper %s (umr -O halt_waves -wa none at a stall of %.0f ms)\n", helper() != nullptr ? "started" : "NOT started", static_cast<double>(waves_ns()) / 1e6);
}
inline void waves(int cq, uint64_t n, const char* kind, uint64_t waited_ns) {
	static std::atomic<int> runs {0};
	const int               k = runs++;
	if (k >= 2 || helper() == nullptr) return;
	std::fprintf(helper(), "%d\n", k);
	std::fflush(helper());
	if (FILE* f = journal_min_file(true); f != nullptr) {
		std::fprintf(f, "dj430: completion queue %d waited %.0f ms for #%" PRIu64 " %s: wave read %d asked of the helper at t %.3f s\n", cq, static_cast<double>(waited_ns) / 1e6, n, kind, k, timing_now());
		std::fflush(f);
		fsync(fileno(f));
	}
}
// (d)/(e) BC5_0430_SNAP=1: with each dump, the memory behind the stalled submission's own dispatches (h430S1: the ring's
// newest 16 were later submissions). For every dispatch of submission n (any ring), 4 KiB at each 64-bit user-data
// pointer (ud k, k+1) and at an indirect dispatch's argument address, read with process_vm_readv (an unmapped address
// gives EFAULT, not a crash); each address once. snap0430-<k>.txt is the index (which dispatch named which address),
// snap0430-<k>.bin the bytes: per address a u64 address, a u32 count of bytes read (0: unreadable), then those bytes.
// The memory as it is at the dump, not at the dispatch's run (R13).
inline bool snap_on() {
	static const bool v = BC5_DIAG_ENV("BC5_0430_SNAP") != nullptr;
	return v;
}
inline void snap(int k, const std::vector<Rec>& mine) {
	char name[640], bname[640];
	std::snprintf(name, sizeof(name), "%s/snap0430-%d.txt", out_dir().c_str(), k);
	std::snprintf(bname, sizeof(bname), "%s/snap0430-%d.bin", out_dir().c_str(), k);
	FILE* f = std::fopen(name, "w");
	FILE* b = std::fopen(bname, "wb");
	if (f == nullptr || b == nullptr) {
		if (f != nullptr) std::fclose(f);
		if (b != nullptr) std::fclose(b);
		return;
	}
	std::fprintf(f, "snap0430 %d at t %.3f s: %zu dispatches of the stalled submission; 4 KiB at each user-data pointer and argument address (memory now, not at the run); bytes in snap0430-%d.bin\n", k, timing_now(), mine.size(), k);
	std::set<uint64_t>  seen;
	std::vector<uint8_t> buf(4096);
	uint64_t            bytes = 0;
	auto one = [&](const Rec& x, const char* what, uint64_t a) {
		if (a < 0x100000000ull || a >= 0x10000000000ull) return;
		std::fprintf(f, "#%" PRIu64 " %s %u op %02x pgm 0x%" PRIx64 " %s 0x%" PRIx64 "%s\n", x.n, x.kind, x.q, x.op, x.pgm, what, a, seen.count(a) != 0 ? " (above)" : "");
		if (!seen.insert(a).second || seen.size() > 16384) return;
		struct iovec  l {buf.data(), buf.size()}, r {reinterpret_cast<void*>(a), buf.size()};
		ssize_t       got = process_vm_readv(getpid(), &l, 1, &r, 1, 0);
		if (got < 0) got = 0;
		const uint32_t g32 = static_cast<uint32_t>(got);
		std::fwrite(&a, 8, 1, b);
		std::fwrite(&g32, 4, 1, b);
		if (got > 0) std::fwrite(buf.data(), 1, static_cast<size_t>(got), b);
		bytes += static_cast<uint64_t>(got);
	};
	for (const Rec& x: mine) {
		char what[8];
		for (uint32_t u = 0; u + 1 < 16; u++) {
			std::snprintf(what, sizeof(what), "ud%u", u);
			one(x, what, x.ud[u] | (static_cast<uint64_t>(x.ud[u + 1] & 0xffffu) << 32u));
		}
		if (x.args != 0) one(x, "args", x.args & ~0xfffull);
	}
	std::fprintf(f, "%zu addresses, %" PRIu64 " bytes read\n", seen.size(), bytes);
	std::fflush(f);
	std::fflush(b);
	fsync(fileno(f));
	fsync(fileno(b));
	std::fclose(f);
	std::fclose(b);
}
struct Wait {
	std::atomic<uint64_t>    since {0};
	std::atomic<uint64_t>    n {0};
	std::atomic<const char*> kind {nullptr};
};
inline Wait* waits() {
	static Wait w[8];
	return w;
}
inline void watchdog_start() {
	if (!on() && waves_ns() == 0) return;
	static std::once_flag once;
	std::call_once(once, [] {
		std::thread([] {
			pthread_setname_np(pthread_self(), "bc5-dj430");
			helper_start(); // (a): before any stall
			const uint64_t limit = waves_ns() != 0 ? waves_ns() : 900'000'000ull;
			uint64_t       done[8] {};
			for (;;) {
				std::this_thread::sleep_for(std::chrono::milliseconds(10));
				for (int c = 0; c < 8; c++) {
					const uint64_t t0 = waits()[c].since.load();
					if (t0 == 0 || t0 == done[c]) continue;
					const uint64_t now = SoftCp::now_ns();
					if (now - t0 < limit) continue;
					done[c]               = t0;
					const uint64_t    n   = waits()[c].n.load();
					const char*       kd  = waits()[c].kind.load();
					if (waves_ns() != 0) waves(c, n, kd != nullptr ? kd : "-", now - t0); // the halt first: the kernel resets the ring soon
					char why[96];
					std::snprintf(why, sizeof(why), "completion queue %d waited %.0f ms", c, static_cast<double>(now - t0) / 1e6);
					dump(why, n, kd);
				}
			}
		}).detach();
	});
}
inline void wait_begin(int cq, uint64_t since, uint64_t n, const char* kind) {
	if (cq < 0 || cq >= 8) return;
	watchdog_start();
	waits()[cq].n    = n;
	waits()[cq].kind = kind;
	waits()[cq].since = since;
}
inline void wait_end(int cq) {
	if (cq >= 0 && cq < 8) waits()[cq].since = 0;
}
} // namespace dj430

'''

EDITS = [
    # the namespace, after exp 0058's watchdog (g_fence_wait_since, journal_min_file and the dump directory are known here)
    ("// Experiment 0412 (tag fr412): BC5_FAULT_RECORD. A GPU fault is a bug to remove at its source: write what is needed to\n",
     NS + "// Experiment 0412 (tag fr412): BC5_FAULT_RECORD. A GPU fault is a bug to remove at its source: write what is needed to\n"),
    # the completion wait: begin and end, per completion queue
    ("\t\t\t\tg_fence_wait_since = j.queued_ns != 0 ? j.queued_ns : SoftCp::now_ns(); // from the job's submission: the kernel resets ~2 s after it hangs\n",
     "\t\t\t\tg_fence_wait_since = j.queued_ns != 0 ? j.queued_ns : SoftCp::now_ns(); // from the job's submission: the kernel resets ~2 s after it hangs\n"
     "\t\t\t\tif (dj430::on() || dj430::waves_ns() != 0) dj430::wait_begin(index, j.queued_ns != 0 ? j.queued_ns : SoftCp::now_ns(), j.n, j.kind); // exp 0430 (tag dj430)\n"),
    ("\t\t\t\tg_fence_wait_since = 0;\n\t\t\t} else {\n\t\t\t\tr.rc = -125; // -ECANCELED: the device it was queued on is gone\n",
     "\t\t\t\tg_fence_wait_since = 0;\n\t\t\t\tdj430::wait_end(index); // exp 0430 (tag dj430)\n\t\t\t} else {\n\t\t\t\tr.rc = -125; // -ECANCELED: the device it was queued on is gone\n"),
    # the host timeouts: async and sync
    ("\t\t\tif (r.timed_out && !j.ib_copy.empty()) timeout_probe(j.ib_copy.data(), static_cast<uint32_t>(j.ib_copy.size()), j.kind, j.n, &j.ran_copy, &j.ge_probe); // experiment 0160\n",
     "\t\t\tif (r.timed_out && !j.ib_copy.empty()) timeout_probe(j.ib_copy.data(), static_cast<uint32_t>(j.ib_copy.size()), j.kind, j.n, &j.ran_copy, &j.ge_probe); // experiment 0160\n"
     "\t\t\tif (r.timed_out) dj430::dump(\"a host timeout\", j.n, j.kind); // exp 0430 (tag dj430)\n"),
    ("\tif (r.timed_out) timeout_probe(fl_ib.empty() ? sub_ib : ib, fl_ib.empty() ? sub_n : num_dwords, kind, g_submits.load(), &r.executed_offsets); // experiment 0160",
     "\tif (r.timed_out) dj430::dump(\"a host timeout (sync)\", g_submits.load(), kind); // exp 0430 (tag dj430)\n"
     "\tif (r.timed_out) timeout_probe(fl_ib.empty() ? sub_ib : ib, fl_ib.empty() ? sub_n : num_dwords, kind, g_submits.load(), &r.executed_offsets); // experiment 0160"),
    # the scan's records: a buffer of this submission
    ("\tconst bool             catch_on = table_catcher_on(); // experiment 0401 series e: the table catcher's slots of this buffer\n",
     "\tstatic thread_local std::vector<dj430::Rec> dj_recs; // exp 0430 (tag dj430): this buffer's dispatches, committed with its number\n"
     "\tdj_recs.clear();\n"
     "\tconst bool             catch_on = table_catcher_on(); // experiment 0401 series e: the table catcher's slots of this buffer\n"),
    ("\t\t\tif (type == 3 && (op == 0x15 || op == 0x16)) flat_aperture_fix(pgm, *maps_p); // experiment 0190\n",
     "\t\t\tif (type == 3 && (op == 0x15 || op == 0x16)) flat_aperture_fix(pgm, *maps_p); // experiment 0190\n"
     "\t\t\tif (type == 3 && (op == 0x15 || op == 0x16) && (dj430::on() || dj430::args_on())) { // exp 0430 (tag dj430): (b) and (c)\n"
     "\t\t\t\tdj430::Rec x;\n"
     "\t\t\t\tx.pgm = pgm;\n"
     "\t\t\t\tx.q   = q;\n"
     "\t\t\t\tx.op  = static_cast<uint8_t>(op);\n"
     "\t\t\t\tstd::memcpy(x.ud, ud, sizeof(x.ud));\n"
     "\t\t\t\tstd::snprintf(x.kind, sizeof(x.kind), \"%s\", kind);\n"
     "\t\t\t\tif (op == 0x16 && len >= 2) {\n"
     "\t\t\t\t\tconst bool mec = compute_ib && len == 4;\n"
     "\t\t\t\t\tx.flags |= 1u;\n"
     "\t\t\t\t\tx.args = mec ? ((ib[q + 1] & ~3ull) | (static_cast<uint64_t>(ib[q + 2] & 0xffffu) << 32u)) : (base1 != 0 ? base1 + ib[q + 1] : 0);\n"
     "\t\t\t\t\tif (x.args != 0 && covered_sorted(*maps_p, x.args, 12)) {\n"
     "\t\t\t\t\t\tconst auto* t = reinterpret_cast<const volatile uint32_t*>(x.args);\n"
     "\t\t\t\t\t\tx.v[0] = t[0];\n"
     "\t\t\t\t\t\tx.v[1] = t[1];\n"
     "\t\t\t\t\t\tx.v[2] = t[2];\n"
     "\t\t\t\t\t\tconstexpr uint64_t lim = 65536ull * 64ull;\n"
     "\t\t\t\t\t\tif (x.v[0] > lim || x.v[1] > lim || x.v[2] > lim || static_cast<uint64_t>(x.v[0]) * x.v[1] > lim || static_cast<uint64_t>(x.v[0]) * x.v[1] * x.v[2] > lim) x.flags |= 2u;\n"
     "\t\t\t\t\t} else {\n"
     "\t\t\t\t\t\tx.flags |= 4u;\n"
     "\t\t\t\t\t}\n"
     "\t\t\t\t\tif ((x.flags & 2u) != 0 && dj430::args_on()) {\n"
     "\t\t\t\t\t\tstatic std::atomic<uint64_t> n_garbage {0};\n"
     "\t\t\t\t\t\tconst uint64_t               g = n_garbage++;\n"
     "\t\t\t\t\t\tif (g < 256 || (g & 0xfffu) == 0)\n"
     "\t\t\t\t\t\t\tjournal(\"args0430: %s ring %d, about #%\" PRIu64 \", op 16 at %u (%s form): pgm 0x%\" PRIx64 \" args 0x%\" PRIx64 \" -> %u %u %u (%08x %08x %08x) garbage at submit (%\" PRIu64 \" so far)\\n\", kind, qring,\n"
     "\t\t\t\t\t\t\t        g_submits.load(), q, mec ? \"compute\" : \"graphics\", pgm, x.args, x.v[0], x.v[1], x.v[2], x.v[0], x.v[1], x.v[2], g + 1);\n"
     "\t\t\t\t\t}\n"
     "\t\t\t\t}\n"
     "\t\t\t\tif (dj430::on()) dj_recs.push_back(x);\n"
     "\t\t\t}\n"),
    # the commit, with the submission's number
    ("\tconst uint64_t n = g_submits.fetch_add(1);\n\t// Crash journal: a hang takes the machine down before any buffered log reaches the disk, so\n",
     "\tconst uint64_t n = g_submits.fetch_add(1);\n\tif (dj430::on()) dj430::commit(qring, n, dj_recs); // exp 0430 (tag dj430)\n"
     "\t// Crash journal: a hang takes the machine down before any buffered log reaches the disk, so\n"),
]


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: mk0430.py <dir>")
        return 2
    path = f"{sys.argv[1]}/{U}"
    with open(path, "rb") as fh:
        data = fh.read()
    md5 = hashlib.md5(data).hexdigest()[:8]
    if md5 != BASE_MD5:
        print(f"mk0430: {path} is {md5}, not the base {BASE_MD5}")
        return 1
    text = data.decode("utf-8", "surrogateescape")
    for i, (old, new) in enumerate(EDITS):
        c = text.count(old)
        if c != 1:
            print(f"mk0430: anchor {i} matches {c} times")
            return 1
        text = text.replace(old, new)
    out = text.encode("utf-8", "surrogateescape")
    with open(path, "wb") as fh:
        fh.write(out)
    print(f"mk0430: {len(EDITS)} edits, {BASE_MD5} -> {hashlib.md5(out).hexdigest()[:8]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
