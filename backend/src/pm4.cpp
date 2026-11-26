// SPDX-License-Identifier: GPL-2.0-only
#include "bc5/pm4.hpp"

#include <stdexcept>

namespace bc5::pm4 {

Builder &Builder::packet(Op op, std::span<const std::uint32_t> payload, bool compute) {
    if (payload.empty() || payload.size() > 0x3fff) {
        throw std::invalid_argument("PM4 type-3 payload must be 1..16383 dwords");
    }
    dwords_.push_back(header3(op, static_cast<std::uint32_t>(payload.size()), compute));
    dwords_.insert(dwords_.end(), payload.begin(), payload.end());
    return *this;
}

Builder &Builder::packet(Op op, std::initializer_list<std::uint32_t> payload, bool compute) {
    return packet(op, std::span<const std::uint32_t>(payload.begin(), payload.size()), compute);
}

Builder &Builder::set_sh_reg(std::uint32_t offset, std::initializer_list<std::uint32_t> values,
                             bool compute) {
    std::vector<std::uint32_t> payload;
    payload.reserve(values.size() + 1);
    payload.push_back(offset);
    payload.insert(payload.end(), values.begin(), values.end());
    return packet(Op::SetShReg, payload, compute);
}

Builder &Builder::pad_to_multiple(std::size_t align) {
    if (align == 0) {
        throw std::invalid_argument("alignment must be positive");
    }
    while (dwords_.size() % align != 0) {
        dwords_.push_back(kNopFiller);
    }
    return *this;
}

} // namespace bc5::pm4
