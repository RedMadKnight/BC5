// SPDX-License-Identifier: GPL-2.0-only
// BC5 experiment 0401 series e6, tag fwa: the CPU test of mkfwa0405.py's edit of src/libs/audio.cpp and
// src/libs/avPlayer.cpp (exp 0405's decision-1 audio items, ported from AnyPS5 4f41f4c; notes fwa0405-notes.md). It calls
// the units' own functions, linked with every emulator object but main.cpp.o and the private audio.cpp.o and
// avPlayer.cpp.o in place of the shared ones. No game, no GPU, no window, no network and no sound device: SDL_AUDIODRIVER
// names a driver that does not exist (as ao0405.cpp does); Audio3d's ports only sleep in their playback threads; Ngs2 and
// the waveform parser are host memory only; the AvPlayer part calls the aspect helper alone (no video file is opened).
// Switch: KYTY_BC5_FW_AUDIO (items pcmloop, audio3d, audio3dstrict, ngs2, avplayer; a comma list turns on only those,
// any other value such as "1" all of them). Each case expects its item's state. With an item off, a case whose today's
// path ends the process (an EXIT, a division by zero) is not run: it prints a "skipped" line and is not counted. Every
// other case runs on and off; off it checks today's behaviour.
// Build: build0401.py ... src/libs/audio.cpp=<out>/src/libs/audio.cpp src/libs/avPlayer.cpp=<out>/src/libs/avPlayer.cpp
//        --gate fwa0405.cpp <dir>/fwa0405 --like src/libs/audio.cpp
// usage: fwa0405 on|off, with KYTY_BC5_FW_AUDIO set to match ("on": at least one item on; "off": none). Run it in a fresh
// directory. Prints one line per case and finally "fwa0405: on|off N of N; end", exit 0 only then. A watchdog ends a hang
// with a FAIL line (exit 3).

#include "common/abi.h"
#include "common/logging/log.h"
#include "kernel/pthread.h"
#include "libs/audio.h"

#include <atomic>
#include <chrono>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <new>
#include <string>
#include <thread>
#include <unistd.h>
#include <vector>

// The units' own definitions of the types the test passes, token for token (audio.h only declares them).
namespace Libs::Audio::Audio3d {

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

} // namespace Libs::Audio::Audio3d

