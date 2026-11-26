#!/usr/bin/env python3
# BC5 exp 0439 (tag sr439b, 11-22 night, the top session's order): the frame-dump catcher for the progressive blackening,
# diagnosis build only (every line under #ifndef BC5_LEAN; the lean binary gets an empty bc5_sr439b_pad). bc5/sr0439b.hpp
# holds the logic (det-tested by k439/test_sr0439b.cpp); this script wires it into the unit and the pad.
#   BC5_0439_FRAME_DUMP=<private dir> turns it on (unset: nothing runs but one relaxed load per submit and per flip).
#   Arming: the pad combination L3 + R3 (both sticks pressed) held 1 s, or automatically once a scene when the display
#           surface's dark fraction rises slowly (sr0439b.hpp AutoArm; the decompressed display buffer, so it needs
#           BC5_DIRECT_DCC_PRESENT=2, which the third title's runs set). The presses still reach the title.
#   Capture: frame F from the next flip to the one after (every submit, every ring), at that flip a drain, the census of
#           every surface found and the raw dump; F+1 recorded on and censused at its flip; the same again 5 s later.
#           Files: <dir>/sr439b-<yyyymmdd-hhmmss>-c<n>/{index,ops,clears}.tsv and s<id>-<base>-<kind>-<w>x<h>x<d>.raw.
#   Disk: before each dump the free space of <dir> is read; below 20 GB, or if the dump would leave less, the dump is
#           refused (the census still runs) and a journal line says so; one dump is capped at 8 GB.
#   Reads of guest memory go through process_vm_readv on ourselves: a surface unmapped since it was recorded is reported,
#           never a crash.
# Usage: python mksr439b.py UNIT.cpp CONTROLLER.cpp OUT_DIR   (unit after mkb2439/mkbl439/mkvl439; controller after
#        mktc439; every anchor exactly once)
import os
import sys

unit, ctl, out = sys.argv[1], sys.argv[2], sys.argv[3]


def load(p):
    s = open(p, 'rb').read().decode('utf-8', 'surrogateescape')
    assert 'sr439b' not in s, p
    return s.replace('\r\n', '\n'), '\r\n' in s


def save(p, s, crlf):
    if crlf:
        s = s.replace('\n', '\r\n')
    open(p, 'wb').write(s.encode('utf-8', 'surrogateescape'))
    print('mksr439b: wrote', p)


s, crlf_u = load(unit)


def rep(a, b):
    global s
    assert s.count(a) == 1, (a[:70], s.count(a))
    s = s.replace(a, b)


