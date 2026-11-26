#!/usr/bin/env python3
r"""BC5 experiment 0421 (tag fs421), prepared 2026-11-15 on the laptop, NOT compiled in the host:
    mk0421.py <tree root>
on a tree of exp 0419's build V or W (after `mkv0419.py lazyfs`). One switch, BC5_DIRECT_FS_LATE, ON by default (the maintainer, 2026-11-15: replaces W's way; "0" gives W's way back):
  - "FileSystem" stays on the lazy list (V's lazyfs takes it out only while the switch is off);
  - a chunk of a lazy view named "FileSystem" that holds data (SEEK_DATA) and is not imported is imported once it has
    been seen for the delay (BC5_DIRECT_FS_LATE=<s>, 5..3600; "1"/"on" is 30 s), one chunk a pass, passes with such
    an import at least 250 ms apart; the logic is src/bc5/late_import.hpp (copied from this directory, CPU test
    test0421late.cpp);
  - a pass is not skipped as "nothing changed" while a chunk's time has come.
The journal lines are under #ifndef BC5_LEAN. Every edit must match exactly once (ed0419g.File)."""
import os, re, shutil, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "0419-switch-cleanup"))
sys.path.insert(0, HERE)  # on the box ed0419g.py is copied next to this script
from ed0419g import File

root = sys.argv[1]
P = lambda *a: os.path.join(root, "src", *a)

shutil.copyfile(os.path.join(HERE, "late_import.hpp"), P("bc5", "late_import.hpp"))
print("bc5/late_import.hpp: copied")

f = File(P("libs", "bc5LleAgc.cpp"))

f.sub('#include "bc5/anon_sync.hpp" // experiment 0415 (as415)\n',
      '#include "bc5/anon_sync.hpp" // experiment 0415 (as415)\n'
      '#include "bc5/late_import.hpp" // exp 0421 (tag fs421): BC5_DIRECT_FS_LATE\n')

f.sub("static bool direct_lazy_name(const char* name) {\n",
      "static uint64_t fs421_late_ns(); // exp 0421 (tag fs421): BC5_DIRECT_FS_LATE, 0 when off ("0")\n"
      "static bool direct_lazy_name(const char* name) {\n")

# V's lazyfs: `if (!bc5::env_on(<reader>("BC5_DIAG_LAZY_FILESYSTEM"))) {` (the reader is std::getenv in V, may be
# BC5_DIAG_ENV after W's lean rewrite). With the switch on, FileSystem stays in the list.
pat = re.compile(rb'(\t\tif \(!bc5::env_on\([A-Za-z_:]+\("BC5_DIAG_LAZY_FILESYSTEM"\)\))\) \{')
hits = pat.findall(f.b)
assert len(hits) == 1, "lazyfs condition: %d matches" % len(hits)
f.b = pat.sub(rb'\1 && fs421_late_ns() == 0) { // exp 0421: BC5_DIRECT_FS_LATE keeps it lazy, imported late', f.b)
f.n += 1

