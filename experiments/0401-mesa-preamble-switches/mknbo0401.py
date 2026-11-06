#!/usr/bin/env python3
"""BC5 experiment 0401 series e10, tag nbo (2026-11-06): the backend side of exp 0408 G6 rows 4 and 5 (B2 row N1), as the
e10 contract's section 3 and item 5 have it (scratchpad e10/CONTRACT.md):
- Device::map_null_window: null pages (one 8 MiB zero BO in VRAM, mapped piece by piece) instead of NULL PRT pages, free
  standing or inside a PRT window (under the title's AMM reservations, the rest of the window staying PRT), because Mesa
  says an SMEM load from a NULL PRT page faults and hangs the GPU on GFX10-12 (src/amd/common/ac_gpu_info.c:437-442,
  ab2374a);
- Device::map_null_range / unmap_null_range: the same null pages at ranges outside every window (the learned-window holes);
- Device::map_shared_rights: map_shared with per-mapping GPU rights (R, R|W, R|X, R|W|X), kept by map_alias.
The host unit calls them only behind its switches (BC5_DIRECT_AMM_NULL_BO, BC5_DIRECT_HOLES_NULL_BO, BC5_DIRECT_GPU_RIGHTS);
the backend has no switch of its own: nothing calls the new methods otherwise, and every existing method and signature
behaves as before while no null window, null range or rights mapping exists.
Four backend files: include/bc5/direct.hpp (the three methods' declarations and the pure helpers: kNullBoBytes,
NullPiece, null_window_pieces, null_pieces, spans_overlap, span_inside, null_place, kRights*, shared_rights_flags; Device
keeps its layout), src/direct.cpp (the null BO, null windows and ranges, va_map/va_unmap inside null windows, the rights
kept per shared mapping and by map_alias, the destructor, the methods), CMakeLists.txt (one test file more in
bc5_backend_tests) and the new tests/null_window_test.cpp (Catch2 cases tagged [nbo]; no device, no ioctl).
usage: mknbo0401.py <backend root> <out dir>   (writes <out>/<rel> for the four files; prints "<rel> <md5>" per file)
The inputs must be main 029e0d6b's files (md5 pinned, as in backend0405.md5); every anchor must occur exactly once; an
input that already holds the edit, or a root that already has the new test file, is refused. The inserted text is ASCII
and LF. After editing, the edits are undone in memory and must give the inputs back byte for byte."""
import hashlib
import os
import sys

PINS = {
    "include/bc5/direct.hpp": "a9fcb26bc48efa2dc19cb0523bfd7a60",
    "src/direct.cpp": "51279eaeb0df4225d69ce0a60587cdb9",
    "CMakeLists.txt": "309acd3c464062352d3c1f43d3b9df23",
}
NEW = "tests/null_window_test.cpp"
MARK = "exp 0401 e10 (tag nbo)"

# ---------------------------------------------------------------------------------------------------- direct.hpp
HPP_INC_OLD = r'''#include <string>
#include <vector>
'''
HPP_INC_NEW = r'''#include <string>
#include <utility> // exp 0401 e10 (tag nbo): null_place's pairs
#include <vector>
'''

HPP_SPLIT_OLD = r'''class Device {
public:
    // Opens a render node; nullptr on failure (message on stderr).
'''
HPP_SPLIT_NEW = r'''// exp 0401 e10 (tag nbo): the null BO behind Device::map_null_window and map_null_range is this big: 8 MiB, as
// RADV's (Mesa src/amd/vulkan/winsys/amdgpu/radv_amdgpu_bo.c:427, ab2374a).
inline constexpr std::uint64_t kNullBoBytes = 8ull << 20;

// exp 0401 e10 (tag nbo): one AMDGPU_VA_OP_MAP, _REPLACE or _UNMAP of the null BO: [va, va + size) maps
// [bo_offset, bo_offset + size) of it.
struct NullPiece {
    std::uint64_t va = 0;
    std::uint64_t bo_offset = 0;
    std::uint64_t size = 0;
};

// exp 0401 e10 (tag nbo): cuts [va, va + size), a range of a null window that starts at window_va,
// into pieces of a chunk-byte null BO. A piece's BO offset is (its va - window_va) mod chunk, so the
// VA and the BO stay aligned to each other the same way all over the window (putting null pages
// back after an unmap gives the offsets the window got first), and no piece crosses a chunk
// boundary of the window, so each one fits in the BO. The pieces are in address order, back to
// back, and add up to size. None when size or chunk is 0, va lies below window_va, or va + size
// does not fit in 64 bits. Pure, no device: the [nbo] tests call it.
inline std::vector<NullPiece> null_window_pieces(std::uint64_t window_va, std::uint64_t va,
                                                 std::uint64_t size, std::uint64_t chunk) {
    std::vector<NullPiece> out;
    if (size == 0 || chunk == 0 || va < window_va || size > ~std::uint64_t{0} - va) return out;
    std::uint64_t off = (va - window_va) % chunk;
    for (std::uint64_t at = va, left = size; left != 0;) {
        const std::uint64_t n = left < chunk - off ? left : chunk - off;
        out.push_back({at, off, n});
        at += n;
        left -= n;
        off = 0;
    }
    return out;
}

// exp 0401 e10 (tag nbo): the pieces the device maps for [va, va + size): window base 0, so a piece's
// BO offset is its va mod 8 MiB wherever a window or range starts. A 2 MiB-aligned VA then meets a
// 2 MiB-aligned BO offset, and an address gets the same offset whether a window, a range or a
// re-bind after an unmap put it there.
inline std::vector<NullPiece> null_pieces(std::uint64_t va, std::uint64_t size) {
    return null_window_pieces(0, va, size, kNullBoBytes);
}

// exp 0401 e10 (tag nbo): whether [a, a + an) and [b, b + bn) share an address (half-open: ranges that
// only touch do not; an empty range shares none).
inline constexpr bool spans_overlap(std::uint64_t a, std::uint64_t an, std::uint64_t b, std::uint64_t bn) {
    return an != 0 && bn != 0 && a < b + bn && b < a + an;
}

// exp 0401 e10 (tag nbo): whether [a, a + an) lies inside [b, b + bn).
inline constexpr bool span_inside(std::uint64_t a, std::uint64_t an, std::uint64_t b, std::uint64_t bn) {
    return a >= b && an <= bn && a - b <= bn - an;
}

// exp 0401 e10 (tag nbo): where null pages for [va, va + size) may go, given the device's PRT windows and
// what else it has (taken: null windows, null ranges and, for a window, userptr and shared mappings),
// each a (va, size) pair. -1: refused: an empty range, an end past 2^64, an overlap with anything
// taken, or an overlap with a PRT window that does not hold the whole range (with prt_inside_ok
// false, as for a null range: any overlap with a PRT window). 0: free (AMDGPU_VA_OP_MAP). 1: inside a
// PRT window (AMDGPU_VA_OP_REPLACE over its PRT pages).
inline int null_place(std::uint64_t va, std::uint64_t size,
                      const std::vector<std::pair<std::uint64_t, std::uint64_t>> &prt,
                      const std::vector<std::pair<std::uint64_t, std::uint64_t>> &taken, bool prt_inside_ok) {
    if (size == 0 || size > ~std::uint64_t{0} - va) return -1;
    for (const auto &[b, bn] : taken)
        if (spans_overlap(va, size, b, bn)) return -1;
    int place = 0;
    for (const auto &[b, bn] : prt) {
        if (!spans_overlap(va, size, b, bn)) continue;
        if (!prt_inside_ok || !span_inside(va, size, b, bn)) return -1;
        place = 1;
    }
    return place;
}

// exp 0401 e10 (tag nbo), exp 0408 G6 row 4: a shared mapping's GPU rights (Device::map_shared_rights):
// 1 read, 2 write, 4 execute, in the order RPCSX gives the GPU's view of the title's memory, the
// title's protection shifted down by 4 (rpcsx/gpu/Device.cpp:1028, e8ae148: prot >> 4).
inline constexpr unsigned kRightsRead = 1, kRightsWrite = 2, kRightsExec = 4;
// exp 0401 e10 (tag nbo): the VA flags for rights, given the three flag values (direct.cpp passes
// AMDGPU_VM_PAGE_READABLE, _WRITEABLE and _EXECUTABLE); 0, which maps nothing, when rights lacks read
// or has any other bit.
inline constexpr std::uint64_t shared_rights_flags(unsigned rights, std::uint64_t readable, std::uint64_t writeable,
                                                   std::uint64_t executable) {
    if ((rights & kRightsRead) == 0 || (rights & ~(kRightsRead | kRightsWrite | kRightsExec)) != 0) return 0;
    return readable | ((rights & kRightsWrite) != 0 ? writeable : 0) | ((rights & kRightsExec) != 0 ? executable : 0);
}

class Device {
public:
    // Opens a render node; nullptr on failure (message on stderr).
'''

