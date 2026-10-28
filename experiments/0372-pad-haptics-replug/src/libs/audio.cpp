#include "libs/audio.h"

#include "SDL.h"
#include "bc5/pad_audio_route.hpp" // BC5 (experiment 0372)
#include "common/assert.h"
#include "common/common.h"
#include "common/logging/log.h"
#include "common/magicEnum.h"
#include "common/stringUtils.h"
#include "common/threads.h"
#include "kernel/pthread.h"
#include "kernel/semaphore.h"
#include "libs/audio_internal.h"
#include "libs/controller.h"
#include "libs/errno.h"
#include "libs/libs.h"

#include <algorithm>
#include <array>
#include <atomic>
#include <cinttypes>
#include <cstdlib>
#include <cstring>
#include <limits>
#include <string>
#include <vector>
#include <cstdio>
#include <mutex>
#include <map>
#include <cmath>
#if KYTY_PLATFORM == KYTY_PLATFORM_LINUX
#include <dirent.h> // BC5 (experiment 0180): Bc5RaiseAudioClientThreads
#include <cerrno>
#include <sys/resource.h>
#endif

namespace Libs::Audio {

namespace {

constexpr int AUDIO_OUT_PORT_TYPE_MAIN      = 0;
constexpr int AUDIO_OUT_PORT_TYPE_BGM       = 1;
constexpr int AUDIO_OUT_PORT_TYPE_VOICE     = 2;
constexpr int AUDIO_OUT_PORT_TYPE_PERSONAL  = 3;
constexpr int AUDIO_OUT_PORT_TYPE_PADSPK    = 4;
constexpr int AUDIO_OUT_PORT_TYPE_VIBRATION = 10;
constexpr int AUDIO_OUT_PORT_TYPE_AUDIO3D   = 126;
constexpr int AUDIO_OUT_PORT_TYPE_AUX       = 127;

constexpr uint32_t AUDIO_OUT_PARAM_FORMAT_MASK = 0x000000ffu;

static bool audio_out_port_type_is_valid(int type) {
	return (type >= AUDIO_OUT_PORT_TYPE_MAIN && type <= AUDIO_OUT_PORT_TYPE_PADSPK) ||
	       type == AUDIO_OUT_PORT_TYPE_VIBRATION || type == AUDIO_OUT_PORT_TYPE_AUDIO3D ||
	       type == AUDIO_OUT_PORT_TYPE_AUX;
}

} // namespace

class Audio {
public:
	using Format = AudioInternal::Format;

	class Id {
	public:
		explicit Id(int id): m_id(id - 1) {}
		[[nodiscard]] int  ToInt() const { return m_id + 1; }
		[[nodiscard]] bool IsValid() const { return m_id >= 0; }

		friend class Audio;

	private:
		Id() = default;
		static Id Invalid() { return {}; }
		static Id Create(int audio_id) {
			Id r;
			r.m_id = audio_id;
			return r;
		}
		[[nodiscard]] int GetId() const { return m_id; }

		int m_id = -1;
	};

	struct OutputParam {
		Id          handle;
		const void* data = nullptr;
	};

	Audio() = default;
	virtual ~Audio();

	KYTY_CLASS_NO_COPY(Audio);

	Id       AudioOutOpen(int type, uint32_t samples_num, uint32_t freq, Format format);
	bool     AudioOutClose(Id handle);
	bool     AudioOutValid(Id handle);
	bool     AudioOutHasDevice(Id handle);
	uint32_t AudioOutQueuedFrames(Id handle); // BC5 (experiment 0188)
	bool     AudioOutSetVolume(Id handle, uint32_t bitflag, const int* volume);
	uint32_t AudioOutOutputs(OutputParam* params, uint32_t num, bool blocking = true);
	bool     AudioOutGetStatus(Id handle, int* type, int* channels_num);

	Id       AudioInOpen(uint32_t type, uint32_t samples_num, uint32_t freq, Format format);
	bool     AudioInValid(Id handle);
	uint32_t AudioInInput(Id handle, void* dest);

	static constexpr int OUT_PORTS_MAX = 32;
	static constexpr int IN_PORTS_MAX  = 8;

private:
	struct PortOut {
		bool     used             = false;
		int      type             = 0;
		uint32_t samples_num      = 0;
		uint32_t freq             = 0;
		Format   format           = Format::Unknown;
		uint64_t last_output_time = 0;
		int      channels_num     = 0;
		int      volume[8]        = {};

		SDL_AudioDeviceID audio_device = 0;
		SDL_AudioSpec     audio_spec   = {};
		// BC5: 0 = the host's default output; 1 = the controller's speaker (its channels 1-2);
		// 2 = the controller's haptic actuators (its channels 3-4). The DualSense is a 4-channel
		// USB audio device, and the game's vibration is an audio stream to those actuators.
		int pad_route = 0;
		// BC5 (experiment 0267, after exp 0268): a pad-speaker port on the default sink, because the pad has
		// no audio device (a DualShock 4), queues without ever holding the title's audio thread, like the
		// pad-routed ports; exp 0268 saw that wait cost the main mix 0.36 s at t 149-150 s of the 16:05 play.
		bool pad_nb = false;
		// BC5: when the port last looked for the controller's device (ms), see PadRouteStep.
		uint64_t pad_retry_ms = 0;
		// BC5 (experiment 0372): the port belongs on the controller (a pad-speaker port unless
		// KYTY_BC5_PAD_SPEAKER=main, a vibration port; KYTY_BC5_NO_PAD_AUDIO unset), whether or not the
		// controller's device is there now; the SDL audio device events it has acted on; whether it looks
		// once a second without one; its failed opens in a row (the log line is rate-limited).
		bool                               pad_want        = false;
		bc5::pad_audio_route::DeviceEvents pad_seen        = {};
		bool                               pad_retry_armed = false;
		uint32_t                           pad_open_fails  = 0;
		// BC5 (audio pacing, KYTY_BC5_AUDIO_TRACE=1): what the port did since the last trace line.
		uint32_t tr_calls = 0, tr_frames = 0, tr_clears = 0;
		uint64_t tr_blocked_us = 0;
		uint32_t tr_queued_min = 0xffffffffu, tr_queued_max = 0;
		uint32_t tr_queued_bytes_per_ms = 0;
		// BC5 (experiment 0372, KYTY_BC5_AUDIO_TRACE=1): calls whose frames were dropped while the controller was away.
		uint32_t tr_pad_dropped = 0;
	};

	// BC5: the channel count of the stream opened on the controller's audio device. The device
	// has four channels (speaker 1-2, actuators 3-4), but SDL's pulseaudio backend declares a
	// 4-channel stream as FL FR FC LFE (the WAVEEX order), and PipeWire then mixes channel 3 into
	// the speaker and drops channel 4: the actuators get nothing (the emulator runs in a container
	// whose SDL has only that backend). A 6-channel stream is declared FL FR FC LFE RL RR, and its
	// channels 5-6 reach the device's 3-4 unchanged, with SDL's pipewire backend too. The speaker
	// pair is channels 1-2 either way; the actuators are the last pair (F80).
	static constexpr uint32_t PAD_STREAM_CHANNELS = 6;

	struct PortIn {
		bool     used            = false;
		uint32_t type            = 0;
		uint32_t samples_num     = 0;
		uint32_t freq            = 0;
		Format   format          = Format::Unknown;
		uint64_t last_input_time = 0;
	};

	Common::Mutex m_mutex;
	PortOut       m_out_ports[OUT_PORTS_MAX];
	PortIn        m_in_ports[IN_PORTS_MAX];

