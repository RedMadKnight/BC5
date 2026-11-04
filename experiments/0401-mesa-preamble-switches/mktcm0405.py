#!/usr/bin/env python3
"""BC5 experiment 0405 (series e7 of experiment 0401), tag "tcm": exp 0405 decision 4 ("=> B => B", the dead KytyPlus tables
are ported first, then loaded, each behind its own switch), batch 2, hardware group, the Camera table of src/libs/libCamera.cpp:
  namespace LibCamera (InitCamera_1, 76 NIDs)  KYTY_BC5_LOAD_CAMERA  50 ported, 4 already match, 22 held
The same switch name makes libs.cpp (loader agent tl3) load the table. Off (unset, empty or "0") every stub takes today's
path (PRINT_NAME, then today's "return OK") and InitCamera_1 registers all 76 NIDs as today; on, a ported stub calls the port
and the 22 held NIDs are not registered (the top session's rule for every dead table, 2026-11-04 evening: exp 0327's
"stubbed import called" line still shows for them). The port answers as a console with no camera attached; it never opens
a host device. Sources: AnyPS5 4f41f4c37 (GPL-2.0-only), whose debt note names shadPS4 as the source of every ported row,
and shadPS4 60c42b9 (GPL-2.0-or-later), cited in the block. Only libCamera.cpp is edited: a few standard includes after
"#include <common/abi.h>", one block after the LIB_VERSION line, the 50 ported stubs' parameter lists and one branch each,
one line at the top of InitCamera_1 and the 22 held LIB_FUNC lines (each wrapped in "if (!on)").
The input md5 is pinned (PINS) and asserted; an input that has this edit already is refused; every anchor must occur
exactly once; each edit keeps braces, parentheses and brackets balanced; the inserted text is ASCII; line ends stay as they
are (LF). After editing, the script undoes its own edits on the output and asserts that this gives the input back byte for
byte.
Prints "<relpath> <md5>". Notes: tcm0405-notes.md; CPU test: tcm0405.cpp.
usage: mktcm0405.py <tree root in> <out dir>"""
import hashlib
import os
import re
import sys

REL = "src/libs/libCamera.cpp"
# The input md5 of every unit this script edits, in ONE dict (the top session re-pins it when it chains scripts).
PINS = {
    REL: "810fada1b7e1d223502ace667b71eb14",  # the e7 input tree's file = the base tree's (KytyPlus f266548 + patch 0001)
}
MARKS = (b"KYTY_BC5_LOAD_CAMERA", b"Bc5Tcm", b"(tcm)", b"bc5_tcm_on")
SWITCH = "KYTY_BC5_LOAD_CAMERA"
ITEM = "camera"
ITEMS = "isattached open-close start-stop frame config attributes device-queries audio"


def T(text):
    """C++ text written with a visible tab ("»") for each tab of the file's indentation, as ASCII bytes."""
    return text.replace("»", "\t").encode("ascii")


ON_FN = f"""static bool Bc5TcmOn() {{
»static const bool on = [] {{
»»const char* e = std::getenv("{SWITCH}");
»»const bool  v = e != nullptr && e[0] != '\\0' && std::strcmp(e, "0") != 0;
»»std::fprintf(stderr, "%s\\n",
»»             v ? "[bc5] exp 0405: {ITEM} port on (items: {ITEMS})"
»»               : "[bc5] exp 0405: {ITEM} port off");
»»std::fflush(stderr);
»»return v;
»}}();
»return on;
}}
"""

INCLUDE_OLD = "#include <common/abi.h>\n"
INCLUDE_NEW = """#include <common/abi.h>

// BC5 experiment 0405 (series e7 of experiment 0401, tag tcm): what the Camera table's port uses.
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <limits>
#include <mutex>
#include <set>
#include <type_traits>
"""

