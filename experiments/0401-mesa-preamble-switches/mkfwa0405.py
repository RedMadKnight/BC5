#!/usr/bin/env python3
"""BC5 experiment 0401 series e6, tag fwa: exp 0405's decision-1 audio items (values AnyPS5's authors took from firmware
modules run natively or under an emulator, or from their readings of modules), ported in adapted form from AnyPS5
(github.com/boykopovar/AnyPS5, GPL-2.0-only) at 4f41f4c375f5abb487dbd184fbc150f31994d762, into two units of the e6 input
tree (e5's sources):
  src/libs/audio.cpp     e5's unit (md5 230f732dbc20b9b196b28cb007ba95ec: KytyPlus f266548 + patch 0001 + exp 0372's pad
                         audio route + e5's mkao0405.py edit)
  src/libs/avPlayer.cpp  the base tree's unit (md5 966cb8a847467b64ce0486168f052a82; mixed CRLF/LF, kept as it is)
Items, one switch KYTY_BC5_FW_AUDIO (default off, read once, one stderr line at the Audio subsystem's init or first use;
a comma list naming items turns on only those, any other value such as "1" all of them):
  pcmloop        R1 #40: Ngs2ParseWaveformData parses RIFF/WAVE PCM with the module's smpl loop rules (9d1a9c82e,
                 403956973; prosper's reading of libSceNgs2.native)
  audio3d        Audio3d: firmware 13.42's errors where today's code exits or divides by a zero queue depth (5f25ef8a9)
  audio3dstrict  Audio3d: firmware 13.42's errors where today's code succeeds (5f25ef8a9)
  ngs2           sampler racks with 0 or more than 32 waveform blocks -> 0x804A8053 (9c009622b; PS5 module runs on a PC)
  avplayer       AvPlayer stream and frame aspect_ratio from the sample aspect ratio (0b41d81e2 over 5fdc6dbd4; BunnyFl's
                 13.42 reading and emulator run)
No header is changed: avPlayer.cpp declares audio.cpp's Bc5FwAudioItems() itself. libs/ngs2_pcm.h, ngs2_vag_decoder.h and
audio3d_impl.inc are not used. Each input's md5 is asserted; a unit with the edit already is refused; each anchor occurs
exactly once; every edit keeps braces, parentheses and brackets balanced; the inserted text is ASCII; the 'exp 0372' lines
of audio.cpp are unchanged; undoing every edit gives each input back byte for byte. Prints "<relpath> <md5>" per output.
usage: mkfwa0405.py <tree root in> <out dir>"""
import hashlib
import os
import sys

AUDIO = "src/libs/audio.cpp"
AVP = "src/libs/avPlayer.cpp"
EXPECT = {AUDIO: "230f732dbc20b9b196b28cb007ba95ec", AVP: "966cb8a847467b64ce0486168f052a82"}
MARKS = (b"tag fwa", b"KYTY_BC5_FW_AUDIO", b"Bc5FwAudio", b"BC5_FWA_", b"Bc5A3d", b"Bc5Ngs2Pcm", b"Bc5FwAvPlayer")
EXP0372 = b"exp 0372"


def T(text):
    """C++ text written with a visible tab ("»") for each tab of the file's indentation, as ASCII bytes (LF)."""
    return text.replace("»", "\t").encode("ascii")


def CRLF(b):
    """avPlayer.cpp's lines at the edit points end in CRLF."""
    assert b"\r" not in b
    return b.replace(b"\n", b"\r\n")


# =========================================== src/libs/audio.cpp ======================================================

# ---- block A: the switch, after e5's switches (it reuses e5's Bc5AoItem and Bc5AoRead) --------------------------------
A_ANCHOR = b"// ---- end of experiment 0405's switches ----\n\nnamespace AudioInternal {\n"
A_BLOCK = T(r"""// ---- end of experiment 0405's switches ----

// ---- experiment 0405, series e6 of experiment 0401, tag fwa (mkfwa0405.py): KYTY_BC5_FW_AUDIO ----
// Decision 1 of 2026-11-04 (the maintainer): values AnyPS5's authors took from firmware modules run natively or under an
// emulator, or from their readings of modules, are taken as another person's description and ported. Source: AnyPS5
// (github.com/boykopovar/AnyPS5, GPL-2.0-only) at 4f41f4c375f5abb487dbd184fbc150f31994d762, adapted; each inserted
// block names its commit and lines. Items of the one switch:
//   pcmloop        Ngs2ParseWaveformData: RIFF/WAVE PCM parsed, with the module's smpl loop rules (exp 0405 R1 #40)
//   audio3d        Audio3d: firmware 13.42's errors where today's code exits (or divides by a zero queue depth)
//   audio3dstrict  Audio3d: firmware 13.42's errors where today's code succeeds (user 1, a second port, ...)
//   ngs2           Ngs2Rack{QueryBufferSize,Create,CreateWithAllocator}: sampler racks with 0 or > 32 waveform blocks
//   avplayer       AvPlayer: stream and frame aspect_ratio from the sample aspect ratio (in avPlayer.cpp)
// A value: unset, empty or "0" is off; a comma list naming items turns on only those; any other value ("1") all of them.
// One stderr line at the Audio subsystem's init (or first use): "[bc5] exp 0405: fw audio on (items: ...)" or "... off".
// Off is today's path exactly: the old code stays, the new code runs only when its item is on.
static constexpr uint32_t BC5_FWA_PCMLOOP       = 1u << 0;
static constexpr uint32_t BC5_FWA_AUDIO3D       = 1u << 1;
static constexpr uint32_t BC5_FWA_AUDIO3DSTRICT = 1u << 2;
static constexpr uint32_t BC5_FWA_NGS2          = 1u << 3;
static constexpr uint32_t BC5_FWA_AVPLAYER      = 1u << 4;

uint32_t Bc5FwAudioItems(); // external linkage: avPlayer.cpp declares it too (no header is changed)

uint32_t Bc5FwAudioItems() {
»static const Bc5AoItem items[] = {{"pcmloop", BC5_FWA_PCMLOOP},
»                                  {"audio3d", BC5_FWA_AUDIO3D},
»                                  {"audio3dstrict", BC5_FWA_AUDIO3DSTRICT},
»                                  {"ngs2", BC5_FWA_NGS2},
»                                  {"avplayer", BC5_FWA_AVPLAYER}};
»static const uint32_t  on      = Bc5AoRead("KYTY_BC5_FW_AUDIO", "fw audio", items, 5);
»return on;
}

static bool Bc5FwAudio(uint32_t items) {
»return (Bc5FwAudioItems() & items) != 0;
}

// A journal line for an answer an item gives where today's path did not (the first 32 only).
static void Bc5FwAudioNote(const char* what, int result) {
»static std::atomic_int count {0};
»if (count.fetch_add(1) < 32) {
»»std::fprintf(stderr, "[bc5] exp 0405 fw audio: %s -> 0x%08x\n", what, static_cast<unsigned>(result));
»»std::fflush(stderr);
»}
}
// ---- end of tag fwa's switch ----

namespace AudioInternal {
""")