TOP = r'''#include "bc5/sr0439b.hpp" // exp 0439 (tag sr439b): the frame-dump catcher
#ifndef BC5_LEAN
#include <sys/stat.h>
#include <sys/statvfs.h>
#include <sys/uio.h>
#include <unistd.h>
#include <atomic>
#include <chrono>
#include <cinttypes>
#include <cstdlib>
#include <ctime>
#include <mutex>
#include <string>
// exp 0439 (tag sr439b): the catcher's state (bc5/sr0439b.hpp). Lock order: a submitter holds the device lock and then
// srb439::g_mu; the flip drains with neither held and takes g_mu after.
namespace srb439 {
static const char* dir() {
	static const char* d = [] {
		const char* e = std::getenv("BC5_0439_FRAME_DUMP");
		return e != nullptr && e[0] != 0 ? e : static_cast<const char*>(nullptr);
	}();
	return d;
}
static std::mutex               g_mu;
static bc5::sr439b::Machine     g_m;
static bc5::sr439b::AutoArm     g_auto;
static bc5::sr439b::Recorder    g_rec;
static bc5::sr439b::Raw         g_raw; // frame F's raw events (events.bin, the dump session's resolver)
static std::atomic<bool>        g_recording {false};
static std::atomic<int>         g_pad {-1};
static std::string              g_cdir;
static uint32_t                 g_captures = 0;
static double now_s() {
	return std::chrono::duration<double>(std::chrono::steady_clock::now().time_since_epoch()).count();
}
static bool copy(uint64_t a, void* dst, size_t n) { // guest memory, without a fault where a page went away
	iovec l {dst, n}, r {reinterpret_cast<void*>(a), n};
	return process_vm_readv(getpid(), &l, 1, &r, 1, 0) == static_cast<ssize_t>(n);
}
static uint64_t free_bytes(const char* d) {
	struct statvfs v {};
	return statvfs(d, &v) == 0 ? static_cast<uint64_t>(v.f_bavail) * v.f_frsize : 0;
}
// After a drain: every recorded surface counted (slot 0: the end of F, 1: of F+1), and dumped when `dump`.
static void census(int slot, bool dump) {
	constexpr uint64_t kMinFree = 20ull << 30, kCap = 8ull << 30, kChunk = 16ull << 20;
	auto&              rec = g_rec;
	uint64_t           total = 0;
	for (const auto& x: rec.surf) total += x.bytes;
	const uint64_t fr = free_bytes(dir());
	if (dump && (fr < kMinFree || fr - kMinFree < std::min(total, kCap))) {
		std::fprintf(stderr, "[bc5] exp 0439 (tag sr439b): dump REFUSED: %.1f GB free in %s, %.1f GB to write, 20 GB must stay free; the census runs\n", fr / 1e9, dir(), std::min(total, kCap) / 1e9);
		dump = false;
	}
	if (dump) mkdir(g_cdir.c_str(), 0700);
	if (dump && slot == 0 && !g_raw.out.empty()) { // the raw events of F (sr0439b.hpp, class Raw)
		if (FILE* f = std::fopen((g_cdir + "/events.bin").c_str(), "wb"); f != nullptr) {
			std::fwrite(g_raw.out.data(), 1, g_raw.out.size(), f);
			std::fclose(f);
		}
		std::fprintf(stderr, "[bc5] exp 0439 (tag sr439b): events.bin %.1f MB: %" PRIu64 " blocks, %" PRIu64 " repeated, %" PRIu64 " programs%s\n", g_raw.out.size() / 1e6, g_raw.blocks, g_raw.refs, g_raw.programs,
		             g_raw.full ? "; FULL at 256 MB, the rest of F not in it" : "");
	}
	if (slot == 0) g_raw = bc5::sr439b::Raw(); // freed
	std::vector<uint8_t> buf(kChunk);
	uint64_t             written = 0, nan_surf = 0, gone = 0;
	const double         t0 = now_s();
	for (size_t i = 0; i < rec.surf.size(); i++) {
		auto&             x = rec.surf[i];
		bc5::sr439b::Census c;
		FILE*             f = nullptr;
		if (dump && written + x.bytes <= kCap) {
			char fn[640];
			std::snprintf(fn, sizeof(fn), "%s/s%04zu-%" PRIx64 "-%s-%ux%ux%u.raw", g_cdir.c_str(), i, x.base, bc5::sr439b::kind_name(x.f.kind), x.w, x.h, x.d);
			f = std::fopen(fn, "wb");
			if (f != nullptr) x.file = fn + g_cdir.size() + 1;
		}
		bool ok = true;
		for (uint64_t off = 0; off < x.bytes; off += kChunk) {
			const size_t n = static_cast<size_t>(std::min(kChunk, x.bytes - off));
			if (!copy(x.base + off, buf.data(), n)) {
				ok = false;
				break;
			}
			c.add(bc5::sr439b::count(buf.data(), n, x.f.kind));
			if (f != nullptr) written += std::fwrite(buf.data(), 1, n, f);
		}
		if (f != nullptr) std::fclose(f);
		if (!ok) gone++, c.done = false;
		x.at[slot] = c;
		nan_surf += (c.nan + c.inf) != 0;
		if (slot == 0 && x.cb && x.dcc && x.dcc_base != 0) { // exp 0439 (tag dk439): the target's DCC keys at the end of F
			const uint64_t       kn = std::min<uint64_t>((x.bytes + 255) / 256, 4ull << 20);
			std::vector<uint8_t> kb(static_cast<size_t>(kn));
			if (kn != 0 && copy(x.dcc_base, kb.data(), kb.size())) {
				bc5::sr439b::KeyHist h;
				h.add(kb.data(), kb.size());
				h.finish();
				uint32_t tv = 0;
				uint64_t tc = 0;
				h.top(tv, tc);
				x.keys_n = h.n, x.keys_ff = h.ff, x.keys_00 = h.z, x.keys_other = h.other, x.keys_top = tv, x.keys_top_n = static_cast<uint32_t>(tc);
				if (dump) {
					char kf[640];
					std::snprintf(kf, sizeof(kf), "%s/k%04zu-%" PRIx64 ".keys", g_cdir.c_str(), i, x.dcc_base);
					if (FILE* g = std::fopen(kf, "wb"); g != nullptr) {
						std::fwrite(kb.data(), 1, kb.size(), g);
						std::fclose(g);
					}
				}
			}
		}
	}
	std::fprintf(stderr, "[bc5] exp 0439 (tag sr439b): capture %u, end of frame %s: %zu surfaces (%.2f GB), %" PRIu64 " with NaN/Inf, %" PRIu64 " no longer readable; %zu ops in %u submits, %u tables read, %zu clears; %s %.2f GB in %.1f s%s%s\n",
	             g_captures, slot == 0 ? "F" : "F+1", rec.surf.size(), total / 1e9, nan_surf, gone, rec.ops.size(), rec.submits, rec.ptr_tables, rec.clears.size(), dump ? "dumped" : "no dump,", written / 1e9, now_s() - t0,
	             dump ? " to " : "", dump ? g_cdir.c_str() : "");
}
static void tables() {
	mkdir(g_cdir.c_str(), 0700);
	if (FILE* f = std::fopen((g_cdir + "/index.tsv").c_str(), "w"); f != nullptr) {
		std::fprintf(f, "id\tbase\tbytes\tkind\tfmt\tw\th\td\tsw\tdcc\trole\tfirst_op\tcb_writes\trefs\tF_elems\tF_nan\tF_inf\tF_zero\tF_dark\tF_ok\tF1_elems\tF1_nan\tF1_inf\tF1_zero\tF1_dark\tF1_ok\tfile"
		                "\tdcc_base\tdcc_control\tword6\tword7\tkeys_n\tkeys_ff\tkeys_00\tkeys_other\tkeys_top\tkeys_top_n\n"); // exp 0439 (tag dk439)
		for (size_t i = 0; i < g_rec.surf.size(); i++) {
			const auto& x = g_rec.surf[i];
			std::fprintf(f, "%zu\t0x%" PRIx64 "\t%" PRIu64 "\t%s\t%u\t%u\t%u\t%u\t%u\t%d\t%s\t%u\t%u\t%u", i, x.base, x.bytes, bc5::sr439b::kind_name(x.f.kind), x.fmt, x.w, x.h, x.d, x.sw_mode, x.dcc ? 1 : 0,
			             x.cb ? "cb" : x.image ? "image" : "buffer", x.first_op, x.cb_writes, x.refs);
			for (int k = 0; k < 2; k++)
				std::fprintf(f, "\t%" PRIu64 "\t%" PRIu64 "\t%" PRIu64 "\t%" PRIu64 "\t%" PRIu64 "\t%d", x.at[k].elems, x.at[k].nan, x.at[k].inf, x.at[k].zero, x.at[k].dark, x.at[k].done ? 1 : 0);
			std::fprintf(f, "\t%s", x.file.empty() ? "-" : x.file.c_str());
			std::fprintf(f, "\t0x%" PRIx64 "\t0x%08x\t0x%08x\t0x%08x\t%" PRIu64 "\t%" PRIu64 "\t%" PRIu64 "\t%" PRIu64 "\t0x%02x\t%u\n", x.dcc_base, x.dcc_control, x.word6, x.word7, x.keys_n, x.keys_ff, x.keys_00,
			             x.keys_other, x.keys_top, x.keys_top_n); // exp 0439 (tag dk439)
		}
		std::fclose(f);
	}
	if (FILE* f = std::fopen((g_cdir + "/ops.tsv").c_str(), "w"); f != nullptr) {
		std::fprintf(f, "seq\tsubmit\tring\tkind\tpgm\tcb_mode\trefs\n");
		for (const auto& o: g_rec.ops) {
			std::fprintf(f, "%u\t%u\t%d\t%c\t0x%" PRIx64 "\t%u\t", o.seq, o.submit, o.ring, o.kind, o.pgm, o.cb_mode);
			for (size_t k = 0; k < o.refs.size(); k++) std::fprintf(f, "%s%u:%c", k ? "," : "", o.refs[k].surf, o.refs[k].cb ? 'w' : 'v');
			std::fprintf(f, "\n");
		}
		std::fclose(f);
	}
	if (FILE* f = std::fopen((g_cdir + "/clears.tsv").c_str(), "w"); f != nullptr) {
		std::fprintf(f, "before_seq\tsubmit\tring\twhat\n");
		for (const auto& c: g_rec.clears) std::fprintf(f, "%u\t%u\t%d\t%s\n", c.seq, c.submit, c.ring, c.what.c_str());
		std::fclose(f);
	}
}
} // namespace srb439
#endif
'''
INC = [ln for ln in s.split('\n') if ln.startswith('#include "bc5/fp0439.hpp"')]
assert len(INC) == 1, INC
rep(INC[0] + '\n', INC[0] + '\n' + TOP)

