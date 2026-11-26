// SPDX-License-Identifier: GPL-2.0-only
// The register catcher (reimpl-agc-psml, after run rmplN01 of 2026-11-21: "Illegal register access
// in command stream" inside an IB2, a failed ring reset and a reboot). Before an IB goes to the
// kernel, every register write it asks the CP for must lie inside the register space of its
// packet; a packet that would write outside it is a bug of whoever built it (a GPU fault is a bug
// to remove at its source), and is caught here instead of reaching the GPU.
//
// Checked, for type-3 packets:
//   SET_CONFIG_REG 0x68, SET_CONTEXT_REG 0x69, SET_SH_REG 0x76, SET_SH_REG_INDEX 0x9b,
//   SET_UCONFIG_REG 0x79, SET_UCONFIG_REG_INDEX 0x7a: start offset + count inside the space;
//   LOAD_CONTEXT_REG_INDEX 0x9f, LOAD_SH_REG_INDEX 0x63, LOAD_UCONFIG_REG_INDEX 0x64 in the
//   offset-and-data form (dword 3 bit 31): every (offset, value) pair of the list in memory, read
//   through the caller's 1:1 mapping when `mapped` says the list is mapped (else not checked).
// Register spaces (dword offsets): Mesa src/amd/common/sid.h (0866ae7) SI_CONFIG_REG_OFFSET
// 0x8000..SI_CONFIG_REG_END 0xB000, SI_SH_REG_OFFSET 0xB000..SI_SH_REG_END 0xC000,
// SI_CONTEXT_REG_OFFSET 0x28000..SI_CONTEXT_REG_END 0x29000, CIK_UCONFIG_REG_OFFSET
// 0x30000..CIK_UCONFIG_REG_END 0x40000 (bytes; divided by 4 here).
// TODO(verify): the five-dword LOAD_*_REG_INDEX layout (address lo, address hi, bit 31 = list of
// offset/data pairs, count) is the one libSceAgc's register-load builders emit (our clean-room
// description); Mesa sid.h names the opcodes only.
//
// Switch BC5_REG_CATCH: unset/0 off; "fatal" ends the process with exit 87 after the record;
// any other value records the packet and NOPs it. No GPU access.
#pragma once

#include <cstdint>
#include <functional>

namespace bc5::reg_catch {

enum class Mode { Off, Log, Fatal };

Mode mode(); // read once from BC5_REG_CATCH
Mode parse_mode(const char *value);

struct Finding {
    const char *reason = nullptr; // nullptr: the packet is fine
    std::uint32_t reg = 0;        // the offending register (relative to its space, or absolute)
    std::uint32_t index = 0;      // which register of the packet / pair of the list
};

// p: the packet (header first), len: its dwords.
Finding check(const std::uint32_t *p, std::uint32_t len,
              const std::function<bool(std::uint64_t, std::uint64_t)> &mapped);

} // namespace bc5::reg_catch
