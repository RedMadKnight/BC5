// SPDX-License-Identifier: GPL-2.0-only
#pragma once

#include <string_view>

namespace bc5 {

// Backend version string; the backend itself arrives in phase 2 (docs/PHASES.md).
std::string_view version() noexcept;

// True when built with BC5_WITH_AMDGPU=ON.
bool has_amdgpu() noexcept;

} // namespace bc5
