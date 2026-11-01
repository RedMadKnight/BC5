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
inline constexpr unsigned      kMaxBoundUs      = 5000;

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

// Microseconds, 0 to kMaxBoundUs: the bound of a wait that only some pushes make.
inline unsigned parse_bound_us(const char* text, bool* invalid = nullptr) {
    const std::string_view s = text == nullptr ? std::string_view {} : std::string_view {text};
    if (invalid != nullptr) {
        *invalid = false;
    }
    if (s.empty()) {
        return 0;
    }
    char*               end   = nullptr;
    const unsigned long value = std::strtoul(text, &end, 10);
    if (*end != '\0' || s.front() == '-' || value > kMaxBoundUs) {
        if (invalid != nullptr) {
            *invalid = true;
        }
        return 0;
    }
    return static_cast<unsigned>(value);
}

// A nice value from -10 to 0, for the worker band; unset or anything else is 0.
inline int parse_worker_nice(const char* text, bool* invalid = nullptr) {
    const std::string_view s = text == nullptr ? std::string_view {} : std::string_view {text};
    if (invalid != nullptr) {
        *invalid = false;
    }
    if (s.empty()) {
        return 0;
    }
    char*      end   = nullptr;
    const long value = std::strtol(text, &end, 10);
    if (*end != '\0' || value < -10 || value > 0) {
        if (invalid != nullptr) {
            *invalid = true;
        }
        return 0;
    }
    return static_cast<int>(value);
}

// The five bands of a time in microseconds, for the catchers' counts.
inline int time_band(std::int64_t us) {
    return us < 50 ? 0 : us < 200 ? 1 : us < 500 ? 2 : us < 2000 ? 3 : 4;
}

// The second title's job handle and table (exp 0358 F449, read from its code; exp 0388 reads them only as catcher and
// candidate, for this title's "JobLoaderSema"): entry = bits 0-1, index = bits 2-30, generation = bits 32-63.
struct JobHandle {
    unsigned      entry;
    unsigned      index;
    std::uint32_t generation;
};

inline JobHandle decode_job(std::uint64_t handle) {
    return {static_cast<unsigned>(handle & 3u), static_cast<unsigned>((handle >> 2) & 0x1fffffffu),
            static_cast<std::uint32_t>(handle >> 32)};
}

inline constexpr std::uint64_t kImageBase      = 0x900000000;
inline constexpr std::uint64_t kJobTable       = 0xb0636d0;
inline constexpr std::uint64_t kJobEntryStride = 0x2f0;
inline constexpr std::uint64_t kJobObjects     = 0x288;
inline constexpr std::uint64_t kJobLive        = 0x294;
inline constexpr std::uint64_t kJobSema        = 0x298;
inline constexpr std::uint64_t kJobPending     = 0x2a0;
inline constexpr std::uint64_t kJobPendingN    = 0x2ac;
inline constexpr std::uint64_t kJobGeneration  = 0x2e0;
inline constexpr std::uint64_t kJobSize        = 0xc0;
inline constexpr std::uint64_t kJobStarted     = 0x90;
inline constexpr std::uint64_t kJobTotal       = 0x98;
inline constexpr std::uint64_t kCrashJobFn     = 0x4661e50;

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
