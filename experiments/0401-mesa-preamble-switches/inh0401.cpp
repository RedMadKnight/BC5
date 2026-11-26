// BC5 experiment 0401 series e3: the CPU test of inherit_scan and of the memory line's parsing, compiled from
// inherit_scan.inc and memline_parse.inc, the exact texts mkunit0401.py --inherit3 puts into the unit. Codex's case A -> B
// first; his second review's cases (a program write voided by a later IB2 or an unreadable table; a missing file or key
// read as "unknown", never 0) after. Built and run on the box by box0401.sh build (clang++ in the container, -Werror);
// prints "inh0401: N of N cases; end" and exits 0 only then. No GPU. (The draft of series e3, exp0401e3w, tested
// inherit_plan: raw/inh0401-e3w.out; the first queue build, exp0401e3q, 13 cases: raw/inh0401-e3q.out.)
#include <algorithm>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <initializer_list>
#include <utility>
#include <vector>

#include "inherit_scan.inc"
#include "memline_parse.inc"

namespace {

uint32_t hdr(uint32_t op, uint32_t len) { // type-3 header: COUNT = len - 2 (the unit's own length rule)
    return 0xC0000000u | ((len - 2u) << 16u) | (op << 8u);
}

struct Part {
    std::vector<uint32_t> d;
    Part& set_sh(uint32_t reg, std::initializer_list<uint32_t> v) {
        d.push_back(hdr(0x76, 2u + static_cast<uint32_t>(v.size())));
        d.push_back(reg);
        d.insert(d.end(), v);
        return *this;
    }
    Part& disp_ind(uint32_t initiator) { // the GFX form: offset, initiator
        d.insert(d.end(), {hdr(0x16, 3), 0x420u, initiator});
        return *this;
    }
    Part& disp_dir(uint32_t initiator) {
        d.insert(d.end(), {hdr(0x15, 5), 1u, 1u, 1u, initiator});
        return *this;
    }
    Part& nop(uint32_t len) {
        d.push_back(hdr(0x10, len));
        d.insert(d.end(), len - 1u, 0u);
        return *this;
    }
    Part& load_pairs(const void* table, uint32_t pairs) {
        const auto a = reinterpret_cast<uint64_t>(table);
        d.insert(d.end(), {hdr(0x63, 5), static_cast<uint32_t>(a) & ~3u, static_cast<uint32_t>(a >> 32u) & 0xffffu, 0x80000000u, pairs});
        return *this;
    }
    Part& load_range(uint32_t reg, uint32_t count) {
        d.insert(d.end(), {hdr(0x63, 5), 0u, 0u, reg, count});
        return *this;
    }
    Part& ib2() {
        d.insert(d.end(), {hdr(0x3f, 4), 0x1000u, 0u, 16u});
        return *this;
    }
    Part& pgm(uint32_t lo) { return set_sh(0x20c, {lo, 0u}); }
    uint32_t n() const { return static_cast<uint32_t>(d.size()); }
};

std::vector<uint32_t> g_table;
const uint32_t* read_table(uint64_t a, uint64_t bytes) {
    return a == reinterpret_cast<uint64_t>(g_table.data()) && bytes <= g_table.size() * 4u ? g_table.data() : nullptr;
}
const uint32_t* read_none(uint64_t, uint64_t) { return nullptr; }

int g_cases = 0, g_bad = 0;
// want: (w32, bound) per dispatch, in order; state: inherit_scan's return; last_end: the last dispatch's end (0: not checked)
template <class Read>
void expect(const char* name, const Part& p, uint32_t n, const Read& read, std::initializer_list<std::pair<bool, bool>> want, int state, uint32_t last_end) {
    g_cases++;
    std::vector<InheritDispatch> ds;
    const int got = inherit_scan(p.d.data(), n, read, ds);
    bool ok = got == state && ds.size() == want.size() && (last_end == 0 || (!ds.empty() && ds.back().end == last_end));
    size_t k = 0;
    for (const auto& w: want) {
        if (k < ds.size() && (ds[k].w32 != w.first || ds[k].bound != w.second)) ok = false;
        k++;
    }
    if (ok) return;
    g_bad++;
    std::printf("inh0401: FAIL %s: state %d (want %d), %zu dispatches:", name, got, state, ds.size());
    for (const auto& d: ds) std::printf(" [at %u end %u %s %s]", d.at, d.end, d.w32 ? "W32" : "W64", d.bound ? "bound" : "unbound");
    std::printf("\n");
}

void expect_line(const char* name, const char* meminfo, const char* psi, const char* gtt_used, const char* gtt_total, std::initializer_list<const char*> parts) {
    g_cases++;
    char line[512];
    mem_line_format(mem_line_parse(meminfo, psi, gtt_used, gtt_total), 12.5, line, sizeof(line));
    for (const char* p: parts) {
        if (std::strstr(line, p) == nullptr) {
            g_bad++;
            std::printf("inh0401: FAIL %s: [%s] not in %s", name, p, line);
            return;
        }
    }
}

} // namespace

