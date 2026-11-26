#!/usr/bin/env python3
"""BC5 experiment 0405 (series e6 of experiment 0401), tag "tbc": exp 0405 decision 4 ("=> B => B": the 32 tables that are
compiled but never loaded are ported first, then loaded, each behind its own switch), batch 1's CPU-only tables, in three
library units of the e6 input tree (= e5's sources), each behind a switch that is off by default and read once (off is
today's path exactly). Libs::InitAll loads each table when its switch is on (libs.cpp, tag "tld", not edited here):
  src/libs/libZlib.cpp  KYTY_BC5_LOAD_ZLIB  Libs::LibZlib::InitZlib_1  AnyPS5 libSceZlib/Export.cpp:16-112 (all 5 NIDs)
  src/libs/libJpeg.cpp  KYTY_BC5_LOAD_JPEG  Libs::LibJpeg::InitJpeg_1  AnyPS5 libSceJpegEnc/Export.cpp:18-105, 169-215 (the
                                                                       checks and the memory answer; the encode is held)
  src/libs/libIme.cpp   KYTY_BC5_LOAD_IME   Libs::LibIme::InitIme_1    items panel,test: AnyPS5 libSceIme/Export.cpp
                                                                       499-512 and 760-762; the 7 NIDs the live Ime table
                                                                       registers are removed from this table (its init is
                                                                       dead today, so off is unchanged)
KYTY_BC5_LOAD_IME may name items ("panel"); any other value but "0" turns every item on. The other two switches have
no items. Each unit's input md5 is pinned and asserted; a unit that has the edit already is refused; every anchor must occur
exactly once; every edit keeps braces, parentheses and brackets balanced; the inserted text is ASCII; line ends stay as they
are (all three are LF with a UTF-8 BOM). After editing, the script undoes its own edits on the output and asserts that this
gives the input back byte for byte. Only the three units are written, and only when all three are done. Prints
"<relpath> <md5>" per written file.
Notes: tbc0405-notes.md; CPU test: tbc0405.cpp.
usage: mktbc0405.py <tree root in> <out dir>"""
import hashlib
import os
import sys

MARKS = (b"experiment 0405", b"KYTY_BC5_LOAD_ZLIB", b"KYTY_BC5_LOAD_JPEG", b"KYTY_BC5_LOAD_IME", b"Bc5Zlib", b"Bc5Jpeg",
         b"Bc5Ime")


def T(text, crlf=False):
    """C++ text written with a visible tab ("»") for each tab of the file's indentation, as ASCII bytes."""
    out = text.replace("»", "\t").encode("ascii")
    if crlf:
        assert b"\r" not in out
        out = out.replace(b"\n", b"\r\n")
    return out


