#!/usr/bin/env python3
# BC5 experiment 0333, phase S (diagnostic): where the all-zero chunks of the second title's render heaps lie, scan after
# scan. A one-file change of exp 0330's output (bc5LleAgc.mem.cpp, md5 29664e3c: the shared tree's bc5LleAgc.cpp 5bccbb80
# plus patch0330.py). Every switch is BC5_DIAG_ENV and off by default; nothing is released (that is phase R).
#   1. BC5_DIRECT_ZEROSCAN_AT=<s>[,<s>...]: exp 0330's zero scan at each of these journal times, one at a time (a time
#      that passes while a scan still runs is taken by the next sync). A single time works as before.
#   2. BC5_DIRECT_ZEROSCAN_MAP=<name>[,<name>...]: after each scan, per named heap, one journal line of counts and the
#      map, one character a 2 MiB chunk in address order: zero '.' unforced, 'l' in a learned window, 'h' in a hint
#      window only; data '#', 'L', 'H'; '-' not imported, '?' not read. The counts: the chunks that left the zero set
#      since the last scan, and what was zero and unforced in every scan so far, in runs of the file (what a narrower
#      import could leave out). The learned class comes from the chunks map_window forces (learned_apply only).
# Each anchor must occur exactly once.
# usage: patch0333.py <exp 0330's bc5LleAgc.mem.cpp, md5 29664e3c> <out .cpp> <out .diff>   (the input is only read)
import difflib, hashlib, sys

IN_MD5 = '29664e3cdfec8c02410fdf59f9b5c116'

HELPERS = r'''// Experiment 0333: the zero scan at several times, and the zero map's classes. The learned windows' chunks of direct
// memory (map_window marks its direct_force calls) and the scan in flight; the forced set has the same writers.
static std::set<uint64_t>   g_zs_learned;
static thread_local bool    t_zs_learned = false;
static std::atomic<bool>    g_zs_busy {false};
static std::vector<double> zeroscan_times(const char* e) { // "240,480,720": the scan times, sorted
	std::vector<double> v;
	for (const char* c = e; c != nullptr;) {
		char*        end = nullptr;
		const double t   = std::strtod(c, &end);
		if (end == c) break;
		if (t >= 0.0) v.push_back(t);
		if (*end != ',') break;
		c = end + 1;
	}
	std::sort(v.begin(), v.end());
	return v;
}
static std::vector<std::string> zeroscan_names(const char* e) {
	std::vector<std::string> v;
	std::string              cur;
	for (const char* c = e; c != nullptr; c++) {
		if (*c == ',' || *c == 0) {
			if (!cur.empty()) v.push_back(cur);
			cur.clear();
			if (*c == 0) break;
		} else {
			cur.push_back(*c);
		}
	}
	return v;
}
'''