namespace Libs::Audio::Ngs2 {

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

struct Ngs2CustomSamplerRackOption {
	Ngs2CustomRackOption custom_rack_option;
	uint32_t             max_channel_works        = 0;
	uint32_t             max_waveform_blocks      = 0;
	uint32_t             max_atrac9_decoders      = 0;
	uint32_t             max_atrac9_channel_works = 0;
	uint32_t             max_ajm_atrac9_decoders  = 0;
	uint32_t             max_codec_caches         = 0;
};

struct Ngs2ContextBufferInfo {
	void*     host_buffer      = nullptr;
	size_t    host_buffer_size = 0;
	uintptr_t reserved[5]      = {};
	uintptr_t user_data        = 0;
};

using Ngs2BufferAllocHandler = int32_t KYTY_SYSV_ABI (*)(Ngs2ContextBufferInfo*);
using Ngs2BufferFreeHandler  = int32_t  KYTY_SYSV_ABI (*)(Ngs2ContextBufferInfo*);

struct Ngs2BufferAllocator {
	Ngs2BufferAllocHandler alloc_handler = nullptr;
	Ngs2BufferFreeHandler  free_handler  = nullptr;
	uintptr_t              user_data     = 0;
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

static_assert(sizeof(Ngs2RackOption) == 176);
static_assert(sizeof(Ngs2ContextBufferInfo) == 64);
static_assert(sizeof(Ngs2WaveformInfo) == 232);

} // namespace Libs::Audio::Ngs2

// The units' new functions with external linkage (mkfwa0405.py; no header declares them).
namespace Libs::Audio {
uint32_t Bc5FwAudioItems();
} // namespace Libs::Audio

namespace Libs::Audio::AvPlayer {
float Bc5FwAvPlayerSar(int num, int den, int fallback_num, int fallback_den);
} // namespace Libs::Audio::AvPlayer

namespace fwa0405 {

namespace A3 = Libs::Audio::Audio3d;
namespace N2 = Libs::Audio::Ngs2;

// The expected codes: Audio3d from shadPS4 60c42b9 src/core/libraries/audio3d/audio3d_error.h:7-13 (the same values as
// AnyPS5 4f41f4c libSceAudio3d/Export.cpp:27-32); Ngs2's waveform codes from KytyPS5 4644c52 src/libs/ngs2.cpp:39-44;
// 0x804A8053 from AnyPS5 9c009622b (its commit message).
const int kA3dInvalidPort  = static_cast<int>(0x80EA0002u);
const int kA3dInvalidParam = static_cast<int>(0x80EA0004u);
const int kA3dOutOfRes     = static_cast<int>(0x80EA0006u);
const int kA3dNotReady     = static_cast<int>(0x80EA0007u);
const int kWaveInvalidData = static_cast<int>(0x804a8430u);
const int kWaveInvalidFmt  = static_cast<int>(0x804a8431u);
const int kWaveUnknownFmt  = static_cast<int>(0x804a8432u);
const int kNgs2BadBlocks   = static_cast<int>(0x804a8053u);

constexpr int      kWatchdogSeconds = 120;
constexpr uint32_t kPcmloop = 1u << 0, kAudio3d = 1u << 1, kStrict = 1u << 2, kNgs2 = 1u << 3, kAvplayer = 1u << 4;

std::atomic<int>         g_cases {0};
std::atomic<int>         g_passed {0};
std::atomic<bool>        g_finished {false};
std::atomic<const char*> g_case {"setup"};
uint32_t                 g_items = 0;

bool On(uint32_t item) {
	return (g_items & item) != 0;
}

void Report(const char* name, bool ok, const std::string& info) {
	g_cases++;
	if (ok) {
		g_passed++;
	}
	std::printf("fwa0405: case %d %s: %s (%s)\n", g_cases.load(), name, ok ? "ok" : "FAIL", info.c_str());
	std::fflush(stdout);
}

void Skip(const char* name, const char* why) {
	std::printf("fwa0405: case - %s: skipped with the item off (%s)\n", name, why);
	std::fflush(stdout);
}

[[noreturn]] void SetupFail(const char* what) {
	std::printf("fwa0405: FAIL setup: %s\n", what);
	std::fflush(stdout);
	_exit(2);
}

void Watchdog() {
	const auto start = std::chrono::steady_clock::now();
	while (!g_finished.load()) {
		std::this_thread::sleep_for(std::chrono::milliseconds(50));
		if (std::chrono::steady_clock::now() - start > std::chrono::seconds(kWatchdogSeconds)) {
			std::printf("fwa0405: FAIL watchdog: case \"%s\" still running after %d s (a hang); %d of %d cases passed before it\n",
			            g_case.load(), kWatchdogSeconds, g_passed.load(), g_cases.load());
			std::fflush(stdout);
			_exit(3);
		}
	}
}

std::string Hex(int v) {
	char b[32];
	std::snprintf(b, sizeof(b), "0x%08x", static_cast<unsigned>(v));
	return b;
}

// The unit's reading of the value (e5's Bc5AoParse, which mkfwa0405.py reuses), repeated: which items the cases expect.
uint32_t Parse(const char* e) {
	static const char* const names[5] = {"pcmloop", "audio3d", "audio3dstrict", "ngs2", "avplayer"};
	static const uint32_t    bits[5]  = {kPcmloop, kAudio3d, kStrict, kNgs2, kAvplayer};
	if (e == nullptr || e[0] == '\0' || std::strcmp(e, "0") == 0) {
		return 0;
	}
	uint32_t    on = 0;
	const char* p  = e;
	for (;;) {
		const char*  comma = std::strchr(p, ',');
		const size_t len   = comma != nullptr ? static_cast<size_t>(comma - p) : std::strlen(p);
		for (int k = 0; k < 5; k++) {
			if (len == std::strlen(names[k]) && std::strncmp(p, names[k], len) == 0) {
				on |= bits[k];
			}
		}
		if (comma == nullptr) {
			break;
		}
		p = comma + 1;
	}
	return on != 0 ? on : (kPcmloop | kAudio3d | kStrict | kNgs2 | kAvplayer);
}

// 64-byte aligned memory that is never freed (the test ends soon after); null when there is none.
uint8_t* AlignedBytes(size_t size) {
	return static_cast<uint8_t*>(::operator new(size != 0 ? size : 64, std::align_val_t {64}, std::nothrow));
}

int32_t KYTY_SYSV_ABI TestAlloc(N2::Ngs2ContextBufferInfo* info) {
	const size_t size = (info->host_buffer_size + 63) / 64 * 64;
	auto*        p    = AlignedBytes(size);
	if (p == nullptr) {
		return -1;
	}
	std::memset(p, 0, size);
	info->host_buffer = p;
	return 0;
}

int32_t KYTY_SYSV_ABI TestFree(N2::Ngs2ContextBufferInfo* /*info*/) {
	return 0;
}

// ---- the switch ------------------------------------------------------------------------------------------------------

void CasesSwitch() {
	g_case                = "switch";
	const uint32_t unit   = Libs::Audio::Bc5FwAudioItems();
	Report("switch: the unit reads KYTY_BC5_FW_AUDIO as the test does", unit == g_items,
	       "unit " + Hex(static_cast<int>(unit)) + ", test " + Hex(static_cast<int>(g_items)));
}

// ---- Audio3d: audio3d, audio3dstrict ---------------------------------------------------------------------------------

struct OpenParams28 { // a size 0x28 block: num_beds after the 0x20 bytes (firmware 13.42 takes 0x20 and 0x28)
	A3::Audio3dOpenParameters p;
	uint32_t                  num_beds = 2;
	uint32_t                  pad2     = 0;
};

A3::Audio3dOpenParameters Params(uint32_t queue_depth) {
	A3::Audio3dOpenParameters p {};
	A3::Audio3dGetDefaultOpenParameters(&p);
	p.queue_depth = queue_depth;
	return p;
}

int SetFloat(uint32_t port, uint32_t id, float v, size_t size = sizeof(float)) {
	float buf[2] = {v, v};
	return A3::Audio3dPortSetAttribute(port, id, buf, size);
}

void CasesAudio3d() {
	const bool a3d    = On(kAudio3d);
	const bool strict = On(kStrict);
	uint32_t   id     = 0xFFFFFFFFu;

	g_case = "audio3d defaults";
	{
		A3::Audio3dOpenParameters p {};
		std::memset(&p, 0xCC, sizeof(p));
		A3::Audio3dGetDefaultOpenParameters(&p);
		Report("a3d: default open parameters are firmware 13.42's {0x20, 256, 0, 512, 2, 2} (we already match)",
		       p.size == 0x20 && p.granularity == 256 && p.rate == 0 && p.max_objects == 512 && p.queue_depth == 2 &&
		           p.buffer_mode == 2,
		       "size " + std::to_string(p.size) + ", granularity " + std::to_string(p.granularity));
	}

	g_case = "audio3dstrict open before initialize";
	if (strict) {
		auto      p = Params(2);
		const int r = A3::Audio3dPortOpen(255, &p, &id);
		Report("a3d strict: PortOpen before Audio3dInitialize -> NOT_READY", r == kA3dNotReady, Hex(r));
	} else {
		Skip("a3d strict: PortOpen before Audio3dInitialize", "today it opens a port; the open cases below cover that");
	}

	g_case = "audio3d initialize reserved";
	if (a3d) {
		const int r = A3::Audio3dInitialize(1);
		Report("a3d: Audio3dInitialize(1) -> INVALID_PARAMETER", r == kA3dInvalidParam, Hex(r));
	} else {
		Skip("a3d: Audio3dInitialize(1)", "today an exit");
	}
	{
		const int r = A3::Audio3dInitialize(0);
		Report("a3d: Audio3dInitialize(0) -> 0", r == 0, Hex(r));
	}

	g_case = "audio3d open: today's exits";
	if (a3d) {
		auto      p  = Params(2);
		const int r1 = A3::Audio3dPortOpen(255, nullptr, &id);
		const int r2 = A3::Audio3dPortOpen(255, &p, nullptr);
		Report("a3d: PortOpen with a null parameters or id -> INVALID_PARAMETER", r1 == kA3dInvalidParam && r2 == kA3dInvalidParam,
		       Hex(r1) + ", " + Hex(r2));
		auto s18 = Params(2);
		s18.size = 0x18;
		const int r3 = A3::Audio3dPortOpen(255, &s18, &id);
		Report("a3d: PortOpen with size 0x18 -> INVALID_PARAMETER", r3 == kA3dInvalidParam, Hex(r3));
		auto q0      = Params(0);
		const int r4 = A3::Audio3dPortOpen(255, &q0, &id);
		Report("a3d: PortOpen with queue_depth 0 -> INVALID_PARAMETER (today: a division by 0 later)", r4 == kA3dInvalidParam, Hex(r4));
		auto b1        = Params(2);
		b1.buffer_mode = 1;
		const int r5   = A3::Audio3dPortOpen(255, &b1, &id);
		Report("a3d: PortOpen with buffer_mode 1 -> INVALID_PARAMETER", r5 == kA3dInvalidParam, Hex(r5));
		const int r6 = A3::Audio3dPortOpen(7, &p, &id);
		Report("a3d: PortOpen with user_id 7 -> INVALID_PARAMETER", r6 == kA3dInvalidParam, Hex(r6));
	} else {
		Skip("a3d: PortOpen with null pointers, size 0x18, queue_depth 0, buffer_mode 1, user_id 7", "today exits");
	}

	g_case = "audio3dstrict open: today's successes";
	{
		auto      p = Params(2);
		const int r = A3::Audio3dPortOpen(1, &p, &id);
		if (strict) {
			Report("a3d strict: PortOpen with user_id 1 -> INVALID_PARAMETER", r == kA3dInvalidParam, Hex(r));
		} else {
			Report("a3d strict off: PortOpen with user_id 1 opens a port (today)", r == 0 && id < 4, Hex(r) + ", id " + std::to_string(id));
		}
		auto rate      = Params(2);
		rate.rate      = 1;
		const int r2   = A3::Audio3dPortOpen(255, &rate, &id);
		if (strict) {
			Report("a3d strict: PortOpen with rate 1 -> INVALID_PARAMETER", r2 == kA3dInvalidParam, Hex(r2));
		} else {
			Report("a3d strict off: PortOpen with rate 1 opens a port (today)", r2 == 0 && id < 4, Hex(r2) + ", id " + std::to_string(id));
		}
	}

	g_case = "audio3d main port";
	// The port the rest uses: queue depth 2, granularity 48 x 256 (256 ms a frame, so that a push's playback is slow).
	OpenParams28 p28 {};
	A3::Audio3dGetDefaultOpenParameters(&p28.p);
	p28.p.granularity = 48 * 256;
	p28.p.queue_depth = 2;
	if (a3d) {
		p28.p.size = 0x28;
	}
	uint32_t  port = 0xFFFFFFFFu;
	const int ro   = A3::Audio3dPortOpen(255, &p28.p, &port);
	Report(a3d ? "a3d: PortOpen with size 0x28 opens a port (today: an exit)" : "a3d off: PortOpen with size 0x20 opens a port",
	       ro == 0 && port < 4 && (!strict || port == 0), Hex(ro) + ", id " + std::to_string(port));
	if (ro != 0 || port >= 4) {
		SetupFail("no Audio3d port to go on with");
	}

	g_case = "audio3d more ports";
	{
		auto      p = Params(2);
		uint32_t  i2 = 0xFFFFFFFFu;
		const int r  = A3::Audio3dPortOpen(255, &p, &i2);
		if (strict) {
			Report("a3d strict: a second PortOpen -> OUT_OF_RESOURCES (firmware 13.42 has one port)", r == kA3dOutOfRes, Hex(r));
		} else {
			Report("a3d strict off: a second PortOpen opens another port (today: four)", r == 0 && i2 < 4 && i2 != port,
			       Hex(r) + ", id " + std::to_string(i2));
			if (a3d) {
				uint32_t  i3 = 0xFFFFFFFFu;
				const int r3 = A3::Audio3dPortOpen(255, &p, &i3);
				Report("a3d: PortOpen with no port left -> OUT_OF_RESOURCES (today: an exit)", r3 == kA3dOutOfRes, Hex(r3));
			} else {
				Skip("a3d: PortOpen with no port left", "today an exit");
			}
		}
	}

	g_case = "audio3d attributes";
	{
		const int r = SetFloat(port, 0x10001, 0.5f);
		Report("a3d: SetAttribute late reverb 0.5 -> 0", r == 0, Hex(r));
		const int r2 = SetFloat(port, 0x10001, 2.0f);
		const int r3 = SetFloat(port, 0x10002, 0.05f);
		const int r4 = SetFloat(port, 0x10001, std::nanf(""));
		if (strict) {
			Report("a3d strict: SetAttribute reverb 2.0, radius 0.05, reverb NaN -> INVALID_PARAMETER each",
			       r2 == kA3dInvalidParam && r3 == kA3dInvalidParam && r4 == kA3dInvalidParam, Hex(r2) + ", " + Hex(r3) + ", " + Hex(r4));
		} else {
			Report("a3d strict off: SetAttribute reverb 2.0, radius 0.05, reverb NaN -> 0 (today stores them)",
			       r2 == 0 && r3 == 0 && r4 == 0, Hex(r2) + ", " + Hex(r3) + ", " + Hex(r4));
		}
		const int r5 = SetFloat(port, 0x10002, 1.0f);
		Report("a3d: SetAttribute downmix spread radius 1.0 -> 0", r5 == 0, Hex(r5));
		if (a3d) {
			int64_t   aware[2] = {1, 1};
			const int r6       = A3::Audio3dPortSetAttribute(port, 0x10003, aware, 8);
			Report("a3d: SetAttribute height aware with size 8 -> 0 (firmware 13.42 checks the pointer only)", r6 == 0, Hex(r6));
			const int r7 = SetFloat(port, 0x10001, 0.5f, 8);
			Report("a3d: SetAttribute reverb with size 8 -> INVALID_PARAMETER", r7 == kA3dInvalidParam, Hex(r7));
			const int r8 = SetFloat(port, 0x12345, 0.5f);
			Report("a3d: SetAttribute with an unknown id -> INVALID_PARAMETER", r8 == kA3dInvalidParam, Hex(r8));
			const int r9 = A3::Audio3dPortSetAttribute(port, 0x10001, nullptr, 4);
			Report("a3d: SetAttribute with a null attribute -> INVALID_PARAMETER", r9 == kA3dInvalidParam, Hex(r9));
			const int r10 = SetFloat(9, 0x10001, 0.5f);
			Report("a3d: SetAttribute on port 9 -> INVALID_PORT", r10 == kA3dInvalidPort, Hex(r10));
		} else {
			Skip("a3d: SetAttribute with size 8, an unknown id, a null attribute, port 9", "today exits");
		}
	}

	g_case = "audio3d queue";
	{
		uint32_t  level = 99, avail = 99;
		const int r     = A3::Audio3dPortGetQueueLevel(port, &level, &avail);
		Report("a3d: GetQueueLevel on a new port -> 0, level 0, available 2", r == 0 && level == 0 && avail == 2,
		       Hex(r) + ", " + std::to_string(level) + "/" + std::to_string(avail));
		if (a3d) {
			const int r2 = A3::Audio3dPortGetQueueLevel(port, nullptr, nullptr);
			const int r3 = A3::Audio3dPortGetQueueLevel(9, &level, &avail);
			const int r4 = A3::Audio3dPortAdvance(9);
			const int r5 = A3::Audio3dPortPush(9, 1);
			Report("a3d: GetQueueLevel with both outputs null -> INVALID_PARAMETER; port 9 in GetQueueLevel, Advance and "
			       "Push -> INVALID_PORT",
			       r2 == kA3dInvalidParam && r3 == kA3dInvalidPort && r4 == kA3dInvalidPort && r5 == kA3dInvalidPort,
			       Hex(r2) + ", " + Hex(r3) + ", " + Hex(r4) + ", " + Hex(r5));
		} else {
			Skip("a3d: GetQueueLevel with null outputs; port 9", "today exits");
		}
		const int a1 = A3::Audio3dPortAdvance(port);
		const int a2 = A3::Audio3dPortAdvance(port);
		level = avail = 99;
		const int rq  = A3::Audio3dPortGetQueueLevel(port, &level, &avail);
		Report("a3d: two PortAdvance -> 0, 0; the queue is full (level 2, available 0)",
		       a1 == 0 && a2 == 0 && rq == 0 && level == 2 && avail == 0,
		       Hex(a1) + ", " + Hex(a2) + ", " + std::to_string(level) + "/" + std::to_string(avail));
		const int a3 = A3::Audio3dPortAdvance(port);
		if (strict) {
			Report("a3d strict: a third PortAdvance on the full queue -> NOT_READY", a3 == kA3dNotReady, Hex(a3));
		} else {
			Report("a3d strict off: a third PortAdvance on the full queue -> 0 (today: the slot is taken again)", a3 == 0, Hex(a3));
		}

		const auto t0 = std::chrono::steady_clock::now();
		if (a3d) {
			const int  rp = A3::Audio3dPortPush(port, 0);
			const auto ms = std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now() - t0).count();
			Report("a3d: PortPush(blocking 0) -> 0 at once (today: an exit), under 150 ms", rp == 0 && ms < 150,
			       Hex(rp) + ", " + std::to_string(ms) + " ms");
			const int ra = A3::Audio3dPortAdvance(port);
			Report("a3d: PortAdvance while the pushed frame plays -> NOT_READY (today: an exit)", ra == kA3dNotReady, Hex(ra));
		} else {
			const int  rp = A3::Audio3dPortPush(port, 1);
			const auto ms = std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now() - t0).count();
			Report("a3d off: PortPush(blocking 1) -> 0 after a frame's playback (>= 200 ms)", rp == 0 && ms >= 200,
			       Hex(rp) + ", " + std::to_string(ms) + " ms");
			Skip("a3d: PortPush(blocking 0); PortAdvance while a frame plays", "today exits");
		}
		g_case         = "audio3d drain";
		bool drained   = false;
		const auto end = std::chrono::steady_clock::now() + std::chrono::seconds(5);
		while (std::chrono::steady_clock::now() < end) {
			level = avail = 99;
			if (A3::Audio3dPortGetQueueLevel(port, &level, &avail) == 0 && avail == 2) {
				drained = true;
				break;
			}
			std::this_thread::sleep_for(std::chrono::milliseconds(20));
		}
		Report("a3d: the playback thread empties the queue (available 2 within 5 s)", drained,
		       std::to_string(level) + "/" + std::to_string(avail));
		const int af = A3::Audio3dPortAdvance(port);
		Report("a3d: PortAdvance on the emptied queue -> 0", af == 0, Hex(af));
	}
}

