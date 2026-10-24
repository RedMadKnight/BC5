#!/usr/bin/env python3
# BC5 experiment 0260: the timeout probe (BC5_DIRECT_TIMEOUT_PROBE=1, experiment 0160) made to catch a stuck compute
# buffer through a machine-down (exp 0259: S6N's last packet was not recorded). A one-file change of the shared tree's
# bc5LleAgc.cpp after the CS-prefix integration (md5 67859271), for a private test binary; the switch stays as it is
# (off unless set), and nothing changes without it.
#   - The dump ib-timeout-*.bin is fflush'ed and fsync'ed before it is closed (it was lost in F260 and F262).
#   - For each WAIT_REG_MEM (0x3C) and WAIT_REG_MEM64 (0x93) of the timed-out buffer: its offset, label (or register),
#     function, reference, mask, engine, the label's value now and whether that meets it, and "ran" (kept for the GPU)
#     or "DROPPED" (served on the CPU). Fields as wait_satisfied() reads them; MEM_SPACE bits 5:4 and PFP bit 8 from
#     Mesa src/amd/common/sid.h @ 0866ae7 (lines 90-95).
#   - For each label write (RELEASE_MEM 0x49, EVENT_WRITE_EOP 0x47, WRITE_DATA 0x37 to memory): the address, data
#     select, value and the address's value now. Fields as register_label_writes() reads them.
#   - For each dispatch (0x15 / 0x16): its program (COMPUTE_PGM_LO/HI as the probe's state tracking has them, or "not
#     set in this buffer").
#   - At most 200 lines of each kind per buffer, then a count line; then the journal is flushed and fsync'ed, so the
#     lines reach the disk and a stream of the journal before the machine goes down.
# The pending-write registry is not printed: the completion thread clears it (forget_label_writes, timed out) before
# the probe runs.
# Each anchor must occur exactly once.
# usage: patch0260.py <shared bc5LleAgc.cpp, md5 67859271> <out .cpp> <out .diff>   (the input is only read)
import difflib, hashlib, sys

IN_MD5 = '67859271bf3ec04c6c2bac20e034688e'