MAP = r'''		// Experiment 0333 (BC5_DIRECT_ZEROSCAN_MAP=<name>[,<name>...]): where these heaps' all-zero chunks lie, one character
		// a 2 MiB chunk in address order (zero: '.' unforced, 'l' learned window, 'h' hint window only; data: '#', 'L', 'H';
		// '-' not imported, '?' not read), what changed since the last scan, and what was zero and unforced in every scan
		// so far, in runs of the file: the part a narrower import could leave out (exp 0333's design).
		static const std::vector<std::string>            map_names = zeroscan_names(BC5_DIAG_ENV("BC5_DIRECT_ZEROSCAN_MAP"));
		static std::map<std::string, std::set<uint64_t>> last_read, last_zero, always; // the scans run one at a time (g_zs_busy)
		const auto in_bo = [&bos](uint64_t c) {
			const auto it = std::upper_bound(bos.begin(), bos.end(), c, [](uint64_t o, const DBo& b) { return o < b.off; });
			return it != bos.begin() && c < std::prev(it)->off + std::prev(it)->size;
		};
		for (const auto& name: map_names) {
			std::string        chars;
			std::set<uint64_t> read_now, zero_now, free_now;
			uint64_t           zc[3] = {0, 0, 0}, dc = 0, nr = 0;
			size_t             nviews = 0;
			for (const auto& v: views_p->v) {
				if (v.name != name) continue;
				nviews++;
				for (uint64_t c = v.off & ~(kDChunk - 1); c < v.off + v.size; c += kDChunk) {
					const int  k  = learned.count(c) != 0 ? 1 : (forced.count(c) != 0 ? 2 : 0);
					const auto it = zero.find(c);
					if (it == zero.end()) {
						const bool imp = in_bo(c);
						chars += imp ? '?' : '-';
						if (imp) nr++;
						continue;
					}
					read_now.insert(c);
					if (it->second) {
						zero_now.insert(c);
						if (k == 0) free_now.insert(c);
						zc[k]++;
						chars += ".lh"[k];
					} else {
						dc++;
						chars += "#LH"[k];
					}
				}
			}
			if (nviews == 0) {
				journal("zero map (exp 0333) scan %u at %.0f s, %s: no view of this name\n", scan, t_at, name.c_str());
				continue;
			}
			const bool first = last_read.count(name) == 0;
			size_t     left = 0, became = 0;
			for (const uint64_t c: last_zero[name]) left += read_now.count(c) != 0 && zero_now.count(c) == 0 ? 1 : 0;
			for (const uint64_t c: zero_now) became += last_read[name].count(c) != 0 && last_zero[name].count(c) == 0 ? 1 : 0;
			std::set<uint64_t>& al = always[name];
			if (first) {
				al = free_now;
			} else {
				std::set<uint64_t> x;
				std::set_intersection(al.begin(), al.end(), free_now.begin(), free_now.end(), std::inserter(x, x.begin()));
				al.swap(x);
			}
			last_read[name] = read_now;
			last_zero[name] = zero_now;
			uint64_t   runs = 0, run = 0, largest = 0, big = 0, prev = 0;
			const auto close_run = [&] {
				if (run != 0) {
					runs++;
					largest = std::max(largest, run);
					if (run >= 4) big += run;
				}
				run = 0;
			};
			for (const uint64_t c: al) {
				if (run != 0 && c != prev + kDChunk) close_run();
				run++;
				prev = c;
			}
			close_run();
			const double ch = static_cast<double>(kDChunk) / mib;
			journal("zero map (exp 0333) scan %u at %.0f s, %s (%zu views, %zu chunks): zero %.0f MiB (unforced %.0f, learned %.0f, hint only %.0f), data %.0f, not read %.0f; "
			        "since the last scan %zu chunks left the zero set and %zu became zero; zero and unforced in every scan so far %.0f MiB in %" PRIu64 " runs (the largest %.0f MiB; %.0f MiB in runs of 8 MiB or more)\n",
			        scan, t_at, name.c_str(), nviews, chars.size(), static_cast<double>(zc[0] + zc[1] + zc[2]) * ch, static_cast<double>(zc[0]) * ch, static_cast<double>(zc[1]) * ch,
			        static_cast<double>(zc[2]) * ch, static_cast<double>(dc) * ch, static_cast<double>(nr) * ch, first ? 0 : left, first ? 0 : became, static_cast<double>(al.size()) * ch, runs,
			        static_cast<double>(largest) * ch, static_cast<double>(big) * ch);
			for (size_t i = 0; i < chars.size(); i += 128) journal("zero map %u %-24s +%5zu MiB %s\n", scan, name.c_str(), i * 2, chars.substr(i, 128).c_str());
		}
		g_zs_busy = false;
'''

