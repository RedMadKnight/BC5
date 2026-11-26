#!/usr/bin/env python3
# BC5 experiment 0243: put vgmstream's ATRAC9 decoder into ~/src/KytyPlus for the vibration configurations 6-7.
# Edits three files in place (backups are made by the caller) and fails loudly if an anchor is missing.
import os, sys
K = os.path.expanduser("~/src/KytyPlus")


def edit(rel, pairs):
    p = os.path.join(K, rel)
    t = open(p, encoding="utf-8", newline="").read()
    crlf = "\r\n" in t
    if crlf:
        t = t.replace("\r\n", "\n")
    for old, new in pairs:
        if t.count(old) != 1:
            sys.exit(f"{rel}: anchor found {t.count(old)} times: {old[:60]!r}")
        t = t.replace(old, new)
    if crlf:
        t = t.replace("\n", "\r\n")
    open(p, "w", encoding="utf-8", newline="").write(t)
    print("edited", rel)


edit("3rdparty/CMakeLists.txt", [(
    "add_library(LibAtrac9 STATIC ${LIBATRAC9_SOURCES})\n",
    "add_library(LibAtrac9 STATIC ${LIBATRAC9_SOURCES})\n"
    "# BC5 (experiment 0243, F300): vgmstream's ATRAC9 decoder (ISC, vgmstream-atrac9/COPYING) for the vibration\n"
    "# channel configurations 6 and 7, which LibAtrac9 lacks.\n"
    "add_library(VgmstreamAtrac9 STATIC vgmstream-atrac9/src/coding/libs/atrac9_dec.c\n"
    "            vgmstream-atrac9/src/coding/libs/atrac9_internal.c)\n"
    "target_include_directories(VgmstreamAtrac9 PUBLIC vgmstream-atrac9/src/coding/libs)\n"
    "if (MSVC)\n\ttarget_compile_options(VgmstreamAtrac9 PRIVATE /W0)\nelse()\n"
    "\ttarget_compile_options(VgmstreamAtrac9 PRIVATE -w)\nendif()\n")])

edit("src/CMakeLists.txt", [(
    " LibAtrac9 kyty_git_version", " LibAtrac9 VgmstreamAtrac9 kyty_git_version")])

