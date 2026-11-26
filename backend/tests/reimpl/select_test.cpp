// SPDX-License-Identifier: GPL-2.0-only
// The module-selection rule: BC5's own by default, the game's own copy when it ships one, =0 opts out.
#include <catch2/catch_test_macros.hpp>

#include "bc5/reimpl/select.hpp"

#include <chrono>
#include <filesystem>
#include <fstream>
#include <string>

using namespace bc5::reimpl;
namespace fs = std::filesystem;

TEST_CASE("switch values: unset, empty and anything but 0 allow BC5's module", "[reimpl][select]") {
    CHECK(switch_allows(nullptr));
    CHECK(switch_allows(""));
    CHECK(switch_allows("1"));
    CHECK(switch_allows("yes"));
    CHECK(switch_allows("00"));
    CHECK_FALSE(switch_allows("0"));
}

TEST_CASE("choice: default BC5, game's own wins, =0 opts out", "[reimpl][select]") {
    CHECK(choose(nullptr, false) == Choice::Bc5Own);
    CHECK(choose("", false) == Choice::Bc5Own);
    CHECK(choose("1", false) == Choice::Bc5Own);
    CHECK(choose(nullptr, true) == Choice::GameOwn);
    CHECK(choose("1", true) == Choice::GameOwn);
    CHECK(choose("0", false) == Choice::OptedOut);
    CHECK(choose("0", true) == Choice::OptedOut);
    CHECK(std::string(choice_name(Choice::Bc5Own)).find("BC5") != std::string::npos);
    // Test-only force: BC5's own over the game's copy, and the game's copy kept off the load.
    CHECK(choose("force", true) == Choice::Bc5Forced);
    CHECK(choose("force", false) == Choice::Bc5Forced);
    CHECK(is_bc5(Choice::Bc5Forced));
    CHECK_FALSE(is_bc5(Choice::GameOwn));
    CHECK(keeps_off_load("force", true));
    CHECK_FALSE(keeps_off_load(nullptr, true));
    CHECK(keeps_off_load(nullptr, false));
    CHECK_FALSE(keeps_off_load("0", false));
    CHECK(std::string(choice_name(Choice::Bc5Forced)).rfind("BC5's own re-creation", 0) == 0);
}

namespace {
struct TempDir {
    fs::path path;
    TempDir() {
        path = fs::temp_directory_path() /
               ("bc5-select-" +
                std::to_string(std::chrono::steady_clock::now().time_since_epoch().count()));
        fs::create_directories(path);
    }
    ~TempDir() {
        std::error_code ec;
        fs::remove_all(path, ec);
    }
};
void touch(const fs::path &p) {
    fs::create_directories(p.parent_path());
    std::ofstream(p) << "x";
}
} // namespace

TEST_CASE("find_game_copy looks in the root, sce_module and sce_modules", "[reimpl][select]") {
    TempDir t;
    CHECK(find_game_copy(t.path, "libSceAgc").empty());
    CHECK(find_game_copy({}, "libSceAgc").empty());
    CHECK(find_game_copy(t.path / "missing", "libSceAgc").empty());

    touch(t.path / "sce_module" / "libc.prx"); // a different module
    CHECK(find_game_copy(t.path, "libSceAgc").empty());

    touch(t.path / "sce_module" / "LIBSCEAGC.SPRX"); // names compare case-insensitively
    CHECK(find_game_copy(t.path, "libSceAgc").filename() == "LIBSCEAGC.SPRX");
    CHECK(choose(nullptr, !find_game_copy(t.path, "libSceAgc").empty()) == Choice::GameOwn);
    CHECK(find_game_copy(t.path, "libSceAgcDriver").empty()); // a prefix is not a match

    touch(t.path / "sce_modules" / "libScePsml.prx");
    CHECK(find_game_copy(t.path, "libScePsml").filename() == "libScePsml.prx");

    touch(t.path / "libSceAgcDriver.sprx");
    CHECK(find_game_copy(t.path, "libSceAgcDriver").filename() == "libSceAgcDriver.sprx");

    // fakelib/ holds the game's modified system modules and counts as the game's own copy (the
    // maintainer's decision, 2026-11-25), searched after the root and sce_module(s)/.
    touch(t.path / "fakelib" / "libSceBar.sprx");
    CHECK(find_game_copy(t.path, "libSceBar").parent_path().filename() == "fakelib");
    CHECK(choose(nullptr, !find_game_copy(t.path, "libSceBar").empty()) == Choice::GameOwn);
    CHECK_FALSE(keeps_off_load(nullptr, !find_game_copy(t.path, "libSceBar").empty()));
    CHECK(choose("force", !find_game_copy(t.path, "libSceBar").empty()) == Choice::Bc5Forced);
    touch(t.path / "sce_module" / "libSceBar.sprx"); // a copy in sce_module/ comes first
    CHECK(find_game_copy(t.path, "libSceBar").parent_path().filename() == "sce_module");
    CHECK(choose(nullptr, true) == Choice::GameOwn);
    CHECK(choose("force", true) == Choice::Bc5Forced);

    fs::create_directories(t.path / "sce_module" / "libSceFoo.sprx"); // a directory is not a file
    CHECK(find_game_copy(t.path, "libSceFoo").empty());
}

TEST_CASE("libSceAgc and libSceAgcDriver are chosen as one pair", "[reimpl][select]") {
    CHECK(choose_agc_pair(nullptr, false, nullptr, false) == Choice::Bc5Own);
    CHECK(choose_agc_pair(nullptr, true, nullptr, true) == Choice::GameOwn);
    CHECK(choose_agc_pair(nullptr, true, nullptr, false) == Choice::Bc5Own);  // the game's driver missing: BC5's pair
    CHECK(choose_agc_pair(nullptr, false, nullptr, true) == Choice::Bc5Own);  // the game's libSceAgc missing: BC5's pair
    CHECK(choose_agc_pair("0", true, nullptr, true) == Choice::OptedOut);     // one opt-out takes both
    CHECK(choose_agc_pair(nullptr, false, "0", false) == Choice::OptedOut);
    CHECK(choose_agc_pair("force", true, nullptr, true) == Choice::Bc5Forced); // one force takes both
    CHECK(choose_agc_pair(nullptr, true, "force", true) == Choice::Bc5Forced);
    CHECK(choose_agc_pair("0", true, "force", true) == Choice::OptedOut);     // opt-out wins
}
