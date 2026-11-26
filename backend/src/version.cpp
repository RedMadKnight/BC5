// SPDX-License-Identifier: GPL-2.0-only
#include "bc5/version.hpp"

namespace bc5 {

std::string_view version() noexcept { return "0.0.0"; }

bool has_amdgpu() noexcept {
#ifdef BC5_WITH_AMDGPU
    return true;
#else
    return false;
#endif
}

} // namespace bc5
