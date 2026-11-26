#!/usr/bin/env python3
"""BC5 experiment 0405 (series e7 of experiment 0401), tag "tus": exp 0405 decision 4 ("=> B => B", the dead KytyPlus tables
are ported first, then loaded, each behind its own switch), batch 2, hardware group, the Usbd table of src/libs/libUsbd.cpp:
  namespace LibUsbd  (InitUsbd_1, 65 NIDs)  KYTY_BC5_LOAD_USBD  61 ported, 4 held (absent upstream)
The port is AnyPS5's libSceUsbd. Its host transport (libusb) runs only for the devices the allow-list KYTY_BC5_USBD_ALLOW
names ("vvvv:pppp[,vvvv:pppp...]", hex, default empty; the maintainer approved libusb on 2026-11-04, relayed by the top
session). libusb-1.0 is loaded at run time (dlopen of libusb-1.0.so.0, our own declarations), so no compile or link command
changes. With the list empty (the default) libusb is never loaded and every call answers as on a host with no USB device.
A device is never passed through when its id is one of Sony's controllers (DualShock 4, DualSense, DualSense Edge) or when
the device or any interface of any configuration is HID (3) or audio (1), even when listed.
The same switch name makes libs.cpp (agent tl3) load the table. Off (unset, empty or "0") every stub takes today's path
(PRINT_NAME, then today's return OK), InitUsbd_1 registers all 65 NIDs as today and the allow-list is not read; on, the 61
ported stubs call the port and InitUsbd_1 does not register the 4 held NIDs (so the runtime linker's stubbed-import line
shows for them). Source: AnyPS5 4f41f4c37 (GPL-2.0-only), core/libs/prx/libSceUsbd/Export.cpp and its debt note; shadPS4
60c42b9 (GPL-2.0-or-later); libusb's public header (LGPL-2.1-or-later) for the declarations; cited in the block.
Edits, all in src/libs/libUsbd.cpp (this agent owns the file): includes after <common/abi.h>, one block after the
LIB_VERSION line, the 61 ported stubs' signatures and one branch each, and in LIB_DEFINE one statement plus a guard around
each of the 4 held registration lines. The 4 held stubs are not edited.
The input md5 is pinned (PINS, one dict) and asserted; an input that has the edit already is refused; every anchor must
occur exactly once; each edit keeps braces, parentheses and brackets balanced; the inserted text is ASCII; line ends stay LF
(the UTF-8 BOM is kept). After editing, the script undoes its own edits on the output and asserts that this gives the input
back byte for byte.
Prints "<relpath> <md5>". Notes: tus0405-notes.md; CPU test: tus0405.cpp.
usage: mktus0405.py <tree root in> <out dir>"""
import hashlib
import os
import sys

# The pinned inputs, one entry per unit this script edits (the top session re-pins here when it chains scripts).
PINS = {
    "src/libs/libUsbd.cpp": "f15039f248f156341d68cb3cb58a2b0f",  # the base tree's file (KytyPlus f266548 + patch 0001), e7 input
}
REL = "src/libs/libUsbd.cpp"
MARKS = (b"KYTY_BC5_LOAD_USBD", b"Bc5Usb", b"(tus)", b"KYTY_BC5_USBD_ALLOW")


def T(text):
    """C++ text written with a visible tab ("»") for each tab of the file's indentation, as ASCII bytes."""
    return text.replace("»", "\t").encode("ascii")


INCLUDES_OLD = "#include <common/abi.h>\n"
INCLUDES_NEW = """#include <common/abi.h>

// BC5 experiment 0405 (series e7 of experiment 0401, tag tus): what the Usbd port uses.
#include <algorithm>
#include <atomic>
#include <chrono>
#include <climits>
#include <condition_variable>
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <map>
#include <mutex>
#include <optional>
#include <set>
#include <string>
#include <thread>
#include <type_traits>
#include <vector>
#ifndef _WIN32
#include <dlfcn.h> // libusb-1.0 is loaded at run time; KytyPlus already links CMAKE_DL_LIBS (src/CMakeLists.txt)
#endif
"""