H = "src/libs/ajm/atrac9_decoder.h"
edit(H, [
    ('extern "C" {\n#include "libatrac9.h"\n}\n',
     'extern "C" {\n#include "libatrac9.h"\n'
     "// BC5 (experiment 0243, F300): vgmstream's ATRAC9 decoder (3rdparty/vgmstream-atrac9, ISC) decodes the\n"
     "// vibration channel configurations 6 and 7, which LibAtrac9 does not know.\n"
     '#include "atrac9_dec.h"\n}\n#include <cstdlib>\n'),
    ("\t~AjmAt9Decoder() override {\n\t\tif (m_handle != nullptr) {\n\t\t\tAtrac9ReleaseHandle(m_handle);\n\t\t}\n\t}\n",
     "\t~AjmAt9Decoder() override {\n\t\tif (m_handle != nullptr) {\n\t\t\tAtrac9ReleaseHandle(m_handle);\n\t\t}\n"
     "\t\tif (m_vib != nullptr) {\n\t\t\tatrac9_free(m_vib);\n\t\t}\n\t}\n"),
    ("\t\t// BC5 (experiment 0154): the vibration layouts' frames are not the mono/dual-mono bitstream\n"
     "\t\t// LibAtrac9 decodes (two low-band blocks per frame; every frame fails to unpack). Until the\n"
     "\t\t// layout is implemented, these instances decode to silence of the right length: the voice\n"
     "\t\t// stays alive, which the second title's cinematic clock depends on (its sync source is the\n"
     "\t\t// haptic track of the opening), and the haptics are simply not produced.\n"
     "\t\tm_vibration = ((init_config[1] >> 1u) & 7u) >= 6u;\n"
     "\t\tif (m_vibration) {\n"
     "\t\t\tinit_config[1] = static_cast<uint8_t>(init_config[1] - (6u << 1u));\n"
     "\t\t\tstatic std::atomic_bool noted {false};\n"
     "\t\t\tif (!noted.exchange(true)) {\n"
     '\t\t\t\tstd::fprintf(stderr, "bc5 ajm: ATRAC9 vibration layout %u decoded as silence (haptics not produced)\\n",\n'
     "\t\t\t\t             static_cast<unsigned>((m_config_data[1] >> 1u) & 7u));\n"
     "\t\t\t}\n\t\t}\n",
     "\t\t// BC5 (experiment 0154): the vibration layouts' frames are not the mono/dual-mono bitstream\n"
     "\t\t// LibAtrac9 decodes (two low-band blocks per frame; every frame fails to unpack). LibAtrac9\n"
     "\t\t// still describes the stream (same channels, frame and superframe sizes), and the voice must\n"
     "\t\t// stay alive either way: the second title's cinematic clock syncs to the opening's haptic\n"
     "\t\t// track. BC5 (experiment 0243, F300): vgmstream's decoder decodes these frames; they are the\n"
     "\t\t// DualSense's haptic tracks (energy below 1 kHz, exp 0241). KYTY_BC5_AT9_VIBRATION=0 restores\n"
     "\t\t// the old silence of the right length.\n"
     "\t\tm_vibration = ((init_config[1] >> 1u) & 7u) >= 6u;\n"
     "\t\tif (m_vib != nullptr) {\n\t\t\tatrac9_free(m_vib);\n\t\t\tm_vib = nullptr;\n\t\t}\n"
     "\t\tif (m_vibration) {\n"
     "\t\t\tinit_config[1] = static_cast<uint8_t>(init_config[1] - (6u << 1u));\n"
     "\t\t\tif (VibrationDecodeEnabled()) {\n"
     "\t\t\t\tm_vib = atrac9_init(m_config_data);\n"
     "\t\t\t}\n"
     "\t\t\tstatic std::atomic_bool noted {false};\n"
     "\t\t\tif (!noted.exchange(true)) {\n"
     '\t\t\t\tstd::fprintf(stderr, "bc5 ajm: ATRAC9 vibration layout %u %s\\n",\n'
     "\t\t\t\t             static_cast<unsigned>((m_config_data[1] >> 1u) & 7u),\n"
     '\t\t\t\t             m_vib != nullptr ? "decoded by vgmstream (haptics)"\n'
     '\t\t\t\t                              : "decoded as silence (haptics not produced)");\n'
     "\t\t\t}\n\t\t}\n"),
    ("\t\tm_is_initialized          = true;\n\t\tm_num_frames              = 0;\n",
     "\t\tif (m_vib != nullptr) {\n"
     "\t\t\tatrac9_info_t vib_info {};\n"
     "\t\t\tif (atrac9_get_info(m_vib, &vib_info) == 0 && vib_info.channels > 0 &&\n"
     "\t\t\t    vib_info.channels * vib_info.frame_samples <= ATRAC9_MAX_FRAME_SAMPLES * 2) {\n"
     "\t\t\t\tm_codec_info.channels           = vib_info.channels;\n"
     "\t\t\t\tm_codec_info.samplingRate       = vib_info.sample_rate;\n"
     "\t\t\t\tm_codec_info.superframeSize     = vib_info.superframe_size;\n"
     "\t\t\t\tm_codec_info.framesInSuperframe = vib_info.frames_per_superframe;\n"
     "\t\t\t\tm_codec_info.frameSamples       = vib_info.frame_samples;\n"
     "\t\t\t} else {\n\t\t\t\tatrac9_free(m_vib);\n\t\t\t\tm_vib = nullptr;\n\t\t\t}\n\t\t}\n\n"
     "\t\tm_is_initialized          = true;\n\t\tm_num_frames              = 0;\n"),
    ("\t\tif (m_vibration) {\n\t\t\t// BC5 (experiment 0154): a frame of silence; the input is consumed frame by frame.\n",
     "\t\tif (m_vibration && m_vib != nullptr) {\n\t\t\treturn DecodeVibrationFrame(input, bytes_used);\n\t\t}\n"
     "\t\tif (m_vibration) {\n\t\t\t// BC5 (experiment 0154): a frame of silence; the input is consumed frame by frame.\n"),
    ("\tuint64_t CopyDecodedFrame(uint8_t* output, size_t output_size, size_t* output_written,\n",
     "\t// BC5 (experiment 0243): one vibration frame through vgmstream. Callers guarantee the rest of the current\n"
     "\t// superframe is in the input (GetMinimumInputSize), so that is the frame's bound. Returns 0 on success like\n"
     "\t// LibAtrac9's Atrac9Decode, else a nonzero code.\n"
     "\tstatic bool VibrationDecodeEnabled() {\n"
     "\t\tstatic const bool on = [] {\n"
     '\t\t\tconst char* v = std::getenv("KYTY_BC5_AT9_VIBRATION");\n'
     '\t\t\treturn v == nullptr || std::strcmp(v, "0") != 0;\n'
     "\t\t}();\n\t\treturn on;\n\t}\n\n"
     "\tint DecodeVibrationFrame(const uint8_t* input, int* bytes_used) {\n"
     "\t\tconst int src_size = static_cast<int>(m_superframe_bytes_remain);\n"
     "\t\tint       samples  = -1;\n"
     "\t\tswitch (m_sample_encoding) {\n"
     "\t\t\tcase AjmSampleEncoding::S16:\n"
     "\t\t\t\tsamples = atrac9_decode_pcm16(m_vib, input, src_size,\n"
     "\t\t\t\t                              reinterpret_cast<int16_t*>(m_pcm_buffer.data()), bytes_used);\n"
     "\t\t\t\tbreak;\n"
     "\t\t\tcase AjmSampleEncoding::Float:\n"
     "\t\t\t\tsamples = atrac9_decode_float(m_vib, input, src_size,\n"
     "\t\t\t\t                              reinterpret_cast<float*>(m_pcm_buffer.data()), bytes_used);\n"
     "\t\t\t\tbreak;\n"
     "\t\t\tcase AjmSampleEncoding::S32: {\n"
     "\t\t\t\tfloat tmp[ATRAC9_MAX_FRAME_SAMPLES * 2];\n"
     "\t\t\t\tsamples = atrac9_decode_float(m_vib, input, src_size, tmp, bytes_used);\n"
     "\t\t\t\tconst size_t n = (samples > 0 ? static_cast<size_t>(samples) * m_codec_info.channels : 0);\n"
     "\t\t\t\tauto* dst = reinterpret_cast<int32_t*>(m_pcm_buffer.data());\n"
     "\t\t\t\tfor (size_t i = 0; i < n; i++) {\n"
     "\t\t\t\t\tdst[i] = static_cast<int32_t>(std::clamp(static_cast<double>(tmp[i]) * 2147483647.0,\n"
     "\t\t\t\t\t                                         -2147483648.0, 2147483647.0));\n"
     "\t\t\t\t}\n\t\t\t\tbreak;\n\t\t\t}\n"
     "\t\t\tdefault:\n"
     '\t\t\t\tEXIT("unsupported AJM PCM sample encoding %u\\n", static_cast<uint32_t>(m_sample_encoding));\n'
     "\t\t}\n"
     "\t\treturn (samples > 0 ? 0 : (samples < 0 ? samples : -1));\n\t}\n\n"
     "\tuint64_t CopyDecodedFrame(uint8_t* output, size_t output_size, size_t* output_written,\n"),
    ("\tvoid*                m_handle            = nullptr;\n",
     "\tvoid*                m_handle            = nullptr;\n\tatrac9_handle_t*     m_vib               = nullptr;\n"),
])
