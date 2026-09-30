// SPDX-License-Identifier: GPL-2.0-only
#include "bc5/direct.hpp"

#include <amdgpu.h>
#include <amdgpu_drm.h>
#include <fcntl.h>
#include <xf86drm.h>
#include <unistd.h>

#include <chrono>
#include <cstdio>
#include <cstring>
#include <mutex>

namespace bc5::direct {

namespace {

double now_ms() {
    return std::chrono::duration<double, std::milli>(
               std::chrono::steady_clock::now().time_since_epoch())
        .count();
}

struct UserptrBo {
    std::uint64_t va = 0;
    std::uint64_t size = 0;
    amdgpu_bo_handle bo = nullptr;
    bool readonly = false;
};

struct ScratchBo {
    amdgpu_bo_handle bo = nullptr;
    amdgpu_va_handle va_handle = nullptr; // only with legacy_scratch_va
    std::uint64_t va = 0;
    std::uint64_t size = 0;
    void *cpu = nullptr;
};

} // namespace

struct Device::Impl {
    int fd = -1;
    amdgpu_device_handle dev = nullptr;
    amdgpu_context_handle ctx = nullptr;
    std::vector<UserptrBo> userptrs;
    ScratchBo scratch;
    amdgpu_bo_handle gds = nullptr; // OpenOptions::gds_kib
    amdgpu_bo_handle oa = nullptr;  // OpenOptions::oa_count
    amdgpu_bo_handle gws = nullptr; // OpenOptions::gws_count
    amdgpu_bo_handle shadow = nullptr; // OpenOptions::gds_shadow, 64 KiB at kShadowVa
    static constexpr std::uint64_t kShadowVa = 0x1000'0400'0000ull; // 64 MiB above the scratch
    std::mutex mutex;

    // The scratch IB lives at a fixed GPU VA of 16 TiB: inside the 48-bit range the CP can
    // address (an IB address above 2^48 is truncated by the CP — the kernel-half "high VA" range
    // hung the BC-250, experiment 0016), above every guest window a track-B host maps 1:1
    // (< 1 TiB) and away from libdrm's low-range allocator (0x100000000+).
    static constexpr std::uint64_t kScratchVa = 0x1000'0000'0000ull;
    OpenOptions opts;

    bool scratch_reserve(std::uint64_t bytes) {
        if (scratch.bo != nullptr && scratch.size >= bytes) return true;
        scratch_free();
        // Exactly the pages needed (dispatch-min's 4 KiB command BO is the configuration known
        // to work; a 1 MiB scratch hung the CP on the second fetch, experiment 0016).
        std::uint64_t size = (bytes + 4095) & ~std::uint64_t{4095};
        if (size == 0) size = 4096;
        amdgpu_bo_alloc_request req{};
        req.alloc_size = size;
        req.phys_alignment = 4096;
        req.preferred_heap = AMDGPU_GEM_DOMAIN_GTT;
        if (amdgpu_bo_alloc(dev, &req, &scratch.bo) != 0) return false;
        if (opts.legacy_scratch_va) {
            if (amdgpu_va_range_alloc(dev, amdgpu_gpu_va_range_general, size, 4096, 0, &scratch.va,
                                      &scratch.va_handle, 0) != 0)
                return false;
        } else {
            drm_amdgpu_info_device dev_info{};
            if (amdgpu_query_info(dev, AMDGPU_INFO_DEV_INFO, sizeof(dev_info), &dev_info) != 0 ||
                kScratchVa + size > dev_info.virtual_address_max) {
                std::fprintf(stderr, "bc5-direct: scratch VA 0x%llx outside the device's range\n",
                             static_cast<unsigned long long>(kScratchVa));
                return false;
            }
            scratch.va = kScratchVa;
        }
        // MTYPE_UC: the CP must never read the scratch through a stale GL2 line. A buffer read
        // once by the GPU and then rewritten by the CPU is served from the GPU L2 on the next
        // fetch (CPU-side coherence does not reach it): the first submit cached "8 NOPs + zeros",
        // the next one executed the zeros as type-0 packets and hung (experiment 0016, eight
        // resets to find). Uncached PTEs make every IB fetch go to memory.
        const std::uint64_t flags = AMDGPU_VM_PAGE_READABLE | AMDGPU_VM_PAGE_WRITEABLE |
                                    AMDGPU_VM_PAGE_EXECUTABLE | AMDGPU_VM_MTYPE_UC;
        if (amdgpu_bo_va_op_raw(dev, scratch.bo, 0, size, scratch.va, flags, AMDGPU_VA_OP_MAP) != 0) {
            std::fprintf(stderr, "bc5-direct: scratch map at 0x%llx failed\n",
                         static_cast<unsigned long long>(scratch.va));
            return false;
        }
        if (amdgpu_bo_cpu_map(scratch.bo, &scratch.cpu) != 0) return false;
        scratch.size = size;
        return true;
    }

