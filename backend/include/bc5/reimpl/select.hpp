// SPDX-License-Identifier: GPL-2.0-only
// Which implementation of a re-created module a title gets (the maintainer's rule, 2026-11-20:
// by default take BC5's own,
// unless the game has its own):
//   - BC5's own re-creation by default;
//   - the game's own copy when the game ships one: its root directory, sce_module/, sce_modules/
//     or fakelib/, in that order. A game's fakelib/ holds system modules modified for that game, and
//     a game that brings them must use them (the maintainer's decision of 2026-11-25, reversing the
//     one of 2026-11-23 that counted fakelib/ as a module pack). The host's loader loads the game's
//     fakelib/ itself, before any module pack, so no launcher word is needed;
//   - libSceAgc and libSceAgcDriver only as a pair from one source (choose_agc_pair): BC5's
//     re-created libSceAgc does not start with the game's driver (exp 0439 fl439x: an access
//     violation at load), and the game's libSceAgc with BC5's driver hung once after the opening
//     film. The game's pair is chosen only when the game ships both;
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

// libSceAgc and libSceAgcDriver come from one source (exp 0439 fl439x): one choice for both. A "0"
// on either switch opts both out; "force" on either forces both; the game's pair only when the game
// ships both modules; else BC5's pair.
inline Choice choose_agc_pair(const char *agc_switch, bool game_ships_agc, const char *driver_switch,
                              bool game_ships_driver) {
    if (!switch_allows(agc_switch) || !switch_allows(driver_switch)) {
        return Choice::OptedOut;
    }
    if (switch_forces(agc_switch) || switch_forces(driver_switch)) {
        return Choice::Bc5Forced;
    }
    return game_ships_agc && game_ships_driver ? Choice::GameOwn : Choice::Bc5Own;
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
// <root>, <root>/sce_module, <root>/sce_modules or <root>/fakelib (the game's modified system modules), file
// <module>.sprx or <module>.prx, names
// compared case-insensitively. Empty when the game ships none.
std::filesystem::path find_game_copy(const std::filesystem::path &root, std::string_view module);

} // namespace bc5::reimpl
