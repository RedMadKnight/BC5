// SPDX-License-Identifier: GPL-2.0-only
// Experiment 0372: where a pad port's frames may go after the DualSense is unplugged and plugged in again.
//
// What went wrong (2026-10-28 23:32, the second title, USB DualSense, the shared normal build): the title's pad-speaker
// port (type 4) and its vibration port (type 10) each open an SDL device on the controller's PipeWire sink. When the
// sink goes away, SDL 2.33.0 (KytyPlus f266548's 3rdparty/SDL2, 4b69833) stops only the FIRST open device on that node
// (SDL_RemoveAudioDevice breaks out of its loop after one: src/audio/SDL_audio.c:522-529), and its PipeWire backend
// reports nothing itself
// (stream_state_changed_callback, src/audio/pipewire/SDL_pipewire.c:1129-1140). The second port's device stays
// "playing"; its stream carries target.object but neither node.dont-reconnect nor node.dont-fallback
// (SDL_pipewire.c:1160, 1243-1272), so WirePlumber 0.5.17 neither destroys it (linking/find-defined-target.lua:116)
// nor keeps it from a new target (linking/prepare-link.lua:71-76): it was linked to the default sink, where the
// haptics were heard. Before exp 0181 SDL's PulseAudio backend opened a named device with PA_STREAM_DONT_MOVE
// (SDL_pulseaudio.c:695-699), which pipewire-pulse turns into PW_STREAM_FLAG_DONT_RECONNECT (PipeWire 1.6.9
// module-protocol-pulse/pulse-server.c, do_create_playback_stream): by today's WirePlumber scripts the second stream
// was then left unlinked, silent rather than on the speakers (not observed), and F94 saw only the pad-speaker port
// reopen after the unplugs of 2026-10-09.
//
// The host now follows the controller's device by SDL's audio device events, counted by an event watch on the thread
// that pushes them (SDL_PushEvent calls the watches first, src/events/SDL_events.c:1156-1176), and decides here, per
// port and per call on the thread that writes the port, what to do with its device. This header holds that decision
// and the PIPEWIRE_PROPS value for a pad stream, so they can be unit-tested; the host side lives in KytyPlus
// src/libs/audio.cpp (Audio::PadRouteStep).
#pragma once

#include <cstdint>
#include <string>
#include <string_view>