// ---- Ngs2ParseWaveformData: pcmloop ----------------------------------------------------------------------------------

void Put16(std::vector<uint8_t>& f, uint32_t v) {
	f.push_back(static_cast<uint8_t>(v));
	f.push_back(static_cast<uint8_t>(v >> 8u));
}

void Put32(std::vector<uint8_t>& f, uint32_t v) {
	Put16(f, v & 0xffffu);
	Put16(f, v >> 16u);
}

void PutTag(std::vector<uint8_t>& f, const char* t) {
	f.insert(f.end(), t, t + 4);
}

void FixRiff(std::vector<uint8_t>& f) {
	const auto size = static_cast<uint32_t>(f.size() - 8);
	std::memcpy(f.data() + 4, &size, 4);
}

// A RIFF/WAVE file: fmt (tag 1 or 3: 16 bytes; 0xfffe: 40 bytes with the PCM GUID), then data of `frames` zero frames.
std::vector<uint8_t> Wave(uint32_t tag, uint32_t channels, uint32_t rate, uint32_t bits, uint32_t frames,
                          uint32_t align_override = 0) {
	static const uint8_t pcm_guid[16] = {0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x10, 0x00,
	                                     0x80, 0x00, 0x00, 0xaa, 0x00, 0x38, 0x9b, 0x71};
	const uint32_t       align        = align_override != 0 ? align_override : channels * bits / 8;
	std::vector<uint8_t> f;
	PutTag(f, "RIFF");
	Put32(f, 0);
	PutTag(f, "WAVE");
	PutTag(f, "fmt ");
	Put32(f, tag == 0xfffe ? 40 : 16);
	Put16(f, tag);
	Put16(f, channels);
	Put32(f, rate);
	Put32(f, rate * align);
	Put16(f, align);
	Put16(f, bits);
	if (tag == 0xfffe) {
		Put16(f, 22);
		Put16(f, bits);
		Put32(f, 3);
		f.insert(f.end(), pcm_guid, pcm_guid + 16);
	}
	PutTag(f, "data");
	Put32(f, frames * (channels * bits / 8));
	f.resize(f.size() + static_cast<size_t>(frames) * (channels * bits / 8), 0);
	FixRiff(f);
	return f;
}

