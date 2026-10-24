#!/usr/bin/env python3
# BC5 experiment 0265: the ring order's stale pending writes (exp 0255, F322), as a private build on top of exp 0260's
# probe (bc5LleAgc.probe.cpp, md5 daca24cc: the integrated tree's 67859271 plus patch0260.py). Switch
# BC5_DIRECT_RING_ORDER_STALE, off when unset (D16):
#   count  journal each time ring_will_satisfy() would answer from a stale pending write, and change nothing else
#          (GPU-neutral: the same waits are kept);
#   skip   also do not count such a write: the wait is then not kept for the GPU on it (served on the CPU, held or
#          given up, as when no write is pending).
# Stale: the label has changed since the write was registered (register_label_writes, right after the submission) while
# the wait still does not hold. Either the write's job has run and the title has re-armed the label since, or the label
# was re-armed before the write ran; either way this write will not end the wait, and a wait kept for the GPU on it
# waits for a later writer, which may sit behind the other stuck buffer (F322's two-ring timeouts). Skipping a keep is
# always safe: the wait falls back to the paths that do not keep it. No backend change and no fence query: the label's
# value at registration is read once per registered write, the value now once per positive answer.
# Each anchor must occur exactly once.
# usage: patch0265.py <bc5LleAgc.probe.cpp, md5 daca24cc> <out .cpp> <out .diff>   (the input is only read)
import difflib, hashlib, sys

IN_MD5 = 'daca24cca83fa6e8ec1778b3422470db'