namespace bc5::pad_audio_route {

// How often a port that is on the controller, or waiting for it, looks at the device list without an event.
inline constexpr std::uint64_t kLookPeriodMs = 1000;

// SDL_AUDIODEVICEREMOVED / SDL_AUDIODEVICEADDED of output devices since the start (wrapping counters).
struct DeviceEvents {
    std::uint32_t removed = 0;
    std::uint32_t added   = 0;
};

// What the port's writer does before queueing its frames.
enum class Step : std::uint8_t {
    Play,  // keep the device the port has (on the controller, or on the default sink) and queue on it
    Drop,  // the port has no device now: its frames are dropped
    Close, // close the port's device (its controller device has gone) and drop the frames
    Open,  // open the port on the controller's device; a device still on the controller is closed first, one on
           // the default sink only after the new one is open
};

enum class Why : std::uint8_t {
    None,
    DeviceRemoved, // an output device was removed since the port last looked
    DeviceStopped, // SDL stopped the port's device (the first device on a removed node, F93)
    NotListed,     // the once-a-second look did not find the controller's device (an event missed)
    DeviceAdded,   // an output device was added since the port last looked
    Retry,         // the once-a-second retry after a failed open, or while the controller is away
};

struct PortState {
    bool          wants_pad   = false; // the port belongs on the controller (type 4 unless =main, type 10)
    bool          on_pad      = false; // its stream is laid out for the controller (6 channels, pad_route != 0)
    bool          has_device  = false; // an SDL device is open for it
    bool          stopped     = false; // SDL reports that device stopped
    bool          retry_armed = false; // look once a second without an event
    DeviceEvents  seen {};             // the events the port has acted on
    std::uint64_t last_look_ms = 0;    // when it last looked at the device list
};

struct Decision {
    Step step   = Step::Play;
    Why  why    = Why::None;
    bool looked = false; // `present` was called
};

// The decision for one call. `present()` looks for the controller's device in SDL's list (and keeps its name); it is
// called at most once, and only when the port has to look.
//
// A port whose stream is on the controller never keeps it after a removal: SDL cannot say which node went, and a
// stream whose node went may already be on the default sink. If the controller is listed again (a replug faster than
// the port's next write, or the removed device was another sink), the port is reopened at once, at the cost of one
// close and open; otherwise it is closed and its frames are dropped. A port without a stream on the controller looks
// at every device event, and once a second when it is armed; with no controller listed, a port on the default sink
// (a DualShock 4's pad speaker, F329/F330) keeps playing there and a port without a device drops its frames.
template <class Present>
Decision decide(const PortState& p, DeviceEvents now, std::uint64_t now_ms, Present&& present) {
    Decision d;
    if (!p.wants_pad) {
        return d;
    }
    const bool removed = now.removed != p.seen.removed;
    const bool added   = now.added != p.seen.added;
    const bool due     = now_ms - p.last_look_ms >= kLookPeriodMs;
    if (p.on_pad && p.has_device) {
        if (removed || p.stopped) {
            d.why    = removed ? Why::DeviceRemoved : Why::DeviceStopped;
            d.looked = true;
            d.step   = present() ? Step::Open : Step::Close;
            return d;
        }
        if (due) {
            d.looked = true;
            if (!present()) {
                d.step = Step::Close;
                d.why  = Why::NotListed;
            }
        }
        return d;
    }
    if (removed || added || (p.retry_armed && due)) {
        d.looked = true;
        if (present()) {
            d.step = Step::Open;
            d.why  = removed ? Why::DeviceRemoved : added ? Why::DeviceAdded : Why::Retry;
            return d;
        }
    }
    d.step = p.has_device ? Step::Play : Step::Drop;
    return d;
}

// The port after the step was carried out (`open_ok`: the open of Step::Open succeeded).
inline PortState after(const PortState& p, const Decision& d, DeviceEvents now, std::uint64_t now_ms, bool open_ok) {
    PortState n = p;
    n.seen      = now;
    if (d.looked) {
        n.last_look_ms = now_ms;
    }
    switch (d.step) {
    case Step::Play:
    case Step::Drop:
        // A port that was never on the controller stops polling once a look found nothing; one that was on it
        // keeps looking once a second until it is back (F93).
        if (d.looked && !p.on_pad) {
            n.retry_armed = false;
        }
        break;
    case Step::Close:
        n.has_device  = false;
        n.stopped     = false;
        n.retry_armed = true;
        break;
    case Step::Open:
        if (open_ok) {
            n.on_pad      = true;
            n.has_device  = true;
            n.stopped     = false;
            n.retry_armed = false;
        } else {
            // A stream on the controller was closed before the open; one on the default sink is kept.
            n.has_device  = !p.on_pad && p.has_device;
            n.stopped     = false;
            n.retry_armed = true;
        }
        break;
    }
    return n;
}

// The host's PIPEWIRE_PROPS default (exp 0181: PipeWire's downmix normalized so that it cannot clip).
inline constexpr char kHostStreamProps[] = "{ channelmix.normalize = true }";
// What a stream on the controller adds: never moved to another sink when its target goes, never linked to the default
// sink when its target is not found (pipewire-props(7), PipeWire 1.6.9: node.dont-reconnect, node.dont-fallback;
// WirePlumber 0.5.17 linking/prepare-link.lua:71-76 and find-defined-target.lua:116-123, which destroys such a stream,
// node.linger unset). dont-fallback matters most: with dont-reconnect alone, a reopen that reaches WirePlumber before
// the returning sink is linkable would be linked to the default sink and then kept there (prepare-link.lua:63-67);
// with dont-fallback it fails, and the port retries a second later.
inline constexpr std::string_view kPadStreamKeys = "node.dont-reconnect = true node.dont-fallback = true";

// The PIPEWIRE_PROPS value for a stream opened on the controller: the host's default with kPadStreamKeys added, or
// empty when `current` is not the host's default (a value the user set is left as it is).
inline std::string pad_stream_props(std::string_view current) {
    const std::string_view host(kHostStreamProps);
    if (current != host) {
        return {};
    }
    std::string out(host.substr(0, host.rfind('}')));
    out += kPadStreamKeys;
    out += " }";
    return out;
}

} // namespace bc5::pad_audio_route
