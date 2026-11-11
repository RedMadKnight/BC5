// SPDX-License-Identifier: GPL-2.0-only
// BC5 experiment 0412 (tag ps412): the CPU test of physmap0412.inc. Two tables get the same random operations: OLD is
// PhysicalMemory's code as it is (an unsorted vector; Unmap, Find, the name and type edits and ProtectMapping copied
// from e8's memory.cpp), NEW is the sorted table through pm412 (and the same ProtectMapping, which keeps the order).
// After every operation the results must be equal (return value, GPU mode, the host address to release, what Find
// returns) and, with OLD sorted by address, the tables must be equal block for block; NEW must stay sound. Maps never
// overlap an existing block (the condition the sorted table is used under); a separate part checks that insert()
// refuses every overlapping, empty or wrapping block.
//   clang++ -std=c++20 -O1 -Wall -Wextra -Werror physmap0412.cpp -o physmap0412 && ./physmap0412
#include <algorithm>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <random>
#include <vector>

#include "physmap0412.inc"

struct Block {
    uint64_t start_addr, size, map_vaddr, map_size, host_vaddr, host_size;
    int      prot, mode, gpu_mode, memory_type;
    char     name[32];
    bool     operator==(const Block& o) const {
        return start_addr == o.start_addr && size == o.size && map_vaddr == o.map_vaddr && map_size == o.map_size && host_vaddr == o.host_vaddr &&
               host_size == o.host_size && prot == o.prot && mode == o.mode && gpu_mode == o.gpu_mode && memory_type == o.memory_type && std::strcmp(name, o.name) == 0;
    }
};
using Table = std::vector<Block>;

static bool Overlap(uint64_t ls, uint64_t lz, uint64_t rs, uint64_t rz) { // VirtualRangesOverlap
    if (lz == 0 || rz == 0) return false;
    const uint64_t le = UINT64_MAX - ls < lz ? UINT64_MAX : ls + lz, re = UINT64_MAX - rs < rz ? UINT64_MAX : rs + rz;
    return ls < re && rs < le;
}

// ---- OLD: the unit's code ----
static bool old_unmap(Table& m, uint64_t vaddr, uint64_t size, int* gpu_mode, uint64_t* release) {
    *release = 0;
    auto last = [&m, release](uint64_t hv, uint64_t hs) {
        if (hv == 0 || hs == 0) return;
        if (!std::any_of(m.begin(), m.end(), [hv, hs](const Block& b) { return b.host_vaddr == hv && b.host_size == hs; })) *release = hv;
    };
    size_t index = 0;
    for (auto& b: m) {
        if (b.map_vaddr == vaddr && b.map_size == size) {
            *gpu_mode     = b.gpu_mode;
            const auto hv = b.host_vaddr, hs = b.host_size;
            m.erase(m.begin() + static_cast<std::ptrdiff_t>(index));
            last(hv, hs);
            return true;
        }
        if (vaddr > b.map_vaddr && vaddr + size < b.map_vaddr + b.map_size) {
            *gpu_mode   = b.gpu_mode;
            Block right = b;
            right.start_addr += (vaddr + size) - b.map_vaddr;
            right.size      = b.map_vaddr + b.map_size - (vaddr + size);
            right.map_size  = right.size;
            right.map_vaddr = vaddr + size;
            b.size          = vaddr - b.map_vaddr;
            b.map_size      = b.size;
            m.push_back(right);
            return true;
        }
        if (vaddr == b.map_vaddr && size < b.map_size) {
            *gpu_mode = b.gpu_mode;
            b.start_addr += size;
            b.size -= size;
            b.map_vaddr += size;
            b.map_size -= size;
            return true;
        }
        if (vaddr > b.map_vaddr && vaddr + size == b.map_vaddr + b.map_size) {
            *gpu_mode  = b.gpu_mode;
            b.size     = vaddr - b.map_vaddr;
            b.map_size = b.size;
            return true;
        }
        index++;
    }
    return false;
}
static const Block* old_find(const Table& m, uint64_t vaddr) {
    for (const auto& b: m) {
        if (vaddr >= b.map_vaddr && vaddr < b.map_vaddr + b.map_size) return &b;
    }
    return nullptr;
}
static void old_name(Table& m, uint64_t vaddr, uint64_t len, const char* name) {
    for (auto& b: m) {
        if (Overlap(vaddr, len, b.map_vaddr, b.map_size)) std::snprintf(b.name, sizeof(b.name), "%s", name);
    }
}
static void old_type(Table& m, uint64_t vaddr, uint64_t len, int type) {
    for (auto& b: m) {
        if (Overlap(vaddr, len, b.map_vaddr, b.map_size)) b.memory_type = type;
    }
}
static void protect(Table& m, uint64_t vaddr, uint64_t size, int prot, int mode, int gpu_mode) { // both tables: the unit's code, unchanged
    if (size == 0 || UINT64_MAX - vaddr < size) return;
    const auto end = vaddr + size;
    Table      updated;
    for (const auto& block: m) {
        const auto block_end = block.map_vaddr + block.map_size;
        if (!Overlap(vaddr, size, block.map_vaddr, block.map_size)) {
            updated.push_back(block);
            continue;
        }
        const auto os = std::max(vaddr, block.map_vaddr), oe = std::min(end, block_end);
        if (block.map_vaddr < os) {
            auto left     = block;
            left.size     = os - block.map_vaddr;
            left.map_size = left.size;
            updated.push_back(left);
        }
        auto middle       = block;
        middle.start_addr = block.start_addr + os - block.map_vaddr;
        middle.size       = oe - os;
        middle.map_vaddr  = os;
        middle.map_size   = middle.size;
        middle.prot       = prot;
        middle.mode       = mode;
        middle.gpu_mode   = gpu_mode;
        updated.push_back(middle);
        if (oe < block_end) {
            auto right       = block;
            right.start_addr = block.start_addr + oe - block.map_vaddr;
            right.size       = block_end - oe;
            right.map_vaddr  = oe;
            right.map_size   = right.size;
            updated.push_back(right);
        }
    }
    m = std::move(updated);
}