ANCHOR = 'LIB_VERSION("libSceUsbd", 1, "libSceUsbd", 1, 1);\n'
BLOCK = r"""
// ---- BC5 experiment 0405 (series e7 of experiment 0401), tag tus: KYTY_BC5_LOAD_USBD, the Usbd table's port ----
// Exp 0405 decision 4 ("=> B => B", 2026-11-04): this table is compiled but Libs::InitAll never loaded it; it is ported
// first, then loaded behind KYTY_BC5_LOAD_USBD (libs.cpp, agent tl3). Unset, empty or "0" is off: every stub below takes
// today's path (PRINT_NAME, return OK), InitUsbd_1 registers all 65 NIDs as today and nothing below runs. On, 61 exports
// answer as AnyPS5 (github.com/boykopovar/AnyPS5, GPL-2.0-only) @ 4f41f4c375f5abb487dbd184fbc150f31994d762,
// core/libs/prx/libSceUsbd/Export.cpp:24-853 (the codes, the transfer object, the device and handle calls, the event lock,
// handler and waiters after FreeBSD 11.4 lib/libusb/libusb10_io.c), whose debt note docs/dev/debt/libSceUsbd.md says:
// errors are libusb's codes as 0x80240000 minus the code (after shadPS4, github.com/shadps4-emu/shadPS4, GPL-2.0-or-later,
// @ 60c42b9 src/core/libraries/usbd/usbd.cpp:16-24), the descriptor and transfer layouts are FreeBSD 11.4 libusb's (equal
// to libusb's on x86-64), nothing is measured on a console (TODO(verify)), and "When the host has no USB access,
// initialization keeps the empty device list and event handling waits for its timeout".
//  - The host transport (libusb) runs only for the devices the allow-list KYTY_BC5_USBD_ALLOW names (the maintainer
//    approved libusb on 2026-11-04): "vvvv:pppp[,vvvv:pppp...]", hex, read once and journaled. Empty (the default),
//    malformed, or nothing left after Sony's controllers are dropped: libusb is never loaded and every call answers as on
//    a host with no USB device (an empty list; nothing can be opened).
//  - libusb-1.0 is loaded at run time (dlopen of libusb-1.0.so.0 and dlsym), with our own minimal declarations after
//    libusb's public header libusb.h (github.com/libusb/libusb, LGPL-2.1-or-later): no compile or link command changes.
//    Missing library or symbol: a stderr line, then no host access. TODO(verify) the declarations against the container's
//    libusb 1.0.x; AnyPS5 Export.cpp:38-44 pins the same x86-64 layouts.
//  - Never passed through, even when listed: Sony's DualShock 4 (054c:05c4, 054c:09cc, dongle 054c:0ba0), DualSense
//    (054c:0ce6) and DualSense Edge (054c:0df2) (SDL src/joystick/usb_ids.h:40,60-63, zlib, as vendored in
//    github.com/InoriRus/Kyty @ 4733b7e; RPCS3 rpcs3/Input/ds4_pad_handler.cpp:11-13 and dualsense_pad_handler.cpp:28-29,
//    GPL-2.0, in github.com/RPCSX/rpcsx @ e8ae148; our libs/dualsense.h:27-28), and any device whose device class or any
//    interface of any configuration is HID (3) or audio (1), or whose descriptors cannot be read. Such a device is not in
//    the device list and sceUsbdOpenDeviceWithVidPid does not open it, so no call can open, claim or detach it.
//  - Where AnyPS5 has no answer (it throws: a device or handle this library never handed out, a null transfer, buffer or
//    output it would dereference, a second lock in one thread, an unlock or a wait without the lock, a timeout over
//    INT_MAX seconds, transfer flags other than short-not-ok and add-zero-packet, an exit or alternate setting with
//    transfers in flight, a halt error other than not-found), today's answer runs after one stderr line per function and
//    case ("... AnyPS5 has no answer for ...; today's answer kept").
//  - Host safety, TODO(verify): sceUsbdFreeTransfer frees only a transfer sceUsbdAllocTransfer handed out (AnyPS5 frees any
//    pointer that is not in flight); a sync transfer's count is written only for an open handle.
// Held, not registered when on: the four unnamed exports AnyPS5 does not have.
// AnyPS5's, shadPS4's and libusb's copyrights remain with their authors; GPL-2.0 as the rest of this file.
static bool Bc5UsbOn() {
»static const bool on = [] {
»»const char* e = std::getenv("KYTY_BC5_LOAD_USBD");
»»const bool  v = e != nullptr && e[0] != '\0' && std::strcmp(e, "0") != 0;
»»std::fprintf(stderr, "%s\n",
»»             v ? "[bc5] exp 0405: usbd port on (items: devicelist transfer fill iso cancel events checks, host transport "
»»                 "for KYTY_BC5_USBD_ALLOW devices; held: 4 unnamed)"
»»               : "[bc5] exp 0405: usbd port off");
»»std::fflush(stderr);
»»return v;
»}();
»return on;
}

// One stderr line per key: where AnyPS5 has no answer (the caller then runs today's answer), and the journal lines.
static bool Bc5UsbOnce(const std::string& key, const std::string& line) {
»static std::mutex m;
»static auto*      seen = new std::set<std::string>;
»std::lock_guard   lock(m);
»if (!seen->insert(key).second) {
»»return false;
»}
»std::fprintf(stderr, "[bc5] exp 0405: usbd %s\n", line.c_str());
»std::fflush(stderr);
»return true;
}

static std::nullopt_t Bc5UsbNoAnswer(const char* function, const char* what) {
»(void)Bc5UsbOnce(std::string(function) + "/" + what, std::string(function) + ": " + what + "; today's answer kept");
»return std::nullopt;
}

// ---- the allow-list ----------------------------------------------------------------------------------------------------
constexpr uint32_t BC5_USB_SONY_CONTROLLERS[] = {0x054C05C4u, 0x054C09CCu, 0x054C0BA0u, 0x054C0CE6u, 0x054C0DF2u};

static bool Bc5UsbSonyController(uint32_t id) {
»return std::find(std::begin(BC5_USB_SONY_CONTROLLERS), std::end(BC5_USB_SONY_CONTROLLERS), id) !=
»       std::end(BC5_USB_SONY_CONTROLLERS);
}

static std::string Bc5UsbId(uint32_t id) {
»char buf[16];
»std::snprintf(buf, sizeof(buf), "%04x:%04x", static_cast<unsigned>(id >> 16u), static_cast<unsigned>(id & 0xFFFFu));
»return buf;
}

// "vvvv:pppp" (four hex digits each); false when the text is anything else.
static bool Bc5UsbParseId(const std::string& text, uint32_t* id) {
»if (text.size() != 9 || text[4] != ':') {
»»return false;
»}
»uint32_t v = 0;
»for (size_t i = 0; i < 9; i++) {
»»if (i == 4) {
»»»continue;
»»}
»»const char c = text[i];
»»int        d = -1;
»»if (c >= '0' && c <= '9') {
»»»d = c - '0';
»»} else if (c >= 'a' && c <= 'f') {
»»»d = c - 'a' + 10;
»»} else if (c >= 'A' && c <= 'F') {
»»»d = c - 'A' + 10;
»»}
»»if (d < 0) {
»»»return false;
»»}
»»v = (v << 4u) | static_cast<uint32_t>(d);
»}
»*id = v;
»return true;
}

// KYTY_BC5_USBD_ALLOW, read once (InitUsbd_1 reads it when the switch is on) and journaled. Entries are separated by
// commas, blanks around them are ignored, an empty entry is skipped; one malformed entry refuses the whole list.
static const std::vector<uint32_t>& Bc5UsbAllowList() {
»static const std::vector<uint32_t> list = [] {
»»std::vector<uint32_t> ids;
»»const char*           e    = std::getenv("KYTY_BC5_USBD_ALLOW");
»»const std::string     text = e != nullptr ? e : "";
»»size_t                at   = 0;
»»while (at <= text.size()) {
»»»size_t end = text.find(',', at);
»»»if (end == std::string::npos) {
»»»»end = text.size();
»»»}
»»»std::string entry = text.substr(at, end - at);
»»»at               = end + 1;
»»»entry.erase(0, entry.find_first_not_of(" \t"));
»»»entry.erase(entry.find_last_not_of(" \t") + 1);
»»»if (entry.empty()) {
»»»»continue;
»»»}
»»»uint32_t id = 0;
»»»if (!Bc5UsbParseId(entry, &id)) {
»»»»(void)Bc5UsbOnce("allow", "allow-list KYTY_BC5_USBD_ALLOW refused, bad entry \"" + entry.substr(0, 32) +
»»»»                             "\" (want vvvv:pppp[,vvvv:pppp...]): no host USB access, libusb not loaded");
»»»»return std::vector<uint32_t> {};
»»»}
»»»if (Bc5UsbSonyController(id)) {
»»»»(void)Bc5UsbOnce("drop " + Bc5UsbId(id), "allow-list: " + Bc5UsbId(id) +
»»»»                                           " dropped (a Sony DualShock 4 or DualSense id, never passed through)");
»»»»continue;
»»»}
»»»if (std::find(ids.begin(), ids.end(), id) == ids.end()) {
»»»»ids.push_back(id);
»»»}
»»}
»»if (ids.empty()) {
»»»(void)Bc5UsbOnce("allow", "allow-list KYTY_BC5_USBD_ALLOW empty: no host USB access, libusb not loaded");
»»} else {
»»»std::string names;
»»»for (const uint32_t id: ids) {
»»»»names += " " + Bc5UsbId(id);
»»»}
»»»(void)Bc5UsbOnce("allow", "allow-list:" + names + " (a device with a HID or audio class is still refused)");
»»}
»»return ids;
»}();
»return list;
}

static bool Bc5UsbListed(uint32_t id) {
»const auto& ids = Bc5UsbAllowList();
»return std::find(ids.begin(), ids.end(), id) != ids.end();
}

// ---- libusb-1.0: our own declarations after libusb.h (LGPL-2.1-or-later), x86-64 ---------------------------------------
struct Bc5UsbDeviceDescriptor {
»uint8_t  bLength;
»uint8_t  bDescriptorType;
»uint16_t bcdUSB;
»uint8_t  bDeviceClass;
»uint8_t  bDeviceSubClass;
»uint8_t  bDeviceProtocol;
»uint8_t  bMaxPacketSize0;
»uint16_t idVendor;
»uint16_t idProduct;
»uint16_t bcdDevice;
»uint8_t  iManufacturer;
»uint8_t  iProduct;
»uint8_t  iSerialNumber;
»uint8_t  bNumConfigurations;
};
struct Bc5UsbEndpointDescriptor {
»uint8_t              bLength;
»uint8_t              bDescriptorType;
»uint8_t              bEndpointAddress;
»uint8_t              bmAttributes;
»uint16_t             wMaxPacketSize;
»uint8_t              bInterval;
»uint8_t              bRefresh;
»uint8_t              bSynchAddress;
»const unsigned char* extra;
»int                  extra_length;
};
struct Bc5UsbInterfaceDescriptor {
»uint8_t                         bLength;
»uint8_t                         bDescriptorType;
»uint8_t                         bInterfaceNumber;
»uint8_t                         bAlternateSetting;
»uint8_t                         bNumEndpoints;
»uint8_t                         bInterfaceClass;
»uint8_t                         bInterfaceSubClass;
»uint8_t                         bInterfaceProtocol;
»uint8_t                         iInterface;
»const Bc5UsbEndpointDescriptor* endpoint;
»const unsigned char*            extra;
»int                             extra_length;
};
struct Bc5UsbInterface {
»const Bc5UsbInterfaceDescriptor* altsetting;
»int                              num_altsetting;
};
struct Bc5UsbConfigDescriptor {
»uint8_t                bLength;
»uint8_t                bDescriptorType;
»uint16_t               wTotalLength;
»uint8_t                bNumInterfaces;
»uint8_t                bConfigurationValue;
»uint8_t                iConfiguration;
»uint8_t                bmAttributes;
»uint8_t                MaxPower;
»const Bc5UsbInterface* interfaces;
»const unsigned char*   extra;
»int                    extra_length;
};
struct Bc5UsbHostTransfer {
»void*    dev_handle;
»uint8_t  flags;
»uint8_t  endpoint;
»uint8_t  type;
»uint32_t timeout;
»int32_t  status;
»int32_t  length;
»int32_t  actual_length;
»void (*callback)(Bc5UsbHostTransfer*);
»void*    user_data;
»uint8_t* buffer;
»int32_t  num_iso_packets;
»// +60: num_iso_packets packet records (length, actual length, status)
};
struct Bc5UsbHostTimeval { // struct timeval
»long seconds;
»long microseconds;
};
static_assert(sizeof(Bc5UsbDeviceDescriptor) == 18 && offsetof(Bc5UsbDeviceDescriptor, idVendor) == 8 &&
              offsetof(Bc5UsbDeviceDescriptor, idProduct) == 10 &&
              offsetof(Bc5UsbDeviceDescriptor, bNumConfigurations) == 17,
              "libusb_device_descriptor");
static_assert(sizeof(Bc5UsbEndpointDescriptor) == 32 && offsetof(Bc5UsbEndpointDescriptor, wMaxPacketSize) == 4 &&
              offsetof(Bc5UsbEndpointDescriptor, extra) == 16 && offsetof(Bc5UsbEndpointDescriptor, extra_length) == 24,
              "libusb_endpoint_descriptor");
static_assert(sizeof(Bc5UsbInterfaceDescriptor) == 40 && offsetof(Bc5UsbInterfaceDescriptor, bInterfaceClass) == 5 &&
              offsetof(Bc5UsbInterfaceDescriptor, endpoint) == 16 && offsetof(Bc5UsbInterfaceDescriptor, extra) == 24 &&
              offsetof(Bc5UsbInterfaceDescriptor, extra_length) == 32,
              "libusb_interface_descriptor");
static_assert(sizeof(Bc5UsbInterface) == 16 && offsetof(Bc5UsbInterface, num_altsetting) == 8, "libusb_interface");
static_assert(sizeof(Bc5UsbConfigDescriptor) == 40 && offsetof(Bc5UsbConfigDescriptor, interfaces) == 16 &&
              offsetof(Bc5UsbConfigDescriptor, extra) == 24 && offsetof(Bc5UsbConfigDescriptor, extra_length) == 32,
              "libusb_config_descriptor");
static_assert(offsetof(Bc5UsbHostTransfer, timeout) == 12 && offsetof(Bc5UsbHostTransfer, status) == 16 &&
              offsetof(Bc5UsbHostTransfer, callback) == 32 && offsetof(Bc5UsbHostTransfer, buffer) == 48 &&
              offsetof(Bc5UsbHostTransfer, num_iso_packets) == 56,
              "libusb_transfer");

constexpr int     BC5_LIBUSB_ERROR_NO_DEVICE      = -4;
constexpr int     BC5_LIBUSB_ERROR_NOT_FOUND      = -5;
constexpr int     BC5_LIBUSB_ERROR_BUSY           = -6;
constexpr int     BC5_LIBUSB_ERROR_TIMEOUT        = -7;
constexpr int     BC5_LIBUSB_ERROR_NO_MEM         = -11;
constexpr int     BC5_LIBUSB_ERROR_OTHER          = -99;
constexpr int     BC5_LIBUSB_SPEED_UNKNOWN        = 0;
constexpr int     BC5_LIBUSB_SPEED_LOW            = 1;
constexpr int     BC5_LIBUSB_SPEED_FULL           = 2;
constexpr int     BC5_LIBUSB_SPEED_SUPER          = 4;
constexpr uint8_t BC5_LIBUSB_SHORT_NOT_OK         = 1u << 0u;
constexpr uint8_t BC5_LIBUSB_ADD_ZERO_PACKET      = 1u << 3u;
constexpr uint8_t BC5_LIBUSB_CLASS_AUDIO          = 1;
constexpr uint8_t BC5_LIBUSB_CLASS_HID            = 3;
constexpr uint8_t BC5_LIBUSB_DT_STRING            = 3;
constexpr uint8_t BC5_LIBUSB_ENDPOINT_IN          = 0x80;
constexpr uint8_t BC5_LIBUSB_REQUEST_GET_DESCRIPT = 6;
constexpr int     BC5_LIBUSB_DESCRIPTOR_TIMEOUT   = 1000; // libusb.h's inline libusb_get_descriptor and _string_descriptor

// The libusb functions the port calls (libusb.h's prototypes; LIBUSB_CALL is empty on Linux).
struct Bc5UsbLib {
»int (*init)(void** context);
»void (*exit)(void* context);
»std::ptrdiff_t (*get_device_list)(void* context, void*** list);
»void (*free_device_list)(void** list, int unref_devices);
»void* (*ref_device)(void* device);
»void (*unref_device)(void* device);
»int (*get_device_descriptor)(void* device, Bc5UsbDeviceDescriptor* descriptor);
»int (*get_active_config_descriptor)(void* device, Bc5UsbConfigDescriptor** config);
»int (*get_config_descriptor)(void* device, uint8_t config_index, Bc5UsbConfigDescriptor** config);
»int (*get_config_descriptor_by_value)(void* device, uint8_t config_value, Bc5UsbConfigDescriptor** config);
»void (*free_config_descriptor)(Bc5UsbConfigDescriptor* config);
»uint8_t (*get_bus_number)(void* device);
»uint8_t (*get_device_address)(void* device);
»int (*get_device_speed)(void* device);
»int (*open)(void* device, void** handle);
»void (*close)(void* handle);
»void* (*get_device)(void* handle);
»int (*get_configuration)(void* handle, int* config);
»int (*set_configuration)(void* handle, int config);
»int (*claim_interface)(void* handle, int interface_number);
»int (*release_interface)(void* handle, int interface_number);
»int (*set_interface_alt_setting)(void* handle, int interface_number, int alternate_setting);
»int (*clear_halt)(void* handle, unsigned char endpoint);
»int (*reset_device)(void* handle);
»int (*kernel_driver_active)(void* handle, int interface_number);
»int (*detach_kernel_driver)(void* handle, int interface_number);
»int (*control_transfer)(void* handle, uint8_t request_type, uint8_t request, uint16_t value, uint16_t index,
»                        unsigned char* data, uint16_t length, unsigned int timeout);
»int (*bulk_transfer)(void* handle, unsigned char endpoint, unsigned char* data, int length, int* transferred,
»                     unsigned int timeout);
»int (*interrupt_transfer)(void* handle, unsigned char endpoint, unsigned char* data, int length, int* transferred,
»                          unsigned int timeout);
»Bc5UsbHostTransfer* (*alloc_transfer)(int iso_packets);
»void (*free_transfer)(Bc5UsbHostTransfer* transfer);
»int (*submit_transfer)(Bc5UsbHostTransfer* transfer);
»int (*cancel_transfer)(Bc5UsbHostTransfer* transfer);
»int (*handle_events_timeout_completed)(void* context, Bc5UsbHostTimeval* timeout, int* completed);
};

static void* Bc5UsbDlsym(void* module, const char* name) {
#ifdef _WIN32
»(void)module;
»(void)name;
»return nullptr;
#else
»return dlsym(module, name);
#endif
}

// For the CPU test only (tus0405.cpp declares it): when set before the first sceUsbdInit, the port takes libusb's symbols
// from it and never calls dlopen. Nothing in the emulator sets it.
void* (*bc5_usb_symbols_for_test)(const char* name) = nullptr;

// libusb, loaded once, the first time a context is made: only with a non-empty allow-list.
static const Bc5UsbLib* Bc5UsbLibrary() {
»static const Bc5UsbLib* lib = []() -> const Bc5UsbLib* {
»»if (Bc5UsbAllowList().empty()) {
»»»return nullptr; // no allow-list: libusb is never loaded
»»}
»»void* (*const symbols)(const char*) = bc5_usb_symbols_for_test;
»»void* module                         = nullptr;
»»if (symbols == nullptr) {
#ifdef _WIN32
»»»(void)Bc5UsbOnce("lib", "libusb-1.0 is loaded only on Linux: no host USB access");
»»»return nullptr;
#else
»»»module = dlopen("libusb-1.0.so.0", RTLD_NOW | RTLD_LOCAL);
»»»if (module == nullptr) {
»»»»const char* why = dlerror();
»»»»(void)Bc5UsbOnce("lib", std::string("libusb-1.0.so.0 not loaded (") + (why != nullptr ? why : "?") +
»»»»                           "): no host USB access");
»»»»return nullptr;
»»»}
#endif
»»}
»»auto* l       = new Bc5UsbLib {};
»»bool  missing = false;
»»auto  get     = [&](auto& fn, const char* name) {
»»»void* p = symbols != nullptr ? symbols(name) : Bc5UsbDlsym(module, name);
»»»if (p == nullptr) {
»»»»missing = true;
»»»»(void)Bc5UsbOnce(std::string("sym ") + name, std::string("libusb-1.0.so.0 has no ") + name);
»»»}
»»»fn = reinterpret_cast<std::remove_reference_t<decltype(fn)>>(p);
»»};
»»get(l->init, "libusb_init");
»»get(l->exit, "libusb_exit");
»»get(l->get_device_list, "libusb_get_device_list");
»»get(l->free_device_list, "libusb_free_device_list");
»»get(l->ref_device, "libusb_ref_device");
»»get(l->unref_device, "libusb_unref_device");
»»get(l->get_device_descriptor, "libusb_get_device_descriptor");
»»get(l->get_active_config_descriptor, "libusb_get_active_config_descriptor");
»»get(l->get_config_descriptor, "libusb_get_config_descriptor");
»»get(l->get_config_descriptor_by_value, "libusb_get_config_descriptor_by_value");
»»get(l->free_config_descriptor, "libusb_free_config_descriptor");
»»get(l->get_bus_number, "libusb_get_bus_number");
»»get(l->get_device_address, "libusb_get_device_address");
»»get(l->get_device_speed, "libusb_get_device_speed");
»»get(l->open, "libusb_open");
»»get(l->close, "libusb_close");
»»get(l->get_device, "libusb_get_device");
»»get(l->get_configuration, "libusb_get_configuration");
»»get(l->set_configuration, "libusb_set_configuration");
»»get(l->claim_interface, "libusb_claim_interface");
»»get(l->release_interface, "libusb_release_interface");
»»get(l->set_interface_alt_setting, "libusb_set_interface_alt_setting");
»»get(l->clear_halt, "libusb_clear_halt");
»»get(l->reset_device, "libusb_reset_device");
»»get(l->kernel_driver_active, "libusb_kernel_driver_active");
»»get(l->detach_kernel_driver, "libusb_detach_kernel_driver");
»»get(l->control_transfer, "libusb_control_transfer");
»»get(l->bulk_transfer, "libusb_bulk_transfer");
»»get(l->interrupt_transfer, "libusb_interrupt_transfer");
»»get(l->alloc_transfer, "libusb_alloc_transfer");
»»get(l->free_transfer, "libusb_free_transfer");
»»get(l->submit_transfer, "libusb_submit_transfer");
»»get(l->cancel_transfer, "libusb_cancel_transfer");
»»get(l->handle_events_timeout_completed, "libusb_handle_events_timeout_completed");
»»if (missing) {
»»»delete l;
»»»return nullptr;
»»}
»»(void)Bc5UsbOnce("lib", symbols != nullptr ? "libusb-1.0 symbols from the test's stand-in"
»»                                           : "libusb-1.0.so.0 loaded (dlopen)");
»»return l;
»}();
»return lib;
}

// AnyPS5 :73-77.
static int32_t Bc5UsbGuestError(int result) {
»if (result >= 0) {
»»return result;
»}
»if (result == BC5_LIBUSB_ERROR_OTHER) {
»»return static_cast<int32_t>(0x802400FFu);
»}
»return static_cast<int32_t>(0x80240000u - static_cast<uint32_t>(result));
}

constexpr int32_t BC5_USB_INVALID_ARG     = static_cast<int32_t>(0x80240002u); // libusb INVALID_PARAM (-2)
constexpr int32_t BC5_USB_OTHER           = static_cast<int32_t>(0x802400FFu); // libusb OTHER (-99)
constexpr uint8_t BC5_USB_TYPE_CONTROL    = 0;
constexpr uint8_t BC5_USB_TYPE_ISO        = 1;
constexpr uint8_t BC5_USB_TYPE_BULK       = 2;
constexpr uint8_t BC5_USB_TYPE_INTERRUPT  = 3;
constexpr int32_t BC5_USB_SETUP_SIZE      = 8; // a control transfer's buffer starts with its 8-byte setup packet
constexpr int64_t BC5_USB_USEC_PER_SECOND = 1000000;
constexpr size_t  BC5_USB_STRING_SIZE     = 255;

// A transfer as the title holds it (libusb_transfer's layout, as above): the packet records follow at +60.
struct Bc5UsbIsoPacket {
»uint32_t length;
»uint32_t actual_length;
»int32_t  status;
};
struct Bc5UsbTransfer {
»void*    handle;
»uint8_t  flags;
»uint8_t  endpoint;
»uint8_t  type;
»uint32_t timeout;
»int32_t  status;
»int32_t  length;
»int32_t  actual_length;
»void*    callback; // the title's: void (*)(transfer), SysV
»void*    user_data;
»uint8_t* buffer;
»int32_t  iso_count;
};
constexpr size_t BC5_USB_ISO_OFFSET = 60;
static_assert(offsetof(Bc5UsbTransfer, flags) == 8 && offsetof(Bc5UsbTransfer, endpoint) == 9 &&
              offsetof(Bc5UsbTransfer, type) == 10 && offsetof(Bc5UsbTransfer, timeout) == 12 &&
              offsetof(Bc5UsbTransfer, status) == 16 && offsetof(Bc5UsbTransfer, length) == 20 &&
              offsetof(Bc5UsbTransfer, actual_length) == 24 && offsetof(Bc5UsbTransfer, callback) == 32 &&
              offsetof(Bc5UsbTransfer, user_data) == 40 && offsetof(Bc5UsbTransfer, buffer) == 48 &&
              offsetof(Bc5UsbTransfer, iso_count) == 56 && sizeof(Bc5UsbIsoPacket) == 12,
              "the transfer layout");
using Bc5UsbGuestCallback = void (KYTY_SYSV_ABI*)(void* transfer);

static Bc5UsbIsoPacket* Bc5UsbIso(void* transfer) {
»return reinterpret_cast<Bc5UsbIsoPacket*>(static_cast<uint8_t*>(transfer) + BC5_USB_ISO_OFFSET);
}

// The event calls' timeout: seconds, then microseconds.
struct Bc5UsbTimeval {
»int64_t seconds;
»int64_t microseconds;
};

// AnyPS5 :46-61: what the title holds. The devices, handles, lists and configurations exist only with a host context.
struct Bc5UsbState {
»std::mutex                mutex;
»std::set<void*>           transfers; // handed out by sceUsbdAllocTransfer and not yet freed
»void*                     context    = nullptr;
»uint32_t                  init_count = 0;
»std::map<void*, uint32_t> devices; // a device: the references the title holds
»std::set<void**>          lists;   // the device lists handed out (ours: the admitted devices, then null)
»std::set<void*>           handles;
»std::map<void*, uint32_t> claimed; // a handle: its claimed interfaces, one bit each
»std::set<void*>           configs;
»std::map<void*, Bc5UsbHostTransfer*> in_flight; // the title's transfer: its host copy
};

static Bc5UsbState& Bc5Usb() {
»static auto* s = new Bc5UsbState; // never destroyed: guest threads may call late
»return *s;
}

static void* bc5_usb_empty_list[1] = {nullptr}; // AnyPS5 :63: the list with no host context

static const Bc5UsbLib& Bc5UsbL() { // only where a host context exists, which needs the library
»return *Bc5UsbLibrary();
}

static void* Bc5UsbContext() {
»auto&           st = Bc5Usb();
»std::lock_guard lock(st.mutex);
»return st.context;
}

constexpr const char* BC5_USB_UNKNOWN_DEVICE =
    "AnyPS5 has no answer for a device sceUsbdGetDeviceList never returned or that was released";
constexpr const char* BC5_USB_UNKNOWN_HANDLE =
    "AnyPS5 has no answer for a handle sceUsbdOpen never returned or that was closed";
constexpr const char* BC5_USB_NULL_TRANSFER = "AnyPS5 has no answer for a null transfer";
constexpr const char* BC5_USB_NULL_DEVICE   = "AnyPS5 has no answer for a null device";
constexpr const char* BC5_USB_LOCKED_TWICE  = "AnyPS5 has no answer for a thread that holds the event lock already";
constexpr const char* BC5_USB_NOT_LOCKED    = "AnyPS5 has no answer for a thread that does not hold the event lock";
constexpr const char* BC5_USB_BAD_TIMEOUT   = "AnyPS5 has no answer for a negative or oversized timeout";

// AnyPS5 :79-97 (the caller holds the state's lock): a device the title holds, or the device of an open handle.
static bool Bc5UsbKnownDeviceLocked(const Bc5UsbState& st, void* device) {
»if (device == nullptr || st.context == nullptr) {
»»return false;
»}
»if (st.devices.count(device) != 0) {
»»return true;
»}
»return std::any_of(st.handles.begin(), st.handles.end(),
»                   [device](void* handle) { return Bc5UsbL().get_device(handle) == device; });
}

static bool Bc5UsbKnownDevice(void* device) {
»auto&           st = Bc5Usb();
»std::lock_guard lock(st.mutex);
»return Bc5UsbKnownDeviceLocked(st, device);
}

static bool Bc5UsbKnownHandle(void* handle) {
»auto&           st = Bc5Usb();
»std::lock_guard lock(st.mutex);
»return handle != nullptr && st.handles.count(handle) != 0;
}

// The gate: a device is passed through only when the allow-list names it, it is not one of Sony's controllers, and
// neither its device class nor any interface of any configuration is HID or audio; anything unreadable is refused.
static bool Bc5UsbRefuse(uint32_t id, const char* why) {
»(void)Bc5UsbOnce("refuse " + Bc5UsbId(id) + why, "device " + Bc5UsbId(id) + " refused: " + why);
»return false;
}

static bool Bc5UsbAdmit(const Bc5UsbLib& lib, void* device) {
»Bc5UsbDeviceDescriptor d {};
»if (lib.get_device_descriptor(device, &d) != 0) {
»»return false; // unreadable: not passed through (and its id is unknown)
»}
»const uint32_t id = (static_cast<uint32_t>(d.idVendor) << 16u) | d.idProduct;
»if (!Bc5UsbListed(id)) {
»»return false; // not listed: never visible to the title
»}
»if (Bc5UsbSonyController(id)) {
»»return Bc5UsbRefuse(id, "a Sony DualShock 4 or DualSense id");
»}
»if (d.bDeviceClass == BC5_LIBUSB_CLASS_HID || d.bDeviceClass == BC5_LIBUSB_CLASS_AUDIO) {
»»return Bc5UsbRefuse(id, "its device class is HID or audio");
»}
»if (d.bNumConfigurations == 0) {
»»return Bc5UsbRefuse(id, "it has no configuration to check");
»}
»for (uint8_t c = 0; c < d.bNumConfigurations; c++) {
»»Bc5UsbConfigDescriptor* config = nullptr;
»»if (lib.get_config_descriptor(device, c, &config) != 0 || config == nullptr) {
»»»return Bc5UsbRefuse(id, "a configuration that cannot be read");
»»}
»»bool hid_or_audio = false;
»»for (int i = 0; i < config->bNumInterfaces && !hid_or_audio; i++) {
»»»const Bc5UsbInterface& entry = config->interfaces[i];
»»»for (int a = 0; a < entry.num_altsetting && !hid_or_audio; a++) {
»»»»const uint8_t cls = entry.altsetting[a].bInterfaceClass;
»»»»hid_or_audio      = cls == BC5_LIBUSB_CLASS_HID || cls == BC5_LIBUSB_CLASS_AUDIO;
»»»}
»»}
»»lib.free_config_descriptor(config);
»»if (hid_or_audio) {
»»»return Bc5UsbRefuse(id, "an interface of class HID or audio");
»»}
»}
»return true;
}

// AnyPS5 :236-255: an endpoint's packet size, from the active configuration.
static int Bc5UsbMaxPacket(void* device, uint8_t endpoint) {
»const auto&             lib    = Bc5UsbL();
»Bc5UsbConfigDescriptor* config = nullptr;
»const int               result = lib.get_active_config_descriptor(device, &config);
»if (result < 0) {
»»return result;
»}
»int size = BC5_LIBUSB_ERROR_NOT_FOUND;
»for (int i = 0; i < config->bNumInterfaces && size == BC5_LIBUSB_ERROR_NOT_FOUND; i++) {
»»const Bc5UsbInterface& entry = config->interfaces[i];
»»for (int a = 0; a < entry.num_altsetting && size == BC5_LIBUSB_ERROR_NOT_FOUND; a++) {
»»»const Bc5UsbInterfaceDescriptor& setting = entry.altsetting[a];
»»»for (int e = 0; e < setting.bNumEndpoints; e++) {
»»»»if (setting.endpoint[e].bEndpointAddress == endpoint) {
»»»»»size = setting.endpoint[e].wMaxPacketSize;
»»»»»break;
»»»»}
»»»}
»»}
»}
»lib.free_config_descriptor(config);
»return size;
}

// libusb.h's inline libusb_get_descriptor and libusb_get_string_descriptor: a GET_DESCRIPTOR control request.
static int Bc5UsbGetDescriptorRequest(void* handle, uint8_t type, uint8_t index, uint16_t language, uint8_t* data,
                                      int length) {
»return Bc5UsbL().control_transfer(handle, BC5_LIBUSB_ENDPOINT_IN, BC5_LIBUSB_REQUEST_GET_DESCRIPT,
»                                  static_cast<uint16_t>((type << 8u) | index), language, data,
»                                  static_cast<uint16_t>(length), BC5_LIBUSB_DESCRIPTOR_TIMEOUT);
}

// AnyPS5 :257-262.
static bool Bc5UsbStringRequest(void* handle, uint8_t index, uint16_t language, uint8_t* descriptor) {
»std::memset(descriptor, 0, BC5_USB_STRING_SIZE);
»const int result = Bc5UsbGetDescriptorRequest(handle, BC5_LIBUSB_DT_STRING, index, language, descriptor,
»                                              static_cast<int>(BC5_USB_STRING_SIZE));
»return result >= 0 && descriptor[1] == BC5_LIBUSB_DT_STRING;
}

// ---- the events (AnyPS5 :109-210, after FreeBSD 11.4 libusb10_io.c) --------------------------------------------------
struct Bc5UsbEvents {
»std::mutex                   lock;
»std::condition_variable      changed;
»std::atomic<std::thread::id> owner {};
»std::atomic<std::thread::id> handler {};
»std::atomic<uint64_t>        completions {0}; // finished transfers
};

static Bc5UsbEvents& Bc5UsbEv() {
»static auto* e = new Bc5UsbEvents; // never destroyed: guest threads may call late
»return *e;
}

// AnyPS5 :212-228: the host transfer finished (on the thread that handles events): its result goes back to the title's
// transfer, then the title's callback runs.
static void Bc5UsbComplete(Bc5UsbHostTransfer* host) {
»auto* guest         = static_cast<Bc5UsbTransfer*>(host->user_data);
»guest->status        = host->status;
»guest->actual_length = host->actual_length;
»for (int32_t p = 0; p < host->num_iso_packets; p++) {
»»Bc5UsbIso(guest)[p].actual_length = Bc5UsbIso(host)[p].actual_length;
»»Bc5UsbIso(guest)[p].status        = Bc5UsbIso(host)[p].status;
»}
»{
»»auto&           st = Bc5Usb();
»»std::lock_guard lock(st.mutex);
»»st.in_flight.erase(guest);
»}
»Bc5UsbL().free_transfer(host);
»Bc5UsbEv().completions.fetch_add(1);
»if (guest->callback != nullptr) {
»»reinterpret_cast<Bc5UsbGuestCallback>(guest->callback)(guest);
»}
}

static bool Bc5UsbValidTimeout(const Bc5UsbTimeval* tv) {
»return tv == nullptr || (tv->seconds >= 0 && tv->seconds <= INT_MAX && tv->microseconds >= 0 &&
»                         tv->microseconds < BC5_USB_USEC_PER_SECOND);
}

static bool Bc5UsbHolds(const Bc5UsbEvents& ev) {
»return ev.owner.load() == std::this_thread::get_id();
}

// AnyPS5 :126-131; false: this thread holds the lock already.
static bool Bc5UsbAcquire(Bc5UsbEvents& ev) {
»if (Bc5UsbHolds(ev)) {
»»return false;
»}
»ev.lock.lock();
»ev.owner.store(std::this_thread::get_id());
»return true;
}

// AnyPS5 :137-141 (the caller holds the lock).
static void Bc5UsbRelease(Bc5UsbEvents& ev) {
»ev.owner.store(std::thread::id {});
»ev.lock.unlock();
}

// AnyPS5 :143-146.
static bool Bc5UsbAcquireAndClaim(Bc5UsbEvents& ev) {
»if (!Bc5UsbAcquire(ev)) {
»»return false;
»}
»if (ev.handler.load() == std::thread::id {}) {
»»ev.handler.store(std::this_thread::get_id());
»}
»return true;
}

// AnyPS5 :148-155 (the caller holds the lock).
static void Bc5UsbReleaseAndUnclaim(Bc5UsbEvents& ev) {
»if (ev.handler.load() == std::this_thread::get_id()) {
»»ev.handler.store(std::thread::id {});
»»ev.changed.notify_all();
»}
»Bc5UsbRelease(ev);
}

// AnyPS5 :157-172: a waiter (the caller holds the lock); 1 when its timeout ran out. It takes over handling when there
// is no handler.
static int Bc5UsbWaitForChange(Bc5UsbEvents& ev, const Bc5UsbTimeval* tv) {
»const auto       self = std::this_thread::get_id();
»std::unique_lock guard(ev.lock, std::adopt_lock);
»ev.owner.store(std::thread::id {});
»bool timed_out = false;
»if (tv == nullptr) {
»»ev.changed.wait(guard);
»} else {
»»const auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(tv->seconds) +
»»                      std::chrono::microseconds(tv->microseconds);
»»timed_out = ev.changed.wait_until(guard, deadline) == std::cv_status::timeout;
»}
»guard.release();
»ev.owner.store(self);
»if (ev.handler.load() == std::thread::id {}) {
»»ev.handler.store(self);
»}
»return timed_out ? 1 : 0;
}

// AnyPS5 :176-205: the handler lets the lock go and handles host events for its timeout (with none, until a transfer
// completes); with no host context it sleeps instead. Then it takes the lock back and wakes the waiters.
static int Bc5UsbHandlePass(Bc5UsbEvents& ev, const Bc5UsbTimeval* tv) {
»const auto self   = std::this_thread::get_id();
»const auto before = ev.completions.load();
»ev.owner.store(std::thread::id {});
»ev.lock.unlock();
»void* context = Bc5UsbContext();
»int   result  = 0;
»if (tv != nullptr && context == nullptr) {
»»std::this_thread::sleep_for(std::chrono::seconds(tv->seconds) + std::chrono::microseconds(tv->microseconds));
»} else if (tv != nullptr) {
»»Bc5UsbHostTimeval host {static_cast<long>(tv->seconds), static_cast<long>(tv->microseconds)};
»»result = Bc5UsbL().handle_events_timeout_completed(context, &host, nullptr);
»} else {
»»while (result == 0 && ev.completions.load() == before) {
»»»if (context == nullptr) {
»»»»std::this_thread::sleep_for(std::chrono::milliseconds(100));
»»»} else {
»»»»Bc5UsbHostTimeval slice {1, 0};
»»»»result = Bc5UsbL().handle_events_timeout_completed(context, &slice, nullptr);
»»»}
»»}
»}
»ev.lock.lock();
»ev.owner.store(self);
»ev.changed.notify_all();
»return result;
}

// AnyPS5 :207-210 (the caller holds the lock).
static int Bc5UsbHandleLocked(Bc5UsbEvents& ev, const Bc5UsbTimeval* tv) {
»if (ev.handler.load() == std::this_thread::get_id()) {
»»return Bc5UsbGuestError(Bc5UsbHandlePass(ev, tv));
»}
»return Bc5UsbWaitForChange(ev, tv) != 0 ? Bc5UsbGuestError(BC5_LIBUSB_ERROR_TIMEOUT) : 0;
}

// ---- the exports' ports ----------------------------------------------------------------------------------------------
// AnyPS5 :268-277: the first Init makes the host context (only with an allow-list; otherwise there is none).
static int Bc5UsbInit() {
»auto&           st = Bc5Usb();
»std::lock_guard lock(st.mutex);
»if (st.init_count == 0) {
»»const Bc5UsbLib* lib     = Bc5UsbLibrary();
»»void*            context = nullptr;
»»if (lib != nullptr && lib->init(&context) == 0) {
»»»st.context = context;
»»}
»}
»++st.init_count;
»return 0;
}

// AnyPS5 :279-297: the last Exit releases everything the title still holds, then the context.
static std::optional<int> Bc5UsbExit() {
»auto&           st = Bc5Usb();
»std::lock_guard lock(st.mutex);
»if (st.init_count == 0) {
»»return OK;
»}
»if (st.init_count == 1 && !st.in_flight.empty()) {
»»return Bc5UsbNoAnswer("sceUsbdExit", "AnyPS5 has no answer for the last exit with transfers in flight");
»}
»if (--st.init_count != 0 || st.context == nullptr) {
»»return OK;
»}
»const auto& lib = Bc5UsbL();
»for (void* handle: st.handles) {
»»lib.close(handle);
»}
»for (void* config: st.configs) {
»»lib.free_config_descriptor(static_cast<Bc5UsbConfigDescriptor*>(config));
»}
»for (void** list: st.lists) {
»»delete[] list;
»}
»for (const auto& [device, references]: st.devices) {
»»for (uint32_t r = 0; r < references; r++) {
»»»lib.unref_device(device);
»»}
»}
»st.handles.clear();
»st.claimed.clear();
»st.configs.clear();
»st.lists.clear();
»st.devices.clear();
»lib.exit(st.context);
»st.context = nullptr;
»return OK;
}

// AnyPS5 :299-314: with a host context, only the devices the gate admits are listed (each with one reference).
static int64_t Bc5UsbGetDeviceList(void*** list) {
»if (list == nullptr) {
»»return BC5_USB_INVALID_ARG;
»}
»auto&           st = Bc5Usb();
»std::lock_guard lock(st.mutex);
»if (st.context == nullptr) {
»»*list = bc5_usb_empty_list;
»»return 0;
»}
»const auto&          lib   = Bc5UsbL();
»void**               all   = nullptr;
»const std::ptrdiff_t count = lib.get_device_list(st.context, &all);
»if (count < 0) {
»»return Bc5UsbGuestError(static_cast<int>(count));
»}
»std::vector<void*> admitted;
»for (std::ptrdiff_t i = 0; i < count; i++) {
»»if (Bc5UsbAdmit(lib, all[i])) {
»»»admitted.push_back(all[i]);
»»}
»}
»auto** ours = new void*[admitted.size() + 1];
»for (size_t i = 0; i < admitted.size(); i++) {
»»ours[i] = lib.ref_device(admitted[i]);
»»++st.devices[admitted[i]];
»}
»ours[admitted.size()] = nullptr;
»lib.free_device_list(all, 1);
»st.lists.insert(ours);
»*list = ours;
»return static_cast<int64_t>(admitted.size());
}

// AnyPS5 :316-326.
static std::optional<int> Bc5UsbFreeDeviceList(void** list, int32_t unref_devices) {
»if (list == nullptr || list == bc5_usb_empty_list) {
»»return OK;
»}
»auto&           st = Bc5Usb();
»std::lock_guard lock(st.mutex);
»if (st.lists.erase(list) == 0) {
»»return Bc5UsbNoAnswer("sceUsbdFreeDeviceList", "AnyPS5 has no answer for a list sceUsbdGetDeviceList did not return");
»}
»if (unref_devices != 0) {
»»for (void** device = list; *device != nullptr; device++) {
»»»auto found = st.devices.find(*device);
»»»if (found != st.devices.end() && --found->second == 0) {
»»»»st.devices.erase(found);
»»»}
»»»Bc5UsbL().unref_device(*device);
»»}
»}
»delete[] list;
»return OK;
}

// AnyPS5 :338-345: zeroed, with its packet count set; a negative count gives null.
static uint64_t Bc5UsbAllocTransfer(int32_t iso_count) {
»if (iso_count < 0) {
»»return 0;
»}
»const size_t size =
»    std::max(sizeof(Bc5UsbTransfer), BC5_USB_ISO_OFFSET + sizeof(Bc5UsbIsoPacket) * static_cast<size_t>(iso_count));
»auto* t = static_cast<Bc5UsbTransfer*>(std::calloc(1, size));
»if (t == nullptr) {
»»return 0;
»}
»t->iso_count = iso_count;
»auto&           st = Bc5Usb();
»std::lock_guard lock(st.mutex);
»st.transfers.insert(t);
»return reinterpret_cast<uint64_t>(t);
}

// AnyPS5 :347-355.
static std::optional<int> Bc5UsbFreeTransfer(void* transfer) {
»if (transfer == nullptr) {
»»return OK;
»}
»{
»»auto&           st = Bc5Usb();
»»std::lock_guard lock(st.mutex);
»»if (st.in_flight.count(transfer) != 0) {
»»»return Bc5UsbNoAnswer("sceUsbdFreeTransfer", "AnyPS5 has no answer for a transfer still in flight");
»»}
»»if (st.transfers.erase(transfer) == 0) {
»»»return Bc5UsbNoAnswer("sceUsbdFreeTransfer",
»»»                      "a transfer sceUsbdAllocTransfer did not hand out is not freed (host safety)");
»»}
»}
»std::free(transfer);
»return OK;
}

// AnyPS5 :357-392.
static std::optional<int> Bc5UsbFill(const char* function, void* transfer, void* handle, uint8_t endpoint, uint8_t type,
                                     uint8_t* buffer, int32_t length, void* callback, void* user_data, uint32_t timeout) {
»if (transfer == nullptr) {
»»return Bc5UsbNoAnswer(function, BC5_USB_NULL_TRANSFER);
»}
»auto* t      = static_cast<Bc5UsbTransfer*>(transfer);
»t->handle    = handle;
»t->endpoint  = endpoint;
»t->type      = type;
»t->timeout   = timeout;
»t->buffer    = buffer;
»t->length    = length;
»t->user_data = user_data;
»t->callback  = callback;
»return OK;
}

static std::optional<int> Bc5UsbFillIso(void* transfer, void* handle, uint8_t endpoint, uint8_t* buffer, int32_t length,
                                        int32_t iso_count, void* callback, void* user_data, uint32_t timeout) {
»const auto answer = Bc5UsbFill("sceUsbdFillIsoTransfer", transfer, handle, endpoint, BC5_USB_TYPE_ISO, buffer, length,
»                               callback, user_data, timeout);
»if (answer) {
»»static_cast<Bc5UsbTransfer*>(transfer)->iso_count = iso_count;
»}
»return answer;
}

// AnyPS5 :394-404: the 8-byte setup packet, its 16-bit fields little-endian.
static std::optional<int> Bc5UsbFillControlSetup(uint8_t* buffer, uint8_t request_type, uint8_t request, uint16_t value,
                                                 uint16_t index, uint16_t length) {
»if (buffer == nullptr) {
»»return Bc5UsbNoAnswer("sceUsbdFillControlSetup", "AnyPS5 has no answer for a null buffer");
»}
»buffer[0] = request_type;
»buffer[1] = request;
»buffer[2] = static_cast<uint8_t>(value & 0xFFu);
»buffer[3] = static_cast<uint8_t>(value >> 8u);
»buffer[4] = static_cast<uint8_t>(index & 0xFFu);
»buffer[5] = static_cast<uint8_t>(index >> 8u);
»buffer[6] = static_cast<uint8_t>(length & 0xFFu);
»buffer[7] = static_cast<uint8_t>(length >> 8u);
»return OK;
}

// AnyPS5 :406-416: endpoint 0; the length is the setup packet plus the wLength it holds, 0 without a buffer.
static std::optional<int> Bc5UsbFillControl(void* transfer, void* handle, uint8_t* buffer, void* callback, void* user_data,
                                            uint32_t timeout) {
»if (transfer == nullptr) {
»»return Bc5UsbNoAnswer("sceUsbdFillControlTransfer", BC5_USB_NULL_TRANSFER);
»}
»const int32_t length = buffer != nullptr ? BC5_USB_SETUP_SIZE + (buffer[6] | (buffer[7] << 8)) : 0;
»return Bc5UsbFill("sceUsbdFillControlTransfer", transfer, handle, 0, BC5_USB_TYPE_CONTROL, buffer, length, callback,
»                  user_data, timeout);
}

// AnyPS5 :418-426.
static std::optional<uint64_t> Bc5UsbControlData(void* transfer) {
»if (transfer == nullptr) {
»»return Bc5UsbNoAnswer("sceUsbdControlTransferGetData", BC5_USB_NULL_TRANSFER);
»}
»const auto* t = static_cast<Bc5UsbTransfer*>(transfer);
»return t->buffer != nullptr ? reinterpret_cast<uint64_t>(t->buffer + BC5_USB_SETUP_SIZE) : uint64_t {0};
}

static std::optional<uint64_t> Bc5UsbControlSetup(void* transfer) {
»if (transfer == nullptr) {
»»return Bc5UsbNoAnswer("sceUsbdControlTransferGetSetup", BC5_USB_NULL_TRANSFER);
»}
»return reinterpret_cast<uint64_t>(static_cast<Bc5UsbTransfer*>(transfer)->buffer);
}

// AnyPS5 :428-439.
static std::optional<int> Bc5UsbSetIsoLengths(void* transfer, uint32_t length) {
»if (transfer == nullptr) {
»»return Bc5UsbNoAnswer("sceUsbdSetIsoPacketLengths", BC5_USB_NULL_TRANSFER);
»}
»auto* t = static_cast<Bc5UsbTransfer*>(transfer);
»auto* p = Bc5UsbIso(t);
»for (int32_t i = 0; i < t->iso_count; i++) {
»»p[i].length = length;
»}
»return OK;
}

static std::optional<uint64_t> Bc5UsbIsoBuffer(void* transfer, uint32_t packet) {
»if (transfer == nullptr) {
»»return Bc5UsbNoAnswer("sceUsbdGetIsoPacketBuffer", BC5_USB_NULL_TRANSFER);
»}
»auto* t = static_cast<Bc5UsbTransfer*>(transfer);
»if (t->iso_count < 0 || packet >= static_cast<uint32_t>(t->iso_count) || t->buffer == nullptr) {
»»return uint64_t {0};
»}
»const auto* p  = Bc5UsbIso(t);
»uint8_t*    at = t->buffer;
»for (uint32_t i = 0; i < packet; i++) {
»»at += p[i].length;
»}
»return reinterpret_cast<uint64_t>(at);
}

// AnyPS5 :441-453 (the count is written once the handle is known to be open).
static std::optional<int> Bc5UsbSyncTransfer(const char* function, bool interrupt, void* handle, uint8_t endpoint,
                                             uint8_t* data, int32_t length, int32_t* transferred, uint32_t timeout) {
»if (handle == nullptr || (length != 0 && data == nullptr)) {
»»return BC5_USB_INVALID_ARG;
»}
»if (transferred == nullptr) {
»»return Bc5UsbNoAnswer(function, "AnyPS5 has no answer for a null transferred output");
»}
»if (!Bc5UsbKnownHandle(handle)) {
»»return Bc5UsbNoAnswer(function, BC5_USB_UNKNOWN_HANDLE);
»}
»*transferred     = 0;
»const auto& lib = Bc5UsbL();
»int         n   = 0;
»const int   r   = interrupt ? lib.interrupt_transfer(handle, endpoint, data, length, &n, timeout)
»                            : lib.bulk_transfer(handle, endpoint, data, length, &n, timeout);
»*transferred     = n;
»return Bc5UsbGuestError(r);
}

// AnyPS5 :455-462.
static std::optional<int> Bc5UsbCancel(void* transfer) {
»if (transfer == nullptr) {
»»return Bc5UsbNoAnswer("sceUsbdCancelTransfer", BC5_USB_NULL_TRANSFER);
»}
»auto&           st = Bc5Usb();
»std::lock_guard lock(st.mutex);
»const auto      found = st.in_flight.find(transfer);
»if (found == st.in_flight.end()) {
»»return Bc5UsbGuestError(BC5_LIBUSB_ERROR_NOT_FOUND);
»}
»return Bc5UsbGuestError(Bc5UsbL().cancel_transfer(found->second));
}

// AnyPS5 :468-475.
static std::optional<int> Bc5UsbFreeConfig(void* config) {
»if (config == nullptr) {
»»return OK;
»}
»auto&           st = Bc5Usb();
»std::lock_guard lock(st.mutex);
»if (st.configs.erase(config) == 0) {
»»return Bc5UsbNoAnswer("sceUsbdFreeConfigDescriptor",
»»                      "AnyPS5 has no answer for a descriptor this library did not return");
»}
»Bc5UsbL().free_config_descriptor(static_cast<Bc5UsbConfigDescriptor*>(config));
»return OK;
}

// The calls on a handle: refused arguments answer INVALID_ARG; a handle that is not open has no answer.
static bool Bc5UsbOpenHandle(const char* function, void* handle, std::optional<int>* answer, bool refused = false) {
»if (handle == nullptr || refused) {
»»*answer = BC5_USB_INVALID_ARG;
»»return false;
»}
»if (!Bc5UsbKnownHandle(handle)) {
»»*answer = Bc5UsbNoAnswer(function, BC5_USB_UNKNOWN_HANDLE);
»»return false;
»}
»return true;
}

// The calls on a device: the same for devices.
static bool Bc5UsbHeldDevice(const char* function, void* device, std::optional<int>* answer, bool refused = false) {
»if (device == nullptr || refused) {
»»*answer = BC5_USB_INVALID_ARG;
»»return false;
»}
»if (!Bc5UsbKnownDevice(device)) {
»»*answer = Bc5UsbNoAnswer(function, BC5_USB_UNKNOWN_DEVICE);
»»return false;
»}
»return true;
}

// AnyPS5 :477-482 (FreeBSD's stub: 0 for an open handle).
static std::optional<int> Bc5UsbAttachKernelDriver(void* handle) {
»std::optional<int> answer;
»if (!Bc5UsbOpenHandle("sceUsbdAttachKernelDriver", handle, &answer)) {
»»return answer;
»}
»return 0;
}

// AnyPS5 :484-489.
static std::optional<int> Bc5UsbCheckConnected(void* handle) {
»std::optional<int> answer;
»if (!Bc5UsbOpenHandle("sceUsbdCheckConnected", handle, &answer)) {
»»return answer;
»}
»int       configuration = 0;
»const int result        = Bc5UsbL().get_configuration(handle, &configuration);
»return result == BC5_LIBUSB_ERROR_NO_DEVICE ? Bc5UsbGuestError(BC5_LIBUSB_ERROR_NO_DEVICE) : 0;
}

// AnyPS5 :491-501, 597-607.
static std::optional<int> Bc5UsbClaim(void* handle, int32_t interface_number, bool claim) {
»std::optional<int> answer;
»if (!Bc5UsbOpenHandle(claim ? "sceUsbdClaimInterface" : "sceUsbdReleaseInterface", handle, &answer)) {
»»return answer;
»}
»const auto& lib    = Bc5UsbL();
»const int   result = claim ? lib.claim_interface(handle, interface_number) : lib.release_interface(handle, interface_number);
»if (result == 0 && interface_number >= 0 && interface_number < 32) {
»»auto&           st = Bc5Usb();
»»std::lock_guard lock(st.mutex);
»»const uint32_t  bit = 1u << static_cast<uint32_t>(interface_number);
»»if (claim) {
»»»st.claimed[handle] |= bit;
»»} else {
»»»st.claimed[handle] &= ~bit;
»»}
»}
»return Bc5UsbGuestError(result);
}

// AnyPS5 :503-511.
static std::optional<int> Bc5UsbClose(void* handle) {
»if (handle == nullptr) {
»»return OK;
»}
»auto&           st = Bc5Usb();
»std::lock_guard lock(st.mutex);
»if (st.handles.erase(handle) == 0) {
»»return Bc5UsbNoAnswer("sceUsbdClose", BC5_USB_UNKNOWN_HANDLE);
»}
»st.claimed.erase(handle);
»Bc5UsbL().close(handle);
»return OK;
}

// AnyPS5 :513-516.
static std::optional<int> Bc5UsbControlTransfer(void* handle, uint8_t request_type, uint8_t request, uint16_t value,
                                                uint16_t index, uint8_t* data, uint16_t length, uint32_t timeout) {
»std::optional<int> answer;
»if (!Bc5UsbOpenHandle("sceUsbdControlTransfer", handle, &answer, length != 0 && data == nullptr)) {
»»return answer;
»}
»return Bc5UsbGuestError(Bc5UsbL().control_transfer(handle, request_type, request, value, index, data, length, timeout));
}

// AnyPS5 :518-530, 537-548, 682-693: the descriptor is the host's, kept until sceUsbdFreeConfigDescriptor.
static std::optional<int> Bc5UsbConfig(const char* function, int which, void* device, uint8_t value, void** config) {
»if (which == 0 && device == nullptr) {
»»return Bc5UsbNoAnswer(function, BC5_USB_NULL_DEVICE);
»}
»std::optional<int> answer;
»if (!Bc5UsbHeldDevice(function, device, &answer, config == nullptr)) {
»»return answer;
»}
»const auto&             lib    = Bc5UsbL();
»Bc5UsbConfigDescriptor* host   = nullptr;
»const int               result = which == 0   ? lib.get_active_config_descriptor(device, &host)
»                                 : which == 1 ? lib.get_config_descriptor(device, value, &host)
»                                              : lib.get_config_descriptor_by_value(device, value, &host);
»*config                        = nullptr;
»if (result != 0) {
»»return Bc5UsbGuestError(result);
»}
»auto&           st = Bc5Usb();
»std::lock_guard lock(st.mutex);
»st.configs.insert(host);
»*config = host;
»return 0;
}

// AnyPS5 :532-535, 550-553, 715-718: 0 for null.
static std::optional<int> Bc5UsbDeviceValue(const char* function, int which, void* device) {
»if (device == nullptr) {
»»return which == 2 ? BC5_LIBUSB_SPEED_UNKNOWN : 0;
»}
»if (!Bc5UsbKnownDevice(device)) {
»»return Bc5UsbNoAnswer(function, BC5_USB_UNKNOWN_DEVICE);
»}
»const auto& lib = Bc5UsbL();
»if (which == 0) {
»»return lib.get_bus_number(device);
»}
»if (which == 1) {
»»return lib.get_device_address(device);
»}
»return std::min(lib.get_device_speed(device), BC5_LIBUSB_SPEED_SUPER);
}

// AnyPS5 :555-558.
static std::optional<int> Bc5UsbGetDeviceDescriptor(void* device, void* descriptor) {
»std::optional<int> answer;
»if (!Bc5UsbHeldDevice("sceUsbdGetDeviceDescriptor", device, &answer, descriptor == nullptr)) {
»»return answer;
»}
»return Bc5UsbGuestError(
»    Bc5UsbL().get_device_descriptor(device, static_cast<Bc5UsbDeviceDescriptor*>(descriptor)));
}

// AnyPS5 :560-566, 703-708.
static std::optional<int> Bc5UsbDescriptor(const char* function, uint8_t type, uint8_t index, uint16_t language,
                                           void* handle, uint8_t* data, int32_t length) {
»std::optional<int> answer;
»if (!Bc5UsbOpenHandle(function, handle, &answer, data == nullptr || length < 1)) {
»»return answer;
»}
»if (length > 65535) {
»»length = 65535;
»}
»if (type == BC5_LIBUSB_DT_STRING) {
»»data[0] = 0;
»}
»return Bc5UsbGuestError(Bc5UsbGetDescriptorRequest(handle, type, index, language, data, length));
}

// AnyPS5 :568-571, 609-617, 673-676: one handle and one integer.
static std::optional<int> Bc5UsbHandleCall(const char* function, int which, void* handle, int32_t number) {
»std::optional<int> answer;
»if (!Bc5UsbOpenHandle(function, handle, &answer)) {
»»return answer;
»}
»const auto& lib = Bc5UsbL();
»switch (which) {
»»case 0: return Bc5UsbGuestError(lib.kernel_driver_active(handle, number));
»»case 1: return Bc5UsbGuestError(lib.reset_device(handle));
»»case 2: return Bc5UsbGuestError(lib.set_configuration(handle, number));
»»default: return lib.detach_kernel_driver(handle, static_cast<uint8_t>(number)) == 0 ? 0 : BC5_USB_OTHER;
»}
}

// AnyPS5 :573-585.
static std::optional<int> Bc5UsbOpen(void* device, void** handle) {
»if (device == nullptr) {
»»return Bc5UsbNoAnswer("sceUsbdOpen", BC5_USB_NULL_DEVICE);
»}
»std::optional<int> answer;
»if (!Bc5UsbHeldDevice("sceUsbdOpen", device, &answer, handle == nullptr)) {
»»return answer;
»}
»*handle        = nullptr;
»void*     host = nullptr;
»const int r    = Bc5UsbL().open(device, &host);
»if (r != 0) {
»»return Bc5UsbGuestError(r);
»}
»auto&           st = Bc5Usb();
»std::lock_guard lock(st.mutex);
»st.handles.insert(host);
»*handle = host;
»return 0;
}

// AnyPS5 :587-595, 656-663.
static std::optional<uint64_t> Bc5UsbRefDevice(void* device) {
»if (device == nullptr) {
»»return uint64_t {0};
»}
»auto&           st = Bc5Usb();
»std::lock_guard lock(st.mutex);
»if (!Bc5UsbKnownDeviceLocked(st, device)) {
»»return Bc5UsbNoAnswer("sceUsbdRefDevice", BC5_USB_UNKNOWN_DEVICE);
»}
»++st.devices[device];
»return reinterpret_cast<uint64_t>(Bc5UsbL().ref_device(device));
}

static std::optional<int> Bc5UsbUnrefDevice(void* device) {
»if (device == nullptr) {
»»return OK;
»}
»auto&           st = Bc5Usb();
»std::lock_guard lock(st.mutex);
»const auto      found = st.devices.find(device);
»if (found == st.devices.end()) {
»»return Bc5UsbNoAnswer("sceUsbdUnrefDevice", BC5_USB_UNKNOWN_DEVICE);
»}
»if (--found->second == 0) {
»»st.devices.erase(found);
»}
»Bc5UsbL().unref_device(device);
»return OK;
}

// AnyPS5 :619-654: a host copy of the title's transfer; its completion comes back through event handling.
static std::optional<int> Bc5UsbSubmit(void* transfer) {
»auto* t = static_cast<Bc5UsbTransfer*>(transfer);
»if (t == nullptr || t->handle == nullptr) {
»»return BC5_USB_INVALID_ARG;
»}
»if (!Bc5UsbKnownHandle(t->handle)) {
»»return Bc5UsbNoAnswer("sceUsbdSubmitTransfer", BC5_USB_UNKNOWN_HANDLE);
»}
»if ((t->flags & ~(BC5_LIBUSB_SHORT_NOT_OK | BC5_LIBUSB_ADD_ZERO_PACKET)) != 0) {
»»return Bc5UsbNoAnswer("sceUsbdSubmitTransfer", "AnyPS5 has no answer for transfer flags other than 1 and 8");
»}
»if (t->iso_count < 0) {
»»return BC5_USB_INVALID_ARG;
»}
»const auto& lib  = Bc5UsbL();
»auto*       host = lib.alloc_transfer(t->iso_count);
»if (host == nullptr) {
»»return Bc5UsbGuestError(BC5_LIBUSB_ERROR_NO_MEM);
»}
»host->dev_handle      = t->handle;
»host->flags           = t->flags;
»host->endpoint        = t->endpoint;
»host->type            = t->type;
»host->timeout         = t->timeout;
»host->length          = t->length;
»host->buffer          = t->buffer;
»host->user_data       = t;
»host->callback        = Bc5UsbComplete;
»host->num_iso_packets = t->iso_count;
»for (int32_t p = 0; p < t->iso_count; p++) {
»»Bc5UsbIso(host)[p].length = Bc5UsbIso(t)[p].length;
»}
»auto& st = Bc5Usb();
»{
»»std::lock_guard lock(st.mutex);
»»if (!st.in_flight.emplace(t, host).second) {
»»»lib.free_transfer(host);
»»»return Bc5UsbGuestError(BC5_LIBUSB_ERROR_BUSY);
»»}
»}
»const int result = lib.submit_transfer(host);
»if (result != 0) {
»»{
»»»std::lock_guard lock(st.mutex);
»»»st.in_flight.erase(t);
»»}
»»lib.free_transfer(host);
»}
»return Bc5UsbGuestError(result);
}

// AnyPS5 :665-671.
static std::optional<int> Bc5UsbClearHalt(void* handle, uint8_t endpoint) {
»if (handle == nullptr) {
»»return Bc5UsbNoAnswer("sceUsbdClearHalt", "AnyPS5 has no answer for a null handle");
»}
»if (!Bc5UsbKnownHandle(handle)) {
»»return Bc5UsbNoAnswer("sceUsbdClearHalt", BC5_USB_UNKNOWN_HANDLE);
»}
»const int result = Bc5UsbL().clear_halt(handle, endpoint);
»if (result == 0) {
»»return 0;
»}
»if (result == BC5_LIBUSB_ERROR_NOT_FOUND) {
»»return BC5_USB_OTHER;
»}
»return Bc5UsbNoAnswer("sceUsbdClearHalt", "AnyPS5 has no answer for a halt error other than not found");
}

// AnyPS5 :695-701.
static std::optional<int> Bc5UsbGetConfiguration(void* handle, int32_t* configuration) {
»std::optional<int> answer;
»if (!Bc5UsbOpenHandle("sceUsbdGetConfiguration", handle, &answer, configuration == nullptr)) {
»»return answer;
»}
»int       host   = 0;
»const int result = Bc5UsbL().get_configuration(handle, &host);
»if (result == 0) {
»»*configuration = host;
»}
»return Bc5UsbGuestError(result);
}

// AnyPS5 :710-713.
static std::optional<uint64_t> Bc5UsbGetDevice(void* handle) {
»if (handle == nullptr) {
»»return uint64_t {0};
»}
»if (!Bc5UsbKnownHandle(handle)) {
»»return Bc5UsbNoAnswer("sceUsbdGetDevice", BC5_USB_UNKNOWN_HANDLE);
»}
»return reinterpret_cast<uint64_t>(Bc5UsbL().get_device(handle));
}

// AnyPS5 :720-732: FreeBSD's sizes, from the active configuration; the iso size scaled above full speed.
static std::optional<int> Bc5UsbPacketSize(bool iso, void* device, uint8_t endpoint) {
»const char* function = iso ? "sceUsbdGetMaxIsoPacketSize" : "sceUsbdGetMaxPacketSize";
»if (device == nullptr) {
»»if (iso) {
»»»return Bc5UsbNoAnswer(function, BC5_USB_NULL_DEVICE);
»»}
»»return Bc5UsbGuestError(BC5_LIBUSB_ERROR_NO_DEVICE);
»}
»if (!Bc5UsbKnownDevice(device)) {
»»return Bc5UsbNoAnswer(function, BC5_USB_UNKNOWN_DEVICE);
»}
»int size = Bc5UsbMaxPacket(device, endpoint);
»if (iso) {
»»const int speed = Bc5UsbL().get_device_speed(device);
»»if (speed != BC5_LIBUSB_SPEED_LOW && speed != BC5_LIBUSB_SPEED_FULL && size >= 0) {
»»»size = (size & 0x7FF) * std::min(1 + ((size >> 11) & 3), 3);
»»}
»}
»return Bc5UsbGuestError(size);
}

// AnyPS5 :734-764: libusb20_dev_req_string_simple_sync's two reads; printable ASCII only, no '<' or '>'.
static std::optional<int> Bc5UsbStringAscii(void* handle, uint8_t index, uint8_t* data, int32_t length) {
»std::optional<int> answer;
»if (!Bc5UsbOpenHandle("sceUsbdGetStringDescriptorAscii", handle, &answer, data == nullptr || length < 1)) {
»»return answer;
»}
»if (length > 65535) {
»»length = 65535;
»}
»data[0] = 0;
»uint8_t descriptor[BC5_USB_STRING_SIZE];
»if (!Bc5UsbStringRequest(handle, 0, 0, descriptor)) {
»»return BC5_USB_OTHER;
»}
»const auto language = static_cast<uint16_t>(descriptor[2] | (descriptor[3] << 8));
»if (!Bc5UsbStringRequest(handle, index, language, descriptor) || descriptor[0] < 2) {
»»return BC5_USB_OTHER;
»}
»int32_t units = descriptor[0] / 2 - 1;
»if (units > length - 1) {
»»units = length - 1;
»}
»uint8_t order   = 3;
»int32_t written = 0;
»for (int32_t u = 0; u < units; u++) {
»»const auto code = static_cast<uint16_t>(descriptor[2 * u + 2] | (descriptor[2 * u + 3] << 8));
»»uint8_t    character = 0;
»»if ((code & 0xFF00u) == 0 && (order & 1u) != 0) {
»»»character = static_cast<uint8_t>(code);
»»»order     = 1;
»»} else if ((code & 0x00FFu) == 0 && (order & 2u) != 0) {
»»»character = static_cast<uint8_t>(code >> 8u);
»»»order     = 2;
»»} else {
»»»continue;
»»}
»»if (character < 0x20 || character > 0x7E || character == '<' || character == '>') {
»»»continue;
»»}
»»data[written++] = character;
»}
»data[written] = 0;
»return written;
}

// AnyPS5 :789-807: the first device with this id, opened, only when the allow-list names it and the gate admits it.
static uint64_t Bc5UsbOpenVidPid(uint16_t vendor_id, uint16_t product_id) {
»auto&           st = Bc5Usb();
»std::lock_guard lock(st.mutex);
»if (st.context == nullptr || !Bc5UsbListed((static_cast<uint32_t>(vendor_id) << 16u) | product_id)) {
»»return 0;
»}
»const auto&          lib   = Bc5UsbL();
»void**               all   = nullptr;
»const std::ptrdiff_t count = lib.get_device_list(st.context, &all);
»if (count < 0) {
»»return 0;
»}
»void* handle = nullptr;
»for (std::ptrdiff_t i = 0; i < count; i++) {
»»Bc5UsbDeviceDescriptor d {};
»»if (lib.get_device_descriptor(all[i], &d) == 0 && d.idVendor == vendor_id && d.idProduct == product_id) {
»»»if (!Bc5UsbAdmit(lib, all[i]) || lib.open(all[i], &handle) != 0) {
»»»»handle = nullptr;
»»»}
»»»break;
»»}
»}
»lib.free_device_list(all, 1);
»if (handle != nullptr) {
»»st.handles.insert(handle);
»}
»return reinterpret_cast<uint64_t>(handle);
}

// AnyPS5 :809-823.
static std::optional<int> Bc5UsbAltSetting(void* handle, int32_t interface_number, int32_t alternate_setting) {
»std::optional<int> answer;
»if (!Bc5UsbOpenHandle("sceUsbdSetInterfaceAltSetting", handle, &answer)) {
»»return answer;
»}
»if (interface_number < 0 || interface_number > 31) {
»»return BC5_USB_INVALID_ARG;
»}
»{
»»auto&           st      = Bc5Usb();
»»std::lock_guard lock(st.mutex);
»»const auto      claimed = st.claimed.find(handle);
»»if (claimed == st.claimed.end() || (claimed->second & (1u << static_cast<uint32_t>(interface_number))) == 0) {
»»»return Bc5UsbGuestError(BC5_LIBUSB_ERROR_NOT_FOUND);
»»}
»»for (const auto& [guest, host]: st.in_flight) {
»»»if (host->dev_handle == handle) {
»»»»return Bc5UsbNoAnswer("sceUsbdSetInterfaceAltSetting",
»»»»                      "AnyPS5 has no answer while the device has transfers in flight");
»»»}
»»}
»}
»return Bc5UsbL().set_interface_alt_setting(handle, interface_number, static_cast<uint8_t>(alternate_setting)) == 0
»           ? 0
»           : BC5_USB_OTHER;
}

// AnyPS5 :464-466, 678-680.
static int Bc5UsbHandlingOk() {
»return Bc5UsbEv().handler.load() == std::this_thread::get_id() ? 1 : 0;
}

static int Bc5UsbHandlerActive() {
»return Bc5UsbEv().handler.load() != std::thread::id {} ? 1 : 0;
}

// AnyPS5 :781-787, 838-844.
static std::optional<int> Bc5UsbLockEvents() {
»if (!Bc5UsbAcquireAndClaim(Bc5UsbEv())) {
»»return Bc5UsbNoAnswer("sceUsbdLockEvents", BC5_USB_LOCKED_TWICE);
»}
»return OK;
}

static std::optional<int> Bc5UsbLockWaiters() {
»if (!Bc5UsbAcquire(Bc5UsbEv())) {
»»return Bc5UsbNoAnswer("sceUsbdLockEventWaiters", BC5_USB_LOCKED_TWICE);
»}
»return OK;
}

static std::optional<int> Bc5UsbUnlockEvents() {
»auto& ev = Bc5UsbEv();
»if (!Bc5UsbHolds(ev)) {
»»return Bc5UsbNoAnswer("sceUsbdUnlockEvents", BC5_USB_NOT_LOCKED);
»}
»Bc5UsbReleaseAndUnclaim(ev);
»return OK;
}

static std::optional<int> Bc5UsbUnlockWaiters() {
»auto& ev = Bc5UsbEv();
»if (!Bc5UsbHolds(ev)) {
»»return Bc5UsbNoAnswer("sceUsbdUnlockEventWaiters", BC5_USB_NOT_LOCKED);
»}
»Bc5UsbRelease(ev);
»return OK;
}

// AnyPS5 :825-836: 0 when this thread took the lock and became the handler, else 1.
static int Bc5UsbTryLockEvents() {
»auto&      ev   = Bc5UsbEv();
»const auto self = std::this_thread::get_id();
»if (ev.owner.load() == self || !ev.lock.try_lock()) {
»»return 1;
»}
»if (ev.handler.load() != std::thread::id {}) {
»»ev.lock.unlock();
»»return 1;
»}
»ev.owner.store(self);
»ev.handler.store(self);
»return 0;
}

// AnyPS5 :846-851: 0 when woken, 1 when the timeout ran out.
static std::optional<int> Bc5UsbWaitForEvent(const Bc5UsbTimeval* tv) {
»if (!Bc5UsbValidTimeout(tv)) {
»»return Bc5UsbNoAnswer("sceUsbdWaitForEvent", BC5_USB_BAD_TIMEOUT);
»}
»auto& ev = Bc5UsbEv();
»if (!Bc5UsbHolds(ev)) {
»»return Bc5UsbNoAnswer("sceUsbdWaitForEvent", BC5_USB_NOT_LOCKED);
»}
»return Bc5UsbWaitForChange(ev, tv);
}

// AnyPS5 :774-779.
static std::optional<int> Bc5UsbHandleEventsLocked(const Bc5UsbTimeval* tv) {
»if (!Bc5UsbValidTimeout(tv)) {
»»return Bc5UsbNoAnswer("sceUsbdHandleEventsLocked", BC5_USB_BAD_TIMEOUT);
»}
»auto& ev = Bc5UsbEv();
»if (!Bc5UsbHolds(ev)) {
»»return Bc5UsbNoAnswer("sceUsbdHandleEventsLocked", BC5_USB_NOT_LOCKED);
»}
»return Bc5UsbHandleLocked(ev, tv);
}

// AnyPS5 :766-772: with no host context the handler waits until a transfer completes, which never happens.
static std::optional<int> Bc5UsbHandleEvents() {
»auto& ev = Bc5UsbEv();
»if (!Bc5UsbAcquireAndClaim(ev)) {
»»return Bc5UsbNoAnswer("sceUsbdHandleEvents", BC5_USB_LOCKED_TWICE);
»}
»const int answer = Bc5UsbHandleLocked(ev, nullptr);
»Bc5UsbReleaseAndUnclaim(ev);
»return answer;
}

// AnyPS5 :328-336.
static std::optional<int> Bc5UsbHandleEventsTimeout(const Bc5UsbTimeval* tv) {
»if (tv == nullptr || tv->seconds < 0 || tv->microseconds < 0 || tv->microseconds >= BC5_USB_USEC_PER_SECOND) {
»»return BC5_USB_INVALID_ARG;
»}
»if (!Bc5UsbValidTimeout(tv)) {
»»return Bc5UsbNoAnswer("sceUsbdHandleEventsTimeout", "AnyPS5 has no answer for a timeout over INT_MAX seconds");
»}
»auto& ev = Bc5UsbEv();
»if (!Bc5UsbAcquireAndClaim(ev)) {
»»return Bc5UsbNoAnswer("sceUsbdHandleEventsTimeout", BC5_USB_LOCKED_TWICE);
»}
»const int answer = Bc5UsbHandleLocked(ev, tv);
»Bc5UsbReleaseAndUnclaim(ev);
»return answer;
}
// ---- end of the Usbd port (tus) --------------------------------------------------------------------------------------
"""