# =====================================================================================================================
# src/libs/libZlib.cpp
# =====================================================================================================================
ZLIB_BLOCK_ANCHOR = "static int KYTY_SYSV_ABI sceZlibInitialize() {\n"
ZLIB_BLOCK = r"""// ---- BC5 experiment 0405 (series e6 of experiment 0401), tag "tbc": KYTY_BC5_LOAD_ZLIB, libSceZlib ported ----
// Exp 0405 decision 4 (the tables compiled but never loaded): this table is ported first, then loaded by Libs::InitAll when
// KYTY_BC5_LOAD_ZLIB is on (libs.cpp, tag "tld"). Ported in adapted form from AnyPS5 (github.com/boykopovar/AnyPS5,
// GPL-2.0-only) @ 4f41f4c375f5abb487dbd184fbc150f31994d762, core/libs/prx/libSceZlib/Export.cpp:16-112: the error codes,
// one service with an initialized flag, a request id per inflate, the ids handed out by WaitForDone in submission order
// (with a timeout in microseconds), the results kept until Finalize; and its note docs/dev/debt/libSceZlib.md:5 ("Native
// validation confirms the 64-bit initialization length, 2 KiB output granularity up to 64 KiB, null-argument errors and
// initialization precedence"; the rest follows shadPS4 (PS4) and SharpProspero and is unverified on a PS5). The inflate
// runs at submission, as AnyPS5's does, over the zlib this tree already links (ZLIB::ZLIBSTATIC with KYTY_HAS_ZLIB=1 in
// src/CMakeLists.txt; libPngEnc.cpp and rpfArchiveReader.cpp use it): a zlib-wrapped stream (inflateInit), Z_FINISH into
// the caller's buffer; Z_STREAM_END is 0, an output that ran out with input left is NO_SPACE, anything else FATAL.
// Adapted where AnyPS5 throws (a case it does not know): a non-null work memory is accepted and not used, a destination
// not on a 2 KiB boundary is written as any other, and a wait that Finalize ends returns NOT_INITIALIZED; each
// TODO(verify). KYTY_BC5_LOAD_ZLIB: unset, empty or "0" is off (today's stubs: OK, nothing written); any other value is
// on. Read once; one stderr line at registration or at the first call.
// AnyPS5's copyright remains with its authors; GPL-2.0 as the rest of this file (AnyPS5's part is GPL-2.0-only).
static constexpr int      BC5_ZLIB_ERROR_NOT_FOUND           = static_cast<int>(0x81120002u);
static constexpr int      BC5_ZLIB_ERROR_INVALID_ARGUMENT    = static_cast<int>(0x81120016u);
static constexpr int      BC5_ZLIB_ERROR_NO_SPACE            = static_cast<int>(0x8112001Cu);
static constexpr int      BC5_ZLIB_ERROR_TIMED_OUT           = static_cast<int>(0x81120027u);
static constexpr int      BC5_ZLIB_ERROR_NOT_INITIALIZED     = static_cast<int>(0x81120032u);
static constexpr int      BC5_ZLIB_ERROR_ALREADY_INITIALIZED = static_cast<int>(0x81120033u);
static constexpr int      BC5_ZLIB_ERROR_FATAL               = static_cast<int>(0x811200FFu);
static constexpr uint32_t BC5_ZLIB_OUT_STEP                  = 2048;  // a destination length is a multiple of 2 KiB ...
static constexpr uint32_t BC5_ZLIB_OUT_MAX                   = 65536; // ... up to 64 KiB

// KYTY_BC5_LOAD_ZLIB, read once; the first call prints the switch's line.
static bool Bc5ZlibOn() {
»static const bool on = [] {
»»const char* e = std::getenv("KYTY_BC5_LOAD_ZLIB");
»»const bool  v = e != nullptr && e[0] != '\0' && !(e[0] == '0' && e[1] == '\0');
»»std::fputs(v ? "[bc5] exp 0405: zlib port on (items: Initialize Finalize Inflate WaitForDone GetResult)\n"
»»             : "[bc5] exp 0405: zlib port off\n",
»»           stderr);
»»std::fflush(stderr);
»»return v;
»}();
»return on;
}

struct Bc5ZlibResult {
»uint32_t produced; // bytes written to the destination
»int32_t  status;   // 0, NO_SPACE or FATAL
};

struct Bc5ZlibState {
»std::mutex                                  mutex;
»std::condition_variable                     done;
»bool                                        initialized = false;
»uint64_t                                    next_id     = 1;
»uint64_t                                    session     = 0; // counts the Finalize calls: a wait that one ends sees it
»std::unordered_map<uint64_t, Bc5ZlibResult> results;         // every request since Initialize
»std::deque<uint64_t>                        completed;       // ids WaitForDone has not handed out yet, in order
};

// Never destroyed: a guest thread may still wait on it while the process ends.
static Bc5ZlibState& Bc5Zlib() {
»static auto* state = new Bc5ZlibState;
»return *state;
}

static int Bc5ZlibInitialize(const void* buffer, uint64_t length) {
»auto&           z = Bc5Zlib();
»std::lock_guard lock(z.mutex);
»if (z.initialized) {
»»return BC5_ZLIB_ERROR_ALREADY_INITIALIZED;
»}
»if ((buffer == nullptr) != (length == 0)) {
»»return BC5_ZLIB_ERROR_INVALID_ARGUMENT;
»}
»z.initialized = true; // a work memory (AnyPS5 throws there) is accepted and not used: TODO(verify)
»return OK;
}

static int Bc5ZlibFinalize() {
»auto&           z = Bc5Zlib();
»std::lock_guard lock(z.mutex);
»if (!z.initialized) {
»»return BC5_ZLIB_ERROR_NOT_INITIALIZED;
»}
»z.results.clear();
»z.completed.clear();
»z.initialized = false;
»z.session++;
»z.done.notify_all();
»return OK;
}

static int Bc5ZlibInflate(const void* source, uint32_t source_length, void* destination, uint32_t destination_length,
                          uint64_t* request_id) {
»auto&           z = Bc5Zlib();
»std::lock_guard lock(z.mutex);
»if (!z.initialized) {
»»return BC5_ZLIB_ERROR_NOT_INITIALIZED;
»}
»if (source == nullptr || source_length == 0 || destination == nullptr || request_id == nullptr ||
»    destination_length == 0 || destination_length > BC5_ZLIB_OUT_MAX || (destination_length % BC5_ZLIB_OUT_STEP) != 0) {
»»return BC5_ZLIB_ERROR_INVALID_ARGUMENT;
»}
»// A destination not on a 2 KiB boundary (AnyPS5 throws there) is written as any other: TODO(verify).
»Bc5ZlibResult result {0, BC5_ZLIB_ERROR_FATAL};
»z_stream      stream {};
»stream.next_in   = static_cast<Bytef*>(const_cast<void*>(source));
»stream.avail_in  = source_length;
»stream.next_out  = static_cast<Bytef*>(destination);
»stream.avail_out = destination_length;
»if (inflateInit(&stream) == Z_OK) {
»»const int r     = inflate(&stream, Z_FINISH);
»»const bool full = (r == Z_BUF_ERROR) && stream.avail_out == 0 && stream.avail_in != 0;
»»result.produced = static_cast<uint32_t>(stream.total_out);
»»result.status   = (r == Z_STREAM_END) ? 0 : (full ? BC5_ZLIB_ERROR_NO_SPACE : BC5_ZLIB_ERROR_FATAL);
»»inflateEnd(&stream);
»}
»const uint64_t id = z.next_id++;
»z.results[id]     = result;
»z.completed.push_back(id);
»z.done.notify_one();
»*request_id = id;
»return OK;
}

static int Bc5ZlibWaitForDone(uint64_t* request_id, const uint32_t* timeout) {
»auto&            z = Bc5Zlib();
»std::unique_lock lock(z.mutex);
»if (!z.initialized) {
»»return BC5_ZLIB_ERROR_NOT_INITIALIZED;
»}
»if (request_id == nullptr) {
»»return BC5_ZLIB_ERROR_INVALID_ARGUMENT;
»}
»const uint64_t session  = z.session;
»const auto     finished = [&z, session] { return !z.completed.empty() || z.session != session; };
»if (timeout == nullptr) {
»»z.done.wait(lock, finished);
»} else if (!z.done.wait_for(lock, std::chrono::microseconds(*timeout), finished)) {
»»return BC5_ZLIB_ERROR_TIMED_OUT;
»}
»if (z.session != session) {
»»return BC5_ZLIB_ERROR_NOT_INITIALIZED; // Finalize ended the wait (AnyPS5 throws there): TODO(verify)
»}
»*request_id = z.completed.front();
»z.completed.pop_front();
»return OK;
}

static int Bc5ZlibGetResult(uint64_t request_id, uint32_t* destination_length, int32_t* status) {
»auto&           z = Bc5Zlib();
»std::lock_guard lock(z.mutex);
»if (!z.initialized) {
»»return BC5_ZLIB_ERROR_NOT_INITIALIZED;
»}
»if (destination_length == nullptr || status == nullptr) {
»»return BC5_ZLIB_ERROR_INVALID_ARGUMENT;
»}
»const auto found = z.results.find(request_id);
»if (found == z.results.end()) {
»»return BC5_ZLIB_ERROR_NOT_FOUND;
»}
»*destination_length = found->second.produced;
»*status             = found->second.status;
»return OK;
}
// ---- end of BC5 experiment 0405 (KYTY_BC5_LOAD_ZLIB) ----

"""

