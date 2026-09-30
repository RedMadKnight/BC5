// SPDX-License-Identifier: GPL-2.0-only
// Direct submission (ADR 0005): the game's memory mapped 1:1 as userptr BOs, its command buffers
// copied through the policy filter into a scratch IB and submitted on the GFX ring with a fence.
// Only built with BC5_WITH_AMDGPU. Nothing here submits unless the host calls submit(); hosts
// keep that behind an explicit switch (hard rule 5).
#pragma once

#include "bc5/policy.hpp"

#include <cstdint>
#include <memory>
#include <span>
#include <string>
#include <vector>

namespace bc5::direct {

struct SubmitResult {
    bool ok = false;
    int rc = 0;            // libdrm / ioctl return code when not ok
    bool timed_out = false; // fence did not signal within the timeout
    double submit_ms = 0;   // submit + fence wall clock
    policy::FilterStats filter;
};

struct Mapping {
    std::uint64_t va = 0;
    std::uint64_t size = 0;
};

// Diagnostic knobs (experiment 0016 bisection); the defaults are the intended configuration.
struct OpenOptions {
    bool deduplicate_device = false; // true: plain amdgpu_device_initialize (shares a device already open in the process)
    bool legacy_scratch_va = false;  // true: scratch VA from libdrm's allocator instead of the fixed 16 TiB
};

class Device {
public:
    // Opens a render node; nullptr on failure (message on stderr).
    static std::unique_ptr<Device> open(const std::string &node, const OpenOptions &opts = {});
    ~Device();
    Device(const Device &) = delete;
    Device &operator=(const Device &) = delete;

    // Maps [cpu_va, cpu_va + size) — page-aligned host memory of this process — into the GPU at
    // the same address. Overlapping or duplicate ranges are rejected.
    bool map_userptr(std::uint64_t cpu_va, std::uint64_t size);
    bool unmap_userptr(std::uint64_t cpu_va);
    std::vector<Mapping> mappings() const;

    // Filters `ib` into a scratch IB and submits it on the GFX ring with every mapping in the BO
    // list; waits for the fence up to `timeout_ns`. After a timeout the device refuses further
    // submits (a wedged ring is not retried; ADR 0005 §3).
    SubmitResult submit(std::span<const std::uint32_t> ib, const policy::FilterOptions &opt,
                        std::uint64_t timeout_ns);

    bool wedged() const { return wedged_; }
    std::uint64_t submits() const { return submits_; }

    // Staging knob: when false, submits carry only the scratch IB in their BO list (the userptr
    // mappings stay mapped but are not validated per submit). Default true.
    void set_include_mappings(bool v) { include_mappings_ = v; }

private:
    Device() = default;
    struct Impl;
    std::unique_ptr<Impl> impl_;
    bool wedged_ = false;
    bool include_mappings_ = true;
    std::uint64_t submits_ = 0;
};

} // namespace bc5::direct
