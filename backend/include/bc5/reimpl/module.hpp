// SPDX-License-Identifier: GPL-2.0-only
// Clean-room re-creations of the PS5 system modules libSceAgc, libSceAgcDriver and libScePsml
// (see backend/src/reimpl/PROVENANCE.md). This header is the frame every re-created module uses:
// how it publishes its exports to the host and how it receives its imports.
//
// A re-created module is ordinary C++ built into libbc5_backend. On the KytyPlus host (Linux
// x86-64) the native calling convention is the guest's System V convention, so an export's
// function pointer is registered with the host's symbol table as is; every export therefore has
// a C-compatible signature (scalars and raw pointers only, guest pointers are host pointers).
// The modules do not depend on KytyPlus: the host glue (kytyplus-patches/0002) walks exports()
// and imports() of each module whose switch is on.
#pragma once

#include <cstdint>
#include <span>

namespace bc5::reimpl {

// One exported function or object, as the guest links it: the NID is the ABI, the name is for
// logs only (empty when the original name is unknown).
struct ExportEntry {
    const char *nid;
    const char *library; // e.g. "libSceAgc", "libSceAgcDriverPaDebug", "libScePsml_mfsr2"
    const char *name;
    void *address;       // function or object address
    bool is_object;      // true for exported data objects
    // A foreign library's NID the original module defines at a local stub that returns 0
    // (PROVENANCE.md, "Foreign-NID exports"): the host registers it only while no other module or
    // HLE function provides that NID, so it can never shadow the real provider.
    bool foreign = false;
};

// One import the module calls, resolved by the host glue before the module's first call. The
// glue writes the resolved address into *slot (the slot is a function pointer of the right type,
// reinterpreted). An unresolved slot stays nullptr; modules must treat nullptr as "not
// available" and fail the way their description says the firmware fails without that import.
struct ImportSlot {
    const char *nid;
    const char *library; // library the original module imports it from
    const char *name;    // for logs
    void **slot;
};

// Read-only access to data that the original module embeds and that cannot be shipped in this
// repository (GPU shader binaries, register-default tables, ...). The host provides it from the
// maintainer's own copy of the module (BC5_REIMPL_FW_DIR). `vaddr` is the address of the data in
// the original module's image (base 0). Returns nullptr when the file or range is not available;
// the caller then fails cleanly (and logs once). libSceAgc and libSceAgcDriver use it only behind
// BC5_REIMPL_FW_DATA / BC5_REIMPL_FW_COMPARE (data_source.hpp); by default they use own data.
class FirmwareData {
  public:
    virtual ~FirmwareData() = default;
    virtual const std::uint8_t *get(const char *module, std::uint64_t vaddr,
                                    std::uint64_t size) = 0;
};

// Set by the host before any export is called; tests install their own.
void set_firmware_data(FirmwareData *data);
FirmwareData *firmware_data();

// Log sink (the host forwards to its log; default: stderr). printf-style.
using LogFn = void (*)(const char *module, const char *message);
void set_log(LogFn fn);
void log(const char *module, const char *fmt, ...)
#if defined(__GNUC__) || defined(__clang__)
    __attribute__((format(printf, 2, 3)))
#endif
    ;

namespace agc {
std::span<const ExportEntry> exports();
std::span<const ImportSlot> imports();
} // namespace agc

namespace agc_driver {
std::span<const ExportEntry> exports();
std::span<const ImportSlot> imports();
} // namespace agc_driver

namespace psml {
std::span<const ExportEntry> exports();
std::span<const ImportSlot> imports();
} // namespace psml

} // namespace bc5::reimpl
