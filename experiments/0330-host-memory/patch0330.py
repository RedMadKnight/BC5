#!/usr/bin/env python3
# BC5 experiment 0330: three diagnostic switches for the host's memory, all off by default (BC5_DIAG_ENV, so the lean
# build never has them). A one-file change of the shared tree's bc5LleAgc.cpp (md5 5bccbb80, the file in main's patch
# 0001 since exp 0278's integration).
#   1. BC5_DIRECT_JOURNAL_DONTNEED=1: the journal's written pages leave the page cache once they are on the disk. Every
#      8 MiB written, the writeback of the new part is started (sync_file_range SYNC_FILE_RANGE_WRITE, not waited for)
#      and the part started the time before is dropped (posix_fadvise POSIX_FADV_DONTNEED). Exp 0288 Q4: the normal
#      build's journal went through the page cache and the kernel reclaimed the title's own pages for it.
#   2. BC5_DIRECT_BREAKDOWN_AT=<s>: the per-name import table of direct memory once, at that journal time;
#      BC5_DIRECT_BREAKDOWN_NODATA=1 leaves out its SEEK_DATA walk (which held the game thread for minutes in exp 0288
#      run M1; for an eager heap "with data" equals "imported" anyway). Each row now also names the heap's address span.
#   3. BC5_DIRECT_ZEROSCAN_AT=<s>: once, at that journal time, a background thread (nice 19) reads every imported chunk
#      of direct memory (pread from the memfd) and counts per heap name the 2 MiB chunks and the 4 KiB pages that are
#      all zero. Pinning allocates the pages, so what the GPU alone touched cannot be read from the pinned size; a page
#      still all zero after minutes of play was most likely written by neither the CPU nor the GPU, so the counts bound
#      what a narrower import could leave out. Read only.
# Each anchor must occur exactly once.
# usage: patch0330.py <shared bc5LleAgc.cpp, md5 5bccbb80> <out .cpp> <out .diff>   (the input is only read)
import difflib, hashlib, sys

IN_MD5 = '5bccbb808c397f3180330425917b04c6'

DROP = r'''// Experiment 0330 (BC5_DIRECT_JOURNAL_DONTNEED=1): the journal's written pages leave the page cache once they are on
// the disk. The normal build's journal (~200 MB in ten minutes of the second title) went through the page cache of a box
// with ~0.5 GB available, and the kernel reclaimed the title's own pages for it (exp 0288 Q4). Every 8 MiB written, the
// writeback of the new part is started (not waited for) and the part started the time before is dropped.
static void journal_drop(int fd) {
	static const bool on = BC5_DIAG_ENV("BC5_DIRECT_JOURNAL_DONTNEED") != nullptr;
	if (!on || fd < 0) return;
	static std::mutex m;
	static off_t      started = 0, dropped = 0;
	std::lock_guard   lk(m);
	const off_t       end = lseek(fd, 0, SEEK_END); // the file is open for appending: the offset does not move the writes
	if (end < 0 || end - started < (8 << 20)) return;
	if (started > dropped) {
		posix_fadvise(fd, dropped, started - dropped, POSIX_FADV_DONTNEED);
		dropped = started;
	}
	sync_file_range(fd, started, end - started, SYNC_FILE_RANGE_WRITE);
	started = end;
}
'''