ZLIB_GATE = "»if (Bc5ZlibOn()) { // BC5 experiment 0405 (KYTY_BC5_LOAD_ZLIB); false when off\n"
ZLIB_EDITS = (
    ("includes", "#include <common/abi.h>\n",
     "#include <common/abi.h>\n"
     "\n"
     "#include <chrono> // BC5 experiment 0405 (KYTY_BC5_LOAD_ZLIB): these includes to <zlib.h>\n"
     "#include <condition_variable>\n"
     "#include <cstdint>\n"
     "#include <cstdio>\n"
     "#include <cstdlib>\n"
     "#include <deque>\n"
     "#include <mutex>\n"
     "#include <unordered_map>\n"
     "\n"
     "#include <zlib.h>\n"),
    ("Initialize", "static int KYTY_SYSV_ABI sceZlibInitialize() {\n»PRINT_NAME();\n",
     "static int KYTY_SYSV_ABI sceZlibInitialize(const void* buffer, uint64_t length) {\n»PRINT_NAME();\n" + ZLIB_GATE +
     "»»return Bc5ZlibInitialize(buffer, length);\n»}\n"),
    ("Finalize", "static int KYTY_SYSV_ABI sceZlibFinalize() {\n»PRINT_NAME();\n",
     "static int KYTY_SYSV_ABI sceZlibFinalize() {\n»PRINT_NAME();\n" + ZLIB_GATE + "»»return Bc5ZlibFinalize();\n»}\n"),
    ("Inflate", "static int KYTY_SYSV_ABI sceZlibInflate() {\n»PRINT_NAME();\n",
     "static int KYTY_SYSV_ABI sceZlibInflate(const void* source, uint32_t source_length, void* destination,\n"
     "                                        uint32_t destination_length, uint64_t* request_id) {\n»PRINT_NAME();\n" +
     ZLIB_GATE + "»»return Bc5ZlibInflate(source, source_length, destination, destination_length, request_id);\n»}\n"),
    ("WaitForDone", "static int KYTY_SYSV_ABI sceZlibWaitForDone() {\n»PRINT_NAME();\n",
     "static int KYTY_SYSV_ABI sceZlibWaitForDone(uint64_t* request_id, const uint32_t* timeout) {\n»PRINT_NAME();\n" +
     ZLIB_GATE + "»»return Bc5ZlibWaitForDone(request_id, timeout);\n»}\n"),
    ("GetResult", "static int KYTY_SYSV_ABI sceZlibGetResult() {\n»PRINT_NAME();\n",
     "static int KYTY_SYSV_ABI sceZlibGetResult(uint64_t request_id, uint32_t* destination_length, int32_t* status) {\n"
     "»PRINT_NAME();\n" + ZLIB_GATE + "»»return Bc5ZlibGetResult(request_id, destination_length, status);\n»}\n"),
    ("registration", "LIB_DEFINE(InitZlib_1) {\n",
     "LIB_DEFINE(InitZlib_1) {\n"
     "»(void)Bc5ZlibOn(); // BC5 experiment 0405: reads KYTY_BC5_LOAD_ZLIB once and prints its line at registration\n"),
)
ZLIB_BEFORE = ("#include <common/abi.h>\n", "LIB_VERSION(\"libSceZlib\", 1, \"libSceZlib\", 1, 1);\n")
ZLIB_AFTER = ("static int KYTY_SYSV_ABI sceZlibGetResult() {\n", "LIB_DEFINE(InitZlib_1) {\n")
ZLIB_USES = (("Bc5ZlibOn()", 7), ("Bc5Zlib()", 6), ("Bc5ZlibInitialize(", 2), ("Bc5ZlibFinalize(", 2), ("Bc5ZlibInflate(", 2),
             ("Bc5ZlibWaitForDone(", 2), ("Bc5ZlibGetResult(", 2), ("TODO(verify)", 4))

