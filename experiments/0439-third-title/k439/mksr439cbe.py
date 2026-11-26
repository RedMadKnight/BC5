#!/usr/bin/env python3
# BC5 exp 0439 (tag sr439c, 11-23): the pass census's backend half, on direct.cpp after b2be439 + pw439patch + mkdk439be.
# Diagnosis only and inert unless the unit defines bc5_sr439c_block (the normal build with BC5_0439_PASS_DUMP set; the
# lean unit defines nothing, so the weak hook is null and each submit pays one null test).
#   - the arena: one GTT buffer at a fixed GPU VA (17 TiB, above the job slots' 16 TiB + 128 x 4 GiB), allocated and freed
#     by the unit at a flip after a drain (bc5_sr439c_arena), named in every BO list while it exists;
#   - the blocks: for the root (where 1), each chained or called piece (where 0) and, for a compute job laid out flat
#     (fl439), each flattened guest segment (where 2, its copies at the job's end), the unit's block of flush and copy
#     packets (bc5/sr0439c.hpp) is fetched (a size query, then the fill, which takes it off the unit's queue);
#   - placement: the root's block goes before the root's last packet when that is a chain, else after it
#     (indirect_check::insert_before, which grows COND_EXEC counts); a piece's block goes before its outgoing chain packet
#     (the chain moves down by the block's size) or after its last packet, in room the layout reserves, and every
#     INDIRECT_BUFFER pointing at the piece gets the grown size. A piece whose COND_EXEC reaches its end gets nothing
#     (counted). Nothing else moves: the executed offsets and the filters ran on the unchanged layout before.
#   python mksr439cbe.py <direct.cpp>   (in place; every anchor exactly once)
import sys

p = sys.argv[1]
s = open(p, 'rb').read().decode('utf-8')
assert '\r' not in s and 'sr439c' not in s


def rep(a, b):
    global s
    assert s.count(a) == 1, (a[:80], s.count(a))
    s = s.replace(a, b)


rep('#include "bc5/pw0439.hpp" // exp 0439 (tag pw439, mode 3)\n',
    '#include "bc5/pw0439.hpp" // exp 0439 (tag pw439, mode 3)\n#include "bc5/sr0439c.hpp" // exp 0439 (tag sr439c): the pass census\n')
rep('extern "C" void bc5_pw439_piece_note(std::uint64_t label, int decision, int ring) __attribute__((weak));\n',
    r'''extern "C" void bc5_pw439_piece_note(std::uint64_t label, int decision, int ring) __attribute__((weak));
// exp 0439 (tag sr439c): the unit's block for a buffer (src: the guest address the unit walked; where 0 a piece, 1 the
// root, 2 a flattened segment). out null: the size; else the block written (at most cap dwords) and taken off the queue.
extern "C" std::uint32_t bc5_sr439c_block(const std::uint32_t *src, int ring, int where, std::uint32_t *out, std::uint32_t cap) __attribute__((weak));
''')

