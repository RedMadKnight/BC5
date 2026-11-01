#!/usr/bin/env python3
"""BC5 exp 0388, memory cycle: bc5LleAgc.cpp with exp 0379's zero skip (already applied) and the shared canary slices.
Each edit's anchor must occur exactly once, or nothing is written. usage: mkunit.py <unit with 0379's diff> <out>"""
import sys

EDITS = [
    ("g_zruns = 0; // the list's runs: one slice each, whatever order the heaps are placed in\n",
     "g_zruns = 0; // the list's runs, whatever order the heaps are placed in\n"
     "static size_t                                   g_zslices = 0; // exp 0388: canary slices, g_zruns unless BC5_DIRECT_ZERO_SLICES shares them\n"
     "static std::atomic<size_t>                      g_zplaced_runs {0}; // exp 0388: the runs the watcher may flag\n"),
    ("""static void zcanary_watch(size_t runs) {
	setpriority(PRIO_PROCESS, static_cast<id_t>(syscall(SYS_gettid)), 10);
	for (size_t r = 0; !g_zcanary_stop; r = (r + 1) % runs) {
		std::this_thread::sleep_for(std::chrono::milliseconds(50));
		if (g_zflag[r].load() != 0) continue;
		const unsigned char* p = g_zcanary_cpu + r * kDChunk;
""", """static void zcanary_watch(size_t slices) {
	setpriority(PRIO_PROCESS, static_cast<id_t>(syscall(SYS_gettid)), 10);
	for (size_t s = 0; !g_zcanary_stop; s = (s + 1) % slices) {
		std::this_thread::sleep_for(std::chrono::milliseconds(50));
		const size_t placed = g_zplaced_runs.load();
		if (!bc5::zero_skip::slice_watched(g_zflag.get(), placed, slices, s)) continue;
		const unsigned char* p = g_zcanary_cpu + s * kDChunk;
"""),
    ("		if (!bc5::zero_skip::all_zero(p, kDChunk)) g_zflag[r] = 1;\n",
     "		if (!bc5::zero_skip::all_zero(p, kDChunk)) bc5::zero_skip::slice_hit(g_zflag.get(), placed, slices, s);\n"),
    ("if (g_dev->map_shared(g_zcanary_id, static_cast<uint64_t>(run) * kDChunk + (lo - c), hi - lo, va)) {",
     "if (g_dev->map_shared(g_zcanary_id, static_cast<uint64_t>(bc5::zero_skip::slice_of(static_cast<size_t>(run), g_zslices)) * kDChunk + (lo - c), hi - lo, va)) {"),
    ("		const uint64_t size = static_cast<uint64_t>(g_zruns) * kDChunk;\n",
     "		g_zslices           = bc5::zero_skip::slice_count(g_zruns, bc5::zero_skip::parse_slices(std::getenv(\"BC5_DIRECT_ZERO_SLICES\")));\n"
     "		const uint64_t size = static_cast<uint64_t>(g_zslices) * kDChunk;\n"),
    ("		std::thread(zcanary_watch, g_zruns).detach();\n		journal(\"zero skip: canary BO %u, %zu slices of 2 MiB\\n\", g_zcanary_id, g_zruns);\n",
     "		std::thread(zcanary_watch, g_zslices).detach();\n		journal(\"zero skip: canary BO %u, %zu slices of 2 MiB for %zu runs\\n\", g_zcanary_id, g_zslices, g_zruns);\n"),
    ("		if (g_zleft[r] == 0 && g_zflag[r].load() == 0) g_zleft[r] = g_zskip.run_left(static_cast<uint32_t>(r));\n	}\n	return true;\n",
     "		if (g_zleft[r] == 0 && g_zflag[r].load() == 0) g_zleft[r] = g_zskip.run_left(static_cast<uint32_t>(r));\n	}\n"
     "	g_zplaced_runs = std::min(g_zskip.run_count(), g_zruns); // exp 0388: g_zleft first, then the watcher\n	return true;\n"),
]

text = open(sys.argv[1], encoding="utf-8", newline="").read()
for a, b in EDITS:
    a, b = a.replace("\n", "\r\n"), b.replace("\n", "\r\n")  # the host's file has CRLF line ends
    assert text.count(a) == 1, a[:70]
    text = text.replace(a, b)
open(sys.argv[2], "w", encoding="utf-8", newline="").write(text)
print(len(EDITS), "edits")
