#!/usr/bin/env python3
# BC5 experiment 0272 (probe v2 of exp 0260's timeout probe): the timeout probe journals each dispatch's group counts, so that a compute chain that
# hangs in an indirect dispatch (exp 0265, F332: the title's "Ray Tracing Update" chain, 286 indirect dispatches of
# 0x909936c00 and 153 of 0x909939900 in the stall window) shows the grids those dispatches read. A one-file change of
# the shared tree's bc5LleAgc.cpp after exp 0260's integration (md5 daca24cc), inside timeout_probe() only: its counters,
# its dispatch line (exp 0260) and its count line. It acts only after a fence timeout, with BC5_DIRECT_TIMEOUT_PROBE.
#   - DISPATCH_DIRECT (0x15): the counts from the packet, dwords 1-3.
#   - DISPATCH_INDIRECT (0x16): three dwords in memory as the GPU left them, at the address the packet names. Two forms,
#     as this file's mec_expand_ib (experiment 0038) reads and writes them: the compute-queue form of 4 dwords (address
#     low/high in dwords 1-2), and the graphics form of 3 dwords (an offset in dword 1 from the SET_BASE index 1 base,
#     which the probe already tracks for indirect draws).
#   - Every indirect dispatch is journaled (up to 2,000 a buffer, the direct ones up to 200 as before). The count line
#     gives the indirect count and the largest grid (groups) with its offset.
# Each anchor must occur exactly once.
# usage: patch0272.py <shared bc5LleAgc.cpp, md5 daca24cc> <out .cpp> <out .diff>   (the input is only read)
import difflib, hashlib, sys

IN_MD5 = 'daca24cca83fa6e8ec1778b3422470db'

EDITS = [
    # 1. The counters.
    ('''\t\tuint32_t n_waits = 0, n_kept = 0, n_writes = 0, n_disp = 0; // experiment 0260
''',
     '''\t\tuint32_t n_waits = 0, n_kept = 0, n_writes = 0, n_disp = 0; // experiment 0260
\t\tuint32_t n_ind = 0, max_at = 0;                              // experiment 0272: indirect dispatches, the largest grid's offset
\t\tuint64_t max_groups = 0;
'''),
    # 2. The dispatch line, with the group counts.
    ('''\t\t\t\t} else if (op == 0x15 || op == 0x16) { // experiment 0260: the dispatches' programs
\t\t\t\t\tconst uint32_t pl = g(st_sh, 0x20cu), ph = g(st_sh, 0x20du);
\t\t\t\t\tif (n_disp++ < 200)
\t\t\t\t\t\tjournal("timeout probe: dispatch op %02x at %u: program %s0x%" PRIx64 "%s\\n", op, q, pl == 0xffffffffu ? "not set in this buffer, " : "",
\t\t\t\t\t\t        (static_cast<uint64_t>(pl) | (static_cast<uint64_t>(ph & 0xffu) << 32u)) << 8u, ex);
\t\t\t\t}
''',
     '''\t\t\t\t} else if (op == 0x15 || op == 0x16) { // experiment 0260: the dispatches' programs; experiment 0272: and their group counts
\t\t\t\t\tconst uint32_t pl = g(st_sh, 0x20cu), ph = g(st_sh, 0x20du);
\t\t\t\t\tuint32_t       gx = 0, gy = 0, gz = 0;
\t\t\t\t\tbool           have = false;
\t\t\t\t\tchar           where[64] = "";
\t\t\t\t\tif (op == 0x15 && len >= 4) {
\t\t\t\t\t\tgx = sub_ib[q + 1], gy = sub_ib[q + 2], gz = sub_ib[q + 3], have = true;
\t\t\t\t\t} else if (op == 0x16 && len >= 3) { // the compute-queue form (4 dwords: the address) or the SET_BASE form (3: an offset), as mec_expand_ib has them
\t\t\t\t\t\tconst uint64_t a = len >= 4 ? (sub_ib[q + 1] & ~3u) | (static_cast<uint64_t>(sub_ib[q + 2] & 0xffffu) << 32u) : b1 + sub_ib[q + 1];
\t\t\t\t\t\tif ((len >= 4 || b1 != 0) && covered_sorted(*pm, a, 12)) {
\t\t\t\t\t\t\tconst auto* t = reinterpret_cast<const volatile uint32_t*>(a);
\t\t\t\t\t\t\tgx = t[0], gy = t[1], gz = t[2], have = true;
\t\t\t\t\t\t}
\t\t\t\t\t\tstd::snprintf(where, sizeof(where), " (arguments at 0x%" PRIx64 "%s)", a, have ? "" : ", not mapped");
\t\t\t\t\t}
\t\t\t\t\tconst uint64_t groups = static_cast<uint64_t>(gx) * gy * gz;
\t\t\t\t\tif (have && groups > max_groups) max_groups = groups, max_at = q;
\t\t\t\t\tif (op == 0x16 ? n_ind++ < 2000 : n_disp - n_ind < 200) {
\t\t\t\t\t\tchar grid[64] = "?";
\t\t\t\t\t\tif (have) std::snprintf(grid, sizeof(grid), "%u x %u x %u", gx, gy, gz);
\t\t\t\t\t\tjournal("timeout probe: dispatch op %02x at %u: program %s0x%" PRIx64 ", groups %s%s%s\\n", op, q, pl == 0xffffffffu ? "not set in this buffer, " : "",
\t\t\t\t\t\t        (static_cast<uint64_t>(pl) | (static_cast<uint64_t>(ph & 0xffu) << 32u)) << 8u, grid, where, ex);
\t\t\t\t\t}
\t\t\t\t\tn_disp++;
\t\t\t\t}
'''),
    # 3. The count line.
    ('''\t\tjournal("timeout probe: %s #%" PRIu64 " %u dwords: %u waits (%u kept for the GPU), %u label writes, %u dispatches\\n", kind, n, sub_n, n_waits, n_kept, n_writes, n_disp);
''',
     '''\t\tjournal("timeout probe: %s #%" PRIu64 " %u dwords: %u waits (%u kept for the GPU), %u label writes, %u dispatches (%u indirect; the largest grid %" PRIu64 " groups, at %u)\\n", kind, n, sub_n,
\t\t        n_waits, n_kept, n_writes, n_disp, n_ind, max_groups, max_at);
'''),
    # 4. The comment.
    ('''// compute buffer then shows what it waits on even when the machine goes down (exp 0259: S6N's was not recorded).
''',
     '''// compute buffer then shows what it waits on even when the machine goes down (exp 0259: S6N's was not recorded).
// Experiment 0272 (exp 0265, F332: a compute chain hung inside its dispatches): each dispatch's group counts, from the packet
// or, for DISPATCH_INDIRECT, from memory as the GPU left it; every indirect one is journaled, with the largest grid.
'''),
]


def main():
    src_path, out_path, diff_path = sys.argv[1:4]
    raw = open(src_path, 'rb').read()
    md5 = hashlib.md5(raw).hexdigest()
    if md5 != IN_MD5:
        sys.exit(f"{src_path}: md5 {md5}, expected {IN_MD5} (the shared tree after exp 0260's integration)")
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