# =====================================================================================================================
# src/libs/libJpeg.cpp
# =====================================================================================================================
JPEG_BLOCK_ANCHOR = "static int KYTY_SYSV_ABI sceJpegEncCreate() {\n"
JPEG_BLOCK = r"""// ---- BC5 experiment 0405 (series e6 of experiment 0401), tag "tbc": KYTY_BC5_LOAD_JPEG, libSceJpegEnc ported ----
// Exp 0405 decision 4 (the tables compiled but never loaded): this table is ported first, then loaded by Libs::InitAll when
// KYTY_BC5_LOAD_JPEG is on (libs.cpp, tag "tld"). Ported in adapted form from AnyPS5 (github.com/boykopovar/AnyPS5,
// GPL-2.0-only) @ 4f41f4c375f5abb487dbd184fbc150f31994d762, core/libs/prx/libSceJpegEnc/Export.cpp:18-105 and 169-215: the
// error codes; the create-parameter checks; the encode-parameter checks in their order; the 0x800-byte memory answer,
// which is also Create's minimum; a handle placed at the first 32-byte boundary of the caller's memory that points at
// itself, which Delete clears and Delete and Encode check. The parameter layouts follow core/libs/SceTypes.hpp:2030-2049.
// Its note docs/dev/debt/libSceJpegEnc.md:5: restart intervals 0, -1 (one MCU row) and 1..65535 "are confirmed by the
// native validator", other values are an invalid parameter. shadPS4 (GPL-2.0-or-later) @ 60c42b9,
// src/core/libraries/jpeg/jpegenc.cpp:16-198 and jpeg_error.h, has the same codes, sizes and checks on the PS4, without
// AnyPS5's zero-width and zero-height checks and its restart-interval floor of -1.
// Held: the encode itself (no JPEG encoder is compiled in this tree). When the checks pass, Encode keeps today's answer:
// OK, with nothing written to the JPEG buffer or the output info (AnyPS5 returns the JPEG's size and fills both).
// KYTY_BC5_LOAD_JPEG: unset, empty or "0" is off (today's stubs: OK, nothing written); any other value is on. Read once;
// one stderr line at registration or at the first call.
// AnyPS5's copyright remains with its authors; GPL-2.0 as the rest of this file (AnyPS5's part is GPL-2.0-only).
static constexpr int       BC5_JPEG_ENC_ERROR_INVALID_ADDR   = static_cast<int>(0x80650101u);
static constexpr int       BC5_JPEG_ENC_ERROR_INVALID_SIZE   = static_cast<int>(0x80650102u);
static constexpr int       BC5_JPEG_ENC_ERROR_INVALID_PARAM  = static_cast<int>(0x80650103u);
static constexpr int       BC5_JPEG_ENC_ERROR_INVALID_HANDLE = static_cast<int>(0x80650104u);
static constexpr uint32_t  BC5_JPEG_ENC_MEMORY_SIZE          = 0x800; // QueryMemorySize's answer and Create's minimum
static constexpr uintptr_t BC5_JPEG_ENC_HANDLE_ALIGN         = 0x20;
static constexpr uint32_t  BC5_JPEG_ENC_MAX_DIMENSION        = 0xFFFF;
static constexpr uint32_t  BC5_JPEG_ENC_MAX_PITCH            = 0xFFFFFFF;
static constexpr uint64_t  BC5_JPEG_ENC_MAX_IMAGE_SIZE       = 0x7FFFFFFF;
static constexpr uint16_t  BC5_JPEG_ENC_PIXEL_R8G8B8A8       = 0;
static constexpr uint16_t  BC5_JPEG_ENC_PIXEL_B8G8R8A8       = 1;
static constexpr uint16_t  BC5_JPEG_ENC_PIXEL_Y8U8Y8V8       = 10;
static constexpr uint16_t  BC5_JPEG_ENC_PIXEL_Y8             = 11;
static constexpr uint16_t  BC5_JPEG_ENC_MODE_NORMAL          = 0;
static constexpr uint16_t  BC5_JPEG_ENC_MODE_MJPEG           = 1;
static constexpr uint16_t  BC5_JPEG_ENC_COLOR_YCC            = 1;
static constexpr uint16_t  BC5_JPEG_ENC_COLOR_GRAY           = 2;
static constexpr uint8_t   BC5_JPEG_ENC_SAMPLING_FULL        = 0;
static constexpr uint8_t   BC5_JPEG_ENC_SAMPLING_422         = 1;
static constexpr uint8_t   BC5_JPEG_ENC_SAMPLING_420         = 2;
static constexpr int32_t   BC5_JPEG_ENC_RESTART_PER_ROW      = -1;

struct Bc5JpegEncCreateParam {
»uint32_t size; // sizeof(Bc5JpegEncCreateParam)
»uint32_t attr; // 0
};

struct Bc5JpegEncEncodeParam {
»const void* image;
»void*       jpeg;
»uint32_t    image_size;
»uint32_t    jpeg_size;
»uint32_t    image_width;
»uint32_t    image_height;
»uint32_t    image_pitch;
»uint16_t    pixel_format;
»uint16_t    encode_mode;
»uint16_t    color_space;
»uint8_t     sampling_type;
»uint8_t     compression_ratio;
»int32_t     restart_interval;
};

static_assert(sizeof(Bc5JpegEncCreateParam) == 0x8);
static_assert(sizeof(Bc5JpegEncEncodeParam) == 0x30);

// What Create leaves in the caller's memory: a pointer to itself while the handle is valid.
struct Bc5JpegEncHandle {
»Bc5JpegEncHandle* self;
};

// KYTY_BC5_LOAD_JPEG, read once; the first call prints the switch's line.
static bool Bc5JpegOn() {
»static const bool on = [] {
»»const char* e = std::getenv("KYTY_BC5_LOAD_JPEG");
»»const bool  v = e != nullptr && e[0] != '\0' && !(e[0] == '0' && e[1] == '\0');
»»std::fputs(v ? "[bc5] exp 0405: jpeg port on (items: Create Delete QueryMemorySize Encode-checks; Encode itself held)\n"
»»             : "[bc5] exp 0405: jpeg port off\n",
»»           stderr);
»»std::fflush(stderr);
»»return v;
»}();
»return on;
}

static int Bc5JpegCheckCreateParam(const void* param_in) {
»const auto* param = static_cast<const Bc5JpegEncCreateParam*>(param_in);
»if (param == nullptr) {
»»return BC5_JPEG_ENC_ERROR_INVALID_ADDR;
»}
»if (param->size != sizeof(Bc5JpegEncCreateParam)) {
»»return BC5_JPEG_ENC_ERROR_INVALID_SIZE;
»}
»if (param->attr != 0) {
»»return BC5_JPEG_ENC_ERROR_INVALID_PARAM;
»}
»return OK;
}

// The handle a Create made and no Delete has cleared; nullptr for any other value.
static Bc5JpegEncHandle* Bc5JpegValidHandle(void* handle) {
»const auto address = reinterpret_cast<uintptr_t>(handle);
»if (address == 0 || (address % BC5_JPEG_ENC_HANDLE_ALIGN) != 0) {
»»return nullptr;
»}
»auto* h = static_cast<Bc5JpegEncHandle*>(handle);
»return h->self == h ? h : nullptr;
}

static int Bc5JpegCheckEncodeParam(const void* param_in) {
»const auto* p = static_cast<const Bc5JpegEncEncodeParam*>(param_in);
»if (p == nullptr) {
»»return BC5_JPEG_ENC_ERROR_INVALID_ADDR;
»}
»const bool gray_input = p->pixel_format == BC5_JPEG_ENC_PIXEL_Y8;
»if (p->image == nullptr || (!gray_input && (reinterpret_cast<uintptr_t>(p->image) % 4) != 0) || p->jpeg == nullptr) {
»»return BC5_JPEG_ENC_ERROR_INVALID_ADDR;
»}
»if (p->image_size == 0 || p->jpeg_size == 0) {
»»return BC5_JPEG_ENC_ERROR_INVALID_SIZE;
»}
»if (p->image_width == 0 || p->image_height == 0 || p->image_width > BC5_JPEG_ENC_MAX_DIMENSION ||
»    p->image_height > BC5_JPEG_ENC_MAX_DIMENSION) {
»»return BC5_JPEG_ENC_ERROR_INVALID_PARAM;
»}
»if (p->image_pitch == 0 || p->image_pitch > BC5_JPEG_ENC_MAX_PITCH || (!gray_input && (p->image_pitch % 4) != 0)) {
»»return BC5_JPEG_ENC_ERROR_INVALID_PARAM;
»}
»const uint64_t needed = static_cast<uint64_t>(p->image_height) * p->image_pitch;
»if (needed > BC5_JPEG_ENC_MAX_IMAGE_SIZE || needed > p->image_size) {
»»return BC5_JPEG_ENC_ERROR_INVALID_PARAM;
»}
»if (p->encode_mode != BC5_JPEG_ENC_MODE_NORMAL && p->encode_mode != BC5_JPEG_ENC_MODE_MJPEG) {
»»return BC5_JPEG_ENC_ERROR_INVALID_PARAM;
»}
»if (p->color_space != BC5_JPEG_ENC_COLOR_YCC && p->color_space != BC5_JPEG_ENC_COLOR_GRAY) {
»»return BC5_JPEG_ENC_ERROR_INVALID_PARAM;
»}
»if (p->sampling_type != BC5_JPEG_ENC_SAMPLING_FULL && p->sampling_type != BC5_JPEG_ENC_SAMPLING_422 &&
»    p->sampling_type != BC5_JPEG_ENC_SAMPLING_420) {
»»return BC5_JPEG_ENC_ERROR_INVALID_PARAM;
»}
»if (p->restart_interval < BC5_JPEG_ENC_RESTART_PER_ROW ||
»    p->restart_interval > static_cast<int32_t>(BC5_JPEG_ENC_MAX_DIMENSION)) {
»»return BC5_JPEG_ENC_ERROR_INVALID_PARAM;
»}
»bool fits = false;
»switch (p->pixel_format) {
»»case BC5_JPEG_ENC_PIXEL_R8G8B8A8:
»»case BC5_JPEG_ENC_PIXEL_B8G8R8A8:
»»»fits = p->image_pitch / 4 >= p->image_width && p->color_space == BC5_JPEG_ENC_COLOR_YCC &&
»»»       p->sampling_type != BC5_JPEG_ENC_SAMPLING_FULL;
»»»break;
»»case BC5_JPEG_ENC_PIXEL_Y8U8Y8V8:
»»»fits = p->image_pitch / 2 >= ((p->image_width + 1) & ~1u) && p->color_space == BC5_JPEG_ENC_COLOR_YCC &&
»»»       p->sampling_type != BC5_JPEG_ENC_SAMPLING_FULL;
»»»break;
»»case BC5_JPEG_ENC_PIXEL_Y8:
»»»fits = p->image_pitch >= p->image_width && p->color_space == BC5_JPEG_ENC_COLOR_GRAY &&
»»»       p->sampling_type == BC5_JPEG_ENC_SAMPLING_FULL;
»»»break;
»»default: fits = false; break;
»}
»return fits ? OK : BC5_JPEG_ENC_ERROR_INVALID_PARAM;
}

static int Bc5JpegQueryMemorySize(const void* param) {
»const int checked = Bc5JpegCheckCreateParam(param);
»return checked != OK ? checked : static_cast<int>(BC5_JPEG_ENC_MEMORY_SIZE);
}

static int Bc5JpegCreate(const void* param, void* memory, uint32_t memory_size, void** handle) {
»const int checked = Bc5JpegCheckCreateParam(param);
»if (checked != OK) {
»»return checked;
»}
»if (memory == nullptr) {
»»return BC5_JPEG_ENC_ERROR_INVALID_ADDR;
»}
»if (memory_size < BC5_JPEG_ENC_MEMORY_SIZE) {
»»return BC5_JPEG_ENC_ERROR_INVALID_SIZE;
»}
»if (handle == nullptr) {
»»return BC5_JPEG_ENC_ERROR_INVALID_ADDR;
»}
»const uintptr_t at =
»    (reinterpret_cast<uintptr_t>(memory) + BC5_JPEG_ENC_HANDLE_ALIGN - 1) & ~(BC5_JPEG_ENC_HANDLE_ALIGN - 1);
»auto* h = reinterpret_cast<Bc5JpegEncHandle*>(at); // within the 0x800 bytes the caller gave
»h->self = h;
»*handle = h;
»return OK;
}

static int Bc5JpegDelete(void* handle) {
»Bc5JpegEncHandle* h = Bc5JpegValidHandle(handle);
»if (h == nullptr) {
»»return BC5_JPEG_ENC_ERROR_INVALID_HANDLE;
»}
»h->self = nullptr;
»return OK;
}

// Encode's checks: the handle, then the parameters. OK when they pass; the encode itself is held.
static int Bc5JpegEncodeChecks(void* handle, const void* param) {
»if (Bc5JpegValidHandle(handle) == nullptr) {
»»return BC5_JPEG_ENC_ERROR_INVALID_HANDLE;
»}
»return Bc5JpegCheckEncodeParam(param);
}
// ---- end of BC5 experiment 0405 (KYTY_BC5_LOAD_JPEG) ----

"""

