// SPDX-License-Identifier: GPL-2.0-only
#include "bc5/direct.hpp"

#include <amdgpu.h>
#include <amdgpu_drm.h>
#include <fcntl.h>
#include <linux/udmabuf.h>
#include <sys/ioctl.h>
#include <xf86drm.h>
#include <unistd.h>

#include <algorithm>
#include <atomic>
#include <cerrno>
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

// ADR 0006: an imported memfd range and its mappings.
struct SharedBo {
    std::uint32_t id = 0;
    amdgpu_bo_handle bo = nullptr;
    std::uint64_t size = 0;
};
struct SharedMap {
    std::uint64_t va = 0;
    std::uint64_t size = 0;
    std::uint64_t bo_offset = 0;
    std::uint32_t id = 0;
    amdgpu_bo_handle bo = nullptr;
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
    std::vector<SharedBo> shared;
    std::vector<SharedMap> shared_maps;
    std::uint32_t next_shared_id = 1;
    int udmabuf_fd = -1;
    // The BO list of a submission with draws names every mapping; it is kept between
    // submissions while the set of mapped BOs stays the same (experiment 0022).
    std::uint64_t list_gen = 0;
    amdgpu_bo_list_handle full_list = nullptr;
    std::uint64_t full_list_gen = 0;
    bool full_list_gds = false;
    std::uint32_t full_list_count = 0;
    amdgpu_bo_handle gds = nullptr; // OpenOptions::gds_kib
    amdgpu_bo_handle oa = nullptr;  // OpenOptions::oa_count
    amdgpu_bo_handle gws = nullptr; // OpenOptions::gws_count
    amdgpu_bo_handle shadow = nullptr; // OpenOptions::gds_shadow, 64 KiB at kShadowVa
    void *shadow_cpu = nullptr;
    state_stack::Tracker tracker; // Device::set_state_stack
    static constexpr std::uint64_t kShadowVa = 0x1000'0400'0000ull; // 64 MiB above the scratch
    std::mutex mutex;

    // The scratch IB lives at a fixed GPU VA of 16 TiB: inside the 48-bit range the CP can
    // address (an IB address above 2^48 is truncated by the CP — the kernel-half "high VA" range
    // hung the BC-250, experiment 0016), above every guest window a track-B host maps 1:1
    // (< 1 TiB) and away from libdrm's low-range allocator (0x100000000+).
    static constexpr std::uint64_t kScratchVa = 0x1000'0000'0000ull;
    OpenOptions opts;

    // One scratch buffer per job in flight (Device::set_async); synchronous submission uses
    // slot 0 only. Each slot has its own VA, 4 GiB apart.
    static constexpr int kSlots = 16;
    ScratchBo slots[kSlots];
    int cur = 0;
    std::atomic<std::uint64_t> slot_seq[kSlots] = {}; // sequence number of the job using the slot, 0 = free
    std::atomic<std::uint64_t> last_seq{0};            // the job queued last (Device::wait_idle)