# ---- block B: the Audio3d helpers, after g_ports ------------------------------------------------------------------
B_ANCHOR = b"static Audio3dInternal g_ports[MAX_PORTS] = {};\n"
B_BLOCK = T(r"""static Audio3dInternal g_ports[MAX_PORTS] = {};

// ---- experiment 0405 fwa: audio3d and audio3dstrict (KYTY_BC5_FW_AUDIO; mkfwa0405.py) ----
// From AnyPS5 (github.com/boykopovar/AnyPS5, GPL-2.0-only) 4f41f4c core/libs/prx/libSceAudio3d/Export.cpp: 156-169
// (OpenPs5Port), 214-220 (CheckFloatAttribute), 306-318 (sceAudio3dInitialize), 331-358 (sceAudio3dPortAdvance),
// 377-385 (sceAudio3dPortGetQueueLevel), 407-416 (sceAudio3dPortPush), 453-470 (sceAudio3dPortSetAttribute); the rules
// follow commit 5f25ef8a9 "follow firmware 13.42 for the port, report and audio out calls", whose source is "the checks
// of firmware 13.42's libSceAudio3d.sprx for a PS5 process" (commit message; docs/dev/debt/libSceAudio3d.md), a reading
// of the module (decision 1). The error values are also shadPS4's (60c42b9 src/core/libraries/audio3d/audio3d_error.h:
// 7-13, GPL-2.0-or-later). Our host runs PS5 processes only (no sceKernelIsPs4Process here), so the PS4-process branch
// (96aa06c34, 7f4526471, f4d2d4446) is not taken. Each rule is one of two kinds: audio3d, where today's code exits (or
// divides by a zero queue depth later), and audio3dstrict, where today's code succeeds; a rule whose item is off is
// passed over and its case keeps today's path. Firmware 13.42 has one port, id 0; ours keeps its four unless
// audio3dstrict is on. A full queue is our ring's current slot not empty (AnyPS5 counts mixed frames not pushed yet).
static constexpr int BC5_AUDIO3D_ERROR_INVALID_PORT      = static_cast<int>(0x80EA0002u);
static constexpr int BC5_AUDIO3D_ERROR_INVALID_PARAMETER = static_cast<int>(0x80EA0004u);
static constexpr int BC5_AUDIO3D_ERROR_OUT_OF_RESOURCES  = static_cast<int>(0x80EA0006u);
static constexpr int BC5_AUDIO3D_ERROR_NOT_READY         = static_cast<int>(0x80EA0007u);

static std::atomic_bool g_bc5_a3d_initialized {false}; // Audio3dInitialize returned OK (audio3dstrict's NOT_READY)

static int Bc5A3dRefuse(const char* what, int result) {
»Bc5FwAudioNote(what, result);
»return result;
}

// The port rules of every per-port call: OK, or the error (today: an exit for a bad id, audio3d; success for an open
// port other than 0, audio3dstrict).
static int Bc5A3dPortCheck(const char* function, uint32_t port_id) {
»if (port_id >= MAX_PORTS || !g_ports[port_id].used) {
»»return Bc5FwAudio(BC5_FWA_AUDIO3D) ? Bc5A3dRefuse(function, BC5_AUDIO3D_ERROR_INVALID_PORT) : OK;
»}
»if (port_id != 0 && Bc5FwAudio(BC5_FWA_AUDIO3DSTRICT)) {
»»return Bc5A3dRefuse(function, BC5_AUDIO3D_ERROR_INVALID_PORT);
»}
»return OK;
}

// Audio3dPortOpen's checks in firmware 13.42's order; OK: go on with today's code.
static int Bc5A3dOpenCheck(int user_id, const Audio3dOpenParameters* p, const uint32_t* id) {
»const bool a3d    = Bc5FwAudio(BC5_FWA_AUDIO3D);
»const bool strict = Bc5FwAudio(BC5_FWA_AUDIO3DSTRICT);
»if (strict && !g_bc5_a3d_initialized.load()) {
»»return Bc5A3dRefuse("Audio3dPortOpen before Audio3dInitialize", BC5_AUDIO3D_ERROR_NOT_READY);
»}
»if (p == nullptr || id == nullptr) {
»»return a3d ? Bc5A3dRefuse("Audio3dPortOpen: a null pointer", BC5_AUDIO3D_ERROR_INVALID_PARAMETER) : OK;
»}
»if (user_id != 0xFF && (user_id == 1 ? strict : a3d)) { // today: 255 and 1 open, others exit
»»return Bc5A3dRefuse("Audio3dPortOpen: user_id not 255", BC5_AUDIO3D_ERROR_INVALID_PARAMETER);
»}
»if (p->size != 0x20 && p->size != 0x28) { // today: an exit for every size but 0x20
»»return a3d ? Bc5A3dRefuse("Audio3dPortOpen: size", BC5_AUDIO3D_ERROR_INVALID_PARAMETER) : OK;
»}
»if (strict && (p->rate != 0 || p->granularity < 0x100 || (p->granularity & 0xFFu) != 0 || p->max_objects == 0)) {
»»return Bc5A3dRefuse("Audio3dPortOpen: rate, granularity or max_objects", BC5_AUDIO3D_ERROR_INVALID_PARAMETER);
»}
»if (a3d && (p->queue_depth == 0 || p->buffer_mode != 2)) { // today: a division by 0 later, or an exit
»»return Bc5A3dRefuse("Audio3dPortOpen: queue_depth or buffer_mode", BC5_AUDIO3D_ERROR_INVALID_PARAMETER);
»}
»bool any_used = false;
»bool any_free = false;
»for (const auto& port: g_ports) {
»»any_used = any_used || port.used;
»»any_free = any_free || !port.used;
»}
»if ((strict && any_used) || (a3d && !any_free)) { // firmware 13.42: one port; today: four, then an exit
»»return Bc5A3dRefuse("Audio3dPortOpen: no port left", BC5_AUDIO3D_ERROR_OUT_OF_RESOURCES);
»}
»return OK;
}

// Audio3dPortSetAttribute under the items: true when answered here (*result), false: go on with today's code.
static bool Bc5A3dSetAttribute(uint32_t port_id, uint32_t attribute_id, const void* attribute, size_t attribute_size,
                               int* result) {
»const bool a3d    = Bc5FwAudio(BC5_FWA_AUDIO3D);
»const bool strict = Bc5FwAudio(BC5_FWA_AUDIO3DSTRICT);
»*result           = Bc5A3dPortCheck("Audio3dPortSetAttribute: port", port_id);
»if (*result != OK) {
»»return true;
»}
»if (port_id >= MAX_PORTS || !g_ports[port_id].used) {
»»return false; // audio3d off: today's exit
»}
»const bool is_float = attribute_id == 0x10001 || attribute_id == 0x10002;
»if (!is_float && attribute_id != 0x10003) {
»»*result = a3d ? Bc5A3dRefuse("Audio3dPortSetAttribute: attribute id", BC5_AUDIO3D_ERROR_INVALID_PARAMETER) : OK;
»»return a3d;
»}
»if (attribute == nullptr || (is_float && attribute_size != sizeof(float))) {
»»*result = a3d ? Bc5A3dRefuse("Audio3dPortSetAttribute: attribute or its size", BC5_AUDIO3D_ERROR_INVALID_PARAMETER)
»»              : OK;
»»return a3d;
»}
»float value = 0.0f;
»if (is_float) {
»»std::memcpy(&value, attribute, sizeof(value));
»»const float low  = attribute_id == 0x10001 ? 0.0f : 0.1f; // late reverb level 0..1, downmix spread radius 0.1..2
»»const float high = attribute_id == 0x10001 ? 1.0f : 2.0f;
»»if (strict && (!std::isfinite(value) || value < low || value > high)) {
»»»*result = Bc5A3dRefuse("Audio3dPortSetAttribute: value out of range", BC5_AUDIO3D_ERROR_INVALID_PARAMETER);
»»»return true;
»»}
»}
»if (!a3d) {
»»return false; // today's code stores it
»}
»auto& port = g_ports[port_id]; // stored as today's code does; 0x10003 of any size (firmware 13.42 checks the pointer)
»if (attribute_id == 0x10001) {
»»port.late_reverb_level = value;
»} else if (attribute_id == 0x10002) {
»»port.downmix_spread_radius = value;
»} else if (attribute_size >= sizeof(int)) {
»»std::memcpy(&port.downmix_spread_height_aware, attribute, sizeof(int));
»}
»*result = OK;
»return true;
}
// ---- end of experiment 0405 fwa's Audio3d helpers ----
""")