// A smpl chunk with `loops` loops (each begin..last, play count `plays`), or a chunk of `short_size` bytes when not 0.
void Smpl(std::vector<uint8_t>& f, uint32_t loops, uint32_t begin, uint32_t last, uint32_t plays, uint32_t short_size = 0) {
	PutTag(f, "smpl");
	if (short_size != 0) {
		Put32(f, short_size);
		f.resize(f.size() + short_size, 0);
	} else {
		Put32(f, 36 + 24 * loops);
		for (int i = 0; i < 7; i++) {
			Put32(f, 0);
		}
		Put32(f, loops);
		Put32(f, 0);
		for (uint32_t l = 0; l < loops; l++) {
			Put32(f, l);
			Put32(f, 0);
			Put32(f, begin);
			Put32(f, last);
			Put32(f, 0);
			Put32(f, plays);
		}
	}
	FixRiff(f);
}

int Parse(const std::vector<uint8_t>& f, N2::Ngs2WaveformInfo* info, size_t size = 0) {
	std::memset(static_cast<void*>(info), 0xCC, sizeof(*info));
	return N2::Ngs2ParseWaveformData(f.data(), size != 0 ? size : f.size(), info);
}

// Today's stub answer for data of `size` bytes.
bool Stub(int r, const N2::Ngs2WaveformInfo& i, size_t size) {
	return r == 0 && i.format.waveform_type == 0x80 && i.format.num_channels == 1 && i.format.sample_rate == 48000 &&
	       i.data_size == size && i.num_samples == 0 && i.num_blocks == 0 && i.num_audio_unit_samples == 1;
}

