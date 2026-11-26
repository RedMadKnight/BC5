// SPDX-License-Identifier: GPL-2.0-only
// The data-source switches of the re-created modules (see include/bc5/reimpl/data_source.hpp).
#include "bc5/reimpl/data_source.hpp"

#include "bc5/env_flag.hpp"

#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <mutex>
#include <set>
#include <string>

namespace bc5::reimpl {

namespace {

std::mutex g_mutex;
bool g_have_switches = false;
DataSwitches g_switches;
std::set<std::string> g_compared; // "module/table" already compared

bool env_switch(const char *name) {
#if defined(_MSC_VER)
    char *value = nullptr;
    std::size_t length = 0;
    if (_dupenv_s(&value, &length, name) != 0) {
        return false;
    }
    const bool on = env_on(value);
    std::free(value);
    return on;
#else
    return env_on(std::getenv(name));
#endif
}

DataSwitches switches_locked() {
    if (!g_have_switches) {
        g_switches.fw_data = env_switch("BC5_REIMPL_FW_DATA");
        g_switches.fw_compare = env_switch("BC5_REIMPL_FW_COMPARE");
        g_have_switches = true;
    }
    return g_switches;
}

std::uint32_t file_word(const std::uint8_t *file, std::size_t index) {
    std::uint32_t v = 0;
    std::memcpy(&v, file + 4u * index, 4);
    return v;
}

} // namespace

DataSwitches data_switches() {
    std::lock_guard<std::mutex> lock(g_mutex);
    return switches_locked();
}

void set_data_switches(const DataSwitches &switches) {
    std::lock_guard<std::mutex> lock(g_mutex);
    g_switches = switches;
    g_have_switches = true;
    g_compared.clear();
}

void reset_data_switches() {
    std::lock_guard<std::mutex> lock(g_mutex);
    g_have_switches = false;
    g_compared.clear();
}

FirmwareData *firmware_data_for_use() {
    return data_switches().fw_data ? firmware_data() : nullptr;
}

FirmwareData *firmware_data_for_compare() {
    return data_switches().fw_compare ? firmware_data() : nullptr;
}

std::size_t compare_with_firmware(const char *module, const char *table, const std::uint32_t *ours,
                                  const std::uint8_t *file, std::size_t entries,
                                  std::size_t entry_words) {
    if (ours == nullptr || file == nullptr || entry_words == 0) {
        return 0;
    }
    {
        std::lock_guard<std::mutex> lock(g_mutex);
        if (!g_compared.insert(std::string(module) + "/" + table).second) {
            return 0;
        }
    }
    std::size_t differing = 0;
    for (std::size_t i = 0; i < entries; ++i) {
        bool same = true;
        for (std::size_t w = 0; w < entry_words; ++w) {
            same = same && ours[i * entry_words + w] == file_word(file, i * entry_words + w);
        }
        if (same) {
            continue;
        }
        ++differing;
        std::string a;
        std::string b;
        char buf[16];
        for (std::size_t w = 0; w < entry_words; ++w) {
            std::snprintf(buf, sizeof buf, "%s0x%08X", w == 0 ? "" : ",",
                          ours[i * entry_words + w]);
            a += buf;
            std::snprintf(buf, sizeof buf, "%s0x%08X", w == 0 ? "" : ",",
                          file_word(file, i * entry_words + w));
            b += buf;
        }
        log(module, "FW_COMPARE %s[%zu]: ours {%s} file {%s}", table, i, a.c_str(), b.c_str());
    }
    log(module, "FW_COMPARE %s: %zu of %zu entries differ", table, differing, entries);
    return differing;
}

std::size_t compare_table_with_firmware(const char *module, const char *table, std::uint64_t vaddr,
                                        const std::uint32_t *ours, std::size_t entries,
                                        std::size_t entry_words) {
    FirmwareData *fw = firmware_data_for_compare();
    if (fw == nullptr || entries == 0) {
        return 0;
    }
    const std::uint8_t *file = fw->get(module, vaddr, 4ull * entries * entry_words);
    if (file == nullptr) {
        return 0;
    }
    return compare_with_firmware(module, table, ours, file, entries, entry_words);
}

} // namespace bc5::reimpl