ANCHOR = 'LIB_VERSION("libSceCamera", 1, "libSceCamera", 1, 1);\n'
BLOCK = r"""
// ---- BC5 experiment 0405 (series e7 of experiment 0401), tag tcm: KYTY_BC5_LOAD_CAMERA, the Camera table's port ----
// Exp 0405 decision 4 ("=> B => B", 2026-11-04): this table is compiled but Libs::InitAll never loaded it; it is ported
// first, then loaded behind KYTY_BC5_LOAD_CAMERA (libs.cpp). Unset, empty or "0" is off: every stub below takes today's
// path (PRINT_NAME, return OK) and InitCamera_1 registers all 76 NIDs. On, the exports answer as a console with NO camera
// attached; nothing here opens, maps or reads a host device:
//  - AnyPS5 (github.com/boykopovar/AnyPS5, GPL-2.0-only) @ 4f41f4c375f5abb487dbd184fbc150f31994d762,
//    core/libs/prx/libSceCamera/: Export.cpp:11-14 (sceCameraIsAttached: index 0 is "not attached", any other index is
//    refused), 214-216 and 238-240 (the audio data calls refuse a null buffer, else 0, nothing written); src/Handles.cpp:
//    11-92 (open hands out a handle for the system user, type 0, index 0, handles are not reused; close, start, stop,
//    the frame data calls with their 584-byte limit: start reports "not connected", the frame data "not open");
//    src/Config.cpp:7-57 (the default configuration and the cleared device configurations; a new one is refused with
//    "not connected"); src/Device.cpp:7-52 (device, product and registry queries report a missing device, the mmap
//    count is 0, the calibration data "not connected", audio open "fatal"); src/Attributes.cpp:8-182 (the getters report
//    the defaults, the setters check their arguments and report "not connected"). Its debt note
//    docs/dev/debt/libSceCamera.md:18-25 names shadPS4's camera library (without a camera configured) as the source of
//    every one of these and says none is measured on a console (TODO(verify)).
//  - Values: the errors are shadPS4's (github.com/shadps4-emu/shadPS4, GPL-2.0-or-later) @ 60c42b9,
//    src/core/libraries/camera/camera_error.h:8-31 (PS4 values; AnyPS5 include/Camera.hpp:5-10 uses the same on the PS5);
//    the system user 0xFF is shadPS4 src/core/libraries/system/userservice.h:22; the defaults are shadPS4
//    camera_config.cpp:28-37, 122, 156-157, 191, 265, 281, 304-305; the layouts below follow shadPS4 camera.h:42-46,
//    63-74, 89-158 (AnyPS5 include/Api.hpp:5-97 is the same), only as far as the answers read or write them.
//  - Our own choice (host safety): where AnyPS5 throws once the handle space is exhausted, open answers 0x802E0014
//    (shadPS4 camera_error.h:26, MAX_HANDLE; TODO(verify)). Clearing a configuration also clears its padding.
//  - Already today's answer, not changed: sceCameraAudioClose, sceCameraAudioReset, sceCameraDeviceOpen and
//    sceCameraSetAttributeInternal answer 0 and do nothing (AnyPS5 Export.cpp:175-177, 351-353, 282-284, 86-88).
//  - Held (AnyPS5 has throwing placeholders for them, debt :29-91: "signature and behavior are unverified"): 22 exports,
//    not registered when the switch is on (see InitCamera_1); today's stubs are kept for the off path.
// AnyPS5's and shadPS4's copyrights remain with their authors; GPL-2.0 as the rest of this file.
""" + ON_FN + r"""
constexpr int BC5_TCM_ERROR_PARAM          = static_cast<int>(0x802E0000u);
constexpr int BC5_TCM_ERROR_NOT_INIT       = static_cast<int>(0x802E0002u);
constexpr int BC5_TCM_ERROR_NOT_OPEN       = static_cast<int>(0x802E0004u);
constexpr int BC5_TCM_ERROR_FORMAT_UNKNOWN = static_cast<int>(0x802E0007u);
constexpr int BC5_TCM_ERROR_NOT_CONNECTED  = static_cast<int>(0x802E0010u);
constexpr int BC5_TCM_ERROR_MAX_HANDLE     = static_cast<int>(0x802E0014u);
constexpr int BC5_TCM_ERROR_FATAL          = static_cast<int>(0x802E00FFu);

constexpr int32_t  BC5_TCM_SYSTEM_USER          = 0xFF;
constexpr uint32_t BC5_TCM_FRAME_DATA_MAX       = 584;
constexpr uint32_t BC5_TCM_FIRST_CHANNEL        = 1; // channel 0 = 1, channel 1 = 2, both = 3
constexpr uint32_t BC5_TCM_BOTH_CHANNELS        = 3;
constexpr uint32_t BC5_TCM_DEFAULT_CONTRAST     = 32;
constexpr uint32_t BC5_TCM_DEFAULT_SATURATION   = 64;
constexpr uint32_t BC5_TCM_DEFAULT_SHARPNESS    = 1;
constexpr int32_t  BC5_TCM_DEFAULT_HUE          = 1;
constexpr uint32_t BC5_TCM_DEFAULT_GAMMA        = 4;
constexpr uint32_t BC5_TCM_MAX_SHARPNESS        = 10;
constexpr uint32_t BC5_TCM_CONFIG_TYPE_DEFAULT  = 1;
constexpr uint32_t BC5_TCM_FORMAT_YUV422        = 0;
constexpr uint32_t BC5_TCM_FORMAT_SCALED_Y8     = 4;
constexpr uint32_t BC5_TCM_FRAMERATE_DEFAULT    = 60;
constexpr uint32_t BC5_TCM_LAST_CALIBRATION_FUN = 1;

// What the answers read or write in the caller's buffers.
struct Bc5TcmExposure {
»uint32_t control;
»uint32_t exposure;
»uint32_t gain;
»uint32_t mode;
};
struct Bc5TcmBalance {
»uint32_t control;
»uint32_t red;
»uint32_t blue;
»uint32_t green;
};
struct Bc5TcmGammaValue {
»uint32_t control;
»uint32_t value;
»uint8_t  unused[16];
};
struct Bc5TcmAttributes { // the whole set of image settings of one channel
»uint32_t         size;
»uint32_t         channel;
»uint32_t         window[4];
»Bc5TcmExposure   exposure;
»Bc5TcmBalance    balance;
»Bc5TcmGammaValue gamma;
»uint32_t         saturation;
»uint32_t         contrast;
»uint32_t         sharpness;
»int32_t          hue;
»uint32_t         unused[4];
};
struct Bc5TcmTarget { // the optional automatic exposure target
»uint32_t size;
»uint32_t level;
};
struct Bc5TcmOutput { // one sensor's output in a configuration
»uint32_t format[4];
»uint32_t resolution;
»uint32_t framerate;
»uint32_t width;
»uint32_t height;
»uint32_t unused;
»void*    extra;
};
struct Bc5TcmConfiguration {
»uint32_t     size;
»uint32_t     type;
»Bc5TcmOutput output[2];
};
struct Bc5TcmDeviceQuery {
»uint32_t size;
»uint32_t revision;
»uint32_t unused[2];
};
struct Bc5TcmCalibrationQuery {
»uint32_t size;
»uint32_t format;
»uint32_t function;
};
struct Bc5TcmStartRequest {
»uint32_t size;
»uint32_t format[2];
»void*    extra;
};
struct Bc5TcmFrameView { // only the size and the two status words are used
»uint32_t size;
»uint32_t mode;
»uint8_t  frames[224];
»uint32_t status[2];
»uint8_t  rest[344];
};
static_assert(sizeof(Bc5TcmAttributes) == 112 && offsetof(Bc5TcmAttributes, saturation) == 80);
static_assert(sizeof(Bc5TcmTarget) == 8 && sizeof(Bc5TcmDeviceQuery) == 16 && sizeof(Bc5TcmCalibrationQuery) == 12);
static_assert(sizeof(Bc5TcmOutput) == 48 && sizeof(Bc5TcmConfiguration) == 104);
static_assert(sizeof(Bc5TcmStartRequest) == 24);
static_assert(sizeof(Bc5TcmFrameView) == BC5_TCM_FRAME_DATA_MAX && offsetof(Bc5TcmFrameView, status) == 232);

// The open handles (AnyPS5 Handles.cpp:14-16, 26-34): handles start at 1 and are never handed out twice.
struct Bc5TcmHandles {
»std::mutex        mutex;
»std::set<int32_t> open;
»int64_t           next = 1;
};
static Bc5TcmHandles& Bc5TcmState() {
»static Bc5TcmHandles state;
»return state;
}
static bool Bc5TcmIsOpen(int32_t handle) {
»auto&                 st = Bc5TcmState();
»std::lock_guard<std::mutex> lock(st.mutex);
»return st.open.count(handle) != 0;
}
static bool Bc5TcmAnyOpen() {
»auto&                 st = Bc5TcmState();
»std::lock_guard<std::mutex> lock(st.mutex);
»return !st.open.empty();
}

// ---- attached, open, close, start, stop, frames (AnyPS5 Export.cpp:11-14, Handles.cpp:18-22, 38-92) ----
static int Bc5TcmIsAttached(int32_t index) {
»return index != 0 ? BC5_TCM_ERROR_PARAM : 0; // 0: no camera attached
}

static int Bc5TcmOpen(int32_t user_id, int32_t type, int32_t index) {
»if (user_id != BC5_TCM_SYSTEM_USER || type != 0 || index != 0) {
»»return BC5_TCM_ERROR_PARAM;
»}
»auto&                 st = Bc5TcmState();
»std::lock_guard<std::mutex> lock(st.mutex);
»if (st.next > std::numeric_limits<int32_t>::max()) {
»»return BC5_TCM_ERROR_MAX_HANDLE;
»}
»const auto handle = static_cast<int32_t>(st.next++);
»st.open.insert(handle);
»return handle;
}

static int Bc5TcmClose(int32_t handle) {
»if (handle < 1) {
»»return BC5_TCM_ERROR_PARAM;
»}
»auto&                 st = Bc5TcmState();
»std::lock_guard<std::mutex> lock(st.mutex);
»return st.open.erase(handle) == 0 ? BC5_TCM_ERROR_NOT_OPEN : 0;
}

static int Bc5TcmCheckStart(int32_t handle, const void* request) {
»const auto* r = static_cast<const Bc5TcmStartRequest*>(request);
»if (handle < 1 || r == nullptr || r->size != sizeof(Bc5TcmStartRequest)) {
»»return BC5_TCM_ERROR_PARAM;
»}
»return Bc5TcmIsOpen(handle) ? 0 : BC5_TCM_ERROR_NOT_OPEN;
}

static int Bc5TcmStart(int32_t handle, const void* request) {
»if (const int error = Bc5TcmCheckStart(handle, request); error != 0) {
»»return error;
»}
»const auto* r = static_cast<const Bc5TcmStartRequest*>(request);
»if (r->format[0] > 0xF || r->format[1] > 0xF || (r->format[0] | r->format[1]) == 0) {
»»return BC5_TCM_ERROR_FORMAT_UNKNOWN;
»}
»return BC5_TCM_ERROR_NOT_CONNECTED;
}

static int Bc5TcmStop(int32_t handle) {
»if (handle < 1) {
»»return BC5_TCM_ERROR_PARAM;
»}
»return Bc5TcmIsOpen(handle) ? 0 : BC5_TCM_ERROR_NOT_OPEN;
}

static int Bc5TcmGetFrameData(int32_t handle, void* frame) {
»auto* f = static_cast<Bc5TcmFrameView*>(frame);
»if (f == nullptr) {
»»return BC5_TCM_ERROR_PARAM;
»}
»f->status[0] = 0xFFFFFFFFu; // no frame on either sensor
»f->status[1] = 0xFFFFFFFFu;
»if (handle < 1 || f->size > BC5_TCM_FRAME_DATA_MAX) {
»»return BC5_TCM_ERROR_PARAM;
»}
»return BC5_TCM_ERROR_NOT_OPEN; // no camera was started, so no frame can be read
}

static int Bc5TcmIsValidFrameData(int32_t handle, const void* frame) {
»const auto* f = static_cast<const Bc5TcmFrameView*>(frame);
»if (handle < 1 || f == nullptr || f->size > BC5_TCM_FRAME_DATA_MAX) {
»»return BC5_TCM_ERROR_PARAM;
»}
»if (!Bc5TcmIsOpen(handle)) {
»»return BC5_TCM_ERROR_NOT_OPEN;
»}
»return (f->status[0] == 1 && f->status[1] == 1) ? 1 : 0;
}

// ---- configuration (AnyPS5 Config.cpp:7-57) ----
static int Bc5TcmCheckConfig(int32_t handle, const void* config) {
»const auto* c = static_cast<const Bc5TcmConfiguration*>(config);
»if (handle < 1 || c == nullptr || c->size != sizeof(Bc5TcmConfiguration)) {
»»return BC5_TCM_ERROR_PARAM;
»}
»return Bc5TcmIsOpen(handle) ? 0 : BC5_TCM_ERROR_NOT_OPEN;
}

static int Bc5TcmGetConfig(int32_t handle, void* config) {
»if (const int error = Bc5TcmCheckConfig(handle, config); error != 0) {
»»return error;
»}
»auto* c = static_cast<Bc5TcmConfiguration*>(config);
»c->type = BC5_TCM_CONFIG_TYPE_DEFAULT;
»for (auto& out: c->output) { // YUV422 with three scaled Y8 levels, 1280x800 (resolution 0), 60 fps
»»std::memset(&out, 0, sizeof(out));
»»out.format[0] = BC5_TCM_FORMAT_YUV422;
»»out.format[1] = BC5_TCM_FORMAT_SCALED_Y8;
»»out.format[2] = BC5_TCM_FORMAT_SCALED_Y8;
»»out.format[3] = BC5_TCM_FORMAT_SCALED_Y8;
»»out.framerate = BC5_TCM_FRAMERATE_DEFAULT;
»}
»return 0;
}

static int Bc5TcmSetConfig(int32_t handle, const void* config) {
»if (const int error = Bc5TcmCheckConfig(handle, config); error != 0) {
»»return error;
»}
»return BC5_TCM_ERROR_NOT_CONNECTED;
}

static int Bc5TcmGetDeviceConfig(int32_t handle, void* config) {
»if (const int error = Bc5TcmCheckConfig(handle, config); error != 0) {
»»return error;
»}
»auto* c = static_cast<Bc5TcmConfiguration*>(config);
»std::memset(c, 0, sizeof(Bc5TcmConfiguration));
»c->size = sizeof(Bc5TcmConfiguration);
»return 0;
}

static int Bc5TcmGetDeviceConfigWithoutHandle(void* config) {
»auto* c = static_cast<Bc5TcmConfiguration*>(config);
»if (c == nullptr || c->size != sizeof(Bc5TcmConfiguration)) {
»»return BC5_TCM_ERROR_PARAM;
»}
»if (!Bc5TcmAnyOpen()) {
»»return BC5_TCM_ERROR_NOT_OPEN;
»}
»std::memset(c, 0, sizeof(Bc5TcmConfiguration)); // the size word too, as AnyPS5 does
»return 0;
}

// ---- device queries and audio (AnyPS5 Device.cpp:7-52, Export.cpp:214-216, 238-240) ----
static int Bc5TcmRefuseQuery(const void* out) {
»if (out == nullptr) {
»»return BC5_TCM_ERROR_PARAM;
»}
»return Bc5TcmAnyOpen() ? BC5_TCM_ERROR_NOT_CONNECTED : BC5_TCM_ERROR_NOT_INIT;
}

static int Bc5TcmGetDeviceInfo(int32_t reserved, const void* info) {
»const auto* q = static_cast<const Bc5TcmDeviceQuery*>(info);
»if (reserved != 0 || q == nullptr || q->size != sizeof(Bc5TcmDeviceQuery) || q->revision != 1) {
»»return BC5_TCM_ERROR_PARAM;
»}
»return Bc5TcmRefuseQuery(info);
}

static int Bc5TcmGetMmapConnectedCount(uint32_t* count) {
»if (!Bc5TcmAnyOpen()) {
»»return BC5_TCM_ERROR_NOT_OPEN;
»}
»if (count == nullptr) {
»»return BC5_TCM_ERROR_PARAM;
»}
»*count = 0;
»return 0;
}

static int Bc5TcmGetCalibDataFromDevice() {
»return BC5_TCM_ERROR_NOT_CONNECTED;
}

static int Bc5TcmGetCalibrationData(const void* query, const void* data) {
»const auto* q = static_cast<const Bc5TcmCalibrationQuery*>(query);
»if (q == nullptr || data == nullptr || q->size != sizeof(Bc5TcmCalibrationQuery) || q->format != 0 ||
»    q->function > BC5_TCM_LAST_CALIBRATION_FUN) {
»»return BC5_TCM_ERROR_PARAM;
»}
»return BC5_TCM_ERROR_NOT_CONNECTED;
}

static int Bc5TcmAudioOpen() {
»return BC5_TCM_ERROR_FATAL;
}

static int Bc5TcmAudioGetData(const void* data) {
»return data == nullptr ? BC5_TCM_ERROR_PARAM : 0; // nothing is written
}

// ---- image settings (AnyPS5 Attributes.cpp:8-182) ----
static bool Bc5TcmReadable(uint32_t channel) {
»return channel >= BC5_TCM_FIRST_CHANNEL && channel < BC5_TCM_BOTH_CHANNELS;
}
static bool Bc5TcmWritable(uint32_t channel) {
»return channel >= BC5_TCM_FIRST_CHANNEL && channel <= BC5_TCM_BOTH_CHANNELS;
}

// A getter: a valid open handle, one readable channel, an output and no option; then the value.
template <typename V>
static int Bc5TcmReport(int32_t handle, uint32_t channel, V* out, const void* option, std::type_identity_t<V> value) {
»if (handle < 1 || !Bc5TcmReadable(channel) || out == nullptr || option != nullptr) {
»»return BC5_TCM_ERROR_PARAM;
»}
»if (!Bc5TcmIsOpen(handle)) {
»»return BC5_TCM_ERROR_NOT_OPEN;
»}
»*out = value;
»return 0;
}

// A setter: checked, then refused, since no camera takes the value.
static int Bc5TcmRefuseSet(int32_t handle, uint32_t channel, bool valid) {
»if (handle < 1 || !Bc5TcmWritable(channel) || !valid) {
»»return BC5_TCM_ERROR_PARAM;
»}
»return Bc5TcmIsOpen(handle) ? BC5_TCM_ERROR_NOT_CONNECTED : BC5_TCM_ERROR_NOT_OPEN;
}

static bool Bc5TcmTargetOk(const void* target) {
»const auto* t = static_cast<const Bc5TcmTarget*>(target);
»if (t == nullptr) {
»»return true;
»}
»if (t->size != sizeof(Bc5TcmTarget)) {
»»return false;
»}
»switch (t->level) { // 0 (default) and 0.2 to 2.0 in the steps the library knows
»»case 0x00:
»»case 0x02:
»»case 0x04:
»»case 0x06:
»»case 0x08:
»»case 0x10:
»»case 0x12:
»»case 0x14:
»»case 0x16:
»»case 0x20: return true;
»»default: return false;
»}
}

static int Bc5TcmGetAttribute(int32_t handle, void* attributes) {
»auto* a = static_cast<Bc5TcmAttributes*>(attributes);
»if (handle < 1 || a == nullptr || a->size != sizeof(Bc5TcmAttributes) || !Bc5TcmReadable(a->channel)) {
»»return BC5_TCM_ERROR_PARAM;
»}
»if (!Bc5TcmIsOpen(handle)) {
»»return BC5_TCM_ERROR_NOT_OPEN;
»}
»const uint32_t channel = a->channel;
»std::memset(a, 0, sizeof(Bc5TcmAttributes));
»a->size              = sizeof(Bc5TcmAttributes);
»a->channel           = channel;
»a->exposure.exposure = 83;
»a->exposure.gain     = 100;
»a->balance           = Bc5TcmBalance {0, 768, 768, 512};
»a->gamma.value       = BC5_TCM_DEFAULT_GAMMA;
»a->saturation        = BC5_TCM_DEFAULT_SATURATION;
»a->contrast          = BC5_TCM_DEFAULT_CONTRAST;
»a->sharpness         = BC5_TCM_DEFAULT_SHARPNESS;
»a->hue               = BC5_TCM_DEFAULT_HUE;
»return 0;
}

static int Bc5TcmGetAutoExposureGain(int32_t handle, uint32_t channel, uint32_t* enable, void* target) {
»auto* t = static_cast<Bc5TcmTarget*>(target);
»if (handle < 1 || !Bc5TcmReadable(channel) || enable == nullptr) {
»»return BC5_TCM_ERROR_PARAM;
»}
»if (t != nullptr && t->size != sizeof(Bc5TcmTarget)) {
»»return BC5_TCM_ERROR_PARAM;
»}
»if (!Bc5TcmIsOpen(handle)) {
»»return BC5_TCM_ERROR_NOT_OPEN;
»}
»*enable = 0;
»if (t != nullptr) {
»»*t = Bc5TcmTarget {0, 0}; // cleared, the size word too, as AnyPS5 does
»}
»return 0;
}

static int Bc5TcmGetExposureGain(int32_t handle, uint32_t channel, void* exposure, void* option) {
»return Bc5TcmReport(handle, channel, static_cast<Bc5TcmExposure*>(exposure), option, Bc5TcmExposure {0, 20, 100, 0});
}

static int Bc5TcmGetWhiteBalance(int32_t handle, uint32_t channel, void* balance, void* option) {
»return Bc5TcmReport(handle, channel, static_cast<Bc5TcmBalance*>(balance), option, Bc5TcmBalance {0, 768, 768, 512});
}

static int Bc5TcmGetGamma(int32_t handle, uint32_t channel, void* gamma, void* option) {
»Bc5TcmGammaValue value {};
»value.value = BC5_TCM_DEFAULT_GAMMA;
»return Bc5TcmReport(handle, channel, static_cast<Bc5TcmGammaValue*>(gamma), option, value);
}

static int Bc5TcmSetAttribute(int32_t handle, const void* attributes) {
»const auto* a = static_cast<const Bc5TcmAttributes*>(attributes);
»if (a == nullptr || a->size != sizeof(Bc5TcmAttributes)) {
»»return BC5_TCM_ERROR_PARAM;
»}
»return Bc5TcmRefuseSet(handle, a->channel, true);
}
// ---- end of BC5 experiment 0405 (tcm) Camera block ----
"""