EDITS = [
    # the helpers, before exp 0330's zero scan
    ('// Experiment 0330 (BC5_DIRECT_ZEROSCAN_AT=<s>): once, a background thread (nice 19) reads every imported chunk of direct\n',
     HELPERS + '// Experiment 0330 (BC5_DIRECT_ZEROSCAN_AT=<s>): once, a background thread (nice 19) reads every imported chunk of direct\n'),
    # the scan: its number and time, the forced and learned sets as of now, one scan in flight
    ('static void direct_zeroscan(const DState& S) {\n\tconst int fd = dstate_fd(S);\n\tif (fd < 0) return;\n\tconst auto            views_p = direct_views(S);\n\tconst std::vector<DBo> bos    = S.bos;\n\tstd::thread([fd, views_p, bos] {\n',
     '''static void direct_zeroscan(const DState& S, unsigned scan) {
	const int fd = dstate_fd(S);
	if (fd < 0) return;
	const auto            views_p = direct_views(S);
	const std::vector<DBo> bos    = S.bos;
	const std::set<uint64_t> forced = S.forced, learned = g_zs_learned; // experiment 0333: the zero map's classes, as of now
	const double             t_at   = timing_now();
	g_zs_busy                       = true;
	std::thread([fd, views_p, bos, forced, learned, scan, t_at] {
'''),
    ('\t\tstd::set<uint64_t>         seen;\n\t\tstd::vector<uint8_t>       buf(kDChunk);\n',
     '\t\tstd::set<uint64_t>         seen;\n\t\tstd::map<uint64_t, bool>   zero; // experiment 0333: every chunk read, all zero or not\n\t\tstd::vector<uint8_t>       buf(kDChunk);\n'),
    ('\t\t\t\t\tfor (Row* x: {&r, &total}) {\n\t\t\t\t\t\tx->imported += kDChunk;\n',
     '\t\t\t\t\tzero[c] = zp == kDChunk / 4096; // experiment 0333\n\t\t\t\t\tfor (Row* x: {&r, &total}) {\n\t\t\t\t\t\tx->imported += kDChunk;\n'),
    ('''		journal("zero scan (exp 0330): direct memory, %.1f MiB of imported chunks read in %.1f s: all-zero 2 MiB chunks and 4 KiB pages by name\\n", static_cast<double>(total.imported) / mib,
		        timing_now() - t0);
''',
     '''		journal("zero scan (exp 0330): direct memory, %.1f MiB of imported chunks read in %.1f s: all-zero 2 MiB chunks and 4 KiB pages by name; scan %u at %.0f s (exp 0333)\\n",
		        static_cast<double>(total.imported) / mib, timing_now() - t0, scan, t_at);
'''),
    ('''		journal("  %-28s %9.1f MiB imported, %9.1f in all-zero chunks, %9.1f in all-zero pages\\n", "total", static_cast<double>(total.imported) / mib, static_cast<double>(total.zchunks) / mib,
		        static_cast<double>(total.zpages) / mib);
	}).detach();
''',
     '''		journal("  %-28s %9.1f MiB imported, %9.1f in all-zero chunks, %9.1f in all-zero pages\\n", "total", static_cast<double>(total.imported) / mib, static_cast<double>(total.zchunks) / mib,
		        static_cast<double>(total.zpages) / mib);
''' + MAP + '''	}).detach();
'''),
    # the learned class: the chunks a learned window forces
    ('\t\t\t\tif (S.forced.insert(c).second) here += kDChunk;\n',
     '\t\t\t\tif (S.forced.insert(c).second) here += kDChunk;\n\t\t\t\tif (t_zs_learned && S.kind == 0) g_zs_learned.insert(c); // experiment 0333: the zero map\'s learned class\n'),
    ('static void map_window(uint64_t lo, uint64_t hi, std::vector<bc5::direct::Mapping>& have, const char* what, uint64_t addr) {\n\tif (const uint64_t asked = direct_force(lo, hi); asked != 0) {\n',
     '''static void map_window(uint64_t lo, uint64_t hi, std::vector<bc5::direct::Mapping>& have, const char* what, uint64_t addr) {
	t_zs_learned               = std::strcmp(what, "learned") == 0; // experiment 0333: a learned window's chunks, for the zero map
	const uint64_t asked_0333 = direct_force(lo, hi);
	t_zs_learned               = false;
	if (const uint64_t asked = asked_0333; asked != 0) {
'''),
    # the trigger: a list of times, one scan at a time
    ('''		static const double      at_zs = BC5_DIAG_ENV("BC5_DIRECT_ZEROSCAN_AT") != nullptr ? std::atof(BC5_DIAG_ENV("BC5_DIRECT_ZEROSCAN_AT")) : -1.0;
		static std::atomic<bool> done_bd {false}, done_zs {false};
		if (at_bd >= 0.0 || at_zs >= 0.0) {
			const double t = timing_now();
			if (at_bd >= 0.0 && t >= at_bd && !done_bd.exchange(true)) direct_breakdown_one(S, "at the set time", 0);
			if (at_zs >= 0.0 && t >= at_zs && !done_zs.exchange(true)) direct_zeroscan(S);
		}
''',
     '''		static const std::vector<double> at_zs = zeroscan_times(BC5_DIAG_ENV("BC5_DIRECT_ZEROSCAN_AT")); // experiment 0333: a list
		static std::atomic<bool>         done_bd {false};
		static std::atomic<size_t>       next_zs {0};
		if (at_bd >= 0.0 || next_zs.load() < at_zs.size()) {
			const double t = timing_now();
			if (at_bd >= 0.0 && t >= at_bd && !done_bd.exchange(true)) direct_breakdown_one(S, "at the set time", 0);
			// Experiment 0333: one scan at a time; the times that passed while one ran are taken together by the next
			size_t k = next_zs.load();
			if (k < at_zs.size() && t >= at_zs[k] && !g_zs_busy.load()) {
				size_t n = k + 1;
				while (n < at_zs.size() && t >= at_zs[n]) n++;
				if (next_zs.compare_exchange_strong(k, n)) direct_zeroscan(S, static_cast<unsigned>(k + 1));
			}
		}
'''),
]


def main():
    src_path, out_path, diff_path = sys.argv[1:4]
    raw = open(src_path, 'rb').read()
    md5 = hashlib.md5(raw).hexdigest()
    if md5 != IN_MD5:
        sys.exit(f"{src_path}: md5 {md5}, expected {IN_MD5} (exp 0330's bc5LleAgc.mem.cpp)")
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