bool Block(const N2::Ngs2WaveformBlock& b, uint64_t offset, uint64_t size, uint32_t repeats, uint32_t samples) {
	return b.data_offset == offset && b.data_size == size && b.num_repeats == repeats && b.num_skip_samples == 0 &&
	       b.num_samples == samples;
}

std::string Info(int r, const N2::Ngs2WaveformInfo& i) {
	return Hex(r) + ", type " + Hex(static_cast<int>(i.format.waveform_type)) + ", samples " + std::to_string(i.num_samples) +
	       ", loop " + std::to_string(i.loop_begin_position) + ".." + std::to_string(i.loop_end_position) + ", blocks " +
	       std::to_string(i.num_blocks);
}

void CasesPcm() {
	g_case                  = "pcmloop";
	const bool           on = On(kPcmloop);
	N2::Ngs2WaveformInfo i {};

	{
		const auto w = Wave(1, 2, 48000, 16, 100);
		const int  r = Parse(w, &i);
		const bool ok =
		    on ? r == 0 && i.format.waveform_type == 0x12 && i.format.num_channels == 2 && i.format.sample_rate == 48000 &&
		             i.data_offset == 44 && i.data_size == 400 && i.num_samples == 100 && i.audio_unit_size == 4 &&
		             i.audio_frame_size == 4 && i.num_audio_frame_samples == 1 && i.num_delay_samples == 0 &&
		             i.loop_begin_position == 0 && i.loop_end_position == 0 && i.num_blocks == 1 &&
		             Block(i.blocks[0], 44, 400, 0, 100)
		       : Stub(r, i, w.size());
		Report(on ? "pcm: 16-bit stereo 48 kHz, 100 frames -> type 0x12, one block" : "pcm off: a PCM wave gets today's stub (0x80)",
		       ok, Info(r, i));
	}
	for (const uint32_t bits: {16u, 24u}) {
		auto           w     = Wave(1, 2, 48000, bits, 100);
		const uint32_t frame = 2 * bits / 8;
		Smpl(w, 1, 10, 59, 0);
		const int  r  = Parse(w, &i);
		const bool ok = on ? r == 0 && i.format.waveform_type == (bits == 16 ? 0x12u : 0x14u) && i.num_samples == 100 &&
		                         i.loop_begin_position == 10 && i.loop_end_position == 60 && i.num_blocks == 3 &&
		                         Block(i.blocks[0], 44, 10 * frame, 0, 10) &&
		                         Block(i.blocks[1], 44 + 10 * frame, 50 * frame, UINT32_MAX, 50) &&
		                         Block(i.blocks[2], 44 + 60 * frame, 40 * frame, 0, 40)
		                   : Stub(r, i, w.size());
		Report(on ? (bits == 16 ? "pcm: smpl loop 10..59 (16-bit) -> blocks 0-10, 10-60 forever, 60-100"
		                        : "pcm: smpl loop 10..59 (24-bit, type 0x14) -> the same three blocks")
		          : "pcm off: a looped wave gets today's stub",
		       ok, Info(r, i));
	}
	{
		auto w = Wave(1, 1, 44100, 16, 100);
		Smpl(w, 1, 0, 99, 3);
		const int  r  = Parse(w, &i);
		const bool ok = on ? r == 0 && i.loop_begin_position == 0 && i.loop_end_position == 100 && i.num_blocks == 1 &&
		                         Block(i.blocks[0], 44, 200, UINT32_MAX, 100)
		                   : Stub(r, i, w.size());
		Report(on ? "pcm: a loop over the whole wave, play count 3 -> one block repeating forever (403956973)"
		          : "pcm off: whole-wave loop gets today's stub",
		       ok, Info(r, i));
	}
	if (on) {
		auto w0 = Wave(1, 1, 44100, 16, 100);
		Smpl(w0, 0, 0, 0, 0);
		int r = Parse(w0, &i);
		Report("pcm: a smpl chunk with no loops -> one block, no loop",
		       r == 0 && i.num_blocks == 1 && i.loop_end_position == 0 && Block(i.blocks[0], 44, 200, 0, 100), Info(r, i));
		auto wr = Wave(1, 1, 44100, 16, 100);
		Smpl(wr, 1, 50, 10, 0);
		r = Parse(wr, &i);
		Report("pcm: a loop whose end is not after its start -> one block, the positions as read (50..11)",
		       r == 0 && i.num_blocks == 1 && i.loop_begin_position == 50 && i.loop_end_position == 11 &&
		           Block(i.blocks[0], 44, 200, 0, 100),
		       Info(r, i));
		auto wp = Wave(1, 1, 44100, 16, 100);
		Smpl(wp, 1, 0, 120, 0);
		r = Parse(wp, &i);
		Report("pcm: a loop past the last sample -> kept as one block, no loop (AnyPS5 throws; TODO(verify))",
		       r == 0 && i.num_blocks == 1 && i.loop_begin_position == 0 && i.loop_end_position == 0 &&
		           Block(i.blocks[0], 44, 200, 0, 100),
		       Info(r, i));
		auto ws = Wave(1, 1, 44100, 16, 100);
		Smpl(ws, 0, 0, 0, 0, 20);
		r = Parse(ws, &i);
		Report("pcm: a smpl chunk of 20 bytes -> kept as one block (AnyPS5 throws; TODO(verify))",
		       r == 0 && i.num_blocks == 1 && i.loop_end_position == 0, Info(r, i));
		struct Kind {
			uint32_t    tag, bits, type;
			const char* name;
		};
		const Kind kinds[] = {{1, 8, 0x11, "8-bit -> 0x11"},      {1, 32, 0x16, "32-bit -> 0x16"},
		                      {3, 32, 0x18, "float 32 -> 0x18"},  {3, 64, 0x1a, "float 64 -> 0x1a"},
		                      {0xfffe, 16, 0x12, "extensible PCM 16-bit -> 0x12"}};
		bool        all   = true;
		std::string got;
		for (const auto& k: kinds) {
			const auto w = Wave(k.tag, 2, 48000, k.bits, 10);
			r            = Parse(w, &i);
			all          = all && r == 0 && i.format.waveform_type == k.type && i.num_samples == 10;
			got += std::string(k.name) + ": " + Hex(static_cast<int>(i.format.waveform_type)) + "; ";
		}
		Report("pcm: types 8, 32-bit, float 32 and 64, extensible", all, got);
		const auto w12 = Wave(1, 1, 48000, 12, 10, 2);
		r              = Parse(w12, &i);
		Report("pcm: 12-bit -> UNKNOWN_WAVEFORM_FORMAT", r == kWaveUnknownFmt, Hex(r));
		const auto wc0 = Wave(1, 0, 48000, 16, 10, 2);
		r              = Parse(wc0, &i);
		const int  ra  = Parse(Wave(1, 1, 48000, 16, 10, 4), &i);
		Report("pcm: 0 channels, or a block align not channels x bytes -> INVALID_WAVEFORM_FORMAT",
		       r == kWaveInvalidFmt && ra == kWaveInvalidFmt, Hex(r) + ", " + Hex(ra));
		auto wodd = Wave(1, 1, 48000, 16, 50);
		wodd[40]  = 101; // the data chunk's size: 101 bytes, not whole frames
		wodd.resize(44 + 101);
		FixRiff(wodd);
		r = Parse(wodd, &i);
		const auto wt = Wave(1, 1, 48000, 16, 200);
		const int  rt = Parse(wt, &i, 44 + 200); // the data chunk runs past the buffer
		Report("pcm: data not in whole frames, or past the buffer -> INVALID_WAVEFORM_DATA",
		       r == kWaveInvalidData && rt == kWaveInvalidData, Hex(r) + ", " + Hex(rt));
	} else {
		Skip("pcm: loop rules, other depths, the errors", "the stub answers every one with 0x80 (checked above)");
	}
	{
		auto mp3 = Wave(0x55, 2, 48000, 16, 10);
		int  r   = Parse(mp3, &i);
		const bool ok1 = Stub(r, i, mp3.size());
		const std::vector<uint8_t> junk(64, 0x5A);
		const int  r2  = Parse(junk, &i);
		const bool ok2 = Stub(r2, i, junk.size());
		Report("pcm: a non-PCM fmt tag (0x55) and data that is not RIFF get today's stub, on or off", ok1 && ok2,
		       Hex(r) + ", " + Hex(r2));
	}
}