# The 50 ported stubs: (name, parameter list, the port's call).
GET_FLAG = "int32_t handle, uint32_t channel, uint32_t* enable, void* option"
SET_FLAG = "int32_t handle, uint32_t channel, uint32_t enable, const void* option"
STUBS = (
    ("sceCameraAudioGetData", "void* data", "Bc5TcmAudioGetData(data)"),
    ("sceCameraAudioGetData2", "void* data", "Bc5TcmAudioGetData(data)"),
    ("sceCameraAudioOpen", "", "Bc5TcmAudioOpen()"),
    ("sceCameraClose", "int32_t handle", "Bc5TcmClose(handle)"),
    ("sceCameraCloseByHandle", "int32_t handle", "Bc5TcmClose(handle)"),
    ("sceCameraGetAttribute", "int32_t handle, void* attributes", "Bc5TcmGetAttribute(handle, attributes)"),
    ("sceCameraGetAutoExposureGain", "int32_t handle, uint32_t channel, uint32_t* enable, void* target",
     "Bc5TcmGetAutoExposureGain(handle, channel, enable, target)"),
    ("sceCameraGetAutoWhiteBalance", GET_FLAG, "Bc5TcmReport(handle, channel, enable, option, 0u)"),
    ("sceCameraGetCalibDataFromDevice", "", "Bc5TcmGetCalibDataFromDevice()"),
    ("sceCameraGetCalibrationData", "const void* query, void* data", "Bc5TcmGetCalibrationData(query, data)"),
    ("sceCameraGetConfig", "int32_t handle, void* config", "Bc5TcmGetConfig(handle, config)"),
    ("sceCameraGetContrast", "int32_t handle, uint32_t channel, uint32_t* contrast, void* option",
     "Bc5TcmReport(handle, channel, contrast, option, BC5_TCM_DEFAULT_CONTRAST)"),
    ("sceCameraGetDefectivePixelCancellation", GET_FLAG, "Bc5TcmReport(handle, channel, enable, option, 0u)"),
    ("sceCameraGetDeviceConfig", "int32_t handle, void* config", "Bc5TcmGetDeviceConfig(handle, config)"),
    ("sceCameraGetDeviceConfigWithoutHandle", "void* config", "Bc5TcmGetDeviceConfigWithoutHandle(config)"),
    ("sceCameraGetDeviceInfo", "int32_t reserved, const void* info", "Bc5TcmGetDeviceInfo(reserved, info)"),
    ("sceCameraGetExposureGain", "int32_t handle, uint32_t channel, void* exposure, void* option",
     "Bc5TcmGetExposureGain(handle, channel, exposure, option)"),
    ("sceCameraGetFrameData", "int32_t handle, void* frame", "Bc5TcmGetFrameData(handle, frame)"),
    ("sceCameraGetGamma", "int32_t handle, uint32_t channel, void* gamma, void* option",
     "Bc5TcmGetGamma(handle, channel, gamma, option)"),
    ("sceCameraGetHue", "int32_t handle, uint32_t channel, int32_t* hue, void* option",
     "Bc5TcmReport(handle, channel, hue, option, BC5_TCM_DEFAULT_HUE)"),
    ("sceCameraGetLensCorrection", GET_FLAG, "Bc5TcmReport(handle, channel, enable, option, 0u)"),
    ("sceCameraGetMmapConnectedCount", "uint32_t* count", "Bc5TcmGetMmapConnectedCount(count)"),
    ("sceCameraGetProductInfo", "void* info", "Bc5TcmRefuseQuery(info)"),
    ("sceCameraGetRegistryInfo", "void* info", "Bc5TcmRefuseQuery(info)"),
    ("sceCameraGetSaturation", "int32_t handle, uint32_t channel, uint32_t* saturation, void* option",
     "Bc5TcmReport(handle, channel, saturation, option, BC5_TCM_DEFAULT_SATURATION)"),
    ("sceCameraGetSharpness", "int32_t handle, uint32_t channel, uint32_t* sharpness, void* option",
     "Bc5TcmReport(handle, channel, sharpness, option, BC5_TCM_DEFAULT_SHARPNESS)"),
    ("sceCameraGetWhiteBalance", "int32_t handle, uint32_t channel, void* balance, void* option",
     "Bc5TcmGetWhiteBalance(handle, channel, balance, option)"),
    ("sceCameraIsAttached", "int32_t index", "Bc5TcmIsAttached(index)"),
    ("sceCameraIsValidFrameData", "int32_t handle, const void* frame", "Bc5TcmIsValidFrameData(handle, frame)"),
    ("sceCameraOpen", "int32_t user_id, int32_t type, int32_t index, void* param",
     "(static_cast<void>(param), Bc5TcmOpen(user_id, type, index))"),
    ("sceCameraSetAttribute", "int32_t handle, const void* attributes", "Bc5TcmSetAttribute(handle, attributes)"),
    ("sceCameraSetAutoExposureGain", "int32_t handle, uint32_t channel, uint32_t enable, const void* target",
     "(static_cast<void>(enable), Bc5TcmRefuseSet(handle, channel, Bc5TcmTargetOk(target)))"),
    ("sceCameraSetAutoWhiteBalance", SET_FLAG,
     "(static_cast<void>(enable), Bc5TcmRefuseSet(handle, channel, option == nullptr))"),
    ("sceCameraSetConfig", "int32_t handle, const void* config", "Bc5TcmSetConfig(handle, config)"),
    ("sceCameraSetConfigInternal", "int32_t handle, const void* config", "Bc5TcmSetConfig(handle, config)"),
    ("sceCameraSetContrast", "int32_t handle, uint32_t channel, uint32_t contrast, const void* option",
     "(static_cast<void>(contrast), Bc5TcmRefuseSet(handle, channel, option == nullptr))"),
    ("sceCameraSetDefectivePixelCancellation", SET_FLAG,
     "Bc5TcmRefuseSet(handle, channel, enable <= 1 && option == nullptr)"),
    ("sceCameraSetDefectivePixelCancellationInternal", SET_FLAG,
     "Bc5TcmRefuseSet(handle, channel, enable <= 2 && option == nullptr)"),
    ("sceCameraSetExposureGain", "int32_t handle, uint32_t channel, const void* exposure, const void* option",
     "Bc5TcmRefuseSet(handle, channel, exposure != nullptr && option == nullptr)"),
    ("sceCameraSetGamma", "int32_t handle, uint32_t channel, const void* gamma, const void* option",
     "Bc5TcmRefuseSet(handle, channel, gamma != nullptr && option == nullptr)"),
    ("sceCameraSetHue", "int32_t handle, uint32_t channel, int32_t hue, const void* option",
     "(static_cast<void>(hue), Bc5TcmRefuseSet(handle, channel, option == nullptr))"),
    ("sceCameraSetLensCorrection", SET_FLAG, "Bc5TcmRefuseSet(handle, channel, enable <= 1 && option == nullptr)"),
    ("sceCameraSetLensCorrectionInternal", SET_FLAG,
     "Bc5TcmRefuseSet(handle, channel, enable <= 2 && option == nullptr)"),
    ("sceCameraSetSaturation", "int32_t handle, uint32_t channel, uint32_t saturation, const void* option",
     "(static_cast<void>(saturation), Bc5TcmRefuseSet(handle, channel, option == nullptr))"),
    ("sceCameraSetSharpness", "int32_t handle, uint32_t channel, uint32_t sharpness, const void* option",
     "Bc5TcmRefuseSet(handle, channel, sharpness <= BC5_TCM_MAX_SHARPNESS && option == nullptr)"),
    ("sceCameraSetWhiteBalance", "int32_t handle, uint32_t channel, const void* balance, const void* option",
     "Bc5TcmRefuseSet(handle, channel, balance != nullptr && option == nullptr)"),
    ("sceCameraStart", "int32_t handle, const void* request", "Bc5TcmStart(handle, request)"),
    ("sceCameraStartByHandle", "int32_t handle, const void* request", "Bc5TcmCheckStart(handle, request)"),
    ("sceCameraStop", "int32_t handle", "Bc5TcmStop(handle)"),
    ("sceCameraStopByHandle", "int32_t handle", "Bc5TcmStop(handle)"),
)
# Already today's answer (0, nothing written): not edited, registered in both modes.
MATCH = ("sceCameraAudioClose", "sceCameraAudioReset", "sceCameraDeviceOpen", "sceCameraSetAttributeInternal")
# AnyPS5 placeholders (pending in the sweep): held; their stubs stay, their registration is skipped when on.
HELD = (
    ("QhjrPkRPUZQ", "sceCameraAccGetData"), ("Y0pCDajzkVQ", "sceCameraChangeAppModuleState"),
    ("hHA1frlMxYE", "sceCameraGetCalibData"), ("jTJCdyv9GLU", "sceCameraGetDeviceID"),
    ("-H3UwGQvNZI", "sceCameraGetDeviceIDWithoutOpen"), ("olojYZKYiYs", "sceCameraGetRegister"),
    ("IAz2HgZQWzE", "sceCameraGetVrCaptureInfo"), ("0wnf2a60FqI", "sceCameraInitializeRegistryCalibData"),
    ("wQfd7kfRZvo", "sceCameraIsConfigChangeDone"), ("eTywOSWsEiI", "sceCameraOpenByModuleId"),
    ("py8p6kZcHmA", "sceCameraRemoveAppModuleFocus"), ("j5isFVIlZLk", "sceCameraSetAppModuleFocus"),
    ("LEMk5cTHKEA", "sceCameraSetCalibData"), ("vejouEusC7g", "sceCameraSetDebugStop"),
    ("jeTpU0MqKU0", "sceCameraSetForceActivate"), ("lS0tM6n+Q5E", "sceCameraSetProcessFocus"),
    ("NVITuK83Z7o", "sceCameraSetProcessFocusByHandle"), ("8MjO05qk5hA", "sceCameraSetRegister"),
    ("3VJOpzKoIeM", "sceCameraSetTrackerMode"), ("nnR7KAIDPv8", "sceCameraSetUacModeInternal"),
    ("wpeyFwJ+UEI", "sceCameraSetVideoSync"), ("8WtmqmE4edw", "sceCameraSetVideoSyncInternal"),
)
DEFINE_OLD = "LIB_DEFINE(InitCamera_1) {\n"
DEFINE_NEW = ("LIB_DEFINE(InitCamera_1) {\n"
              f"»const bool bc5_tcm_on = Bc5TcmOn(); // BC5 experiment 0405 (tcm): reads {SWITCH} once and prints its line; "
              "on, the 22 held exports are not registered\n")