    void scratch_free() {
        if (scratch.cpu) amdgpu_bo_cpu_unmap(scratch.bo);
        if (scratch.va && scratch.bo) amdgpu_bo_va_op_raw(dev, scratch.bo, 0, scratch.size, scratch.va, 0, AMDGPU_VA_OP_UNMAP);
        if (scratch.va_handle) amdgpu_va_range_free(scratch.va_handle);
        if (scratch.bo) amdgpu_bo_free(scratch.bo);
        scratch = ScratchBo{};
    }
};

std::unique_ptr<Device> Device::open(const std::string &node, const OpenOptions &opts) {
    std::unique_ptr<Device> d(new Device());
    d->impl_ = std::make_unique<Impl>();
    d->impl_->opts = opts;
    d->impl_->fd = ::open(node.c_str(), O_RDWR | O_CLOEXEC);
    if (d->impl_->fd < 0) {
        std::perror(node.c_str());
        return nullptr;
    }
    std::uint32_t major = 0, minor = 0;
    // deduplicate_device = false: libdrm otherwise returns the amdgpu_device (and therefore the
    // VM, VA allocator and fd) already opened by another client of the same node in this process
    // — RADV, in a track-B host — and every 1:1 mapping and scratch IB of ours lands in that VM.
    // A private device means a private VM. (Diagnostic: OpenOptions::deduplicate_device.)
    const int rc = opts.deduplicate_device
                       ? amdgpu_device_initialize(d->impl_->fd, &major, &minor, &d->impl_->dev)
                       : amdgpu_device_initialize2(d->impl_->fd, false, &major, &minor, &d->impl_->dev);
    if (rc != 0) {
        std::fprintf(stderr, "bc5-direct: amdgpu_device_initialize%s failed on %s\n",
                     opts.deduplicate_device ? "" : "2", node.c_str());
        return nullptr;
    }
    if (amdgpu_cs_ctx_create(d->impl_->dev, &d->impl_->ctx) != 0) {
        std::fprintf(stderr, "bc5-direct: amdgpu_cs_ctx_create failed\n");
        return nullptr;
    }
    if (opts.gds_kib != 0) {
        amdgpu_bo_alloc_request req{};
        req.alloc_size = static_cast<std::uint64_t>(opts.gds_kib) * 1024;
        req.preferred_heap = AMDGPU_GEM_DOMAIN_GDS;
        const int grc = amdgpu_bo_alloc(d->impl_->dev, &req, &d->impl_->gds);
        std::fprintf(stderr, "bc5-direct: GDS BO %u KiB: %s (%d)\n", opts.gds_kib, grc == 0 ? "ok" : "FAILED", grc);
        if (grc != 0) d->impl_->gds = nullptr;
    }
    if (opts.oa_count != 0) {
        amdgpu_bo_alloc_request req{};
        req.alloc_size = opts.oa_count;
        req.preferred_heap = AMDGPU_GEM_DOMAIN_OA;
        const int orc = amdgpu_bo_alloc(d->impl_->dev, &req, &d->impl_->oa);
        std::fprintf(stderr, "bc5-direct: OA BO %u: %s (%d)\n", opts.oa_count, orc == 0 ? "ok" : "FAILED", orc);
        if (orc != 0) d->impl_->oa = nullptr;
    }
    if (opts.gds_shadow) {
        amdgpu_bo_alloc_request req{};
        req.alloc_size = 65536;
        req.phys_alignment = 4096;
        req.preferred_heap = AMDGPU_GEM_DOMAIN_GTT;
        int src = amdgpu_bo_alloc(d->impl_->dev, &req, &d->impl_->shadow);
        if (src == 0) {
            void *cpu = nullptr;
            if (amdgpu_bo_cpu_map(d->impl_->shadow, &cpu) == 0) {
                std::memset(cpu, 0, 65536);
                amdgpu_bo_cpu_unmap(d->impl_->shadow);
            }
            src = amdgpu_bo_va_op_raw(d->impl_->dev, d->impl_->shadow, 0, 65536, Impl::kShadowVa,
                                      AMDGPU_VM_PAGE_READABLE | AMDGPU_VM_PAGE_WRITEABLE, AMDGPU_VA_OP_MAP);
        }
        std::fprintf(stderr, "bc5-direct: GDS shadow 64 KiB at 0x%llx: %s (%d)\n",
                     static_cast<unsigned long long>(Impl::kShadowVa), src == 0 ? "ok" : "FAILED", src);
        if (src != 0 && d->impl_->shadow) { amdgpu_bo_free(d->impl_->shadow); d->impl_->shadow = nullptr; }
    }
    if (opts.gws_count != 0) {
        amdgpu_bo_alloc_request req{};
        req.alloc_size = opts.gws_count;
        req.preferred_heap = AMDGPU_GEM_DOMAIN_GWS;
        const int wrc = amdgpu_bo_alloc(d->impl_->dev, &req, &d->impl_->gws);
        std::fprintf(stderr, "bc5-direct: GWS BO %u: %s (%d)\n", opts.gws_count, wrc == 0 ? "ok" : "FAILED", wrc);
        if (wrc != 0) d->impl_->gws = nullptr;
    }
    return d;
}

Device::~Device() {
    if (!impl_) return;
    for (auto &u : impl_->userptrs) {
        amdgpu_bo_va_op(u.bo, 0, u.size, u.va, 0, AMDGPU_VA_OP_UNMAP);
        amdgpu_bo_free(u.bo);
    }
    impl_->scratch_free();
    if (impl_->gds) amdgpu_bo_free(impl_->gds);
    if (impl_->oa) amdgpu_bo_free(impl_->oa);
    if (impl_->shadow) {
        amdgpu_bo_va_op_raw(impl_->dev, impl_->shadow, 0, 65536, Impl::kShadowVa, 0, AMDGPU_VA_OP_UNMAP);
        amdgpu_bo_free(impl_->shadow);
    }
    if (impl_->gws) amdgpu_bo_free(impl_->gws);
    if (impl_->ctx) amdgpu_cs_ctx_free(impl_->ctx);
    if (impl_->dev) amdgpu_device_deinitialize(impl_->dev);
    if (impl_->fd >= 0) close(impl_->fd);
}

bool Device::map_userptr(std::uint64_t cpu_va, std::uint64_t size) {
    return map_userptr(cpu_va, size, false);
}

bool Device::map_userptr(std::uint64_t cpu_va, std::uint64_t size, bool readonly) {
    std::lock_guard lock(impl_->mutex);
    if (size == 0 || (cpu_va & 0xfff) != 0 || (size & 0xfff) != 0) return false;
    for (const auto &u : impl_->userptrs) {
        if (cpu_va < u.va + u.size && u.va < cpu_va + size) {
            std::fprintf(stderr, "bc5-direct: mapping 0x%llx+0x%llx overlaps 0x%llx+0x%llx\n",
                         static_cast<unsigned long long>(cpu_va), static_cast<unsigned long long>(size),
                         static_cast<unsigned long long>(u.va), static_cast<unsigned long long>(u.size));
            return false;
        }
    }
    UserptrBo u;
    u.va = cpu_va;
    u.size = size;
    u.readonly = readonly;
    int rc = 0;
    if (readonly) {
        // Same flags as libdrm's helper plus READONLY (amdgpu_drm.h): the kernel accepts them
        // over r-- anonymous pages (probed on the BC-250, experiment 0016). NOT USABLE YET: the
        // raw ioctl hands back a GEM handle and libdrm's amdgpu_bo_import refuses KMS handles
        // (-EPERM), so the BO cannot enter an amdgpu_bo_list; a raw-handle BO list
        // (amdgpu_bo_list_create_raw) and a raw VA map are needed. Until then the host keeps
        // the guest's pages writable instead (KYTY_BC5_ALL_RW).
        drm_amdgpu_gem_userptr args{};
        args.addr = cpu_va;
        args.size = size;
        args.flags = AMDGPU_GEM_USERPTR_READONLY | AMDGPU_GEM_USERPTR_ANONONLY |
                     AMDGPU_GEM_USERPTR_REGISTER | AMDGPU_GEM_USERPTR_VALIDATE;
        rc = drmCommandWriteRead(impl_->fd, DRM_AMDGPU_GEM_USERPTR, &args, sizeof(args));
        if (rc == 0) {
            amdgpu_bo_import_result res{};
            rc = amdgpu_bo_import(impl_->dev, amdgpu_bo_handle_type_kms, args.handle, &res);
            u.bo = res.buf_handle;
        }
    } else {
        rc = amdgpu_create_bo_from_user_mem(impl_->dev, reinterpret_cast<void *>(cpu_va), size, &u.bo);
    }
    if (rc != 0) {
        std::fprintf(stderr, "bc5-direct: userptr%s 0x%llx+0x%llx failed: %d\n", readonly ? " (ro)" : "",
                     static_cast<unsigned long long>(cpu_va), static_cast<unsigned long long>(size), rc);
        return false;
    }
    if (readonly) {
        rc = amdgpu_bo_va_op_raw(impl_->dev, u.bo, 0, size, cpu_va,
                                 AMDGPU_VM_PAGE_READABLE | AMDGPU_VM_PAGE_EXECUTABLE, AMDGPU_VA_OP_MAP);
    } else {
        rc = amdgpu_bo_va_op(u.bo, 0, size, cpu_va, 0, AMDGPU_VA_OP_MAP);
    }
    if (rc != 0) {
        std::fprintf(stderr, "bc5-direct: va map 0x%llx+0x%llx failed: %d\n",
                     static_cast<unsigned long long>(cpu_va), static_cast<unsigned long long>(size), rc);
        amdgpu_bo_free(u.bo);
        return false;
    }
    impl_->userptrs.push_back(u);
    return true;
}

bool Device::unmap_userptr(std::uint64_t cpu_va) {
    std::lock_guard lock(impl_->mutex);
    for (auto it = impl_->userptrs.begin(); it != impl_->userptrs.end(); ++it) {
        if (it->va == cpu_va) {
            amdgpu_bo_va_op(it->bo, 0, it->size, it->va, 0, AMDGPU_VA_OP_UNMAP);
            amdgpu_bo_free(it->bo);
            impl_->userptrs.erase(it);
            return true;
        }
    }
    return false;
}

std::uint64_t Device::gds_shadow_va() const { return impl_->shadow ? Impl::kShadowVa : 0; }

std::vector<Mapping> Device::mappings() const {
    std::lock_guard lock(impl_->mutex);
    std::vector<Mapping> out;
    for (const auto &u : impl_->userptrs) out.push_back({u.va, u.size, u.readonly});
    return out;
}

namespace {

// Which type-3 packets of `src` survived the filter into `dst` (the filter NOPs in place).
void executed_offsets_of(std::span<const std::uint32_t> src, const std::uint32_t *dst,
                         std::vector<std::uint32_t> &out) {
    for (std::size_t i = 0; i < src.size();) {
        const std::uint32_t h = src[i];
        const std::uint32_t type = h >> 30;
        std::size_t len = 1;
        if (type == 3) {
            const std::uint32_t count = (h >> 16) & 0x3fff;
            len = count == 0x3fff ? 1 : count + 2;
            const std::uint32_t op_in = (h >> 8) & 0xff;
            const std::uint32_t op_out = (dst[i] >> 8) & 0xff;
            if (op_in != 0x10 && (dst[i] >> 30) == 3 && op_out != 0x10)
                out.push_back(static_cast<std::uint32_t>(i));
        } else if (type == 0) {
            len = ((h >> 16) & 0x3fff) + 2;
        } else if (type == 2) {
            len = 1;
        } else {
            break;
        }
        i += len;
    }
}

struct Piece {
    const std::uint32_t *src = nullptr;
    std::size_t n = 0;      // dwords
    std::size_t off = 0;    // dword offset in the scratch
    std::size_t padded = 0; // n rounded up to 8
    int depth = 0;
};

// INDIRECT_BUFFER / INDIRECT_BUFFER_CNST targets of an IB that lie inside the mapped ranges.
void nested_targets(std::span<const std::uint32_t> ib, const policy::FilterOptions &opt,
                    std::vector<std::pair<const std::uint32_t *, std::size_t>> &out) {
    for (std::size_t i = 0; i < ib.size();) {
        const std::uint32_t h = ib[i];
        const std::uint32_t type = h >> 30;
        std::size_t len = 1;
        if (type == 3 || type == 0) {
            const std::uint32_t count = (h >> 16) & 0x3fff;
            len = count == 0x3fff ? 1 : count + 2;
        }
        if (i + len > ib.size()) break;
        const std::uint32_t op = (h >> 8) & 0xff;
        if (type == 3 && (op == 0x3f || op == 0x33) && len >= 4) {
            const std::uint64_t a = (static_cast<std::uint64_t>(ib[i + 1]) & ~3ull) |
                                    (static_cast<std::uint64_t>(ib[i + 2] & 0xffu) << 32);
            const std::size_t n = ib[i + 3] & 0xfffffu;
            if (a != 0 && n != 0 && (!opt.mapped || opt.mapped(a, n * 4)))
                out.emplace_back(reinterpret_cast<const std::uint32_t *>(a), n);
        }
        i += len;
    }
}

} // namespace

SubmitResult Device::submit(std::span<const std::uint32_t> ib, const policy::FilterOptions &opt,
                            std::uint64_t timeout_ns) {
    SubmitResult r;
    std::lock_guard lock(impl_->mutex);
    if (wedged_) {
        r.rc = -1;
        return r;
    }
    if (ib.empty()) {
        r.rc = -2;
        return r;
    }
    // Layout: the IB first, then every INDIRECT_BUFFER target it (transitively) reaches, each
    // padded to 8 dwords with NOPs — the CP fetches IBs in 32-byte chunks and must never run
    // into what lies past a buffer (experiment 0016). The nested copies let the filter see the
    // console's compute rings, which are rings of INDIRECT_BUFFER packets (step e).
    std::vector<Piece> pieces;
    pieces.push_back({ib.data(), ib.size(), 0, (ib.size() + 7) & ~std::size_t{7}, 0});
    for (std::size_t k = 0; k < pieces.size() && pieces.size() < 64; ++k) {
        if (pieces[k].depth >= 3) continue;
        std::vector<std::pair<const std::uint32_t *, std::size_t>> targets;
        nested_targets(std::span<const std::uint32_t>(pieces[k].src, pieces[k].n), opt, targets);
        for (const auto &[src, n] : targets) {
            bool seen = false;
            for (const auto &q : pieces) seen = seen || (q.src == src && q.n == n);
            if (seen) continue;
            const Piece &last = pieces.back();
            pieces.push_back({src, n, last.off + last.padded, (n + 7) & ~std::size_t{7}, pieces[k].depth + 1});
        }
    }
    const Piece &last = pieces.back();
    const std::uint64_t bytes = (last.off + last.padded) * sizeof(std::uint32_t);
    if (!impl_->scratch_reserve(bytes)) {
        r.rc = -2;
        return r;
    }
    auto *dst = static_cast<std::uint32_t *>(impl_->scratch.cpu);
    for (std::size_t k = 0; k < pieces.size(); ++k) {
        const Piece &pc = pieces[k];
        policy::FilterStats st;
        policy::filter(policy::Policy::builtin(), std::span<const std::uint32_t>(pc.src, pc.n),
                       std::span<std::uint32_t>(dst + pc.off, pc.n), opt, k == 0 ? r.filter : st);
        for (std::size_t i = pc.n; i < pc.padded; ++i) dst[pc.off + i] = policy::kNop;
        std::vector<std::uint32_t> ex;
        executed_offsets_of(std::span<const std::uint32_t>(pc.src, pc.n), dst + pc.off, ex);
        if (k == 0) {
            r.executed_offsets = std::move(ex);
        } else {
            r.nested.push_back({reinterpret_cast<std::uint64_t>(pc.src),
                                static_cast<std::uint32_t>(pc.n), std::move(ex)});
        }
    }
    // Point the surviving INDIRECT_BUFFER packets at the scratch copies.
    for (const Piece &pc : pieces) {
        std::uint32_t *d = dst + pc.off;
        for (std::size_t i = 0; i < pc.n;) {
            const std::uint32_t h = d[i];
            const std::uint32_t type = h >> 30;
            std::size_t len = 1;
            if (type == 3 || type == 0) {
                const std::uint32_t count = (h >> 16) & 0x3fff;
                len = count == 0x3fff ? 1 : count + 2;
            }
            if (i + len > pc.n) break;
            const std::uint32_t op = (h >> 8) & 0xff;
            if (type == 3 && (op == 0x3f || op == 0x33) && len >= 4) {
                const std::uint64_t a = (static_cast<std::uint64_t>(d[i + 1]) & ~3ull) |
                                        (static_cast<std::uint64_t>(d[i + 2] & 0xffu) << 32);
                const std::size_t n = d[i + 3] & 0xfffffu;
                bool found = false;
                for (const Piece &q : pieces) {
                    if (reinterpret_cast<std::uint64_t>(q.src) == a && q.n == n) {
                        const std::uint64_t va = impl_->scratch.va + q.off * 4;
                        d[i + 1] = static_cast<std::uint32_t>(va & 0xffffffffu);
                        d[i + 2] = static_cast<std::uint32_t>((va >> 32) & 0xffffu);
                        found = true;
                        break;
                    }
                }
                if (!found) { // an unmapped or over-deep target: never let the CP follow it
                    for (std::size_t q = 0; q < len; ++q) d[i + q] = policy::kNop;
                }
            }
            i += len;
        }
    }
    const std::size_t padded = pieces[0].padded;

    std::vector<amdgpu_bo_handle> bos;
    bos.reserve(impl_->userptrs.size() + 1);
    bos.push_back(impl_->scratch.bo);
    if (impl_->gds) bos.push_back(impl_->gds);
    if (impl_->oa) bos.push_back(impl_->oa);
    if (impl_->shadow) bos.push_back(impl_->shadow);
    if (impl_->gws) bos.push_back(impl_->gws);
    if (include_mappings_) {
        for (const auto &u : impl_->userptrs) bos.push_back(u.bo);
    }
    amdgpu_bo_list_handle list = nullptr;
    r.rc = amdgpu_bo_list_create(impl_->dev, static_cast<std::uint32_t>(bos.size()), bos.data(),
                                 nullptr, &list);
    if (r.rc != 0) return r;

    amdgpu_cs_ib_info ib_info{};
    ib_info.ib_mc_address = impl_->scratch.va;
    ib_info.size = static_cast<std::uint32_t>(padded);
    amdgpu_cs_request req{};
    req.ip_type = AMDGPU_HW_IP_GFX;
    req.ring = 0;
    req.resources = list;
    req.number_of_ibs = 1;
    req.ibs = &ib_info;

    const double t0 = now_ms();
    r.rc = amdgpu_cs_submit(impl_->ctx, 0, &req, 1);
    std::uint32_t expired = 0;
    r.seq_no = req.seq_no;
    if (r.rc == 0) {
        amdgpu_cs_fence fence{};
        fence.context = impl_->ctx;
        fence.ip_type = AMDGPU_HW_IP_GFX;
        fence.ring = 0;
        fence.fence = req.seq_no;
        r.rc = amdgpu_cs_query_fence_status(&fence, timeout_ns, 0, &expired);
        if (r.rc == 0 && !expired) {
            r.timed_out = true;
            wedged_ = true;
#ifdef AMDGPU_INFO_GPUVM_FAULT
            // A shader-side fault is what usually sits behind a timeout (experiment 0016, step
            // d): the kernel keeps the last VM fault per process; it names the page to map.
            drm_amdgpu_info_gpuvm_fault fault{};
            if (amdgpu_query_info(impl_->dev, AMDGPU_INFO_GPUVM_FAULT, sizeof(fault), &fault) == 0) {
                r.fault_addr = fault.addr;
                r.fault_status = fault.status;
            }
#endif
        }
    }
    r.submit_ms = now_ms() - t0;
    amdgpu_bo_list_destroy(list);
    submits_++;
    r.ok = r.rc == 0 && expired != 0;
    return r;
}

} // namespace bc5::direct
