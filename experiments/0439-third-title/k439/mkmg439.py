#!/usr/bin/env python3
# BC5 exp 0439 (tag mg439, 11-24 night, the top session's step 3): the direct memory's growth in numbers. Diagnosis builds
# only (BC5_LEAN compiles it out); a journal line every 10 s while BC5_0439_MG_CENSUS=1 (off by default):
#   allocated   = the direct memory the title holds (offered - the allocator's free list, memory.cpp Bc5FreeStats);
#   released    = the bytes sceKernelReleaseDirectMemory gave back so far (cumulative);
#   resident    = the memfd's data bytes (SEEK_DATA / SEEK_HOLE walk: pages written once and never punched out);
#   viewed      = the union of the file ranges under the title's live direct views (aliases counted once);
#   pinned      = the imported BOs (S.bos), split into eager-view and the rest.
# resident - allocated is the memory the title gave back that still occupies RAM (KytyPlus does not punch released
# ranges out of the memfd); pinned - viewed is the chunk rounding plus anything imported and no longer viewed.
# Usage: python3 mkmg439.py <d2/new> <memory.cpp out dir>   (patches d2/new/bc5LleAgc.cpp in place and writes
#        <out>/memory.cpp from ~/src/KytyPlus/src/kernel/memory.cpp; every anchor exactly once)
import os
import sys

D, OUT = sys.argv[1], sys.argv[2]


def load(p):
    s = open(p, 'rb').read().decode('utf-8', 'surrogateescape')
    assert 'mg439' not in s, p
    return s, '\r\n' in s


def save(p, s, crlf):
    if crlf:
        s = s.replace('\n', '\r\n')
    open(p, 'wb').write(s.encode('utf-8', 'surrogateescape'))
    print('mkmg439: wrote', p)


def rep(s, a, b):
    assert s.count(a) == 1, (a[:70], s.count(a))
    return s.replace(a, b)


# memory.cpp: the numbers, exported
src = os.path.expanduser('~/src/KytyPlus/src/kernel/memory.cpp')
s, crlf = load(src)
s = s.replace('\r\n', '\n')
s = rep(s, 'static void ff412_state_line() {\n', '''#ifndef BC5_LEAN
// exp 0439 (tag mg439): the direct memory in numbers for the growth census (bc5LleAgc.cpp's mg439 line)
static std::atomic<uint64_t> g_mg439_released {0};
extern "C" void bc5_mg439_direct(uint64_t* offered, uint64_t* free_total, uint64_t* released_total) {
	std::scoped_lock memory_lock(g_memory_operation_mutex);
	uint64_t total = 0, largest = 0, runs = 0;
	if (g_physical_memory) g_physical_memory->Bc5FreeStats(&total, &largest, &runs);
	*offered        = static_cast<uint64_t>(PhysicalMemory::Size());
	*free_total     = total;
	*released_total = g_mg439_released.load();
}
#endif
static void ff412_state_line() {
''')
s = rep(s, '''	if (g_free_callback != nullptr) {
		for (const auto& alias: mapped_aliases) {
			g_free_callback(alias.map_vaddr, alias.map_size);
		}
	}

	return OK;
}
''', '''	if (g_free_callback != nullptr) {
		for (const auto& alias: mapped_aliases) {
			g_free_callback(alias.map_vaddr, alias.map_size);
		}
	}
#ifndef BC5_LEAN
	g_mg439_released += len; // exp 0439 (tag mg439)
#endif

	return OK;
}
''')
save(os.path.join(OUT, 'memory.cpp'), s, crlf)

# bc5LleAgc.cpp: the line, every 10 s, from the direct sync
p = os.path.join(D, 'bc5LleAgc.cpp')
s, crlf = load(p)
s = s.replace('\r\n', '\n')
s = rep(s, 'static void direct_sync_one(DState& S, bool force) {\n', '''#ifndef BC5_LEAN
// exp 0439 (tag mg439): BC5_0439_MG_CENSUS=1, the growth census line every 10 s (see mkmg439.py)
extern "C" void bc5_mg439_direct(uint64_t* offered, uint64_t* free_total, uint64_t* released_total);
static void mg439_census(const DState& S, const std::vector<DView>& views, int fd) {
	static const bool on = [] {
		const char* e = std::getenv("BC5_0439_MG_CENSUS");
		return e != nullptr && e[0] == '1' && e[1] == 0;
	}();
	if (!on || S.kind != 0) return;
	static uint64_t last_ns = 0;
	const uint64_t  now     = SoftCp::now_ns();
	if (last_ns != 0 && now - last_ns < 10'000'000'000ull) return;
	last_ns = now;
	uint64_t offered = 0, freeb = 0, released = 0;
	bc5_mg439_direct(&offered, &freeb, &released);
	uint64_t resident = 0, extents = 0;
	const off_t end = lseek(fd, 0, SEEK_END);
	for (off_t pos = 0; pos < end;) {
		const off_t d = lseek(fd, pos, SEEK_DATA);
		if (d < 0) break;
		off_t h = lseek(fd, d, SEEK_HOLE);
		if (h < 0) h = end;
		resident += static_cast<uint64_t>(h - d);
		extents++;
		pos = h;
	}
	std::vector<std::pair<uint64_t, uint64_t>> r;
	r.reserve(views.size());
	uint64_t eager_view = 0;
	for (const auto& v: views) {
		r.emplace_back(v.off, v.off + v.size);
		if (v.eager) eager_view += v.size;
	}
	std::sort(r.begin(), r.end());
	uint64_t viewed = 0, lo = 0, hi = 0;
	bool     open = false;
	for (const auto& x: r) {
		if (!open || x.first > hi) {
			if (open) viewed += hi - lo;
			lo = x.first; hi = x.second; open = true;
		} else if (x.second > hi) {
			hi = x.second;
		}
	}
	if (open) viewed += hi - lo;
	uint64_t pinned = 0;
	for (const auto& b: S.bos) pinned += b.size;
	const double M = 1048576.0;
	journal("mg439 (exp 0439): t %.0f s: allocated %.0f MiB (offered %.0f, free %.0f); released so far %.0f MiB; memfd resident %.0f MiB in %" PRIu64
	        " extents; viewed (union) %.0f MiB under %zu views (eager views %.0f MiB, sizes summed); pinned %.0f MiB in %zu BOs; resident - allocated %.0f MiB, pinned - viewed %.0f MiB\\n",
	        timing_now(), static_cast<double>(offered - freeb) / M, static_cast<double>(offered) / M, static_cast<double>(freeb) / M, static_cast<double>(released) / M,
	        static_cast<double>(resident) / M, extents, static_cast<double>(viewed) / M, views.size(), static_cast<double>(eager_view) / M, static_cast<double>(pinned) / M,
	        S.bos.size(), (static_cast<double>(resident) - static_cast<double>(offered - freeb)) / M, (static_cast<double>(pinned) - static_cast<double>(viewed)) / M);
}
#endif
static void direct_sync_one(DState& S, bool force) {
''')
s = rep(s, '\twa412_look(S, views, fd); // exp 0412 (tag wa412)\n', '\twa412_look(S, views, fd); // exp 0412 (tag wa412)\n#ifndef BC5_LEAN\n\tmg439_census(S, views, fd); // exp 0439 (tag mg439)\n#endif\n')
save(p, s, crlf)