rep('''std::unique_ptr<Device> Device::open(const std::string &node, const OpenOptions &opts) {
''', r'''// exp 0439 (tag sr439c): the arena (one at a time) and what of the device it needs, set at open
namespace {
struct Sc439Arena {
    amdgpu_bo_handle bo = nullptr;
    std::uint64_t va = 0, size = 0;
    void *cpu = nullptr;
};
Sc439Arena g_sc439;
amdgpu_device_handle g_sc439_dev = nullptr;
std::uint64_t *g_sc439_gen = nullptr;
std::mutex *g_sc439_mu = nullptr;
std::shared_mutex *g_sc439_flight = nullptr;
constexpr std::uint64_t kSc439Va = 0x1100'0000'0000ull;
} // namespace
// bytes > 0: a new arena (the old one freed first); 0: freed. Returns 0, or a negative errno-like code. Called by the
// unit at a flip after a drain (no job in flight); takes the device's locks in their order (flight, then mutex).
extern "C" int bc5_sr439c_arena(std::uint64_t bytes, void **cpu, std::uint64_t *va) {
    if (g_sc439_dev == nullptr) return -19;
    std::unique_lock<std::shared_mutex> flight(*g_sc439_flight);
    std::lock_guard<std::mutex> lk(*g_sc439_mu);
    Sc439Arena &a = g_sc439;
    if (a.bo != nullptr) {
        if (a.cpu != nullptr) amdgpu_bo_cpu_unmap(a.bo);
        amdgpu_bo_va_op_raw(g_sc439_dev, a.bo, 0, a.size, a.va, 0, AMDGPU_VA_OP_UNMAP);
        amdgpu_bo_free(a.bo);
        a = Sc439Arena{};
        ++*g_sc439_gen; // the BO lists must drop it
    }
    if (cpu != nullptr) *cpu = nullptr;
    if (va != nullptr) *va = 0;
    if (bytes == 0) return 0;
    bytes = (bytes + 0xffffu) & ~std::uint64_t{0xffffu};
    amdgpu_bo_alloc_request req{};
    req.alloc_size = bytes;
    req.phys_alignment = 65536;
    req.preferred_heap = AMDGPU_GEM_DOMAIN_GTT; // cached for the CPU: the census reads it back
    if (amdgpu_bo_alloc(g_sc439_dev, &req, &a.bo) != 0) {
        a = Sc439Arena{};
        return -12;
    }
    if (amdgpu_bo_va_op_raw(g_sc439_dev, a.bo, 0, bytes, kSc439Va, AMDGPU_VM_PAGE_READABLE | AMDGPU_VM_PAGE_WRITEABLE, AMDGPU_VA_OP_MAP) != 0) {
        amdgpu_bo_free(a.bo);
        a = Sc439Arena{};
        return -14;
    }
    if (amdgpu_bo_cpu_map(a.bo, &a.cpu) != 0) {
        amdgpu_bo_va_op_raw(g_sc439_dev, a.bo, 0, bytes, kSc439Va, 0, AMDGPU_VA_OP_UNMAP);
        amdgpu_bo_free(a.bo);
        a = Sc439Arena{};
        return -5;
    }
    a.va = kSc439Va, a.size = bytes;
    ++*g_sc439_gen; // the BO lists must name it
    if (cpu != nullptr) *cpu = a.cpu;
    if (va != nullptr) *va = a.va;
    return 0;
}

std::unique_ptr<Device> Device::open(const std::string &node, const OpenOptions &opts) {
''')
rep('''    return d;
}

Device::~Device() {
''', '''    g_sc439_dev = d->impl_->dev, g_sc439_gen = &d->impl_->list_gen, g_sc439_mu = &d->impl_->mutex, g_sc439_flight = &d->impl_->flight_mu; // exp 0439 (tag sr439c)
    return d;
}

Device::~Device() {
''')

rep('''    std::vector<std::uint32_t> flat_local;
    std::vector<ib_chain::FlatSeg> flat_segs;
''', '''    const std::uint32_t *sc439_orig = ib.data(); // exp 0439 (tag sr439c): the guest root the unit walked
    std::vector<std::uint32_t> flat_local;
    std::vector<ib_chain::FlatSeg> flat_segs;
''')

# the root's block (and the flattened segments'), before the CP DMA idle wait and before main_n is fixed
rep('''    if (dma_idle_ && !comp) {
''', r'''    static std::atomic<std::uint64_t> sc439_blocks{0}, sc439_dwords{0}, sc439_refused{0}; // exp 0439 (tag sr439c)
    if (bc5_sr439c_block != nullptr) { // exp 0439 (tag sr439c): the root's copies (a flattened job: every segment's, at its end)
        std::vector<std::uint32_t> blk;
        auto take = [&](const std::uint32_t *src, int where) {
            const std::uint32_t n = bc5_sr439c_block(src, ring, where, nullptr, 0);
            if (n == 0) return;
            const std::size_t at = blk.size();
            blk.resize(at + n);
            blk.resize(at + bc5_sr439c_block(src, ring, where, blk.data() + at, n));
        };
        take(sc439_orig, 1);
        for (const auto &fs : flat_segs)
            if (fs.src != sc439_orig) take(fs.src, 2);
        if (!blk.empty()) {
            bool chain = false;
            const std::size_t c = bc5::sr439c::last_packet(main_out.data(), main_out.size(), chain);
            const std::size_t at = chain ? c : main_out.size();
            if (indirect_check::insert_before(main_out, {{at, blk}})) {
                sc439_blocks++;
                sc439_dwords += blk.size();
            } else {
                sc439_refused++;
            }
        }
    }
    if (dma_idle_ && !comp) {
''')