HPP_RIGHTS_OLD = r'''    // range may be mapped at several addresses (the guest's aliases of one physical range).
    bool map_shared(std::uint32_t id, std::uint64_t bo_offset, std::uint64_t size, std::uint64_t gpu_va);
'''
HPP_RIGHTS_NEW = r'''    // range may be mapped at several addresses (the guest's aliases of one physical range).
    bool map_shared(std::uint32_t id, std::uint64_t bo_offset, std::uint64_t size, std::uint64_t gpu_va);
    // exp 0401 e10 (tag nbo), exp 0408 G6 row 4: map_shared with the GPU rights given (kRightsRead 1,
    // kRightsWrite 2, kRightsExec 4; read is required and any other bit is refused: false, nothing
    // mapped), where map_shared gives R|W|X. Otherwise as map_shared: the same sorted list, unmap_shared
    // and free_shared, REPLACE inside PRT and null windows. Aliases of it (map_alias) keep its rights.
    // mappings() still lists it as shared with readonly false.
    bool map_shared_rights(std::uint32_t id, std::uint64_t bo_offset, std::uint64_t size, std::uint64_t gpu_va,
                           unsigned rights);
'''

HPP_DECL_OLD = r'''    // and their unmapping restores them. 64 KiB aligned; call before anything is mapped there.
    bool map_prt_window(std::uint64_t va, std::uint64_t size);
'''
HPP_DECL_NEW = r'''    // and their unmapping restores them. 64 KiB aligned; call before anything is mapped there.
    bool map_prt_window(std::uint64_t va, std::uint64_t size);
    // exp 0401 e10 (tag nbo), exp 0408 B2 N1 and G6 rows 4-5: a window of null pages instead of PRT
    // pages: one zero BO of kNullBoBytes in VRAM, mapped again and again over [va, va + size) in pieces
    // (null_pieces: BO offset = va mod 8 MiB), as RADV binds its null BO (Mesa
    // src/amd/vulkan/winsys/amdgpu/radv_amdgpu_bo.c:143-166, ab2374a); Mesa says an SMEM load from a
    // NULL PRT page faults and hangs the GPU on GFX10-12 (src/amd/common/ac_gpu_info.c:437-442).
    // Contract: va and size 64 KiB aligned; either clear of everything this device has mapped (the
    // pieces are mapped), or wholly inside one PRT window, map_prt_window first (the pieces REPLACE its
    // PRT pages there: null pages under the title's reservations, PRT for the rest). Refused (false,
    // nothing mapped): an overlap with a userptr or shared mapping, another null window, a null range,
    // or a PRT window's edge (null_place). Later userptr and shared mappings inside REPLACE the null
    // pages, and unmapping them puts null pages back. Null pages read as 0. writable false: read and
    // execute only (what a GPU write does then is TODO(verify), see direct.cpp); true: writable too,
    // and a write lands in the one shared BO, so it shows at every address with the same BO offset, in
    // every null window and range. There is no call to give a null window back; ~Device clears it. On
    // failure nothing stays mapped (inside a PRT window, its PRT pages are put back) and it returns
    // false; the caller then keeps or maps PRT pages.
    bool map_null_window(std::uint64_t va, std::uint64_t size, bool writable);
    // exp 0401 e10 (tag nbo), exp 0408 G6 row 5: null pages of the same BO over [va, va + size) outside
    // every window (the learned-window holes, where the host maps its writable scratch BO today), in a
    // list of their own. 4 KiB aligned; refused (false, nothing mapped) when it overlaps a PRT or null
    // window or another null range (null_place); a mapping already there makes the kernel refuse it. Not
    // a window: va_map and va_unmap do nothing different around it, so a userptr or shared mapping there
    // fails until unmap_null_range takes the range back. writable as for map_null_window.
    bool map_null_range(std::uint64_t va, std::uint64_t size, bool writable);
    // exp 0401 e10 (tag nbo): UNMAPs exactly the pieces map_null_range put in at va. False when no null
    // range starts at va, or when an UNMAP failed (the range is forgotten either way).
    bool unmap_null_range(std::uint64_t va);
'''

# ---------------------------------------------------------------------------------------------------- direct.cpp
CPP_SMAP_OLD = r'''struct SharedMap {
    std::uint64_t va = 0;
    std::uint64_t size = 0;
    std::uint64_t bo_offset = 0;
    std::uint32_t id = 0;
    amdgpu_bo_handle bo = nullptr;
};
'''
CPP_SMAP_NEW = r'''struct SharedMap {
    std::uint64_t va = 0;
    std::uint64_t size = 0;
    std::uint64_t bo_offset = 0;
    std::uint32_t id = 0;
    amdgpu_bo_handle bo = nullptr;
    // exp 0401 e10 (tag nbo): the VA flags it was mapped with (map_shared: R|W|X; map_shared_rights: its
    // rights), which map_alias gives its aliases.
    std::uint64_t vm_flags = AMDGPU_VM_PAGE_READABLE | AMDGPU_VM_PAGE_WRITEABLE | AMDGPU_VM_PAGE_EXECUTABLE;
};
'''

