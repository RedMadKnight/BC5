#!/usr/bin/env python3
"""BC5 experiment 0401 series e5, tag ao (exp 0405 top-32 rows 16-18, plus extras KA06, KA07, KA08): KytyPS5's AudioOut,
AudioIn and Ngs2 fixes in the e5 tree's src/libs/audio.cpp (KytyPlus f266548 + patch 0001, the base tree's unit with exp
0372's pad audio route; md5 f58ec0105874173a9f84954706a17e96). Ported in adapted form from KytyPS5
(github.com/KytyPS5/KytyPS5, GPL-2.0) at dfec14aa8c59f8ea2bc4d87eba9854fc370161c6:
  ka01  src/libs/audio.cpp:995-997    sceAudioOutOutputs: num 0 or > 32 -> AUDIO_OUT_ERROR_INVALID_SIZE
  ka02  src/libs/audio.cpp:870-872    sceAudioOutOpen: freq 0 -> AUDIO_OUT_ERROR_INVALID_SAMPLE_FREQ
  ka03  src/libs/ngs2.cpp:1456-1528   Ngs2RackDestroy unlinks the rack, calls its allocator's free handler, returns its
        (+1377, 1380-1384, 910, 1972-1983)  context buffer; the racks' list under its own mutex
  ka06  src/libs/audio.cpp:747-749, 805-811, 822   sceAudioInInput: silence into dest; dest null returns 0
  ka07  src/libs/audio.cpp:1047-1058  sceAudioInOpen: errors (type, index, len 0, freq 0) instead of an exit
  ka08  src/libs/ngs2.cpp:2795-2813, 897-905 (a0b99a8)   Ngs2VoiceGetState: custom racks' state as configured
Switches (default off, read once, one stderr line each at the Audio subsystem's init): KYTY_BC5_AUDIOOUT_CHECKS (ka01,
ka02), KYTY_BC5_AUDIOIN_CHECKS (ka06, ka07), KYTY_BC5_NGS2_RACK_FIX (ka03, ka08); a value naming items ("ka01") turns on
only those. Off is today's path exactly. No header is changed; libs/ngs2_pcm.h is not used.
Only audio.cpp is written; src/bc5/pad_audio_route.hpp (exp 0372) must be there and is only read. The input's md5 is
asserted; a unit with the edit already is refused; each anchor occurs exactly once; every edit keeps braces, parentheses
and brackets balanced; the inserted text is ASCII; the count of lines with 'exp 0372' is the same after the edit; undoing
every edit gives the input back byte for byte. Prints "<relpath> <md5>" for the written file.
usage: mkao0405.py <tree root in> <out dir>"""
import hashlib
import os
import sys

REL = "src/libs/audio.cpp"
RO = ("src/bc5/pad_audio_route.hpp",)  # read only (experiment 0372)
EXPECT_IN = "f58ec0105874173a9f84954706a17e96"
MARKS = (b"experiment 0405", b"KYTY_BC5_AUDIOOUT_CHECKS", b"KYTY_BC5_AUDIOIN_CHECKS", b"KYTY_BC5_NGS2_RACK_FIX", b"Bc5Ao",
         b"g_bc5_racks_mutex")
EXP0372 = b"exp 0372"


def T(text):
    """C++ text written with a visible tab ("»") for each tab of the file's indentation, as ASCII bytes."""
    return text.replace("»", "\t").encode("ascii")