# each piece's block, fetched before the layout's offsets are fixed
rep('''    const Piece &last = pieces.back();
    const std::size_t flag_off = last.off + last.padded; // experiment 0052: 8 dwords
''', r'''    std::vector<std::vector<std::uint32_t>> sc439_pb(pieces.size()); // exp 0439 (tag sr439c): each piece's block
    if (bc5_sr439c_block != nullptr && pieces.size() > 1) {
        bool any = false;
        for (std::size_t k = 1; k < pieces.size(); ++k) {
            const std::uint32_t n = bc5_sr439c_block(pieces[k].src, ring, 0, nullptr, 0);
            if (n == 0) continue;
            sc439_pb[k].resize(n);
            sc439_pb[k].resize(bc5_sr439c_block(pieces[k].src, ring, 0, sc439_pb[k].data(), n));
            bool chain = false;
            const std::size_t c = bc5::sr439c::last_packet(pieces[k].src, pieces[k].n, chain);
            if (bc5::sr439c::cond_exec_reaches(pieces[k].src, pieces[k].n, chain ? c : pieces[k].n) ||
                pieces[k].n + sc439_pb[k].size() > 0xfffffu) { // a COND_EXEC over the end, or the IB size field would overflow
                sc439_pb[k].clear();
                sc439_refused++;
                continue;
            }
            any = any || !sc439_pb[k].empty();
        }
        if (any)
            for (std::size_t k = 1; k < pieces.size(); ++k) {
                pieces[k].off = pieces[k - 1].off + pieces[k - 1].padded;
                pieces[k].padded = (pieces[k].n + sc439_pb[k].size() + 7) & ~std::size_t{7};
            }
    }
    const Piece &last = pieces.back();
    const std::size_t flag_off = last.off + last.padded; // experiment 0052: 8 dwords
''')

# placement in the scratch copies, after the filters (and dk439), before the IB packets are pointed at the copies
rep('''    // Point the surviving INDIRECT_BUFFER packets at the scratch copies.
''', r'''    for (std::size_t k = 1; k < pieces.size(); ++k) { // exp 0439 (tag sr439c): each piece's block at its end
        const std::vector<std::uint32_t> &b = sc439_pb[k];
        if (b.empty()) continue;
        std::uint32_t *d = dst + pieces[k].off;
        const std::size_t n = pieces[k].n, bn = b.size();
        bool chain = false;
        const std::size_t c = bc5::sr439c::last_packet(d, n, chain);
        if (chain) {
            std::memmove(d + c + bn, d + c, (n - c) * sizeof(std::uint32_t));
            std::memcpy(d + c, b.data(), bn * sizeof(std::uint32_t));
        } else {
            std::memcpy(d + n, b.data(), bn * sizeof(std::uint32_t));
        }
        for (std::size_t i = n + bn; i < pieces[k].padded; ++i) d[i] = policy::kNop;
        sc439_blocks++;
        sc439_dwords += bn;
    }
    // Point the surviving INDIRECT_BUFFER packets at the scratch copies.
''')
rep('''        const std::size_t pc_n = k == 0 ? main_n : pc.n;
''', '''        const std::size_t pc_n = k == 0 ? main_n : pc.n + sc439_pb[k].size(); // exp 0439 (tag sr439c): with its block
''')
rep('''                        d[i + 2] = static_cast<std::uint32_t>((va >> 32) & 0xffffu);
                        found = true;
''', '''                        d[i + 2] = static_cast<std::uint32_t>((va >> 32) & 0xffffu);
                        if (const std::size_t ext = sc439_pb[static_cast<std::size_t>(&q - pieces.data())].size(); ext != 0) // exp 0439 (tag sr439c)
                            d[i + 3] = (d[i + 3] & ~0xfffffu) | static_cast<std::uint32_t>(q.n + ext);
                        found = true;
''')
rep('''    if (impl_->args_slot) bos.push_back(impl_->args_slot); // experiment 0380 (F574)
''', '''    if (impl_->args_slot) bos.push_back(impl_->args_slot); // experiment 0380 (F574)
    if (g_sc439.bo != nullptr) bos.push_back(g_sc439.bo); // exp 0439 (tag sr439c): the pass census's arena
''')
assert s.count('sr439c') >= 14, s.count('sr439c')
open(p, 'wb').write(s.encode('utf-8'))
print('mksr439cbe: patched', p)