    bool scratch_reserve(std::uint64_t bytes) {
        ScratchBo &scratch = slots[cur];
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
            const std::uint64_t slot_va = kScratchVa + (static_cast<std::uint64_t>(cur) << 32);
            if (amdgpu_query_info(dev, AMDGPU_INFO_DEV_INFO, sizeof(dev_info), &dev_info) != 0 ||
                slot_va + size > dev_info.virtual_address_max) {
                std::fprintf(stderr, "bc5-direct: scratch VA 0x%llx outside the device's range\n",
                             static_cast<unsigned long long>(kScratchVa));
                return false;
            }
            scratch.va = slot_va;
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
        ScratchBo &scratch = slots[cur];
        if (scratch.cpu) amdgpu_bo_cpu_unmap(scratch.bo);
        if (scratch.va && scratch.bo) amdgpu_bo_va_op_raw(dev, scratch.bo, 0, scratch.size, scratch.va, 0, AMDGPU_VA_OP_UNMAP);
        if (scratch.va_handle) amdgpu_va_range_free(scratch.va_handle);
        if (scratch.bo) amdgpu_bo_free(scratch.bo);
        scratch = ScratchBo{};
        list_gen++; // a kept BO list names the old scratch BO
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
                d->impl_->shadow_cpu = cpu; // kept mapped: snapshots are read through it
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
    if (impl_->full_list) amdgpu_bo_list_destroy(impl_->full_list);
    for (auto &u : impl_->userptrs) {
        amdgpu_bo_va_op(u.bo, 0, u.size, u.va, 0, AMDGPU_VA_OP_UNMAP);
        amdgpu_bo_free(u.bo);
    }
    for (auto &m : impl_->shared_maps)
        amdgpu_bo_va_op_raw(impl_->dev, m.bo, m.bo_offset, m.size, m.va, 0, AMDGPU_VA_OP_UNMAP);
    for (auto &b : impl_->shared) amdgpu_bo_free(b.bo);
    if (impl_->udmabuf_fd >= 0) close(impl_->udmabuf_fd);
    for (int k = 0; k < Impl::kSlots; ++k) {
        impl_->cur = k;
        impl_->scratch_free();
    }
    if (impl_->gds) amdgpu_bo_free(impl_->gds);
    if (impl_->oa) amdgpu_bo_free(impl_->oa);
    if (impl_->shadow) {
        if (impl_->shadow_cpu) amdgpu_bo_cpu_unmap(impl_->shadow);
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
    impl_->list_gen++;
    return true;
}

bool Device::unmap_userptr(std::uint64_t cpu_va) {
    std::lock_guard lock(impl_->mutex);
    for (auto it = impl_->userptrs.begin(); it != impl_->userptrs.end(); ++it) {
        if (it->va == cpu_va) {
            amdgpu_bo_va_op(it->bo, 0, it->size, it->va, 0, AMDGPU_VA_OP_UNMAP);
            amdgpu_bo_free(it->bo);
            impl_->userptrs.erase(it);
            impl_->list_gen++;
            return true;
        }
    }
    return false;
}

std::uint64_t Device::gds_shadow_va() const { return impl_->shadow ? Impl::kShadowVa : 0; }
volatile std::uint32_t *Device::gds_shadow_cpu() const {
    return static_cast<volatile std::uint32_t *>(impl_->shadow_cpu);
}

std::vector<Mapping> Device::mappings() const {
    std::lock_guard lock(impl_->mutex);
    std::vector<Mapping> out;
    for (const auto &u : impl_->userptrs) out.push_back({u.va, u.size, u.readonly, false});
    for (const auto &m : impl_->shared_maps) out.push_back({m.va, m.size, false, true});
    return out;
}

std::uint32_t Device::import_memfd(int memfd, std::uint64_t offset, std::uint64_t size) {
    std::lock_guard lock(impl_->mutex);
    if (size == 0 || (offset & 0xfff) != 0 || (size & 0xfff) != 0) return 0;
    if (impl_->udmabuf_fd < 0) {
        impl_->udmabuf_fd = ::open("/dev/udmabuf", O_RDWR | O_CLOEXEC);
        if (impl_->udmabuf_fd < 0) {
            std::fprintf(stderr, "bc5-direct: /dev/udmabuf: %s\n", std::strerror(errno));
            return 0;
        }
    }
    udmabuf_create c{};
    c.memfd = static_cast<std::uint32_t>(memfd);
    c.flags = UDMABUF_FLAGS_CLOEXEC;
    c.offset = offset;
    c.size = size;
    const int buf = ioctl(impl_->udmabuf_fd, UDMABUF_CREATE, &c);
    if (buf < 0) {
        std::fprintf(stderr, "bc5-direct: UDMABUF_CREATE 0x%llx+0x%llx: %s\n",
                     static_cast<unsigned long long>(offset), static_cast<unsigned long long>(size),
                     std::strerror(errno));
        return 0;
    }
    amdgpu_bo_import_result res{};
    const int rc = amdgpu_bo_import(impl_->dev, amdgpu_bo_handle_type_dma_buf_fd,
                                    static_cast<std::uint32_t>(buf), &res);
    close(buf); // the BO keeps the dma-buf
    if (rc != 0) {
        std::fprintf(stderr, "bc5-direct: dma-buf import 0x%llx+0x%llx: %d\n",
                     static_cast<unsigned long long>(offset), static_cast<unsigned long long>(size), rc);
        return 0;
    }
    SharedBo b;
    b.id = impl_->next_shared_id++;
    b.bo = res.buf_handle;
    b.size = size;
    impl_->shared.push_back(b);
    return b.id;
}

bool Device::map_shared(std::uint32_t id, std::uint64_t bo_offset, std::uint64_t size, std::uint64_t gpu_va) {
    std::lock_guard lock(impl_->mutex);
    if (size == 0 || ((bo_offset | size | gpu_va) & 0xfff) != 0) return false;
    const SharedBo *b = nullptr;
    for (const auto &x : impl_->shared) {
        if (x.id == id) b = &x;
    }
    if (b == nullptr || bo_offset + size > b->size) return false;
    const int rc = amdgpu_bo_va_op_raw(impl_->dev, b->bo, bo_offset, size, gpu_va,
                                       AMDGPU_VM_PAGE_READABLE | AMDGPU_VM_PAGE_WRITEABLE |
                                           AMDGPU_VM_PAGE_EXECUTABLE,
                                       AMDGPU_VA_OP_MAP);
    if (rc != 0) {
        std::fprintf(stderr, "bc5-direct: shared map at 0x%llx+0x%llx: %d\n",
                     static_cast<unsigned long long>(gpu_va), static_cast<unsigned long long>(size), rc);
        return false;
    }
    impl_->shared_maps.push_back({gpu_va, size, bo_offset, id, b->bo});
    impl_->list_gen++;
    return true;
}

bool Device::unmap_shared(std::uint64_t gpu_va) {
    std::lock_guard lock(impl_->mutex);
    for (auto it = impl_->shared_maps.begin(); it != impl_->shared_maps.end(); ++it) {
        if (it->va != gpu_va) continue;
        amdgpu_bo_va_op_raw(impl_->dev, it->bo, it->bo_offset, it->size, it->va, 0, AMDGPU_VA_OP_UNMAP);
        impl_->shared_maps.erase(it);
        impl_->list_gen++;
        return true;
    }
    return false;
}

bool Device::free_shared(std::uint32_t id) {
    std::lock_guard lock(impl_->mutex);
    for (auto b = impl_->shared.begin(); b != impl_->shared.end(); ++b) {
        if (b->id != id) continue;
        for (auto it = impl_->shared_maps.begin(); it != impl_->shared_maps.end();) {
            if (it->id == id) {
                amdgpu_bo_va_op_raw(impl_->dev, it->bo, it->bo_offset, it->size, it->va, 0, AMDGPU_VA_OP_UNMAP);
                it = impl_->shared_maps.erase(it);
            } else {
                ++it;
            }
        }
        // a kept list would hold the BO (and its pages) alive
        if (impl_->full_list) {
            amdgpu_bo_list_destroy(impl_->full_list);
            impl_->full_list = nullptr;
        }
        amdgpu_bo_free(b->bo);
        impl_->shared.erase(b);
        impl_->list_gen++;
        return true;
    }
    return false;
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

// Does a filtered IB still hold a draw or a dispatch?
bool has_draw_or_dispatch(const std::uint32_t *d, std::size_t n) {
    for (std::size_t i = 0; i < n;) {
        const std::uint32_t h = d[i];
        const std::uint32_t type = h >> 30;
        const std::uint32_t count = (h >> 16) & 0x3fff;
        std::size_t len = 1;
        if (type == 3 || type == 0) len = count == 0x3fff ? 1 : count + 2;
        if (type == 3 && count != 0x3fff &&
            policy::is_draw_or_dispatch(static_cast<std::uint8_t>((h >> 8) & 0xff)))
            return true;
        i += len;
    }
    return false;
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
                            std::uint64_t timeout_ns, bool with_gds) {
    SubmitResult r;
    std::lock_guard lock(impl_->mutex);
    if (async_) {
        impl_->cur = (impl_->cur + 1) % Impl::kSlots;
        if (impl_->slot_seq[impl_->cur].load() != 0) { // the host lets fewer jobs fly than there are slots
            r.rc = -EBUSY;
            return r;
        }
    } else {
        impl_->cur = 0;
    }
    const double t_enter = now_ms();
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
    const std::size_t pro = opt.prologue.size();
    const std::size_t pro_padded = (pro + 7) & ~std::size_t{7};
    const std::size_t epi = opt.epilogue.size();
    // The IB itself is filtered into a vector first: the state-stack emulation may grow it
    // (a CLEAR_STATE pop becomes the SET_CONTEXT_REG packets of the saved context), and the
    // nested copies are laid out behind what will actually be executed.
    // Short lists: the operands the filter accepts are recorded, for the BO list of an IB
    // without draws and dispatches.
    const bool short_possible = short_lists_ && include_mappings_ && static_cast<bool>(opt.mapped);
    std::vector<std::pair<std::uint64_t, std::uint64_t>> touched;
    policy::FilterOptions fopt = opt;
    if (short_possible) {
        fopt.mapped = [&opt, &touched](std::uint64_t a, std::uint64_t bytes) {
            const bool ok = opt.mapped(a, bytes);
            if (ok) touched.emplace_back(a, bytes);
            return ok;
        };
    }
    std::vector<std::uint32_t> main_out(ib.size());
    policy::filter(policy::Policy::builtin(), ib, main_out, fopt, r.filter);
    executed_offsets_of(ib, main_out.data(), r.executed_offsets);
    if (state_stack_ && opt.mapped) {
        main_out = impl_->tracker.apply(ib, main_out, opt.mapped, r.state_stack);
    }
    // The CU mask for registers loaded from memory (phase 3 step f): a SET_SH_REG after the load.
    if (opt.cu_mask != 0xffffffffu && opt.mapped) {
        main_out = cu_tables::apply(main_out, opt.cu_mask, opt.mapped, r.cu_tables);
    }
    if (dma_idle_) {
        // PKT3(DMA_DATA, 5, 0); CP_SYNC | SRC_SEL and DST_SEL "address using L2"; no addresses;
        // zero bytes — as si_emit_cp_dma(sctx, cs, 0, 0, 0, CP_DMA_SYNC) emits it (Mesa 0866ae7).
        main_out.insert(main_out.end(), {0xC0055000u, 0xE0300000u, 0u, 0u, 0u, 0u, 0u});
    }
    const std::size_t main_n = main_out.size();
    pieces.push_back({ib.data(), ib.size(), pro_padded, (main_n + epi + 7) & ~std::size_t{7}, 0});
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
    auto *dst = static_cast<std::uint32_t *>(impl_->slots[impl_->cur].cpu);
    for (std::size_t i = 0; i < pro; ++i) dst[i] = opt.prologue[i];
    for (std::size_t i = pro; i < pro_padded; ++i) dst[i] = policy::kNop;
    for (std::size_t k = 0; k < pieces.size(); ++k) {
        const Piece &pc = pieces[k];
        if (k == 0) { // filtered above; the epilogue sits between the IB and its padding
            for (std::size_t i = 0; i < main_n; ++i) dst[pc.off + i] = main_out[i];
            for (std::size_t i = main_n; i < pc.padded; ++i) dst[pc.off + i] = policy::kNop;
            for (std::size_t i = 0; i < epi; ++i) dst[pc.off + main_n + i] = opt.epilogue[i];
            continue;
        }
        // nested IBs: no statistics samples (their slots belong to the main IB)
        policy::FilterStats st;
        policy::FilterOptions nested_opt = fopt;
        nested_opt.stat_sample_va = 0;
        policy::filter(policy::Policy::builtin(), std::span<const std::uint32_t>(pc.src, pc.n),
                       std::span<std::uint32_t>(dst + pc.off, pc.n), nested_opt, st);
        for (std::size_t i = pc.n; i < pc.padded; ++i) dst[pc.off + i] = policy::kNop;
        std::vector<std::uint32_t> ex;
        executed_offsets_of(std::span<const std::uint32_t>(pc.src, pc.n), dst + pc.off, ex);
        r.nested.push_back({reinterpret_cast<std::uint64_t>(pc.src),
                            static_cast<std::uint32_t>(pc.n), std::move(ex)});
    }
    // Point the surviving INDIRECT_BUFFER packets at the scratch copies.
    for (std::size_t k = 0; k < pieces.size(); ++k) {
        const Piece &pc = pieces[k];
        std::uint32_t *d = dst + pc.off;
        const std::size_t pc_n = k == 0 ? main_n : pc.n;
        for (std::size_t i = 0; i < pc_n;) {
            const std::uint32_t h = d[i];
            const std::uint32_t type = h >> 30;
            std::size_t len = 1;
            if (type == 3 || type == 0) {
                const std::uint32_t count = (h >> 16) & 0x3fff;
                len = count == 0x3fff ? 1 : count + 2;
            }
            if (i + len > pc_n) break;
            const std::uint32_t op = (h >> 8) & 0xff;
            if (type == 3 && (op == 0x3f || op == 0x33) && len >= 4) {
                const std::uint64_t a = (static_cast<std::uint64_t>(d[i + 1]) & ~3ull) |
                                        (static_cast<std::uint64_t>(d[i + 2] & 0xffu) << 32);
                const std::size_t n = d[i + 3] & 0xfffffu;
                bool found = false;
                for (const Piece &q : pieces) {
                    if (reinterpret_cast<std::uint64_t>(q.src) == a && q.n == n) {
                        const std::uint64_t va = impl_->slots[impl_->cur].va + q.off * 4;
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
    const std::size_t padded = pro_padded + pieces[0].padded; // the CP runs prologue then IB

    std::vector<amdgpu_bo_handle> bos;
    bos.reserve(impl_->userptrs.size() + 1);
    for (const auto &sl : impl_->slots) {
        if (sl.bo != nullptr) bos.push_back(sl.bo);
    }
    if (with_gds && impl_->gds) bos.push_back(impl_->gds);
    if (with_gds && impl_->oa) bos.push_back(impl_->oa);
    if (with_gds && impl_->gws) bos.push_back(impl_->gws);
    if (impl_->shadow) bos.push_back(impl_->shadow);
    bool draws = !short_possible;
    if (short_possible) {
        draws = has_draw_or_dispatch(dst + pieces[0].off, main_n);
        for (std::size_t k = 1; k < pieces.size() && !draws; ++k)
            draws = has_draw_or_dispatch(dst + pieces[k].off, pieces[k].n);
    }
    // Imported memfd ranges (ADR 0006): each BO once, however many addresses it is mapped at.
    auto add_shared = [&](amdgpu_bo_handle bo) {
        if (std::find(bos.begin(), bos.end(), bo) == bos.end()) bos.push_back(bo);
    };
    const bool full = include_mappings_ && draws;
    const bool kept = full && impl_->full_list != nullptr && impl_->full_list_gen == impl_->list_gen &&
                      impl_->full_list_gds == with_gds;
    if (kept) {
        // the list of the last submission with draws still names every mapping
    } else if (full) {
        for (const auto &u : impl_->userptrs) bos.push_back(u.bo);
        const std::size_t first_shared = bos.size();
        bos.reserve(bos.size() + impl_->shared.size());
        // every imported BO that is mapped somewhere; the maps are grouped by BO in practice,
        // so comparing with the last one added keeps this linear
        for (const auto &m : impl_->shared_maps) {
            if (bos.size() > first_shared && bos.back() == m.bo) continue;
            bool seen = false;
            for (std::size_t k = first_shared; k < bos.size() && !seen; ++k) seen = bos[k] == m.bo;
            if (!seen) bos.push_back(m.bo);
        }
    } else if (include_mappings_) {
        // Table operands are declared with a nominal size; the margins cover their real extent.
        constexpr std::uint64_t kBefore = 0x10000, kAfter = 0x20000;
        for (const auto &u : impl_->userptrs) {
            for (const auto &[a, span_bytes] : touched) {
                const std::uint64_t lo = a > kBefore ? a - kBefore : 0;
                const std::uint64_t hi = a + 2 * span_bytes + kAfter;
                if (u.va < hi && u.va + u.size > lo) {
                    bos.push_back(u.bo);
                    break;
                }
            }
        }
        for (const auto &m : impl_->shared_maps) {
            for (const auto &[a, span_bytes] : touched) {
                const std::uint64_t lo = a > kBefore ? a - kBefore : 0;
                const std::uint64_t hi = a + 2 * span_bytes + kAfter;
                if (m.va < hi && m.va + m.size > lo) {
                    add_shared(m.bo);
                    break;
                }
            }
        }
        r.short_list = true;
    }
    r.bo_count = kept ? impl_->full_list_count : static_cast<std::uint32_t>(bos.size());
    amdgpu_bo_list_handle list = nullptr;
    const double t_list = now_ms();
    r.prepare_ms = t_list - t_enter;
    if (kept) {
        list = impl_->full_list;
    } else {
        r.rc = amdgpu_bo_list_create(impl_->dev, static_cast<std::uint32_t>(bos.size()), bos.data(),
                                     nullptr, &list);
        if (r.rc == 0 && full) {
            if (impl_->full_list) amdgpu_bo_list_destroy(impl_->full_list);
            impl_->full_list = list;
            impl_->full_list_gen = impl_->list_gen;
            impl_->full_list_gds = with_gds;
            impl_->full_list_count = r.bo_count;
        }
    }
    r.list_ms = now_ms() - t_list;
    if (r.rc != 0) return r;

    amdgpu_cs_ib_info ib_info{};
    ib_info.ib_mc_address = impl_->slots[impl_->cur].va;
    ib_info.size = static_cast<std::uint32_t>(padded);
    amdgpu_cs_request req{};
    req.ip_type = AMDGPU_HW_IP_GFX;
    req.ring = 0;
    req.resources = list;
    req.number_of_ibs = 1;
    req.ibs = &ib_info;

    const double t0 = now_ms();
    r.rc = amdgpu_cs_submit(impl_->ctx, 0, &req, 1);
    r.cs_ms = now_ms() - t0;
    std::uint32_t expired = 0;
    r.seq_no = req.seq_no;
    if (async_) {
        r.slot = static_cast<std::uint32_t>(impl_->cur);
        r.pending = r.rc == 0;
        if (r.pending) {
            impl_->slot_seq[impl_->cur] = req.seq_no;
            impl_->last_seq = req.seq_no;
        }
        r.submit_ms = now_ms() - t0;
        if (list != impl_->full_list) amdgpu_bo_list_destroy(list);
        submits_++;
        r.ok = r.rc == 0;
        return r;
    }
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
    r.fence_ms = r.submit_ms - r.cs_ms;
    if (list != impl_->full_list) amdgpu_bo_list_destroy(list);
    submits_++;
    r.ok = r.rc == 0 && expired != 0;
    return r;
}

bool Device::wait_idle(std::uint64_t timeout_ns) {
    const std::uint64_t seq = impl_->last_seq.load();
    if (seq == 0) return true;
    amdgpu_cs_fence fence{};
    fence.context = impl_->ctx;
    fence.ip_type = AMDGPU_HW_IP_GFX;
    fence.ring = 0;
    fence.fence = seq;
    std::uint32_t expired = 0;
    return amdgpu_cs_query_fence_status(&fence, timeout_ns, 0, &expired) == 0 && expired != 0;
}

SubmitResult Device::finish(std::uint64_t seq_no, std::uint32_t slot, std::uint64_t timeout_ns) {
    // No device lock: the submitting thread may be preparing the next IB.
    SubmitResult r;
    r.seq_no = seq_no;
    r.slot = slot;
    const double t0 = now_ms();
    amdgpu_cs_fence fence{};
    fence.context = impl_->ctx;
    fence.ip_type = AMDGPU_HW_IP_GFX;
    fence.ring = 0;
    fence.fence = seq_no;
    std::uint32_t expired = 0;
    r.rc = amdgpu_cs_query_fence_status(&fence, timeout_ns, 0, &expired);
    if (r.rc == 0 && !expired) {
        r.timed_out = true;
        wedged_ = true;
#ifdef AMDGPU_INFO_GPUVM_FAULT
        drm_amdgpu_info_gpuvm_fault fault{};
        if (amdgpu_query_info(impl_->dev, AMDGPU_INFO_GPUVM_FAULT, sizeof(fault), &fault) == 0) {
            r.fault_addr = fault.addr;
            r.fault_status = fault.status;
        }
#endif
    }
    r.fence_ms = now_ms() - t0;
    r.ok = r.rc == 0 && expired != 0;
    if (r.ok && slot < static_cast<std::uint32_t>(Impl::kSlots)) impl_->slot_seq[slot] = 0;
    return r;
}

} // namespace bc5::direct