# ---- block A: the switches, in namespace Libs::Audio after g_audio (before every function that reads them) -------------
A_ANCHOR = b"static Audio* g_audio = nullptr;\n\nnamespace AudioInternal {\n"
A_BLOCK = T(r"""static Audio* g_audio = nullptr;

// ---- experiment 0405 (series e5 of experiment 0401, mkao0405.py): the switches of this file's ports ----
// Ported in adapted form from KytyPS5 (github.com/KytyPS5/KytyPS5, GPL-2.0) at dfec14aa8c59f8ea2bc4d87eba9854fc370161c6;
// each inserted block names its source lines. Three groups, default off, each read once from the environment, with one
// stderr line per group at the Audio subsystem's init (or at the group's first use, if that comes first). A value: unset,
// empty or "0" is off; a comma list naming items ("ka01,ka02") turns on only those; any other value turns on all of the
// group's items.
//   KYTY_BC5_AUDIOOUT_CHECKS  ka01 sceAudioOutOutputs: num 0 or > 32 -> AUDIO_OUT_ERROR_INVALID_SIZE
//                             ka02 sceAudioOutOpen: freq 0 -> AUDIO_OUT_ERROR_INVALID_SAMPLE_FREQ
//   KYTY_BC5_AUDIOIN_CHECKS   ka06 sceAudioInInput: silence written into dest; a null dest returns 0
//                             ka07 sceAudioInOpen: errors for type, index, len 0 and freq 0 instead of an exit
//   KYTY_BC5_NGS2_RACK_FIX    ka03 Ngs2RackDestroy: the rack unlinked and given back through its allocator
//                             ka08 Ngs2VoiceGetState: a custom rack's voice state as large as configured
// Off is today's path exactly: the old code stays, the new code runs only when its item is on.
// KytyPS5's copyright remains with its authors; GPL-2.0 as the rest of this file.
static constexpr uint32_t BC5_AO_KA01 = 1u << 0;
static constexpr uint32_t BC5_AO_KA02 = 1u << 1;
static constexpr uint32_t BC5_AO_KA06 = 1u << 2;
static constexpr uint32_t BC5_AO_KA07 = 1u << 3;
static constexpr uint32_t BC5_AO_KA03 = 1u << 4;
static constexpr uint32_t BC5_AO_KA08 = 1u << 5;

struct Bc5AoItem {
»const char* name;
»uint32_t    bit;
};

// The items (of the n in `items`) that the value `e` turns on; 0: off.
static uint32_t Bc5AoParse(const char* e, const Bc5AoItem* items, int n) {
»if (e == nullptr || e[0] == '\0' || std::strcmp(e, "0") == 0) {
»»return 0;
»}
»uint32_t all = 0;
»for (int k = 0; k < n; k++) {
»»all |= items[k].bit;
»}
»uint32_t    on = 0;
»const char* p  = e;
»for (;;) {
»»const char*  comma = std::strchr(p, ',');
»»const size_t len   = comma != nullptr ? static_cast<size_t>(comma - p) : std::strlen(p);
»»for (int k = 0; k < n; k++) {
»»»if (len == std::strlen(items[k].name) && std::strncmp(p, items[k].name, len) == 0) {
»»»»on |= items[k].bit;
»»»}
»»}
»»if (comma == nullptr) {
»»»break;
»»}
»»p = comma + 1;
»}
»return on != 0 ? on : all;
}

// Reads the group's switch and prints its one line: "[bc5] exp 0405: <group> on (items: ...)" or "... off".
static uint32_t Bc5AoRead(const char* env, const char* group, const Bc5AoItem* items, int n) {
»const uint32_t on   = Bc5AoParse(std::getenv(env), items, n);
»std::string    line = std::string("[bc5] exp 0405: ") + group;
»if (on == 0) {
»»line += " off";
»} else {
»»line += " on (items:";
»»for (int k = 0; k < n; k++) {
»»»if ((on & items[k].bit) != 0) {
»»»»line += std::string(" ") + items[k].name;
»»»}
»»}
»»line += ")";
»}
»std::fprintf(stderr, "%s\n", line.c_str());
»std::fflush(stderr);
»return on;
}

static uint32_t Bc5AudioOutChecks() {
»static const Bc5AoItem items[] = {{"ka01", BC5_AO_KA01}, {"ka02", BC5_AO_KA02}};
»static const uint32_t  on      = Bc5AoRead("KYTY_BC5_AUDIOOUT_CHECKS", "audioout checks", items, 2);
»return on;
}

static uint32_t Bc5AudioInChecks() {
»static const Bc5AoItem items[] = {{"ka06", BC5_AO_KA06}, {"ka07", BC5_AO_KA07}};
»static const uint32_t  on      = Bc5AoRead("KYTY_BC5_AUDIOIN_CHECKS", "audioin checks", items, 2);
»return on;
}

static uint32_t Bc5Ngs2RackFix() {
»static const Bc5AoItem items[] = {{"ka03", BC5_AO_KA03}, {"ka08", BC5_AO_KA08}};
»static const uint32_t  on      = Bc5AoRead("KYTY_BC5_NGS2_RACK_FIX", "ngs2 rack fix", items, 2);
»return on;
}
// ---- end of experiment 0405's switches ----

namespace AudioInternal {
""")

