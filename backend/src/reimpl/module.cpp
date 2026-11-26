// SPDX-License-Identifier: GPL-2.0-only
// The shared frame of the re-created modules: firmware-data provider and log sink.
#include "bc5/reimpl/module.hpp"

#include <cstdarg>
#include <cstdio>

namespace bc5::reimpl {

namespace {
FirmwareData *g_firmware_data = nullptr;
LogFn g_log = nullptr;
} // namespace

void set_firmware_data(FirmwareData *data) { g_firmware_data = data; }
FirmwareData *firmware_data() { return g_firmware_data; }

void set_log(LogFn fn) { g_log = fn; }

void log(const char *module, const char *fmt, ...) {
    char buf[1024];
    va_list ap;
    va_start(ap, fmt);
    std::vsnprintf(buf, sizeof buf, fmt, ap);
    va_end(ap);
    if (g_log != nullptr) {
        g_log(module, buf);
    } else {
        std::fprintf(stderr, "[%s] %s\n", module, buf);
    }
}

} // namespace bc5::reimpl