# The 61 ported stubs: (name, return type, parameter list, kind, call). Kind "ret": the port always answers; kind "opt":
# the port answers or, where AnyPS5 has no answer, returns nothing and today's return runs.
FILL = ("void* transfer, void* handle, uint8_t endpoint, uint8_t* buffer, int32_t length, void* callback, void* user_data, "
        "uint32_t timeout")
SYNC = "void* handle, uint8_t endpoint, uint8_t* data, int32_t length, int32_t* transferred, uint32_t timeout"
IFACE = "void* handle, int32_t interface_number"

STUBS = [
    ("sceUsbdAllocTransfer", "uint64_t", "int32_t iso_packets", "ret", "Bc5UsbAllocTransfer(iso_packets)"),
    ("sceUsbdAttachKernelDriver", "int", "void* handle, int32_t /*interface_number*/", "opt",
     "Bc5UsbAttachKernelDriver(handle)"),
    ("sceUsbdBulkTransfer", "int", SYNC, "opt",
     'Bc5UsbSyncTransfer("sceUsbdBulkTransfer", false, handle, endpoint, data, length, transferred, timeout)'),
    ("sceUsbdCancelTransfer", "int", "void* transfer", "opt", "Bc5UsbCancel(transfer)"),
    ("sceUsbdCheckConnected", "int", "void* handle", "opt", "Bc5UsbCheckConnected(handle)"),
    ("sceUsbdClaimInterface", "int", IFACE, "opt", "Bc5UsbClaim(handle, interface_number, true)"),
    ("sceUsbdClearHalt", "int", "void* handle, uint8_t endpoint", "opt", "Bc5UsbClearHalt(handle, endpoint)"),
    ("sceUsbdClose", "int", "void* handle", "opt", "Bc5UsbClose(handle)"),
    ("sceUsbdControlTransfer", "int",
     "void* handle, uint8_t request_type, uint8_t request, uint16_t value, uint16_t index, uint8_t* data, uint16_t length, "
     "uint32_t timeout", "opt",
     "Bc5UsbControlTransfer(handle, request_type, request, value, index, data, length, timeout)"),
    ("sceUsbdControlTransferGetData", "uint64_t", "void* transfer", "opt", "Bc5UsbControlData(transfer)"),
    ("sceUsbdControlTransferGetSetup", "uint64_t", "void* transfer", "opt", "Bc5UsbControlSetup(transfer)"),
    ("sceUsbdDetachKernelDriver", "int", IFACE, "opt",
     'Bc5UsbHandleCall("sceUsbdDetachKernelDriver", 3, handle, interface_number)'),
    ("sceUsbdEventHandlerActive", "int", "", "ret", "Bc5UsbHandlerActive()"),
    ("sceUsbdEventHandlingOk", "int", "", "ret", "Bc5UsbHandlingOk()"),
    ("sceUsbdExit", "int", "", "opt", "Bc5UsbExit()"),
    ("sceUsbdFillBulkTransfer", "int", FILL, "opt",
     'Bc5UsbFill("sceUsbdFillBulkTransfer", transfer, handle, endpoint, BC5_USB_TYPE_BULK, buffer, length, callback, '
     'user_data, timeout)'),
    ("sceUsbdFillControlSetup", "int",
     "uint8_t* buffer, uint8_t request_type, uint8_t request, uint16_t value, uint16_t index, uint16_t length", "opt",
     "Bc5UsbFillControlSetup(buffer, request_type, request, value, index, length)"),
    ("sceUsbdFillControlTransfer", "int",
     "void* transfer, void* handle, uint8_t* buffer, void* callback, void* user_data, uint32_t timeout", "opt",
     "Bc5UsbFillControl(transfer, handle, buffer, callback, user_data, timeout)"),
    ("sceUsbdFillInterruptTransfer", "int", FILL, "opt",
     'Bc5UsbFill("sceUsbdFillInterruptTransfer", transfer, handle, endpoint, BC5_USB_TYPE_INTERRUPT, buffer, length, '
     'callback, user_data, timeout)'),
    ("sceUsbdFillIsoTransfer", "int",
     "void* transfer, void* handle, uint8_t endpoint, uint8_t* buffer, int32_t length, int32_t iso_count, void* callback, "
     "void* user_data, uint32_t timeout", "opt",
     "Bc5UsbFillIso(transfer, handle, endpoint, buffer, length, iso_count, callback, user_data, timeout)"),
    ("sceUsbdFreeConfigDescriptor", "int", "void* config", "opt", "Bc5UsbFreeConfig(config)"),
    ("sceUsbdFreeDeviceList", "int", "void** list, int32_t unref_devices", "opt",
     "Bc5UsbFreeDeviceList(list, unref_devices)"),
    ("sceUsbdFreeTransfer", "int", "void* transfer", "opt", "Bc5UsbFreeTransfer(transfer)"),
    ("sceUsbdGetActiveConfigDescriptor", "int", "void* device, void** config", "opt",
     'Bc5UsbConfig("sceUsbdGetActiveConfigDescriptor", 0, device, 0, config)'),
    ("sceUsbdGetBusNumber", "int", "void* device", "opt", 'Bc5UsbDeviceValue("sceUsbdGetBusNumber", 0, device)'),
    ("sceUsbdGetConfigDescriptor", "int", "void* device, uint8_t config_index, void** config", "opt",
     'Bc5UsbConfig("sceUsbdGetConfigDescriptor", 1, device, config_index, config)'),
    ("sceUsbdGetConfigDescriptorByValue", "int", "void* device, uint8_t config_value, void** config", "opt",
     'Bc5UsbConfig("sceUsbdGetConfigDescriptorByValue", 2, device, config_value, config)'),
    ("sceUsbdGetConfiguration", "int", "void* handle, int32_t* config", "opt", "Bc5UsbGetConfiguration(handle, config)"),
    ("sceUsbdGetDescriptor", "int",
     "void* handle, uint8_t descriptor_type, uint8_t descriptor_index, uint8_t* data, int32_t length", "opt",
     'Bc5UsbDescriptor("sceUsbdGetDescriptor", descriptor_type, descriptor_index, 0, handle, data, length)'),
    ("sceUsbdGetDevice", "uint64_t", "void* handle", "opt", "Bc5UsbGetDevice(handle)"),
    ("sceUsbdGetDeviceAddress", "int", "void* device", "opt", 'Bc5UsbDeviceValue("sceUsbdGetDeviceAddress", 1, device)'),
    ("sceUsbdGetDeviceDescriptor", "int", "void* device, void* descriptor", "opt",
     "Bc5UsbGetDeviceDescriptor(device, descriptor)"),
    ("sceUsbdGetDeviceList", "int64_t", "void*** list", "ret", "Bc5UsbGetDeviceList(list)"),
    ("sceUsbdGetDeviceSpeed", "int", "void* device", "opt", 'Bc5UsbDeviceValue("sceUsbdGetDeviceSpeed", 2, device)'),
    ("sceUsbdGetIsoPacketBuffer", "uint64_t", "void* transfer, uint32_t packet", "opt", "Bc5UsbIsoBuffer(transfer, packet)"),
    ("sceUsbdGetMaxIsoPacketSize", "int", "void* device, uint8_t endpoint", "opt",
     "Bc5UsbPacketSize(true, device, endpoint)"),
    ("sceUsbdGetMaxPacketSize", "int", "void* device, uint8_t endpoint", "opt", "Bc5UsbPacketSize(false, device, endpoint)"),
    ("sceUsbdGetStringDescriptor", "int",
     "void* handle, uint8_t descriptor_index, uint16_t language_id, uint8_t* data, int32_t length", "opt",
     'Bc5UsbDescriptor("sceUsbdGetStringDescriptor", BC5_LIBUSB_DT_STRING, descriptor_index, language_id, handle, data, '
     'length)'),
    ("sceUsbdGetStringDescriptorAscii", "int", "void* handle, uint8_t descriptor_index, uint8_t* data, int32_t length",
     "opt", "Bc5UsbStringAscii(handle, descriptor_index, data, length)"),
    ("sceUsbdHandleEvents", "int", "", "opt", "Bc5UsbHandleEvents()"),
    ("sceUsbdHandleEventsLocked", "int", "const Bc5UsbTimeval* timeout", "opt", "Bc5UsbHandleEventsLocked(timeout)"),
    ("sceUsbdHandleEventsTimeout", "int", "const Bc5UsbTimeval* timeout", "opt", "Bc5UsbHandleEventsTimeout(timeout)"),
    ("sceUsbdInit", "int", "", "ret", "Bc5UsbInit()"),
    ("sceUsbdInterruptTransfer", "int", SYNC, "opt",
     'Bc5UsbSyncTransfer("sceUsbdInterruptTransfer", true, handle, endpoint, data, length, transferred, timeout)'),
    ("sceUsbdKernelDriverActive", "int", IFACE, "opt",
     'Bc5UsbHandleCall("sceUsbdKernelDriverActive", 0, handle, interface_number)'),
    ("sceUsbdLockEventWaiters", "int", "", "opt", "Bc5UsbLockWaiters()"),
    ("sceUsbdLockEvents", "int", "", "opt", "Bc5UsbLockEvents()"),
    ("sceUsbdOpen", "int", "void* device, void** handle", "opt", "Bc5UsbOpen(device, handle)"),
    ("sceUsbdOpenDeviceWithVidPid", "uint64_t", "uint16_t vendor_id, uint16_t product_id", "ret",
     "Bc5UsbOpenVidPid(vendor_id, product_id)"),
    ("sceUsbdRefDevice", "uint64_t", "void* device", "opt", "Bc5UsbRefDevice(device)"),
    ("sceUsbdReleaseInterface", "int", IFACE, "opt", "Bc5UsbClaim(handle, interface_number, false)"),
    ("sceUsbdResetDevice", "int", "void* handle", "opt", 'Bc5UsbHandleCall("sceUsbdResetDevice", 1, handle, 0)'),
    ("sceUsbdSetConfiguration", "int", "void* handle, int32_t configuration", "opt",
     'Bc5UsbHandleCall("sceUsbdSetConfiguration", 2, handle, configuration)'),
    ("sceUsbdSetInterfaceAltSetting", "int", "void* handle, int32_t interface_number, int32_t alternate_setting", "opt",
     "Bc5UsbAltSetting(handle, interface_number, alternate_setting)"),
    ("sceUsbdSetIsoPacketLengths", "int", "void* transfer, uint32_t length", "opt", "Bc5UsbSetIsoLengths(transfer, length)"),
    ("sceUsbdSubmitTransfer", "int", "void* transfer", "opt", "Bc5UsbSubmit(transfer)"),
    ("sceUsbdTryLockEvents", "int", "", "ret", "Bc5UsbTryLockEvents()"),
    ("sceUsbdUnlockEventWaiters", "int", "", "opt", "Bc5UsbUnlockWaiters()"),
    ("sceUsbdUnlockEvents", "int", "", "opt", "Bc5UsbUnlockEvents()"),
    ("sceUsbdUnrefDevice", "int", "void* device", "opt", "Bc5UsbUnrefDevice(device)"),
    ("sceUsbdWaitForEvent", "int", "const Bc5UsbTimeval* timeout", "opt", "Bc5UsbWaitForEvent(timeout)"),
]