# ---- block C: the Ngs2 helpers (pcmloop, ngs2), before Ngs2FillDefaultRackOption ------------------------------------
C_ANCHOR = b"static void Ngs2FillDefaultRackOption(uint32_t rack_id, Ngs2RackOptionUnion* option) {\n"
C_BLOCK = T(r"""// ---- experiment 0405 fwa: ngs2 and pcmloop (KYTY_BC5_FW_AUDIO; mkfwa0405.py) ----
// ngs2, from AnyPS5 (github.com/boykopovar/AnyPS5, GPL-2.0-only) 9c009622b "reject sampler racks outside 1 to 32 waveform
// blocks", core/libs/prx/libSceNgs2.native/src/Rack.cpp (4f41f4c CheckedRackOption): a sampler (0x1000) or custom
// sampler (0x4001) rack whose max_waveform_blocks is 0 or above 32 returns 0x804A8053 from RackQueryBufferSize, RackCreate
// and RackCreateWithAllocator. Source: the PS5 firmware 3.20 and 4.03 libSceNgs2.native module run on a PC (commit
// message; docs/dev/debt/libSceNgs2.native.md "NGS2 rack block limit"), decision 1. An option too short to hold the field
// keeps today's path. TODO(verify): the order against the voice and channel checks was not run on the module.
static constexpr int32_t BC5_NGS2_ERROR_INVALID_NUM_WAVEFORM_BLOCKS = static_cast<int32_t>(0x804a8053u);

static int Bc5Ngs2RackBlocks(uint32_t rack_id, const Ngs2RackOption* option) {
»if (!Bc5FwAudio(BC5_FWA_NGS2) || option == nullptr) {
»»return OK;
»}
»uint32_t blocks = 0;
»if (rack_id == 0x1000 && option->size >= offsetof(Ngs2SamplerRackOption, max_waveform_blocks) + sizeof(uint32_t)) {
»»blocks = reinterpret_cast<const Ngs2SamplerRackOption*>(option)->max_waveform_blocks;
»} else if (rack_id == 0x4001 &&
»           option->size >= offsetof(Ngs2CustomSamplerRackOption, max_waveform_blocks) + sizeof(uint32_t)) {
»»blocks = reinterpret_cast<const Ngs2CustomSamplerRackOption*>(option)->max_waveform_blocks;
»} else {
»»return OK;
»}
»if (blocks == 0 || blocks > 32) {
»»Bc5FwAudioNote("Ngs2 rack: max_waveform_blocks 0 or above 32", BC5_NGS2_ERROR_INVALID_NUM_WAVEFORM_BLOCKS);
»»return BC5_NGS2_ERROR_INVALID_NUM_WAVEFORM_BLOCKS;
»}
»return OK;
}

// pcmloop (exp 0405 R1 #40), from AnyPS5 4f41f4c core/libs/prx/libSceNgs2.native/src/Atrac9.cpp:288-321 (ReadChunks),
// 380-401 (AddPcmBlock, ParsePcmLoop: commit 403956973 "follow the module's PCM loop rules", over 9d1a9c82e "parse looped
// PCM waveforms"), 403-436 (PcmWaveformType, ParsePcm), 438-452 (ParseWaveform), 459-468 (sceNgs2ParseWaveformData),
// GPL-2.0-only, adapted. Source of the rules: prosper's reading of libSceNgs2.native.sprx (docs/dev/debt/
// libSceNgs2.native.md "NGS2 PCM waveform parsing", citing prosper 40d95db prosper/src/hle/audio/ngs2_waveform.cpp:
// 194-343), decision 1; not measured on a console. The error values are KytyPS5's (github.com/KytyPS5/KytyPS5, GPL-2.0,
// 4644c52 src/libs/ngs2.cpp:39-44). Only a RIFF/WAVE whose fmt chunk is PCM (tag 1, tag 3 float, or WAVE_FORMAT_EXTENSIBLE
// with the PCM GUID) is parsed here; any other data (ATRAC9, VAG, not RIFF) keeps today's stub answer. Where AnyPS5 throws
// as not modelled (a smpl chunk too short for its loop count or first loop; a loop ending past the last sample), the
// waveform is kept as one block without a loop, with a journal line (TODO(verify)). Our renderer is silent, so this is
// what the title reads back: format, offsets, sample count, loop positions and blocks.
static constexpr int32_t BC5_NGS2_ERROR_INVALID_WAVEFORM_DATA   = static_cast<int32_t>(0x804a8430u);
static constexpr int32_t BC5_NGS2_ERROR_INVALID_WAVEFORM_FORMAT = static_cast<int32_t>(0x804a8431u);
static constexpr int32_t BC5_NGS2_ERROR_UNKNOWN_WAVEFORM_FORMAT = static_cast<int32_t>(0x804a8432u);

static uint32_t Bc5Ngs2PcmLe16(const uint8_t* p) {
»return static_cast<uint32_t>(p[0]) | (static_cast<uint32_t>(p[1]) << 8u);
}

static uint32_t Bc5Ngs2PcmLe32(const uint8_t* p) {
»return static_cast<uint32_t>(p[0]) | (static_cast<uint32_t>(p[1]) << 8u) | (static_cast<uint32_t>(p[2]) << 16u) |
»       (static_cast<uint32_t>(p[3]) << 24u);
}

static const uint8_t BC5_NGS2_PCM_GUID[16] = {0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x10, 0x00,
                                              0x80, 0x00, 0x00, 0xaa, 0x00, 0x38, 0x9b, 0x71};

// The fmt chunk's tag says PCM (a bounded walk that only looks; the module's rules come after it).
static bool Bc5Ngs2PcmIsPcm(const uint8_t* b, size_t size) {
»if (b == nullptr || size < 12 || std::memcmp(b, "RIFF", 4) != 0 || std::memcmp(b + 8, "WAVE", 4) != 0) {
»»return false;
»}
»for (size_t offset = 12; offset + 8 <= size;) {
»»const size_t chunk_size = Bc5Ngs2PcmLe32(b + offset + 4);
»»const size_t payload    = offset + 8;
»»if (std::memcmp(b + offset, "fmt ", 4) == 0) {
»»»if (chunk_size < 2 || chunk_size > size - payload) {
»»»»return false;
»»»}
»»»const uint32_t tag = Bc5Ngs2PcmLe16(b + payload);
»»»if (tag == 0xfffe) {
»»»»return chunk_size >= 40 && std::memcmp(b + payload + 24, BC5_NGS2_PCM_GUID, 16) == 0;
»»»}
»»»return tag == 1 || tag == 3;
»»}
»»if (chunk_size > size - payload) {
»»»return false;
»»}
»»offset = payload + chunk_size + (chunk_size & 1u);
»}
»return false;
}

static void Bc5Ngs2PcmBlock(Ngs2WaveformInfo* info, uint32_t begin, uint32_t samples, uint32_t repeats) {
»auto& block            = info->blocks[info->num_blocks++];
»block                  = Ngs2WaveformBlock();
»block.data_offset      = info->data_offset + static_cast<uint64_t>(begin) * info->audio_frame_size;
»block.data_size        = static_cast<uint64_t>(samples) * info->audio_frame_size;
»block.num_repeats      = repeats;
»block.num_skip_samples = 0;
»block.num_samples      = samples;
}

// The waveform kept as the one block ParsePcm made, without a loop, where AnyPS5 throws.
static int Bc5Ngs2PcmNoLoop(Ngs2WaveformInfo* info, const char* what) {
»info->loop_begin_position = 0;
»info->loop_end_position   = 0;
»Bc5FwAudioNote(what, OK);
»return OK;
}

static int Bc5Ngs2PcmLoop(const uint8_t* sampler, size_t sampler_size, Ngs2WaveformInfo* info) {
»if (sampler == nullptr) {
»»return OK;
»}
»if (sampler_size < 32) {
»»return Bc5Ngs2PcmNoLoop(info, "pcmloop: a smpl chunk too short for its loop count, kept as one block");
»}
»if (Bc5Ngs2PcmLe32(sampler + 28) == 0) {
»»return OK;
»}
»if (sampler_size < 52) {
»»return Bc5Ngs2PcmNoLoop(info, "pcmloop: a smpl chunk too short for its first loop, kept as one block");
»}
»const uint32_t begin       = Bc5Ngs2PcmLe32(sampler + 44);
»const uint32_t end         = Bc5Ngs2PcmLe32(sampler + 48) + 1u; // the end in the chunk is the last sample
»info->loop_begin_position = begin;
»info->loop_end_position   = end;
»if (end <= begin) {
»»return OK; // one block, the positions as read
»}
»if (end > info->num_samples) {
»»return Bc5Ngs2PcmNoLoop(info, "pcmloop: a loop ending past the last sample, kept as one block");
»}
»info->num_blocks = 0;
»if (begin != 0) {
»»Bc5Ngs2PcmBlock(info, 0, begin, 0);
»}
»Bc5Ngs2PcmBlock(info, begin, end - begin, UINT32_MAX); // the loop block repeats forever, whatever the play count
»if (end != info->num_samples) {
»»Bc5Ngs2PcmBlock(info, end, info->num_samples - end, 0);
»}
»return OK;
}

// Ngs2ParseWaveformData when pcmloop is on: true when the data is RIFF/WAVE PCM (*result is the answer, *info filled).
static bool Bc5Ngs2PcmParse(const void* data, size_t size, Ngs2WaveformInfo* info, int* result) {
»const auto* b = static_cast<const uint8_t*>(data);
»if (!Bc5Ngs2PcmIsPcm(b, size)) {
»»return false;
»}
»std::memset(info, 0, sizeof(Ngs2WaveformInfo));
»*result = BC5_NGS2_ERROR_INVALID_WAVEFORM_DATA;
»// The chunks (ReadChunks): a chunk past the RIFF end is an error; a data chunk past the buffer ends the walk.
»const size_t   riff_end     = 8 + static_cast<size_t>(Bc5Ngs2PcmLe32(b + 4));
»const size_t   end          = std::min(size, riff_end);
»const uint8_t* format       = nullptr;
»size_t         format_size  = 0;
»const uint8_t* sampler      = nullptr;
»size_t         sampler_size = 0;
»size_t         data_offset  = 0;
»size_t         data_bytes   = 0;
»if (riff_end < 12) {
»»return true;
»}
»for (size_t offset = 12; offset + 8 <= end;) {
»»const uint8_t* chunk      = b + offset;
»»const size_t   payload    = offset + 8;
»»const size_t   chunk_size = Bc5Ngs2PcmLe32(chunk + 4);
»»if (chunk_size > riff_end - payload) {
»»»return true;
»»}
»»if (std::memcmp(chunk, "data", 4) == 0) {
»»»data_offset = payload;
»»»data_bytes  = chunk_size;
»»»if (chunk_size > end - payload) {
»»»»break;
»»»}
»»}
»»if (chunk_size > end - payload) {
»»»return true;
»»}
»»if (std::memcmp(chunk, "fmt ", 4) == 0) {
»»»format      = b + payload;
»»»format_size = chunk_size;
»»} else if (std::memcmp(chunk, "smpl", 4) == 0) {
»»»sampler      = b + payload;
»»»sampler_size = chunk_size;
»»}
»»offset = payload + chunk_size + (chunk_size & 1u);
»}
»if (format == nullptr || data_offset == 0 || data_offset > UINT32_MAX) {
»»return true;
»}
»// The format (ParseWaveform, ParsePcm).
»*result = BC5_NGS2_ERROR_INVALID_WAVEFORM_FORMAT;
»if (format_size < 2) {
»»return true;
»}
»const uint32_t tag = Bc5Ngs2PcmLe16(format);
»if (tag == 0xfffe && (format_size < 40 || std::memcmp(format + 24, BC5_NGS2_PCM_GUID, 16) != 0)) {
»»*result = BC5_NGS2_ERROR_UNKNOWN_WAVEFORM_FORMAT;
»»return true;
»}
»if (format_size < 16) {
»»return true;
»}
»const bool     floating = tag == 3;
»const uint32_t bits     = Bc5Ngs2PcmLe16(format + 14);
»const uint32_t type     = floating ? (bits == 32 ? 0x18u : bits == 64 ? 0x1au : 0u)
»                                   : (bits == 8    ? 0x11u
»                                      : bits == 16 ? 0x12u
»                                      : bits == 24 ? 0x14u
»                                      : bits == 32 ? 0x16u
»                                                   : 0u);
»if (type == 0) {
»»*result = BC5_NGS2_ERROR_UNKNOWN_WAVEFORM_FORMAT;
»»return true;
»}
»const uint32_t channels        = Bc5Ngs2PcmLe16(format + 2);
»const uint32_t sample_rate     = Bc5Ngs2PcmLe32(format + 4);
»const uint32_t bytes_per_frame = channels * (bits / 8);
»if (channels == 0 || channels > 8 || sample_rate == 0 || sample_rate > 192000 ||
»    Bc5Ngs2PcmLe16(format + 12) != bytes_per_frame) {
»»return true;
»}
»*result = BC5_NGS2_ERROR_INVALID_WAVEFORM_DATA;
»if (data_bytes > size - data_offset || data_bytes % bytes_per_frame != 0) {
»»return true;
»}
»info->format.waveform_type     = type;
»info->format.num_channels      = channels;
»info->format.sample_rate       = sample_rate;
»info->data_offset              = static_cast<uint32_t>(data_offset);
»info->data_size                = static_cast<uint32_t>(data_bytes);
»info->num_samples              = static_cast<uint32_t>(data_bytes / bytes_per_frame);
»info->audio_unit_size          = bytes_per_frame;
»info->num_audio_unit_samples   = 1;
»info->num_audio_unit_per_frame = 1;
»info->audio_frame_size         = bytes_per_frame;
»info->num_audio_frame_samples  = 1;
»info->num_blocks               = 1;
»info->blocks[0].data_offset    = data_offset;
»info->blocks[0].data_size      = data_bytes;
»info->blocks[0].num_samples    = info->num_samples;
»*result                        = Bc5Ngs2PcmLoop(sampler, sampler_size, info);
»return true;
}
// ---- end of experiment 0405 fwa's Ngs2 helpers ----

""")