CPP_IMPL_OLD = r'''    int va_map(amdgpu_bo_handle bo, std::uint64_t offset, std::uint64_t size, std::uint64_t va, std::uint64_t flags) {
        return amdgpu_bo_va_op_raw(dev, bo, offset, size, va, flags, in_prt(va, size) ? AMDGPU_VA_OP_REPLACE : AMDGPU_VA_OP_MAP);
    }
    int va_unmap(amdgpu_bo_handle bo, std::uint64_t offset, std::uint64_t size, std::uint64_t va) {
        if (in_prt(va, size)) return amdgpu_bo_va_op_raw(dev, nullptr, 0, size, va, AMDGPU_VM_PAGE_PRT, AMDGPU_VA_OP_REPLACE);
        return amdgpu_bo_va_op_raw(dev, bo, offset, size, va, 0, AMDGPU_VA_OP_UNMAP);
    }
'''
CPP_IMPL_NEW = r'''    // exp 0401 e10 (tag nbo): VA windows of null pages (Device::map_null_window), a list of their own beside
    // the PRT windows; one lies clear of every PRT window or wholly inside one. The null BO is mapped over
    // them piece by piece (null_pieces). Inside one, mappings are made with AMDGPU_VA_OP_REPLACE over the
    // null pages, as in a PRT window, and undone by replacing the range with null pieces again, as RADV
    // re-binds its null BO on an unbind (Mesa src/amd/vulkan/winsys/amdgpu/radv_amdgpu_bo.c:231-251,
    // ab2374a). Null ranges (Device::map_null_range) are pieces of the same BO outside every window, in a
    // list of their own; va_map and va_unmap ignore them.
    struct NullWindow {
        std::uint64_t va = 0;
        std::uint64_t size = 0;
        bool writable = false;
        bool over_prt = false; // inside a PRT window: the pieces REPLACEd its PRT pages
    };
    std::vector<NullWindow> null_windows;
    std::vector<NullWindow> null_ranges; // over_prt always false
    std::uint64_t null_ranges_mapped = 0, null_range_pieces = 0, null_ranges_unmapped = 0, null_ranges_failed = 0;
    amdgpu_bo_handle null_bo = nullptr; // kNullBoBytes of zeros, allocated on first use (null_bo_get)
    const NullWindow *in_null(std::uint64_t va, std::uint64_t size) const {
        for (const auto &w : null_windows)
            if (span_inside(va, size, w.va, w.size)) return &w;
        return nullptr;
    }
    // exp 0401 e10 (tag nbo): the null BO, as RADV allocates its own (radv_amdgpu_bo.c:427-429, whose
    // flags become AMDGPU_GEM_CREATE_NO_CPU_ACCESS at :604-607 and AMDGPU_GEM_CREATE_VM_ALWAYS_VALID at
    // :612-616): VRAM, no CPU view, and valid in this VM at every submission without being on a BO
    // list (the direct path's lists name only the guest's mappings). VRAM_CLEARED (amdgpu_drm.h):
    // the kernel zeroes it; RADV's request sets no such flag, its comment calls the BO zero-allocated
    // (:424-425). RADV also lets it spill to GTT (:591-592); this one asks for VRAM alone.
    int null_bo_get() {
        if (null_bo != nullptr) return 0;
        amdgpu_bo_alloc_request req{};
        req.alloc_size = kNullBoBytes;
        req.phys_alignment = 4096;
        req.preferred_heap = AMDGPU_GEM_DOMAIN_VRAM;
        req.flags = AMDGPU_GEM_CREATE_VRAM_CLEARED | AMDGPU_GEM_CREATE_NO_CPU_ACCESS | AMDGPU_GEM_CREATE_VM_ALWAYS_VALID;
        const int rc = amdgpu_bo_alloc(dev, &req, &null_bo);
        if (rc != 0) null_bo = nullptr;
        return rc;
    }
    void null_bo_drop_if_unused() { // exp 0401 e10 (tag nbo): after a failure, a BO that nothing maps goes back
        if (null_bo != nullptr && null_windows.empty() && null_ranges.empty()) {
            amdgpu_bo_free(null_bo);
            null_bo = nullptr;
        }
    }
    // exp 0401 e10 (tag nbo): maps the pieces in order with op (AMDGPU_VA_OP_MAP or _REPLACE), readable
    // and executable as RADV maps its read-only null BO (radv_amdgpu_bo.c:40-48), writable only when
    // asked. Returns the first failing rc, 0 when every piece went in; done counts those that did.
    int null_map(const std::vector<NullPiece> &pieces, bool writable, std::uint32_t op, std::size_t &done) {
        const std::uint64_t flags = AMDGPU_VM_PAGE_READABLE | AMDGPU_VM_PAGE_EXECUTABLE |
                                    (writable ? AMDGPU_VM_PAGE_WRITEABLE : 0);
        done = 0;
        for (const NullPiece &p : pieces) {
            const int rc = amdgpu_bo_va_op_raw(dev, null_bo, p.bo_offset, p.size, p.va, flags, op);
            if (rc != 0) return rc;
            ++done;
        }
        return 0;
    }
    int va_map(amdgpu_bo_handle bo, std::uint64_t offset, std::uint64_t size, std::uint64_t va, std::uint64_t flags) {
        const bool over = in_null(va, size) != nullptr || in_prt(va, size); // exp 0401 e10 (tag nbo): or null pages
        return amdgpu_bo_va_op_raw(dev, bo, offset, size, va, flags, over ? AMDGPU_VA_OP_REPLACE : AMDGPU_VA_OP_MAP);
    }
    int va_unmap(amdgpu_bo_handle bo, std::uint64_t offset, std::uint64_t size, std::uint64_t va) {
        // exp 0401 e10 (tag nbo): inside a null window, null pages back; asked before the PRT windows, since a
        // null window may lie inside one.
        if (const NullWindow *w = in_null(va, size); w != nullptr) {
            std::size_t done = 0;
            const std::vector<NullPiece> pieces = null_pieces(va, size);
            const int rc = null_map(pieces, w->writable, AMDGPU_VA_OP_REPLACE, done);
            if (rc != 0)
                std::fprintf(stderr, "bc5-direct: exp 0401 e10 (tag nbo): null pages back at 0x%llx+0x%llx: %d after %zu of %zu pieces\n",
                             static_cast<unsigned long long>(va), static_cast<unsigned long long>(size), rc, done, pieces.size());
            return rc;
        }
        if (in_prt(va, size)) return amdgpu_bo_va_op_raw(dev, nullptr, 0, size, va, AMDGPU_VM_PAGE_PRT, AMDGPU_VA_OP_REPLACE);
        return amdgpu_bo_va_op_raw(dev, bo, offset, size, va, 0, AMDGPU_VA_OP_UNMAP);
    }
'''

CPP_DTOR_OLD = r'''    for (const auto &[w, n] : impl_->prt_windows) amdgpu_bo_va_op_raw(impl_->dev, nullptr, 0, n, w, 0, AMDGPU_VA_OP_CLEAR);
'''
CPP_DTOR_NEW = r'''    for (const auto &[w, n] : impl_->prt_windows) amdgpu_bo_va_op_raw(impl_->dev, nullptr, 0, n, w, 0, AMDGPU_VA_OP_CLEAR);
    // exp 0401 e10 (tag nbo): the null windows (one inside a PRT window is clear already), the null ranges'
    // pieces, then their BO.
    for (const auto &x : impl_->null_windows) amdgpu_bo_va_op_raw(impl_->dev, nullptr, 0, x.size, x.va, 0, AMDGPU_VA_OP_CLEAR);
    for (const auto &x : impl_->null_ranges)
        for (const NullPiece &p : null_pieces(x.va, x.size))
            amdgpu_bo_va_op_raw(impl_->dev, impl_->null_bo, p.bo_offset, p.size, p.va, 0, AMDGPU_VA_OP_UNMAP);
    if (impl_->null_ranges_mapped != 0 || impl_->null_ranges_failed != 0)
        std::fprintf(stderr, "bc5-direct: exp 0401 e10 (tag nbo) at close: null ranges: %llu mapped (%llu pieces), %llu taken back, %llu refused or failed, %zu still mapped\n",
                     static_cast<unsigned long long>(impl_->null_ranges_mapped), static_cast<unsigned long long>(impl_->null_range_pieces),
                     static_cast<unsigned long long>(impl_->null_ranges_unmapped), static_cast<unsigned long long>(impl_->null_ranges_failed),
                     impl_->null_ranges.size());
    if (impl_->null_bo) amdgpu_bo_free(impl_->null_bo);
'''