JPEG_GATE = "»if (Bc5JpegOn()) { // BC5 experiment 0405 (KYTY_BC5_LOAD_JPEG); false when off\n"
JPEG_EDITS = (
    ("includes", "#include <common/abi.h>\n",
     "#include <common/abi.h>\n"
     "\n"
     "#include <cstdint> // BC5 experiment 0405 (KYTY_BC5_LOAD_JPEG): these includes\n"
     "#include <cstdio>\n"
     "#include <cstdlib>\n"),
    ("Create", "static int KYTY_SYSV_ABI sceJpegEncCreate() {\n»PRINT_NAME();\n",
     "static int KYTY_SYSV_ABI sceJpegEncCreate(const void* param, void* memory, uint32_t memory_size, void** handle) {\n"
     "»PRINT_NAME();\n" + JPEG_GATE + "»»return Bc5JpegCreate(param, memory, memory_size, handle);\n»}\n"),
    ("Delete", "static int KYTY_SYSV_ABI sceJpegEncDelete() {\n»PRINT_NAME();\n",
     "static int KYTY_SYSV_ABI sceJpegEncDelete(void* handle) {\n»PRINT_NAME();\n" + JPEG_GATE +
     "»»return Bc5JpegDelete(handle);\n»}\n"),
    ("Encode", "static int KYTY_SYSV_ABI sceJpegEncEncode() {\n»PRINT_NAME();\n",
     "static int KYTY_SYSV_ABI sceJpegEncEncode(void* handle, const void* param, void* /*output_info*/) {\n»PRINT_NAME();\n"
     "»if (Bc5JpegOn()) { // BC5 experiment 0405 (KYTY_BC5_LOAD_JPEG); false when off. The encode itself is held:\n"
     "»»const int checked = Bc5JpegEncodeChecks(handle, param); // when the checks pass, today's answer below\n"
     "»»if (checked != OK) {\n"
     "»»»return checked;\n"
     "»»}\n"
     "»}\n"),
    ("QueryMemorySize", "static int KYTY_SYSV_ABI sceJpegEncQueryMemorySize() {\n»PRINT_NAME();\n",
     "static int KYTY_SYSV_ABI sceJpegEncQueryMemorySize(const void* param) {\n»PRINT_NAME();\n" + JPEG_GATE +
     "»»return Bc5JpegQueryMemorySize(param);\n»}\n"),
    ("registration", "LIB_DEFINE(InitJpeg_1) {\n",
     "LIB_DEFINE(InitJpeg_1) {\n"
     "»(void)Bc5JpegOn(); // BC5 experiment 0405: reads KYTY_BC5_LOAD_JPEG once and prints its line at registration\n"),
)
JPEG_BEFORE = ("#include <common/abi.h>\n", "LIB_VERSION(\"libSceJpegEnc\", 1, \"libSceJpegEnc\", 1, 1);\n")
JPEG_AFTER = ("static int KYTY_SYSV_ABI sceJpegEncQueryMemorySize() {\n", "LIB_DEFINE(InitJpeg_1) {\n")
JPEG_USES = (("Bc5JpegOn()", 6), ("Bc5JpegCreate(", 2), ("Bc5JpegDelete(", 2), ("Bc5JpegEncodeChecks(", 2),
             ("Bc5JpegQueryMemorySize(", 2), ("Bc5JpegValidHandle(", 3), ("Bc5JpegCheckCreateParam(", 3),
             ("Bc5JpegCheckEncodeParam(", 2))

