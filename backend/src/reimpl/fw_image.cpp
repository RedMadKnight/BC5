// SPDX-License-Identifier: GPL-2.0-only
// See include/bc5/reimpl/fw_image.hpp for the container layout and its source.
#include "bc5/reimpl/fw_image.hpp"

#include <algorithm>
#include <cstring>
#include <fstream>
#include <iterator>
#include <utility>

namespace bc5::reimpl {

namespace {

constexpr std::uint32_t kPtLoad = 1;
constexpr std::uint64_t kMaxImage = 512ull << 20; // a module image is a few MiB; refuse absurd sizes

template <typename T> bool read_le(std::span<const std::uint8_t> b, std::uint64_t off, T &out) {
    if (off > b.size() || b.size() - off < sizeof(T)) {
        return false;
    }
    std::memcpy(&out, b.data() + off, sizeof(T));
    return true;
}

struct Phdr {
    std::uint32_t type = 0;
    std::uint64_t offset = 0;
    std::uint64_t vaddr = 0;
    std::uint64_t filesz = 0;
    std::uint64_t memsz = 0;
};

bool is_self_magic(std::span<const std::uint8_t> b) {
    if (b.size() < 4) {
        return false;
    }
    const bool ps4 = b[0] == 0x4f && b[1] == 0x15 && b[2] == 0x3d && b[3] == 0x1d;
    const bool ps5 = b[0] == 0x54 && b[1] == 0x14 && b[2] == 0xf5 && b[3] == 0xee;
    return ps4 || ps5;
}

} // namespace

bool FwImage::parse(std::span<const std::uint8_t> file) {
    image_.clear();
    error_.clear();
    std::vector<std::uint8_t> image;

    std::uint64_t ehdr = 0;
    struct SelfEntry {
        std::uint64_t props, offset, filesz;
    };
    std::vector<SelfEntry> entries;
    const bool self = is_self_magic(file);
    if (self) {
        std::uint16_t count = 0;
        if (!read_le(file, 0x18, count)) {
            error_ = "SELF header truncated";
            return false;
        }
        for (std::uint16_t i = 0; i < count; ++i) {
            const std::uint64_t e = 0x20u + 0x20u * i;
            SelfEntry s{};
            if (!read_le(file, e, s.props) || !read_le(file, e + 8, s.offset) ||
                !read_le(file, e + 16, s.filesz)) {
                error_ = "SELF entry table truncated";
                return false;
            }
            entries.push_back(s);
        }
        ehdr = 0x20u + 0x20u * count;
    }

    std::uint32_t magic = 0;
    if (!read_le(file, ehdr, magic) || magic != 0x464c457fu) {
        error_ = "no ELF header";
        return false;
    }
    std::uint64_t phoff = 0;
    std::uint16_t phentsize = 0, phnum = 0;
    if (!read_le(file, ehdr + 0x20, phoff) || !read_le(file, ehdr + 0x36, phentsize) ||
        !read_le(file, ehdr + 0x38, phnum) || phentsize < 0x38) {
        error_ = "bad ELF header";
        return false;
    }
    std::vector<Phdr> ph(phnum);
    for (std::uint16_t i = 0; i < phnum; ++i) {
        const std::uint64_t p = ehdr + phoff + std::uint64_t{phentsize} * i;
        if (!read_le(file, p, ph[i].type) || !read_le(file, p + 8, ph[i].offset) ||
            !read_le(file, p + 16, ph[i].vaddr) || !read_le(file, p + 32, ph[i].filesz) ||
            !read_le(file, p + 40, ph[i].memsz)) {
            error_ = "program headers truncated";
            return false;
        }
    }

    std::uint64_t end = 0;
    for (const auto &p : ph) {
        if (p.type != kPtLoad) {
            continue;
        }
        if (p.filesz > p.memsz || p.vaddr > kMaxImage || p.memsz > kMaxImage - p.vaddr) {
            error_ = "PT_LOAD out of range";
            return false;
        }
        end = std::max(end, p.vaddr + p.memsz);
    }
    image.assign(end, 0);

    for (std::size_t i = 0; i < ph.size(); ++i) {
        const auto &p = ph[i];
        if (p.type != kPtLoad || p.filesz == 0) {
            continue;
        }
        std::uint64_t src = p.offset;
        std::uint64_t len = p.filesz;
        if (self) {
            // The bytes live in the SELF entry that names this program header.
            const auto it = std::find_if(entries.begin(), entries.end(), [&](const SelfEntry &s) {
                return (s.props & 0x800u) != 0 && ((s.props >> 20) & 0xfffu) == i;
            });
            if (it == entries.end()) {
                error_ = "PT_LOAD without SELF entry";
                return false;
            }
            if ((it->props & 0x8u) != 0) {
                error_ = "compressed or encrypted SELF entry";
                return false;
            }
            src = it->offset;
            len = std::min(it->filesz, p.filesz);
        }
        if (src > file.size() || file.size() - src < len) {
            error_ = "segment data truncated";
            return false;
        }
        std::memcpy(image.data() + p.vaddr, file.data() + src, static_cast<std::size_t>(len));
    }
    image_ = std::move(image); // only a fully parsed image becomes visible
    return true;
}

bool FwImage::load_file(const std::string &path) {
    std::ifstream in(path, std::ios::binary);
    if (!in) {
        image_.clear();
        error_ = "cannot open " + path;
        return false;
    }
    std::vector<std::uint8_t> bytes((std::istreambuf_iterator<char>(in)),
                                    std::istreambuf_iterator<char>());
    return parse(bytes);
}

const std::uint8_t *FwImage::at(std::uint64_t vaddr, std::uint64_t size) const {
    if (vaddr > image_.size() || image_.size() - vaddr < size) {
        return nullptr;
    }
    return image_.data() + vaddr;
}

} // namespace bc5::reimpl
