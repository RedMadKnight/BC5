// SPDX-License-Identifier: GPL-2.0-only
// Experiment 0359: the job-arena fix for the second title (PPSA03671) — a TEMPORARY game-code workaround.
//
// What it is (experiments 0358, F447–F454): at the end of a frame the title's main thread ("the owner" of its job
// system) waits for a job and, while waiting, runs pending jobs itself. One kind of job looks its per-thread frame
// arena up by the thread's worker slots in thread-local storage; the owner is never a registered worker, so on the
// owner that lookup yields a null arena and the job dereferences it (eboot.bin+0x3d7eca0). The title's other inline
// path (the "override window") sets the special index and a stack arena around the call and the lookup honours
// them; the owner's help loop does not. On the console the race is won by the workers, which take the job before
// the owner gets to it; on this host it is lost at the fight because the box's cores are saturated (F454).
//
// The fix: the owner's help call `call [r15+0x80]` (eboot.bin+0x3cca87b, 7 bytes) is redirected through an 8-byte
// slot in a padding cave (eboot.bin+0x3cca4c8, eight int3 after a __stack_chk_fail stub) to a host hook, which wraps
// the title's own call in the title's own override window (the special index into the thread's slot, a stack arena
// built as the title builds it into image+0xb064018) and restores both after. Nothing else of the title changes.
//
// It is a change to the title's code, kept behind a per-title switch (input.cfg JobArenaFix.<TITLE_ID>=on|off,
// the Emulation menu's "Game fixes"), and is to be REMOVED once the host's throughput at the fight is fixed
// (docs/HANDOFF.md Q24). This header holds the pure parts (constants, the encoding, the arena layout) so they can be
// unit-tested; the host side (the hook, the writes) lives in the KytyPlus unit loader/gamePatch.cpp.
#pragma once

#include <array>
#include <cstddef>
#include <cstdint>
#include <cstring>

namespace bc5::job_arena_fix {

inline constexpr const char* kTitleId = "PPSA03671";

// The call site in the owner's help loop and the slot cave, as offsets from the image base.
inline constexpr std::uint64_t kSiteOffset = 0x3cca87b;
inline constexpr std::uint64_t kSlotOffset = 0x3cca4c8;
// The title's globals the override window uses: the special index (N, the worker count) and the override arena.
inline constexpr std::uint64_t kSpecialIndexOffset  = 0xb064020;
inline constexpr std::uint64_t kOverrideArenaOffset = 0xb064018;
// The thread-local worker index the job's arena lookup reads (an offset from the thread control block).
inline constexpr std::int64_t kIndexSlotFromTcb = -0x104;
// The two constants the title's override window copies into its stack arena.
inline constexpr std::uint64_t kArenaConstsOffset = 0x77f9c30; // 16 bytes
inline constexpr std::uint64_t kArenaTailOffset   = 0x7555574; // a pointer stored at +0x30

// The minimal expected bytes: the instruction at the site and the padding at the slot.
inline constexpr std::array<std::uint8_t, 7> kSiteExpected {0x41, 0xff, 0x97, 0x80, 0x00, 0x00, 0x00}; // call [r15+0x80]
inline constexpr std::array<std::uint8_t, 8> kSlotExpected {0xcc, 0xcc, 0xcc, 0xcc, 0xcc, 0xcc, 0xcc, 0xcc};

// The replacement at the site: call [rip+disp32] (6 bytes) through the slot, then a nop.
inline bool encode_site(std::uint64_t site, std::uint64_t slot, std::array<std::uint8_t, 7>* out) {
    const std::int64_t disp = static_cast<std::int64_t>(slot) - static_cast<std::int64_t>(site + 6);
    if (disp < INT32_MIN || disp > INT32_MAX) {
        return false;
    }
    const auto d = static_cast<std::uint32_t>(static_cast<std::int32_t>(disp));
    (*out)[0] = 0xff;
    (*out)[1] = 0x15;
    (*out)[2] = static_cast<std::uint8_t>(d & 0xffu);
    (*out)[3] = static_cast<std::uint8_t>((d >> 8u) & 0xffu);
    (*out)[4] = static_cast<std::uint8_t>((d >> 16u) & 0xffu);
    (*out)[5] = static_cast<std::uint8_t>((d >> 24u) & 0xffu);
    (*out)[6] = 0x90;
    return true;
}

inline bool site_matches(const std::uint8_t* site) {
    return std::memcmp(site, kSiteExpected.data(), kSiteExpected.size()) == 0;
}

inline bool slot_matches(const std::uint8_t* slot) {
    return std::memcmp(slot, kSlotExpected.data(), kSlotExpected.size()) == 0;
}

// The stack arena the title's override window builds (0x38 bytes): the block, its size, 16 bytes of constants,
// a zero, 16 zero bytes, the tail pointer.
struct OverrideArena {
    std::uint64_t block;
    std::uint32_t size;
    std::uint8_t  consts[16];
    std::uint32_t zero;
    std::uint8_t  zeros[16];
    std::uint64_t tail;
};
static_assert(sizeof(OverrideArena) == 0x38, "the override arena is 0x38 bytes");
static_assert(offsetof(OverrideArena, size) == 0x8, "size at +0x8");
static_assert(offsetof(OverrideArena, consts) == 0xc, "constants at +0xc");
static_assert(offsetof(OverrideArena, zero) == 0x1c, "zero at +0x1c");
static_assert(offsetof(OverrideArena, zeros) == 0x20, "zeros at +0x20");
static_assert(offsetof(OverrideArena, tail) == 0x30, "tail at +0x30");

inline void build_arena(OverrideArena* arena, std::uint64_t block, std::uint32_t size, const std::uint8_t* consts16,
                        std::uint64_t tail) {
    arena->block = block;
    arena->size  = size;
    std::memcpy(arena->consts, consts16, sizeof(arena->consts));
    arena->zero = 0;
    std::memset(arena->zeros, 0, sizeof(arena->zeros));
    arena->tail = tail;
}

// Only a thread without a worker slot (the owner, index -1) needs the window; a registered worker keeps its own.
inline bool wrap_needed(std::int32_t index) {
    return index == -1;
}

} // namespace bc5::job_arena_fix
