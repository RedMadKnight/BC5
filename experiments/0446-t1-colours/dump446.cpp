// SPDX-License-Identifier: GPL-2.0-only
// BC5 exp 0446: dump the re-created libSceAgc's data the title reads (every default-state table, the
// ported register-name tables and all 40 descriptors' name tables as BC5 builds them) as text, so the
// same program linked against two builds of libbc5_backend.a can be diffed. No GPU, no module file.
#include "bc5/reimpl/agc_internal.hpp"
#include "bc5/reimpl/agc_tables.hpp"
#include "bc5/reimpl/data_source.hpp"

#include <cstdint>
#include <cstdio>
#include <vector>

namespace agc = bc5::reimpl::agc;

int main() {
    bc5::reimpl::set_firmware_data(nullptr);
    bc5::reimpl::set_data_switches({});
    for (int i = 0; i < agc::tables::kTableCount; ++i) {
        const auto id = static_cast<agc::tables::TableId>(i);
        const auto t = agc::tables::table(id);
        std::printf("table %d %s count %zu\n", i, agc::tables::table_name(id), t.size());
        for (std::size_t k = 0; k < t.size(); ++k) {
            std::printf("  %s[%zu] %08x %08x\n", agc::tables::table_name(id), k, t[k].offset, t[k].value);
        }
    }
    for (std::size_t n = 0; n < agc::detail::kPortedNameTableCount; ++n) {
        const auto &p = agc::detail::kPortedNameTables[n];
        std::printf("ported %llx count %u\n", static_cast<unsigned long long>(p.descriptor), p.count);
        for (std::uint32_t e = 0; e < 3u * p.count; ++e) std::printf("  p%zu[%u] %08x\n", n, e, p.entries[e]);
    }
    for (int on : {1, 0}) {
        agc::detail::set_name_tables_ported_for_tests(on);
        for (std::uint32_t k = 0; k < 40; ++k) {
            const std::uint64_t desc = 0x28000u + 0x40u * k;
            std::vector<std::uint32_t> handed, triples;
            const bool ok = agc::detail::name_table_for(desc, handed, triples);
            std::printf("names ported=%d desc %llx ok %d handed %zu triples %zu\n", on,
                        static_cast<unsigned long long>(desc), ok ? 1 : 0, handed.size(), triples.size());
            for (std::size_t e = 0; e < handed.size(); ++e) std::printf("  h%u.%zu %08x\n", k, e, handed[e]);
            for (std::size_t e = 0; e < triples.size(); ++e) std::printf("  t%u.%zu %08x\n", k, e, triples[e]);
        }
    }
    agc::detail::set_name_tables_ported_for_tests(-1);
    return 0;
}