	static bool            FormatIsFloat(Format format);
	static bool            FormatIsStd(Format format);
	static uint32_t        BytesPerSample(Format format);
	static uint32_t        FrameSize(const PortOut& port);
	static SDL_AudioFormat SdlFormat(Format format);
	static bool            OpenSdlDevice(PortOut* port);
	static void            CloseSdlDevice(PortOut* port);
	static const void*     PrepareOutputBuffer(const PortOut& port, const void* data,
	                                           std::vector<uint8_t>* buffer);
	static bool            QueueSdlAudio(PortOut* port, const void* data, bool blocking);
	static void            PadRumbleFromVibrationFrames(const PortOut& port, const void* data);
	// BC5 (experiment 0372): a pad port following the controller's audio device.
	static void            PadRouteStep(PortOut* port);
	static void            PadCloseDevice(PortOut* port);
	static bool            PadOpenDevice(PortOut* port, const std::string& name, const char* why);
	static int             PortId(const PortOut* port);
};

static Audio* g_audio = nullptr;

namespace AudioInternal {

int AudioOutOpen(int type, uint32_t samples_num, uint32_t freq, Format format) {
	if (g_audio == nullptr) {
		return 0;
	}

	auto id = g_audio->AudioOutOpen(type, samples_num, freq, format);
	return id.IsValid() ? id.ToInt() : 0;
}

void AudioOutClose(int handle) {
	if (g_audio != nullptr && handle > 0) {
		(void)g_audio->AudioOutClose(Audio::Id(handle));
	}
}

bool AudioOutHasDevice(int handle) {
	return g_audio != nullptr && handle > 0 && g_audio->AudioOutHasDevice(Audio::Id(handle));
}

uint32_t AudioOutQueuedFrames(int handle) { // BC5 (experiment 0188)
	return g_audio != nullptr && handle > 0 ? g_audio->AudioOutQueuedFrames(Audio::Id(handle)) : 0;
}

uint32_t AudioOutOutputs(const OutputParam* params, uint32_t num, bool blocking) {
	if (g_audio == nullptr || params == nullptr || num == 0) {
		return 0;
	}

	std::vector<Audio::OutputParam> output_params;
	output_params.reserve(num);
	for (uint32_t i = 0; i < num; i++) {
		if (params[i].handle > 0 && params[i].data != nullptr) {
			output_params.push_back(
			    Audio::OutputParam {Audio::Id(params[i].handle), params[i].data});
		}
	}

	if (output_params.empty()) {
		return 0;
	}

	return g_audio->AudioOutOutputs(output_params.data(),
	                                static_cast<uint32_t>(output_params.size()), blocking);
}

} // namespace AudioInternal

KYTY_SUBSYSTEM_INIT(Audio) {
	EXIT_IF(g_audio != nullptr);

	g_audio = new Audio;
}

KYTY_SUBSYSTEM_UNEXPECTED_SHUTDOWN(Audio) {}

KYTY_SUBSYSTEM_DESTROY(Audio) {
	delete g_audio;
	g_audio = nullptr;
}

Audio::~Audio() {
	for (auto& port: m_out_ports) {
		CloseSdlDevice(&port);
	}
}

bool Audio::FormatIsFloat(Format format) {
	return (format == Format::FloatMono || format == Format::FloatStereo ||
	        format == Format::Float8Ch || format == Format::Float8ChStd);
}

bool Audio::FormatIsStd(Format format) {
	return (format == Format::Signed16bit8ChStd || format == Format::Float8ChStd);
}

uint32_t Audio::BytesPerSample(Format format) {
	return FormatIsFloat(format) ? sizeof(float) : sizeof(int16_t);
}

uint32_t Audio::FrameSize(const PortOut& port) {
	return BytesPerSample(port.format) * port.channels_num;
}

SDL_AudioFormat Audio::SdlFormat(Format format) {
	return FormatIsFloat(format) ? AUDIO_F32SYS : AUDIO_S16SYS;
}

// BC5 (experiment 0372): the controller's audio device going away and coming back, seen independently of
// SDL_GetAudioDeviceStatus. SDL 2.33.0 stops only the first open device on a removed node
// (3rdparty/SDL2/src/audio/SDL_audio.c:522-529) and its PipeWire backend never stops one by itself
// (src/audio/pipewire/SDL_pipewire.c:1129-1140): with the pad-speaker and the vibration port both on the
// DualSense, the second stayed "playing" after the unplug of 2026-10-28 23:32:44, F93's reopen never ran for
// it, and PipeWire linked its stream to the default sink (the dock's speakers). SDL pushes
// SDL_AUDIODEVICEREMOVED and SDL_AUDIODEVICEADDED for every output device that goes or comes
// (SDL_audio.c:450-464, 510-551; from the PipeWire registry, SDL_pipewire.c:298-341), and SDL_PushEvent hands
// each event to the event watches on the thread that pushes it, before it is queued
// (src/events/SDL_events.c:1156-1176): SDL's hotplug thread, which nothing of ours waits on. The watch only
// counts; each pad port compares the counts with what it last acted on, on the thread that writes the port
// (Audio::PadRouteStep). Chosen over a once-a-second look at the device list, which cannot see an unplug and
// replug that both fall between two looks (the old stream is then on another sink while the name is listed
// again); that look stays as the backstop for a missed event. The events also reach the window's queue as
// before (window.cpp ProcessEvent ignores them).
static std::atomic<uint32_t> g_bc5_audio_removed {0};
static std::atomic<uint32_t> g_bc5_audio_added {0};

static int SDLCALL Bc5AudioDeviceWatch(void* /*userdata*/, SDL_Event* event) {
	if (event != nullptr && (event->type == SDL_AUDIODEVICEREMOVED || event->type == SDL_AUDIODEVICEADDED) &&
	    event->adevice.iscapture == 0) {
		auto& count = event->type == SDL_AUDIODEVICEREMOVED ? g_bc5_audio_removed : g_bc5_audio_added;
		count.fetch_add(1, std::memory_order_acq_rel);
	}
	return 1; // what a watch returns is ignored (SDL_PushEvent)
}

static bc5::pad_audio_route::DeviceEvents Bc5AudioDeviceEvents() {
	return {g_bc5_audio_removed.load(std::memory_order_acquire), g_bc5_audio_added.load(std::memory_order_acquire)};
}

// BC5 (experiment 0372): every SDL_OpenAudioDevice of this file runs under this lock. A stream opened on the
// controller gets node.dont-reconnect and node.dont-fallback through PIPEWIRE_PROPS, which libpipewire reads in
// pw_stream_connect (PipeWire 1.6.2 src/pipewire/stream.c; SDL calls it inside the open, SDL_pipewire.c:1281);
// the lock keeps that value from ever reaching the main mix's stream. With them, WirePlumber 0.5.17 never links a
// pad stream to another sink: a stream whose target is gone or not found is destroyed
// (/usr/share/wireplumber/scripts/linking/find-defined-target.lua:116-123, node.linger unset) and one already
// linked is not moved (prepare-link.lua:63-76); without them the stream of 23:32:44 went to the default sink
// (pipewire-props(7): "destroy the node as well ... inhibits that the node is moved"). PIPEWIRE_PROPS exists
// from the first open on (exp 0181, below), so the swap replaces one pointer in the environment and frees
// nothing (glibc stdlib/setenv.c __add_to_environ keeps every string in its known_values tree): safe against
// getenv on other threads. KYTY_BC5_PAD_PW_PROPS=0 opens pad streams without them (the A/B arm); a PIPEWIRE_PROPS
// set by the user is left as it is (bc5::pad_audio_route::pad_stream_props); with SDL's PulseAudio backend
// nothing is set (it has PA_STREAM_DONT_MOVE of its own, SDL_pulseaudio.c:695-699).
static std::mutex g_bc5_sdl_open_mutex;

static SDL_AudioDeviceID Bc5OpenSdlAudioDevice(const char* name, const SDL_AudioSpec* desired, SDL_AudioSpec* obtained,
                                               int allowed_changes, bool pad, bool* pad_props) {
	static const bool props_on = [] {
		const char* e = std::getenv("KYTY_BC5_PAD_PW_PROPS");
		return e == nullptr || std::strcmp(e, "0") != 0;
	}();
	std::lock_guard<std::mutex> lock(g_bc5_sdl_open_mutex);
	std::string                 props;
	if (pad && props_on) {
		const char* driver = SDL_GetCurrentAudioDriver();
		const char* now    = std::getenv("PIPEWIRE_PROPS");
		if (driver != nullptr && std::strcmp(driver, "pipewire") == 0 && now != nullptr) {
			props = bc5::pad_audio_route::pad_stream_props(now);
		}
	}
	if (!props.empty()) {
		setenv("PIPEWIRE_PROPS", props.c_str(), 1);
	}
	const SDL_AudioDeviceID dev = SDL_OpenAudioDevice(name, 0, desired, obtained, allowed_changes);
	if (!props.empty()) {
		setenv("PIPEWIRE_PROPS", bc5::pad_audio_route::kHostStreamProps, 1);
	}
	if (pad_props != nullptr) {
		*pad_props = !props.empty();
	}
	return dev;
}

// BC5 (haptics, F69): the controller's own audio output, or an empty name. The first SDL output device
// whose name contains KYTY_BC5_PAD_AUDIO_DEVICE (default "DualSense"). With the default, a device
// named "Wireless Controller" is accepted too when it has the DualSense's four channels: on Linux
// (PipeWire/ALSA) the controller's USB audio device carries Sony's USB product string instead of
// "DualSense" (ported from KytyPlus c885da0a "haptics: recognize 'Wireless Controller' audio
// endpoint on Linux", src/libs/dualSenseHaptics.cpp, GPL-2.0; the channel check is theirs too).
// BC5 (experiment 0372): the name is copied, since SDL frees a removed device's entry at the next
// SDL_GetNumAudioDevices on any thread (SDL_audio.c clean_out_device_list).
static std::string Bc5FindPadAudioDevice() {
	const char* env  = std::getenv("KYTY_BC5_PAD_AUDIO_DEVICE");
	const char* want = env != nullptr ? env : "DualSense";
	const int   n    = SDL_GetNumAudioDevices(0);
	for (int i = 0; i < n; i++) {
		const char* name = SDL_GetAudioDeviceName(i, 0);
		if (name == nullptr) {
			continue;
		}
		if (std::strstr(name, want) != nullptr) {
			return name;
		}
#if SDL_VERSION_ATLEAST(2, 0, 16)
		if (env == nullptr && std::strstr(name, "Wireless Controller") != nullptr) {
			SDL_AudioSpec spec {};
			// The device itself has four channels (F69); PAD_STREAM_CHANNELS is what we open on it.
			if (SDL_GetAudioDeviceSpec(i, 0, &spec) == 0 && spec.channels == 4) {
				return name;
			}
		}
#endif
	}
	return {};
}

bool Audio::OpenSdlDevice(PortOut* port) {
	EXIT_IF(port == nullptr);

	// BC5 (experiment 0181): SDL's own PipeWire backend first. Through its PulseAudio backend the
	// sound went SDL -> libpulse ("PulseMainloop") -> pipewire-pulse -> PipeWire; the native backend
	// is one client stream with PipeWire's real-time data thread in this process. SDL tries
	// PulseAudio first unless told otherwise; SDL_AUDIODRIVER set by the user still wins.
	if (std::getenv("SDL_AUDIODRIVER") == nullptr && SDL_GetHint(SDL_HINT_AUDIODRIVER) == nullptr) {
		SDL_SetHint(SDL_HINT_AUDIODRIVER, "pipewire,pulseaudio,alsa");
	}
	// Experiment 0181: PipeWire mixes the title's 7.1 down to the device's channels in this
	// process; by default it sums the channels, and the second title's loud scenes clipped on a
	// stereo headset (1116 samples at full scale in the night part of the opening: crackle).
	// channelmix.normalize scales the mix so that it cannot clip (0 clipped samples, peaks at half
	// scale). PIPEWIRE_PROPS set by the user still wins.
	{
		static std::once_flag once;
		std::call_once(once, [] {
			if (std::getenv("PIPEWIRE_PROPS") == nullptr) {
				// "{ channelmix.normalize = true }"; experiment 0372 adds two keys to it for the pad streams only.
				setenv("PIPEWIRE_PROPS", bc5::pad_audio_route::kHostStreamProps, 0);
			}
		});
	}
	if (SDL_InitSubSystem(SDL_INIT_AUDIO) < 0) {
		LOGF("AudioOut: SDL audio init failed: %s\n", SDL_GetError());
		return false;
	}
	{
		static std::atomic<bool> told {false};
		if (!told.exchange(true)) {
			const char* d = SDL_GetCurrentAudioDriver();
			std::fprintf(stderr, "AudioOut: SDL audio driver %s\n", d != nullptr ? d : "?");
		}
	}
	// BC5 (experiment 0372): count SDL's audio device events from now on (Bc5AudioDeviceWatch). Audio implies
	// SDL's events subsystem (3rdparty/SDL2/src/SDL.c:289-296), whose lock the watch list uses.
	{
		static std::once_flag watch_once;
		std::call_once(watch_once, [] {
			SDL_AddEventWatch(Bc5AudioDeviceWatch, nullptr);
			std::fprintf(stderr, "AudioOut (exp 0372): the controller's ports follow SDL's audio device events\n");
		});
	}

	SDL_AudioSpec desired {};
	desired.freq     = static_cast<int>(port->freq);
	desired.format   = SdlFormat(port->format);
	desired.channels = static_cast<Uint8>(port->channels_num);
	desired.samples  = static_cast<Uint16>(port->samples_num);
	desired.callback = nullptr;

	// BC5 (haptics): a pad-speaker or vibration port goes to the controller's own audio device
	// when one is present — the first output device whose name has KYTY_BC5_PAD_AUDIO_DEVICE
	// (default "DualSense") in it — opened with its four channels; the port's samples are placed
	// on channels 1-2 (speaker) or 3-4 (actuators) when queued. KYTY_BC5_NO_PAD_AUDIO=1 leaves the
	// old behaviour: the speaker port on the default device, the vibration port unopened.
	std::string pad_name;
	port->pad_route      = 0;
	// KYTY_BC5_PAD_SPEAKER=main: the pad-speaker ports stay on the default output (the game sends
	// some effects to the controller's speaker, as on the console); the haptics still go to the pad.
	// KYTY_BC5_PAD_SPEAKER=off (experiment 0267): a pad-speaker port with no controller audio device
	// stays silent instead of playing on the default output (a DualShock 4 has no such device, and
	// the maintainer heard the pad's effects from the TV after a replug).
	static const bool speaker_on_main = [] {
		const char* e = std::getenv("KYTY_BC5_PAD_SPEAKER");
		return e != nullptr && std::strcmp(e, "main") == 0;
	}();
	static const bool speaker_off = [] {
		const char* e = std::getenv("KYTY_BC5_PAD_SPEAKER");
		return e != nullptr && std::strcmp(e, "off") == 0;
	}();
	// KYTY_BC5_PAD_SPEAKER=main-blocking: the pad-speaker port on the default sink as a blocking port, as
	// before experiment 0267 (the A/B arm of exp 0268's hold).
	static const bool speaker_blocking = [] {
		const char* e = std::getenv("KYTY_BC5_PAD_SPEAKER");
		return e != nullptr && std::strcmp(e, "main-blocking") == 0;
	}();
	// BC5 (experiment 0372): whether the port belongs on the controller, whatever is plugged in now; the device
	// events are read before the look, so that one arriving during it is acted on at the port's next write.
	port->pad_want = std::getenv("KYTY_BC5_NO_PAD_AUDIO") == nullptr &&
	                 ((port->type == AUDIO_OUT_PORT_TYPE_PADSPK && !speaker_on_main) || port->type == AUDIO_OUT_PORT_TYPE_VIBRATION);
	port->pad_seen        = Bc5AudioDeviceEvents();
	port->pad_retry_ms    = LibKernel::KernelGetProcessTime() / 1000;
	port->pad_retry_armed = false;
	port->pad_open_fails  = 0;
	if (port->pad_want) {
		pad_name = Bc5FindPadAudioDevice();
		if (!pad_name.empty()) {
			desired.channels = PAD_STREAM_CHANNELS;
			port->pad_route  = port->type == AUDIO_OUT_PORT_TYPE_VIBRATION ? 2 : 1;
		} else if (port->type == AUDIO_OUT_PORT_TYPE_PADSPK && speaker_off) {
			LOGF("AudioOut: no controller audio device for the pad speaker port; KYTY_BC5_PAD_SPEAKER=off keeps it silent\n");
			return false;
		} else if (port->type == AUDIO_OUT_PORT_TYPE_VIBRATION) {
			LOGF("AudioOut: no controller audio device for the vibration port; it stays silent\n");
			return false;
		}
	}

	SDL_AudioSpec obtained {};
	const bool    on_pad    = !pad_name.empty();
	bool          pad_props = false;

	// BC5 (experiment 0372): through Bc5OpenSdlAudioDevice (one open at a time; a pad stream gets
	// node.dont-reconnect and node.dont-fallback).
	port->audio_device = Bc5OpenSdlAudioDevice(on_pad ? pad_name.c_str() : nullptr, &desired, &obtained,
	                                           on_pad ? (SDL_AUDIO_ALLOW_FREQUENCY_CHANGE | SDL_AUDIO_ALLOW_FORMAT_CHANGE) : SDL_AUDIO_ALLOW_ANY_CHANGE,
	                                           on_pad, &pad_props);
	if (port->audio_device == 0) {
		LOGF("AudioOut: SDL_OpenAudioDevice failed: %s\n", SDL_GetError());
		// BC5 (experiment 0372): a port that found the controller but could not open on it tries again once a
		// second (PadRouteStep).
		port->pad_retry_armed = on_pad;
		port->pad_route       = 0;
		return false;
	}

	port->audio_spec = obtained;
	SDL_PauseAudioDevice(port->audio_device, 0);
	port->pad_nb = port->type == AUDIO_OUT_PORT_TYPE_PADSPK && !on_pad && !speaker_blocking;

	LOGF("AudioOut: opened SDL device (%d Hz, %u ch, format 0x%04x) for port type %d, %d ch%s%s%s\n", obtained.freq,
	     obtained.channels, obtained.format, port->type, port->channels_num, on_pad ? " on " : "", pad_name.c_str(),
	     pad_props ? " (node.dont-reconnect, node.dont-fallback)" : "");
	if (on_pad) { // BC5 (experiment 0372): the start of the port's route, beside the trace (rare: one line per open)
		std::fprintf(stderr, "AudioOut (exp 0372): t %.3f s port %d type %d: opened on %s (%d Hz, %d ch)%s\n",
		             static_cast<double>(LibKernel::KernelGetProcessTime()) / 1e6, PortId(port), port->type, pad_name.c_str(),
		             obtained.freq, static_cast<int>(obtained.channels), pad_props ? "; node.dont-reconnect, node.dont-fallback" : "");
	}
	return true;
}

void Audio::CloseSdlDevice(PortOut* port) {
	EXIT_IF(port == nullptr);

	if (port->audio_device != 0 && SDL_WasInit(SDL_INIT_AUDIO) != 0) {
		SDL_ClearQueuedAudio(port->audio_device);
		SDL_CloseAudioDevice(port->audio_device);
	}

	port->audio_device = 0;
	port->audio_spec   = {};
}

const void* Audio::PrepareOutputBuffer(const PortOut& port, const void* data,
                                       std::vector<uint8_t>* buffer) {
	EXIT_IF(data == nullptr);
	EXIT_IF(buffer == nullptr);

	const auto frames           = port.samples_num;
	const auto channels         = static_cast<uint32_t>(port.channels_num);
	const auto bytes_per_sample = BytesPerSample(port.format);
	const auto src_size         = frames * channels * bytes_per_sample;

	bool volume_changed = false;
	for (uint32_t ch = 0; ch < channels; ch++) {
		if (port.volume[ch] != 32768) {
			volume_changed = true;
			break;
		}
	}

	if (!volume_changed && !FormatIsStd(port.format)) {
		return data;
	}

	buffer->resize(src_size);

	static constexpr uint32_t STD_8CH_MAP[8] = {0, 1, 2, 3, 6, 7, 4, 5};

	if (FormatIsFloat(port.format)) {
		auto*       dst = reinterpret_cast<float*>(buffer->data());
		const auto* src = static_cast<const float*>(data);

		for (uint32_t frame = 0; frame < frames; frame++) {
			for (uint32_t ch = 0; ch < channels; ch++) {
				const auto src_ch =
				    (FormatIsStd(port.format) && channels == 8 ? STD_8CH_MAP[ch] : ch);
				dst[frame * channels + ch] = src[frame * channels + src_ch] *
				                             (static_cast<float>(port.volume[ch]) / 32768.0f);
			}
		}
	} else {
		auto*       dst = reinterpret_cast<int16_t*>(buffer->data());
		const auto* src = static_cast<const int16_t*>(data);

		for (uint32_t frame = 0; frame < frames; frame++) {
			for (uint32_t ch = 0; ch < channels; ch++) {
				const auto src_ch =
				    (FormatIsStd(port.format) && channels == 8 ? STD_8CH_MAP[ch] : ch);
				int64_t sample =
				    static_cast<int64_t>(src[frame * channels + src_ch]) * port.volume[ch] / 32768;
				if (sample > std::numeric_limits<int16_t>::max()) {
					sample = std::numeric_limits<int16_t>::max();
				} else if (sample < std::numeric_limits<int16_t>::min()) {
					sample = std::numeric_limits<int16_t>::min();
				}
				dst[frame * channels + ch] = static_cast<int16_t>(sample);
			}
		}
	}

	return buffer->data();
}

// BC5 (rumble fallback). Ported from AnyPS5 core/libs/prx/libSceAudioOut/src/AudioOut2PadMix.cpp
// @ 7f596df (GPL-2.0), AudioOut2RumbleFromPadFrames: when the controller has no audio sink (a
// DualShock 4, F72) or its device has dropped (F61, F93), the vibration port's frames become
// classic rumble: per channel the RMS of the block, and rms >= 0.01 gives min(1, 2*rms)*255,
// sent through controller.cpp's rumble path. KYTY_BC5_PAD_RUMBLE_FALLBACK=0 disables it.
// TODO(verify): AnyPS5 names the pad speaker port type 0x3 and the vibration port type 0x6
// (AudioOut2PadMix.hpp); F69 recorded the titles opening types 4 and 10, which this file keeps.
static bool PadRumbleFallbackEnabled() {
	static const bool enabled = [] {
		const char* e = std::getenv("KYTY_BC5_PAD_RUMBLE_FALLBACK");
		return e == nullptr || std::strcmp(e, "0") != 0;
	}();
	return enabled;
}

void Audio::PadRumbleFromVibrationFrames(const PortOut& port, const void* data) {
	if (data == nullptr || (port.channels_num != 1 && port.channels_num != 2) || port.samples_num == 0) {
		return;
	}
	const bool     is_float  = FormatIsFloat(port.format);
	const uint32_t frames    = port.samples_num;
	const uint32_t channels  = static_cast<uint32_t>(port.channels_num);
	uint8_t        rumble[2] = {0, 0};
	for (uint32_t ch = 0; ch < 2; ch++) {
		const uint32_t src_ch = channels == 2 ? ch : 0;
		const float    volume = static_cast<float>(port.volume[src_ch]) / 32768.0f;
		double         energy = 0.0;
		for (uint32_t f = 0; f < frames; f++) {
			const size_t index = static_cast<size_t>(f) * channels + src_ch;
			float        v     = 0.0f;
			if (is_float) {
				std::memcpy(&v, static_cast<const float*>(data) + index, sizeof(v));
			} else {
				int16_t s = 0;
				std::memcpy(&s, static_cast<const int16_t*>(data) + index, sizeof(s));
				v = static_cast<float>(s) / 32768.0f;
			}
			v *= volume;
			if (std::isfinite(v)) {
				energy += static_cast<double>(v) * v;
			}
		}
		const double rms = std::sqrt(energy / frames);
		if (rms >= 0.01) {
			rumble[ch] = static_cast<uint8_t>(std::lround(std::min(1.0, rms * 2.0) * 255.0));
		}
	}
	Controller::ControllerAudioRumble(rumble[0], rumble[1]);
}

bool Audio::QueueSdlAudio(PortOut* port, const void* data, bool blocking) {
	EXIT_IF(port == nullptr);

	// BC5 (experiment 0372): a port that belongs on the controller first follows the controller's audio device:
	// its stream is closed when the device goes (the frames dropped, never played on another sink), reopened when
	// it comes back, and moved onto it when it comes after the start (PadRouteStep).
	if (port->pad_want) {
		PadRouteStep(port);
	}

	// BC5 (rumble fallback): a vibration port with no controller audio device, or whose device is
	// not playing (unplugged, F93), drives the pad's motors instead of its actuators.
	if (port->type == AUDIO_OUT_PORT_TYPE_VIBRATION && data != nullptr && PadRumbleFallbackEnabled() &&
	    (port->audio_device == 0 || SDL_GetAudioDeviceStatus(port->audio_device) != SDL_AUDIO_PLAYING)) {
		PadRumbleFromVibrationFrames(*port, data);
	}

	// BC5 (experiment 0182): the window's pause stops the title's clocks (experiment 0166) but its
	// sound went on: the device kept asking, the title's audio engine kept mixing, and its audio
	// clock, which the cutscenes' picture follows, ran ahead of the frozen game by the length of the
	// pause; after Resume the picture raced to catch up ("terrible lags of picture and sound after
	// unpausing"). On the console the whole title stops. The title's output thread now waits here
	// while paused, with its device paused (what is queued, at most ~40 ms, plays before it stops),
	// and both go on at Resume. The controller's ports are written by the same thread after the main
	// one and are not held themselves.
	if (port->pad_route == 0 && port->audio_device != 0 && LibKernel::KernelClocksPaused()) {
		SDL_PauseAudioDevice(port->audio_device, 1);
		while (LibKernel::KernelClocksPaused()) {
			Common::Thread::SleepMicro(5000);
		}
		SDL_PauseAudioDevice(port->audio_device, 0);
	}

	if (port->audio_device == 0 || data == nullptr) {
		if (port->pad_route != 0 && data != nullptr) {
			port->tr_pad_dropped++; // BC5 (experiment 0372): the controller is away
		}
		return false;
	}

	std::vector<uint8_t> prepared_buffer;
	const void*          prepared_data = PrepareOutputBuffer(*port, data, &prepared_buffer);
	auto                 prepared_size = FrameSize(*port) * port->samples_num;
	auto                 src_channels  = static_cast<Uint8>(port->channels_num);

	// BC5 (haptics): onto the stream to the controller — speaker on channels 1-2, actuators on
	// the last pair (PAD_STREAM_CHANNELS); a mono port on both of its pair, the rest silent.
	std::vector<uint8_t> pad_buffer;
	if (port->pad_route != 0 && (port->channels_num == 1 || port->channels_num == 2)) {
		const uint32_t bps    = BytesPerSample(port->format);
		const uint32_t frames = port->samples_num;
		constexpr uint32_t pad_channels = PAD_STREAM_CHANNELS;
		pad_buffer.assign(static_cast<size_t>(frames) * pad_channels * bps, 0);
		const auto* src = static_cast<const uint8_t*>(prepared_data);
		const uint32_t base = port->pad_route == 2 ? pad_channels - 2 : 0;
		// KYTY_BC5_HAPTIC_GAIN=<float> (default 1): the actuators' stream scaled, clipped at full scale.
		static const float haptic_gain = [] {
			const char* e = std::getenv("KYTY_BC5_HAPTIC_GAIN");
			const float g = e != nullptr ? static_cast<float>(std::atof(e)) : 1.0f;
			return g > 0.0f && g < 64.0f ? g : 1.0f;
		}();
		const bool  is_float = FormatIsFloat(port->format);
		float       peak     = 0.0f;
		for (uint32_t f = 0; f < frames; f++) {
			const uint8_t* l = src + (static_cast<size_t>(f) * port->channels_num) * bps;
			const uint8_t* r = port->channels_num == 2 ? l + bps : l;
			uint8_t*       d = pad_buffer.data() + (static_cast<size_t>(f) * pad_channels + base) * bps;
			if (port->pad_route == 2 && haptic_gain != 1.0f) {
				for (int k = 0; k < 2; k++) {
					const uint8_t* in = k == 0 ? l : r;
					if (is_float) {
						float v;
						std::memcpy(&v, in, 4);
						v = std::clamp(v * haptic_gain, -1.0f, 1.0f);
						std::memcpy(d + k * bps, &v, 4);
					} else {
						int16_t v;
						std::memcpy(&v, in, 2);
						v = static_cast<int16_t>(std::clamp(static_cast<float>(v) * haptic_gain, -32768.0f, 32767.0f));
						std::memcpy(d + k * bps, &v, 2);
					}
				}
			} else {
				std::memcpy(d, l, bps);
				std::memcpy(d + bps, r, bps);
			}
			if (is_float) {
				float v;
				std::memcpy(&v, d, 4);
				peak = std::max(peak, std::fabs(v));
			} else {
				int16_t v;
				std::memcpy(&v, d, 2);
				peak = std::max(peak, std::fabs(static_cast<float>(v)) / 32768.0f);
			}
		}
		// KYTY_BC5_INPUT_TRACE=1: once a second per port, what reaches the pad.
		static const bool trace_env = BC5_DIAG_ENV("KYTY_BC5_INPUT_TRACE") != nullptr;
		const bool trace = trace_env && ::Log::Bc5LoggingOn();
		if (trace) {
			static std::map<const PortOut*, std::pair<uint64_t, float>> seen; // port -> (last ms, max peak)
			static std::map<const PortOut*, std::pair<uint32_t, uint32_t>> counts; // port -> (calls, frames)
			static std::mutex                                            seen_mutex;
			std::lock_guard<std::mutex>                                  lock(seen_mutex);
			auto&          e   = seen[port];
			const uint64_t now = LibKernel::KernelGetProcessTime() / 1000;
			e.second           = std::max(e.second, peak);
			auto& c = counts[port];
			c.first++;
			c.second += frames;
			if (now - e.first >= 1000) {
				if (e.second > 0.0f) {
					std::fprintf(stderr, "input trace: pad audio port type %d (%s) %d ch %u Hz %s: peak %.3f in the last second, %u calls, %u frames, volume %d, gain %.1f, sdl queued %u bytes\n",
					             port->type, port->pad_route == 2 ? "haptics, last pair" : "speaker ch 1-2", port->channels_num, port->freq,
					             is_float ? "f32" : "s16", e.second, c.first, c.second, port->volume[0], haptic_gain,
					             static_cast<unsigned>(SDL_GetQueuedAudioSize(port->audio_device)));
					c = {0, 0};
					std::fflush(stderr);
				}
				e.first  = now;
				e.second = 0.0f;
			}
		}
		prepared_data = pad_buffer.data();
		prepared_size = static_cast<uint32_t>(pad_buffer.size());
		src_channels  = static_cast<Uint8>(pad_channels);
	}

	// BC5 (experiment 0166, KYTY_BC5_AUDIO_DUMP=<dir>): the first 40 s of each non-pad port as raw
	// PCM, before the SDL conversion (port<N>-in.raw: the port's format, channels, rate) and as
	// handed to SDL (port<N>-out.raw: the device's), one stderr line describing each.
	static const char* dump_dir = BC5_DIAG_ENV("KYTY_BC5_AUDIO_DUMP");
	// Experiment 0181: KYTY_BC5_AUDIO_DUMP_FROM=<s> starts the dump at that process time (a
	// cutscene, not the first 40 s), KYTY_BC5_AUDIO_DUMP_SECONDS=<s> sets its length (default 40).
	static const uint64_t dump_from_us = [] {
		const char* e = BC5_DIAG_ENV("KYTY_BC5_AUDIO_DUMP_FROM");
		return e != nullptr ? static_cast<uint64_t>(std::strtoull(e, nullptr, 10)) * 1000000u : 0u;
	}();
	static const uint64_t dump_seconds = [] {
		const char* e = BC5_DIAG_ENV("KYTY_BC5_AUDIO_DUMP_SECONDS");
		const long  v = e != nullptr ? std::strtol(e, nullptr, 10) : 40;
		return static_cast<uint64_t>(v > 0 ? v : 40);
	}();
	struct DumpFile { FILE* f = nullptr; uint64_t bytes = 0; bool closed = false; };
	static std::map<const PortOut*, std::pair<DumpFile, DumpFile>> dumps;
	static std::mutex                                                  dumps_mutex;
	auto dump = [&](DumpFile& d, const char* suffix, const void* data, uint32_t size, int ch, int freq, const char* fmt) {
		if (dump_dir == nullptr || port->pad_route != 0 || d.closed) return;
		if (d.f == nullptr && LibKernel::KernelGetProcessTime() < dump_from_us) return;
		if (d.f == nullptr) {
			char path[512];
			std::snprintf(path, sizeof(path), "%s/port-%p-%s.raw", dump_dir, static_cast<const void*>(port), suffix);
			d.f = std::fopen(path, "wb");
			if (d.f == nullptr) { d.closed = true; return; }
			std::fprintf(stderr, "audio dump: %s = port type %d, %d ch, %d Hz, %s\n", path, port->type, ch, freq, fmt);
		}
		std::fwrite(data, 1, size, d.f);
		d.bytes += size;
		const uint64_t limit = static_cast<uint64_t>(freq) * ch * 4 * dump_seconds; // at 4 bytes a sample
		if (d.bytes >= limit) { std::fclose(d.f); d.f = nullptr; d.closed = true; std::fprintf(stderr, "audio dump: %s closed at %" PRIu64 " bytes\n", suffix, d.bytes); }
	};
	{
		std::lock_guard<std::mutex> lk(dumps_mutex);
		dump(dumps[port].first, "in", prepared_data, prepared_size, src_channels, static_cast<int>(port->freq), FormatIsFloat(port->format) ? "f32" : "s16");
	}

	std::vector<uint8_t> convert_buffer;
	const void*          queue_data = prepared_data;
	uint32_t             queue_size = prepared_size;

	SDL_AudioCVT cvt {};
	const int    cvt_result =
	    SDL_BuildAudioCVT(&cvt, SdlFormat(port->format), src_channels,
	                      static_cast<int>(port->freq), port->audio_spec.format,
	                      port->audio_spec.channels, port->audio_spec.freq);

	if (cvt_result < 0) {
		LOGF("AudioOut: SDL_BuildAudioCVT failed: %s\n", SDL_GetError());
		return false;
	}

	if (cvt_result > 0) {
		convert_buffer.resize(prepared_size * cvt.len_mult);
		std::memcpy(convert_buffer.data(), prepared_data, prepared_size);

		cvt.buf = convert_buffer.data();
		cvt.len = static_cast<int>(prepared_size);

		if (SDL_ConvertAudio(&cvt) < 0) {
			LOGF("AudioOut: SDL_ConvertAudio failed: %s\n", SDL_GetError());
			return false;
		}

		queue_data = cvt.buf;
		queue_size = static_cast<uint32_t>(cvt.len_cvt);
	}

	// BC5 (haptics): the controller's device can vanish mid-run (its USB link drops) and its
	// queue then never drains, so the game's audio thread is never held for a pad port: a
	// removed or paused device drops the frames, a full queue is cleared, not waited for.
	// The reopen after an unplug (F93; the maintainer, 2026-10-09: SDL stops a removed device
	// for good) is in PadRouteStep since experiment 0372, at the top of this call.
	if (port->pad_route != 0) {
		if (SDL_GetAudioDeviceStatus(port->audio_device) != SDL_AUDIO_PLAYING) {
			return false;
		}
		if (SDL_GetQueuedAudioSize(port->audio_device) > queue_size * 8) {
			SDL_ClearQueuedAudio(port->audio_device);
		}
		blocking = false;
	}

	// BC5 (experiment 0267, after exp 0268): the pad-speaker port on the default sink: a full queue is
	// cleared, never waited for, so the title's audio thread (which also writes the main port in lockstep)
	// is not held by it.
	if (port->pad_nb) {
		if (SDL_GetQueuedAudioSize(port->audio_device) > queue_size * 8) {
			SDL_ClearQueuedAudio(port->audio_device);
		}
		blocking = false;
	}

	if (blocking) {
		// More aggressive buffer management to prevent audio issues
		// during heavy GPU load (common in gameplay vs cutscene)
		constexpr uint64_t target_latency_us = 30000; // Slightly lower latency
		const auto buffer_us = port->freq != 0 ? (1000000ULL * port->samples_num) / port->freq : 0;
		const auto buffers =
		    buffer_us != 0 ? static_cast<uint32_t>((target_latency_us + buffer_us - 1) / buffer_us)
		                   : 2u;
		const auto min_queued_size = queue_size * std::clamp(buffers, 2u, 8u); // Smaller max
		const auto wait_start      = LibKernel::KernelGetProcessTime();
		// BC5 (experiment 0180): the console's output call blocks until the hardware has room and never
		// drops what it was given. Here a wait over 100 ms cleared the queue (~42 ms of sound): in the
		// second title's opening a hiccup of the sound server's side then became an audible jump
		// (runs 0180: 1-3 clears in half the runs, at the scene loads), while the title's own audio
		// clock, which the cutscene's picture follows, had counted that sound as played. Held instead,
		// the title's clock waits with the device and the picture with it: nothing is skipped. The
		// queue is cleared only after KYTY_BC5_AUDIO_HOLD_MS (default 1000) without progress, a device
		// that has stopped. The title's audio thread is the one held, not its game thread.
		static const uint64_t timeout_us = [] {
			const char* e = std::getenv("KYTY_BC5_AUDIO_HOLD_MS");
			const long  v = e != nullptr ? std::strtol(e, nullptr, 10) : 1000;
			return static_cast<uint64_t>(v > 0 ? v : 1000) * 1000u;
		}();
		{
			const auto q = SDL_GetQueuedAudioSize(port->audio_device);
			port->tr_queued_min = std::min<uint32_t>(port->tr_queued_min, q);
			port->tr_queued_max = std::max<uint32_t>(port->tr_queued_max, q);
		}
		while (SDL_GetQueuedAudioSize(port->audio_device) > min_queued_size) {
			if (LibKernel::KernelGetProcessTime() - wait_start > timeout_us) {
				// Force clear if we're waiting too long - prevents audio stutter
				SDL_ClearQueuedAudio(port->audio_device);
				port->tr_clears++;
				break;
			}
			Common::Thread::SleepMicro(500); // Sleep less to check more frequently
		}
		port->tr_blocked_us += LibKernel::KernelGetProcessTime() - wait_start;
		port->tr_queued_bytes_per_ms = static_cast<uint32_t>(
		    (static_cast<uint64_t>(port->audio_spec.freq) * port->audio_spec.channels * SDL_AUDIO_BITSIZE(port->audio_spec.format)) / 8000u);
	}
	port->tr_calls++;
	port->tr_frames += port->samples_num;

	{
		std::lock_guard<std::mutex> lk(dumps_mutex);
		dump(dumps[port].second, "out", queue_data, queue_size, port->audio_spec.channels, port->audio_spec.freq,
		     SDL_AUDIO_ISFLOAT(port->audio_spec.format) ? "f32" : SDL_AUDIO_BITSIZE(port->audio_spec.format) == 16 ? "s16" : "other");
	}
	if (SDL_QueueAudio(port->audio_device, queue_data, queue_size) < 0) {
		LOGF("AudioOut: SDL_QueueAudio failed: %s\n", SDL_GetError());
		return false;
	}

	return true;
}

// BC5 (experiment 0372): the port's index, as the audio trace numbers ports.
int Audio::PortId(const PortOut* port) {
	return g_audio != nullptr ? static_cast<int>(port - g_audio->m_out_ports) : -1;
}

static const char* Bc5PadWhy(bc5::pad_audio_route::Why why) {
	using bc5::pad_audio_route::Why;
	switch (why) {
		case Why::DeviceRemoved: return "an output device was removed";
		case Why::DeviceStopped: return "SDL stopped its device";
		case Why::NotListed: return "the controller's device is no longer listed";
		case Why::DeviceAdded: return "an output device was added";
		case Why::Retry: return "the once-a-second retry";
		case Why::None: break;
	}
	return "-";
}

// BC5 (experiment 0372): what a port that belongs on the controller does with its device before its frames are
// queued; the decision is bc5::pad_audio_route::decide (bc5/pad_audio_route.hpp, unit-tested in the BC5 backend).
// - A stream on the controller is closed at any output device removal, when SDL stopped it (F93), or when the
//   once-a-second look no longer lists the controller, and reopened at once with the port's spec if the
//   controller is listed (a replug faster than this port's next write, or another sink removed: one close and
//   open). SDL cannot say which node went, and a stream whose node went may already be on the default sink.
// - While the controller is away the frames are dropped (the vibration port's go to the rumble fallback, F214),
//   and the port looks at every device event and once a second.
// - A port opened before the controller came (no pad at the start; a DualShock 4 swapped for a DualSense) is moved
//   onto it when it is listed; with no controller a pad-speaker port on the default sink stays there (F329, F330).
// Only the thread that writes the port opens and closes its device, as with F93; the port's device fields change
// under m_mutex, under which AudioOutHasDevice and AudioOutQueuedFrames read them, and SDL's close runs after the
// field is cleared. Every pad port is handled at its own next write, so each one is closed and reopened.
void Audio::PadRouteStep(PortOut* port) {
	namespace route = bc5::pad_audio_route;
	const route::DeviceEvents now    = Bc5AudioDeviceEvents();
	const uint64_t            now_ms = LibKernel::KernelGetProcessTime() / 1000;

	route::PortState state;
	state.wants_pad    = true;
	state.on_pad       = port->pad_route != 0;
	state.has_device   = port->audio_device != 0;
	state.stopped      = state.has_device && SDL_GetAudioDeviceStatus(port->audio_device) == SDL_AUDIO_STOPPED;
	state.retry_armed  = port->pad_retry_armed;
	state.seen         = port->pad_seen;
	state.last_look_ms = port->pad_retry_ms;

	std::string           name;
	const route::Decision d = route::decide(state, now, now_ms, [&name] {
		name = Bc5FindPadAudioDevice();
		return !name.empty();
	});

	bool opened = false;
	if (d.step == route::Step::Close || (d.step == route::Step::Open && state.on_pad && state.has_device)) {
		// First: the stream may already be on another sink.
		PadCloseDevice(port);
		std::fprintf(stderr, "AudioOut (exp 0372): t %.3f s port %d type %d: its stream on the controller closed (%s)%s\n",
		             static_cast<double>(LibKernel::KernelGetProcessTime()) / 1e6, PortId(port), port->type, Bc5PadWhy(d.why),
		             d.step == route::Step::Close ? "; frames dropped until the controller is back" : "");
		std::fflush(stderr);
	}
	if (d.step == route::Step::Open) {
		opened = PadOpenDevice(port, name, Bc5PadWhy(d.why));
	}

	const route::PortState next = route::after(state, d, now, now_ms, opened);
	port->pad_seen        = next.seen;
	port->pad_retry_ms    = next.last_look_ms;
	port->pad_retry_armed = next.retry_armed;
}

// BC5 (experiment 0372): the port's device closed, its spec and route kept for the reopen.
void Audio::PadCloseDevice(PortOut* port) {
	SDL_AudioDeviceID old = 0;
	{
		Common::LockGuard lock(g_audio->m_mutex);
		old                = port->audio_device;
		port->audio_device = 0;
	}
	if (old != 0) {
		SDL_ClearQueuedAudio(old);
		SDL_CloseAudioDevice(old);
	}
}

#if KYTY_PLATFORM == KYTY_PLATFORM_LINUX
static void Bc5RaiseAudioClientThreads(); // below (experiment 0180)
#endif

// BC5 (experiment 0372): the port opened on the controller's device `name`: with the spec it had there (F93's
// reopen), or the first time (the controller came after the port was opened) as OpenSdlDevice opens a pad port.
// A device the port still has (on the default sink) is closed once the new one is open, so a port has one device
// at a time. False, the port as it was, when SDL cannot open it (e.g. WirePlumber destroyed the stream because the
// returning sink was not linkable yet, node.dont-fallback); the port tries again a second later. The new
// stream's SDLAudioP thread gets nice -15 like those of the first opens (exp 0180/0181; F93's reopen left it at 0).
bool Audio::PadOpenDevice(PortOut* port, const std::string& name, const char* why) {
	SDL_AudioSpec desired {};
	int           allowed = 0;
	if (port->pad_route != 0) {
		desired = port->audio_spec;
	} else {
		desired.freq     = static_cast<int>(port->freq);
		desired.format   = SdlFormat(port->format);
		desired.channels = PAD_STREAM_CHANNELS;
		desired.samples  = static_cast<Uint16>(port->samples_num);
		desired.callback = nullptr;
		allowed          = SDL_AUDIO_ALLOW_FREQUENCY_CHANGE | SDL_AUDIO_ALLOW_FORMAT_CHANGE;
	}
	SDL_AudioSpec           obtained {};
	bool                    props = false;
	const SDL_AudioDeviceID dev   = Bc5OpenSdlAudioDevice(name.c_str(), &desired, &obtained, allowed, true, &props);
	const double            t     = static_cast<double>(LibKernel::KernelGetProcessTime()) / 1e6;
	if (dev == 0) {
		if (port->pad_open_fails++ % 60 == 0) {
			std::fprintf(stderr, "AudioOut (exp 0372): t %.3f s port %d type %d: opening on %s failed (after %s): %s; %u in a row, again in 1 s\n",
			             t, PortId(port), port->type, name.c_str(), why, SDL_GetError(), port->pad_open_fails);
			std::fflush(stderr);
		}
		return false;
	}
	const bool        moved = port->pad_route == 0 && port->audio_device != 0;
	SDL_AudioDeviceID old   = 0;
	{
		Common::LockGuard lock(g_audio->m_mutex);
		old                = port->audio_device;
		port->audio_device = dev;
		port->audio_spec   = obtained;
		port->pad_route    = port->type == AUDIO_OUT_PORT_TYPE_VIBRATION ? 2 : 1;
		port->pad_nb       = false;
	}
	if (old != 0) {
		SDL_ClearQueuedAudio(old);
		SDL_CloseAudioDevice(old);
	}
	SDL_PauseAudioDevice(dev, 0);
#if KYTY_PLATFORM == KYTY_PLATFORM_LINUX
	Bc5RaiseAudioClientThreads();
#endif
	port->pad_open_fails = 0;
	LOGF("AudioOut: controller audio device %s for port type %d on %s\n", moved ? "taken from the default sink" : "reopened", port->type, name.c_str());
	std::fprintf(stderr, "AudioOut (exp 0372): t %.3f s port %d type %d: %s on %s (%d Hz, %d ch) after %s%s\n", t, PortId(port),
	             port->type, moved ? "moved from the default sink" : "opened", name.c_str(), obtained.freq,
	             static_cast<int>(obtained.channels), why, props ? "; node.dont-reconnect, node.dont-fallback" : "");
	std::fflush(stderr);
	return true;
}

#if KYTY_PLATFORM == KYTY_PLATFORM_LINUX
// BC5 (experiment 0180): SDL's PulseAudio backend moves the sound to the server on its own thread,
// "PulseMainloop", which ran at nice 0 beside ~60 busy game threads while SDL's audio threads have
// nice -15. When it waited for a CPU the server ran dry (a gap) and the host's queue backed up
// until the 100-ms limit below cleared it (a jump): the cutscene's sound slowed and sped up. It
// gets the same -15 (SDL_LinuxSetThreadPriority: setpriority, else RealtimeKit1), once a port is
// open. Experiment 0181: with SDL's native PipeWire backend the stream runs on SDL's PipeWire thread
// loops ("SDLAudioP<n>"), which PipeWire's own real-time module cannot raise from the container;
// they get -15 too. Every open looks again (each device brings its own thread), and a thread
// already at -15 is left alone. KYTY_BC5_AUDIO_PRIORITY=0 leaves them all.
static void Bc5RaiseAudioClientThreads() {
	const char* e = std::getenv("KYTY_BC5_AUDIO_PRIORITY");
	if (e != nullptr && std::strcmp(e, "0") == 0) {
		return;
	}
	DIR* d = opendir("/proc/self/task");
	if (d == nullptr) {
		return;
	}
	while (const dirent* de = readdir(d)) {
		if (de->d_name[0] < '0' || de->d_name[0] > '9') continue;
		char path[64];
		std::snprintf(path, sizeof(path), "/proc/self/task/%s/comm", de->d_name);
		char  comm[32] = {};
		FILE* f        = std::fopen(path, "r");
		if (f == nullptr) continue;
		const bool got = std::fgets(comm, sizeof(comm), f) != nullptr;
		std::fclose(f);
		if (got && (std::strncmp(comm, "PulseMainloop", 13) == 0 || std::strncmp(comm, "SDLAudioP", 9) == 0)) {
			const long tid = std::strtol(de->d_name, nullptr, 10);
			errno          = 0;
			const int now  = getpriority(PRIO_PROCESS, static_cast<id_t>(tid));
			if (errno == 0 && now <= -15) {
				continue;
			}
			comm[std::strcspn(comm, "\n")] = 0;
			const int rc = SDL_LinuxSetThreadPriority(tid, -15);
			std::fprintf(stderr, "AudioOut: %s thread %ld at nice -15%s\n", comm, tid, rc == 0 ? "" : " refused");
		}
	}
	closedir(d);
}
#endif

Audio::Id Audio::AudioOutOpen(int type, uint32_t samples_num, uint32_t freq, Format format) {
#if KYTY_PLATFORM == KYTY_PLATFORM_LINUX
	struct Raise {
		~Raise() { Bc5RaiseAudioClientThreads(); } // after the device is open (end of this call)
	} raise;
#endif
	Common::LockGuard lock(m_mutex);

	for (int id = 0; id < OUT_PORTS_MAX; id++) {
		if (!m_out_ports[id].used) {
			auto& port = m_out_ports[id];

			port.used             = true;
			port.type             = type;
			port.samples_num      = samples_num;
			port.freq             = freq;
			port.format           = format;
			port.last_output_time = 0;

			switch (format) {
				case Format::Signed16bitMono:
				case Format::FloatMono: port.channels_num = 1; break;
				case Format::Signed16bitStereo:
				case Format::FloatStereo: port.channels_num = 2; break;
				case Format::Signed16bit8Ch:
				case Format::Float8Ch:
				case Format::Signed16bit8ChStd:
				case Format::Float8ChStd: port.channels_num = 8; break;
				default: EXIT("unknown format");
			}

			for (int i = 0; i < port.channels_num; i++) {
				port.volume[i] = 32768;
			}

			if (type != AUDIO_OUT_PORT_TYPE_VIBRATION || std::getenv("KYTY_BC5_NO_PAD_AUDIO") == nullptr) {
				// KytyPlus diagnostic: OpenSdlDevice() may fail (no host audio device,
				// unsupported sample rate/format, or SDL init failure). The return is
				// otherwise ignored, which silently leaves audio_device == 0 and makes
				// QueueSdlAudio() drop every buffer with no log. Surfacing it turns
				// "in-game but silent" into a diagnosable log entry.
				const bool sdl_opened = OpenSdlDevice(&port);
				if (!sdl_opened) {
					LOGF("AudioOut: SDL device open failed for port type=%d format=%s "
					     "samples=%u freq=%u; this port will be silent\n",
					     type, Common::EnumName(format).c_str(), samples_num, freq);
				}
			}

			return Id::Create(id);
		}
	}

	return Id::Invalid();
}

bool Audio::AudioOutClose(Id handle) {
	Common::LockGuard lock(m_mutex);

	if (AudioOutValid(handle)) {
		auto& port = m_out_ports[handle.GetId()];

		CloseSdlDevice(&port);
		port = {};

		return true;
	}

	return false;
}

bool Audio::AudioOutValid(Id handle) {
	Common::LockGuard lock(m_mutex);

	return (handle.GetId() >= 0 && handle.GetId() < OUT_PORTS_MAX &&
	        m_out_ports[handle.GetId()].used);
}

bool Audio::AudioOutHasDevice(Id handle) {
	Common::LockGuard lock(m_mutex);

	return (handle.GetId() >= 0 && handle.GetId() < OUT_PORTS_MAX &&
	        m_out_ports[handle.GetId()].used && m_out_ports[handle.GetId()].audio_device != 0);
}

// BC5 (experiment 0188): the frames handed to the port's SDL device and not yet played (0 without one).
uint32_t Audio::AudioOutQueuedFrames(Id handle) {
	Common::LockGuard lock(m_mutex);

	if (handle.GetId() < 0 || handle.GetId() >= OUT_PORTS_MAX || !m_out_ports[handle.GetId()].used ||
	    m_out_ports[handle.GetId()].audio_device == 0) {
		return 0;
	}
	const auto&    port        = m_out_ports[handle.GetId()];
	const uint32_t frame_bytes = static_cast<uint32_t>(port.audio_spec.channels) * (SDL_AUDIO_BITSIZE(port.audio_spec.format) / 8u);
	return frame_bytes != 0 ? SDL_GetQueuedAudioSize(port.audio_device) / frame_bytes : 0;
}

bool Audio::AudioOutGetStatus(Id handle, int* type, int* channels_num) {
	Common::LockGuard lock(m_mutex);

	if (AudioOutValid(handle)) {
		auto& port = m_out_ports[handle.GetId()];

		*type         = port.type;
		*channels_num = port.channels_num;

		return true;
	}

	return false;
}

bool Audio::AudioOutSetVolume(Id handle, uint32_t bitflag, const int* volume) {
	Common::LockGuard lock(m_mutex);

	if (AudioOutValid(handle)) {
		auto& port = m_out_ports[handle.GetId()];

		for (int i = 0; i < port.channels_num; i++, bitflag >>= 1u) {
			auto bit = bitflag & 0x1u;

			if (bit == 1) {
				int src_index = i;
				if (port.format == Format::Float8ChStd ||
				    port.format == Format::Signed16bit8ChStd) {
					switch (i) {
						case 4: src_index = 6; break;
						case 5: src_index = 7; break;
						case 6: src_index = 4; break;
						case 7: src_index = 5; break;
						default:;
					}
				}
				port.volume[i] = volume[src_index];

				LOGF("\t port.volume[%d] = volume[%d] (%d)\n", i, src_index, volume[src_index]);
			}
		}

		return true;
	}

	return false;
}

uint32_t Audio::AudioOutOutputs(OutputParam* params, uint32_t num, bool blocking) {
	EXIT_NOT_IMPLEMENTED_MSG(num == 0, "AudioOut: called with zero ports");
	EXIT_NOT_IMPLEMENTED_MSG(!AudioOutValid(params[0].handle), "AudioOut: invalid output handle");

	const auto& first_port = m_out_ports[params[0].handle.GetId()];

	uint64_t block_time   = (1000000 * first_port.samples_num) / first_port.freq;
	uint64_t current_time = LibKernel::KernelGetProcessTime();

	uint64_t max_wait_time = 0;

	for (uint32_t i = 0; i < num; i++) {
		uint64_t next_time = m_out_ports[params[i].handle.GetId()].last_output_time + block_time;
		uint64_t wait_time = (next_time > current_time ? next_time - current_time : 0);
		max_wait_time      = (wait_time > max_wait_time ? wait_time : max_wait_time);
	}

	bool any_port_has_device = false;
	for (uint32_t i = 0; i < num; i++) {
		if (m_out_ports[params[i].handle.GetId()].audio_device != 0) {
			any_port_has_device = true;
			break;
		}
	}

	// One real output device is enough to pace the whole synchronized batch. Applying the fallback
	// when a vibration port is present would rate-limit the device-backed ports to exactly 1x and
	// prevent their SDL queues from building an underrun cushion.
	if (blocking && max_wait_time != 0 && !any_port_has_device) {
		Common::Thread::SleepMicro(max_wait_time);
	}

	for (uint32_t i = 0; i < num; i++) {
		auto& port = m_out_ports[params[i].handle.GetId()];

		QueueSdlAudio(&port, params[i].data, blocking);
	}

	for (uint32_t i = 0; i < num; i++) {
		m_out_ports[params[i].handle.GetId()].last_output_time = LibKernel::KernelGetProcessTime();
	}

	// BC5 (audio pacing): KYTY_BC5_AUDIO_TRACE=1 prints, once a second, how fast the game's audio
	// thread pushed frames against the wall clock (the title's game clock is Wwise's play
	// position, i.e. the frames the host accepted), how long it was held, and the SDL queue.
	static const bool trace_env = BC5_DIAG_ENV("KYTY_BC5_AUDIO_TRACE") != nullptr;
	// Experiment 0174: KYTY_BC5_MEASURE=1 keeps this one-line-a-second measurement on when the
	// session's logging is switched off (the maintainer plays with logging off).
	static const bool measure = BC5_DIAG_ENV("KYTY_BC5_MEASURE") != nullptr;
	const bool trace = trace_env && (measure || ::Log::Bc5LoggingOn());
	if (trace) {
		static uint64_t last_us = 0;
		const uint64_t  now     = LibKernel::KernelGetProcessTime();
		if (last_us == 0) {
			last_us = now;
		} else if (now - last_us >= 1000000) {
			const double wall_s = static_cast<double>(now - last_us) / 1e6;
			for (int id = 0; id < OUT_PORTS_MAX; id++) {
				auto& p = m_out_ports[id];
				// BC5 (experiment 0372): a pad port whose controller is away has no device and no trace line of
				// its own; once a second, how many of its calls were dropped.
				if (p.used && p.tr_pad_dropped != 0) {
					std::fprintf(stderr, "pad route: t %.3f s port %d type %d (pad): %u calls dropped, no controller device\n",
					             static_cast<double>(now) / 1e6, id, p.type, p.tr_pad_dropped);
					p.tr_pad_dropped = 0;
				}
				if (!p.used || p.tr_calls == 0) {
					continue;
				}
				const double  pushed_s = p.freq != 0 ? static_cast<double>(p.tr_frames) / p.freq : 0.0;
				const uint32_t per_ms  = p.tr_queued_bytes_per_ms != 0 ? p.tr_queued_bytes_per_ms : 1;
				std::fprintf(stderr, "audio trace: t %.3f s port %d type %d %d ch %u Hz%s: %u calls, %u frames = %.3f s of sound in %.3f s (rate %.3f), held %.1f ms, %u clears, sdl queued %u-%u bytes (%u-%u ms), device %s\n",
				             static_cast<double>(now) / 1e6, id, p.type, p.channels_num, p.freq, p.pad_route != 0 ? " (pad)" : "",
				             p.tr_calls, p.tr_frames, pushed_s, wall_s, wall_s > 0 ? pushed_s / wall_s : 0.0,
				             static_cast<double>(p.tr_blocked_us) / 1e3, p.tr_clears,
				             p.tr_queued_min == 0xffffffffu ? 0u : p.tr_queued_min, p.tr_queued_max,
				             (p.tr_queued_min == 0xffffffffu ? 0u : p.tr_queued_min) / per_ms, p.tr_queued_max / per_ms,
				             p.audio_device == 0 ? "none" : SDL_GetAudioDeviceStatus(p.audio_device) == SDL_AUDIO_PLAYING ? "playing" : "not playing");
				p.tr_calls = p.tr_frames = p.tr_clears = 0;
				p.tr_blocked_us = 0;
				p.tr_queued_min = 0xffffffffu;
				p.tr_queued_max = 0;
			}
			std::fflush(stderr);
			last_us = now;
		}
	}

	return first_port.samples_num;
}

Audio::Id Audio::AudioInOpen(uint32_t type, uint32_t samples_num, uint32_t freq, Format format) {
	Common::LockGuard lock(m_mutex);

	for (int id = 0; id < IN_PORTS_MAX; id++) {
		if (!m_in_ports[id].used) {
			auto& port = m_in_ports[id];

			port.used        = true;
			port.type        = type;
			port.samples_num = samples_num;
			port.freq        = freq;
			port.format      = format;

			switch (format) {
				case Format::Signed16bitMono:
				case Format::Signed16bitStereo: break;
				default: EXIT("unknown format");
			}

			return Id::Create(id);
		}
	}

	return Id::Invalid();
}

bool Audio::AudioInValid(Id handle) {
	Common::LockGuard lock(m_mutex);

	return (handle.GetId() >= 0 && handle.GetId() < IN_PORTS_MAX &&
	        m_in_ports[handle.GetId()].used);
}

uint32_t Audio::AudioInInput(Id handle, void* dest) {
	EXIT_NOT_IMPLEMENTED_MSG(!AudioInValid(handle), "AudioIn: invalid input handle");
	EXIT_NOT_IMPLEMENTED(dest == nullptr);

	const auto& port = m_in_ports[handle.GetId()];

	uint64_t block_time   = (1000000 * port.samples_num) / port.freq;
	uint64_t current_time = LibKernel::KernelGetProcessTime();

	uint64_t next_time = m_in_ports[handle.GetId()].last_input_time + block_time;
	uint64_t wait_time = (next_time > current_time ? next_time - current_time : 0);

	// TODO(): Audio input is not yet implemented, so simulate audio delay
	Common::Thread::SleepMicro(wait_time);

	m_in_ports[handle.GetId()].last_input_time = LibKernel::KernelGetProcessTime();

	return port.samples_num;
}

namespace AudioOut {

LIB_NAME("AudioOut", "AudioOut");

struct AudioOutOutputParam {
	int         handle;
	const void* ptr;
};

struct AudioOutPortState {
	uint16_t output;
	uint8_t  channel;
	uint8_t  reserved1[1];
	int16_t  volume;
	uint16_t reroute_counter;
	uint64_t flag;
	uint64_t reserved2[2];
};

int KYTY_SYSV_ABI AudioOutInit() {
	PRINT_NAME();

	return OK;
}

int KYTY_SYSV_ABI AudioOutOpen(int user_id, int type, int index, uint32_t len, uint32_t freq,
                               uint32_t param) {
	PRINT_NAME();

	LOGF("\t user_id = %d\n"
	     "\t type    = %d\n"
	     "\t index   = %d\n"
	     "\t len     = %u\n"
	     "\t freq    = %u\n",
	     user_id, type, index, len, freq);

	if (!audio_out_port_type_is_valid(type)) {
		return AUDIO_OUT_ERROR_INVALID_PORT_TYPE;
	}
	EXIT_NOT_IMPLEMENTED(index != 0);

	Audio::Format format       = Audio::Format::Unknown;
	const auto    format_param = param & AUDIO_OUT_PARAM_FORMAT_MASK;

	switch (format_param) {
		case 0: format = Audio::Format::Signed16bitMono; break;
		case 1: format = Audio::Format::Signed16bitStereo; break;
		case 2: format = Audio::Format::Signed16bit8Ch; break;
		case 3: format = Audio::Format::FloatMono; break;
		case 4: format = Audio::Format::FloatStereo; break;
		case 5: format = Audio::Format::Float8Ch; break;
		case 6: format = Audio::Format::Signed16bit8ChStd; break;
		case 7: format = Audio::Format::Float8ChStd; break;
		default:;
	}

	LOGF("\t param   = %u (format=%u, %s)\n", param, format_param,
	     Common::EnumName(format).c_str());

	EXIT_NOT_IMPLEMENTED(format == Audio::Format::Unknown);

	EXIT_IF(g_audio == nullptr);

	auto id = g_audio->AudioOutOpen(type, len, freq, format);

	if (!id.IsValid()) {
		return AUDIO_OUT_ERROR_PORT_FULL;
	}

	return id.ToInt();
}

int KYTY_SYSV_ABI AudioOutClose(int handle) {
	PRINT_NAME();

	if (!g_audio->AudioOutClose(Audio::Id(handle))) {
		return AUDIO_OUT_ERROR_INVALID_PORT;
	}

	return OK;
}

int KYTY_SYSV_ABI AudioOutGetPortState(int handle, AudioOutPortState* state) {
	PRINT_NAME();

	int type         = 0;
	int channels_num = 0;

	if (!g_audio->AudioOutGetStatus(Audio::Id(handle), &type, &channels_num)) {
		return AUDIO_OUT_ERROR_INVALID_PORT;
	}

	EXIT_NOT_IMPLEMENTED(state == nullptr);

	state->reroute_counter = 0;
	state->volume          = 127;

	switch (type) {
		case AUDIO_OUT_PORT_TYPE_MAIN:
		case AUDIO_OUT_PORT_TYPE_BGM:
		case AUDIO_OUT_PORT_TYPE_AUDIO3D:
			state->output  = 1;
			state->channel = (channels_num > 2 ? 2 : channels_num);
			break;
		case AUDIO_OUT_PORT_TYPE_VOICE:
		case AUDIO_OUT_PORT_TYPE_PERSONAL:
			state->output  = 0x40;
			state->channel = 1;
			break;
		case AUDIO_OUT_PORT_TYPE_PADSPK:
		case AUDIO_OUT_PORT_TYPE_VIBRATION:
			state->output  = 4;
			state->channel = 1;
			break;
		case AUDIO_OUT_PORT_TYPE_AUX:
			state->output  = 0x80;
			state->channel = 0;
			break;
		default: EXIT("unknown port type: %d\n", type);
	}

	LOGF("\t output  = %" PRIu16 "\n"
	     "\t channel = %" PRIu8 "\n",
	     state->output, state->channel);

	return OK;
}

int KYTY_SYSV_ABI AudioOutSetVolume(int handle, uint32_t flag, int* vol) {
	PRINT_NAME();

	LOGF("\t handle = %d\n"
	     "\t flag   = %u\n",
	     handle, flag);

	EXIT_IF(g_audio == nullptr);
	EXIT_NOT_IMPLEMENTED(vol == nullptr);

	if (!g_audio->AudioOutSetVolume(Audio::Id(handle), flag, vol)) {
		return AUDIO_OUT_ERROR_INVALID_PORT;
	}

	return OK;
}

int KYTY_SYSV_ABI AudioOutOutputs(AudioOutOutputParam* param, uint32_t num) {
	PRINT_NAME();

	EXIT_NOT_IMPLEMENTED(param == nullptr);

	Audio::OutputParam params[Audio::OUT_PORTS_MAX];

	EXIT_IF(g_audio == nullptr);

	for (uint32_t i = 0; i < num; i++) {
		params[i].handle = Audio::Id(param[i].handle);
		params[i].data   = param[i].ptr;

		if (!g_audio->AudioOutValid(params[i].handle)) {
			return AUDIO_OUT_ERROR_INVALID_PORT;
		}
	}

	return static_cast<int>(g_audio->AudioOutOutputs(params, num));
}

int KYTY_SYSV_ABI AudioOutOutput(int handle, const void* ptr) {
	// EXIT_NOT_IMPLEMENTED(ptr == nullptr);

	Audio::OutputParam params[1];

	EXIT_IF(g_audio == nullptr);

	params[0].handle = Audio::Id(handle);
	params[0].data   = ptr;

	if (!g_audio->AudioOutValid(params[0].handle)) {
		return AUDIO_OUT_ERROR_INVALID_PORT;
	}

	return static_cast<int>(g_audio->AudioOutOutputs(params, 1));
}

} // namespace AudioOut

namespace AudioIn {

LIB_NAME("AudioIn", "AudioIn");

int KYTY_SYSV_ABI AudioInOpen(int user_id, uint32_t type, uint32_t index, uint32_t len,
                              uint32_t freq, uint32_t param) {
	PRINT_NAME();

	LOGF("\t user_id = %d\n"
	     "\t type    = %u\n"
	     "\t index   = %d\n"
	     "\t len     = %u\n"
	     "\t freq    = %u\n",
	     user_id, type, index, len, freq);

	if (user_id != 255 && user_id != 1) {
		LOGF("\t temporary: accepting unsupported audio input user_id %d\n", user_id);
	}
	EXIT_NOT_IMPLEMENTED(type != 1);
	EXIT_NOT_IMPLEMENTED(index != 0);

	Audio::Format format = Audio::Format::Unknown;

	switch (param) {
		case 0: format = Audio::Format::Signed16bitMono; break;
		case 2: format = Audio::Format::Signed16bitStereo; break;
		default:
			LOGF("\t temporary: using signed 16-bit stereo for unsupported audio input param %u\n",
			     param);
			format = Audio::Format::Signed16bitStereo;
			break;
	}

	LOGF("\t param   = %u (%s)\n", param, Common::EnumName(format).c_str());

	EXIT_IF(g_audio == nullptr);

	auto id = g_audio->AudioInOpen(type, len, freq, format);

	if (!id.IsValid()) {
		return AUDIO_IN_ERROR_PORT_FULL;
	}

	return id.ToInt();
}

int KYTY_SYSV_ABI AudioInInput(int handle, void* dest) {
	PRINT_NAME();

	EXIT_NOT_IMPLEMENTED(dest == nullptr);

	EXIT_IF(g_audio == nullptr);

	if (!g_audio->AudioInValid(Audio::Id(handle))) {
		return AUDIO_IN_ERROR_INVALID_HANDLE;
	}

	return static_cast<int>(g_audio->AudioInInput(Audio::Id(handle), dest));
}

} // namespace AudioIn

namespace VoiceQoS {

LIB_NAME("VoiceQoS", "VoiceQoS");

int KYTY_SYSV_ABI VoiceQoSInit(void* mem_block, uint32_t mem_size, int32_t app_type) {
	PRINT_NAME();

	LOGF("\t mem_block = %016" PRIx64 "\n"
	     "\t mem_size = %" PRIu32 "\n"
	     "\t app_type = %" PRId32 "\n",
	     reinterpret_cast<uint64_t>(mem_block), mem_size, app_type);

	return OK;
}

} // namespace VoiceQoS

namespace Acm {

LIB_NAME("Acm", "Acm");

struct AcmBatchInfo {
	void*  buffer;
	size_t offset;
	size_t buffer_size;
};

struct AcmBatchError {
	uint32_t reserved[8];
};

static std::atomic_uint32_t g_acm_next_context {1};
static std::atomic_uint32_t g_acm_next_batch {1};

static void acm_advance_batch(AcmBatchInfo* info, size_t bytes) {
	if (info == nullptr || info->buffer == nullptr || info->buffer_size == 0) {
		return;
	}

	info->offset = std::min(info->buffer_size, info->offset + bytes);
}

int KYTY_SYSV_ABI AcmContextCreate(AcmContextId* context) {
	PRINT_NAME();

	EXIT_NOT_IMPLEMENTED(context == nullptr);

	*context = g_acm_next_context.fetch_add(1, std::memory_order_relaxed);

	LOGF("\t context = %" PRIu32 "\n", *context);

	return OK;
}

int KYTY_SYSV_ABI AcmContextDestroy(AcmContextId context) {
	PRINT_NAME();
	LOGF("\t context = %" PRIu32 "\n", context);
	return OK;
}

int KYTY_SYSV_ABI AcmBatchStartBuffer(AcmContextId context, const void* batch_commands,
                                      size_t batch_size, AcmBatchError* batch_error,
                                      AcmBatchId* batch) {
	PRINT_NAME();

	EXIT_NOT_IMPLEMENTED(batch == nullptr);

	if (batch_error != nullptr) {
		std::memset(batch_error, 0, sizeof(AcmBatchError));
	}

	*batch = g_acm_next_batch.fetch_add(1, std::memory_order_relaxed);

	return OK;
}

int KYTY_SYSV_ABI AcmBatchStartBuffers(AcmContextId context, uint32_t batch_info_count,
                                       const AcmBatchInfo* const batch_info[],
                                       AcmBatchError* batch_error, AcmBatchId* batch) {
	PRINT_NAME();

	EXIT_NOT_IMPLEMENTED(batch_info_count != 0 && batch_info == nullptr);
	EXIT_NOT_IMPLEMENTED(batch == nullptr);

	if (batch_error != nullptr) {
		std::memset(batch_error, 0, sizeof(AcmBatchError));
	}

	*batch = g_acm_next_batch.fetch_add(1, std::memory_order_relaxed);

	return OK;
}

int KYTY_SYSV_ABI AcmBatchWait(AcmContextId context, AcmBatchId batch, uint32_t timeout) {
	return OK;
}

int KYTY_SYSV_ABI AcmBatchJobNotification(AcmBatchInfo* batch_info) {
	PRINT_NAME();
	acm_advance_batch(batch_info, 2 * 16);
	return OK;
}

// Experiment 0329: sceAcmBatchJobPriority (GTfJ64qFCPw): a job that sets the priority of the batch it is written
// into, recorded in the batch buffer as this library records every job (the batch is advanced by the job's size and
// nothing is executed: no audio compute runs on this host, see AcmFft above); the priority is kept per batch
// buffer for the batch's start. TODO(verify): the job's size in the batch buffer (one 16-byte command here) and
// the priority's range; AnyPS5 has no implementation.
static std::mutex                        g_acm_priority_mutex;
static std::map<const void*, uint32_t>   g_acm_batch_priorities;

int KYTY_SYSV_ABI AcmBatchJobPriority(AcmBatchInfo* batch_info, uint32_t priority) {
	PRINT_NAME();
	EXIT_NOT_IMPLEMENTED(batch_info == nullptr);
	LOGF("\t batch buffer = 0x%016" PRIx64 ", priority = %u\n", reinterpret_cast<uint64_t>(batch_info->buffer),
	     priority);
	{
		std::lock_guard lock(g_acm_priority_mutex);
		g_acm_batch_priorities[batch_info->buffer] = priority;
	}
	acm_advance_batch(batch_info, 16);
	return OK;
}

int KYTY_SYSV_ABI AcmConvReverbSharedInput(AcmBatchInfo* batch_info, uint32_t block_count, void* in,
                                           uint32_t count, const void* const ir[],
                                           const float* gain, void* const out[]) {
	PRINT_NAME();
	(void)block_count;
	(void)in;
	(void)count;
	(void)ir;
	(void)gain;
	(void)out;
	acm_advance_batch(batch_info, 1024);
	return OK;
}

int KYTY_SYSV_ABI AcmConvReverbSharedIr(AcmBatchInfo* batch_info, uint32_t block_count,
                                        const void* ir, uint32_t count, void* const in[],
                                        const float* gain, void* const out[]) {
	PRINT_NAME();
	(void)block_count;
	(void)ir;
	(void)count;
	(void)in;
	(void)gain;
	(void)out;
	acm_advance_batch(batch_info, 1024);
	return OK;
}

int KYTY_SYSV_ABI AcmFft(AcmBatchInfo* batch_info, int size, int count, int input_format,
                         const void* const input[], int output_format, void* const output[],
                         uint32_t flags) {
	PRINT_NAME();
	(void)size;
	(void)count;
	(void)input_format;
	(void)input;
	(void)output_format;
	(void)output;
	(void)flags;
	acm_advance_batch(batch_info, 256);
	return OK;
}

int KYTY_SYSV_ABI AcmIfft(AcmBatchInfo* batch_info, int size, int count, int input_format,
                          const void* const input[], int output_format, void* const output[],
                          uint32_t flags) {
	PRINT_NAME();
	(void)size;
	(void)count;
	(void)input_format;
	(void)input;
	(void)output_format;
	(void)output;
	(void)flags;
	acm_advance_batch(batch_info, 256);
	return OK;
}

int KYTY_SYSV_ABI AcmPanner(AcmBatchInfo* batch_info, uint32_t in_count, const float* const in[],
                            uint32_t biquad_count, uint32_t biquad_update_count, uint32_t out_count,
                            const void* const parameter[], void* const state[],
                            const float* const out_init[], float* const out[]) {
	PRINT_NAME();
	(void)in_count;
	(void)in;
	(void)biquad_count;
	(void)biquad_update_count;
	(void)out_count;
	(void)parameter;
	(void)state;
	(void)out_init;
	(void)out;
	acm_advance_batch(batch_info, 512);
	return OK;
}

} // namespace Acm

namespace Audio3d {

LIB_NAME("Audio3d", "Audio3d");

namespace Semaphore = LibKernel::Semaphore;

struct Audio3dOpenParameters {
	size_t   size        = 0x20;
	uint32_t granularity = 256;
	uint32_t rate        = 0;
	uint32_t max_objects = 512;
	uint32_t queue_depth = 2;
	uint32_t buffer_mode = 2;
	uint32_t pad         = 0;
	// uint32_t num_beds;
};

struct Audio3dData {
	enum class State { Empty, Ready, Play };