ZEROSCAN = r'''// Experiment 0330 (BC5_DIRECT_ZEROSCAN_AT=<s>): once, a background thread (nice 19) reads every imported chunk of direct
// memory and counts, per heap name, the 2 MiB chunks and the 4 KiB pages that are all zero. Pinning allocates the pages,
// so what the GPU alone touched cannot be read from the pinned size (exp 0288); a page still all zero after minutes of
// play was most likely written by neither the CPU nor the GPU, so the counts bound what a narrower import could leave
// out. A chunk aliased by several views counts once, under the first view by address. Read only.
static void direct_zeroscan(const DState& S) {
	const int fd = dstate_fd(S);
	if (fd < 0) return;
	const auto            views_p = direct_views(S);
	const std::vector<DBo> bos    = S.bos;
	std::thread([fd, views_p, bos] {
		setpriority(PRIO_PROCESS, static_cast<id_t>(gettid()), 19);
		struct Row {
			uint64_t imported = 0, zchunks = 0, zpages = 0, lo = ~0ull, hi = 0;
		};
		std::map<std::string, Row> rows;
		Row                        total;
		std::set<uint64_t>         seen;
		std::vector<uint8_t>       buf(kDChunk);
		const double               t0 = timing_now();
		for (const auto& v: views_p->v) {
			Row&           r    = rows[v.size >= (1ull << 20u) ? v.name : std::string("(views under 1 MiB)")];
			const uint64_t vend = v.off + v.size;
			r.lo                = std::min(r.lo, v.va);
			r.hi                = std::max(r.hi, v.va + v.size);
			auto it = std::upper_bound(bos.begin(), bos.end(), v.off, [](uint64_t o, const DBo& b) { return o < b.off; });
			if (it != bos.begin()) --it;
			for (; it != bos.end() && it->off < vend; ++it) {
				for (uint64_t c = std::max(it->off, v.off & ~(kDChunk - 1)); c < std::min(it->off + it->size, vend); c += kDChunk) {
					if (!seen.insert(c).second) continue;
					if (pread(fd, buf.data(), kDChunk, static_cast<off_t>(c)) != static_cast<ssize_t>(kDChunk)) continue;
					uint64_t zp = 0;
					for (uint64_t p = 0; p < kDChunk; p += 4096) {
						const auto* w = reinterpret_cast<const uint64_t*>(buf.data() + p);
						bool        z = true;
						for (uint32_t k = 0; k < 512 && z; k++) z = w[k] == 0;
						if (z) zp++;
					}
					for (Row* x: {&r, &total}) {
						x->imported += kDChunk;
						x->zpages += zp * 4096;
						if (zp == kDChunk / 4096) x->zchunks += kDChunk;
					}
				}
			}
		}
		const double mib = 1048576.0;
		journal("zero scan (exp 0330): direct memory, %.1f MiB of imported chunks read in %.1f s: all-zero 2 MiB chunks and 4 KiB pages by name\n", static_cast<double>(total.imported) / mib,
		        timing_now() - t0);
		for (const auto& [name, x]: rows) {
			if (x.imported == 0) continue;
			journal("  %-28s %9.1f MiB imported, %9.1f in all-zero chunks, %9.1f in all-zero pages; at 0x%" PRIx64 "-0x%" PRIx64 "\n", name.c_str(), static_cast<double>(x.imported) / mib,
			        static_cast<double>(x.zchunks) / mib, static_cast<double>(x.zpages) / mib, x.lo, x.hi);
		}
		journal("  %-28s %9.1f MiB imported, %9.1f in all-zero chunks, %9.1f in all-zero pages\n", "total", static_cast<double>(total.imported) / mib, static_cast<double>(total.zchunks) / mib,
		        static_cast<double>(total.zpages) / mib);
	}).detach();
}
'''