# ---- the submit hook: before experiment 0049's shader dump, with the mappings of this submit ----
rep('''	shader_dump(ib, num_dwords, *maps_p); // experiment 0049
''', '''#ifndef BC5_LEAN
	if (srb439::g_recording.load(std::memory_order_relaxed)) { // exp 0439 (tag sr439b): the frame being recorded
		const auto cov = [&maps_p](uint64_t a, uint64_t b) { return covered_sorted(*maps_p, a, b); };
		const auto cr  = bc5::ib_chain::collect(ib, num_dwords, cov, true);
		std::vector<std::pair<const uint32_t*, size_t>> pcs;
		for (const auto& pc: cr.pieces) pcs.emplace_back(pc.src, static_cast<size_t>(pc.n));
		std::lock_guard lk(srb439::g_mu);
		if (srb439::g_recording.load()) srb439::g_rec.submit(pcs, ring, cov);
	}
#endif
	shader_dump(ib, num_dwords, *maps_p); // experiment 0049
''')

# ---- the flip: the state machine, the census and the dump (start of dc439_flip), the auto-arm sample (its end) ----
rep('''static void dc439_flip(int index) {
''', '''#ifndef BC5_LEAN
static void sr439b_flip() { // exp 0439 (tag sr439b): at every flip the title submits with an EOP
	if (srb439::dir() == nullptr) return;
	const double t   = srb439::now_s();
	const int    pad = srb439::g_pad.exchange(-1);
	bc5::sr439b::Act act;
	{
		std::lock_guard lk(srb439::g_mu);
		if (pad >= 0) srb439::g_m.pad(pad != 0, t);
		act = srb439::g_m.flip(t);
		if (act == bc5::sr439b::Act::Record && srb439::g_m.capture == 0) {
			srb439::g_captures++;
		}
		if (act == bc5::sr439b::Act::Record) {
			srb439::g_rec.reset();
			srb439::g_raw     = bc5::sr439b::Raw();
			srb439::g_rec.raw = &srb439::g_raw; // frame F only
			char       ts[32];
			const auto now = std::time(nullptr);
			std::strftime(ts, sizeof(ts), "%Y%m%d-%H%M%S", std::localtime(&now));
			srb439::g_cdir = std::string(srb439::dir()) + "/sr439b-" + ts + "-c" + std::to_string(srb439::g_m.capture);
			std::fprintf(stderr, "[bc5] exp 0439 (tag sr439b): capture %u%s: recording the next frame to %s\\n", srb439::g_captures, srb439::g_m.capture == 0 ? "" : " (5 s later)", srb439::g_cdir.c_str());
			srb439::g_recording.store(true);
			return;
		}
		if (act == bc5::sr439b::Act::None) return;
		srb439::g_recording.store(false); // no submit records while the GPU is drained and the memory read
		srb439::g_rec.raw = nullptr;      // F+1 adds no raw events
	}
	drain(); // every ring's jobs of the frame are done: the surfaces hold what the frame left
	std::lock_guard lk(srb439::g_mu);
	srb439::census(act == bc5::sr439b::Act::CensusDump ? 0 : 1, act == bc5::sr439b::Act::CensusDump);
	if (act == bc5::sr439b::Act::CensusDump) srb439::g_recording.store(true); // F+1
	else srb439::tables();
}
static void sr439b_dark(uint64_t data, uint32_t w, uint32_t h) { // exp 0439 (tag sr439b): the auto-arm's sample
	if (srb439::dir() == nullptr || data == 0 || w == 0 || h == 0) return;
	// the surface the decompress just read and wrote (dc439 reads it directly too): 4096 pixels, evenly spaced
	const uint64_t px = static_cast<uint64_t>(w) * h;
	uint8_t        q[4 * 4096];
	const auto*    m = reinterpret_cast<const volatile uint8_t*>(data);
	for (uint32_t i = 0; i < 4096; i++)
		for (uint32_t c = 0; c < 4; c++) q[4 * i + c] = m[4 * (px * i / 4096) + c];
	const double t = srb439::now_s(), d = bc5::sr439b::dark_fraction(q, 4096, 4096);
	std::lock_guard lk(srb439::g_mu);
	if (srb439::g_auto.feed(t, d) && srb439::g_m.arm("auto"))
		std::fprintf(stderr, "[bc5] exp 0439 (tag sr439b): armed by the dark fraction (%.2f, a slow rise)\\n", d);
}
#else
static void sr439b_flip() {}
static void sr439b_dark(uint64_t, uint32_t, uint32_t) {}
#endif
static void dc439_flip(int index) {
	sr439b_flip(); // exp 0439 (tag sr439b)
''')
rep('''	if (!ok) {
		static std::atomic<uint64_t> n_failed {0};
''', '''	if (ok) sr439b_dark(s.data, s.w, s.h); // exp 0439 (tag sr439b): the decompressed display surface
	if (!ok) {
		static std::atomic<uint64_t> n_failed {0};
''')
s = s.rstrip('\n') + '''

// exp 0439 (tag sr439b): the pad's L3 + R3 state from src/libs/controller.cpp (pad_fill_data, at each change)
extern "C" void bc5_sr439b_pad(int both) {
#if defined(KYTY_BC5_DIRECT) && !defined(BC5_LEAN)
	if (srb439::dir() != nullptr) srb439::g_pad.store(both != 0 ? 1 : 0);
#else
	(void)both;
#endif
}
'''
assert s.count('tag sr439b') >= 9, s.count('tag sr439b')
save(os.path.join(out, os.path.basename(unit)), s, crlf_u)

s, crlf_c = load(ctl)
rep('#include "bc5/tc0439.hpp" // exp 0439 (tag tc439)\n', '''#include "bc5/tc0439.hpp" // exp 0439 (tag tc439)
extern "C" void bc5_sr439b_pad(int both); // exp 0439 (tag sr439b): src/libs/bc5LleAgc.cpp
''')
rep('''	data->buttons                = state.buttons;
''', '''	data->buttons                = state.buttons;
	{ // exp 0439 (tag sr439b): L3 + R3 held 1 s arms the frame dump (BC5_0439_FRAME_DUMP); the presses still reach the title
		static int last = -1;
		const int  both = (state.buttons & (PAD_BUTTON_L3 | PAD_BUTTON_R3)) == (PAD_BUTTON_L3 | PAD_BUTTON_R3) ? 1 : 0;
		// only a connected pad's reads: the third title reads a second, unconnected handle every frame (buttons 0), which
		// flipped the state each read and the 1-s hold never built up (run st439-1122-2340, KYTY_BC5_INPUT_TRACE=1)
		if (connected && both != last) {
			last = both;
			bc5_sr439b_pad(both);
		}
	}
''')
save(os.path.join(out, os.path.basename(ctl)), s, crlf_c)