f.sub("static void direct_sync_one(DState& S, bool force) {\n", r'''// Exp 0421 (tag fs421), BC5_DIRECT_FS_LATE (default ON, 30 s; "0" is build W's way): the GPU read fault of arm n13P4 (fault record
// 20261114-184017) read two written chunks of the lazy heap "FileSystem" 580 s after they were written. Build V/W
// imports the heap by data instead, at the moment of each write, and W's loads gained in-host stalls (exp 0412
// section 102; the link is inferred). With the switch on the heap stays lazy and each written chunk is imported once
// it has been written for the delay, one chunk a pass: no import of it during the load that wrote it.
static uint64_t fs421_late_ns() {
	static const uint64_t ns = [] {
		const uint64_t v = bc5::late_import::delay_of(std::getenv("BC5_DIRECT_FS_LATE"));
#ifndef BC5_LEAN
		if (v != 0)
			std::fprintf(stderr, "[bc5] exp 0421 (tag fs421): BC5_DIRECT_FS_LATE on: \"FileSystem\" stays lazy; a written chunk of it is imported %.0f s after it is first seen, "
			                     "one chunk a pass, passes 250 ms apart\n", static_cast<double>(v) / 1e9);
#endif
		return v;
	}();
	return ns;
}
static bc5::late_import::State g_fs421[2]; // per DState kind
// The data chunks of a late view that no import covers (the by-data walk of direct_sync_one, for one view).
static void fs421_scan(const DState& S, const DView& v, int fd, std::vector<uint64_t>& out) {
	const uint64_t end = v.off + v.size;
	uint64_t       pos = v.off & ~(kDChunk - 1);
	while (pos < end) {
		if (const uint64_t ce = direct_covered_end(S, pos); ce != 0) { pos = ce; continue; }
		const off_t d = lseek(fd, static_cast<off_t>(pos), SEEK_DATA);
		if (d < 0 || static_cast<uint64_t>(d) >= end) break;
		const uint64_t c = static_cast<uint64_t>(d) & ~(kDChunk - 1);
		if (direct_covered_end(S, c) == 0) out.push_back(c);
		pos = c + kDChunk;
	}
}
static void fs421_pick(const DState& S, const std::vector<uint64_t>& written, uint64_t now, std::vector<uint64_t>& need) {
	std::vector<uint64_t> w;
	w.reserve(written.size());
	for (const uint64_t c: written) {
		if (S.failed.count(c) == 0 && c + kDChunk <= S.file_size) w.push_back(c);
	}
	bc5::late_import::Limits L;
	L.delay_ns = fs421_late_ns();
	auto& st = g_fs421[S.kind == 0 ? 0 : 1];
#ifndef BC5_LEAN
	std::vector<std::pair<uint64_t, uint64_t>> first; // the chunks about to be picked, with when they were first seen
	for (const auto& [c, t]: st.seen) first.emplace_back(c, t);
#endif
	const std::vector<uint64_t> got = bc5::late_import::pick(st, std::move(w), now, L);
	for (const uint64_t c: got) need.push_back(c);
#ifndef BC5_LEAN
	static uint64_t lines = 0;
	for (const uint64_t c: got) {
		uint64_t t0 = now;
		for (const auto& [fc, ft]: first) if (fc == c) t0 = ft;
		if (lines++ < 64)
			journal("fs421 late import (exp 0421): %s chunk 0x%" PRIx64 " of \"FileSystem\", seen written %.1f s ago; %" PRIu64 " late chunks so far, %zu waiting\n", S.label, c,
			        static_cast<double>(now - t0) / 1e9, st.imported, st.seen.size() - got.size());
	}
#endif
}

static void direct_sync_one(DState& S, bool force) {
''')

f.sub("\t// 1. chunks to import: data inside a view, and the forced ones\n\tstd::vector<uint64_t> need;\n",
      "\t// 1. chunks to import: data inside a view, and the forced ones\n\tstd::vector<uint64_t> need;\n"
      "\tstd::vector<uint64_t> fs421_written; // exp 0421 (tag fs421): written chunks of \"FileSystem\" while it is lazy\n")

f.sub("\t\tif (v.lazy) continue; // BC5_DIRECT_LAZY_NAMES: only what is forced\n",
      "\t\tif (v.lazy) { // BC5_DIRECT_LAZY_NAMES: only what is forced\n"
      "\t\t\tif (fs421_late_ns() != 0 && v.name == \"FileSystem\") fs421_scan(S, v, fd, fs421_written); // exp 0421: BC5_DIRECT_FS_LATE\n"
      "\t\t\tcontinue;\n"
      "\t\t}\n")

f.sub("\tstd::sort(need.begin(), need.end());\n\tneed.erase(std::unique(need.begin(), need.end()), need.end());\n",
      "\tif (fs421_late_ns() != 0) fs421_pick(S, fs421_written, now, need); // exp 0421 (tag fs421): at most one late chunk a pass\n"
      "\tstd::sort(need.begin(), need.end());\n\tneed.erase(std::unique(need.begin(), need.end()), need.end());\n")

f.sub("S.bos.size() == S.bos_mapped && !merge_due) {\n",
      "S.bos.size() == S.bos_mapped && !merge_due &&\n"
      "\t\t    !bc5::late_import::due(g_fs421[S.kind == 0 ? 0 : 1], now)) { // exp 0421: a late chunk whose time has come\n")

f.gone("BC5_DIRECT_FS_LATE_")
f.save()
