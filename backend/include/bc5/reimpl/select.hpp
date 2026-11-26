// SPDX-License-Identifier: GPL-2.0-only
// Which implementation of a re-created module a title gets (the maintainer's rule, 2026-11-20:
// by default take BC5's own,
// unless the game has its own):
//   - BC5's own re-creation by default;
//   - the game's own copy when the game ships one: its root directory, sce_module/ or sce_modules/
//     (as KytyPlus's loader scans them). libSceAgc, libSceAgcDriver and libScePsml are firmware
//     system modules, which retail titles do not ship; a fakelib/ folder beside a game is the dump
//     tooling's (a firmware's system modules placed there) and counts as a module pack, not as the
//     game's own (the maintainer's decision of 2026-11-23): its copies stay off the load;
//   - opted out with BC5_REIMPL_<X>=0: neither BC5's nor a forced choice, the host's previous
//     behaviour (a module pack from SHADPS4_SYSMODULES_PACK_DIR, else KytyPlus's HLE);
//   - TEST ONLY: BC5_REIMPL_<X>=force takes BC5's own even when the game ships its own copy (the
//     game's copy is then kept off the load as well), to test the re-creations on a title that
//     ships the modules. Never set in a shortcut or a shared launcher.
#pragma once

#include <filesystem>
#include <string>
#include <string_view>

namespace bc5::reimpl {

enum class Choice { Bc5Own, GameOwn, OptedOut, Bc5Forced };

inline bool is_bc5(Choice c) { return c == Choice::Bc5Own || c == Choice::Bc5Forced; }

// The test-only force value.
inline bool switch_forces(const char *value) {
    return value != nullptr && value[0] == 'f' && std::string_view(value) == "force";
}

// The switch's value: unset or empty means the default (on); "0" opts out; anything else is on.
inline bool switch_allows(const char *value) {
    return value == nullptr || value[0] == 0 || !(value[0] == '0' && value[1] == 0);
}

inline Choice choose(const char *switch_value, bool game_ships_module) {
    if (!switch_allows(switch_value)) {
        return Choice::OptedOut;
    }
    if (switch_forces(switch_value)) {
        return Choice::Bc5Forced;
    }
    return game_ships_module ? Choice::GameOwn : Choice::Bc5Own;
}

// Whether the host keeps the module off its LLE load (module pack or the game's own copy).
inline bool keeps_off_load(const char *switch_value, bool game_ships_module) {
    return is_bc5(choose(switch_value, game_ships_module));
}

inline const char *choice_name(Choice c) {
    switch (c) {
    case Choice::Bc5Own:
        return "BC5's own re-creation";
    case Choice::GameOwn:
        return "the game's own copy";
    case Choice::OptedOut:
        return "opted out (=0): module pack or host HLE";
    case Choice::Bc5Forced:
        return "BC5's own re-creation, FORCED over the game's own copy (test only)";
    }
    return "?";
}

// The path of the game's own copy of `module` (e.g. "libSceAgc") under the title's directory:
// <root>, <root>/sce_module or <root>/sce_modules (not fakelib/: the dump tooling's folder), file
// <module>.sprx or <module>.prx, names
// compared case-insensitively. Empty when the game ships none.
std::filesystem::path find_game_copy(const std::filesystem::path &root, std::string_view module);

} // namespace bc5::reimpl