NIDS = 76


def balance(b):
    return (b.count(b"{") - b.count(b"}"), b.count(b"(") - b.count(b")"), b.count(b"[") - b.count(b"]"))


def md5(b):
    return hashlib.md5(b).hexdigest()


def edits():
    out = [(INCLUDE_OLD, INCLUDE_NEW, "includes"), (ANCHOR, ANCHOR + BLOCK, "block")]
    for name, params, call in STUBS:
        old = f"static int KYTY_SYSV_ABI {name}() {{\n»PRINT_NAME();\n"
        new = (f"static int KYTY_SYSV_ABI {name}({params}) {{\n»PRINT_NAME();\n"
               f"»if (Bc5TcmOn()) {{ // BC5 experiment 0405 (tcm): the port, {SWITCH}\n"
               f"»»return {call};\n»}}\n")
        out.append((old, new, name))
    out.append((DEFINE_OLD, DEFINE_NEW, "InitCamera_1"))
    for nid, name in HELD:
        old = f'»LIB_FUNC("{nid}", LibCamera::{name});\n'
        new = (f'»if (!bc5_tcm_on) {{ LIB_FUNC("{nid}", LibCamera::{name}); }} '
               "// BC5 experiment 0405 (tcm): held, registered only when off\n")
        out.append((old, new, f"held {name}"))
    return out


