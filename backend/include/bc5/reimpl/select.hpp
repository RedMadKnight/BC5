// SPDX-License-Identifier: GPL-2.0-only
// Which implementation of a re-created module a title gets (the maintainer's rule, 2026-11-20:
// "domyślnie ma brać z BC5, chyba że gra ma własne implementacje", by default take BC5's own,
// unless the game has its own):
//   - BC5's own re-creation by default;
//   - the game's own copy when the game ships one (its root directory, sce_module/ or
//     sce_modules/, as KytyPlus's loader scans them);
//   - opted out with BC5_REIMPL_<X>=0: neither BC5's nor a forced choice, the host's previous
//     behaviour (a module pack from SHADPS4_SYSMODULES_PACK_DIR, else KytyPlus's HLE).
#pragma once

#include <filesystem>
#include <string>
#include <string_view>

namespace bc5::reimpl {

enum class Choice { Bc5Own, GameOwn, OptedOut };

// The switch's value: unset or empty means the default (on); "0" opts out; anything else is on.
inline bool switch_allows(const char *value) {
    return value == nullptr || value[0] == 0 || !(value[0] == '0' && value[1] == 0);
}

inline Choice choose(const char *switch_value, bool game_ships_module) {
    if (!switch_allows(switch_value)) {
        return Choice::OptedOut;
    }
    return game_ships_module ? Choice::GameOwn : Choice::Bc5Own;
}

inline const char *choice_name(Choice c) {
    switch (c) {
    case Choice::Bc5Own:
        return "BC5's own re-creation";
    case Choice::GameOwn:
        return "the game's own copy";
    case Choice::OptedOut:
        return "opted out (=0): module pack or host HLE";
    }
    return "?";
}

// The path of the game's own copy of `module` (e.g. "libSceAgc") under the title's directory:
// <root>, <root>/sce_module or <root>/sce_modules, file <module>.sprx or <module>.prx, names
// compared case-insensitively. Empty when the game ships none.
std::filesystem::path find_game_copy(const std::filesystem::path &root, std::string_view module);

} // namespace bc5::reimpl
