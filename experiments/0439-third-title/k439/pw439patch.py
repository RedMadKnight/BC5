# BC5 exp 0439 (tag pw439): patch the private backend copy new/be/direct.cpp (run on the box, in k439/).
# The nested-piece filter call gets the root's FilterOptions (direct.cpp `nested_opt = fopt`), so the root's
# drop_offsets and keep_wait_offsets (root dword offsets) are applied by offset to every piece, and a piece's
# WAIT_REG_MEM on a label the same piece does not write is dropped (self_waits_only): in a frame made of one chain no
# cross-queue wait reaches the GPU, and the host's wait handling never sees them (the sweep of 11-22, README 49).
# BC5_0439_PIECE_WAITS=1: the root's offset lists are cleared for pieces; =2: also self_waits_only off for pieces (the
# GPU waits as the console's does; deadlocked at once on the stock kernel, F916); =3 (11-23, after F916): mode 1, and
# a piece's open wait is kept only when the host proves it cannot take part in a cycle (pw0439.hpp: memory meets it, or
# the last pending write of a job already in the kernel does; the host's answer through the weak hook
# bc5_pw439_piece_wait, defined by the unit's mkpw439.py; no hook = every open wait dropped, as today). Off unless
# "1", "2" or "3". A counter line every 4096 pieces; mode 3's decisions are counted for the unit (bc5_pw439_counts).
# The FilterOptions layout (the host's ABI) is unchanged: mode 3 only fills nested_opt.keep_wait_offsets.
import sys

p = sys.argv[1] if len(sys.argv) > 1 else 'new/be/direct.cpp'
s = open(p, encoding='utf-8', newline='').read()


def rep(tag, a, b):
    global s
    assert s.count(a) == 1, (tag, s.count(a))
    s = s.replace(a, b)


rep('include', '#include "bc5/ds0439.hpp" // exp 0439 (tag ds439)\n', '''#include "bc5/ds0439.hpp" // exp 0439 (tag ds439)
#include "bc5/pw0439.hpp" // exp 0439 (tag pw439, mode 3)
#include <atomic> // exp 0439 (tag pw439, mode 3): the counts below come before the file's own system includes
// exp 0439 (tag pw439, mode 3): the host's answer for one open piece wait (bc5::pw439::Decision), and its note of each
// decision (the unit prints dropped labels once); weak: a host without them drops every open wait, as today.
extern "C" int bc5_pw439_piece_wait(const std::uint32_t *pkt, int is64, int ring) __attribute__((weak));
extern "C" void bc5_pw439_piece_note(std::uint64_t label, int decision, int ring) __attribute__((weak));
static std::atomic<std::uint64_t> g_pw439_counts[bc5::pw439::kCount] = {}; // exp 0439 (tag pw439, mode 3)
extern "C" void bc5_pw439_counts(std::uint64_t *out) { // exp 0439 (tag pw439, mode 3): totals since the start
    for (int k = 0; k < bc5::pw439::kCount; ++k) out[k] = g_pw439_counts[k].load(std::memory_order_relaxed);
}
''')

rep('job', '    for (std::size_t i = pro; i < pro_padded; ++i) dst[i] = policy::kNop;\n',
    '''    for (std::size_t i = pro; i < pro_padded; ++i) dst[i] = policy::kNop;
    std::vector<std::uint64_t> pw3_job; // exp 0439 (tag pw439, mode 3): every label this job writes, sorted
    bool pw3_job_done = false;
''')

rep('loop', '''        policy::FilterOptions nested_opt = fopt;
        nested_opt.stat_sample_va = 0;
        policy::filter(policy::Policy::builtin(), std::span<const std::uint32_t>(pc.src, pc.n),
                       std::span<std::uint32_t>(dst + pc.off, pc.n), nested_opt, st);
''', '''        policy::FilterOptions nested_opt = fopt;
        nested_opt.stat_sample_va = 0;
        static const int pw439 = [] { // exp 0439 (tag pw439)
            const char *e = std::getenv("BC5_0439_PIECE_WAITS");
            const int v = e != nullptr && e[0] >= '1' && e[0] <= '3' && e[1] == 0 ? e[0] - '0' : 0;
            std::fprintf(stderr, "[bc5] exp 0439 (tag pw439): piece filter options %s%s\\n",
                         v == 0 ? "the root's (off)" : v == 1 ? "without the root's offset lists" : v == 2 ? "without the root's offset lists, memory waits kept"
                                                                                                 : "without the root's offset lists, open waits kept when a submitted writer or memory proves them (mode 3)",
                         v == 3 && bc5_pw439_piece_wait == nullptr ? "; NO host hook: every open wait dropped" : "");
            return v;
        }();
        if (pw439 >= 1) {
            nested_opt.drop_offsets.clear();
            nested_opt.keep_wait_offsets.clear();
        }
        if (pw439 == 2) nested_opt.self_waits_only = false;
        if (pw439 == 3) { // exp 0439 (tag pw439, mode 3)
            if (!pw3_job_done) {
                for (const Piece &q : pieces) bc5::pw439::labels_written(std::span<const std::uint32_t>(q.src, q.n), pw3_job);
                std::sort(pw3_job.begin(), pw3_job.end());
                pw3_job_done = true;
            }
            std::uint64_t c3[bc5::pw439::kCount] = {};
            bc5::pw439::decide(
                std::span<const std::uint32_t>(pc.src, pc.n), pw3_job,
                [&](const std::uint32_t *pk, bool is64) { return bc5_pw439_piece_wait != nullptr ? bc5_pw439_piece_wait(pk, is64 ? 1 : 0, ring) : 0; },
                [&](std::uint64_t label, int d) {
                    if (bc5_pw439_piece_note != nullptr) bc5_pw439_piece_note(label, d, ring);
                },
                nested_opt.keep_wait_offsets, c3);
            for (int c = 0; c < bc5::pw439::kCount; ++c)
                if (c3[c] != 0) g_pw439_counts[c].fetch_add(c3[c], std::memory_order_relaxed);
        }
        policy::filter(policy::Policy::builtin(), std::span<const std::uint32_t>(pc.src, pc.n),
                       std::span<std::uint32_t>(dst + pc.off, pc.n), nested_opt, st);
        { // exp 0439 (tag pw439): piece waits dropped as unsatisfiable, root-list hits in pieces
            static std::atomic<std::uint64_t> pw_n{0}, pw_drop{0}, pw_kept{0}, pw_off{0};
            pw_drop += st.unsatisfiable_wait_drops;
            pw_kept += st.ring_ordered_waits;
            pw_off += st.offset_drops;
            if ((pw_n++ & 0xfffu) == 0)
                std::fprintf(stderr, "[bc5] exp 0439 (tag pw439): %llu pieces filtered: waits dropped %llu, kept by a root offset or mode 3 %llu, packets dropped by a root offset %llu (mode %d)\\n",
                             static_cast<unsigned long long>(pw_n.load()), static_cast<unsigned long long>(pw_drop.load()),
                             static_cast<unsigned long long>(pw_kept.load()), static_cast<unsigned long long>(pw_off.load()), pw439);
        }
''')
open(p, 'w', encoding='utf-8', newline='').write(s)
print('pw439: patched', p)