# ---- the small edits of audio.cpp: (what, old, new); each old occurs exactly once in the input --------------------------
AUDIO_EDITS = (
    ("includes: <cstddef> for offsetof",
     T("#include <cmath>\n"),
     T("#include <cmath>\n#include <cstddef> // experiment 0405 fwa (mkfwa0405.py): offsetof\n")),
    ("KYTY_SUBSYSTEM_INIT(Audio): the switch's line",
     T("»(void)Bc5Ngs2RackFix();\n}\n"),
     T("»(void)Bc5Ngs2RackFix();\n"
       "»(void)Bc5FwAudioItems(); // experiment 0405 fwa: KYTY_BC5_FW_AUDIO's line, on or off (mkfwa0405.py)\n"
       "}\n")),
    ("Audio3dInitialize",
     T("int KYTY_SYSV_ABI Audio3dInitialize(int64_t reserved) {\n»PRINT_NAME();\n\n»EXIT_NOT_IMPLEMENTED(reserved != 0);\n\n"
       "»return OK;\n}\n"),
     T("int KYTY_SYSV_ABI Audio3dInitialize(int64_t reserved) {\n»PRINT_NAME();\n\n"
       "»// experiment 0405 fwa audio3d (KYTY_BC5_FW_AUDIO): reserved not 0 is INVALID_PARAMETER in firmware 13.42 (AnyPS5\n"
       "»// 4f41f4c libSceAudio3d/Export.cpp:306-318, 5f25ef8a9; Bc5A3dRefuse); a repeated call stays OK (TODO(verify))\n"
       "»if (Bc5FwAudio(BC5_FWA_AUDIO3D) && reserved != 0) {\n"
       "»»return Bc5A3dRefuse(\"Audio3dInitialize: reserved\", BC5_AUDIO3D_ERROR_INVALID_PARAMETER);\n"
       "»}\n"
       "»EXIT_NOT_IMPLEMENTED(reserved != 0);\n"
       "»if (Bc5FwAudio(BC5_FWA_AUDIO3D | BC5_FWA_AUDIO3DSTRICT)) {\n"
       "»»g_bc5_a3d_initialized = true; // experiment 0405 fwa audio3dstrict: Audio3dPortOpen before this is NOT_READY\n"
       "»}\n\n"
       "»return OK;\n}\n")),
    ("Audio3dPortOpen",
     T("»PRINT_NAME();\n\n»EXIT_NOT_IMPLEMENTED(parameters == nullptr);\n»EXIT_NOT_IMPLEMENTED(id == nullptr);\n"
       "»EXIT_NOT_IMPLEMENTED(parameters->size != 0x20);\n"),
     T("»PRINT_NAME();\n\n"
       "»// experiment 0405 fwa audio3d, audio3dstrict (KYTY_BC5_FW_AUDIO): firmware 13.42's checks first (Bc5A3dOpenCheck);\n"
       "»// with audio3d a size of 0x28 (num_beds; not used here) opens as 0x20 does\n"
       "»const bool bc5_a3d = Bc5FwAudio(BC5_FWA_AUDIO3D);\n"
       "»if (Bc5FwAudio(BC5_FWA_AUDIO3D | BC5_FWA_AUDIO3DSTRICT)) {\n"
       "»»if (const int bc5_result = Bc5A3dOpenCheck(user_id, parameters, id); bc5_result != OK) {\n"
       "»»»return bc5_result;\n"
       "»»}\n"
       "»}\n"
       "»EXIT_NOT_IMPLEMENTED(parameters == nullptr);\n»EXIT_NOT_IMPLEMENTED(id == nullptr);\n"
       "»EXIT_NOT_IMPLEMENTED(parameters->size != 0x20 && !(bc5_a3d && parameters->size == 0x28)); // was: size != 0x20\n")),
    ("Audio3dPortSetAttribute",
     T("»PRINT_NAME();\n\n»EXIT_NOT_IMPLEMENTED(port_id >= MAX_PORTS);\n»EXIT_NOT_IMPLEMENTED(!g_ports[port_id].used);\n"
       "»EXIT_NOT_IMPLEMENTED(attribute == nullptr);\n"),
     T("»PRINT_NAME();\n\n"
       "»// experiment 0405 fwa audio3d, audio3dstrict (KYTY_BC5_FW_AUDIO): firmware 13.42's checks (Bc5A3dSetAttribute)\n"
       "»if (int bc5_result = OK; Bc5FwAudio(BC5_FWA_AUDIO3D | BC5_FWA_AUDIO3DSTRICT) &&\n"
       "»                         Bc5A3dSetAttribute(port_id, attribute_id, attribute, attribute_size, &bc5_result)) {\n"
       "»»return bc5_result;\n"
       "»}\n"
       "»EXIT_NOT_IMPLEMENTED(port_id >= MAX_PORTS);\n»EXIT_NOT_IMPLEMENTED(!g_ports[port_id].used);\n"
       "»EXIT_NOT_IMPLEMENTED(attribute == nullptr);\n")),
    ("Audio3dPortGetQueueLevel",
     T("»PRINT_NAME();\n\n»EXIT_NOT_IMPLEMENTED(port_id >= MAX_PORTS);\n»EXIT_NOT_IMPLEMENTED(!g_ports[port_id].used);\n"
       "»EXIT_NOT_IMPLEMENTED(queue_level == nullptr && queue_available == nullptr);\n"),
     T("»PRINT_NAME();\n\n"
       "»// experiment 0405 fwa audio3d, audio3dstrict (KYTY_BC5_FW_AUDIO): firmware 13.42's port check, then both outputs\n"
       "»// null is INVALID_PARAMETER (AnyPS5 4f41f4c libSceAudio3d/Export.cpp:377-385)\n"
       "»if (Bc5FwAudio(BC5_FWA_AUDIO3D | BC5_FWA_AUDIO3DSTRICT)) {\n"
       "»»if (const int bc5_result = Bc5A3dPortCheck(\"Audio3dPortGetQueueLevel: port\", port_id); bc5_result != OK) {\n"
       "»»»return bc5_result;\n"
       "»»}\n"
       "»»if (Bc5FwAudio(BC5_FWA_AUDIO3D) && queue_level == nullptr && queue_available == nullptr) {\n"
       "»»»return Bc5A3dRefuse(\"Audio3dPortGetQueueLevel: both outputs null\", BC5_AUDIO3D_ERROR_INVALID_PARAMETER);\n"
       "»»}\n"
       "»}\n"
       "»EXIT_NOT_IMPLEMENTED(port_id >= MAX_PORTS);\n»EXIT_NOT_IMPLEMENTED(!g_ports[port_id].used);\n"
       "»EXIT_NOT_IMPLEMENTED(queue_level == nullptr && queue_available == nullptr);\n")),
    ("Audio3dPortAdvance: the port",
     T("int KYTY_SYSV_ABI Audio3dPortAdvance(uint32_t port_id) {\n»PRINT_NAME();\n\n"),
     T("int KYTY_SYSV_ABI Audio3dPortAdvance(uint32_t port_id) {\n»PRINT_NAME();\n\n"
       "»// experiment 0405 fwa audio3d, audio3dstrict (KYTY_BC5_FW_AUDIO): firmware 13.42's port check (AnyPS5 4f41f4c\n"
       "»// libSceAudio3d/Export.cpp:331-358)\n"
       "»if (Bc5FwAudio(BC5_FWA_AUDIO3D | BC5_FWA_AUDIO3DSTRICT)) {\n"
       "»»if (const int bc5_result = Bc5A3dPortCheck(\"Audio3dPortAdvance: port\", port_id); bc5_result != OK) {\n"
       "»»»return bc5_result;\n"
       "»»}\n"
       "»}\n")),
    ("Audio3dPortAdvance: a full queue",
     T("»»if (port->data[current_index].state == Audio3dData::State::Empty) {\n"
       "»»»port->data[current_index].state = Audio3dData::State::Ready;\n»»}\n"),
     T("»»// experiment 0405 fwa: a full queue is NOT_READY in firmware 13.42 (AnyPS5 4f41f4c libSceAudio3d/Export.cpp:336):\n"
       "»»// the current slot still being played (today: the exit below; audio3d) or advanced and not pushed yet (today:\n"
       "»»// taken again; audio3dstrict)\n"
       "»»if (const auto bc5_state = port->data[current_index].state.load();\n"
       "»»    (bc5_state == Audio3dData::State::Play && Bc5FwAudio(BC5_FWA_AUDIO3D)) ||\n"
       "»»    (bc5_state == Audio3dData::State::Ready && Bc5FwAudio(BC5_FWA_AUDIO3DSTRICT))) {\n"
       "»»»port->data_mutex->Unlock();\n"
       "»»»return Bc5A3dRefuse(\"Audio3dPortAdvance: the queue is full\", BC5_AUDIO3D_ERROR_NOT_READY);\n"
       "»»}\n"
       "»»if (port->data[current_index].state == Audio3dData::State::Empty) {\n"
       "»»»port->data[current_index].state = Audio3dData::State::Ready;\n»»}\n")),
    ("Audio3dPortPush",
     T("int KYTY_SYSV_ABI Audio3dPortPush(uint32_t port_id, uint32_t blocking) {\n»PRINT_NAME();\n\n"
       "»EXIT_NOT_IMPLEMENTED(port_id >= MAX_PORTS);\n»EXIT_NOT_IMPLEMENTED(!g_ports[port_id].used);\n\n"
       "»auto* port = &g_ports[port_id];\n\n»EXIT_NOT_IMPLEMENTED(blocking != 1);\n"),
     T("int KYTY_SYSV_ABI Audio3dPortPush(uint32_t port_id, uint32_t blocking) {\n»PRINT_NAME();\n\n"
       "»// experiment 0405 fwa audio3d, audio3dstrict (KYTY_BC5_FW_AUDIO): firmware 13.42's port check, and with audio3d\n"
       "»// blocking 0 (asynchronous) pushes without waiting (AnyPS5 4f41f4c libSceAudio3d/Export.cpp:407-416); other\n"
       "»// blocking values exit as today (AnyPS5 throws: not known)\n"
       "»if (Bc5FwAudio(BC5_FWA_AUDIO3D | BC5_FWA_AUDIO3DSTRICT)) {\n"
       "»»if (const int bc5_result = Bc5A3dPortCheck(\"Audio3dPortPush: port\", port_id); bc5_result != OK) {\n"
       "»»»return bc5_result;\n"
       "»»}\n"
       "»}\n"
       "»EXIT_NOT_IMPLEMENTED(port_id >= MAX_PORTS);\n»EXIT_NOT_IMPLEMENTED(!g_ports[port_id].used);\n\n"
       "»auto* port = &g_ports[port_id];\n\n"
       "»EXIT_NOT_IMPLEMENTED(blocking != 1 && !(blocking == 0 && Bc5FwAudio(BC5_FWA_AUDIO3D))); // was: blocking != 1\n")),
    ("Ngs2RackQueryBufferSize (ngs2)",
     T("»LOGF(\"\\t rack_id    = 0x%\" PRIx32 \"\\n\"\n»     \"\\t max_voices = %u\\n\",\n»     rack_id, option->max_voices);\n\n"
       "»buffer_info->host_buffer_size =\n"),
     T("»LOGF(\"\\t rack_id    = 0x%\" PRIx32 \"\\n\"\n»     \"\\t max_voices = %u\\n\",\n»     rack_id, option->max_voices);\n\n"
       "»if (const int bc5_result = Bc5Ngs2RackBlocks(rack_id, option); bc5_result != OK) { // experiment 0405 fwa ngs2\n"
       "»»return bc5_result;\n"
       "»}\n"
       "»buffer_info->host_buffer_size =\n")),
    ("Ngs2RackCreate (ngs2)",
     T("»EXIT_NOT_IMPLEMENTED(buffer_info->host_buffer_size == 0);\n»EXIT_NOT_IMPLEMENTED(system_handle == 0);\n\n"
       "»Ngs2RackOptionUnion default_option {};\n»if (option == nullptr) {\n"
       "»»Ngs2FillDefaultRackOption(rack_id, &default_option);\n»»option = &default_option.common;\n"
       "»»LOGF(\"\\t option                 = nullptr, using reset defaults for rack_id 0x%\" PRIx32\n»»     \"\\n\",\n"
       "»»     rack_id);\n»}\n\n»EXIT_NOT_IMPLEMENTED(option->size < sizeof(Ngs2RackOption));\n"),
     T("»EXIT_NOT_IMPLEMENTED(buffer_info->host_buffer_size == 0);\n»EXIT_NOT_IMPLEMENTED(system_handle == 0);\n\n"
       "»Ngs2RackOptionUnion default_option {};\n»if (option == nullptr) {\n"
       "»»Ngs2FillDefaultRackOption(rack_id, &default_option);\n»»option = &default_option.common;\n"
       "»»LOGF(\"\\t option                 = nullptr, using reset defaults for rack_id 0x%\" PRIx32\n»»     \"\\n\",\n"
       "»»     rack_id);\n»}\n\n»EXIT_NOT_IMPLEMENTED(option->size < sizeof(Ngs2RackOption));\n"
       "»if (const int bc5_result = Bc5Ngs2RackBlocks(rack_id, option); bc5_result != OK) { // experiment 0405 fwa ngs2\n"
       "»»return bc5_result;\n"
       "»}\n")),
    ("Ngs2RackCreateWithAllocator (ngs2)",
     T("»EXIT_NOT_IMPLEMENTED(allocator->free_handler == nullptr);\n»EXIT_NOT_IMPLEMENTED(system_handle == 0);\n\n"
       "»Ngs2RackOptionUnion default_option {};\n»if (option == nullptr) {\n"
       "»»Ngs2FillDefaultRackOption(rack_id, &default_option);\n»»option = &default_option.common;\n"
       "»»LOGF(\"\\t option                 = nullptr, using reset defaults for rack_id 0x%\" PRIx32\n»»     \"\\n\",\n"
       "»»     rack_id);\n»}\n\n»EXIT_NOT_IMPLEMENTED(option->size < sizeof(Ngs2RackOption));\n"),
     T("»EXIT_NOT_IMPLEMENTED(allocator->free_handler == nullptr);\n»EXIT_NOT_IMPLEMENTED(system_handle == 0);\n\n"
       "»Ngs2RackOptionUnion default_option {};\n»if (option == nullptr) {\n"
       "»»Ngs2FillDefaultRackOption(rack_id, &default_option);\n»»option = &default_option.common;\n"
       "»»LOGF(\"\\t option                 = nullptr, using reset defaults for rack_id 0x%\" PRIx32\n»»     \"\\n\",\n"
       "»»     rack_id);\n»}\n\n»EXIT_NOT_IMPLEMENTED(option->size < sizeof(Ngs2RackOption));\n"
       "»if (const int bc5_result = Bc5Ngs2RackBlocks(rack_id, option); bc5_result != OK) { // experiment 0405 fwa ngs2\n"
       "»»return bc5_result;\n"
       "»}\n")),
    ("Ngs2ParseWaveformData (pcmloop)",
     T("»EXIT_NOT_IMPLEMENTED(info == nullptr);\n\n»std::memset(info, 0, sizeof(Ngs2WaveformInfo));\n"
       "»info->format.waveform_type = 0x80;\n"),
     T("»EXIT_NOT_IMPLEMENTED(info == nullptr);\n\n"
       "»// experiment 0405 fwa pcmloop (KYTY_BC5_FW_AUDIO): RIFF/WAVE PCM parsed with the module's loop rules\n"
       "»// (Bc5Ngs2PcmParse); any other data keeps the answer below\n"
       "»if (int bc5_result = OK; Bc5FwAudio(BC5_FWA_PCMLOOP) && Bc5Ngs2PcmParse(data, data_size, info, &bc5_result)) {\n"
       "»»return bc5_result;\n"
       "»}\n"
       "»std::memset(info, 0, sizeof(Ngs2WaveformInfo));\n"
       "»info->format.waveform_type = 0x80;\n")),
)