	std::atomic<State> state = State::Empty;
};

struct Audio3dInternal {
	Audio3dData*          data                        = nullptr;
	Common::Mutex*        data_mutex                  = nullptr;
	uint64_t              data_delay                  = 0;
	Semaphore::KernelSema playback_sema               = nullptr;
	Audio3dOpenParameters params                      = {};
	int                   user_id                     = 0;
	float                 late_reverb_level           = 0.0f;
	float                 downmix_spread_radius       = 2.0f;
	int                   downmix_spread_height_aware = 0;
	uint32_t              data_index                  = 0;
	bool                  used                        = false;
	std::atomic_bool      playback_finished           = false;
};

constexpr uint32_t MAX_PORTS = 4;

static Audio3dInternal g_ports[MAX_PORTS] = {};

static void playback_simulate(void* arg) {
	auto* port = static_cast<Audio3dInternal*>(arg);
	EXIT_IF(port == nullptr);
	EXIT_IF(port->data_mutex == nullptr);
	EXIT_IF(port->data == nullptr);

	for (;;) {
		int result = Semaphore::KernelWaitSema(port->playback_sema, 1, nullptr);

		if (result != OK) {
			break;
		}

		Audio3dData* play_data = nullptr;

		port->data_mutex->Lock();
		{
			for (uint32_t i = 0; i < port->params.queue_depth; i++) {
				uint32_t index = (port->data_index + i) % port->params.queue_depth;

				if (port->data[index].state == Audio3dData::State::Play) {
					play_data = &port->data[index];
					break;
				}
			}
		}
		port->data_mutex->Unlock();

		EXIT_IF(play_data == nullptr);

		if (play_data != nullptr) {
			// TODO(): Audio output is not yet implemented, so simulate audio delay
			Common::Thread::SleepMicro(port->data_delay);
			play_data->state = Audio3dData::State::Empty;
		}
	}

	port->playback_finished = true;
}

int KYTY_SYSV_ABI Audio3dInitialize(int64_t reserved) {
	PRINT_NAME();

	EXIT_NOT_IMPLEMENTED(reserved != 0);

	return OK;
}

void KYTY_SYSV_ABI Audio3dGetDefaultOpenParameters(Audio3dOpenParameters* p) {
	PRINT_NAME();

	EXIT_NOT_IMPLEMENTED(sizeof(Audio3dOpenParameters) != 0x20);

	*p = Audio3dOpenParameters();
}

int KYTY_SYSV_ABI Audio3dPortOpen(int user_id, const Audio3dOpenParameters* parameters,
                                  uint32_t* id) {
	PRINT_NAME();

	EXIT_NOT_IMPLEMENTED(parameters == nullptr);
	EXIT_NOT_IMPLEMENTED(id == nullptr);
	EXIT_NOT_IMPLEMENTED(parameters->size != 0x20);

	LOGF("\t user_id     = %d\n"
	     "\t granularity = %u\n"
	     "\t rate        = %u\n"
	     "\t max_objects = %u\n"
	     "\t queue_depth = %u\n"
	     "\t buffer_mode = %u\n",
	     user_id, parameters->granularity, parameters->rate, parameters->max_objects,
	     parameters->queue_depth, parameters->buffer_mode);

	EXIT_NOT_IMPLEMENTED(parameters->buffer_mode != 2);
	EXIT_NOT_IMPLEMENTED(user_id != 255 && user_id != 1);

	uint32_t port = 0;
	for (; port < MAX_PORTS; port++) {
		if (!g_ports[port].used) {
			break;
		}
	}

	EXIT_NOT_IMPLEMENTED(port >= MAX_PORTS);

	g_ports[port].user_id = user_id;
	g_ports[port].params  = *parameters;
	g_ports[port].used    = true;

	EXIT_IF(g_ports[port].data != nullptr);
	EXIT_IF(g_ports[port].data_mutex != nullptr);
	EXIT_IF(g_ports[port].playback_sema != nullptr);

	g_ports[port].data       = new Audio3dData[parameters->queue_depth];
	g_ports[port].data_index = 0;
	g_ports[port].data_mutex = new Common::Mutex;
	g_ports[port].data_delay = (1000000 * static_cast<uint64_t>(parameters->granularity)) / 48000;

	for (uint32_t d = 0; d < parameters->queue_depth; d++) {
		g_ports[port].data[d].state = Audio3dData::State::Empty;
	}

	int result = Semaphore::KernelCreateSema(&g_ports[port].playback_sema, "audio3d_play", 0x01, 0,
	                                         static_cast<int>(parameters->queue_depth), nullptr);
	EXIT_NOT_IMPLEMENTED(result != OK);

	g_ports[port].playback_finished = false;
	Common::Thread playback_thread(playback_simulate, &g_ports[port]);
	playback_thread.Detach();

	*id = port;

	return OK;
}

int KYTY_SYSV_ABI Audio3dPortSetAttribute(uint32_t port_id, uint32_t attribute_id,
                                          const void* attribute, size_t attribute_size) {
	PRINT_NAME();

	EXIT_NOT_IMPLEMENTED(port_id >= MAX_PORTS);
	EXIT_NOT_IMPLEMENTED(!g_ports[port_id].used);
	EXIT_NOT_IMPLEMENTED(attribute == nullptr);

	LOGF("\t attribute_id = 0x%" PRIx32 "\n", attribute_id);

	switch (attribute_id) {
		case 0x10001:
			EXIT_NOT_IMPLEMENTED(attribute_size != 4);
			g_ports[port_id].late_reverb_level = *static_cast<const float*>(attribute);
			LOGF("\t late_reverb_level = %f\n", g_ports[port_id].late_reverb_level);
			break;
		case 0x10002:
			EXIT_NOT_IMPLEMENTED(attribute_size != 4);
			g_ports[port_id].downmix_spread_radius = *static_cast<const float*>(attribute);
			LOGF("\t downmix_spread_radius = %f\n", g_ports[port_id].downmix_spread_radius);
			break;
		case 0x10003:
			EXIT_NOT_IMPLEMENTED(attribute_size != 4);
			g_ports[port_id].downmix_spread_height_aware = *static_cast<const int*>(attribute);
			LOGF("\t downmix_spread_height_aware = %d\n",
			     g_ports[port_id].downmix_spread_height_aware);
			break;
		default: EXIT("unknown attribute: 0x%" PRIx32 "\n", attribute_id);
	}

	return OK;
}

int KYTY_SYSV_ABI Audio3dPortGetQueueLevel(uint32_t port_id, uint32_t* queue_level,
                                           uint32_t* queue_available) {
	PRINT_NAME();

	EXIT_NOT_IMPLEMENTED(port_id >= MAX_PORTS);
	EXIT_NOT_IMPLEMENTED(!g_ports[port_id].used);
	EXIT_NOT_IMPLEMENTED(queue_level == nullptr && queue_available == nullptr);

	auto* port = &g_ports[port_id];

	uint32_t empty_num = 0;

	port->data_mutex->Lock();
	{
		for (uint32_t i = 0; i < port->params.queue_depth; i++) {
			uint32_t index = (port->data_index + i) % port->params.queue_depth;

			if (port->data[index].state == Audio3dData::State::Empty) {
				empty_num++;
			} else {
				break;
			}
		}
	}
	port->data_mutex->Unlock();

	EXIT_IF(empty_num > port->params.queue_depth);

	LOGF("\t queue_available = %u\n", empty_num);

	if (queue_level != nullptr) {
		*queue_level = port->params.queue_depth - empty_num;
	}
	if (queue_available != nullptr) {
		*queue_available = empty_num;
	}

	return OK;
}

int KYTY_SYSV_ABI Audio3dPortAdvance(uint32_t port_id) {
	PRINT_NAME();

	EXIT_NOT_IMPLEMENTED(port_id >= MAX_PORTS);
	EXIT_NOT_IMPLEMENTED(!g_ports[port_id].used);

	auto* port = &g_ports[port_id];

	port->data_mutex->Lock();
	{
		uint32_t current_index = port->data_index;
		uint32_t next_index    = (current_index + 1) % port->params.queue_depth;

		if (port->data[current_index].state == Audio3dData::State::Empty) {
			port->data[current_index].state = Audio3dData::State::Ready;
		}

		EXIT_NOT_IMPLEMENTED(port->data[current_index].state != Audio3dData::State::Ready);

		port->data_index = next_index;

		LOGF("\t %u -> %u\n", current_index, next_index);
	}
	port->data_mutex->Unlock();

	return OK;
}

int KYTY_SYSV_ABI Audio3dPortPush(uint32_t port_id, uint32_t blocking) {
	PRINT_NAME();

	EXIT_NOT_IMPLEMENTED(port_id >= MAX_PORTS);
	EXIT_NOT_IMPLEMENTED(!g_ports[port_id].used);

	auto* port = &g_ports[port_id];

	EXIT_NOT_IMPLEMENTED(blocking != 1);

	LOGF("\t blocking = %u\n", blocking);

	int          data_num   = 0;
	Audio3dData* first_data = nullptr;

	port->data_mutex->Lock();
	{
		first_data = port->data + port->data_index;

		for (uint32_t i = 0; i < port->params.queue_depth; i++) {
			uint32_t index = (port->data_index + i) % port->params.queue_depth;

			if (port->data[index].state == Audio3dData::State::Ready) {
				port->data[index].state = Audio3dData::State::Play;
				data_num++;
			}
		}
	}
	port->data_mutex->Unlock();

	LOGF("\t push num = %d\n", data_num);

	if (data_num > 0) {
		Semaphore::KernelSignalSema(port->playback_sema, data_num);

		if (blocking == 1) {
			auto wait_time = port->data_delay / 8;
			while (first_data->state != Audio3dData::State::Empty) {
				Common::Thread::SleepMicro(wait_time);
			}
		}
	}

	return OK;
}

} // namespace Audio3d

namespace Ngs2 {

LIB_NAME("Ngs2", "Ngs2");

struct Ngs2SystemOption {
	size_t    size                     = 0;
	char      name[64]                 = {};
	uintptr_t job_scheduler_options[4] = {};
	uint32_t  flags                    = 0;
	uint32_t  max_grain_samples        = 0;
	uint32_t  num_grain_samples        = 0;
	uint32_t  sample_rate              = 0;
	uint32_t  max_voice_channels       = 0;
	uint32_t  reserved[5]              = {};
};

struct Ngs2RackOption {
	size_t   size                   = 0;
	char     name[64]               = {};
	uint32_t flags                  = 0;
	uint32_t max_grain_samples      = 0;
	uint32_t max_voices             = 0;
	uint32_t max_input_delay_blocks = 0;
	uint32_t max_matrices           = 0;
	uint32_t max_ports              = 0;
	uint32_t max_voice_channels     = 0;
	uint32_t max_output_channels    = 0;
	uint32_t reserved[18]           = {};
};

struct Ngs2MasteringRackOption {
	Ngs2RackOption rack_option;
	uint32_t       max_channels          = 0;
	uint32_t       num_peak_meter_blocks = 0;
};

struct Ngs2SubmixerRackOption {
	Ngs2RackOption rack_option;
	uint32_t       max_channels          = 0;
	uint32_t       max_envelope_points   = 0;
	uint32_t       max_filters           = 0;
	uint32_t       max_inputs            = 0;
	uint32_t       num_peak_meter_blocks = 0;
};

struct Ngs2SamplerRackOption {
	Ngs2RackOption rack_option;
	uint32_t       max_channel_works        = 0;
	uint32_t       max_codec_caches         = 0;
	uint32_t       max_waveform_blocks      = 0;
	uint32_t       max_envelope_points      = 0;
	uint32_t       max_filters              = 0;
	uint32_t       max_atrac9_decoders      = 0;
	uint32_t       max_atrac9_channel_works = 0;
	uint32_t       max_ajm_atrac9_decoders  = 0;
	uint32_t       num_peak_meter_blocks    = 0;
};

struct Ngs2ReverbRackOption {
	Ngs2RackOption rack_option;
	uint32_t       max_channels = 0;
	uint32_t       reverb_size  = 0;
};

struct Ngs2CustomModuleOption {
	uint32_t size = 0;
};

struct Ngs2CustomRackModuleInfo {
	const Ngs2CustomModuleOption* option           = nullptr;
	uint32_t                      module_id        = 0;
	uint32_t                      source_buffer_id = 0;
	uint32_t                      extra_buffer_id  = 0;
	uint32_t                      dest_buffer_id   = 0;
	uint32_t                      state_offset     = 0;
	uint32_t                      state_size       = 0;
	uint32_t                      reserved         = 0;
	uint32_t                      reserved2        = 0;
};

struct Ngs2CustomRackPortInfo {
	uint32_t source_buffer_id = 0;
	uint32_t reserved         = 0;
};

struct Ngs2CustomRackOption {
	Ngs2RackOption           rack_option;
	uint32_t                 state_size  = 0;
	uint32_t                 num_buffers = 0;
	uint32_t                 num_modules = 0;
	uint32_t                 reserved    = 0;
	Ngs2CustomRackModuleInfo module[24];
	Ngs2CustomRackPortInfo   port[16];
};

struct Ngs2CustomSubmixerRackOption {
	Ngs2CustomRackOption custom_rack_option;
	uint32_t             max_channels = 0;
	uint32_t             max_inputs   = 0;
};

struct Ngs2CustomMasteringRackOption {
	Ngs2CustomRackOption custom_rack_option;
	uint32_t             max_channels = 0;
	uint32_t             max_inputs   = 0;
};

struct Ngs2CustomSamplerRackOption {
	Ngs2CustomRackOption custom_rack_option;
	uint32_t             max_channel_works        = 0;
	uint32_t             max_waveform_blocks      = 0;
	uint32_t             max_atrac9_decoders      = 0;
	uint32_t             max_atrac9_channel_works = 0;
	uint32_t             max_ajm_atrac9_decoders  = 0;
	uint32_t             max_codec_caches         = 0;
};

union Ngs2RackOptionUnion {
	Ngs2RackOption               common;
	Ngs2SamplerRackOption        sampler;
	Ngs2MasteringRackOption      mastering;
	Ngs2SubmixerRackOption       submixer;
	Ngs2ReverbRackOption         reverb;
	Ngs2CustomSubmixerRackOption custom_submixer;
	Ngs2CustomMasteringRackOption custom_mastering;
	Ngs2CustomSamplerRackOption  custom_sampler;
};

struct Ngs2ContextBufferInfo {
	void*     host_buffer      = nullptr;
	size_t    host_buffer_size = 0;
	uintptr_t reserved[5]      = {};
	uintptr_t user_data        = 0;
};

struct Ngs2RenderBufferInfo {
	void*    buffer        = nullptr;
	size_t   buffer_size   = 0;
	uint32_t waveform_type = 0;
	uint32_t num_channels  = 0;
};

struct Ngs2WaveformFormat {
	uint32_t waveform_type = 0;
	uint32_t num_channels  = 0;
	uint32_t sample_rate   = 0;
	uint32_t config_data   = 0;
	uint32_t frame_margin  = 0;
	uint32_t frame_offset  = 0;
};

struct Ngs2WaveformBlock {
	uintptr_t data_offset      = 0;
	size_t    data_size        = 0;
	uint32_t  num_repeats      = 0;
	uint32_t  num_skip_samples = 0;
	uint32_t  num_samples      = 0;
	uint32_t  reserved         = 0;
	uintptr_t user_data        = 0;
};

struct Ngs2WaveformInfo {
	Ngs2WaveformFormat format;
	uint32_t           data_offset              = 0;
	uint32_t           data_size                = 0;
	uint32_t           loop_begin_position      = 0;
	uint32_t           loop_end_position        = 0;
	uint32_t           num_samples              = 0;
	uint32_t           audio_unit_size          = 0;
	uint32_t           num_audio_unit_samples   = 0;
	uint32_t           num_audio_unit_per_frame = 0;
	uint32_t           audio_frame_size         = 0;
	uint32_t           num_audio_frame_samples  = 0;
	uint32_t           num_delay_samples        = 0;
	uint32_t           num_blocks               = 0;
	Ngs2WaveformBlock  blocks[4];
};

struct Ngs2PanParam {
	float angle     = 0.0f;
	float distance  = 0.0f;
	float fbw_level = 0.0f;
	float lfe_level = 0.0f;
};

struct Ngs2PanWork {
	float    speaker_angles[8] = {};
	float    unit_angle        = 0.0f;
	uint32_t num_speakers      = 0;
};

struct Ngs2GeomVector {
	float x = 0.0f;
	float y = 0.0f;
	float z = 0.0f;
};

struct Ngs2GeomCone {
	float inner_level = 0.0f;
	float inner_angle = 0.0f;
	float outer_level = 0.0f;
	float outer_angle = 0.0f;
};

struct Ngs2GeomRolloff {
	uint32_t model              = 0;
	float    max_distance       = 0.0f;
	float    rolloff_factor     = 0.0f;
	float    reference_distance = 0.0f;
};

struct Ngs2GeomListenerParam {
	Ngs2GeomVector position;
	Ngs2GeomVector orient_front;
	Ngs2GeomVector orient_up;
	Ngs2GeomVector velocity;
	float          sound_speed = 0.0f;
	uint32_t       reserved[2] = {};
};

struct Ngs2GeomListenerWork {
	float          matrix[4][4] = {};
	Ngs2GeomVector velocity;
	float          sound_speed = 0.0f;
	uint32_t       coordinate  = 0;
	uint32_t       reserved[3] = {};
};

struct Ngs2GeomSourceParam {
	Ngs2GeomVector  position;
	Ngs2GeomVector  velocity;
	Ngs2GeomVector  direction;
	Ngs2GeomCone    cone;
	Ngs2GeomRolloff rolloff;
	float           doppler_factor = 0.0f;
	float           fbw_level      = 0.0f;
	float           lfe_level      = 0.0f;
	float           max_level      = 0.0f;
	float           min_level      = 0.0f;
	float           radius         = 0.0f;
	uint32_t        num_speakers   = 0;
	uint32_t        matrix_format  = 0;
	uint32_t        reserved[2]    = {};
};

struct Ngs2GeomA3dAttribute {
	Ngs2GeomVector position;
	float          volume      = 0.0f;
	uint32_t       reserved[4] = {};
};

struct Ngs2GeomAttribute {
	float                pitch_ratio = 0.0f;
	float                level[64]   = {};
	Ngs2GeomA3dAttribute a3d_attrib;
	uint32_t             reserved[4] = {};
};

using Ngs2BufferAllocHandler = int32_t KYTY_SYSV_ABI (*)(Ngs2ContextBufferInfo*);
using Ngs2BufferFreeHandler  = int32_t  KYTY_SYSV_ABI (*)(Ngs2ContextBufferInfo*);

struct Ngs2BufferAllocator {
	Ngs2BufferAllocHandler alloc_handler = nullptr;
	Ngs2BufferFreeHandler  free_handler  = nullptr;
	uintptr_t              user_data     = 0;
};

struct Ngs2Internal {
	Ngs2SystemOption    option;
	Ngs2BufferAllocator allocator;
	Ngs2Internal*       next = nullptr;
	Common::Mutex       mutex;
};

enum class Ngs2RackType {
	Sampler,
	Submixer,
	Mastering,
	Reverb,
	CustomSubmixer,
	CustomMastering,
	CustomSampler,
};

struct Ngs2RackInternal {
	Ngs2Internal*       ngs  = nullptr;
	Ngs2RackInternal*   next = nullptr;
	Ngs2RackType        type = Ngs2RackType::Sampler;
	Ngs2RackOptionUnion option;
	Ngs2BufferAllocator allocator;
};

enum class Ngs2VoicePlayState { Empty, Playing, Paused, Stopped };

enum class Ngs2VoicePlayEvent { None, Play, Pause, Resume, Stop, StopImm, Kill };

struct Ngs2VoiceInternal {
	Ngs2VoicePlayEvent event          = Ngs2VoicePlayEvent::None;
	Ngs2VoicePlayState state          = Ngs2VoicePlayState::Empty;
	Ngs2RackInternal*  rack           = nullptr;
	uintptr_t          callback       = 0;
	uintptr_t          callback_data  = 0;
	uint32_t           callback_flags = 0;
};

struct Ngs2VoiceParamHeader {
	uint16_t size;
	int16_t  next;
	uint32_t id;
};

struct Ngs2VoiceEventParam {
	Ngs2VoiceParamHeader header;
	uint32_t             event_id;
};

struct Ngs2VoicePatchParam {
	Ngs2VoiceParamHeader header;
	uint32_t             port;
	uint32_t             dest_input_id;
	uintptr_t            dest_handle;
};

struct Ngs2VoiceMatrixLevelsParam {
	Ngs2VoiceParamHeader header;
	uint32_t             matrix_id;
	uint32_t             num_levels;
	const float*         levels;
};

struct Ngs2VoicePortMatrixParam {
	Ngs2VoiceParamHeader header;
	uint32_t             port;
	int32_t              matrix_id;
};

struct Ngs2VoicePortVolumeParam {
	Ngs2VoiceParamHeader header;
	uint32_t             port;
	float                level;
};

struct Ngs2VoicePortDelayParam {
	Ngs2VoiceParamHeader header;
	uint32_t             port;
	uint32_t             num_samples;
};

struct Ngs2VoiceCallbackParam {
	Ngs2VoiceParamHeader header;
	uintptr_t            callback;
	uintptr_t            callback_data;
	uint32_t             flags;
	uint32_t             reserved;
};

struct Ngs2VoiceState {
	uint32_t state_flags;
	int32_t  error_code;
};

struct Ngs2SubmixerVoiceState {
	Ngs2VoiceState voice_state;
	float          envelope_height;
	float          peak_height;
	float          compressor_height;
};

struct Ngs2CustomMasteringVoiceState {
	Ngs2VoiceState voice_state;
	uint32_t       reserved;
	uint32_t       reserved2;
};

struct Ngs2SamplerVoiceState {
	Ngs2VoiceState voice_state;
	float          envelope_height;
	float          peak_height;
	uint32_t       reserved;
	uint64_t       num_decoded_samples;
	uint64_t       decoded_data_size;
	uint64_t       user_data;
	const void*    waveform_data;
};

static Ngs2Internal*     g_ngs_list   = nullptr;
static Ngs2RackInternal* g_racks_list = nullptr;

static_assert(sizeof(Ngs2SystemOption) == 144);
static_assert(sizeof(Ngs2RackOption) == 176);
static_assert(sizeof(Ngs2VoiceState) == 8);
static_assert(sizeof(Ngs2SubmixerVoiceState) == 20);
static_assert(sizeof(Ngs2CustomMasteringVoiceState) == 16);
static_assert(sizeof(Ngs2SamplerVoiceState) == 56);

static uint32_t Ngs2GetStateFlags(const Ngs2VoiceInternal* voice) {
	switch (voice->state) {
		case Ngs2VoicePlayState::Empty: return 0;
		case Ngs2VoicePlayState::Playing: return 0x3;
		case Ngs2VoicePlayState::Paused: return 0x5;
		case Ngs2VoicePlayState::Stopped: return 0xb;
	}

	return 0;
}

static Ngs2SystemOption Ngs2DefaultSystemOption() {
	Ngs2SystemOption option {};
	option.size              = sizeof(Ngs2SystemOption);
	option.max_grain_samples = 512;
	option.num_grain_samples = 256;
	option.sample_rate       = 48000;
	return option;
}

int KYTY_SYSV_ABI Ngs2SystemResetOption(Ngs2SystemOption* option) {
	PRINT_NAME();

	EXIT_NOT_IMPLEMENTED(option == nullptr);

	*option = Ngs2DefaultSystemOption();
	return OK;
}

static Ngs2Internal* Ngs2CreateSystemInternal(const Ngs2SystemOption* option, void* host_buffer) {
	auto* ngs = new (host_buffer) Ngs2Internal;

	ngs->option = *option;
	ngs->next   = g_ngs_list;
	g_ngs_list  = ngs;

	return ngs;
}

static bool Ngs2RackIsCustom(Ngs2RackType type) {
	switch (type) {
		case Ngs2RackType::CustomSubmixer:
		case Ngs2RackType::CustomMastering:
		case Ngs2RackType::CustomSampler: return true;
		default: return false;
	}
}

int KYTY_SYSV_ABI Ngs2SystemQueryBufferSize(const Ngs2SystemOption* option,
                                            Ngs2ContextBufferInfo*  buffer_info) {
	PRINT_NAME();

	EXIT_NOT_IMPLEMENTED(buffer_info == nullptr);

	auto default_option = Ngs2DefaultSystemOption();
	if (option == nullptr) {
		option = &default_option;
		LOGF("\t option            = nullptr, using reset defaults\n");
	}

	EXIT_NOT_IMPLEMENTED(option->size != sizeof(Ngs2SystemOption));

	std::memset(buffer_info, 0, sizeof(Ngs2ContextBufferInfo));
	buffer_info->host_buffer_size = sizeof(Ngs2Internal);

	return OK;
}

int KYTY_SYSV_ABI Ngs2SystemCreate(const Ngs2SystemOption*      option,
                                   const Ngs2ContextBufferInfo* buffer_info, uintptr_t* handle) {
	PRINT_NAME();

	EXIT_NOT_IMPLEMENTED(buffer_info == nullptr);
	EXIT_NOT_IMPLEMENTED(handle == nullptr);
	EXIT_NOT_IMPLEMENTED(buffer_info->host_buffer == nullptr);
	EXIT_NOT_IMPLEMENTED(buffer_info->host_buffer_size < sizeof(Ngs2Internal));

	auto default_option = Ngs2DefaultSystemOption();
	if (option == nullptr) {
		option = &default_option;
		LOGF("\t option            = nullptr, using reset defaults\n");
	}

	EXIT_NOT_IMPLEMENTED(option->size != sizeof(Ngs2SystemOption));

	auto* ngs = Ngs2CreateSystemInternal(option, buffer_info->host_buffer);

	*handle = reinterpret_cast<uintptr_t>(ngs);

	return OK;
}

static void Ngs2FillDefaultRackOption(uint32_t rack_id, Ngs2RackOptionUnion* option) {
	EXIT_NOT_IMPLEMENTED(option == nullptr);

	*option = {};

	switch (rack_id) {
		case 0x1000:
			option->sampler.rack_option.size                   = sizeof(Ngs2SamplerRackOption);
			option->sampler.rack_option.max_grain_samples      = 512;
			option->sampler.rack_option.max_voices             = 256;
			option->sampler.rack_option.max_input_delay_blocks = 0;
			option->sampler.rack_option.max_matrices           = 1;
			option->sampler.rack_option.max_ports              = 8;
			option->sampler.max_channel_works                  = 256;
			option->sampler.max_codec_caches                   = 32;
			option->sampler.max_waveform_blocks                = 4;
			option->sampler.max_envelope_points                = 4;
			option->sampler.max_filters                        = 8;
			option->sampler.max_atrac9_decoders                = 256;
			option->sampler.max_atrac9_channel_works           = 256;
			option->sampler.max_ajm_atrac9_decoders            = 0;
			option->sampler.num_peak_meter_blocks              = 8;
			break;
		case 0x2000:
			option->submixer.rack_option.size                   = sizeof(Ngs2SubmixerRackOption);
			option->submixer.rack_option.max_grain_samples      = 512;
			option->submixer.rack_option.max_voices             = 1;
			option->submixer.rack_option.max_input_delay_blocks = 1;
			option->submixer.rack_option.max_matrices           = 1;
			option->submixer.rack_option.max_ports              = 8;
			option->submixer.max_channels                       = 8;
			option->submixer.max_envelope_points                = 4;
			option->submixer.max_filters                        = 8;
			option->submixer.max_inputs                         = 1;
			option->submixer.num_peak_meter_blocks              = 8;
			break;
		case 0x2001:
			option->reverb.rack_option.size                   = sizeof(Ngs2ReverbRackOption);
			option->reverb.rack_option.max_grain_samples      = 512;
			option->reverb.rack_option.max_voices             = 1;
			option->reverb.rack_option.max_input_delay_blocks = 1;
			option->reverb.rack_option.max_matrices           = 1;
			option->reverb.rack_option.max_ports              = 8;
			option->reverb.max_channels                       = 8;
			option->reverb.reverb_size                        = 1;
			break;
		case 0x3000:
			option->mastering.rack_option.size                   = sizeof(Ngs2MasteringRackOption);
			option->mastering.rack_option.max_grain_samples      = 512;
			option->mastering.rack_option.max_voices             = 1;
			option->mastering.rack_option.max_input_delay_blocks = 1;
			option->mastering.rack_option.max_matrices           = 0;
			option->mastering.rack_option.max_ports              = 0;
			option->mastering.max_channels                       = 8;
			option->mastering.num_peak_meter_blocks              = 8;
			break;
		case 0x4002:
			// FIXME: Temporary PS5 progress fallback. This mirrors Prospero reset helper's
			// common custom-submixer defaults, but the custom module internals are still stubbed.
			option->custom_submixer.custom_rack_option.rack_option.size =
			    sizeof(Ngs2CustomSubmixerRackOption);
			option->custom_submixer.custom_rack_option.rack_option.max_grain_samples      = 512;
			option->custom_submixer.custom_rack_option.rack_option.max_voices             = 1;
			option->custom_submixer.custom_rack_option.rack_option.max_input_delay_blocks = 1;
			option->custom_submixer.custom_rack_option.rack_option.max_matrices           = 1;
			option->custom_submixer.custom_rack_option.rack_option.max_ports              = 8;
			option->custom_submixer.custom_rack_option.num_buffers                        = 1;
			option->custom_submixer.max_channels                                          = 8;
			option->custom_submixer.max_inputs                                            = 1;
			break;
		case 0x4001:
			option->custom_sampler.custom_rack_option.rack_option.size =
			    sizeof(Ngs2CustomSamplerRackOption);
			option->custom_sampler.custom_rack_option.rack_option.max_grain_samples      = 512;
			option->custom_sampler.custom_rack_option.rack_option.max_voices             = 256;
			option->custom_sampler.custom_rack_option.rack_option.max_input_delay_blocks = 0;
			option->custom_sampler.custom_rack_option.rack_option.max_matrices           = 1;
			option->custom_sampler.custom_rack_option.rack_option.max_ports              = 8;
			option->custom_sampler.custom_rack_option.num_buffers                        = 1;
			option->custom_sampler.max_channel_works                                     = 256;
			option->custom_sampler.max_waveform_blocks                                   = 4;
			option->custom_sampler.max_atrac9_decoders                                   = 256;
			option->custom_sampler.max_atrac9_channel_works                              = 256;
			option->custom_sampler.max_ajm_atrac9_decoders                               = 0;
			option->custom_sampler.max_codec_caches                                      = 32;
			break;
		default: EXIT("unknown rack_id for default option: 0x%" PRIx32 "\n", rack_id);
	}
}

int KYTY_SYSV_ABI Ngs2RackQueryBufferSize(uint32_t rack_id, const Ngs2RackOption* option,
                                          Ngs2ContextBufferInfo* buffer_info) {
	PRINT_NAME();

	EXIT_NOT_IMPLEMENTED(buffer_info == nullptr);

	Ngs2RackOptionUnion default_option {};
	if (option == nullptr) {
		Ngs2FillDefaultRackOption(rack_id, &default_option);
		option = &default_option.common;
		LOGF("\t option     = nullptr, using reset defaults for rack_id 0x%" PRIx32 "\n", rack_id);
	}

	LOGF("\t rack_id    = 0x%" PRIx32 "\n"
	     "\t max_voices = %u\n",
	     rack_id, option->max_voices);

	buffer_info->host_buffer_size =
	    sizeof(Ngs2RackInternal) + sizeof(Ngs2VoiceInternal) * option->max_voices;

	return OK;
}

int KYTY_SYSV_ABI Ngs2SystemCreateWithAllocator(const Ngs2SystemOption*    option,
                                                const Ngs2BufferAllocator* allocator,
                                                uintptr_t*                 handle) {
	PRINT_NAME();

	EXIT_NOT_IMPLEMENTED(allocator == nullptr);
	EXIT_NOT_IMPLEMENTED(handle == nullptr);
	EXIT_NOT_IMPLEMENTED(allocator->alloc_handler == nullptr);
	EXIT_NOT_IMPLEMENTED(allocator->free_handler == nullptr);

	auto default_option = Ngs2DefaultSystemOption();
	if (option == nullptr) {
		option = &default_option;
		LOGF("\t option            = nullptr, using reset defaults\n");
	}

	EXIT_NOT_IMPLEMENTED(option->size != sizeof(Ngs2SystemOption));

	LOGF("\t name              = %.64s\n"
	     "\t flags             = %u\n"
	     "\t max_grain_samples = %u\n"
	     "\t num_grain_samples = %u\n"
	     "\t sample_rate       = %u\n"
	     "\t max_voice_channels = %u\n"
	     "\t alloc_handler     = 0x%016" PRIx64 "\n"
	     "\t free_handler      = 0x%016" PRIx64 "\n"
	     "\t user_data         = 0x%016" PRIx64 "\n",
	     option->name, option->flags, option->max_grain_samples, option->num_grain_samples,
	     option->sample_rate, option->max_voice_channels,
	     reinterpret_cast<uint64_t>(allocator->alloc_handler),
	     reinterpret_cast<uint64_t>(allocator->free_handler),
	     static_cast<uint64_t>(allocator->user_data));

	Ngs2ContextBufferInfo buf {};
	buf.host_buffer      = nullptr;
	buf.host_buffer_size = sizeof(Ngs2Internal);
	buf.user_data        = allocator->user_data;

	int result = allocator->alloc_handler(&buf);

	EXIT_NOT_IMPLEMENTED(result != OK);
	EXIT_NOT_IMPLEMENTED(buf.host_buffer == nullptr);

	auto* ngs      = Ngs2CreateSystemInternal(option, buf.host_buffer);
	ngs->allocator = *allocator;

	*handle = reinterpret_cast<uintptr_t>(ngs);

	return OK;
}

int KYTY_SYSV_ABI Ngs2SystemSetGrainSamples(uintptr_t system_handle, uint32_t num_samples) {
	PRINT_NAME();
	LOGF("\t system_handle = 0x%016" PRIx64 "\n"
	     "\t num_samples   = %u\n",
	     static_cast<uint64_t>(system_handle), num_samples);

	EXIT_NOT_IMPLEMENTED(system_handle == 0);

	auto* ngs                     = reinterpret_cast<Ngs2Internal*>(system_handle);
	ngs->option.num_grain_samples = num_samples;

	return OK;
}

int KYTY_SYSV_ABI Ngs2SystemDestroy(uintptr_t system_handle, Ngs2ContextBufferInfo* buffer_info) {
	PRINT_NAME();
	LOGF("\t system_handle = 0x%016" PRIx64 "\n", static_cast<uint64_t>(system_handle));

	if (buffer_info != nullptr) {
		std::memset(buffer_info, 0, sizeof(Ngs2ContextBufferInfo));
	}

	return OK;
}

int KYTY_SYSV_ABI Ngs2RackCreate(uintptr_t system_handle, uint32_t rack_id,
                                 const Ngs2RackOption*        option,
                                 const Ngs2ContextBufferInfo* buffer_info, uintptr_t* handle) {
	PRINT_NAME();

	EXIT_NOT_IMPLEMENTED(buffer_info == nullptr);
	EXIT_NOT_IMPLEMENTED(handle == nullptr);
	EXIT_NOT_IMPLEMENTED(buffer_info->host_buffer == nullptr);
	EXIT_NOT_IMPLEMENTED(buffer_info->host_buffer_size == 0);
	EXIT_NOT_IMPLEMENTED(system_handle == 0);

	Ngs2RackOptionUnion default_option {};
	if (option == nullptr) {
		Ngs2FillDefaultRackOption(rack_id, &default_option);
		option = &default_option.common;
		LOGF("\t option                 = nullptr, using reset defaults for rack_id 0x%" PRIx32
		     "\n",
		     rack_id);
	}

	EXIT_NOT_IMPLEMENTED(option->size < sizeof(Ngs2RackOption));

	LOGF("\t rack_id                = 0x%" PRIx32 "\n"
	     "\t name                   = %.64s\n"
	     "\t flags                  = %u\n"
	     "\t max_grain_samples      = %u\n"
	     "\t max_voices             = %u\n"
	     "\t max_input_delay_blocks = %u\n"
	     "\t max_matrices           = %u\n"
	     "\t max_ports              = %u\n"
	     "\t max_voice_channels     = %u\n"
	     "\t max_output_channels    = %u\n"
	     "\t host_buffer            = 0x%016" PRIx64 "\n"
	     "\t host_buffer_size      = 0x%016" PRIx64 "\n",
	     rack_id, option->name, option->flags, option->max_grain_samples, option->max_voices,
	     option->max_input_delay_blocks, option->max_matrices, option->max_ports,
	     option->max_voice_channels, option->max_output_channels,
	     reinterpret_cast<uint64_t>(buffer_info->host_buffer),
	     static_cast<uint64_t>(buffer_info->host_buffer_size));

	auto* ngs    = reinterpret_cast<Ngs2Internal*>(system_handle);
	auto* rack   = static_cast<Ngs2RackInternal*>(buffer_info->host_buffer);
	auto* voices = reinterpret_cast<Ngs2VoiceInternal*>(rack + 1);

	Common::LockGuard lock(ngs->mutex);

	switch (rack_id) {
		case 0x1000:
			EXIT_NOT_IMPLEMENTED(option->size != sizeof(Ngs2SamplerRackOption));
			rack->option.sampler = *reinterpret_cast<const Ngs2SamplerRackOption*>(option);
			rack->type           = Ngs2RackType::Sampler;
			break;
		case 0x2000:
			EXIT_NOT_IMPLEMENTED(option->size != sizeof(Ngs2SubmixerRackOption));
			rack->option.submixer = *reinterpret_cast<const Ngs2SubmixerRackOption*>(option);
			rack->type            = Ngs2RackType::Submixer;
			break;
		case 0x2001:
			EXIT_NOT_IMPLEMENTED(option->size != sizeof(Ngs2ReverbRackOption));
			rack->option.reverb = *reinterpret_cast<const Ngs2ReverbRackOption*>(option);
			rack->type          = Ngs2RackType::Reverb;
			break;
		case 0x3000:
			EXIT_NOT_IMPLEMENTED(option->size != sizeof(Ngs2MasteringRackOption));
			rack->option.mastering = *reinterpret_cast<const Ngs2MasteringRackOption*>(option);
			rack->type             = Ngs2RackType::Mastering;
			break;
		case 0x4002:
			EXIT_NOT_IMPLEMENTED(option->size != sizeof(Ngs2CustomSubmixerRackOption));
			rack->option.custom_submixer =
			    *reinterpret_cast<const Ngs2CustomSubmixerRackOption*>(option);
			rack->type = Ngs2RackType::CustomSubmixer;
			break;
		case 0x4003:
			EXIT_NOT_IMPLEMENTED(option->size != sizeof(Ngs2CustomMasteringRackOption));
			rack->option.custom_mastering =
			    *reinterpret_cast<const Ngs2CustomMasteringRackOption*>(option);
			rack->type = Ngs2RackType::CustomMastering;
			break;
		case 0x4001:
			EXIT_NOT_IMPLEMENTED(option->size != sizeof(Ngs2CustomSamplerRackOption));
			rack->option.custom_sampler =
			    *reinterpret_cast<const Ngs2CustomSamplerRackOption*>(option);
			rack->type = Ngs2RackType::CustomSampler;
			break;
		default: EXIT("unknown rack_id: 0x%" PRIx32 "\n", rack_id);
	}

	LOGF("\t type                   = %s\n", Common::EnumName(rack->type).c_str());

	rack->allocator = Ngs2BufferAllocator();
	rack->ngs       = ngs;

	rack->next   = g_racks_list;
	g_racks_list = rack;

	for (uint32_t i = 0; i < option->max_voices; i++) {
		voices[i].rack  = rack;
		voices[i].event = Ngs2VoicePlayEvent::None;
		voices[i].state = Ngs2VoicePlayState::Empty;
	}

	*handle = reinterpret_cast<uintptr_t>(rack);

	return OK;
}

int KYTY_SYSV_ABI Ngs2RackCreateWithAllocator(uintptr_t system_handle, uint32_t rack_id,
                                              const Ngs2RackOption*      option,
                                              const Ngs2BufferAllocator* allocator,
                                              uintptr_t*                 handle) {
	PRINT_NAME();

	EXIT_NOT_IMPLEMENTED(allocator == nullptr);
	EXIT_NOT_IMPLEMENTED(handle == nullptr);
	EXIT_NOT_IMPLEMENTED(allocator->alloc_handler == nullptr);
	EXIT_NOT_IMPLEMENTED(allocator->free_handler == nullptr);
	EXIT_NOT_IMPLEMENTED(system_handle == 0);

	Ngs2RackOptionUnion default_option {};
	if (option == nullptr) {
		Ngs2FillDefaultRackOption(rack_id, &default_option);
		option = &default_option.common;
		LOGF("\t option                 = nullptr, using reset defaults for rack_id 0x%" PRIx32
		     "\n",
		     rack_id);
	}

	EXIT_NOT_IMPLEMENTED(option->size < sizeof(Ngs2RackOption));

	LOGF("\t rack_id                = 0x%" PRIx32 "\n"
	     "\t name                   = %.64s\n"
	     "\t flags                  = %u\n"
	     "\t max_grain_samples      = %u\n"
	     "\t max_voices             = %u\n"
	     "\t max_input_delay_blocks = %u\n"
	     "\t max_matrices           = %u\n"
	     "\t max_ports              = %u\n"
	     "\t max_voice_channels     = %u\n"
	     "\t max_output_channels    = %u\n"
	     "\t alloc_handler          = 0x%016" PRIx64 "\n"
	     "\t free_handler           = 0x%016" PRIx64 "\n"
	     "\t user_data              = 0x%016" PRIx64 "\n",
	     rack_id, option->name, option->flags, option->max_grain_samples, option->max_voices,
	     option->max_input_delay_blocks, option->max_matrices, option->max_ports,
	     option->max_voice_channels, option->max_output_channels,
	     reinterpret_cast<uint64_t>(allocator->alloc_handler),
	     reinterpret_cast<uint64_t>(allocator->free_handler),
	     static_cast<uint64_t>(allocator->user_data));

	Ngs2ContextBufferInfo buf {};
	buf.host_buffer      = nullptr;
	buf.host_buffer_size = 0;
	buf.user_data        = allocator->user_data;

	Ngs2RackQueryBufferSize(rack_id, option, &buf);

	EXIT_NOT_IMPLEMENTED(buf.host_buffer_size == 0);

	int result = allocator->alloc_handler(&buf);

	EXIT_NOT_IMPLEMENTED(result != OK);
	EXIT_NOT_IMPLEMENTED(buf.host_buffer == nullptr);

	result = Ngs2RackCreate(system_handle, rack_id, option, &buf, handle);

	if (result == OK) {
		auto* rack      = static_cast<Ngs2RackInternal*>(buf.host_buffer);
		rack->allocator = *allocator;
	}

	return result;
}

int KYTY_SYSV_ABI Ngs2RackDestroy(uintptr_t rack_handle, Ngs2ContextBufferInfo* buffer_info) {
	PRINT_NAME();
	LOGF("\t rack_handle = 0x%016" PRIx64 "\n", static_cast<uint64_t>(rack_handle));

	if (buffer_info != nullptr) {
		std::memset(buffer_info, 0, sizeof(Ngs2ContextBufferInfo));
	}

	return OK;
}

int KYTY_SYSV_ABI Ngs2RackLock(uintptr_t rack_handle) {
	PRINT_NAME();
	LOGF("\t rack_handle = 0x%016" PRIx64 "\n", static_cast<uint64_t>(rack_handle));

	EXIT_NOT_IMPLEMENTED(rack_handle == 0);

	auto* rack = reinterpret_cast<Ngs2RackInternal*>(rack_handle);

	EXIT_NOT_IMPLEMENTED(rack->ngs == nullptr);

	rack->ngs->mutex.Lock();

	return OK;
}

int KYTY_SYSV_ABI Ngs2RackUnlock(uintptr_t rack_handle) {
	PRINT_NAME();
	LOGF("\t rack_handle = 0x%016" PRIx64 "\n", static_cast<uint64_t>(rack_handle));

	EXIT_NOT_IMPLEMENTED(rack_handle == 0);

	auto* rack = reinterpret_cast<Ngs2RackInternal*>(rack_handle);

	EXIT_NOT_IMPLEMENTED(rack->ngs == nullptr);

	rack->ngs->mutex.Unlock();

	return OK;
}

int KYTY_SYSV_ABI Ngs2SystemRender(uintptr_t system_handle, const Ngs2RenderBufferInfo* buffer_info,
                                   uint32_t num_buffer_info) {
	static std::atomic_uint32_t render_log_count = 0;
	const auto log_index     = render_log_count.fetch_add(1, std::memory_order_relaxed);
	const bool log_this_call = (log_index < 16 || (log_index % 600) == 0);

	if (log_this_call) {
		PRINT_NAME();
		LOGF("\t call_count      = %" PRIu32 "\n", log_index + 1);
	}

	EXIT_NOT_IMPLEMENTED(buffer_info == nullptr);
	EXIT_NOT_IMPLEMENTED(system_handle == 0);
	EXIT_NOT_IMPLEMENTED(num_buffer_info == 0);

	auto* ngs = reinterpret_cast<Ngs2Internal*>(system_handle);

	Common::LockGuard lock(ngs->mutex);

	for (uint32_t i = 0; i < num_buffer_info; i++) {
		if (buffer_info[i].buffer != nullptr && buffer_info[i].buffer_size != 0) {
			std::memset(buffer_info[i].buffer, 0, buffer_info[i].buffer_size);
		}
	}

	for (auto* rack = g_racks_list; rack != nullptr; rack = rack->next) {
		if (rack->ngs == ngs) {
			auto* voices = reinterpret_cast<Ngs2VoiceInternal*>(rack + 1);

			for (uint32_t i = 0; i < rack->option.common.max_voices; i++) {
				auto& voice = voices[i];
				switch (voice.event) {
					case Ngs2VoicePlayEvent::None:
						if (voice.state == Ngs2VoicePlayState::Playing ||
						    voice.state == Ngs2VoicePlayState::Stopped) {
							voice.state = Ngs2VoicePlayState::Empty;
						}
						break;
					case Ngs2VoicePlayEvent::Play:
						if (voice.state == Ngs2VoicePlayState::Empty) {
							voice.state = Ngs2VoicePlayState::Playing;
						}
						break;
					case Ngs2VoicePlayEvent::Pause:
						if (voice.state == Ngs2VoicePlayState::Playing) {
							voice.state = Ngs2VoicePlayState::Paused;
						}
						break;
					case Ngs2VoicePlayEvent::Resume:
						if (voice.state == Ngs2VoicePlayState::Paused) {
							voice.state = Ngs2VoicePlayState::Playing;
						}
						break;
					case Ngs2VoicePlayEvent::Stop:
						if (voice.state == Ngs2VoicePlayState::Playing) {
							voice.state = Ngs2VoicePlayState::Stopped;
						}
						break;
					case Ngs2VoicePlayEvent::StopImm:
					case Ngs2VoicePlayEvent::Kill: voice.state = Ngs2VoicePlayState::Empty; break;
				}
				voice.event = Ngs2VoicePlayEvent::None;
			}
		}
	}

	return OK;
}

int KYTY_SYSV_ABI Ngs2ParseWaveformData(const void* data, size_t data_size,
                                        Ngs2WaveformInfo* info) {
	PRINT_NAME();
	LOGF("\t data = 0x%016" PRIx64 ", data_size = 0x%016" PRIx64 "\n",
	     reinterpret_cast<uint64_t>(data), static_cast<uint64_t>(data_size));

	EXIT_NOT_IMPLEMENTED(info == nullptr);

	std::memset(info, 0, sizeof(Ngs2WaveformInfo));
	info->format.waveform_type = 0x80;
	info->format.num_channels  = 1;
	info->format.sample_rate   = 48000;
	info->data_size =
	    static_cast<uint32_t>(std::min<size_t>(data_size, std::numeric_limits<uint32_t>::max()));
	info->num_audio_unit_samples   = 1;
	info->num_audio_unit_per_frame = 1;
	info->num_audio_frame_samples  = 1;
	return OK;
}

int KYTY_SYSV_ABI Ngs2CalcWaveformBlock(const Ngs2WaveformFormat* format, uint32_t sample_pos,
                                        uint32_t num_samples, Ngs2WaveformBlock* block) {
	PRINT_NAME();
	LOGF("\t format = 0x%016" PRIx64 ", sample_pos = %" PRIu32 ", num_samples = %" PRIu32 "\n",
	     reinterpret_cast<uint64_t>(format), sample_pos, num_samples);

	EXIT_NOT_IMPLEMENTED(block == nullptr);

	std::memset(block, 0, sizeof(Ngs2WaveformBlock));
	block->num_samples = num_samples;
	return OK;
}

int KYTY_SYSV_ABI Ngs2PanInit(Ngs2PanWork* work, const float* speaker_angles, float unit_angle,
                              uint32_t num_speakers) {
	PRINT_NAME();
	LOGF("\t work = 0x%016" PRIx64 ", num_speakers = %" PRIu32 "\n",
	     reinterpret_cast<uint64_t>(work), num_speakers);

	EXIT_NOT_IMPLEMENTED(work == nullptr);

	std::memset(work, 0, sizeof(Ngs2PanWork));
	work->unit_angle   = unit_angle;
	work->num_speakers = std::min<uint32_t>(num_speakers, 8);
	if (speaker_angles != nullptr) {
		for (uint32_t i = 0; i < work->num_speakers; i++) {
			work->speaker_angles[i] = speaker_angles[i];
		}
	}
	return OK;
}

int KYTY_SYSV_ABI Ngs2PanGetVolumeMatrix(Ngs2PanWork* work, const Ngs2PanParam* params,
                                         uint32_t num_params, uint32_t matrix_format,
                                         float* out_volume_matrix) {
	PRINT_NAME();
	LOGF("\t work = 0x%016" PRIx64 ", params = 0x%016" PRIx64 ", num_params = %" PRIu32
	     ", matrix_format = %" PRIu32 "\n",
	     reinterpret_cast<uint64_t>(work), reinterpret_cast<uint64_t>(params), num_params,
	     matrix_format);

	EXIT_NOT_IMPLEMENTED(out_volume_matrix == nullptr && num_params != 0);

	const auto channels = (matrix_format == 0 ? 2u : std::min<uint32_t>(matrix_format, 8));
	for (uint32_t p = 0; p < num_params; p++) {
		for (uint32_t c = 0; c < channels; c++) {
			out_volume_matrix[p * channels + c] = (c == 0 ? 1.0f : 0.0f);
		}
	}

	return OK;
}

int KYTY_SYSV_ABI Ngs2GeomResetListenerParam(Ngs2GeomListenerParam* out_listener_param) {
	PRINT_NAME();

	EXIT_NOT_IMPLEMENTED(out_listener_param == nullptr);

	std::memset(out_listener_param, 0, sizeof(Ngs2GeomListenerParam));
	out_listener_param->orient_front.z = 1.0f;
	out_listener_param->orient_up.y    = 1.0f;
	out_listener_param->sound_speed    = 343.0f;

	return OK;
}

int KYTY_SYSV_ABI Ngs2GeomResetSourceParam(Ngs2GeomSourceParam* out_source_param) {
	PRINT_NAME();

	EXIT_NOT_IMPLEMENTED(out_source_param == nullptr);

	std::memset(out_source_param, 0, sizeof(Ngs2GeomSourceParam));
	out_source_param->direction.z                = 1.0f;
	out_source_param->cone.inner_level           = 1.0f;
	out_source_param->cone.inner_angle           = 360.0f;
	out_source_param->cone.outer_level           = 1.0f;
	out_source_param->cone.outer_angle           = 360.0f;
	out_source_param->rolloff.model              = 0;
	out_source_param->rolloff.max_distance       = 1000000.0f;
	out_source_param->rolloff.rolloff_factor     = 1.0f;
	out_source_param->rolloff.reference_distance = 1.0f;
	out_source_param->doppler_factor             = 1.0f;
	out_source_param->fbw_level                  = 1.0f;
	out_source_param->lfe_level                  = 1.0f;
	out_source_param->max_level                  = 1.0f;
	out_source_param->min_level                  = 0.0f;
	out_source_param->num_speakers               = 2;
	out_source_param->matrix_format              = 2;

	return OK;
}

int KYTY_SYSV_ABI Ngs2GeomCalcListener(const Ngs2GeomListenerParam* param,
                                       Ngs2GeomListenerWork* out_work, uint32_t flags) {
	PRINT_NAME();
	LOGF("\t flags = 0x%08" PRIx32 "\n", flags);

	EXIT_NOT_IMPLEMENTED(param == nullptr);
	EXIT_NOT_IMPLEMENTED(out_work == nullptr);

	std::memset(out_work, 0, sizeof(Ngs2GeomListenerWork));
	for (uint32_t i = 0; i < 4; i++) {
		out_work->matrix[i][i] = 1.0f;
	}
	out_work->velocity    = param->velocity;
	out_work->sound_speed = (param->sound_speed > 0.0f ? param->sound_speed : 343.0f);
	out_work->coordinate  = flags & 0x1u;

	return OK;
}

int KYTY_SYSV_ABI Ngs2GeomApply(const Ngs2GeomListenerWork* listener,
                                const Ngs2GeomSourceParam* source, Ngs2GeomAttribute* out_attrib,
                                uint32_t flags) {
	PRINT_NAME();
	LOGF("\t flags = 0x%08" PRIx32 "\n", flags);

	EXIT_NOT_IMPLEMENTED(listener == nullptr);
	EXIT_NOT_IMPLEMENTED(source == nullptr);
	EXIT_NOT_IMPLEMENTED(out_attrib == nullptr);

	std::memset(out_attrib, 0, sizeof(Ngs2GeomAttribute));
	out_attrib->pitch_ratio         = 1.0f;
	out_attrib->a3d_attrib.position = source->position;
	out_attrib->a3d_attrib.volume   = std::max(source->min_level, source->max_level);

	const auto channels =
	    std::min<uint32_t>((source->matrix_format == 0 ? 2u : source->matrix_format), 8);
	const auto level = (source->max_level > 0.0f ? source->max_level : 1.0f);
	for (uint32_t ch = 0; ch < channels; ch++) {
		out_attrib->level[ch * 8 + ch] = level;
	}

	return OK;
}

int KYTY_SYSV_ABI Ngs2RackGetVoiceHandle(uintptr_t rack_handle, uint32_t voice_id,
                                         uintptr_t* handle) {
	PRINT_NAME();

	EXIT_NOT_IMPLEMENTED(handle == nullptr);
	EXIT_NOT_IMPLEMENTED(rack_handle == 0);

	LOGF("\t voice_id = %u\n", voice_id);

	auto* rack   = reinterpret_cast<Ngs2RackInternal*>(rack_handle);
	auto* voices = reinterpret_cast<Ngs2VoiceInternal*>(rack_handle + sizeof(Ngs2RackInternal));

	if (voice_id >= rack->option.common.max_voices) {
		LOGF("\t warning: voice_id %u >= max_voices %u, using last available stub voice\n",
		     voice_id, rack->option.common.max_voices);
		if (rack->option.common.max_voices == 0) {
			return -1;
		}
		voice_id = rack->option.common.max_voices - 1;
	}

	EXIT_IF(voices[voice_id].rack != rack);

	*handle = reinterpret_cast<uintptr_t>(voices + voice_id);

	return OK;
}

// NOLINTNEXTLINE(readability-function-cognitive-complexity)
int KYTY_SYSV_ABI Ngs2VoiceControl(uintptr_t voice_handle, const Ngs2VoiceParamHeader* param_list) {
	PRINT_NAME();

	EXIT_NOT_IMPLEMENTED(param_list == nullptr);
	EXIT_NOT_IMPLEMENTED(voice_handle == 0);

	auto* voice = reinterpret_cast<Ngs2VoiceInternal*>(voice_handle);

	Common::LockGuard lock(voice->rack->ngs->mutex);

	const auto* param = param_list;

	for (;;) {
		LOGF("\t id   = 0x%08" PRIx32 "\n"
		     "\t size = %" PRIu16 "\n"
		     "\t next = %" PRId16 "\n",
		     param->id, param->size, param->next);

		auto rack_id = param->id >> 16u;

		EXIT_NOT_IMPLEMENTED(((param->id >> 15u) & 0x1u) != 0);

		switch (rack_id) {
			case 0x0000: {
				auto cid = param->id & 0x7fffu;
				switch (cid) {
					case 0x0001: {
						EXIT_NOT_IMPLEMENTED(param->size != sizeof(Ngs2VoiceMatrixLevelsParam));
						const auto* ml = reinterpret_cast<const Ngs2VoiceMatrixLevelsParam*>(param);
						LOGF("\t matrix_id  = %u\n"
						     "\t num_levels = %u\n"
						     "\t levels     = 0x%016" PRIx64 "\n",
						     ml->matrix_id, ml->num_levels, reinterpret_cast<uint64_t>(ml->levels));
						break;
					}
					case 0x0002: {
						EXIT_NOT_IMPLEMENTED(param->size != sizeof(Ngs2VoicePortVolumeParam));
						const auto* volume =
						    reinterpret_cast<const Ngs2VoicePortVolumeParam*>(param);
						LOGF("\t port  = %u\n"
						     "\t level = %f\n",
						     volume->port, volume->level);
						break;
					}
					case 0x0003: {
						EXIT_NOT_IMPLEMENTED(param->size != sizeof(Ngs2VoicePortMatrixParam));
						const auto* pm = reinterpret_cast<const Ngs2VoicePortMatrixParam*>(param);
						LOGF("\t port      = %u\n"
						     "\t matrix_id = %d\n",
						     pm->port, pm->matrix_id);
						break;
					}
					case 0x0004: {
						EXIT_NOT_IMPLEMENTED(param->size != sizeof(Ngs2VoicePortDelayParam));
						const auto* delay = reinterpret_cast<const Ngs2VoicePortDelayParam*>(param);
						LOGF("\t port        = %u\n"
						     "\t num_samples = %u\n",
						     delay->port, delay->num_samples);
						break;
					}
					case 0x0005: {
						EXIT_NOT_IMPLEMENTED(param->size != sizeof(Ngs2VoicePatchParam));
						const auto* patch = reinterpret_cast<const Ngs2VoicePatchParam*>(param);
						LOGF("\t connect->port          = %u\n"
						     "\t connect->dest_input_id = %u\n"
						     "\t connect->dest_handle   = 0x%016" PRIx64 "\n",
						     patch->port, patch->dest_input_id, patch->dest_handle);
						break;
					}
					case 0x0006: {
						EXIT_NOT_IMPLEMENTED(param->size != sizeof(Ngs2VoiceEventParam));
						const auto* event = reinterpret_cast<const Ngs2VoiceEventParam*>(param);
						switch (event->event_id) {
							case 0x0001: voice->event = Ngs2VoicePlayEvent::Play; break;
							case 0x0002: voice->event = Ngs2VoicePlayEvent::Stop; break;
							case 0x0004: voice->event = Ngs2VoicePlayEvent::StopImm; break;
							case 0x0008: voice->event = Ngs2VoicePlayEvent::Kill; break;
							case 0x0010: voice->event = Ngs2VoicePlayEvent::Pause; break;
							case 0x0020: voice->event = Ngs2VoicePlayEvent::Resume; break;
							default: EXIT("unknown event_id: 0x%08" PRIx32 "\n", event->event_id);
						}
						LOGF("\t event = %u\n", event->event_id);
						break;
					}
					case 0x0007: {
						EXIT_NOT_IMPLEMENTED(param->size != sizeof(Ngs2VoiceCallbackParam));
						const auto* callback =
						    reinterpret_cast<const Ngs2VoiceCallbackParam*>(param);
						voice->callback       = callback->callback;
						voice->callback_data  = callback->callback_data;
						voice->callback_flags = callback->flags;
						LOGF("\t callback      = 0x%016" PRIx64 "\n"
						     "\t callback_data = 0x%016" PRIx64 "\n"
						     "\t flags         = 0x%08" PRIx32 "\n",
						     static_cast<uint64_t>(voice->callback),
						     static_cast<uint64_t>(voice->callback_data), voice->callback_flags);
						break;
					}
					default: EXIT("unknown id: 0x%04" PRIx32 "\n", cid);
				}
				break;
			}
			case 0x1000: EXIT_NOT_IMPLEMENTED(voice->rack->type != Ngs2RackType::Sampler); break;
			case 0x2000: EXIT_NOT_IMPLEMENTED(voice->rack->type != Ngs2RackType::Submixer); break;
			case 0x2001: EXIT_NOT_IMPLEMENTED(voice->rack->type != Ngs2RackType::Reverb); break;
			case 0x3000: EXIT_NOT_IMPLEMENTED(voice->rack->type != Ngs2RackType::Mastering); break;
			case 0x4000: {
				EXIT_NOT_IMPLEMENTED(!Ngs2RackIsCustom(voice->rack->type));
				auto cid       = param->id & 0xffffu;
				auto module_id = (cid >> 8u) & 0xffu;
				auto ctl_id    = (cid >> 5u) & 0x7u;
				auto module_no = cid & 0x1fu;
				LOGF("\t custom module_id = 0x%02" PRIx32 ", ctl_id = 0x%" PRIx32
				     ", module_no = %" PRIu32 "\n",
				     module_id, ctl_id, module_no);
				break;
			}
			case 0x4001:
				EXIT_NOT_IMPLEMENTED(voice->rack->type != Ngs2RackType::CustomSampler);
				break;
			case 0x4002:
				EXIT_NOT_IMPLEMENTED(voice->rack->type != Ngs2RackType::CustomSubmixer);
				break;
			case 0x4003:
				EXIT_NOT_IMPLEMENTED(voice->rack->type != Ngs2RackType::CustomMastering);
				break;
			default: EXIT("unknown rack_id: 0x%" PRIx32 "\n", rack_id);
		}

		if (param->next == 0) {
			break;
		}
		param = reinterpret_cast<const Ngs2VoiceParamHeader*>(reinterpret_cast<uintptr_t>(param) +
		                                                      param->next);
	}

	return OK;
}

int KYTY_SYSV_ABI Ngs2VoiceRunCommands(uintptr_t voice_handle, const void* commands,
                                       uint32_t num_commands, uint32_t flags) {
	PRINT_NAME();

	(void)voice_handle;
	(void)commands;
	(void)num_commands;
	(void)flags;

	return OK;
}

int KYTY_SYSV_ABI Ngs2VoiceGetState(uintptr_t voice_handle, Ngs2VoiceState* state,
                                    size_t state_size) {
	PRINT_NAME();

	EXIT_NOT_IMPLEMENTED(state == nullptr);
	EXIT_NOT_IMPLEMENTED(voice_handle == 0);

	auto* voice = reinterpret_cast<Ngs2VoiceInternal*>(voice_handle);

	Common::LockGuard lock(voice->rack->ngs->mutex);

	switch (voice->rack->type) {
		case Ngs2RackType::Submixer: {
			EXIT_NOT_IMPLEMENTED(state_size != sizeof(Ngs2SubmixerVoiceState));
			auto* submixer = reinterpret_cast<Ngs2SubmixerVoiceState*>(state);
			*submixer     = {};
			submixer->voice_state.state_flags = Ngs2GetStateFlags(voice);
			LOGF("\t state_flags = %u\n", submixer->voice_state.state_flags);
			break;
		}
		case Ngs2RackType::CustomMastering: {
			const auto configured_size =
			    voice->rack->option.custom_mastering.custom_rack_option.state_size;
			EXIT_NOT_IMPLEMENTED(configured_size < sizeof(Ngs2CustomMasteringVoiceState));
			EXIT_NOT_IMPLEMENTED(state_size != configured_size);
			std::memset(state, 0, state_size);
			auto* mastering = reinterpret_cast<Ngs2CustomMasteringVoiceState*>(state);
			mastering->voice_state.state_flags = Ngs2GetStateFlags(voice);
			LOGF("\t state_flags = %u\n", mastering->voice_state.state_flags);
			break;
		}
		case Ngs2RackType::Sampler:
		case Ngs2RackType::CustomSampler: {
			if (state_size != sizeof(Ngs2SamplerVoiceState)) {
				LOGF("\t warning: sampler state_size = 0x%016" PRIx64 ", expected 0x%016" PRIx64
				     "\n",
				     static_cast<uint64_t>(state_size),
				     static_cast<uint64_t>(sizeof(Ngs2SamplerVoiceState)));
			}
			std::memset(state, 0, state_size);

			state->state_flags = Ngs2GetStateFlags(voice);
			if (state_size < sizeof(Ngs2SamplerVoiceState)) {
				LOGF("\t state_flags = %u\n", state->state_flags);
				break;
			}

			auto* sampler                = reinterpret_cast<Ngs2SamplerVoiceState*>(state);
			sampler->envelope_height     = 1.0f;
			sampler->peak_height         = 0.0f;
			sampler->reserved            = 0;
			sampler->num_decoded_samples = 0;
			sampler->user_data           = 0;
			sampler->waveform_data       = nullptr;
			LOGF("\t state_flags = %u\n", sampler->voice_state.state_flags);
			break;
		}
		default: EXIT("unknown type: %s\n", Common::EnumName(voice->rack->type).c_str());
	}

	return OK;
}

int KYTY_SYSV_ABI Ngs2VoiceGetStateFlags(uintptr_t voice_handle, uint32_t* state_flags) {
	PRINT_NAME();

	EXIT_NOT_IMPLEMENTED(state_flags == nullptr);
	EXIT_NOT_IMPLEMENTED(voice_handle == 0);

	auto* voice = reinterpret_cast<Ngs2VoiceInternal*>(voice_handle);

	Common::LockGuard lock(voice->rack->ngs->mutex);

	*state_flags = Ngs2GetStateFlags(voice);

	LOGF("\t state_flags = %u\n", *state_flags);

	return OK;
}

} // namespace Ngs2

} // namespace Libs::Audio
