#!/usr/bin/env python3
# BC5 exp 0439 (tag vz439, 11-24 night, the top session's order on the film noise): the decoder's slot bytes dumped
# against shots of the same moment, and each slot's import and K1R state watched. Diagnosis builds only (BC5_LEAN
# compiles all of it out); everything is off unless BC5_0439_VD2_DUMP is set.
#   BC5_0439_VD2_DUMP=<k,k,...>  picture numbers (counted from 0 over all decoder instances) whose slot is written to
#                                BC5_0439_VD2_DUMP_DIR/vz-<k>-w.nv12 right after the CPU copy (and the vf439 fill), and
#                                again as vz-<k>-r.nv12 just before the next picture is copied into the same slot (what
#                                the slot held, seen by the CPU, for the whole time the GPU could read it). "1" with no
#                                list = the log lines only.
#   the log (stderr, play-last.log): one line per picture (number, slot, time on the journal's base, wall clock); one
#   line at the FIRST CPU write into each slot; one per dump with an FNV-1a hash of the bytes (w and r compared).
#   the watch (gc/direct.log, "tag vz439"): every slot's start, each 2 MiB boundary inside it, its chroma start and its
#   last byte are described by wa412_text at each mapping sync, a line when the text changes: the view, whether the
#   chunk is WRITTEN (SEEK_DATA) and IMPORTED, and the GPU's mapping (title's memory / K1R zero cover / none).
# Usage: python3 mkvz439.py <d2/new>   (patches bc5LleAgc.cpp and videoDec2Decoder.cpp in place, every anchor once)
import os
import sys

D = sys.argv[1]


def patch(name, reps):
    p = os.path.join(D, name)
    s = open(p, 'rb').read().decode('utf-8', 'surrogateescape')
    assert 'vz439' not in s, name
    crlf = '\r\n' in s
    s = s.replace('\r\n', '\n')
    for a, b in reps:
        assert s.count(a) == 1, (name, a[:80], s.count(a))
        s = s.replace(a, b)
    if crlf:
        s = s.replace('\n', '\r\n')
    open(p, 'wb').write(s.encode('utf-8', 'surrogateescape'))
    print('mkvz439: patched', p)


UNIT_CODE = r'''#ifndef BC5_LEAN
// exp 0439 (tag vz439): the decoder's slots watched (BC5_0439_VD2_DUMP; the decoder registers the addresses)
static std::atomic<uint64_t> g_vz439_a[48];
static std::atomic<uint32_t> g_vz439_n {0};
extern "C" void bc5_vz439_watch(uint64_t a) {
	const uint32_t n = std::min<uint32_t>(g_vz439_n.load(std::memory_order_acquire), 48);
	for (uint32_t i = 0; i < n; i++)
		if (g_vz439_a[i].load(std::memory_order_relaxed) == a) return;
	const uint32_t i = g_vz439_n.fetch_add(1);
	if (i < 48) g_vz439_a[i].store(a, std::memory_order_release);
}
extern "C" double bc5_vz439_now() { return timing_now(); }
static void vz439_look(const DState& S, const std::vector<DView>& views, int fd) {
	const uint32_t n = std::min<uint32_t>(g_vz439_n.load(std::memory_order_acquire), 48);
	if (n == 0 || S.kind != 0) return;
	static std::string last[48];
	for (uint32_t i = 0; i < n; i++) {
		const uint64_t a = g_vz439_a[i].load(std::memory_order_acquire);
		if (a == 0) continue;
		char text[640];
		wa412_text(S, views, fd, a, text, sizeof(text));
		if (last[i] != text) {
			journal("watch (exp 0439, tag vz439): t %.3f s: slot address 0x%" PRIx64 ": %s%s\n", timing_now(), a, text, last[i].empty() ? "  (first look)" : "  <-- changed");
			last[i] = text;
		}
	}
}
#endif
'''

patch('bc5LleAgc.cpp', [
    ('static void direct_sync_one(DState& S, bool force) {\n',
     UNIT_CODE + 'static void direct_sync_one(DState& S, bool force) {\n'),
    ('\twa412_look(S, views, fd); // exp 0412 (tag wa412)\n',
     '\twa412_look(S, views, fd); // exp 0412 (tag wa412)\n#ifndef BC5_LEAN\n\tvz439_look(S, views, fd); // exp 0439 (tag vz439)\n#endif\n'),
])

