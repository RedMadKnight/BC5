// SPDX-License-Identifier: GPL-2.0-only
// Where the re-created modules take their embedded data from. By default every table is our own
// source (agc_tables.hpp, agc_driver_tables.hpp) and no module file is needed. Two switches,
// read once here with the rule of bc5/env_flag.hpp (unset, empty and "0" are off):
//
//   BC5_REIMPL_FW_DATA=1     use the data of the maintainer's own module files
//                            (firmware_data(), BC5_REIMPL_FW_DIR) where present, as before.
//   BC5_REIMPL_FW_COMPARE=1  diagnostic only: when the module files are present, compare their
//                            data with ours and log every differing entry once (module, table,
//                            index, ours vs file). It does not change which data is used.
//
// libScePsml does not go through this: its embedded data is only reached past its PS5 Pro gate.
#pragma once

#include "bc5/reimpl/module.hpp"

#include <cstddef>
#include <cstdint>

namespace bc5::reimpl {

struct DataSwitches {
    bool fw_data = false;
    bool fw_compare = false;
};

// The switches, read from the environment on first use.
DataSwitches data_switches();

// Test seam: replace the switches (until reset_data_switches(), which re-reads the environment
// on next use). Also forgets which tables were already compared.
void set_data_switches(const DataSwitches &switches);
void reset_data_switches();

// The firmware-data provider when BC5_REIMPL_FW_DATA is on, else nullptr (own data is used).
FirmwareData *firmware_data_for_use();

// The firmware-data provider when BC5_REIMPL_FW_COMPARE is on, else nullptr.
FirmwareData *firmware_data_for_compare();

// Compares `entries` entries of `entry_words` u32 each: our own data against the file's bytes
// (little-endian u32, same layout). Logs every differing entry, and does this only once per
// (module, table); later calls return 0 without logging. Returns the number of differing entries.
std::size_t compare_with_firmware(const char *module, const char *table, const std::uint32_t *ours,
                                  const std::uint8_t *file, std::size_t entries,
                                  std::size_t entry_words);

// Convenience: when COMPARE is on and the file holds `entries * entry_words` u32 at `vaddr` of
// `module`, compare them with `ours` (as above). Returns the number of differing entries.
std::size_t compare_table_with_firmware(const char *module, const char *table, std::uint64_t vaddr,
                                        const std::uint32_t *ours, std::size_t entries,
                                        std::size_t entry_words);

} // namespace bc5::reimpl
