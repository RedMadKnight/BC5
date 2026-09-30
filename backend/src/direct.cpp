// SPDX-License-Identifier: GPL-2.0-only
#include "bc5/direct.hpp"

#include <amdgpu.h>
#include <amdgpu_drm.h>
#include <fcntl.h>
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
};

struct ScratchBo {
    amdgpu_bo_handle bo = nullptr;
    amdgpu_va_handle va_handle = nullptr;
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
    std::mutex mutex;

    bool scratch_reserve(std::uint64_t bytes) {
        if (scratch.bo != nullptr && scratch.size >= bytes) return true;
        scratch_free();
        std::uint64_t size = 1u << 20;
        while (size < bytes) size <<= 1;
        amdgpu_bo_alloc_request req{};
        req.alloc_size = size;
        req.phys_alignment = 4096;
        req.preferred_heap = AMDGPU_GEM_DOMAIN_GTT;
        if (amdgpu_bo_alloc(dev, &req, &scratch.bo) != 0) return false;
        if (amdgpu_va_range_alloc(dev, amdgpu_gpu_va_range_general, size, 4096, 0, &scratch.va,
                                  &scratch.va_handle, 0) != 0)
            return false;
        if (amdgpu_bo_va_op(scratch.bo, 0, size, scratch.va, 0, AMDGPU_VA_OP_MAP) != 0) return false;
        if (amdgpu_bo_cpu_map(scratch.bo, &scratch.cpu) != 0) return false;
        scratch.size = size;
        return true;
    }

    void scratch_free() {
        if (scratch.cpu) amdgpu_bo_cpu_unmap(scratch.bo);
        if (scratch.va) amdgpu_bo_va_op(scratch.bo, 0, scratch.size, scratch.va, 0, AMDGPU_VA_OP_UNMAP);
        if (scratch.va_handle) amdgpu_va_range_free(scratch.va_handle);
        if (scratch.bo) amdgpu_bo_free(scratch.bo);
        scratch = ScratchBo{};
    }
};

std::unique_ptr<Device> Device::open(const std::string &node) {
    std::unique_ptr<Device> d(new Device());
    d->impl_ = std::make_unique<Impl>();
    d->impl_->fd = ::open(node.c_str(), O_RDWR | O_CLOEXEC);
    if (d->impl_->fd < 0) {
        std::perror(node.c_str());
        return nullptr;
    }
    std::uint32_t major = 0, minor = 0;
    if (amdgpu_device_initialize(d->impl_->fd, &major, &minor, &d->impl_->dev) != 0) {
        std::fprintf(stderr, "bc5-direct: amdgpu_device_initialize failed on %s\n", node.c_str());
        return nullptr;
    }
    if (amdgpu_cs_ctx_create(d->impl_->dev, &d->impl_->ctx) != 0) {
        std::fprintf(stderr, "bc5-direct: amdgpu_cs_ctx_create failed\n");
        return nullptr;
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
    if (impl_->ctx) amdgpu_cs_ctx_free(impl_->ctx);
    if (impl_->dev) amdgpu_device_deinitialize(impl_->dev);
    if (impl_->fd >= 0) close(impl_->fd);
}

bool Device::map_userptr(std::uint64_t cpu_va, std::uint64_t size) {
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
    int rc = amdgpu_create_bo_from_user_mem(impl_->dev, reinterpret_cast<void *>(cpu_va), size, &u.bo);
    if (rc != 0) {
        std::fprintf(stderr, "bc5-direct: userptr 0x%llx+0x%llx failed: %d\n",
                     static_cast<unsigned long long>(cpu_va), static_cast<unsigned long long>(size), rc);
        return false;
    }
    rc = amdgpu_bo_va_op(u.bo, 0, size, cpu_va, 0, AMDGPU_VA_OP_MAP);
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

std::vector<Mapping> Device::mappings() const {
    std::lock_guard lock(impl_->mutex);
    std::vector<Mapping> out;
    for (const auto &u : impl_->userptrs) out.push_back({u.va, u.size});
    return out;
}

SubmitResult Device::submit(std::span<const std::uint32_t> ib, const policy::FilterOptions &opt,
                            std::uint64_t timeout_ns) {
    SubmitResult r;
    std::lock_guard lock(impl_->mutex);
    if (wedged_) {
        r.rc = -1;
        return r;
    }
    const std::uint64_t bytes = ib.size() * sizeof(std::uint32_t);
    if (ib.empty() || !impl_->scratch_reserve(bytes)) {
        r.rc = -2;
        return r;
    }
    auto *dst = static_cast<std::uint32_t *>(impl_->scratch.cpu);
    policy::filter(policy::Policy::builtin(), ib, std::span<std::uint32_t>(dst, ib.size()), opt,
                   r.filter);

    std::vector<amdgpu_bo_handle> bos;
    bos.reserve(impl_->userptrs.size() + 1);
    bos.push_back(impl_->scratch.bo);
    if (include_mappings_) {
        for (const auto &u : impl_->userptrs) bos.push_back(u.bo);
    }
    amdgpu_bo_list_handle list = nullptr;
    r.rc = amdgpu_bo_list_create(impl_->dev, static_cast<std::uint32_t>(bos.size()), bos.data(),
                                 nullptr, &list);
    if (r.rc != 0) return r;

    amdgpu_cs_ib_info ib_info{};
    ib_info.ib_mc_address = impl_->scratch.va;
    ib_info.size = static_cast<std::uint32_t>(ib.size());
    amdgpu_cs_request req{};
    req.ip_type = AMDGPU_HW_IP_GFX;
    req.ring = 0;
    req.resources = list;
    req.number_of_ibs = 1;
    req.ibs = &ib_info;

    const double t0 = now_ms();
    r.rc = amdgpu_cs_submit(impl_->ctx, 0, &req, 1);
    std::uint32_t expired = 0;
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
        }
    }
    r.submit_ms = now_ms() - t0;
    amdgpu_bo_list_destroy(list);
    submits_++;
    r.ok = r.rc == 0 && expired != 0;
    return r;
}

} // namespace bc5::direct