CPP_SHARED_OLD = r'''    impl_->shared_maps.insert(at, SharedMap{gpu_va, size, bo_offset, id, b->bo});
'''
CPP_SHARED_NEW = r'''    impl_->shared_maps.insert(at, SharedMap{gpu_va, size, bo_offset, id, b->bo,
                                            AMDGPU_VM_PAGE_READABLE | AMDGPU_VM_PAGE_WRITEABLE | AMDGPU_VM_PAGE_EXECUTABLE}); // exp 0401 e10 (tag nbo): its flags, as mapped above
'''

CPP_RIGHTS_OLD = r'''bool Device::map_prt_window(std::uint64_t va, std::uint64_t size) {
'''
CPP_RIGHTS_NEW = r'''// exp 0401 e10 (tag nbo), exp 0408 G6 row 4: map_shared with the GPU rights given (bc5/direct.hpp; RPCSX
// rpcsx/gpu/Device.cpp:1028, e8ae148, maps the GPU's view of the title's memory with prot >> 4). The same steps as
// map_shared; the flags stay in the SharedMap for map_alias.
bool Device::map_shared_rights(std::uint32_t id, std::uint64_t bo_offset, std::uint64_t size, std::uint64_t gpu_va,
                               unsigned rights) {
    const std::uint64_t flags =
        shared_rights_flags(rights, AMDGPU_VM_PAGE_READABLE, AMDGPU_VM_PAGE_WRITEABLE, AMDGPU_VM_PAGE_EXECUTABLE);
    if (flags == 0) {
        std::fprintf(stderr, "bc5-direct: exp 0401 e10 (tag nbo): shared map at 0x%llx+0x%llx refused: rights 0x%x (read is required; 1 read, 2 write, 4 execute)\n",
                     static_cast<unsigned long long>(gpu_va), static_cast<unsigned long long>(size), rights);
        return false;
    }
    std::lock_guard lock(impl_->mutex);
    if (size == 0 || ((bo_offset | size | gpu_va) & 0xfff) != 0) return false;
    SharedBo *b = impl_->shared_bo_locked(id);
    if (b == nullptr || bo_offset + size > b->size) return false;
    const int rc = impl_->va_map(b->bo, bo_offset, size, gpu_va, flags);
    if (rc != 0) {
        std::fprintf(stderr, "bc5-direct: shared map (rights %u) at 0x%llx+0x%llx: %d\n", rights,
                     static_cast<unsigned long long>(gpu_va), static_cast<unsigned long long>(size), rc);
        return false;
    }
    const auto at = std::upper_bound(impl_->shared_maps.begin(), impl_->shared_maps.end(), gpu_va,
                                     [](std::uint64_t va, const SharedMap &m) { return va < m.va; });
    impl_->shared_maps.insert(at, SharedMap{gpu_va, size, bo_offset, id, b->bo, flags});
    b->maps++;
    impl_->list_gen++;
    return true;
}

bool Device::map_prt_window(std::uint64_t va, std::uint64_t size) {
'''

CPP_METHOD_OLD = r'''    if (rc != 0) return false;
    impl_->prt_windows.emplace_back(va, size);
    return true;
}
'''
CPP_METHOD_NEW = r'''    if (rc != 0) return false;
    impl_->prt_windows.emplace_back(va, size);
    return true;
}

// exp 0401 e10 (tag nbo), exp 0408 B2 N1 and G6 rows 4-5: a window as null pages (bc5/direct.hpp). The whole AMM
// window, 64 GiB, would be 64 GiB / 8 MiB = 8,192 pieces, one AMDGPU_VA_OP_MAP (or _REPLACE) ioctl each; the line
// below gives the time they took.
// TODO(verify): the kernel's page tables for null-BO mappings stay small while the BO is in VRAM (pieces whose BO
// offsets are congruent to their VAs mod 8 MiB, so contiguous VRAM can be mapped with large fragments), while a
// GTT-backed BO would need 4 KiB PTEs: for 64 GiB, 2^24 PTEs of 8 bytes, 128 MiB. Not cited; the host unit journals
// VRAM and GTT use before and after the window maps to measure it.
// TODO(verify): what a GPU write to a read-only null page does with retry faults off is not known (exp 0408 G6
// row 4); PRT pages drop such a write.
bool Device::map_null_window(std::uint64_t va, std::uint64_t size, bool writable) {
    std::lock_guard lock(impl_->mutex);
    if (size == 0 || ((va | size) & 0xffff) != 0 || size > ~std::uint64_t{0} - va) return false;
    const double t0 = now_ms();
    std::vector<std::pair<std::uint64_t, std::uint64_t>> taken; // the contract: nothing of this device's there yet
    for (const auto &x : impl_->null_windows) taken.emplace_back(x.va, x.size);
    for (const auto &x : impl_->null_ranges) taken.emplace_back(x.va, x.size);
    for (const auto &u : impl_->userptrs) taken.emplace_back(u.va, u.size);
    for (const auto &m : impl_->shared_maps) taken.emplace_back(m.va, m.size);
    const int place = null_place(va, size, impl_->prt_windows, taken, true);
    const std::vector<NullPiece> pieces = null_pieces(va, size);
    std::size_t done = 0;
    int rc = -EEXIST;
    const char *what = "overlaps a mapping, a null window or range, or a PRT window's edge; nothing mapped";
    if (place >= 0) {
        rc = impl_->null_bo_get();
        what = "the null BO was not allocated, nothing mapped";
    }
    if (place >= 0 && rc == 0) {
        rc = impl_->null_map(pieces, writable, place == 1 ? AMDGPU_VA_OP_REPLACE : AMDGPU_VA_OP_MAP, done);
        what = place == 1 ? "mapped over its PRT window's pages" : "mapped";
        if (rc == 0) {
            impl_->null_windows.push_back({va, size, writable, place == 1});
        } else { // nothing stays mapped: the pieces that went in come out again (inside a PRT window: PRT pages back)
            for (std::size_t k = 0; k < done; ++k) {
                const NullPiece &p = pieces[k];
                if (place == 1)
                    amdgpu_bo_va_op_raw(impl_->dev, nullptr, 0, p.size, p.va, AMDGPU_VM_PAGE_PRT, AMDGPU_VA_OP_REPLACE);
                else
                    amdgpu_bo_va_op_raw(impl_->dev, impl_->null_bo, p.bo_offset, p.size, p.va, 0, AMDGPU_VA_OP_UNMAP);
            }
            what = "a piece failed, the pieces before it taken back";
        }
    }
    if (rc != 0) impl_->null_bo_drop_if_unused();
    std::fprintf(stderr, "bc5-direct: exp 0401 e10 (tag nbo): null window 0x%llx+0x%llx (%s): %d, %zu of %zu pieces of the %llu MiB zero BO, %.1f ms, %s\n",
                 static_cast<unsigned long long>(va), static_cast<unsigned long long>(size), writable ? "rw" : "ro", rc, done,
                 pieces.size(), static_cast<unsigned long long>(kNullBoBytes >> 20), now_ms() - t0, what);
    return rc == 0;
}

// exp 0401 e10 (tag nbo), exp 0408 G6 row 5: null pages over a range outside every window (bc5/direct.hpp), for the
// learned-window holes: one line at the first range, one per refusal or failure, a count at close.
bool Device::map_null_range(std::uint64_t va, std::uint64_t size, bool writable) {
    std::lock_guard lock(impl_->mutex);
    if (size == 0 || ((va | size) & 0xfff) != 0 || size > ~std::uint64_t{0} - va) return false;
    std::vector<std::pair<std::uint64_t, std::uint64_t>> taken;
    for (const auto &x : impl_->null_windows) taken.emplace_back(x.va, x.size);
    for (const auto &x : impl_->null_ranges) taken.emplace_back(x.va, x.size);
    const bool refused = null_place(va, size, impl_->prt_windows, taken, false) != 0;
    const std::vector<NullPiece> pieces = null_pieces(va, size);
    std::size_t done = 0;
    int rc = refused ? -EEXIST : impl_->null_bo_get();
    if (!refused && rc == 0) {
        rc = impl_->null_map(pieces, writable, AMDGPU_VA_OP_MAP, done);
        if (rc == 0) {
            impl_->null_ranges.push_back({va, size, writable, false});
            impl_->null_range_pieces += pieces.size();
            if (++impl_->null_ranges_mapped == 1)
                std::fprintf(stderr, "bc5-direct: exp 0401 e10 (tag nbo): the first null range 0x%llx+0x%llx (%s): %zu pieces of the %llu MiB zero BO\n",
                             static_cast<unsigned long long>(va), static_cast<unsigned long long>(size), writable ? "rw" : "ro", pieces.size(),
                             static_cast<unsigned long long>(kNullBoBytes >> 20));
            return true;
        }
        for (std::size_t k = 0; k < done; ++k) // nothing stays mapped
            amdgpu_bo_va_op_raw(impl_->dev, impl_->null_bo, pieces[k].bo_offset, pieces[k].size, pieces[k].va, 0, AMDGPU_VA_OP_UNMAP);
    }
    impl_->null_ranges_failed++;
    impl_->null_bo_drop_if_unused();
    std::fprintf(stderr, "bc5-direct: exp 0401 e10 (tag nbo): null range 0x%llx+0x%llx (%s): %d, %zu of %zu pieces, %s; nothing mapped\n",
                 static_cast<unsigned long long>(va), static_cast<unsigned long long>(size), writable ? "rw" : "ro", rc, done, pieces.size(),
                 refused ? "overlaps a PRT or null window or another null range" : "the null BO or a piece failed");
    return false;
}

bool Device::unmap_null_range(std::uint64_t va) { // exp 0401 e10 (tag nbo)
    std::lock_guard lock(impl_->mutex);
    for (auto it = impl_->null_ranges.begin(); it != impl_->null_ranges.end(); ++it) {
        if (it->va != va) continue;
        int rc = 0;
        std::size_t failed = 0;
        for (const NullPiece &p : null_pieces(it->va, it->size)) {
            const int r = amdgpu_bo_va_op_raw(impl_->dev, impl_->null_bo, p.bo_offset, p.size, p.va, 0, AMDGPU_VA_OP_UNMAP);
            if (r != 0) {
                if (rc == 0) rc = r;
                ++failed;
            }
        }
        if (rc != 0)
            std::fprintf(stderr, "bc5-direct: exp 0401 e10 (tag nbo): null range 0x%llx+0x%llx taken back: %d, %zu pieces not unmapped\n",
                         static_cast<unsigned long long>(it->va), static_cast<unsigned long long>(it->size), rc, failed);
        impl_->null_ranges.erase(it);
        impl_->null_ranges_unmapped++;
        return rc == 0;
    }
    return false;
}
'''