# ---- block B: the Ngs2 helpers, after Ngs2GetStateFlags (they use it, the voice structs and g_racks_list) ---------------
B_ANCHOR = b"static Ngs2SystemOption Ngs2DefaultSystemOption() {\n"
B_BLOCK = T(r"""// ---- experiment 0405 ka03 and ka08 (KYTY_BC5_NGS2_RACK_FIX; mkao0405.py) ----
// ka03, from KytyPS5 (github.com/KytyPS5/KytyPS5, GPL-2.0) dfec14a src/libs/ngs2.cpp:1456-1528 (Ngs2RackDestroy), 1377
// (the rack's context buffer kept at create), 910 (g_racks_mutex), 1380-1384 and 1972-1983 (the racks' list linked and
// walked under it), adapted. Ngs2RackDestroy only zeroed *buffer_info: the rack stayed in g_racks_list, Ngs2SystemRender
// went on writing its voices into memory the title had freed, and a rack made with an allocator was never given back.
// When on, the rack is unlinked under its system's mutex and the racks' mutex; then its allocator's free handler gets the
// context buffer the rack was made in (and its result is returned), or, for a rack made without an allocator, that buffer
// is returned in *buffer_info. A handle not in the list (0, or destroyed already) returns
// BC5_NGS2_ERROR_INVALID_RACK_HANDLE. The context buffer is kept in a map beside the rack, not in Ngs2RackInternal, so
// that the rack's size (Ngs2RackQueryBufferSize) does not change. KytyPS5's custom-module cleanup (ngs2.cpp:1503-1518) is
// not ported: our racks have no modules. Lock order, as KytyPS5's: a system's mutex, then the racks' mutex.
// ka08, from KytyPS5 dfec14a src/libs/ngs2.cpp:2795-2813 (a0b99a8 "ngs2: accept larger custom voice state buffers") and
// 897-905 (the custom sampler's voice state), GPL-2.0: a custom mastering or custom sampler voice's state is the rack's
// configured state_size; a larger buffer is accepted (that many bytes written, the rest untouched), a smaller one returns
// BC5_NGS2_ERROR_STATE_SIZE. Ours has no decode state, so only state_flags is filled. A rack configured smaller than its
// state struct takes today's path (KytyPS5 exits there; no new exit here).
// TODO(verify): both error values are KytyPS5's (its PS5 libSceNgs2 codes, 0x804a8xxx); shadPS4 60c42b9
// src/core/libraries/ngs2/ngs2_error.h:50 and :11 give the PS4 library's INVALID_RACK_HANDLE 0x804A0261 and
// INVALID_OUT_SIZE 0x804A0054.
static constexpr int32_t BC5_NGS2_ERROR_INVALID_RACK_HANDLE = static_cast<int32_t>(0x804a8202u); // KytyPS5 ngs2.cpp:1457
static constexpr int32_t BC5_NGS2_ERROR_STATE_SIZE          = static_cast<int32_t>(0x804a8011u); // KytyPS5 ngs2.cpp:2803

struct Bc5Ngs2CustomSamplerVoiceState { // KytyPS5 dfec14a src/libs/ngs2.cpp:897-905
»Ngs2VoiceState voice_state;
»const void*    waveform_data;
»uint64_t       num_decoded_samples;
»uint64_t       decoded_data_size;
»uint64_t       user_data;
»uint32_t       reserved;
»uint32_t       reserved2;
};

static_assert(sizeof(Bc5Ngs2CustomSamplerVoiceState) == 48);

static Common::Mutex                                            g_bc5_racks_mutex;  // KytyPS5's g_racks_mutex
static std::map<const Ngs2RackInternal*, Ngs2ContextBufferInfo> g_bc5_rack_buffers; // each linked rack's context buffer

static bool Bc5Ngs2Ka03() {
»return (Bc5Ngs2RackFix() & BC5_AO_KA03) != 0;
}

// Ngs2RackDestroy when ka03 is on; the caller has zeroed *buffer_info (if given).
static int Bc5Ngs2RackDestroy(uintptr_t rack_handle, Ngs2ContextBufferInfo* buffer_info) {
»if (rack_handle == 0) {
»»return BC5_NGS2_ERROR_INVALID_RACK_HANDLE;
»}
»auto*         rack = reinterpret_cast<Ngs2RackInternal*>(rack_handle);
»Ngs2Internal* ngs  = nullptr;
»g_bc5_racks_mutex.Lock();
»for (auto* current = g_racks_list; current != nullptr; current = current->next) {
»»if (current == rack) {
»»»ngs = current->ngs;
»»»break;
»»}
»}
»g_bc5_racks_mutex.Unlock();
»if (ngs == nullptr) {
»»return BC5_NGS2_ERROR_INVALID_RACK_HANDLE;
»}
»Ngs2ContextBufferInfo context_buffer {};
»Ngs2BufferAllocator   allocator;
»{
»»Common::LockGuard lock(ngs->mutex);
»»Common::LockGuard racks_lock(g_bc5_racks_mutex);
»»auto**            link = &g_racks_list;
»»while (*link != nullptr && *link != rack) {
»»»link = &(*link)->next;
»»}
»»if (*link == nullptr) { // destroyed by another thread meanwhile
»»»return BC5_NGS2_ERROR_INVALID_RACK_HANDLE;
»»}
»»*link = rack->next;
»»if (auto it = g_bc5_rack_buffers.find(rack); it != g_bc5_rack_buffers.end()) {
»»»context_buffer = it->second;
»»»g_bc5_rack_buffers.erase(it);
»»} else { // not expected (the switch is read once): the buffer as Ngs2RackQueryBufferSize sized it
»»»context_buffer.host_buffer = rack;
»»»context_buffer.host_buffer_size =
»»»    sizeof(Ngs2RackInternal) + sizeof(Ngs2VoiceInternal) * rack->option.common.max_voices;
»»»context_buffer.user_data = rack->allocator.user_data;
»»}
»»allocator = rack->allocator;
»}
»LOGF("\t exp 0405 ka03: rack unlinked, host_buffer = 0x%016" PRIx64 ", free_handler = 0x%016" PRIx64 "\n",
»     reinterpret_cast<uint64_t>(context_buffer.host_buffer), reinterpret_cast<uint64_t>(allocator.free_handler));
»if (allocator.free_handler != nullptr) {
»»return allocator.free_handler(&context_buffer);
»}
»if (buffer_info != nullptr) {
»»*buffer_info = context_buffer;
»}
»return OK;
}

// Ngs2VoiceGetState for a custom mastering or custom sampler voice when ka08 is on (under the system's mutex). False: the
// rack is configured smaller than its state struct, and the caller takes today's path.
static bool Bc5Ngs2CustomVoiceState(const Ngs2VoiceInternal* voice, Ngs2VoiceState* state, size_t state_size,
                                    int* result) {
»const bool   sampler    = voice->rack->type == Ngs2RackType::CustomSampler;
»const size_t configured = sampler ? voice->rack->option.custom_sampler.custom_rack_option.state_size
»                                  : voice->rack->option.custom_mastering.custom_rack_option.state_size;
»if (configured < (sampler ? sizeof(Bc5Ngs2CustomSamplerVoiceState) : sizeof(Ngs2CustomMasteringVoiceState))) {
»»return false;
»}
»if (state_size < configured) {
»»*result = BC5_NGS2_ERROR_STATE_SIZE;
»»return true;
»}
»std::memset(state, 0, configured);
»state->state_flags = Ngs2GetStateFlags(voice);
»LOGF("\t exp 0405 ka08: state_flags = %u (%" PRIu64 " of %" PRIu64 " bytes)\n", state->state_flags,
»     static_cast<uint64_t>(configured), static_cast<uint64_t>(state_size));
»*result = OK;
»return true;
}
// ---- end of experiment 0405's Ngs2 helpers ----

""")

