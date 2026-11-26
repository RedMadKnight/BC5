// SPDX-License-Identifier: GPL-2.0-only
// BC5 experiment 0439 (tag dm439): ATRAC9 "DMC" (multichannel) configurations, which LibAtrac9 does not know.
// The third title's Scream engine asks sceAjmDecAt9ParseConfigData about a 12-channel stream whose 4 config bytes are
// 30 72 c0 fe (README items 42-44). Our parser called LibAtrac9 only, which wants the sync byte 0xFE and refused; the title
// then divided by the grain the parse would have given (SIGFPE at eboot+0x3502d2).
//
// Source: vgmstream's ATRAC9 decoder as vendored in KytyPlus f266548 (3rdparty/vgmstream-atrac9, ISC),
// src/coding/libs/atrac9_dec.c parse_config_data: sync 0xFE = the standard config; sync 0x30 = "DMC header config":
// profile 4 bits, dmc_channels 6 bits + 1, data_version 1 bit, frame_size 11 bits + 1, superframe_index 2 bits; atrac9_init
// sets one mono stream per DMC channel, and atrac9_get_config_info reports channels = dmc_channels and superframe_size =
// frame_size x frames x dmc_channels.
//
// Tested by test_dm0439.cpp against the vendored C sources. BC5_DM439_PLANT: the old behaviour (no DMC), must FAIL.
#pragma once

#include <cstdint>

extern "C" {
#include "atrac9_dec.h"
}

namespace bc5::dm439 {

inline constexpr std::uint8_t kDmcSync = 0x30;

// True for a DMC config that vgmstream describes completely; *out holds its description.
inline bool dmc_info(const void *config, atrac9_info_t *out) {
#if defined(BC5_DM439_PLANT)
    (void)config;
    (void)out;
    return false;
#else
    const auto *c = static_cast<const std::uint8_t *>(config);
    if (c == nullptr || out == nullptr || c[0] != kDmcSync) return false;
    *out = atrac9_info_t{};
    if (atrac9_get_config_info(c, out) != 0) return false;
    return out->dmc_mode != 0 && out->channels > 0 && out->sample_rate > 0 && out->frame_samples > 0 &&
           out->frames_per_superframe > 0 && out->superframe_size > 0;
#endif
}

} // namespace bc5::dm439