# Definitions block B uses come before it; the functions that use it after it. Likewise for block C and block A.
A_BEFORE = (b"struct Bc5AoItem {\n", b"static uint32_t Bc5AoRead(const char* env, const char* group, const Bc5AoItem* items, int n) {\n")
A_AFTER = (b"KYTY_SUBSYSTEM_INIT(Audio) {\n", b"namespace Audio3d {\n", b"namespace Ngs2 {\n")
B_BEFORE = (b"struct Audio3dOpenParameters {\n", b"struct Audio3dInternal {\n", b"constexpr uint32_t MAX_PORTS = 4;\n")
B_AFTER = (b"int KYTY_SYSV_ABI Audio3dInitialize(int64_t reserved) {\n",
           b"int KYTY_SYSV_ABI Audio3dPortOpen(int user_id, const Audio3dOpenParameters* parameters,\n",
           b"int KYTY_SYSV_ABI Audio3dPortSetAttribute(uint32_t port_id, uint32_t attribute_id,\n",
           b"int KYTY_SYSV_ABI Audio3dPortGetQueueLevel(uint32_t port_id, uint32_t* queue_level,\n",
           b"int KYTY_SYSV_ABI Audio3dPortAdvance(uint32_t port_id) {\n",
           b"int KYTY_SYSV_ABI Audio3dPortPush(uint32_t port_id, uint32_t blocking) {\n")