// ---- Ngs2 racks: ngs2 ------------------------------------------------------------------------------------------------

void CasesRacks() {
	g_case        = "ngs2 racks";
	const bool on = On(kNgs2);

	auto sampler = [](uint32_t blocks) {
		N2::Ngs2SamplerRackOption o {};
		o.rack_option.size       = sizeof(N2::Ngs2SamplerRackOption);
		o.rack_option.max_voices = 4;
		o.max_waveform_blocks    = blocks;
		return o;
	};
	std::string got;
	bool        ok = true;
	for (const uint32_t blocks: {0u, 33u, 1u, 32u}) {
		auto                      o = sampler(blocks);
		N2::Ngs2ContextBufferInfo b {};
		const int r      = N2::Ngs2RackQueryBufferSize(0x1000, &o.rack_option, &b);
		const bool bad   = blocks == 0 || blocks > 32;
		const bool right = (on && bad) ? r == kNgs2BadBlocks && b.host_buffer_size == 0 : r == 0 && b.host_buffer_size != 0;
		ok               = ok && right;
		got += std::to_string(blocks) + ": " + Hex(r) + "; ";
	}
	Report(on ? "ngs2: sampler RackQueryBufferSize with 0 and 33 blocks -> 0x804A8053, with 1 and 32 -> 0"
	          : "ngs2 off: sampler RackQueryBufferSize with 0, 33, 1, 32 blocks -> 0 (today)",
	       ok, got);
	{
		N2::Ngs2CustomSamplerRackOption c {};
		c.custom_rack_option.rack_option.size       = sizeof(N2::Ngs2CustomSamplerRackOption);
		c.custom_rack_option.rack_option.max_voices = 4;
		c.max_waveform_blocks                       = 0;
		N2::Ngs2ContextBufferInfo b {};
		const int r = N2::Ngs2RackQueryBufferSize(0x4001, &c.custom_rack_option.rack_option, &b);
		Report(on ? "ngs2: custom sampler RackQueryBufferSize with 0 blocks -> 0x804A8053"
		          : "ngs2 off: custom sampler with 0 blocks -> 0 (today)",
		       on ? r == kNgs2BadBlocks : r == 0, Hex(r));
		N2::Ngs2ContextBufferInfo d {};
		const int rd = N2::Ngs2RackQueryBufferSize(0x1000, nullptr, &d);
		Report("ngs2: sampler RackQueryBufferSize with the default option (4 blocks) -> 0", rd == 0 && d.host_buffer_size != 0, Hex(rd));
	}
	{
		N2::Ngs2BufferAllocator alloc {};
		alloc.alloc_handler = TestAlloc;
		alloc.free_handler  = TestFree;
		uintptr_t sys       = 0;
		const int rs        = N2::Ngs2SystemCreateWithAllocator(nullptr, &alloc, &sys);
		if (rs != 0 || sys == 0) {
			SetupFail("Ngs2SystemCreateWithAllocator");
		}
		auto      o    = sampler(33);
		uintptr_t rack = 0;
		const int r    = N2::Ngs2RackCreateWithAllocator(sys, 0x1000, &o.rack_option, &alloc, &rack);
		Report(on ? "ngs2: sampler RackCreateWithAllocator with 33 blocks -> 0x804A8053, no rack"
		          : "ngs2 off: sampler RackCreateWithAllocator with 33 blocks makes a rack (today)",
		       on ? r == kNgs2BadBlocks && rack == 0 : r == 0 && rack != 0, Hex(r));
		auto                      o2 = sampler(0);
		N2::Ngs2ContextBufferInfo q {};
		(void)N2::Ngs2RackQueryBufferSize(0x1000, nullptr, &q);
		N2::Ngs2ContextBufferInfo buf {};
		buf.host_buffer_size = q.host_buffer_size + 64 * 4096;
		buf.host_buffer      = AlignedBytes(buf.host_buffer_size);
		std::memset(buf.host_buffer, 0, buf.host_buffer_size);
		uintptr_t rack2 = 0;
		const int r2    = N2::Ngs2RackCreate(sys, 0x1000, &o2.rack_option, &buf, &rack2);
		Report(on ? "ngs2: sampler RackCreate with 0 blocks -> 0x804A8053" : "ngs2 off: sampler RackCreate with 0 blocks (today: 0)",
		       on ? r2 == kNgs2BadBlocks && rack2 == 0 : r2 == 0 && rack2 != 0, Hex(r2));
	}
}