# ---- the small edits: (what, old, new); each old must occur exactly once in the input -----------------------------------
EDITS = (
    ("KYTY_SUBSYSTEM_INIT(Audio): the switches' lines",
     T("»EXIT_IF(g_audio != nullptr);\n\n»g_audio = new Audio;\n}\n"),
     T("»EXIT_IF(g_audio != nullptr);\n\n»g_audio = new Audio;\n"
       "»// experiment 0405: each group's switch is read once here and prints its line, on or off (mkao0405.py)\n"
       "»(void)Bc5AudioOutChecks();\n"
       "»(void)Bc5AudioInChecks();\n"
       "»(void)Bc5Ngs2RackFix();\n"
       "}\n")),
    ("Audio::AudioInInput: ka06 silence",
     T("»m_in_ports[handle.GetId()].last_input_time = LibKernel::KernelGetProcessTime();\n\n»return port.samples_num;\n}\n"),
     T("»m_in_ports[handle.GetId()].last_input_time = LibKernel::KernelGetProcessTime();\n\n"
       "»// experiment 0405 ka06 (KYTY_BC5_AUDIOIN_CHECKS): there is no capture device here, so the title gets silence instead\n"
       "»// of whatever its buffer held (KytyPS5 dfec14a src/libs/audio.cpp:805-806, GPL-2.0: samples_num frames zeroed when it\n"
       "»// has no capture stream). AudioInOpen keeps only 16-bit mono (2 bytes a frame) and 16-bit stereo (4) ports.\n"
       "»if ((Bc5AudioInChecks() & BC5_AO_KA06) != 0) {\n"
       "»»std::memset(dest, 0, static_cast<size_t>(port.samples_num) * (port.format == Format::Signed16bitMono ? 2u : 4u));\n"
       "»}\n\n"
       "»return port.samples_num;\n}\n")),
    ("AudioOut::AudioOutOpen: ka02",
     T("»»return AUDIO_OUT_ERROR_INVALID_PORT_TYPE;\n»}\n»EXIT_NOT_IMPLEMENTED(index != 0);\n"),
     T("»»return AUDIO_OUT_ERROR_INVALID_PORT_TYPE;\n»}\n"
       "»// experiment 0405 ka02 (KYTY_BC5_AUDIOOUT_CHECKS): no port with freq 0, whose first output divides by it (Audio::\n"
       "»// AudioOutOutputs, block_time: SIGFPE): KytyPS5 dfec14a src/libs/audio.cpp:870-872 (GPL-2.0).\n"
       "»if ((Bc5AudioOutChecks() & BC5_AO_KA02) != 0 && freq == 0) {\n"
       "»»return AUDIO_OUT_ERROR_INVALID_SAMPLE_FREQ;\n"
       "»}\n"
       "»EXIT_NOT_IMPLEMENTED(index != 0);\n")),
    ("AudioOut::AudioOutOutputs: ka01",
     T("»EXIT_NOT_IMPLEMENTED(param == nullptr);\n\n»Audio::OutputParam params[Audio::OUT_PORTS_MAX];\n"),
     T("»EXIT_NOT_IMPLEMENTED(param == nullptr);\n"
       "»// experiment 0405 ka01 (KYTY_BC5_AUDIOOUT_CHECKS): num 0 exited in Audio::AudioOutOutputs, and num > 32 wrote past\n"
       "»// params[] below (a stack overflow): KytyPS5 dfec14a src/libs/audio.cpp:995-997 (GPL-2.0).\n"
       "»if ((Bc5AudioOutChecks() & BC5_AO_KA01) != 0 && (num == 0 || num > static_cast<uint32_t>(Audio::OUT_PORTS_MAX))) {\n"
       "»»return AUDIO_OUT_ERROR_INVALID_SIZE;\n"
       "»}\n\n"
       "»Audio::OutputParam params[Audio::OUT_PORTS_MAX];\n")),
    ("AudioIn::AudioInOpen: ka07",
     T("»EXIT_NOT_IMPLEMENTED(type != 1);\n»EXIT_NOT_IMPLEMENTED(index != 0);\n"),
     T("»// experiment 0405 ka07 (KYTY_BC5_AUDIOIN_CHECKS): errors instead of an exit, and no port with len 0 or freq 0 (its\n"
       "»// first input divides by freq): KytyPS5 dfec14a src/libs/audio.cpp:1047-1058 (GPL-2.0), of its len/freq rules only\n"
       "»// the zero guards (its full sets are exp 0405's KA22). Type 0 opens a port, as type 1 does.\n"
       "»const bool bc5_ka07 = (Bc5AudioInChecks() & BC5_AO_KA07) != 0;\n"
       "»if (bc5_ka07) {\n"
       "»»if (type != 0 && type != 1) {\n"
       "»»»return AUDIO_IN_ERROR_INVALID_TYPE;\n"
       "»»}\n"
       "»»if (index != 0) {\n"
       "»»»return AUDIO_IN_ERROR_INVALID_PARAM;\n"
       "»»}\n"
       "»»if (len == 0) {\n"
       "»»»return AUDIO_IN_ERROR_INVALID_SIZE;\n"
       "»»}\n"
       "»»if (freq == 0) {\n"
       "»»»return AUDIO_IN_ERROR_INVALID_FREQ;\n"
       "»»}\n"
       "»}\n"
       "»EXIT_NOT_IMPLEMENTED(!bc5_ka07 && type != 1); // experiment 0405 ka07: was EXIT_NOT_IMPLEMENTED(type != 1)\n"
       "»EXIT_NOT_IMPLEMENTED(index != 0);\n")),
    ("AudioIn::AudioInInput: ka06 null dest",
     T("»EXIT_NOT_IMPLEMENTED(dest == nullptr);\n\n»EXIT_IF(g_audio == nullptr);\n\n»if (!g_audio->AudioInValid(Audio::Id(handle))) {\n"),
     T("»// experiment 0405 ka06 (KYTY_BC5_AUDIOIN_CHECKS): a null dest is a stop, not an exit: an invalid handle still returns\n"
       "»// AUDIO_IN_ERROR_INVALID_HANDLE, a valid one 0 frames at once (KytyPS5 dfec14a src/libs/audio.cpp:747-749, 808-811\n"
       "»// and 822, GPL-2.0; ours has no capture stream to stop).\n"
       "»if ((Bc5AudioInChecks() & BC5_AO_KA06) != 0 && dest == nullptr) {\n"
       "»»EXIT_IF(g_audio == nullptr);\n"
       "»»return g_audio->AudioInValid(Audio::Id(handle)) ? 0 : AUDIO_IN_ERROR_INVALID_HANDLE;\n"
       "»}\n"
       "»EXIT_NOT_IMPLEMENTED(dest == nullptr);\n\n»EXIT_IF(g_audio == nullptr);\n\n»if (!g_audio->AudioInValid(Audio::Id(handle))) {\n")),
    ("Ngs2RackCreate: the link (ka03)",
     T("»rack->next   = g_racks_list;\n»g_racks_list = rack;\n"),
     T("»// experiment 0405 ka03 (KYTY_BC5_NGS2_RACK_FIX): the list changed under the racks' mutex, and the rack's context\n"
       "»// buffer kept for Ngs2RackDestroy (KytyPS5 dfec14a src/libs/ngs2.cpp:1377-1384, GPL-2.0); neither when off\n"
       "»const bool bc5_ka03 = Bc5Ngs2Ka03();\n"
       "»if (bc5_ka03) {\n"
       "»»g_bc5_racks_mutex.Lock();\n"
       "»»g_bc5_rack_buffers[rack] = *buffer_info;\n"
       "»}\n"
       "»rack->next   = g_racks_list;\n»g_racks_list = rack;\n"
       "»if (bc5_ka03) {\n"
       "»»g_bc5_racks_mutex.Unlock();\n"
       "»}\n")),
    ("Ngs2RackDestroy (ka03)",
     T("»if (buffer_info != nullptr) {\n»»std::memset(buffer_info, 0, sizeof(Ngs2ContextBufferInfo));\n»}\n\n»return OK;\n}\n\n"
       "int KYTY_SYSV_ABI Ngs2RackLock("),
     T("»if (buffer_info != nullptr) {\n»»std::memset(buffer_info, 0, sizeof(Ngs2ContextBufferInfo));\n»}\n"
       "»if (Bc5Ngs2Ka03()) { // experiment 0405 ka03 (KYTY_BC5_NGS2_RACK_FIX): unlinked and given back (Bc5Ngs2RackDestroy)\n"
       "»»return Bc5Ngs2RackDestroy(rack_handle, buffer_info);\n"
       "»}\n\n»return OK;\n}\n\n"
       "int KYTY_SYSV_ABI Ngs2RackLock(")),
    ("Ngs2SystemRender: the walk's lock (ka03)",
     T("»for (auto* rack = g_racks_list; rack != nullptr; rack = rack->next) {\n»»if (rack->ngs == ngs) {\n"),
     T("»// experiment 0405 ka03 (KYTY_BC5_NGS2_RACK_FIX): the racks' list walked under its mutex (KytyPS5 dfec14a\n"
       "»// src/libs/ngs2.cpp:1972-1983, GPL-2.0), so that a rack being destroyed is walked whole or not at all; not when off\n"
       "»const bool bc5_ka03 = Bc5Ngs2Ka03();\n"
       "»if (bc5_ka03) {\n"
       "»»g_bc5_racks_mutex.Lock();\n"
       "»}\n"
       "»for (auto* rack = g_racks_list; rack != nullptr; rack = rack->next) {\n»»if (rack->ngs == ngs) {\n")),
    ("Ngs2SystemRender: the walk's unlock (ka03)",
     T("»}\n\n»return OK;\n}\n\nint KYTY_SYSV_ABI Ngs2ParseWaveformData("),
     T("»}\n"
       "»if (bc5_ka03) { // experiment 0405 ka03\n"
       "»»g_bc5_racks_mutex.Unlock();\n"
       "»}\n\n»return OK;\n}\n\nint KYTY_SYSV_ABI Ngs2ParseWaveformData(")),
    ("Ngs2VoiceGetState (ka08)",
     T("»Common::LockGuard lock(voice->rack->ngs->mutex);\n\n»switch (voice->rack->type) {\n"
       "»»case Ngs2RackType::Submixer: {\n»»»EXIT_NOT_IMPLEMENTED(state_size != sizeof(Ngs2SubmixerVoiceState));\n"),
     T("»Common::LockGuard lock(voice->rack->ngs->mutex);\n\n"
       "»// experiment 0405 ka08 (KYTY_BC5_NGS2_RACK_FIX): a custom rack's voice state as large as configured\n"
       "»// (Bc5Ngs2CustomVoiceState); today's path when off or when the rack is configured smaller than its state struct\n"
       "»if (int bc5_result = OK; (Bc5Ngs2RackFix() & BC5_AO_KA08) != 0 &&\n"
       "»                         (voice->rack->type == Ngs2RackType::CustomMastering ||\n"
       "»                          voice->rack->type == Ngs2RackType::CustomSampler) &&\n"
       "»                         Bc5Ngs2CustomVoiceState(voice, state, state_size, &bc5_result)) {\n"
       "»»return bc5_result;\n"
       "»}\n\n"
       "»switch (voice->rack->type) {\n"
       "»»case Ngs2RackType::Submixer: {\n»»»EXIT_NOT_IMPLEMENTED(state_size != sizeof(Ngs2SubmixerVoiceState));\n")),
)