DEC_CODE = r'''#ifndef BC5_LEAN
#include <algorithm>
#include <ctime>
#include <fcntl.h>
#include <mutex>
#include <string>
#include <unistd.h>
#include <unordered_map>
#include <vector>
extern "C" void   bc5_vz439_watch(uint64_t a); // exp 0439 (tag vz439), in bc5LleAgc.cpp
extern "C" double bc5_vz439_now();
namespace vz439 { // exp 0439 (tag vz439): BC5_0439_VD2_DUMP
struct Cfg {
	bool                  on = false;
	std::vector<uint64_t> ks;
	std::string           dir = ".";
};
inline const Cfg& cfg() {
	static const Cfg c = [] {
		Cfg         r;
		const char* e = std::getenv("BC5_0439_VD2_DUMP");
		if (e == nullptr || e[0] == 0 || (e[0] == '0' && e[1] == 0)) return r;
		r.on = true;
		if (!(e[0] == '1' && e[1] == 0)) {
			while (*e != 0) {
				char*          end = nullptr;
				const uint64_t k   = std::strtoull(e, &end, 10);
				if (end == e) break;
				r.ks.push_back(k);
				e = *end == ',' ? end + 1 : end;
				if (*end != ',') break;
			}
		}
		if (const char* d = std::getenv("BC5_0439_VD2_DUMP_DIR"); d != nullptr && d[0] != 0) r.dir = d;
		std::fprintf(stderr, "[bc5] exp 0439 (tag vz439): BC5_0439_VD2_DUMP on: %zu pictures to dump into %s\n", r.ks.size(), r.dir.c_str());
		return r;
	}();
	return c;
}
struct Slot {
	uint64_t pics = 0, pending_k = ~0ull, pending_len = 0, w_hash = 0;
};
inline std::mutex&                               mu() { static std::mutex m; return m; }
inline std::unordered_map<uintptr_t, Slot>&      slots() { static std::unordered_map<uintptr_t, Slot> s; return s; }
inline std::atomic<uint64_t>&                    counter() { static std::atomic<uint64_t> n {0}; return n; }
inline double                                    wall() { timespec ts {}; clock_gettime(CLOCK_REALTIME, &ts); return static_cast<double>(ts.tv_sec) + static_cast<double>(ts.tv_nsec) / 1e9; }
inline uint64_t fnv(const uint8_t* d, size_t n) {
	uint64_t h = 1469598103934665603ull;
	for (size_t i = 0; i < n; i++) h = (h ^ d[i]) * 1099511628211ull;
	return h;
}
inline bool put(const std::string& p, const uint8_t* d, size_t n) {
	const int fd = open(p.c_str(), O_WRONLY | O_CREAT | O_TRUNC | O_CLOEXEC, 0600);
	if (fd < 0) return false;
	size_t done = 0;
	while (done < n) {
		const ssize_t w = write(fd, d + done, n - done);
		if (w <= 0) break;
		done += static_cast<size_t>(w);
	}
	close(fd);
	return done == n;
}
// before the CPU writes picture k into the slot: the first write is noted (and the slot watched); a pending dump of the
// slot's previous picture is taken now, from what the slot holds just before it is overwritten
inline uint64_t before(uint8_t* dst, size_t size, uint32_t w, uint32_t h, uint32_t pitch, uint64_t required) {
	const Cfg& c = cfg();
	if (!c.on) return ~0ull;
	const uint64_t              k = counter()++;
	std::scoped_lock            l(mu());
	Slot&                       s = slots()[reinterpret_cast<uintptr_t>(dst)];
	const uintptr_t             a = reinterpret_cast<uintptr_t>(dst);
	if (s.pics == 0) {
		uint64_t chunks = 0;
		bc5_vz439_watch(a);
		for (uintptr_t x = (a + 0x200000u) & ~uintptr_t {0x1fffff}; x < a + size; x += 0x200000u) {
			bc5_vz439_watch(x);
			chunks++;
		}
		bc5_vz439_watch(a + static_cast<uintptr_t>(pitch) * h);
		bc5_vz439_watch(a + size - 1);
		std::fprintf(stderr, "[bc5] exp 0439 (tag vz439): picture %" PRIu64 ": FIRST CPU write into slot %p size %zu (%ux%u pitch %u, chroma at +0x%" PRIx64 ", span %" PRIu64 ", 2 MiB boundaries inside %" PRIu64 ") at t %.3f s, wall %.3f\n",
		             k, static_cast<void*>(dst), size, w, h, pitch, static_cast<uint64_t>(pitch) * h, required, chunks, bc5_vz439_now(), wall());
	}
	s.pics++;
	if (s.pending_k != ~0ull) {
		const size_t      n    = static_cast<size_t>(std::min<uint64_t>(s.pending_len, size));
		const uint64_t    hr   = fnv(dst, n);
		const std::string p    = c.dir + "/vz-" + std::to_string(s.pending_k) + "-r.nv12";
		const bool        ok   = put(p, dst, n);
		std::fprintf(stderr, "[bc5] exp 0439 (tag vz439): picture %" PRIu64 " re-read from slot %p before picture %" PRIu64 " overwrites it, t %.3f s, wall %.3f: hash %016" PRIx64 " (written %016" PRIx64 ", %s)%s %s\n",
		             s.pending_k, static_cast<void*>(dst), k, bc5_vz439_now(), wall(), hr, s.w_hash, hr == s.w_hash ? "the same" : "CHANGED", ok ? " ->" : " WRITE FAILED", p.c_str());
		s.pending_k = ~0ull;
	}
	return k;
}
// after the copy and the fill: the per-picture line; a picture on the list is dumped now and its re-read armed
inline void after(uint8_t* dst, uint64_t k, uint32_t w, uint32_t h, uint32_t pitch, uint64_t required) {
	if (k == ~0ull) return;
	const Cfg& c = cfg();
	std::fprintf(stderr, "[bc5] exp 0439 (tag vz439): p %" PRIu64 " slot %p t %.3f wall %.3f\n", k, static_cast<void*>(dst), bc5_vz439_now(), wall());
	if (std::find(c.ks.begin(), c.ks.end(), k) == c.ks.end()) return;
	std::scoped_lock  l(mu());
	Slot&             s  = slots()[reinterpret_cast<uintptr_t>(dst)];
	const size_t      n  = static_cast<size_t>(required);
	const std::string p  = c.dir + "/vz-" + std::to_string(k) + "-w.nv12";
	s.w_hash             = fnv(dst, n);
	const bool        ok = put(p, dst, n);
	s.pending_k          = k;
	s.pending_len        = required;
	std::fprintf(stderr, "[bc5] exp 0439 (tag vz439): picture %" PRIu64 " dumped as written: slot %p %ux%u pitch %u, %" PRIu64 " bytes, hash %016" PRIx64 ", t %.3f s, wall %.3f%s %s\n",
	             k, static_cast<void*>(dst), w, h, pitch, required, s.w_hash, bc5_vz439_now(), wall(), ok ? " ->" : " WRITE FAILED", p.c_str());
}
} // namespace vz439
#endif
'''

patch('videoDec2Decoder.cpp', [
    ('namespace Libs::VideoDec2::Decoder {\n', DEC_CODE + '\nnamespace Libs::VideoDec2::Decoder {\n'),
    ('\t\tauto* dst = static_cast<uint8_t*>(frame_buffer.data);\n\t\tstd::memset(dst, 0, static_cast<size_t>(required));\n',
     '\t\tauto* dst = static_cast<uint8_t*>(frame_buffer.data);\n#ifndef BC5_LEAN\n'
     '\t\tconst uint64_t vz_k = vz439::before(dst, frame_buffer.size, width, height, pitch, required); // exp 0439 (tag vz439)\n#endif\n'
     '\t\tstd::memset(dst, 0, static_cast<size_t>(required));\n'),
    ('\t\t}\n\t\toutput->valid           = true;\n',
     '\t\t}\n#ifndef BC5_LEAN\n\t\tvz439::after(dst, vz_k, width, height, pitch, required); // exp 0439 (tag vz439)\n#endif\n'
     '\t\toutput->valid           = true;\n'),
])