C_BEFORE = (b"struct Ngs2SamplerRackOption {\n", b"struct Ngs2CustomSamplerRackOption {\n", b"struct Ngs2WaveformInfo {\n",
            b"struct Ngs2WaveformBlock {\n")
C_AFTER = (b"int KYTY_SYSV_ABI Ngs2RackQueryBufferSize(uint32_t rack_id, const Ngs2RackOption* option,\n",
           b"int KYTY_SYSV_ABI Ngs2RackCreate(uintptr_t system_handle, uint32_t rack_id,\n",
           b"int KYTY_SYSV_ABI Ngs2RackCreateWithAllocator(uintptr_t system_handle, uint32_t rack_id,\n",
           b"int KYTY_SYSV_ABI Ngs2ParseWaveformData(const void* data, size_t data_size,\n")

# =========================================== src/libs/avPlayer.cpp ====================================================

# ---- block D: the declaration of audio.cpp's switch reader and the aspect helper, at the namespace's start --------------
D_ANCHOR = CRLF(b"namespace Libs::Audio::AvPlayer {\n\nLIB_NAME(\"AvPlayer\", \"AvPlayer\");\n")
D_BLOCK = CRLF(T(r"""// ---- experiment 0405, series e6 of experiment 0401, tag fwa (mkfwa0405.py): avplayer (KYTY_BC5_FW_AUDIO) ----
namespace Libs::Audio {
uint32_t Bc5FwAudioItems(); // defined in audio.cpp (its switch, read once; no header is changed)
} // namespace Libs::Audio

namespace Libs::Audio::AvPlayer {

LIB_NAME("AvPlayer", "AvPlayer");

// From AnyPS5 (github.com/boykopovar/AnyPS5, GPL-2.0-only) 0b41d81e2 "follow the firmware sample aspect ratio fallbacks",
// over 5fdc6dbd4 "report the sample aspect ratio in video frame info", core/libs/prx/libSceAvPlayer/src/Source.cpp
// (4f41f4c: HasAspect/SampleAspect, the stream info and the frame info), adapted. Source of the rules: BunnyFl's reading
// of firmware 13.42 (emulator execution and code reading, H.264 only, no console run; docs/dev/debt/libSceAvPlayer.md
// "AvPlayer frame aspect ratio"), decision 1: a stream's aspect_ratio is its sample aspect ratio, a frame's the picture's
// sample aspect ratio falling back to the stream's, and 0.0 when neither is given (today: width / height x the stream's
// sample aspect ratio, for both). TODO(verify): FFmpeg gives 0/1 both for an H.264 aspect_ratio_idc of 0 (1.0 on the
// console) and for no aspect information (0.0); HEVC and VP9 are unchecked.
static constexpr uint32_t BC5_FWA_AVPLAYER_ITEM = 1u << 4; // audio.cpp's BC5_FWA_AVPLAYER

static bool Bc5FwAvPlayerOn() {
»return (Libs::Audio::Bc5FwAudioItems() & BC5_FWA_AVPLAYER_ITEM) != 0;
}

float Bc5FwAvPlayerSar(int num, int den, int fallback_num, int fallback_den); // external linkage: the CPU test calls it

// The sample aspect ratio num/den when both are above 0, else the fallback's, else 0.0.
float Bc5FwAvPlayerSar(int num, int den, int fallback_num, int fallback_den) {
»if (num > 0 && den > 0) {
»»return static_cast<float>(av_q2d(AVRational {num, den}));
»}
»if (fallback_num > 0 && fallback_den > 0) {
»»return static_cast<float>(av_q2d(AVRational {fallback_num, fallback_den}));
»}
»return 0.0f;
}
// ---- end of experiment 0405 fwa's avplayer helpers ----
"""))