# =====================================================================================================================
# src/libs/libIme.cpp
# =====================================================================================================================
IME_LIVE = (  # the NIDs libs/ime.cpp's InitPlatform_1_Ime registers too (same key: "libSce" is dropped), in table order
    ("TmVP8LzcFcY", "sceImeClose"),
    ("ziPDcIjO0Vk", "sceImeGetPanelSize"),
    ("RPydv-Jr1bc", "sceImeOpen"),
    ("WmYDzdC4EHI", "sceImeParamInit"),
    ("WLxUN2WMim8", "sceImeSetCaret"),
    ("ieCNrVrzKd4", "sceImeSetText"),
    ("TXYHFRuL8UY", "sceImeSetTextGeometry"),
)

IME_BLOCK_ANCHOR = "static int KYTY_SYSV_ABI FinalizeImeModule() {\n"
IME_BLOCK = r"""// ---- BC5 experiment 0405 (series e6 of experiment 0401), tag "tbc": KYTY_BC5_LOAD_IME, libSceIme ported ----
// Exp 0405 decision 4 (the tables compiled but never loaded): this table is ported first, then loaded by Libs::InitAll when
// KYTY_BC5_LOAD_IME is on (libs.cpp, tag "tld"), before the live Ime table (libs/ime.cpp InitPlatform_1_Ime).
// SymbolDatabase::GenerateName drops "libSce", so this table's libSceIme v1 / v1.1 keys are the live table's Ime keys.
// The 7 NIDs the live table also registers (SetText, SetCaret, ParamInit, GetPanelSize, Open, Close, SetTextGeometry) are
// not registered here, and their stubs are removed. Find (exact key) returns a key's last registration, but the NID-only
// fallback FindByNid (RuntimeLinker::Resolve, ResolveLoadedSymbolByNid, libKernel.cpp's symbol lookup) returns the first,
// which would be this table's stub. Today nothing calls this init, so with the switch off nothing changes.
// IME state: "panel" reads the live table's state (the panel ime.cpp's ImeOpen opened); the held stubs read and change no
// state. KYTY_BC5_LOAD_IME: unset, empty or "0" is off (today's answers); a value naming items (comma-separated) turns on
// only those; any other value turns every item on. Read once; one stderr line at registration or at the first call. Items:
//   panel: sceImeGetPanelPositionAndForm (T6FYjZXG93o), ported in adapted form from AnyPS5 (github.com/boykopovar/AnyPS5,
//          GPL-2.0-only) @ 4f41f4c375f5abb487dbd184fbc150f31994d762, core/libs/prx/libSceIme/Export.cpp:499-512 (commit
//          e21d8bd12) and its note docs/dev/debt/libSceIme.md:21. With no panel open it is NOT_OPENED (0x80bc0002),
//          checked before a null form (INVALID_ADDRESS 0x80bc0031). While a panel is open, the form is cleared and gets
//          the type, position and alignments that sceImeOpen was given, and the size that sceImeGetPanelSize gives. The
//          open panel is read through libs/ime.h's GetHostSnapshot (the live table's state). The form is libs/imeDialog.h's
//          PositionAndForm (0x1c bytes), which sceImeDialogGetPanelPositionAndForm fills.
//   test:  sceImeForTestFunction (wVkehxutK-U) returns 0x80bc00ff (the IME's internal error). Source: AnyPS5
//          Export.cpp:760-762 (commit db2575839, "return what the firmware returns from 29 more calls it does not
//          implement") and its note libSceIme.md:25 (a constant error in the supplied module). Exp 0405 decision 1.
// Held (today's stubs: OK, nothing written):
//   - sceImeFilterText: AnyPS5's note libSceIme.md:22 names a disassembly of a firmware module, with addresses, as its
//     source.
//   - 36 calls that AnyPS5 does not implement either (they throw there).
//   - sceImeOpenInternal and sceImeVshDisableController: not in AnyPS5.
// AnyPS5's copyright remains with its authors; GPL-2.0 as the rest of this file (AnyPS5's part is GPL-2.0-only).
static constexpr int      BC5_IME_ERROR_NOT_OPENED      = static_cast<int>(0x80bc0002u);
static constexpr int      BC5_IME_ERROR_INVALID_ADDRESS = static_cast<int>(0x80bc0031u);
static constexpr int      BC5_IME_ERROR_INTERNAL        = static_cast<int>(0x80bc00ffu);
static constexpr uint32_t BC5_IME_PANEL                 = 1u;
static constexpr uint32_t BC5_IME_TEST                  = 2u;
static constexpr uint32_t BC5_IME_ALL                   = 3u;

static uint32_t Bc5ImeItemsParse(const char* e) {
»if (e == nullptr || e[0] == '\0' || std::strcmp(e, "0") == 0) {
»»return 0;
»}
»static const char* const names[] = {"panel", "test"}; // bit i is names[i]
»uint32_t                 parts   = 0;
»const char*              p       = e;
»for (;;) {
»»const char*  comma = std::strchr(p, ',');
»»const size_t n     = comma != nullptr ? static_cast<size_t>(comma - p) : std::strlen(p);
»»for (uint32_t i = 0; i < 2; i++) {
»»»if (n == std::strlen(names[i]) && std::strncmp(p, names[i], n) == 0) {
»»»»parts |= 1u << i;
»»»}
»»}
»»if (comma == nullptr) {
»»»break;
»»}
»»p = comma + 1;
»}
»return parts != 0 ? parts : BC5_IME_ALL;
}

// The items of KYTY_BC5_LOAD_IME that are on (0: off), read once; the first call prints the switch's line.
static uint32_t Bc5ImeItems() {
»static const uint32_t items = [] {
»»const uint32_t p = Bc5ImeItemsParse(std::getenv("KYTY_BC5_LOAD_IME"));
»»if (p == 0) {
»»»std::fputs("[bc5] exp 0405: ime port off\n", stderr);
»»} else {
»»»std::fprintf(stderr, "[bc5] exp 0405: ime port on (items:%s%s; the 7 NIDs of the live Ime table not registered)\n",
»»»             (p & BC5_IME_PANEL) != 0 ? " panel" : "", (p & BC5_IME_TEST) != 0 ? " test" : "");
»»}
»»std::fflush(stderr);
»»return p;
»}();
»return items;
}

static bool Bc5ImeItem(uint32_t item) {
»return (Bc5ImeItems() & item) != 0;
}

// "panel": the open panel's type, position, alignments and size, as AnyPS5's sceImeGetPanelPositionAndForm gives them.
static int Bc5ImeGetPanelPositionAndForm(void* form_out) {
»Libs::Ime::HostSnapshot open {};
»if (!Libs::Ime::GetHostSnapshot(&open)) {
»»return BC5_IME_ERROR_NOT_OPENED;
»}
»if (form_out == nullptr) {
»»return BC5_IME_ERROR_INVALID_ADDRESS;
»}
»using Form = Libs::Dialog::ImeDialog::PositionAndForm;
»using Align = Libs::Dialog::ImeDialog::Alignment;
»auto* form                 = static_cast<Form*>(form_out);
»*form                      = Form {};
»form->type                 = static_cast<uint32_t>(open.type);
»form->posx                 = open.posx;
»form->posy                 = open.posy;
»form->horizontal_alignment = static_cast<Align>(static_cast<uint32_t>(open.horizontal_alignment));
»form->vertical_alignment   = static_cast<Align>(static_cast<uint32_t>(open.vertical_alignment));
»form->width                = open.panel_width;
»form->height               = open.panel_height;
»return OK;
}
// ---- end of BC5 experiment 0405 (KYTY_BC5_LOAD_IME) ----

"""

