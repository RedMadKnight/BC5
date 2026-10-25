#!/usr/bin/env python3
# BC5 experiment 0288: BC5_DIRECT_BREAKDOWN_AT=<seconds> — one per-heap breakdown ("<label> by name (at): ..." and a line
# per heap name: views, MiB reserved, with data, imported) for each memfd, run once, the first time the direct path syncs
# that memfd <seconds> or more after its first sync. The existing BC5_DIRECT_BREAKDOWN=1 runs the same pass at every
# 512 MiB of growth, 25-80 s a pass while the second title loads (patch 0001, direct_sync_one); one pass near the end of a
# scripted run costs that once, off the critical part. Off by default; a diagnostic switch (BC5_DIAG_ENV: null in the lean
# build). Applied to a COPY of the shared tree's src/libs/bc5LleAgc.cpp; the shared tree and builds are not written.
# usage: patch0288.py <bc5LleAgc.cpp in> <bc5LleAgc.cpp out>
import sys

src, dst = sys.argv[1], sys.argv[2]
s = open(src, encoding="utf-8").read()


def sub(old, new, count=1):
    global s
    n = s.count(old)
    if n != count:
        sys.exit("anchor found %d times, expected %d: %r" % (n, count, old[:80]))
    s = s.replace(old, new)


OLD = (
    '\tstatic const bool breakdown = BC5_DIAG_ENV("BC5_DIRECT_BREAKDOWN") != nullptr;\n'
    "\tif (S.bytes >= S.reported + (512ull << 20u)) {\n"
    "\t\tS.reported = S.bytes;\n"
    '\t\tif (breakdown) direct_breakdown_one(S, "growth", 0);\n'
    "\t}\n"
    "}\n"
)
NEW = (
    '\tstatic const bool breakdown = BC5_DIAG_ENV("BC5_DIRECT_BREAKDOWN") != nullptr;\n'
    "\tif (S.bytes >= S.reported + (512ull << 20u)) {\n"
    "\t\tS.reported = S.bytes;\n"
    '\t\tif (breakdown) direct_breakdown_one(S, "growth", 0);\n'
    "\t}\n"
    "\t// Experiment 0288: BC5_DIRECT_BREAKDOWN_AT=<seconds> runs the breakdown once per memfd, at the first sync that\n"
    "\t// many seconds after the memfd's first sync (the per-heap table near the end of a scripted run, one pass).\n"
    "\t{\n"
    '\t\tstatic const double at_s = BC5_DIAG_ENV("BC5_DIRECT_BREAKDOWN_AT") != nullptr ? std::strtod(BC5_DIAG_ENV("BC5_DIRECT_BREAKDOWN_AT"), nullptr) : -1.0;\n'
    "\t\tif (at_s >= 0.0) {\n"
    "\t\t\tstatic uint64_t first_ns[2] = {0, 0};\n"
    "\t\t\tstatic bool     done[2]     = {false, false};\n"
    "\t\t\tconst int       k           = S.kind == 0 ? 0 : 1;\n"
    "\t\t\tif (first_ns[k] == 0) first_ns[k] = now;\n"
    "\t\t\tif (!done[k] && static_cast<double>(now - first_ns[k]) / 1e9 >= at_s) {\n"
    "\t\t\t\tdone[k] = true;\n"
    '\t\t\t\tjournal("%s breakdown at %.1f s after the first sync (BC5_DIRECT_BREAKDOWN_AT=%.0f)\\n", S.label, static_cast<double>(now - first_ns[k]) / 1e9, at_s);\n'
    '\t\t\t\tdirect_breakdown_one(S, "at", 0);\n'
    "\t\t\t}\n"
    "\t\t}\n"
    "\t}\n"
    "}\n"
)
sub(OLD, NEW)

# BC5_DIRECT_BREAKDOWN_NODATA=1: the "with data" column (SEEK_DATA/SEEK_HOLE over every view of the memfd) is skipped.
# Run M1 showed the walk no longer ends in a useful time: 22,000 views over 12 GB of pinned pages held the game thread for
# more than 180 s (3 frames in the run's fifth minute) and the table never came. For the eager heaps the column equals
# "imported" by construction (udmabuf allocates the pages it pins), so reserved and imported, both from the view and BO
# lists, answer the per-heap question in milliseconds.
OLD2 = (
    "\t\tuint64_t       data = 0, imported = 0;\n"
    "\t\tfor (uint64_t pos = v.off; pos < end;) {\n"
    "\t\t\tconst off_t d = lseek(fd, static_cast<off_t>(pos), SEEK_DATA);\n"
)
NEW2 = (
    "\t\tuint64_t       data = 0, imported = 0;\n"
    '\t\tstatic const bool nodata = BC5_DIAG_ENV("BC5_DIRECT_BREAKDOWN_NODATA") != nullptr; // experiment 0288\n'
    "\t\tfor (uint64_t pos = nodata ? end : v.off; pos < end;) {\n"
    "\t\t\tconst off_t d = lseek(fd, static_cast<off_t>(pos), SEEK_DATA);\n"
)
sub(OLD2, NEW2)
open(dst, "w", encoding="utf-8").write(s)
print("patched: BC5_DIRECT_BREAKDOWN_AT and BC5_DIRECT_BREAKDOWN_NODATA ->", dst)