# Held (not edited; not registered when on): (NID, name). AnyPS5 does not have them.
HELD = (("ZfbvM+OP-1A", "Func_65F6EF33E38FFF50"), ("l-BWutkKrec", "Func_97F056BAD90AADE7"),
        ("xVEEozs1smQ", "Func_C55104A33B35B264"), ("1WtDBgcgseA", "Func_D56B43060720B1E0"))
EXPECT_PORTED = 61
EXPECT_TABLE = 65
SWITCH = "KYTY_BC5_LOAD_USBD"
ON = "Bc5UsbOn"
DEFINE = "InitUsbd_1"
TODAY = "static int KYTY_SYSV_ABI {name}() {{\n\n\n»PRINT_NAME();\n\n\n»return OK; // STUBBED\n\n\n}}\n"


def balance(b):
    return (b.count(b"{") - b.count(b"}"), b.count(b"(") - b.count(b")"), b.count(b"[") - b.count(b"]"))


def md5(b):
    return hashlib.md5(b).hexdigest()


def edits():
    out = [("includes", INCLUDES_OLD, INCLUDES_NEW), ("block", ANCHOR, ANCHOR + BLOCK)]
    for name, ret, params, kind, call in STUBS:
        old = f"static int KYTY_SYSV_ABI {name}() {{\n\n\n»PRINT_NAME();\n"
        head = (f"static {ret} KYTY_SYSV_ABI {name}({params}) {{\n\n\n»PRINT_NAME();\n"
                f"»if ({ON}()) {{ // BC5 experiment 0405 (tus): the port, {SWITCH}\n")
        if kind == "ret":
            body = f"»»return {call};\n"
        else:
            assert kind == "opt", kind
            body = f"»»if (const auto answer = {call}) {{\n»»»return *answer;\n»»}} // else AnyPS5 has no answer: today's\n"
        out.append((name, old, head + body + "»}\n"))
    out.append((DEFINE, f"LIB_DEFINE({DEFINE}) {{\n",
                f"LIB_DEFINE({DEFINE}) {{\n»if ({ON}()) {{ // BC5 experiment 0405 (tus): reads {SWITCH} once (its line); on, "
                f"the allow-list (its line)\n»»(void)Bc5UsbAllowList();\n»}}\n"))
    for nid, name in HELD:
        line = f'»LIB_FUNC("{nid}", LibUsbd::{name});\n'
        out.append((f"held {name}", line,
                    f"»if (!{ON}()) {{ // BC5 experiment 0405 (tus): held, registered only when {SWITCH} is off\n»{line}»}}\n"))
    return out


