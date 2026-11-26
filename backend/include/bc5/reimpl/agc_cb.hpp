// SPDX-License-Identifier: GPL-2.0-only
// Clean-room re-creation of libSceAgc (see src/reimpl/PROVENANCE.md): the guest-visible command
// buffer object every builder takes, the register pair, and the space-reservation helpers.
//
// Layouts here are per the original module's behaviour (clean-room description, see
// src/reimpl/PROVENANCE.md). Guest pointers are host pointers (the host maps guest memory 1:1).
#pragma once

#include <cstddef>
#include <cstdint>

namespace bc5::reimpl::agc {

// One register write: dword offset relative to its register space, and the value (8 bytes). The
// *RegisterDirect builders take it by value in one 64-bit register (low half = offset).
struct RegPair {
    std::uint32_t offset;
    std::uint32_t value;
};
static_assert(sizeof(RegPair) == 8);

struct CommandBuffer;

// Owner callback when a builder needs more room. `required_dwords` is the total that must fit,
// including `reserved_dwords`. It may move cursor/limit (e.g. chain to a new chunk).
using OutOfSpaceFn = bool (*)(CommandBuffer *cb, std::uint32_t required_dwords, void *user_data);

// The command-buffer object (0x38 bytes) owned by the caller.
struct CommandBuffer {
    std::uint32_t *begin;           // 0x00 start of the buffer
    std::uint32_t *buffer_end;      // 0x08 start + size rounded down to 4
    std::uint32_t *cursor;          // 0x10 next write position
    std::uint32_t *limit;           // 0x18 end of the writable space
    OutOfSpaceFn out_of_space;      // 0x20
    void *user_data;                // 0x28
    std::uint32_t reserved_dwords;  // 0x30 dwords at the end builders must leave free
    std::uint32_t padding;          // 0x34
};
static_assert(sizeof(CommandBuffer) == 0x38);
static_assert(offsetof(CommandBuffer, begin) == 0x00);
static_assert(offsetof(CommandBuffer, buffer_end) == 0x08);
static_assert(offsetof(CommandBuffer, cursor) == 0x10);
static_assert(offsetof(CommandBuffer, limit) == 0x18);
static_assert(offsetof(CommandBuffer, out_of_space) == 0x20);
static_assert(offsetof(CommandBuffer, user_data) == 0x28);
static_assert(offsetof(CommandBuffer, reserved_dwords) == 0x30);

// Initialise a command buffer over [buffer, buffer + size_bytes) the way the module's internal
// helper does: begin = cursor = buffer, end = limit = buffer + (size & ~3), no reserve; without a
// callback a default one is installed that raises a debug exception and reports failure.
void init_command_buffer(CommandBuffer *cb, void *buffer, std::uint64_t size_bytes,
                         OutOfSpaceFn callback, void *user_data);

// Free dwords: max(0, (limit - cursor) / 4 - reserved_dwords), cursor not yet aligned.
std::uint32_t free_dwords(const CommandBuffer *cb);

// Strict reservation: ensure n dwords are free (calling the callback once if not, honouring its
// result), then align the cursor up to 4 bytes, advance it by n dwords and return the old aligned
// position. nullptr on failure, nothing changed.
std::uint32_t *reserve_strict(CommandBuffer *cb, std::uint32_t n);

// Soft reservation: as strict but the callback's result is ignored (free space is re-checked) and
// the cursor is not moved. Returns whether n dwords are free.
bool reserve_soft(CommandBuffer *cb, std::uint32_t n);

// Space check without moving the cursor; the callback's result is honoured (false -> false).
bool ensure_space(CommandBuffer *cb, std::uint32_t n);

} // namespace bc5::reimpl::agc