EDITS = [
    # 1. The comment.
    ('''// the indirect arguments (first draws) and the first index dwords.
static void timeout_probe(''',
     '''// the indirect arguments (first draws) and the first index dwords.
// Experiment 0260: the dump is synced; each WAIT_REG_MEM(64) of the buffer (offset, label or register, function,
// reference, mask, engine, the label's value now and whether it meets the wait, ran or DROPPED), each label write
// (RELEASE_MEM, EVENT_WRITE_EOP, WRITE_DATA to memory: address, data select, value, the address's value now) and each
// dispatch's program are journaled, 200 lines of each at most, with a count; then the journal is synced. A stuck
// compute buffer then shows what it waits on even when the machine goes down (exp 0259: S6N's was not recorded).
static void timeout_probe('''),
    # 2. The dump synced.
    ('''\t\tif (FILE* f = std::fopen(name, "wb"); f != nullptr) { std::fwrite(sub_ib, sizeof(uint32_t), sub_n, f); std::fclose(f); }
''',
     '''\t\tif (FILE* f = std::fopen(name, "wb"); f != nullptr) {
\t\t\tstd::fwrite(sub_ib, sizeof(uint32_t), sub_n, f);
\t\t\tstd::fflush(f); // experiment 0260: a machine-down follows a timeout often enough
\t\t\tfsync(fileno(f));
\t\t\tstd::fclose(f);
\t\t}
'''),
    # 3. The counters, before the packet loop.
    ('''g.op, g.offset, g.slot, v[0], v[1], v[2], v[3], v[4], v[5], v[6], v[7]);
\t\t\t}
\t\t}
\t\tfor (uint32_t q = 0; q < sub_n;) {
''',
     '''g.op, g.offset, g.slot, v[0], v[1], v[2], v[3], v[4], v[5], v[6], v[7]);
\t\t\t}
\t\t}
\t\tuint32_t n_waits = 0, n_kept = 0, n_writes = 0, n_disp = 0; // experiment 0260
\t\tfor (uint32_t q = 0; q < sub_n;) {
'''),
    # 4. Waits, label writes and dispatches, after the packet's ran/DROPPED mark.
    ('''\t\t\t\tconst char*    ex = ran == nullptr ? "" : (std::binary_search(ran->begin(), ran->end(), q) ? " ran" : " DROPPED");
''',
     '''\t\t\t\tconst char*    ex = ran == nullptr ? "" : (std::binary_search(ran->begin(), ran->end(), q) ? " ran" : " DROPPED");
\t\t\t\tif ((op == 0x3c && len >= 7) || (op == 0x93 && len >= 9)) { // experiment 0260: the waits
\t\t\t\t\tconst bool     is64 = op == 0x93;
\t\t\t\t\tconst uint32_t fn   = sub_ib[q + 1] & 7u;
\t\t\t\t\tconst bool     mem  = ((sub_ib[q + 1] >> 4u) & 3u) != 0;
\t\t\t\t\tconst uint64_t a    = (sub_ib[q + 2] & ~3u) | (static_cast<uint64_t>(sub_ib[q + 3] & 0xffffu) << 32u);
\t\t\t\t\tconst uint64_t ref  = is64 ? sub_ib[q + 4] | (static_cast<uint64_t>(sub_ib[q + 5]) << 32u) : sub_ib[q + 4];
\t\t\t\t\tconst uint64_t msk  = is64 ? sub_ib[q + 6] | (static_cast<uint64_t>(sub_ib[q + 7]) << 32u) : sub_ib[q + 5];
\t\t\t\t\tchar           now[64] = "not read";
\t\t\t\t\tif (mem && a != 0 && covered_sorted(*pm, a, is64 ? 8 : 4)) {
\t\t\t\t\t\tconst uint64_t v  = is64 ? *reinterpret_cast<const volatile uint64_t*>(a) : *reinterpret_cast<const volatile uint32_t*>(a);
\t\t\t\t\t\tconst uint64_t vm = v & msk, rm = ref & msk;
\t\t\t\t\t\tconst bool met = fn == 0 || (fn == 1 && vm < rm) || (fn == 2 && vm <= rm) || (fn == 3 && vm == rm) || (fn == 4 && vm != rm) || (fn == 5 && vm >= rm) || (fn == 6 && vm > rm);
\t\t\t\t\t\tstd::snprintf(now, sizeof(now), "0x%" PRIx64 " (%s)", v, met ? "met" : "NOT met");
\t\t\t\t\t}
\t\t\t\t\tif (ran != nullptr && std::binary_search(ran->begin(), ran->end(), q)) n_kept++;
\t\t\t\t\tif (n_waits++ < 200)
\t\t\t\t\t\tjournal("timeout probe: wait op %02x at %u: %s 0x%" PRIx64 " function %u reference 0x%" PRIx64 " mask 0x%" PRIx64 " %s; now %s%s\\n", op, q, mem ? "label" : "register",
\t\t\t\t\t\t        mem ? a : static_cast<uint64_t>(sub_ib[q + 2]), fn, ref, msk, ((sub_ib[q + 1] >> 8u) & 1u) != 0 ? "pfp" : "me", now, ex);
\t\t\t\t} else if ((op == 0x49 && len >= 8) || (op == 0x47 && len >= 6) || (op == 0x37 && len >= 5)) { // experiment 0260: the label writes
\t\t\t\t\tconst uint32_t* w   = sub_ib + q;
\t\t\t\t\tconst int       lo  = op == 0x49 ? 3 : 2;
\t\t\t\t\tconst uint32_t  sel = op == 0x49 ? w[2] >> 29u : (op == 0x47 ? w[3] >> 29u : (w[1] >> 8u) & 0xfu); // WRITE_DATA: its DST_SEL
\t\t\t\t\tconst uint32_t  dk  = op == 0x49 ? 5u : 4u;
\t\t\t\t\tconst uint64_t  a   = (w[lo] & ~3u) | (static_cast<uint64_t>(w[lo + 1] & 0xffffu) << 32u);
\t\t\t\t\tif (op != 0x37 || sel == 1 || sel == 2 || sel == 5) {
\t\t\t\t\t\tconst bool     two = op == 0x37 ? len >= 6 : sel != 1; // 64-bit data: WRITE_DATA with two dwords, RELEASE_MEM / EOP unless DATA_SEL 1
\t\t\t\t\t\tconst uint64_t v   = w[dk] | (two ? static_cast<uint64_t>(w[dk + 1]) << 32u : 0ull);
\t\t\t\t\t\tchar           now[40] = "not read";
\t\t\t\t\t\tif (a != 0 && covered_sorted(*pm, a, 8)) std::snprintf(now, sizeof(now), "0x%" PRIx64, *reinterpret_cast<const volatile uint64_t*>(a));
\t\t\t\t\t\tif (n_writes++ < 200)
\t\t\t\t\t\t\tjournal("timeout probe: write op %02x at %u: 0x%" PRIx64 " select %u value 0x%" PRIx64 " (packet %u dwords); now %s%s\\n", op, q, a, sel, v, len, now, ex);
\t\t\t\t\t}
\t\t\t\t} else if (op == 0x15 || op == 0x16) { // experiment 0260: the dispatches' programs
\t\t\t\t\tconst uint32_t pl = g(st_sh, 0x20cu), ph = g(st_sh, 0x20du);
\t\t\t\t\tif (n_disp++ < 200)
\t\t\t\t\t\tjournal("timeout probe: dispatch op %02x at %u: program %s0x%" PRIx64 "%s\\n", op, q, pl == 0xffffffffu ? "not set in this buffer, " : "",
\t\t\t\t\t\t        (static_cast<uint64_t>(pl) | (static_cast<uint64_t>(ph & 0xffu) << 32u)) << 8u, ex);
\t\t\t\t}
'''),
    # 5. The count line and the journal synced, at the end of the probe.
    ('''\t\t\tq += len;
\t\t}
\t}
}
// Experiment 0046: a timestamp scale k multiplies''',
     '''\t\t\tq += len;
\t\t}
\t\tjournal("timeout probe: %s #%" PRIu64 " %u dwords: %u waits (%u kept for the GPU), %u label writes, %u dispatches\\n", kind, n, sub_n, n_waits, n_kept, n_writes, n_disp);
\t\tif (g_journal_min) { // experiment 0260: the probe's lines on the disk (and in a stream of the journal) before a machine-down
\t\t\tif (FILE* jf = journal_min_file(true); jf != nullptr) fsync(fileno(jf));
\t\t}
\t}
}
// Experiment 0046: a timestamp scale k multiplies'''),
]


def main():
    src_path, out_path, diff_path = sys.argv[1:4]
    raw = open(src_path, 'rb').read()
    md5 = hashlib.md5(raw).hexdigest()
    if md5 != IN_MD5:
        sys.exit(f'{src_path}: md5 {md5}, expected {IN_MD5} (the tree after the CS-prefix integration)')
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