def edit(s):
    for m in MARKS:
        assert m not in s, ("refused: the unit has the edit already", m.decode())
    assert b"\r" not in s, "a CR in the LF unit"
    assert s.startswith(b"\xef\xbb\xbf"), "the unit's BOM"
    names = [n for n, *_ in STUBS]
    held = [n for _, n in HELD]
    assert len(names) == len(set(names)) == EXPECT_PORTED, ("ported stubs", len(names), len(set(names)))
    assert not set(names) & set(held)
    assert len(names) + len(held) == EXPECT_TABLE
    assert s.count(b"\tLIB_FUNC(") == EXPECT_TABLE, ("table size", s.count(b"\tLIB_FUNC("))
    for n in names + held:  # every name is one of today's stubs, with today's body, registered once
        assert s.count(T(TODAY.format(name=n))) == 1, ("today's stub", n)
        assert s.count(f", LibUsbd::{n});\n".encode()) == 1, ("registration", n)
    assert s.count(b"static int KYTY_SYSV_ABI ") == EXPECT_TABLE
    assert balance(T(BLOCK)) == (0, 0, 0), ("the block is not balanced", balance(T(BLOCK)))
    out = s
    done = []  # (old bytes, new bytes) in order, for the undo check
    for what, old, new in edits():
        o, n = T(old), T(new)
        assert out.count(o) == 1, ("anchor", what, out.count(o))
        assert balance(o) == balance(n), ("the edit changes the balance", what, balance(o), balance(n))
        out = out.replace(o, n)
        done.append((o, n))
    want = 1 + EXPECT_PORTED + 1 + len(HELD)  # the definition, the stubs, the LIB_DEFINE line, the held guards
    assert out.count(T(f"{ON}()")) == want, ("switch uses", out.count(T(f"{ON}()")), want)
    want = BLOCK.count(SWITCH) + EXPECT_PORTED + 1 + len(HELD)  # the block, the stubs', LIB_DEFINE's and guards' comments
    assert out.count(SWITCH.encode()) == want, ("switch name", out.count(SWITCH.encode()), want)
    assert balance(out) == balance(s), ("the unit's balance changed", balance(s), balance(out))
    # The held stubs are as they were.
    for n in held:
        assert out.count(T(TODAY.format(name=n))) == 1, ("not edited", n)
    # Every ported stub keeps today's return after its branch.
    for n in names:
        a = out.index(f" KYTY_SYSV_ABI {n}(".encode())
        z = out.index(b"\n}\n", a)
        assert out[a:z].endswith(b"\n\n\n\treturn OK; // STUBBED\n\n"), ("today's return", n)
    # The registration lines: the same 65, in the same order.
    reg0 = [l.strip() for l in s.split(b"\n") if l.strip().startswith(b"LIB_FUNC(")]
    reg1 = [l.strip() for l in out.split(b"\n") if l.strip().startswith(b"LIB_FUNC(")]
    assert reg0 == reg1 and len(reg1) == EXPECT_TABLE, "the registration lines changed"
    # Undo (last first): the input must come back byte for byte.
    back = out
    for o, n in reversed(done):
        assert back.count(n) == 1, ("undo", n[:60])
        back = back.replace(n, o)
    assert back == s, "undoing the edits does not give the input back"
    for o, n in done:
        n.decode("ascii")
    assert b"\r" not in out
    return out


def main():
    assert len(sys.argv) == 3, __doc__
    root, outdir = sys.argv[1], sys.argv[2]
    assert os.path.abspath(root) != os.path.abspath(outdir), "the out dir must not be the tree"
    assert list(PINS) == [REL]
    with open(os.path.join(root, REL), "rb") as f:
        s = f.read()
    for m in MARKS:
        assert m not in s, ("refused: the unit has the edit already", REL, m.decode())
    assert md5(s) == PINS[REL], ("refused: not the pinned input", REL, md5(s), PINS[REL])
    out = edit(s)
    print(f"# in:  {REL} {md5(s)}  ({len(s)} bytes, LF)", file=sys.stderr)
    dst = os.path.join(outdir, REL)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    with open(dst, "wb") as f:
        f.write(out)
    print(f"{REL} {md5(out)}")


if __name__ == "__main__":
    main()