CPP_ALIAS_LAMBDA_OLD = r'''    auto one = [&](amdgpu_bo_handle bo, std::uint64_t va, std::uint64_t len, std::uint64_t bo_offset,
                   bool readonly) {
'''
CPP_ALIAS_LAMBDA_NEW = r'''    auto one = [&](amdgpu_bo_handle bo, std::uint64_t va, std::uint64_t len, std::uint64_t bo_offset,
                   bool readonly, std::uint64_t vm_flags) { // exp 0401 e10 (tag nbo): vm_flags, a shared mapping's own
'''
CPP_ALIAS_FLAGS_OLD = r'''        const std::uint64_t flags = AMDGPU_VM_PAGE_READABLE | AMDGPU_VM_PAGE_EXECUTABLE |
                                    (readonly ? 0 : AMDGPU_VM_PAGE_WRITEABLE);
'''
CPP_ALIAS_FLAGS_NEW = r'''        std::uint64_t flags = AMDGPU_VM_PAGE_READABLE | AMDGPU_VM_PAGE_EXECUTABLE |
                              (readonly ? 0 : AMDGPU_VM_PAGE_WRITEABLE);
        if (vm_flags != 0) flags = vm_flags; // exp 0401 e10 (tag nbo): an alias keeps map_shared_rights' rights
'''
CPP_ALIAS_CALLS_OLD = r'''    for (const auto &u : impl_->userptrs) one(u.bo, u.va, u.size, 0, u.readonly);
    for (const auto &m : impl_->shared_maps) one(m.bo, m.va, m.size, m.bo_offset, false);
'''
CPP_ALIAS_CALLS_NEW = r'''    for (const auto &u : impl_->userptrs) one(u.bo, u.va, u.size, 0, u.readonly, 0);
    for (const auto &m : impl_->shared_maps) one(m.bo, m.va, m.size, m.bo_offset, false, m.vm_flags); // exp 0401 e10 (tag nbo)
'''

# ---------------------------------------------------------------------------------------------------- CMakeLists.txt
CMAKE_OLD = r'''                   tests/acb_restore_test.cpp tests/env_flag_test.cpp)
'''
CMAKE_NEW = r'''                   tests/acb_restore_test.cpp tests/env_flag_test.cpp
                   tests/null_window_test.cpp) # exp 0401 e10 (tag nbo): the pure helpers of bc5/direct.hpp, no device
'''

EDITS = [
    ("include/bc5/direct.hpp", HPP_INC_OLD, HPP_INC_NEW, "direct.hpp includes"),
    ("include/bc5/direct.hpp", HPP_SPLIT_OLD, HPP_SPLIT_NEW, "direct.hpp pure helpers"),
    ("include/bc5/direct.hpp", HPP_RIGHTS_OLD, HPP_RIGHTS_NEW, "direct.hpp map_shared_rights"),
    ("include/bc5/direct.hpp", HPP_DECL_OLD, HPP_DECL_NEW, "direct.hpp map_null_window and ranges"),
    ("src/direct.cpp", CPP_SMAP_OLD, CPP_SMAP_NEW, "direct.cpp SharedMap"),
    ("src/direct.cpp", CPP_IMPL_OLD, CPP_IMPL_NEW, "direct.cpp Impl"),
    ("src/direct.cpp", CPP_DTOR_OLD, CPP_DTOR_NEW, "direct.cpp ~Device"),
    ("src/direct.cpp", CPP_SHARED_OLD, CPP_SHARED_NEW, "direct.cpp map_shared's SharedMap"),
    ("src/direct.cpp", CPP_RIGHTS_OLD, CPP_RIGHTS_NEW, "direct.cpp map_shared_rights"),
    ("src/direct.cpp", CPP_METHOD_OLD, CPP_METHOD_NEW, "direct.cpp map_null_window and ranges"),
    ("src/direct.cpp", CPP_ALIAS_LAMBDA_OLD, CPP_ALIAS_LAMBDA_NEW, "direct.cpp map_alias lambda"),
    ("src/direct.cpp", CPP_ALIAS_FLAGS_OLD, CPP_ALIAS_FLAGS_NEW, "direct.cpp map_alias flags"),
    ("src/direct.cpp", CPP_ALIAS_CALLS_OLD, CPP_ALIAS_CALLS_NEW, "direct.cpp map_alias calls"),
    ("CMakeLists.txt", CMAKE_OLD, CMAKE_NEW, "CMakeLists.txt bc5_backend_tests"),
]