AVP_EDITS = (
    ("Aspect: the stream's sample aspect ratio (avplayer)",
     CRLF(T("»float Aspect(AVStream* s) const {\n»»if (s->codecpar->height == 0) {\n")),
     CRLF(T("»float Aspect(AVStream* s) const {\n"
            "»»if (Bc5FwAvPlayerOn()) { // experiment 0405 fwa avplayer: the stream's sample aspect ratio alone\n"
            "»»»return Bc5FwAvPlayerSar(s->codecpar->sample_aspect_ratio.num, s->codecpar->sample_aspect_ratio.den, 0, 0);\n"
            "»»}\n"
            "»»if (s->codecpar->height == 0) {\n"))),
    ("PrepareVideo: the frame's sample aspect ratio (avplayer)",
     CRLF(T("»»FillVideoEx(s, &info->details.video);\n»»info->details.video.crop_left_offset = static_cast<uint32_t>(src->crop_left);\n")),
     CRLF(T("»»FillVideoEx(s, &info->details.video);\n"
            "»»if (Bc5FwAvPlayerOn()) { // experiment 0405 fwa avplayer: the picture's, falling back to the stream's\n"
            "»»»info->details.video.aspect_ratio =\n"
            "»»»    Bc5FwAvPlayerSar(src->sample_aspect_ratio.num, src->sample_aspect_ratio.den,\n"
            "»»»                     s->codecpar->sample_aspect_ratio.num, s->codecpar->sample_aspect_ratio.den);\n"
            "»»}\n"
            "»»info->details.video.crop_left_offset = static_cast<uint32_t>(src->crop_left);\n"))),
)
D_AFTER = (b"float Aspect(AVStream* s) const {", b"bool PrepareVideo(AVFrame* src, std::unique_ptr<GuestBuffer>& buffer,")
D_BEFORE = (b"#include <libavutil/avutil.h>",)