# Definitions block B uses must come before it; the functions that use it come after it.
B_BEFORE = (b"static Ngs2RackInternal* g_racks_list = nullptr;\n",
            b"static uint32_t Ngs2GetStateFlags(const Ngs2VoiceInternal* voice) {\n",
            b"struct Ngs2CustomMasteringVoiceState {\n",
            b"struct Ngs2BufferAllocator {\n",
            b"struct Ngs2VoiceState {\n")
B_AFTER = (b"int KYTY_SYSV_ABI Ngs2RackCreate(",
           b"int KYTY_SYSV_ABI Ngs2RackDestroy(",
           b"int KYTY_SYSV_ABI Ngs2SystemRender(",
           b"int KYTY_SYSV_ABI Ngs2VoiceGetState(")
# Block A must come after the class Audio (its member functions and exports use the switches) and before every user.
A_BEFORE = (b"class Audio {\n",)
A_AFTER = (b"KYTY_SUBSYSTEM_INIT(Audio) {\n",
           b"uint32_t Audio::AudioInInput(Id handle, void* dest) {\n",
           b"int KYTY_SYSV_ABI AudioOutOpen(int user_id, int type, int index, uint32_t len, uint32_t freq,\n",
           b"int KYTY_SYSV_ABI AudioOutOutputs(AudioOutOutputParam* param, uint32_t num) {\n",
           b"int KYTY_SYSV_ABI AudioInOpen(int user_id, uint32_t type, uint32_t index, uint32_t len,\n",
           b"int KYTY_SYSV_ABI AudioInInput(int handle, void* dest) {\n",
           B_ANCHOR)