IME_EDITS = (
    ("includes", "#include <common/abi.h>\n",
     "#include <common/abi.h>\n"
     "\n"
     "#include \"libs/ime.h\"       // BC5 experiment 0405 (KYTY_BC5_LOAD_IME): these includes\n"
     "#include \"libs/imeDialog.h\"\n"
     "\n"
     "#include <cstdint>\n"
     "#include <cstdio>\n"
     "#include <cstdlib>\n"
     "#include <cstring>\n"),
    ("GetPanelPositionAndForm", "static int KYTY_SYSV_ABI sceImeGetPanelPositionAndForm() {\n»PRINT_NAME();\n",
     "static int KYTY_SYSV_ABI sceImeGetPanelPositionAndForm(void* form) {\n»PRINT_NAME();\n"
     "»if (Bc5ImeItem(BC5_IME_PANEL)) { // BC5 experiment 0405 (KYTY_BC5_LOAD_IME \"panel\"); false when off\n"
     "»»return Bc5ImeGetPanelPositionAndForm(form);\n»}\n"),
    ("ForTestFunction", "static int KYTY_SYSV_ABI sceImeForTestFunction() {\n»PRINT_NAME();\n",
     "static int KYTY_SYSV_ABI sceImeForTestFunction() {\n»PRINT_NAME();\n"
     "»if (Bc5ImeItem(BC5_IME_TEST)) { // BC5 experiment 0405 (KYTY_BC5_LOAD_IME \"test\"); false when off\n"
     "»»return BC5_IME_ERROR_INTERNAL;\n»}\n"),
    ("registration", "LIB_DEFINE(InitIme_1) {\n",
     "LIB_DEFINE(InitIme_1) {\n"
     "»(void)Bc5ImeItems(); // BC5 experiment 0405: reads KYTY_BC5_LOAD_IME once and prints its line at registration\n"),
) + tuple(  # the 7 stubs the live Ime table replaces: removed, with their registrations (this init is dead today)
    (fn, f"static int KYTY_SYSV_ABI {fn}() {{\n»PRINT_NAME();\n»return OK; // STUBBED\n}}\n",
     f"// BC5 experiment 0405: {fn} ({nid}) is the live Ime table's (libs/ime.cpp), not registered here.\n")
    for nid, fn in IME_LIVE) + tuple(
    (nid, f"»LIB_FUNC(\"{nid}\", LibIme::{fn});\n", f"»// {nid} {fn}: the live Ime table's (BC5 experiment 0405)\n")
    for nid, fn in IME_LIVE)