// ---- AvPlayer: avplayer ----------------------------------------------------------------------------------------------

void CasesAvPlayer() {
	g_case = "avplayer";
	using Libs::Audio::AvPlayer::Bc5FwAvPlayerSar;
	const bool unit_on = (Libs::Audio::Bc5FwAudioItems() & kAvplayer) != 0;
	Report("avplayer: the unit's item state is the test's", unit_on == On(kAvplayer), unit_on ? "on" : "off");
	const float a = Bc5FwAvPlayerSar(1, 1, 0, 0);
	const float b = Bc5FwAvPlayerSar(4, 3, 0, 0);
	const float c = Bc5FwAvPlayerSar(0, 1, 40, 33);
	const float d = Bc5FwAvPlayerSar(0, 0, 0, 1);
	const float e = Bc5FwAvPlayerSar(-4, 3, 0, 0);
	const float f = Bc5FwAvPlayerSar(1, 0, 2, 1);
	Report("avplayer: the aspect helper: 1:1 -> 1, 4:3 -> 1.333, none -> the fallback 40:33, none at all -> 0, a "
	       "negative or zero part -> not a ratio",
	       a == 1.0f && std::fabs(b - 4.0f / 3.0f) < 1e-6f && std::fabs(c - 40.0f / 33.0f) < 1e-6f && d == 0.0f && e == 0.0f &&
	           f == 2.0f,
	       std::to_string(a) + ", " + std::to_string(b) + ", " + std::to_string(c) + ", " + std::to_string(d) + ", " +
	           std::to_string(e) + ", " + std::to_string(f));
}

} // namespace fwa0405

