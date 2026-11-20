// SPDX-License-Identifier: GPL-2.0-only
// Read-only loaded image of a module file the maintainer owns (a SELF container or a plain ELF),
// used by the host to serve bc5::reimpl::FirmwareData: the re-created modules ask for data that
// the original module embeds (shader binaries, register tables) by its virtual address.
//
// Container layout, as KytyPlus reads it (src/loader/elf.h SelfHeader/SelfSegment and
// src/loader/elf.cpp LoadSelfSegments / the segment loop at 249-252, KytyPlus @ f266548):
//   SELF: magic (4 bytes: 4f 15 3d 1d or 54 14 f5 ee), 0x20-byte header with u16 segment count at
//   0x18, then that many 0x20-byte entries {u64 props, u64 offset, u64 file size, u64 memory
//   size}; the ELF header follows the entries. An entry with props bit 11 (0x800) carries the
//   bytes of program header number (props >> 20) & 0xfff, stored at `offset` (bit 3 set would mean
//   a compressed/encrypted entry, which we refuse).
//   ELF: standard ELF64 program headers; every PT_LOAD is copied to p_vaddr, p_memsz - p_filesz
//   bytes zero-filled.
// Nothing here contains or describes Sony data; the files are read at run time from the
// maintainer's own disk.
#pragma once

#include <cstdint>
#include <span>
#include <string>
#include <vector>

namespace bc5::reimpl {

class FwImage {
  public:
    // Parse a whole file's bytes. Returns false with error() set on any malformed input.
    bool parse(std::span<const std::uint8_t> file);
    bool load_file(const std::string &path);

    // Pointer to `size` bytes at virtual address `vaddr` of the loaded image, or nullptr when
    // the range is not fully inside the image.
    const std::uint8_t *at(std::uint64_t vaddr, std::uint64_t size) const;

    std::uint64_t image_size() const { return image_.size(); }
    const std::string &error() const { return error_; }

  private:
    std::vector<std::uint8_t> image_;
    std::string error_;
};

} // namespace bc5::reimpl