IME_BEFORE = ("#include <common/abi.h>\n", "LIB_VERSION(\"libSceIme\", 1, \"libSceIme\", 1, 1);\n")
IME_AFTER = ("static int KYTY_SYSV_ABI sceImeGetPanelPositionAndForm() {\n", "static int KYTY_SYSV_ABI sceImeForTestFunction() {\n",
             "LIB_DEFINE(InitIme_1) {\n")
IME_USES = (("Bc5ImeItems()", 3), ("Bc5ImeItem(", 3), ("Bc5ImeGetPanelPositionAndForm(", 2), ("LIB_FUNC(", 41),
            ("static int KYTY_SYSV_ABI sce", 39), ("static int KYTY_SYSV_ABI ", 41), ("GetHostSnapshot(", 1),
            ("the live Ime table's", 14))

UNITS = (
    # rel, pinned input md5, crlf, block anchor, block, edits, defined-before, used-after, helper uses
    ("src/libs/libZlib.cpp", "f5d3aafebca0d202082365ee609f15b6", False, ZLIB_BLOCK_ANCHOR, ZLIB_BLOCK, ZLIB_EDITS,
     ZLIB_BEFORE, ZLIB_AFTER, ZLIB_USES),
    ("src/libs/libJpeg.cpp", "a85a83b8d541f5e10c14d739ff56457f", False, JPEG_BLOCK_ANCHOR, JPEG_BLOCK, JPEG_EDITS,
     JPEG_BEFORE, JPEG_AFTER, JPEG_USES),
    ("src/libs/libIme.cpp", "a572240f789088264b6e13850978b739", False, IME_BLOCK_ANCHOR, IME_BLOCK, IME_EDITS, IME_BEFORE,
     IME_AFTER, IME_USES),
)


def balance(b):
    return (b.count(b"{") - b.count(b"}"), b.count(b"(") - b.count(b")"), b.count(b"[") - b.count(b"]"))


def md5(b):
    return hashlib.md5(b).hexdigest()


def edit_unit(rel, s, crlf, anchor, block, edits, before, after, uses):
    for m in MARKS:
        assert m not in s, ("the unit has the edit already", rel, m)
    assert (b"\r\n" in s) == crlf, ("line ends are not the expected ones", rel)
    if not crlf:
        assert b"\r" not in s, ("a CR in an LF unit", rel)
    A = T(anchor, crlf)
    B = T(block, crlf)
    assert balance(B) == (0, 0, 0), ("the block is not balanced", rel, balance(B))
    assert s.count(A) == 1, ("the block's anchor", rel, s.count(A))
    at = s.index(A)
    for b in before:
        bb = T(b, crlf)
        assert s.count(bb) == 1 and s.index(bb) < at, ("must be defined before the block, once", rel, b[:70], s.count(bb))
    for b in after:
        bb = T(b, crlf)
        assert s.count(bb) == 1 and s.index(bb) > at, ("must come after the block, once", rel, b[:70], s.count(bb))
    out = s.replace(A, B + A)
    done = []
    for what, old, new in edits:
        o, n = T(old, crlf), T(new, crlf)
        assert out.count(o) == 1, ("anchor", rel, what, out.count(o))
        assert balance(o) == balance(n), ("the edit changes the balance", rel, what, balance(o), balance(n))
        out = out.replace(o, n)
        done.append((o, n))
    assert balance(out) == balance(s), ("the unit's balance changed", rel, balance(s), balance(out))
    for name, n in uses:
        c = out.count(name.encode("ascii"))
        assert c == n, ("helper uses", rel, name, c, n)
    # Undo the edits on the output (last first) and the block: the input must come back byte for byte.
    back = out
    for o, n in reversed(done):
        assert back.count(n) == 1, ("undo", rel, n[:60])
        back = back.replace(n, o)
    assert back.count(B) == 1
    back = back.replace(B, b"")
    assert back == s, ("undoing the edits does not give the input back", rel)
    # The inserted text is ASCII.
    B.decode("ascii")
    for o, n in done:
        n.decode("ascii")
    if crlf:
        assert out.count(b"\n") == out.count(b"\r\n"), ("a bare LF in the CRLF unit", rel)
    else:
        assert b"\r" not in out, ("a CR in the LF unit", rel)
    assert out.startswith(b"\xef\xbb\xbf") == s.startswith(b"\xef\xbb\xbf"), ("the BOM changed", rel)
    return out


def main():
    assert len(sys.argv) == 3, __doc__
    root, outdir = sys.argv[1], sys.argv[2]
    assert os.path.abspath(root) != os.path.abspath(outdir), "the out dir must not be the tree"
    outs = []
    for rel, expect, crlf, anchor, block, edits, before, after, uses in UNITS:
        with open(os.path.join(root, rel), "rb") as f:
            s = f.read()
        for m in MARKS:
            assert m not in s, ("refused: the unit has the edit already", rel, m.decode())
        assert md5(s) == expect, ("refused: not the pinned input", rel, md5(s), expect)
        out = edit_unit(rel, s, crlf, anchor, block, edits, before, after, uses)
        print(f"# in:  {rel} {md5(s)}  ({len(s)} bytes, {'CRLF' if crlf else 'LF'})", file=sys.stderr)
        outs.append((rel, out))
    for rel, out in outs:  # written only when all three are done
        dst = os.path.join(outdir, rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        with open(dst, "wb") as f:
            f.write(out)
        print(f"{rel} {md5(out)}")


if __name__ == "__main__":
    main()