EDITS = [
    # 1. The registered write remembers its label's value at registration.
    ('''struct PendingLabelWrite {
\tuint64_t label;
\tuint64_t value;
\tuint64_t seq;
\tbool     is64;
\tint      ring  = bc5::direct::kGfxRing;
\tuint64_t order = 0;
};''',
     '''struct PendingLabelWrite {
\tuint64_t label;
\tuint64_t value;
\tuint64_t seq;
\tbool     is64;
\tint      ring      = bc5::direct::kGfxRing;
\tuint64_t order     = 0;
\tuint64_t before    = 0;     // experiment 0265: the label's value when the write was registered
\tbool     before_ok = false; // ... read (BC5_DIRECT_RING_ORDER_STALE set and the label mapped)
};'''),
    # 2. register_label_writes reads it, before the registry lock.
    ('''\tif (found.empty()) return;
\tstd::lock_guard lk(g_plw_mutex);
\tstatic uint64_t order = 0;''',
     '''\tif (found.empty()) return;
\tif (ro_stale_mode() != 0 && g_dev) { // experiment 0265: each label as it is now, right after the submission
\t\tconst auto pm = g_dev->sorted_mappings();
\t\tfor (auto& w: found) {
\t\t\tif (!covered_sorted(*pm, w.label, w.is64 ? 8 : 4)) continue;
\t\t\tw.before    = w.is64 ? *reinterpret_cast<const volatile uint64_t*>(w.label) : *reinterpret_cast<const volatile uint32_t*>(w.label);
\t\t\tw.before_ok = true;
\t\t}
\t}
\tstd::lock_guard lk(g_plw_mutex);
\tstatic uint64_t order = 0;'''),
    # 3. The switch and the check, before register_label_writes (which uses the switch).
    ('''static void register_label_writes(const uint32_t* ib, uint32_t num_dwords, const std::vector<uint32_t>& executed, uint64_t seq, int ring) {''',
     '''// Experiment 0265 (BC5_DIRECT_RING_ORDER_STALE=count|skip; off by default, D16): a pending write whose label has changed
// since the write was registered, while the wait still does not hold, will not end the wait: its job has run and the
// title has re-armed the label since (or re-armed it before the write ran). The ring order would keep the wait for the
// GPU on it, and the wait then waits for a later writer (exp 0255, F322: the two-ring timeouts' hand-off labels).
// count: journal it; skip: also do not count the write, so the wait is not kept for the GPU on it.
static int ro_stale_mode() {
\tstatic const int v = [] {
\t\tconst char* e = std::getenv("BC5_DIRECT_RING_ORDER_STALE");
\t\tif (e == nullptr) return 0;
\t\tif (std::strcmp(e, "skip") == 0) return 2;
\t\treturn std::strcmp(e, "count") == 0 ? 1 : 0;
\t}();
\treturn v;
}
static std::atomic<uint64_t> g_ro_checked {0}, g_ro_stale {0};
// Caller holds g_plw_mutex; a: the waited label; ring: the waiting job's ring. True only when skip drops the write.
static bool ro_stale(const PendingLabelWrite& w, uint64_t a, int ring) {
\tif (ro_stale_mode() == 0 || !w.before_ok) return false;
\tg_ro_checked++;
\tconst uint64_t now = w.is64 ? *reinterpret_cast<const volatile uint64_t*>(a) : *reinterpret_cast<const volatile uint32_t*>(a);
\tif (now == w.before) return false;
\tconst uint64_t n = ++g_ro_stale;
\tif (n <= 200 || (n & 0xffu) == 0)
\t\tjournal("ring order: STALE pending write on 0x%" PRIx64 " (value 0x%" PRIx64 ", ring %d, seq %" PRIu64 "): the label was 0x%" PRIx64 " at registration, 0x%" PRIx64 " now; the wait (ring %d) %s (%" PRIu64 " stale of %" PRIu64 " checked)\\n",
\t\t        a, w.value, w.ring, w.seq, w.before, now, ring, ro_stale_mode() == 2 ? "not kept for it" : "kept as before (count only)", n, g_ro_checked.load());
\treturn ro_stale_mode() == 2;
}

static void register_label_writes(const uint32_t* ib, uint32_t num_dwords, const std::vector<uint32_t>& executed, uint64_t seq, int ring) {'''),
    # 4. ring_will_satisfy: the answer computed, then the check.
    ('''\tif (is64) {
\t\tif (!last->is64) return false;
\t\tconst uint64_t ref = p[4] | (static_cast<uint64_t>(p[5]) << 32u), mask = p[6] | (static_cast<uint64_t>(p[7]) << 32u);
\t\tconst uint64_t vm = last->value & mask, rm = ref & mask;
\t\tswitch (function) {
\t\t\tcase 1: return vm < rm;
\t\t\tcase 2: return vm <= rm;
\t\t\tcase 3: return vm == rm;
\t\t\tcase 4: return vm != rm;
\t\t\tcase 5: return vm >= rm;
\t\t\tcase 6: return vm > rm;
\t\t\tdefault: return false;
\t\t}
\t}
\treturn SoftCp::compare(function, static_cast<uint32_t>(last->value), p[5], p[4]);
}''',
     '''\tbool sat = false;
\tif (is64) {
\t\tif (!last->is64) return false;
\t\tconst uint64_t ref = p[4] | (static_cast<uint64_t>(p[5]) << 32u), mask = p[6] | (static_cast<uint64_t>(p[7]) << 32u);
\t\tconst uint64_t vm = last->value & mask, rm = ref & mask;
\t\tswitch (function) {
\t\t\tcase 1: sat = vm < rm; break;
\t\t\tcase 2: sat = vm <= rm; break;
\t\t\tcase 3: sat = vm == rm; break;
\t\t\tcase 4: sat = vm != rm; break;
\t\t\tcase 5: sat = vm >= rm; break;
\t\t\tcase 6: sat = vm > rm; break;
\t\t\tdefault: sat = false; break;
\t\t}
\t} else {
\t\tsat = SoftCp::compare(function, static_cast<uint32_t>(last->value), p[5], p[4]);
\t}
\treturn sat && !ro_stale(*last, a, ring); // experiment 0265
}'''),
]


def main():
    src_path, out_path, diff_path = sys.argv[1:4]
    raw = open(src_path, 'rb').read()
    md5 = hashlib.md5(raw).hexdigest()
    if md5 != IN_MD5:
        sys.exit(f"{src_path}: md5 {md5}, expected {IN_MD5} (exp 0260's bc5LleAgc.probe.cpp)")
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