# =========================================== machinery ===============================================================

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
        assert s.count(b) >= 1 and s.index(b) < at, ("must be defined before the block", b[:70], s.count(b))
    for b in after:
        assert s.count(b) == 1 and s.index(b) > at, ("must come after the block, once", b[:70], s.count(b))


def undo(out, s, edits, blocks):
    """Undo every edit (in reverse) and every block; the result must be the input, byte for byte."""
    back = out
    for what, old, new in reversed(edits):
        assert back.count(new) == 1, ("the edit's text is not unique in the output", what)
        back = back.replace(new, old)
    for blk, anchor in blocks:
        assert back.count(blk) == 1, "a block is not unique in the output"
        back = back.replace(blk, anchor)
    assert back == s, "undoing the edits does not give the input back"


def edit_audio(s):
    n0372 = s.count(EXP0372)
    assert n0372 > 0, "audio.cpp has no 'exp 0372' lines: not the tree with experiment 0372's route"
    assert b"Bc5AoRead(" in s, "audio.cpp has no e5 mkao0405.py edit (Bc5AoRead): not e5's unit"
    for blk, keeps in ((A_BLOCK, A_ANCHOR), (B_BLOCK, B_ANCHOR), (C_BLOCK, b"")):
        assert balance(blk) == balance(keeps), ("a block is not balanced", balance(blk), balance(keeps))
        assert EXP0372 not in blk
        blk.decode("ascii")
    for what, old, new in AUDIO_EDITS:
        assert s.count(old) == 1, ("the anchor must occur exactly once in the input", what, s.count(old))
        assert EXP0372 not in new
    ordered(s, A_ANCHOR, A_BEFORE, A_AFTER)
    ordered(s, B_ANCHOR, B_BEFORE, B_AFTER)
    ordered(s, C_ANCHOR, C_BEFORE, C_AFTER)
    out = once(s, A_ANCHOR, A_BLOCK, "block A")
    out = once(out, B_ANCHOR, B_BLOCK, "block B")
    out = once(out, C_ANCHOR, C_BLOCK + C_ANCHOR, "block C")
    for what, old, new in AUDIO_EDITS:
        out = once(out, old, new, what)
    assert out.count(EXP0372) == n0372, ("the count of 'exp 0372' changed", n0372, out.count(EXP0372))
    lines0372 = [ln for ln in s.split(b"\n") if EXP0372 in ln]
    assert [ln for ln in out.split(b"\n") if EXP0372 in ln] == lines0372, "the lines with 'exp 0372' changed"
    assert balance(out) == balance(s), ("the unit's balance changed", balance(s), balance(out))
    # Every helper is defined once and used where the edits put it (the counts include the definitions).
    for name, uses in ((b"Bc5FwAudioItems()", 4), (b"Bc5FwAudio(BC5_FWA_", 20), (b"Bc5FwAudioNote(", 4),
                       (b"Bc5A3dRefuse(", 16), (b"Bc5A3dPortCheck(", 5), (b"Bc5A3dOpenCheck(", 2),
                       (b"Bc5A3dSetAttribute(", 2), (b"Bc5Ngs2RackBlocks(", 4), (b"Bc5Ngs2PcmParse(", 2),
                       (b"Bc5Ngs2PcmLoop(", 2), (b"Bc5Ngs2PcmIsPcm(", 2), (b"Bc5Ngs2PcmNoLoop(", 4),
                       (b"Bc5Ngs2PcmBlock(", 4), (b"g_bc5_a3d_initialized", 3)):
        assert out.count(name) == uses, (name, out.count(name), uses)
    undo(out, s, AUDIO_EDITS, ((C_BLOCK, b""), (B_BLOCK, B_ANCHOR), (A_BLOCK, A_ANCHOR)))
    return out, n0372


def edit_avp(s):
    assert balance(D_BLOCK) == balance(D_ANCHOR), ("block D is not balanced", balance(D_BLOCK), balance(D_ANCHOR))
    for what, old, new in AVP_EDITS:
        assert s.count(old) == 1, ("the anchor must occur exactly once in the input", what, s.count(old))
    ordered(s, D_ANCHOR, D_BEFORE, D_AFTER)
    out = once(s, D_ANCHOR, D_BLOCK, "block D")
    for what, old, new in AVP_EDITS:
        out = once(out, old, new, what)
    assert balance(out) == balance(s), ("the unit's balance changed", balance(s), balance(out))
    # The inserted lines end in CRLF as their neighbours do; the LF-only lines elsewhere stay as they are.
    assert out.count(b"\n") - out.count(b"\r\n") == s.count(b"\n") - s.count(b"\r\n"), "LF-only line count changed"
    for name, uses in ((b"Bc5FwAvPlayerOn()", 3), (b"Bc5FwAvPlayerSar(", 4), (b"Bc5FwAudioItems()", 2)):
        assert out.count(name) == uses, (name, out.count(name), uses)
    undo(out, s, AVP_EDITS, ((D_BLOCK, D_ANCHOR),))
    return out


def md5(b):
    return hashlib.md5(b).hexdigest()


def main():
    assert len(sys.argv) == 3, __doc__
    root, outdir = sys.argv[1], sys.argv[2]
    assert os.path.abspath(root) != os.path.abspath(outdir), "the out dir must not be the tree"
    ins = {}
    for rel in (AUDIO, AVP):
        with open(os.path.join(root, rel), "rb") as f:
            s = f.read()
        for m in MARKS:
            assert m not in s, ("the unit has the edit already", rel, m.decode())
        assert md5(s) == EXPECT[rel], ("not the pinned input", rel, md5(s), EXPECT[rel])
        print(f"# in:  {rel} {md5(s)}", file=sys.stderr)
        ins[rel] = s
    outs = {}
    outs[AUDIO], n0372 = edit_audio(ins[AUDIO])
    outs[AVP] = edit_avp(ins[AVP])
    for rel in (AUDIO, AVP):
        dst = os.path.join(outdir, rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        with open(dst, "wb") as f:
            f.write(outs[rel])
    print(f"# 'exp 0372' in {AUDIO}: {n0372} lines before and after", file=sys.stderr)
    for rel in (AUDIO, AVP):
        print(f"{rel} {md5(outs[rel])}")


if __name__ == "__main__":
    main()
