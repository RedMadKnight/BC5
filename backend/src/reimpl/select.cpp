// SPDX-License-Identifier: GPL-2.0-only
// See include/bc5/reimpl/select.hpp.
#include "bc5/reimpl/select.hpp"

#include <cctype>
#include <system_error>

namespace bc5::reimpl {

namespace {

bool equal_nocase(std::string_view a, std::string_view b) {
    if (a.size() != b.size()) {
        return false;
    }
    for (std::size_t i = 0; i < a.size(); ++i) {
        if (std::tolower(static_cast<unsigned char>(a[i])) !=
            std::tolower(static_cast<unsigned char>(b[i]))) {
            return false;
        }
    }
    return true;
}

} // namespace

std::filesystem::path find_game_copy(const std::filesystem::path &root, std::string_view module) {
    if (root.empty()) {
        return {};
    }
    const std::string sprx = std::string(module) + ".sprx";
    const std::string prx = std::string(module) + ".prx";
    for (const auto &dir : {root, root / "sce_module", root / "sce_modules", root / "fakelib"}) {
        std::error_code ec;
        if (!std::filesystem::is_directory(dir, ec)) {
            continue;
        }
        for (const auto &entry : std::filesystem::directory_iterator(dir, ec)) {
            if (!entry.is_regular_file(ec)) {
                continue;
            }
            const std::string name = entry.path().filename().string();
            if (equal_nocase(name, sprx) || equal_nocase(name, prx)) {
                return entry.path();
            }
        }
    }
    return {};
}

} // namespace bc5::reimpl