int main() {
    // Codex's counter-example. A binds program P and dispatches W64; B writes only USER_DATA_0 and dispatches W32.
    Part a;
    a.pgm(0x09098ea0u).disp_dir(0x41);
    expect("A binds and dispatches W64", a, a.n(), read_none, {{false, true}}, 1, a.n());
    Part b;
    b.set_sh(0x240, {0x87353120u}).disp_ind(0x8061);
    expect("B inherits W32: not bound", b, b.n(), read_none, {{true, false}}, -1, b.n());

    // The 08:49 head (exp 0403 section 2): four inheriting W32 dispatches, then the part's own binding and a W64 one.
    Part h;
    h.nop(2);
    for (int k = 0; k < 4; k++) h.set_sh(0x240, {0x87353120u + static_cast<uint32_t>(k & 1)}).disp_ind(0x8061);
    h.pgm(0x09098ea0u).set_sh(0x212, {1u, 2u}).disp_ind(0x61);
    expect("the 08:49 head", h, h.n(), read_none, {{true, false}, {true, false}, {true, false}, {true, false}, {false, true}}, 1, h.n());

    // The 18:16 heads (exp 0403's addendum): wave64, inheriting.
    Part w;
    w.set_sh(0x240, {0x87260121u}).disp_ind(0x41);
    expect("an 18:16 wave64 head", w, w.n(), read_none, {{false, false}}, -1, w.n());

    Part c;
    c.pgm(0x11d02879u).disp_ind(0x8061);
    expect("own binding, W32", c, c.n(), read_none, {{true, true}}, 1, c.n());

    Part r1, r2;
    r1.set_sh(0x20b, {1u, 2u, 3u}).disp_ind(0x61); // 0x20b..0x20d covers 0x20c
    r2.set_sh(0x20d, {1u}).disp_ind(0x61);         // 0x20d only
    expect("a SET_SH_REG range over 0x20c", r1, r1.n(), read_none, {{false, true}}, 1, r1.n());
    expect("a SET_SH_REG range past 0x20c", r2, r2.n(), read_none, {{false, false}}, -1, r2.n());

    g_table = {0x240u, 5u, 0x20cu, 0x0909968eu}; // two (register, value) pairs, the second names 0x20c
    Part t;
    t.load_pairs(g_table.data(), 2).disp_ind(0x8061);
    expect("a readable pair table naming 0x20c", t, t.n(), read_table, {{true, true}}, 1, t.n());
    expect("an unreadable pair table", t, t.n(), read_none, {{true, false}}, 0, t.n());

    Part o1, o2;
    o1.load_range(0x208, 8).disp_ind(0x61);
    o2.load_range(0x210, 4).disp_ind(0x61);
    expect("an offset-format load over 0x20c", o1, o1.n(), read_none, {{false, true}}, 1, o1.n());
    expect("an offset-format load past 0x20c", o2, o2.n(), read_none, {{false, false}}, -1, o2.n());

    Part i;
    i.ib2().disp_ind(0x8061);
    expect("an IB2 does not count", i, i.n(), read_none, {{true, false}}, 0, i.n());

    Part cut;
    cut.pgm(1u).disp_ind(0x8061);
    expect("a part cut inside its dispatch", cut, cut.n() - 1u, read_none, {}, 1, 0);

    // Codex's second review, point 3: a later IB2 or unreadable table voids the part's own program until the next write.
    Part v1, v2, v3, v4;
    v1.pgm(0x09098ea0u).ib2().disp_ind(0x61);
    expect("SET_PGM, IB2, dispatch", v1, v1.n(), read_none, {{false, false}}, 0, v1.n());
    v2.pgm(0x09098ea0u).load_pairs(g_table.data(), 2).disp_ind(0x61);
    expect("SET_PGM, unreadable table, dispatch", v2, v2.n(), read_none, {{false, false}}, 0, v2.n());
    v3.pgm(0x09098ea0u).ib2().pgm(0x0909968eu).disp_ind(0x61);
    expect("SET_PGM, IB2, SET_PGM, dispatch", v3, v3.n(), read_none, {{false, true}}, 1, v3.n());
    v4.pgm(0x09098ea0u).disp_ind(0x61).ib2().disp_ind(0x8061);
    expect("bound, then IB2, then unbound", v4, v4.n(), read_none, {{false, true}, {true, false}}, 0, v4.n());

    // Codex's second review, point 1: the memory line never turns a value it could not read into 0.
    const char* mi  = "MemTotal:       15556000 kB\nMemAvailable:    1048576 kB\nSwapTotal:       8388608 kB\nSwapFree:        6291456 kB\n";
    const char* psi = "some avg10=1.50 avg60=0.80 avg300=0.20 total=123456\nfull avg10=0.75 avg60=0.40 avg300=0.10 total=654321\n";
    expect_line("every file read", mi, psi, "1073741824\n", "13958643712\n",
                {"memory (exp 0401): t 12.5 s: available 1024 MiB, swap used 2048 MiB, psi some 1.50 full 0.75 (avg10, %), full total 654 ms, gtt 1024 of 13312 MiB\n"});
    expect_line("no /proc/meminfo", nullptr, psi, "1", "2", {"available unknown MiB, swap used unknown MiB", "psi some 1.50"});
    expect_line("no MemAvailable key", "MemAvailableX:   5 kB\nSwapTotal: 4 kB\nSwapFree: 1 kB\n", psi, "1", "2", {"available unknown MiB", "swap used 0 MiB"});
    expect_line("no SwapFree key", "MemAvailable: 2048 kB\nSwapTotal: 4096 kB\n", psi, "1", "2", {"available 2 MiB", "swap used unknown MiB"});
    expect_line("no full line", mi, "some avg10=0.25 avg60=0.00 avg300=0.00 total=1\n", "1", "2", {"psi some 0.25 full unknown", "full total unknown ms"});
    expect_line("no /proc/pressure/memory", mi, nullptr, "1", "2", {"psi some unknown full unknown", "full total unknown ms"});
    expect_line("no gtt total", mi, psi, "1073741824", nullptr, {"gtt unknown of unknown MiB"});
    expect_line("gtt not a number", mi, psi, "abc", "13958643712", {"gtt unknown of unknown MiB"});

    if (g_bad != 0) {
        std::printf("inh0401: %d of %d cases failed\n", g_bad, g_cases);
        return 1;
    }
    std::printf("inh0401: %d of %d cases; end\n", g_cases, g_cases);
    return 0;
}
