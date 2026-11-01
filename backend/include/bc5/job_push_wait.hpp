// SPDX-License-Identifier: GPL-2.0-only
// Experiment 0388: the job push wait of the second title (PPSA03671), arm J — the pure parts.
//
// The main thread ("the owner") pushes a job and may then take it itself; one kind of job (the crash's, F444-F454) needs
// a worker's slots. After a push on the title's JobLoaderSema, while that semaphore's entry holds an open job of that
// kind, the main thread spins for at most kBoundUs, which leaves the job to the workers. No reason why that much time is
// enough is shown: most waits run out the bound with the job still open. It replaced exp 0359's job-arena fix.
// On by default for every title, off with KYTY_BC5_JOB_PUSH_WAIT=0. Its offsets belong to one build of one executable, so
// it runs only where the code at kSiteOffset is the known one; any other executable has no such table and is left alone.
// This header holds the constants and the look at the table, so they can be unit-tested; the host side lives in the
// KytyPlus units kernel/semaphore.cpp and loader/gamePatch.cpp.
#pragma once

#include <array>
#include <cstdint>
#include <cstring>

namespace bc5::job_push_wait {

inline constexpr std::int64_t kBoundUs = 2000;

// Offsets from the image base: the job table and the crash job's function.
inline constexpr std::uint64_t kJobTable   = 0xb0636d0;
inline constexpr std::uint64_t kCrashJobFn = 0x4661e50;
// The table's entries, and the fields of an entry and of a job.
inline constexpr std::uint64_t kJobEntries     = 3;
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
inline constexpr int           kMaxPending     = 64;

// A pending job's handle: bits 0-1 the entry, 2-30 the index, 32-63 the generation.
struct JobHandle {
    unsigned      entry;
    unsigned      index;
    std::uint32_t generation;
};

inline JobHandle decode_job(std::uint64_t handle) {
    return {static_cast<unsigned>(handle & 3u), static_cast<unsigned>((handle >> 2) & 0x1fffffffu),
            static_cast<std::uint32_t>(handle >> 32)};
}

// The code that names the build: the owner's help call, `call [r15+0x80]`.
inline constexpr std::uint64_t                kSiteOffset = 0x3cca87b;
inline constexpr std::array<std::uint8_t, 7> kSiteExpected {0x41, 0xff, 0x97, 0x80, 0x00, 0x00, 0x00};

// An image too small for these offsets is another executable: nothing there may be read.
inline bool image_holds(std::uint64_t image_size) {
    return image_size > kSiteOffset + kSiteExpected.size() && image_size > kJobTable + kJobEntries * kJobEntryStride;
}

inline bool site_matches(const std::uint8_t* site) {
    return std::memcmp(site, kSiteExpected.data(), kSiteExpected.size()) == 0;
}

// Whether the wait runs: the known code, and no off switch (the value of KYTY_BC5_JOB_PUSH_WAIT).
inline bool wait_on(bool code_ok, const char* off_switch) {
    return code_ok && !(off_switch != nullptr && off_switch[0] == '0' && off_switch[1] == 0);
}

// Whether the entry of semaphore `sem` holds a pending job of the crash's kind with work left. Mem reads the title's
// memory: u64(address), u32(address), i32(address).
template <class Mem>
bool target_job_open(const Mem& mem, std::uint64_t base, std::uint64_t sem) {
    const std::uint64_t table = base + kJobTable;
    for (std::uint64_t k = 0; k < kJobEntries; k++) {
        const std::uint64_t entry = table + k * kJobEntryStride;
        if (mem.u64(entry + kJobSema) != sem) {
            continue;
        }
        const int           pending = mem.i32(entry + kJobPendingN);
        const std::uint64_t list    = mem.u64(entry + kJobPending);
        for (int i = 0; list != 0 && i < pending && i < kMaxPending; i++) {
            const std::uint64_t handle = mem.u64(list + static_cast<std::uint64_t>(i) * 8);
            const JobHandle     id     = decode_job(handle);
            const std::uint64_t owner  = table + id.entry * kJobEntryStride;
            if (handle == 0 || mem.u32(owner + kJobGeneration) != id.generation || static_cast<int>(id.index) >= mem.i32(owner + kJobLive)) {
                continue;
            }
            const std::uint64_t job  = mem.u64(owner + kJobObjects) + id.index * kJobSize;
            bool                kind = false;
            for (std::uint64_t off = 0; off < kJobSize; off += 8) { // where the object keeps the function is not read yet
                kind = kind || mem.u64(job + off) == base + kCrashJobFn;
            }
            if (kind && mem.i32(job + kJobStarted) < mem.i32(job + kJobTotal)) {
                return true;
            }
        }
        return false;
    }
    return false;
}

} // namespace bc5::job_push_wait