# ---------------------------------------------------------------------------------------------------- the new test file
TEST = r'''// SPDX-License-Identifier: GPL-2.0-only
// exp 0401 e10 (tag nbo): the pure helpers of bc5/direct.hpp behind Device::map_null_window, map_null_range and
// map_shared_rights. Pure: no test here opens a device or makes an amdgpu ioctl (CLAUDE.md hard rule 5).
#include "bc5/direct.hpp"

#include <catch2/catch_test_macros.hpp>

#include <cstddef>
#include <cstdint>
#include <utility>
#include <vector>

namespace {

using bc5::direct::null_pieces;
using bc5::direct::null_place;
using bc5::direct::null_window_pieces;
using bc5::direct::NullPiece;
using bc5::direct::shared_rights_flags;
using bc5::direct::span_inside;
using bc5::direct::spans_overlap;
using Spans = std::vector<std::pair<std::uint64_t, std::uint64_t>>;

constexpr std::uint64_t kAmm = 0x80'0000'0000ull;          // the AMM window the host maps (exp 0401 e10)
constexpr std::uint64_t kAmmBytes = 0x10'0000'0000ull;     // 64 GiB
constexpr std::uint64_t kChunk = bc5::direct::kNullBoBytes; // 8 MiB
constexpr std::uint64_t kPage = 4096;

struct Split {
    std::uint64_t window = 0, va = 0, size = 0, chunk = 0;
    std::vector<NullPiece> pieces;
};

// Ranges at and around chunk boundaries, in a chunk-aligned window and in one only 64 KiB aligned, for the
// BO's 8 MiB, a 64 KiB chunk and a 12 KiB one (not a power of two): 2 x 3 x 7 x 8 = 336 splits.
std::vector<Split> sweep() {
    std::vector<Split> out;
    for (const std::uint64_t window : {kAmm, kAmm + 0x10000}) {
        for (const std::uint64_t chunk : {kChunk, std::uint64_t{0x10000}, 3 * kPage}) {
            const std::uint64_t starts[] = {0, kPage, chunk / 2, chunk - kPage, chunk, chunk + kPage, 3 * chunk - 2 * kPage};
            const std::uint64_t sizes[] = {kPage,  2 * kPage, chunk / 2, chunk - kPage, chunk, chunk + kPage,
                                           2 * chunk, 5 * chunk + 3 * kPage};
            for (const std::uint64_t s : starts) {
                for (const std::uint64_t n : sizes) {
                    Split x;
                    x.window = window;
                    x.va = window + s;
                    x.size = n;
                    x.chunk = chunk;
                    x.pieces = null_window_pieces(window, window + s, n, chunk);
                    out.push_back(x);
                }
            }
        }
    }
    return out;
}

} // namespace

TEST_CASE("nbo: the whole 64 GiB window is 8192 pieces of the whole 8 MiB BO", "[nbo]") {
    const auto p = null_window_pieces(kAmm, kAmm, kAmmBytes, kChunk);
    REQUIRE(p.size() == 8192u);
    std::size_t bad = 0;
    for (std::size_t k = 0; k < p.size(); ++k)
        if (p[k].va != kAmm + k * kChunk || p[k].bo_offset != 0 || p[k].size != kChunk) ++bad;
    CHECK(bad == 0u);
    CHECK(p.back().va + p.back().size == kAmm + kAmmBytes);
}

TEST_CASE("nbo: a range unaligned at both ends is a partial chunk, whole chunks and a partial chunk", "[nbo]") {
    // From 3 pages before the end of the window's chunk 5 to 5 pages into its chunk 9.
    const std::uint64_t va = kAmm + 6 * kChunk - 3 * kPage;
    const auto p = null_window_pieces(kAmm, va, 3 * kPage + 3 * kChunk + 5 * kPage, kChunk);
    REQUIRE(p.size() == 5u);
    CHECK(p[0].va == va);
    CHECK(p[0].bo_offset == kChunk - 3 * kPage);
    CHECK(p[0].size == 3 * kPage);
    for (std::size_t k = 1; k <= 3; ++k) {
        CHECK(p[k].va == kAmm + (5 + k) * kChunk);
        CHECK(p[k].bo_offset == 0u);
        CHECK(p[k].size == kChunk);
    }
    CHECK(p[4].va == kAmm + 9 * kChunk);
    CHECK(p[4].bo_offset == 0u);
    CHECK(p[4].size == 5 * kPage);
    // A window only 64 KiB aligned: the offsets count from its base, not from address 0.
    const std::uint64_t w = kAmm + 0x10000;
    const auto q = null_window_pieces(w, w + 2 * kChunk + 7 * kPage, kChunk, kChunk);
    REQUIRE(q.size() == 2u);
    CHECK(q[0].va == w + 2 * kChunk + 7 * kPage);
    CHECK(q[0].bo_offset == 7 * kPage);
    CHECK(q[0].size == kChunk - 7 * kPage);
    CHECK(q[1].va == w + 3 * kChunk);
    CHECK(q[1].bo_offset == 0u);
    CHECK(q[1].size == 7 * kPage);
}

TEST_CASE("nbo: a range inside one chunk is one piece at its own offset", "[nbo]") {
    const std::uint64_t va = kAmm + 17 * kChunk + 0x123000;
    const auto p = null_window_pieces(kAmm, va, 0x40000, kChunk);
    REQUIRE(p.size() == 1u);
    CHECK(p[0].va == va);
    CHECK(p[0].bo_offset == 0x123000u);
    CHECK(p[0].size == 0x40000u);
    const auto whole = null_window_pieces(kAmm, kAmm + 4 * kChunk, kChunk, kChunk); // exactly one chunk
    REQUIRE(whole.size() == 1u);
    CHECK(whole[0].va == kAmm + 4 * kChunk);
    CHECK(whole[0].bo_offset == 0u);
    CHECK(whole[0].size == kChunk);
    const auto tail = null_window_pieces(kAmm, kAmm + kChunk - 2 * kPage, 2 * kPage, kChunk); // up to the chunk's end
    REQUIRE(tail.size() == 1u);
    CHECK(tail[0].bo_offset == kChunk - 2 * kPage);
    CHECK(tail[0].size == 2 * kPage);
}

TEST_CASE("nbo: a range crossing chunk boundaries is cut at each one", "[nbo]") {
    const std::uint64_t va = kAmm + 2 * kChunk - kPage;
    const auto p = null_window_pieces(kAmm, va, 2 * kPage, kChunk); // one boundary
    REQUIRE(p.size() == 2u);
    CHECK(p[0].va == va);
    CHECK(p[0].bo_offset == kChunk - kPage);
    CHECK(p[0].size == kPage);
    CHECK(p[1].va == kAmm + 2 * kChunk);
    CHECK(p[1].bo_offset == 0u);
    CHECK(p[1].size == kPage);
    const auto q = null_window_pieces(kAmm, kAmm + kPage, 4 * kChunk, kChunk); // four boundaries
    REQUIRE(q.size() == 5u);
    CHECK(q[0].va == kAmm + kPage);
    CHECK(q[0].bo_offset == kPage);
    CHECK(q[0].size == kChunk - kPage);
    for (std::size_t k = 1; k <= 3; ++k) {
        CHECK(q[k].va == kAmm + k * kChunk);
        CHECK(q[k].bo_offset == 0u);
        CHECK(q[k].size == kChunk);
    }
    CHECK(q[4].va == kAmm + 4 * kChunk);
    CHECK(q[4].bo_offset == 0u);
    CHECK(q[4].size == kPage);
    const auto s = null_window_pieces(kAmm, kAmm + 0x8000, 0x20000, 0x10000); // the chunk is the caller's
    REQUIRE(s.size() == 3u);
    CHECK(s[0].bo_offset == 0x8000u);
    CHECK(s[0].size == 0x8000u);
    CHECK(s[1].va == kAmm + 0x10000);
    CHECK(s[1].bo_offset == 0u);
    CHECK(s[1].size == 0x10000u);
    CHECK(s[2].va == kAmm + 0x20000);
    CHECK(s[2].size == 0x8000u);
}

TEST_CASE("nbo: every piece's BO offset is congruent to its distance from the window base", "[nbo]") {
    std::size_t pieces = 0, bad = 0;
    for (const Split &x : sweep()) {
        for (const NullPiece &p : x.pieces) {
            ++pieces;
            if (p.bo_offset != (p.va - x.window) % x.chunk) ++bad;
        }
    }
    CHECK(pieces == 742u); // the chunks the 336 ranges touch, counted apart from the splitter
    CHECK(bad == 0u);
}

TEST_CASE("nbo: the pieces are back to back, in order, and add up to the range", "[nbo]") {
    std::size_t splits = 0, bad = 0;
    for (const Split &x : sweep()) {
        ++splits;
        std::uint64_t at = x.va;
        for (const NullPiece &p : x.pieces) {
            if (p.va != at) ++bad;
            at = p.va + p.size;
        }
        // as many pieces as chunks of the window the range touches
        const std::uint64_t touched = (x.va + x.size - 1 - x.window) / x.chunk - (x.va - x.window) / x.chunk + 1;
        if (at != x.va + x.size || x.pieces.size() != touched) ++bad;
    }
    CHECK(splits == 336u);
    CHECK(bad == 0u);
}

TEST_CASE("nbo: no piece is empty, crosses a chunk boundary or runs past the end of the BO", "[nbo]") {
    std::size_t bad = 0, inner = 0;
    for (const Split &x : sweep()) {
        for (std::size_t k = 0; k < x.pieces.size(); ++k) {
            const NullPiece &p = x.pieces[k];
            if (p.size == 0 || p.size > x.chunk || p.bo_offset + p.size > x.chunk ||
                (p.va - x.window) / x.chunk != (p.va + p.size - 1 - x.window) / x.chunk)
                ++bad;
            if (k != 0 && k + 1 != x.pieces.size()) { // between the first and the last: whole chunks only
                ++inner;
                if (p.bo_offset != 0 || p.size != x.chunk) ++bad;
            }
        }
    }
    CHECK(inner == 216u); // likewise counted apart from the splitter
    CHECK(bad == 0u);
}

TEST_CASE("nbo: nothing to map gives no pieces", "[nbo]") {
    CHECK(null_window_pieces(kAmm, kAmm, 0, kChunk).empty());
    CHECK(null_window_pieces(kAmm, kAmm + 3 * kChunk + kPage, 0, kChunk).empty());
    CHECK(null_window_pieces(kAmm, kAmm, kChunk, 0).empty());                             // no chunk
    CHECK(null_window_pieces(kAmm, kAmm - kPage, 2 * kPage, kChunk).empty());             // below the window
    CHECK(null_window_pieces(0, ~std::uint64_t{0} - kPage + 1, 2 * kPage, kChunk).empty()); // the end does not fit
    // The highest range whose end still fits is cut as any other.
    const std::uint64_t top = ~std::uint64_t{0} - 0xffff; // 0xffff'ffff'ffff'0000
    const auto p = null_window_pieces(top, top, 0xffff, kChunk);
    REQUIRE(p.size() == 1u);
    CHECK(p[0].va == top);
    CHECK(p[0].bo_offset == 0u);
    CHECK(p[0].size == 0xffffu);
}

TEST_CASE("nbo: the device's pieces keep every BO offset at va mod 8 MiB", "[nbo]") {
    // The AMM window starts on a chunk boundary: its pieces are the window's own.
    const auto amm = null_pieces(kAmm, kAmmBytes);
    const auto win = null_window_pieces(kAmm, kAmm, kAmmBytes, kChunk);
    REQUIRE(amm.size() == win.size());
    std::size_t bad = 0;
    for (std::size_t k = 0; k < amm.size(); ++k)
        if (amm[k].va != win[k].va || amm[k].bo_offset != win[k].bo_offset || amm[k].size != win[k].size) ++bad;
    CHECK(bad == 0u);
    // A reservation 64 KiB into a chunk: its first piece starts at BO offset 0x10000, not 0.
    const auto r = null_pieces(kAmm + 3 * kChunk + 0x10000, 2 * kChunk);
    REQUIRE(r.size() == 3u);
    CHECK(r[0].va == kAmm + 3 * kChunk + 0x10000);
    CHECK(r[0].bo_offset == 0x10000u);
    CHECK(r[0].size == kChunk - 0x10000);
    CHECK(r[1].va == kAmm + 4 * kChunk);
    CHECK(r[1].bo_offset == 0u);
    CHECK(r[1].size == kChunk);
    CHECK(r[2].va == kAmm + 5 * kChunk);
    CHECK(r[2].bo_offset == 0u);
    CHECK(r[2].size == 0x10000u);
    // A hole, 4 KiB aligned, low in the address space: 0x1'2345'6000 is 0x456000 into its 8 MiB chunk.
    const auto h = null_pieces(0x1'2345'6000ull, 3 * kPage);
    REQUIRE(h.size() == 1u);
    CHECK(h[0].bo_offset == 0x456000u);
    CHECK(h[0].size == 3 * kPage);
}

TEST_CASE("nbo: spans_overlap and span_inside are half-open", "[nbo]") {
    CHECK(spans_overlap(0x1000, 0x2000, 0x2000, 0x1000));        // they share 0x2000-0x2fff
    CHECK(spans_overlap(0x2000, 0x1000, 0x1000, 0x2000));        // the same, the other way round
    CHECK(spans_overlap(0x1000, 0x4000, 0x2000, 0x1000));        // one holds the other
    CHECK_FALSE(spans_overlap(0x1000, 0x1000, 0x2000, 0x1000));  // touching at 0x2000
    CHECK_FALSE(spans_overlap(0x2000, 0x1000, 0x1000, 0x1000));  // touching, the other way round
    CHECK_FALSE(spans_overlap(0x2000, 0, 0x1000, 0x2000));       // an empty range
    CHECK_FALSE(spans_overlap(0x1000, 0x2000, 0x2000, 0));       // an empty range, the other side
    CHECK(span_inside(0x2000, 0x1000, 0x1000, 0x3000));          // strictly inside
    CHECK(span_inside(0x1000, 0x3000, 0x1000, 0x3000));          // the same range
    CHECK(span_inside(0x3000, 0x1000, 0x1000, 0x3000));          // ends at the end
    CHECK_FALSE(span_inside(0x3000, 0x2000, 0x1000, 0x3000));    // runs past the end
    CHECK_FALSE(span_inside(0x0000, 0x2000, 0x1000, 0x3000));    // starts before
    CHECK_FALSE(span_inside(0x1000, 0x4000, 0x1000, 0x3000));    // bigger, the same start
    CHECK_FALSE(span_inside(0x5000, 0x1000, 0x1000, 0x3000));    // after it
    CHECK(span_inside(kAmm, kAmmBytes, kAmm, kAmmBytes));
    CHECK_FALSE(span_inside(~std::uint64_t{0} - 0xfff, 0x1000, 0x1000, 0x1000)); // far above it
}

TEST_CASE("nbo: null_place for a window: clear, inside one PRT window, or refused", "[nbo]") {
    const Spans prt = {{kAmm, kAmmBytes}, {0x20'0000'0000ull, 0x1'0000'0000ull}};
    const Spans none;
    const Spans taken = {{kAmm + 0x100000, 0x10000}, {0x1000'0000ull, 0x10000}};
    CHECK(null_place(0x4000'0000ull, 0x10000, prt, taken, true) == 0);                // nothing there
    CHECK(null_place(kAmm + kChunk, 4 * kChunk, prt, taken, true) == 1);              // inside the AMM PRT window
    CHECK(null_place(kAmm, kAmmBytes, prt, none, true) == 1);                         // the whole PRT window
    CHECK(null_place(0x20'0000'0000ull + 0x10000, 0x10000, prt, taken, true) == 1);   // inside the second one
    CHECK(null_place(kAmm - 0x10000, 0x20000, prt, taken, true) == -1);               // across the window's start
    CHECK(null_place(kAmm + kAmmBytes - 0x10000, 0x20000, prt, taken, true) == -1);   // across its end
    CHECK(null_place(kAmm - 0x10000, 0x10000, prt, taken, true) == 0);                // ends where it starts
    CHECK(null_place(kAmm + kAmmBytes, 0x10000, prt, taken, true) == 0);              // starts where it ends
    CHECK(null_place(kAmm + 0xf0000, 0x20000, prt, taken, true) == -1);               // inside, over a taken range
    CHECK(null_place(kAmm + 0x110000, 0x10000, prt, taken, true) == 1);               // inside, right after it
    CHECK(null_place(0x1000'0000ull - 0x8000, 0x10000, prt, taken, true) == -1);      // over a taken range outside
    CHECK(null_place(0x1000'0000ull + 0x10000, 0x10000, prt, taken, true) == 0);      // right after that one
    CHECK(null_place(kAmm + kChunk, 0, prt, taken, true) == -1);                      // empty
    CHECK(null_place(~std::uint64_t{0} - 0xffff, 0x20000, none, none, true) == -1);   // the end past 2^64
}

TEST_CASE("nbo: null_place for a range refuses every PRT window", "[nbo]") {
    const Spans prt = {{kAmm, kAmmBytes}};
    const Spans windows = {{0x30'0000'0000ull, 0x100'0000ull}}; // a null window clear of the PRT window, as taken
    CHECK(null_place(kAmm + kChunk, 0x1000, prt, windows, false) == -1);                // inside the PRT window
    CHECK(null_place(kAmm - 0x1000, 0x2000, prt, windows, false) == -1);                // across its start
    CHECK(null_place(kAmm - 0x1000, 0x1000, prt, windows, false) == 0);                 // just before it
    CHECK(null_place(0x30'0000'0000ull + 0x5000, 0x1000, prt, windows, false) == -1);   // inside the null window
    CHECK(null_place(0x30'0000'0000ull - 0x1000, 0x1000, prt, windows, false) == 0);    // just before that one
    CHECK(null_place(0x1'2345'6000ull, 0x3000, prt, windows, false) == 0);              // a hole elsewhere
}

TEST_CASE("nbo: shared rights: read, read-write, read-execute and all three give their flags", "[nbo]") {
    constexpr std::uint64_t r = 0x100, w = 0x200, x = 0x400; // stand-ins: the device passes AMDGPU_VM_PAGE_*
    CHECK(shared_rights_flags(1, r, w, x) == r);
    CHECK(shared_rights_flags(3, r, w, x) == (r | w));
    CHECK(shared_rights_flags(5, r, w, x) == (r | x));
    CHECK(shared_rights_flags(7, r, w, x) == (r | w | x));
    CHECK(shared_rights_flags(bc5::direct::kRightsRead | bc5::direct::kRightsExec, r, w, x) == (r | x));
    static_assert(shared_rights_flags(7, 2, 4, 8) == 14, "constexpr");
}

TEST_CASE("nbo: shared rights without read or with any other bit give no flags", "[nbo]") {
    for (const unsigned bad : {0u, 2u, 4u, 6u, 8u, 9u, 15u, 0x11u, 0x31u, 0x80000001u})
        CHECK(shared_rights_flags(bad, 0x100, 0x200, 0x400) == 0u);
}
'''
TEST_CASES = 14  # box0401.sh requires "All tests passed (... in 14 test cases)" for bc5_backend_tests '[nbo]'


