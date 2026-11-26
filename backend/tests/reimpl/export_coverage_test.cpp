// SPDX-License-Identifier: GPL-2.0-only
// Export coverage of the re-created modules against the originals' export tables
// (original_exports.inc): every (NID, library) pair the original exports must be in ours, with
// the same own/foreign kind, and ours exports nothing the original does not. libSceAgc 258/258,
// libSceAgcDriver 179 rows (177 NIDs) / 179, libScePsml 92/92 (the maintainer's word of
// 2026-11-23: full coverage).
#include "bc5/reimpl/module.hpp"

#include <catch2/catch_test_macros.hpp>

#include <cstdint>
#include <cstring>
#include <map>
#include <set>
#include <span>
#include <string>
#include <utility>

namespace {

struct OriginalExport {
    const char *nid;
    const char *library;
    bool foreign; // a foreign library's NID at the original's local stub
};

#include "original_exports.inc"

using Key = std::pair<std::string, std::string>;

std::map<Key, const bc5::reimpl::ExportEntry *>
by_key(std::span<const bc5::reimpl::ExportEntry> ex) {
    std::map<Key, const bc5::reimpl::ExportEntry *> out;
    for (const auto &e : ex) {
        out.emplace(Key{e.nid, e.library}, &e);
    }
    return out;
}

struct Coverage {
    int missing_own = 0;
    int missing_foreign = 0;
    int kind_mismatch = 0;
    int extra = 0;
};

template <std::size_t N>
Coverage compare(const OriginalExport (&orig)[N], std::span<const bc5::reimpl::ExportEntry> ours) {
    Coverage c;
    const auto mine = by_key(ours);
    std::set<Key> theirs;
    for (const OriginalExport &o : orig) {
        theirs.insert(Key{o.nid, o.library});
        const auto it = mine.find(Key{o.nid, o.library});
        if (it == mine.end()) {
            UNSCOPED_INFO("missing " << o.nid << " (" << o.library << ")"
                                     << (o.foreign ? " foreign" : " own"));
            ++(o.foreign ? c.missing_foreign : c.missing_own);
            continue;
        }
        if (it->second->foreign != o.foreign) {
            UNSCOPED_INFO("kind differs " << o.nid << " (" << o.library << ")");
            ++c.kind_mismatch;
        }
    }
    for (const auto &[k, e] : mine) {
        if (theirs.count(k) == 0) {
            UNSCOPED_INFO("not in the original: " << k.first << " (" << k.second << ")");
            ++c.extra;
        }
    }
    return c;
}

} // namespace

TEST_CASE("export coverage: libSceAgc exports all 258 of the original's", "[reimpl][coverage]") {
    REQUIRE(std::size(kOriginalAgc) == 258);
    const Coverage c = compare(kOriginalAgc, bc5::reimpl::agc::exports());
    CHECK(c.missing_own == 0);
    CHECK(c.missing_foreign == 0);
    CHECK(c.kind_mismatch == 0);
    CHECK(c.extra == 0);
    CHECK(bc5::reimpl::agc::exports().size() == 258);
}

TEST_CASE("export coverage: libSceAgcDriver exports all 179 rows of the original's",
          "[reimpl][coverage]") {
    REQUIRE(std::size(kOriginalAgcDriver) == 179);
    const Coverage c = compare(kOriginalAgcDriver, bc5::reimpl::agc_driver::exports());
    CHECK(c.missing_own == 0);
    CHECK(c.missing_foreign == 0);
    CHECK(c.kind_mismatch == 0);
    CHECK(c.extra == 0);
    std::set<std::string> nids;
    for (const auto &e : bc5::reimpl::agc_driver::exports()) {
        nids.insert(e.nid);
    }
    CHECK(nids.size() == 177);
}

TEST_CASE("export coverage: libScePsml exports all 92 of the original's",
          "[reimpl][coverage]") {
    REQUIRE(std::size(kOriginalPsml) == 92);
    const Coverage c = compare(kOriginalPsml, bc5::reimpl::psml::exports());
    CHECK(c.missing_own == 0);
    CHECK(c.missing_foreign == 0);
    CHECK(c.kind_mismatch == 0);
    CHECK(c.extra == 0);
    CHECK(bc5::reimpl::psml::exports().size() == 92);
}

TEST_CASE("foreign-NID exports behave as the originals' stub", "[reimpl][coverage]") {
    int functions = 0;
    int objects = 0;
    for (auto ex : {bc5::reimpl::agc::exports(), bc5::reimpl::agc_driver::exports(),
                    bc5::reimpl::psml::exports()}) {
        for (const auto &e : ex) {
            if (!e.foreign) {
                continue;
            }
            INFO(e.nid << " (" << e.library << ")");
            REQUIRE(e.address != nullptr);
            CHECK(std::string(e.name).empty());
            if (e.is_object) {
                // A data object at the stub's address: its bytes, 31 c0 c3 and int3 padding.
                ++objects;
                const auto *b = static_cast<const std::uint8_t *>(e.address);
                CHECK(b[0] == 0x31);
                CHECK(b[1] == 0xc0);
                CHECK(b[2] == 0xc3);
                for (int i = 3; i < 16; ++i) {
                    CHECK(b[i] == 0xcc);
                }
                continue;
            }
            // A function: it ignores its arguments and returns 0; call it with none.
            ++functions;
            std::uint64_t (*f)() = nullptr;
            static_assert(sizeof f == sizeof e.address);
            std::memcpy(&f, &e.address, sizeof f);
            CHECK(f() == 0);
            CHECK(f() == 0);
        }
    }
    CHECK(functions == 9 + 4 + 46);
    CHECK(objects == 5);
}