def balance(b):
    return (b.count(b"{") - b.count(b"}"), b.count(b"(") - b.count(b")"), b.count(b"[") - b.count(b"]"))


def once(s, old, new, what):
    assert s.count(old) == 1, ("the anchor must occur exactly once", what, old[:80], s.count(old))
    assert balance(old) == balance(new), ("the edit changes the balance", what, balance(old), balance(new))
    new.decode("ascii")
    return s.replace(old, new)


def ordered(s, anchor, before, after):
    at = s.index(anchor)
    for b in before:
        assert s.count(b) == 1 and s.index(b) < at, ("must be defined before the block, once", b[:70], s.count(b))
    for b in after:
        assert s.count(b) == 1 and s.index(b) > at, ("must come after the block, once", b[:70], s.count(b))


def edit(s):
    for m in MARKS:
        assert m not in s, ("the unit has the edit already", m)
    n0372 = s.count(EXP0372)
    assert n0372 > 0, "audio.cpp has no 'exp 0372' lines: not the tree with experiment 0372's route"
    for blk, keeps in ((A_BLOCK, A_ANCHOR), (B_BLOCK, b"")):  # block A ends with its anchor (an open namespace brace)
        assert balance(blk) == balance(keeps), ("a block is not balanced", balance(blk), balance(keeps))
        assert EXP0372 not in blk
    for what, old, new in EDITS:
        assert s.count(old) == 1, ("the anchor must occur exactly once in the input", what, s.count(old))
        assert EXP0372 not in new
    ordered(s, A_ANCHOR, A_BEFORE, A_AFTER)
    ordered(s, B_ANCHOR, B_BEFORE, B_AFTER)
    out = once(s, A_ANCHOR, A_BLOCK, "block A")
    out = once(out, B_ANCHOR, B_BLOCK + B_ANCHOR, "block B")
    for what, old, new in EDITS:
        out = once(out, old, new, what)
    assert out.count(EXP0372) == n0372, ("the count of 'exp 0372' changed", n0372, out.count(EXP0372))
    lines0372 = sum(1 for ln in s.split(b"\n") if EXP0372 in ln)
    assert sum(1 for ln in out.split(b"\n") if EXP0372 in ln) == lines0372, "the lines with 'exp 0372' changed"
    assert balance(out) == balance(s), ("the unit's balance changed", balance(s), balance(out))
    # Every helper is defined once and used where the edits put it (the count includes the definition).
    for name, uses in ((b"Bc5AudioOutChecks()", 4), (b"Bc5AudioInChecks()", 5), (b"Bc5Ngs2RackFix()", 4),
                       (b"Bc5Ngs2Ka03()", 4), (b"Bc5Ngs2RackDestroy(", 2), (b"Bc5Ngs2CustomVoiceState(", 2),
                       (b"BC5_AO_KA01", 3), (b"BC5_AO_KA02", 3), (b"BC5_AO_KA03", 3), (b"BC5_AO_KA06", 4),
                       (b"BC5_AO_KA07", 3), (b"BC5_AO_KA08", 3), (b"g_bc5_racks_mutex", 8), (b"g_bc5_rack_buffers", 5),
                       (b"BC5_NGS2_ERROR_INVALID_RACK_HANDLE", 5), (b"BC5_NGS2_ERROR_STATE_SIZE", 3)):
        assert out.count(name) == uses, (name, out.count(name), uses)
    # Undoing every edit gives the input back byte for byte (each new text occurs once in the output).
    back = out
    for what, old, new in reversed(EDITS):
        assert back.count(new) == 1, ("the edit's text is not unique in the output", what)
        back = back.replace(new, old)
    assert back.count(B_BLOCK) == 1 and back.count(A_BLOCK) == 1
    back = back.replace(B_BLOCK, b"").replace(A_BLOCK, A_ANCHOR)
    assert back == s, "undoing the edits does not give the input back"
    return out, n0372


def md5(b):
    return hashlib.md5(b).hexdigest()


def main():
    assert len(sys.argv) == 3, __doc__
    root, outdir = sys.argv[1], sys.argv[2]
    assert os.path.abspath(root) != os.path.abspath(outdir), "the out dir must not be the tree"
    src = os.path.join(root, REL)
    with open(src, "rb") as f:
        s = f.read()
    for m in MARKS:
        assert m not in s, ("the unit has the edit already", m.decode())
    assert md5(s) == EXPECT_IN, ("not the pinned input", REL, md5(s), EXPECT_IN)
    print(f"# in:  {REL} {md5(s)}", file=sys.stderr)
    for rel in RO:
        p = os.path.join(root, rel)
        assert os.path.isfile(p), ("experiment 0372's file is missing from the tree", rel)
        with open(p, "rb") as f:
            b = f.read()
        print(f"# read only: {rel} {md5(b)} (not written)", file=sys.stderr)
    out, n0372 = edit(s)
    dst = os.path.join(outdir, REL)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    with open(dst, "wb") as f:
        f.write(out)
    print(f"# 'exp 0372' in {REL}: {n0372} lines before and after", file=sys.stderr)
    print(f"{REL} {md5(out)}")


if __name__ == "__main__":
    main()