// ---- NEW: the statements mksort0412.py puts into the unit ----
static bool new_unmap(Table& m, uint64_t vaddr, uint64_t size, int* gpu_mode, uint64_t* release) {
    if (size == 0) { // the unit keeps the old walk for an empty range; it can split a block and append the right half, so sort again
        const bool r = old_unmap(m, vaddr, size, gpu_mode, release);
        std::stable_sort(m.begin(), m.end(), [](const Block& x, const Block& y) { return x.map_vaddr < y.map_vaddr; });
        return r;
    }
    *release = 0;
    uint64_t        hv = 0, hs = 0;
    const pm412::Hit hit = pm412::unmap(m, vaddr, size, gpu_mode, &hv, &hs);
    if (hit == pm412::Whole && hv != 0 && hs != 0 && !pm412::host_still_mapped(m, hv, hs)) *release = hv;
    return hit != pm412::None;
}
static const Block* new_find(Table& m, uint64_t vaddr) {
    const auto it = pm412::containing(m, vaddr);
    return it != m.end() ? &*it : nullptr;
}
static void new_name(Table& m, uint64_t vaddr, uint64_t len, const char* name) {
    for (auto it = pm412::walk_from(m, vaddr); it != m.end(); ++it) {
        if (it->map_vaddr > vaddr && it->map_vaddr - vaddr >= len) break;
        if (Overlap(vaddr, len, it->map_vaddr, it->map_size)) std::snprintf(it->name, sizeof(it->name), "%s", name);
    }
}
static void new_type(Table& m, uint64_t vaddr, uint64_t len, int type) {
    for (auto it = pm412::walk_from(m, vaddr); it != m.end(); ++it) {
        if (it->map_vaddr > vaddr && it->map_vaddr - vaddr >= len) break;
        if (Overlap(vaddr, len, it->map_vaddr, it->map_size)) it->memory_type = type;
    }
}

static uint64_t g_checks = 0, g_ok = 0;
static void     check(bool c, const char* what, int seq, int op) {
    g_checks++;
    if (c) g_ok++;
    else if (g_checks - g_ok <= 8) std::printf("FAIL %s (sequence %d, operation %d)\n", what, seq, op);
}

