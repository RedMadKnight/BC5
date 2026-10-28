// SPDX-License-Identifier: GPL-2.0-only
// Experiment 0372: where a pad port's frames may go after the controller is unplugged (bc5/pad_audio_route.hpp).
#include "bc5/pad_audio_route.hpp"

#include <catch2/catch_test_macros.hpp>

#include <cstdint>
#include <string>

namespace {

using namespace bc5::pad_audio_route;

// One port's writer as audio.cpp drives it: per call, the decision, then the step carried out.
struct Sim {
    PortState s;
    int       lookups = 0;
    bool      open_ok = true;

    Decision call(DeviceEvents now, std::uint64_t now_ms, bool listed) {
        const Decision d = decide(s, now, now_ms, [&] {
            lookups++;
            return listed;
        });
        s = after(s, d, now, now_ms, open_ok);
        return d;
    }
};

// A port opened on the controller at t = 0 with no events yet.
Sim on_pad_port() {
    Sim p;
    p.s.wants_pad  = true;
    p.s.on_pad     = true;
    p.s.has_device = true;
    return p;
}

TEST_CASE("a port that does not belong on the controller is never touched", "[pad_audio_route]") {
    Sim p;
    p.s.has_device = true;
    for (std::uint32_t k = 0; k < 4; k++) {
        const Decision d = p.call({k, k}, 1000u * k, true);
        CHECK(d.step == Step::Play);
        CHECK_FALSE(d.looked);
    }
    CHECK(p.lookups == 0);
}

TEST_CASE("a stream on the controller plays, and looks only once a second without an event", "[pad_audio_route]") {
    Sim p = on_pad_port();
    p.s.last_look_ms = 0;
    CHECK(p.call({}, 10, true).step == Step::Play);
    CHECK(p.call({}, 999, true).step == Step::Play);
    CHECK(p.lookups == 0);
    const Decision d = p.call({}, 1000, true);
    CHECK(d.step == Step::Play);
    CHECK(d.looked);
    CHECK(p.lookups == 1);
    CHECK(p.call({}, 1500, true).step == Step::Play);
    CHECK(p.lookups == 1);
}

TEST_CASE("unplug: the stream is closed at the removal, the frames dropped, and it reopens when the pad is back",
          "[pad_audio_route]") {
    Sim p = on_pad_port();
    // 23:32:44: the sink is removed; the controller is no longer listed.
    Decision d = p.call({1, 0}, 100, false);
    CHECK(d.step == Step::Close);
    CHECK(d.why == Why::DeviceRemoved);
    CHECK_FALSE(p.s.has_device);
    CHECK(p.s.on_pad);
    CHECK(p.s.retry_armed);
    // Away: frames dropped; one look a second.
    CHECK(p.call({1, 0}, 200, false).step == Step::Drop);
    CHECK(p.call({1, 0}, 1099, false).step == Step::Drop);
    const int before = p.lookups;
    d = p.call({1, 0}, 1100, false);
    CHECK(d.step == Step::Drop);
    CHECK(p.lookups == before + 1);
    // 23:32:49: the sink is added again.
    d = p.call({1, 1}, 1200, true);
    CHECK(d.step == Step::Open);
    CHECK(d.why == Why::DeviceAdded);
    CHECK(p.s.has_device);
    CHECK(p.s.on_pad);
    CHECK_FALSE(p.s.retry_armed);
    CHECK(p.call({1, 1}, 1300, true).step == Step::Play);
}

TEST_CASE("both pad ports leave the controller at a removal, the one SDL stopped and the one it did not",
          "[pad_audio_route]") {
    // SDL 2.33.0 stops only the first open device on a removed node (SDL_audio.c:522-529).
    Sim speaker   = on_pad_port();
    Sim vibration = on_pad_port();
    speaker.s.stopped = true;
    const Decision a  = speaker.call({1, 0}, 100, false);
    const Decision b  = vibration.call({1, 0}, 101, false);
    CHECK(a.step == Step::Close);
    CHECK(b.step == Step::Close);
    CHECK(b.why == Why::DeviceRemoved);
    CHECK_FALSE(speaker.s.has_device);
    CHECK_FALSE(vibration.s.has_device);
}

TEST_CASE("a replug faster than the port's next write reopens the stream at once", "[pad_audio_route]") {
    Sim p = on_pad_port();
    const Decision d = p.call({1, 1}, 100, true);
    CHECK(d.step == Step::Open);
    CHECK(d.why == Why::DeviceRemoved);
    CHECK(p.s.has_device);
    CHECK(p.lookups == 1);
}

TEST_CASE("another sink removed while the pad stays: the pad stream is reopened (the price of not knowing which)",
          "[pad_audio_route]") {
    Sim p = on_pad_port();
    const Decision d = p.call({1, 0}, 100, true);
    CHECK(d.step == Step::Open);
    CHECK(p.s.has_device);
    CHECK(p.call({1, 0}, 200, true).step == Step::Play);
}

TEST_CASE("an added sink does not disturb a stream on the controller", "[pad_audio_route]") {
    Sim p = on_pad_port();
    p.s.last_look_ms = 50;
    const Decision d = p.call({0, 1}, 100, true);
    CHECK(d.step == Step::Play);
    CHECK_FALSE(d.looked);
}

TEST_CASE("SDL stopping the device without an event (F93's path) closes or reopens it", "[pad_audio_route]") {
    Sim p     = on_pad_port();
    p.s.stopped = true;
    Decision d  = p.call({}, 100, false);
    CHECK(d.step == Step::Close);
    CHECK(d.why == Why::DeviceStopped);
    Sim q       = on_pad_port();
    q.s.stopped = true;
    d           = q.call({}, 100, true);
    CHECK(d.step == Step::Open);
    CHECK(d.why == Why::DeviceStopped);
}

TEST_CASE("a missed removal is caught by the once-a-second look", "[pad_audio_route]") {
    Sim p = on_pad_port();
    p.s.last_look_ms = 0;
    CHECK(p.call({}, 500, false).step == Step::Play);
    const Decision d = p.call({}, 1000, false);
    CHECK(d.step == Step::Close);
    CHECK(d.why == Why::NotListed);
}

TEST_CASE("a failed reopen is retried once a second while the pad is listed", "[pad_audio_route]") {
    Sim p = on_pad_port();
    CHECK(p.call({1, 0}, 100, false).step == Step::Close);
    p.open_ok        = false; // e.g. WirePlumber destroyed the stream: its sink was not linkable yet (dont-fallback)
    Decision d       = p.call({1, 1}, 200, true);
    CHECK(d.step == Step::Open);
    CHECK_FALSE(p.s.has_device);
    CHECK(p.s.retry_armed);
    CHECK(p.call({1, 1}, 900, true).step == Step::Drop);
    p.open_ok = true;
    d         = p.call({1, 1}, 1200, true);
    CHECK(d.step == Step::Open);
    CHECK(d.why == Why::Retry);
    CHECK(p.s.has_device);
}

TEST_CASE("a DualShock 4: the vibration port without a device only looks at events, and stays without one",
          "[pad_audio_route]") {
    Sim p;
    p.s.wants_pad = true; // a type-10 port; no controller audio device at the open (F72, F214)
    for (std::uint64_t t = 0; t < 10000; t += 10) {
        CHECK(p.call({}, t, false).step == Step::Drop);
    }
    CHECK(p.lookups == 0);
    // The DualShock 4 unplugged and plugged in again: its own 2-channel sink goes and comes; not the controller's.
    CHECK(p.call({1, 0}, 10000, false).step == Step::Drop);
    CHECK(p.call({1, 1}, 15000, false).step == Step::Drop);
    CHECK(p.lookups == 2);
    CHECK(p.call({1, 1}, 30000, false).step == Step::Drop);
    CHECK(p.lookups == 2);
}

TEST_CASE("a DualShock 4: the pad-speaker port keeps playing on the default sink (F329/F330)", "[pad_audio_route]") {
    Sim p;
    p.s.wants_pad  = true;
    p.s.has_device = true; // on the default sink, non-blocking
    CHECK(p.call({}, 100, false).step == Step::Play);
    CHECK(p.call({1, 0}, 200, false).step == Step::Play);
    CHECK(p.call({1, 1}, 300, false).step == Step::Play);
    CHECK(p.s.has_device);
    CHECK_FALSE(p.s.on_pad);
    CHECK(p.call({1, 1}, 5000, false).step == Step::Play);
    CHECK(p.lookups == 2);
}

TEST_CASE("a DualSense plugged in after the start takes both pad ports over", "[pad_audio_route]") {
    Sim speaker;
    speaker.s.wants_pad  = true;
    speaker.s.has_device = true; // started without a controller device: the default sink
    Sim vibration;
    vibration.s.wants_pad = true; // started without a device
    Decision a = speaker.call({0, 1}, 100, true);
    Decision b = vibration.call({0, 1}, 101, true);
    CHECK(a.step == Step::Open);
    CHECK(b.step == Step::Open);
    CHECK(a.why == Why::DeviceAdded);
    CHECK(speaker.s.on_pad);
    CHECK(vibration.s.on_pad);
    // A failed move keeps the speaker on the default sink, and it tries again a second later.
    Sim late;
    late.s.wants_pad  = true;
    late.s.has_device = true;
    late.open_ok      = false;
    a                 = late.call({0, 1}, 100, true);
    CHECK(a.step == Step::Open);
    CHECK(late.s.has_device);
    CHECK_FALSE(late.s.on_pad);
    CHECK(late.s.retry_armed);
    CHECK(late.call({0, 1}, 500, true).step == Step::Play);
    late.open_ok = true;
    CHECK(late.call({0, 1}, 1100, true).step == Step::Open);
    CHECK(late.s.on_pad);
}

TEST_CASE("the event counters may wrap", "[pad_audio_route]") {
    Sim p      = on_pad_port();
    p.s.seen   = {0xffffffffu, 7};
    const Decision d = p.call({0, 7}, 100, false);
    CHECK(d.step == Step::Close);
    CHECK(d.why == Why::DeviceRemoved);
}

TEST_CASE("the pad streams' PIPEWIRE_PROPS add the two keys to the host's default only", "[pad_audio_route]") {
    CHECK(pad_stream_props(kHostStreamProps) ==
          "{ channelmix.normalize = true node.dont-reconnect = true node.dont-fallback = true }");
    CHECK(pad_stream_props("{ channelmix.normalize = false }").empty());
    CHECK(pad_stream_props("").empty());
    CHECK(pad_stream_props("{ node.latency = 256/48000 }").empty());
}

} // namespace