def md5(b):
    return hashlib.md5(b).hexdigest()


def edit(text, old, new, what):
    n = text.count(old)
    assert n == 1, f"{what}: the anchor occurs {n} times"
    return text.replace(old, new)


def snippet_ok(s, what):
    assert all(ord(c) < 128 for c in s), f"{what}: not ASCII"
    assert "\r" not in s, f"{what}: has CR"


def main():
    if len(sys.argv) != 3:
        print("usage: mknbo0401.py <backend root> <out dir>", file=sys.stderr)
        sys.exit(2)
    root, out = sys.argv[1], sys.argv[2]
    assert os.path.abspath(root) != os.path.abspath(out), "the out dir is the backend root"
    src = {}
    for rel, pin in PINS.items():
        with open(os.path.join(root, rel), "rb") as f:
            b = f.read()
        assert MARK.encode() not in b, f"{rel} already holds the edit"
        assert md5(b) == pin, f"{rel} is {md5(b)}, not {pin}"
        assert b"\r" not in b, f"{rel} has CR bytes"
        src[rel] = b
    assert not os.path.exists(os.path.join(root, NEW)), f"{NEW} is already there"
    for rel, old, new, what in EDITS:
        snippet_ok(old, what + " (anchor)")
        snippet_ok(new, what)
        assert MARK in new.replace(old, ""), f"{what}: the inserted text carries no '{MARK}'"
    snippet_ok(TEST, NEW)
    assert TEST.count("TEST_CASE(") == TEST_CASES and TEST.count('"[nbo]")') == TEST_CASES, "the [nbo] case count"
    res = {}
    for rel in PINS:
        text = src[rel].decode("utf-8")
        for r, old, new, what in EDITS:
            if r == rel:
                text = edit(text, old, new, what)
        res[rel] = text
    # Undo in memory: the inputs must come back byte for byte.
    for rel in PINS:
        text = res[rel]
        for r, old, new, what in reversed(EDITS):
            if r == rel:
                assert text.count(new) == 1, f"{what}: the edit occurs {text.count(new)} times in the output"
                text = text.replace(new, old)
        assert text.encode("utf-8") == src[rel], f"{rel}: undoing the edits does not give the input back"
    res[NEW] = TEST
    for rel, text in res.items():
        p = os.path.join(out, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        b = text.encode("utf-8")
        assert b"\r" not in b
        with open(p, "wb") as f:
            f.write(b)
        print(rel, md5(b))


if __name__ == "__main__":
    main()
