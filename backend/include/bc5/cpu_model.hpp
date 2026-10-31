// SPDX-License-Identifier: GPL-2.0-only
// Experiment 0388: the CPU the host shows the title, in place of the job-arena workaround (F444-F455).
//
// The host's default thread affinity is 0x7f, seven CPUs. The second title sizes its job system on a CPU count as
// N = min(max(cpus, 7) - 2, 8) (exp 0358), so seven gives 5 workers per entry. KytyPS5's sceKernelGetAvailableCpumask
// (src/libs/libKernel.cpp, 8c01d8e) and AnyPS5's DEFAULT_THREAD_AFFINITY (Pthread.hpp, 27c88a8; GPL-2.0-only) both give
// 0x1fff, thirteen CPUs. TODO(verify): neither is a console measurement, and that the title's count comes from the
// affinity mask is what the trace and the code read show.
// All of this is a private test candidate: each switch is default off, and off leaves the host as it was.
#pragma once

#include <bit>
#include <cstdint>
#include <cstdlib>
#include <string_view>

namespace bc5::cpu_model {

inline constexpr std::uint64_t kHostDefaultMask = 0x7f;
inline constexpr std::uint64_t kAvailableMask   = 0x1fff;
inline constexpr unsigned      kMaxSpinUs       = 500;

// unset, "" and "0" are off, "1" is on; anything else is off and marked invalid.
inline bool parse_flag(const char* text, bool* invalid = nullptr) {
    const std::string_view s = text == nullptr ? std::string_view {} : std::string_view {text};
    if (s == "1") {
        return true;
    }
    if (invalid != nullptr) {
        *invalid = !(s.empty() || s == "0");
    }
    return false;
}

// unset, "" and "0" keep the host's mask, "1" is the available mask, 0x<hex> a mask inside it.
inline std::uint64_t parse_mask(const char* text, bool* invalid = nullptr) {
    const std::string_view s = text == nullptr ? std::string_view {} : std::string_view {text};
    if (invalid != nullptr) {
        *invalid = false;
    }
    if (s.empty() || s == "0") {
        return kHostDefaultMask;
    }
    if (s == "1") {
        return kAvailableMask;
    }
    char*               end   = nullptr;
    const unsigned long value = s.starts_with("0x") ? std::strtoul(text, &end, 16) : 0;
    if (end == nullptr || *end != '\0' || value == 0 || (value & ~kAvailableMask) != 0) {
        if (invalid != nullptr) {
            *invalid = true;
        }
        return kHostDefaultMask;
    }
    return value;
}

// Microseconds, 0 to kMaxSpinUs; unset, empty or anything else is 0.
inline unsigned parse_spin_us(const char* text, bool* invalid = nullptr) {
    const std::string_view s = text == nullptr ? std::string_view {} : std::string_view {text};
    if (invalid != nullptr) {
        *invalid = false;
    }
    if (s.empty()) {
        return 0;
    }
    char*               end   = nullptr;
    const unsigned long value = std::strtoul(text, &end, 10);
    if (*end != '\0' || s.front() == '-' || value > kMaxSpinUs) {
        if (invalid != nullptr) {
            *invalid = true;
        }
        return 0;
    }
    return static_cast<unsigned>(value);
}

// A host CPU as one of the CPUs of the thread's guest mask (AnyPS5's GuestCpuFromHost).
inline int guest_cpu(unsigned host_cpu, std::uint64_t thread_mask, std::uint64_t available) {
    std::uint64_t mask = thread_mask & available;
    if (mask == 0) {
        mask = available;
    }
    for (unsigned skip = host_cpu % static_cast<unsigned>(std::popcount(mask)); skip != 0; --skip) {
        mask &= mask - 1;
    }
    return std::countr_zero(mask);
}

// The host mask for a guest mask: the same CPU numbers, or 0 for "leave the thread free" when the mask names every CPU
// the title sees or none of them.
inline std::uint64_t host_mask(std::uint64_t guest_mask, std::uint64_t available) {
    const std::uint64_t mask = guest_mask & available;
    return mask == available ? 0 : mask;
}

} // namespace bc5::cpu_model