EDITS = [
    # setpriority
    ('#include <sys/mman.h>\n', '#include <sys/mman.h>\n#include <sys/resource.h> // experiment 0330: setpriority\n'),
    # 1. the journal's page cache
    ('static FILE* journal_min_file(bool flush_now) {\n', DROP + 'static FILE* journal_min_file(bool flush_now) {\n'),
    ('\t\t\tstd::fflush(f);\n\t\t\tlast_flush = now;\n', '\t\t\tstd::fflush(f);\n\t\t\tlast_flush = now;\n\t\t\tjournal_drop(fileno(f)); // experiment 0330\n'),
    ('\tstd::fflush(f);\n\tif (g_journal_sync) fsync(fileno(f));\n\tstd::fclose(f);\n}\n',
     '\tstd::fflush(f);\n\tif (g_journal_sync) fsync(fileno(f));\n\tjournal_drop(fileno(f)); // experiment 0330\n\tstd::fclose(f);\n}\n'),
    # 2. the breakdown: no SEEK_DATA walk with NODATA, and each name's address span
    ('\tstruct Row {\n\t\tuint64_t reserved = 0, data = 0, imported = 0;\n',
     '\tstatic const bool nodata = BC5_DIAG_ENV("BC5_DIRECT_BREAKDOWN_NODATA") != nullptr; // experiment 0330\n\tstruct Row {\n\t\tuint64_t reserved = 0, data = 0, imported = 0;\n\t\tuint64_t lo = ~0ull, hi = 0; // experiment 0330: the views\' address span\n'),
    ('\t\tfor (uint64_t pos = v.off; pos < end;) {\n\t\t\tconst off_t d = lseek(fd, static_cast<off_t>(pos), SEEK_DATA);\n\t\t\tif (d < 0 || static_cast<uint64_t>(d) >= end) break;\n\t\t\tconst off_t    h  = lseek(fd, d, SEEK_HOLE);\n',
     '\t\tr.lo = std::min(r.lo, v.va); // experiment 0330\n\t\tr.hi = std::max(r.hi, v.va + v.size);\n\t\tfor (uint64_t pos = v.off; pos < end && !nodata;) {\n\t\t\tconst off_t d = lseek(fd, static_cast<off_t>(pos), SEEK_DATA);\n\t\t\tif (d < 0 || static_cast<uint64_t>(d) >= end) break;\n\t\t\tconst off_t    h  = lseek(fd, d, SEEK_HOLE);\n'),
    ('''		journal("  %-28s %3u views: %8.1f MiB reserved, %8.1f with data, %8.1f imported%s\\n", name.c_str(), r.views, static_cast<double>(r.reserved) / mib,
		        static_cast<double>(r.data) / mib, static_cast<double>(r.imported) / mib, r.lazy ? " (lazy)" : "");
''',
     '''		journal("  %-28s %3u views: %8.1f MiB reserved, %8.1f with data, %8.1f imported%s; at 0x%" PRIx64 "-0x%" PRIx64 "\\n", name.c_str(), r.views, static_cast<double>(r.reserved) / mib,
		        static_cast<double>(r.data) / mib, static_cast<double>(r.imported) / mib, r.lazy ? " (lazy)" : (nodata ? " (data not read)" : ""), r.lo, r.hi); // experiment 0330: the span
'''),
    # 3. the zero scan
    ('static std::vector<std::pair<uint64_t, uint64_t>> g_scratch; // experiment 0037: zero-buffer pieces, va and size\n',
     ZEROSCAN + 'static std::vector<std::pair<uint64_t, uint64_t>> g_scratch; // experiment 0037: zero-buffer pieces, va and size\n'),
    # the two timed triggers, at the end of a direct-memory sync
    ('\t\tif (breakdown) direct_breakdown_one(S, "growth", 0);\n\t}\n}\n',
     '''		if (breakdown) direct_breakdown_one(S, "growth", 0);
	}
	// Experiment 0330: the breakdown (BC5_DIRECT_BREAKDOWN_AT) and the zero scan (BC5_DIRECT_ZEROSCAN_AT), once each, at a
	// journal time, for direct memory
	if (S.kind == 0) {
		static const double      at_bd = BC5_DIAG_ENV("BC5_DIRECT_BREAKDOWN_AT") != nullptr ? std::atof(BC5_DIAG_ENV("BC5_DIRECT_BREAKDOWN_AT")) : -1.0;
		static const double      at_zs = BC5_DIAG_ENV("BC5_DIRECT_ZEROSCAN_AT") != nullptr ? std::atof(BC5_DIAG_ENV("BC5_DIRECT_ZEROSCAN_AT")) : -1.0;
		static std::atomic<bool> done_bd {false}, done_zs {false};
		if (at_bd >= 0.0 || at_zs >= 0.0) {
			const double t = timing_now();
			if (at_bd >= 0.0 && t >= at_bd && !done_bd.exchange(true)) direct_breakdown_one(S, "at the set time", 0);
			if (at_zs >= 0.0 && t >= at_zs && !done_zs.exchange(true)) direct_zeroscan(S);
		}
	}
}
'''),
]


def main():
    src_path, out_path, diff_path = sys.argv[1:4]
    raw = open(src_path, 'rb').read()
    md5 = hashlib.md5(raw).hexdigest()
    if md5 != IN_MD5:
        sys.exit(f"{src_path}: md5 {md5}, expected {IN_MD5} (the shared tree's bc5LleAgc.cpp, main's patch 0001)")
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