def edit(s):
    for m in MARKS:
        assert m not in s, ("refused: the unit has the edit already", m.decode())
    assert b"\r" not in s, "a CR in the LF unit"
    # The three lists cover the table's 76 NIDs exactly once.
    regs = re.findall(rb'\tLIB_FUNC\("([^"]+)", LibCamera::(\w+)\);\n', s)
    assert len(regs) == NIDS and s.count(b"LIB_FUNC(") == NIDS, ("LIB_FUNC count", len(regs))
    names = [n.decode() for _, n in regs]
    ported = [n for n, _, _ in STUBS]
    held = [n for _, n in HELD]
    assert len(set(ported)) == 50 and len(set(MATCH)) == 4 and len(set(held)) == 22
    assert sorted(ported + list(MATCH) + held) == sorted(names), "the lists do not cover the table"
    for nid, name in HELD:
        assert (nid.encode(), name.encode()) in regs, ("held NID/name pair", nid, name)
    # The already-matching and held stubs are today's two-line stubs and stay so.
    for name in list(MATCH) + held:
        stub = T(f"static int KYTY_SYSV_ABI {name}() {{\n»PRINT_NAME();\n»return OK; // STUBBED\n}}\n")
        assert s.count(stub) == 1, ("not today's stub", name)

    out = s
    done = []  # (old bytes, new bytes) in order, for the undo check
    for old, new, what in edits():
        o, n = T(old), T(new)
        assert out.count(o) == 1, ("anchor", what, out.count(o))
        assert balance(o) == balance(n), ("the edit changes the balance", what, balance(o), balance(n))
        if what == "includes":
            assert out.index(o) < out.index(b"namespace Libs {\n"), "include anchor not in the include block"
        else:
            assert out.index(o) > out.index(b"namespace LibCamera {\n"), ("anchor outside the namespace", what)
        out = out.replace(o, n)
        done.append((o, n))
    assert balance(T(BLOCK)) == (0, 0, 0), ("the block is not balanced", balance(T(BLOCK)))
    assert balance(out) == balance(s), ("the unit's balance changed", balance(s), balance(out))
    assert out.count(b"LIB_FUNC(") == NIDS, "LIB_FUNC count after"
    assert out.count(b"Bc5TcmOn()") == len(STUBS) + 2, ("switch uses", out.count(b"Bc5TcmOn()"))
    assert out.count(b"if (!bc5_tcm_on) { LIB_FUNC(") == len(HELD), "held registrations"
    assert out.count(SWITCH.encode()) == BLOCK.count(SWITCH) + len(STUBS) + 1, "switch name count"
    for name in list(MATCH) + held:  # still today's stubs
        stub = T(f"static int KYTY_SYSV_ABI {name}() {{\n»PRINT_NAME();\n»return OK; // STUBBED\n}}\n")
        assert out.count(stub) == 1, ("a held or matching stub changed", name)
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
