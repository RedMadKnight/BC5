// SPDX-License-Identifier: GPL-2.0-only
// BC5 experiment 0439 (tag dm439): the det test of dm0439.hpp against the vendored vgmstream ATRAC9 sources (KytyPlus
// f266548 3rdparty/vgmstream-atrac9, ISC). Built in the ubuntu distrobox (k439/test_dm0439.sh); no game data: the config
// bytes are the 4-byte descriptors recorded in this repository's experiment logs (0241, 0154, 0439 item 43) and AnyPS5's
// test (fe 72 1f f0).
#include "bc5/dm0439.hpp"

#include <cstdio>
#include <cstdlib>
#include <vector>

static int g_fail = 0;
#define CHECK(x)                                                                                                       \
    do {                                                                                                               \
        if (!(x)) {                                                                                                    \
            std::printf("FAIL %s:%d: %s\n", __FILE__, __LINE__, #x);                                                   \
            g_fail++;                                                                                                  \
        }                                                                                                              \
    } while (0)

int main() {
    // 1. this title's 12-channel stream (exp 0439 item 43): profile 7 = 48 kHz, dmc channels 0b001011 + 1 = 12,
    //    frame 63 + 1 = 64 bytes per channel, superframe index 2 = 4 frames of 256 samples
    {
        const std::uint8_t cfg[4] = {0x30, 0x72, 0xc0, 0xfe};
        atrac9_info_t i{};
        CHECK(bc5::dm439::dmc_info(cfg, &i));
        CHECK(i.channels == 12);
        CHECK(i.sample_rate == 48000);
        CHECK(i.frame_samples == 256);
        CHECK(i.frames_per_superframe == 4);
        CHECK(i.superframe_size == 64 * 4 * 12);
        CHECK(i.dmc_mode == 1);
        std::printf("dmc 30 72 c0 fe: %d ch, %d Hz, frame %d samples, %d frames, superframe %d bytes\n", i.channels,
                    i.sample_rate, i.frame_samples, i.frames_per_superframe, i.superframe_size);
        // the decoder vgmstream would make for it decodes a superframe of silence-coded zeros without crashing
        atrac9_handle_t *h = atrac9_init(cfg);
        CHECK(h != nullptr);
        if (h != nullptr) {
            atrac9_info_t hi{};
            CHECK(atrac9_get_info(h, &hi) == 0 && hi.channels == 12 && hi.superframe_size == i.superframe_size);
            atrac9_free(h);
        }
    }
    // 2. standard configs are not DMC (they stay on LibAtrac9's path): exp 0241's three and AnyPS5's stereo
    for (const auto &c : std::vector<std::vector<std::uint8_t>>{
             {0xfe, 0x7e, 0x03, 0xf0}, {0xfe, 0x7c, 0x01, 0xf0}, {0xfe, 0x7a, 0x17, 0xe0}, {0xfe, 0x72, 0x1f, 0xf0}}) {
        atrac9_info_t i{};
        CHECK(!bc5::dm439::dmc_info(c.data(), &i));
    }
    // 3. garbage and a DMC header with the data-version bit set are refused (vgmstream's own checks)
    {
        const std::uint8_t bad[4] = {0x31, 0x72, 0xc0, 0xfe};
        atrac9_info_t i{};
        CHECK(!bc5::dm439::dmc_info(bad, &i));
        const std::uint8_t ver[4] = {0x30, 0x72, 0xe0, 0xfe}; // byte 2 bit 5 = data_version 1
        CHECK(!bc5::dm439::dmc_info(ver, &i));
        CHECK(!bc5::dm439::dmc_info(nullptr, &i));
    }
    std::printf("%s (%d failures)\n", g_fail == 0 ? "PASS" : "FAIL", g_fail);
    return g_fail == 0 ? 0 : 1;
}