int main() {
    std::mt19937_64 rng(4120);
    const uint64_t  P = 0x4000;
    uint64_t        kinds[8] = {};
    for (int seq = 0; seq < 300; seq++) {
        Table          o, n;
        const uint64_t base = 0x100000000ull + P * (rng() % 64);
        const int      span = 200 + static_cast<int>(rng() % 3000); // pages of address space the sequence works in
        for (int op = 0; op < 1500; op++) {
            const uint64_t a = base + P * (rng() % static_cast<uint64_t>(span)), len = P * (1 + rng() % 12);
            const int      k = static_cast<int>(rng() % 100);
            if (k < 34) { // map, where nothing is mapped yet
                bool free_here = true;
                for (const auto& b: o) free_here = free_here && !Overlap(a, len, b.map_vaddr, b.map_size);
                Block b {rng() % (1ull << 34), len, a, len, a, len, static_cast<int>(rng() % 8), static_cast<int>(rng() % 3), static_cast<int>(rng() % 3), 0, "fresh"};
                if (free_here) {
                    o.push_back(b);
                    check(pm412::insert(n, b), "insert of a free range", seq, op);
                    kinds[0]++;
                } else {
                    const size_t before = n.size();
                    check(!pm412::insert(n, b) && n.size() == before, "insert of an overlapping range is refused", seq, op);
                    kinds[1]++;
                }
            } else if (k < 70) { // unmap: an existing block whole, its head, tail or middle, or something else
                uint64_t va = a, sz = len;
                if (!o.empty() && k < 64) {
                    const Block& b = o[rng() % o.size()];
                    const int    how = static_cast<int>(rng() % 5);
                    const uint64_t pages = b.map_size / P;
                    if (how == 0 || pages < 3) va = b.map_vaddr, sz = b.map_size;
                    else if (how == 1) va = b.map_vaddr, sz = P * (1 + rng() % (pages - 1));
                    else if (how == 2) sz = P * (1 + rng() % (pages - 1)), va = b.map_vaddr + b.map_size - sz;
                    else if (how == 3) va = b.map_vaddr + P, sz = P * (1 + rng() % (pages - 2));
                    else va = b.map_vaddr + P * (rng() % pages), sz = b.map_size + P * (rng() % 3); // runs past the block
                }
                if (k == 69) sz = 0;
                int      go = -1, gn = -1;
                uint64_t ro = 1, rn = 1;
                const bool bo = old_unmap(o, va, sz, &go, &ro), bn = new_unmap(n, va, sz, &gn, &rn);
                // An empty range changes no block; which block's GPU mode it reports depends on the walk order, so it is not compared.
                check(bo == bn && (sz == 0 || go == gn) && ro == rn, "unmap: result, gpu mode, host release", seq, op);
                kinds[bo ? 2 : 3]++;
            } else if (k < 80) {
                uint64_t q = a + (rng() % 2 ? 0 : 0x123);
                if (!o.empty() && rng() % 2) { // the first or the last byte of an existing block, or one past it
                    const Block& b = o[rng() % o.size()];
                    const int    w = static_cast<int>(rng() % 3);
                    q = w == 0 ? b.map_vaddr : w == 1 ? b.map_vaddr + b.map_size - 1 : b.map_vaddr + b.map_size;
                }
                const Block* fo = old_find(o, q);
                const Block* fn = new_find(n, q);
                check((fo == nullptr) == (fn == nullptr) && (fo == nullptr || *fo == *fn), "find", seq, op);
                kinds[4]++;
            } else if (k < 88) {
                char nm[32];
                std::snprintf(nm, sizeof(nm), "n%d", op);
                const uint64_t l = k == 87 ? 0 : len * (1 + rng() % 6);
                old_name(o, a, l, nm);
                new_name(n, a, l, nm);
                kinds[5]++;
            } else if (k < 94) {
                const uint64_t l = len * (1 + rng() % 6);
                old_type(o, a, l, op);
                new_type(n, a, l, op);
                kinds[6]++;
            } else {
                const uint64_t l = len * (1 + rng() % 4);
                protect(o, a, l, op & 7, op % 3, op % 2);
                protect(n, a, l, op & 7, op % 3, op % 2);
                kinds[7]++;
            }
            Table so = o;
            std::sort(so.begin(), so.end(), [](const Block& x, const Block& y) { return x.map_vaddr < y.map_vaddr; });
            check(so == n, "the tables hold the same blocks", seq, op);
            check(pm412::sound(n), "the sorted table is sound", seq, op);
        }
    }
    { // insert refuses what it must
        Table n;
        Block b {0, 0x8000, 0x10000, 0x8000, 0x10000, 0x8000, 0, 0, 0, 0, "a"};
        check(pm412::insert(n, b), "first insert", -1, 0);
        Block c = b;
        c.map_vaddr = 0x17000, c.map_size = 0x1000;
        check(!pm412::insert(n, c), "inside an existing block", -1, 1);
        c.map_vaddr = 0xf000, c.map_size = 0x2000;
        check(!pm412::insert(n, c), "running into the next block", -1, 2);
        c.map_vaddr = 0x18000, c.map_size = 0;
        check(!pm412::insert(n, c), "empty", -1, 3);
        c.map_vaddr = UINT64_MAX - 0xfff, c.map_size = 0x2000;
        check(!pm412::insert(n, c), "wrapping", -1, 4);
        c.map_vaddr = 0x18000, c.map_size = 0x1000;
        check(pm412::insert(n, c) && n.size() == 2 && n[1].map_vaddr == 0x18000, "touching the end is not an overlap", -1, 5);
        c.map_vaddr = 0x8000, c.map_size = 0x8000;
        check(pm412::insert(n, c) && n.size() == 3 && n[0].map_vaddr == 0x8000, "touching the start is not an overlap", -1, 6);
    }
    bool mixed = true;
    for (const uint64_t x: kinds) mixed = mixed && x > 1000; // every kind of operation ran often, so the test is not vacuous
    if (!mixed) std::printf("FAIL the operations are not mixed: %llu %llu %llu %llu %llu %llu %llu %llu\n", (unsigned long long)kinds[0], (unsigned long long)kinds[1],
                            (unsigned long long)kinds[2], (unsigned long long)kinds[3], (unsigned long long)kinds[4], (unsigned long long)kinds[5], (unsigned long long)kinds[6], (unsigned long long)kinds[7]);
    std::printf("physmap0412: %llu of %llu; end\n", static_cast<unsigned long long>(mixed ? g_ok : 0), static_cast<unsigned long long>(g_checks));
    return g_ok == g_checks && mixed ? 0 : 1;
}