int main(int argc, char** argv) {
	using namespace fwa0405;
	if (argc != 2 || (std::strcmp(argv[1], "on") != 0 && std::strcmp(argv[1], "off") != 0)) {
		std::printf("usage: fwa0405 on|off (with KYTY_BC5_FW_AUDIO set to match)\n");
		return 2;
	}
	const bool  want = std::strcmp(argv[1], "on") == 0;
	const char* env  = std::getenv("KYTY_BC5_FW_AUDIO");
	g_items          = Parse(env);
	if (want != (g_items != 0)) {
		std::printf("fwa0405: the argument says %s but KYTY_BC5_FW_AUDIO is %s\n", argv[1], env != nullptr ? env : "unset");
		return 2;
	}
	std::printf("fwa0405: items on:%s%s%s%s%s%s\n", g_items == 0 ? " none" : "", On(kPcmloop) ? " pcmloop" : "",
	            On(kAudio3d) ? " audio3d" : "", On(kStrict) ? " audio3dstrict" : "", On(kNgs2) ? " ngs2" : "",
	            On(kAvplayer) ? " avplayer" : "");
	std::fflush(stdout);
	std::thread(Watchdog).detach();

	setenv("SDL_AUDIODRIVER", "bc5-no-device-0405", 1); // no sound device: SDL's audio init fails
	std::printf("fwa0405: SDL_AUDIODRIVER=bc5-no-device-0405 (no sound device is opened)\n");
	::Log::Bc5SetLogging(false);                   // the units' LOGF lines are not needed here
	(void)Libs::LibKernel::KernelGetProcessTime(); // the process clock starts at its first read
	std::this_thread::sleep_for(std::chrono::milliseconds(2));
	Libs::Audio::AudioSubsystem::Instance()->Init(nullptr); // prints the "[bc5] exp 0405: ..." lines (stderr)

	CasesSwitch();
	CasesPcm();
	CasesRacks();
	CasesAvPlayer();
	CasesAudio3d(); // last: its ports' playback threads stay (Audio3d has no close here)

	g_case = "teardown";
	Libs::Audio::AudioSubsystem::Instance()->Destroy(nullptr);
	g_finished = true;

	const int cases  = g_cases.load();
	const int passed = g_passed.load();
	if (passed != cases || cases == 0) {
		std::printf("fwa0405: %s %d of %d; %d failures\n", argv[1], passed, cases, cases - passed);
		return 1;
	}
	std::printf("fwa0405: %s %d of %d; end\n", argv[1], passed, cases);
	return 0;
}
