// SPDX-License-Identifier: GPL-2.0-only
// Experiment 0388: the job push wait (bc5/job_push_wait.hpp).
#include "bc5/job_push_wait.hpp"

#include <catch2/catch_test_macros.hpp>

#include <cstdint>
#include <map>

namespace {

using namespace bc5::job_push_wait;

constexpr std::uint64_t kBase = 0x900000000;
constexpr std::uint64_t kSem  = 0x7000;
constexpr std::uint64_t kList = 0x1000000000;
constexpr std::uint64_t kJobs = 0x1100000000;

struct Mem {
    std::map<std::uint64_t, std::uint64_t> m;

    [[nodiscard]] std::uint64_t u64(std::uint64_t a) const {
        const auto it = m.find(a);
        return it == m.end() ? 0 : it->second;
    }
    [[nodiscard]] std::uint32_t u32(std::uint64_t a) const { return static_cast<std::uint32_t>(u64(a)); }
    [[nodiscard]] int           i32(std::uint64_t a) const { return static_cast<int>(u64(a)); }
};

constexpr std::uint64_t entry_at(std::uint64_t k) {
    return kBase + kJobTable + k * kJobEntryStride;
}

constexpr std::uint64_t handle(std::uint64_t entry, std::uint64_t index, std::uint64_t generation) {
    return entry | (index << 2u) | (generation << 32u);
}

// One semaphore on entry 1, one pending job of the crash's kind, index 2, two of its four parts started.
Mem one_open_job() {
    Mem mem;
    const std::uint64_t e = entry_at(1);
    mem.m[e + kJobSema]       = kSem;
    mem.m[e + kJobPendingN]   = 1;
    mem.m[e + kJobPending]    = kList;
    mem.m[e + kJobGeneration] = 7;
    mem.m[e + kJobLive]       = 3;
    mem.m[e + kJobObjects]    = kJobs;
    mem.m[kList]              = handle(1, 2, 7);
    const std::uint64_t job   = kJobs + 2 * kJobSize;
    mem.m[job + 0x28]         = kBase + kCrashJobFn;
    mem.m[job + kJobStarted]  = 2;
    mem.m[job + kJobTotal]    = 4;
    return mem;
}

TEST_CASE("the wait runs only for the known title and code, and the switch turns it off", "[job_push_wait]") {
    CHECK(wait_on(true, true, nullptr));
    CHECK(wait_on(true, true, ""));
    CHECK(wait_on(true, true, "1"));
    CHECK_FALSE(wait_on(true, true, "0"));
    CHECK_FALSE(wait_on(false, true, nullptr));
    CHECK_FALSE(wait_on(true, false, nullptr));
    CHECK(wait_on(true, true, "00")); // only the exact 0 is off, as the fix's switch reads its first character
}

TEST_CASE("a handle splits into entry, index and generation", "[job_push_wait]") {
    const auto h = decode_job(handle(2, 0x1fffffff, 0xdeadbeef));
    CHECK(h.entry == 2);
    CHECK(h.index == 0x1fffffff);
    CHECK(h.generation == 0xdeadbeef);
}

TEST_CASE("an open job of the crash's kind is found", "[job_push_wait]") {
    CHECK(target_job_open(one_open_job(), kBase, kSem));
}

TEST_CASE("no wait for another semaphore, no job or a finished job", "[job_push_wait]") {
    Mem mem = one_open_job();
    CHECK_FALSE(target_job_open(mem, kBase, kSem + 8));
    Mem none = one_open_job();
    none.m[entry_at(1) + kJobPendingN] = 0;
    CHECK_FALSE(target_job_open(none, kBase, kSem));
    Mem done = one_open_job();
    done.m[kJobs + 2 * kJobSize + kJobStarted] = 4;
    CHECK_FALSE(target_job_open(done, kBase, kSem));
}

TEST_CASE("a job of another kind, a stale handle or a dead index does not count", "[job_push_wait]") {
    Mem other = one_open_job();
    other.m[kJobs + 2 * kJobSize + 0x28] = kBase + kCrashJobFn + 8;
    CHECK_FALSE(target_job_open(other, kBase, kSem));
    Mem stale = one_open_job();
    stale.m[entry_at(1) + kJobGeneration] = 8;
    CHECK_FALSE(target_job_open(stale, kBase, kSem));
    Mem dead = one_open_job();
    dead.m[entry_at(1) + kJobLive] = 2;
    CHECK_FALSE(target_job_open(dead, kBase, kSem));
    Mem empty = one_open_job();
    empty.m[kList] = 0;
    CHECK_FALSE(target_job_open(empty, kBase, kSem));
}

TEST_CASE("the look stops at 64 pending jobs", "[job_push_wait]") {
    Mem mem = one_open_job();
    mem.m[entry_at(1) + kJobPendingN] = 1000;
    for (std::uint64_t i = 0; i < 70; i++) {
        mem.m[kList + i * 8] = 0;
    }
    mem.m[kList + 64 * 8] = handle(1, 2, 7);
    CHECK_FALSE(target_job_open(mem, kBase, kSem));
    mem.m[kList + 63 * 8] = handle(1, 2, 7);
    CHECK(target_job_open(mem, kBase, kSem));
}

TEST_CASE("the image base comes from the caller", "[job_push_wait]") {
    CHECK_FALSE(target_job_open(one_open_job(), kBase + 0x1000, kSem));
}

} // namespace
