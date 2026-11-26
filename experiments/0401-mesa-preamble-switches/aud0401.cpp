// SPDX-License-Identifier: GPL-2.0-only
// BC5 experiment 0401 series e4: the CPU test of KYTY_BC5_AUDIO_FIXES, mkaud0401.py's edit of src/libs/libAudio2.cpp (the
// AnyPS5 AudioOut2 fixes c34ab0258, 11f217b14 and 42beeaa46; notes aud0401-notes.md). No game, no GPU and no sound device:
// SDL_AUDIODRIVER is set to a driver that does not exist, so SDL's audio init fails and every port opens with an audio
// handle but no device (audio.cpp AudioOutOpen keeps the port; QueueSdlAudio drops its frames). The test drives the host's
// own AudioOut2 functions and reads the advanced grains back through the unit's hook Bc5AudioFixesPeekGrain:
//   set      the title sets its buffer, clears it, then advances: on, the grain holds the PCM given at the set; off, the
//            cleared buffer (read at Advance, today's model);
//   silence  a buffer given twice, then rewritten and advanced without a set: on, silence; off, the rewritten memory;
//   once     a buffer given once and rewritten: the grain reads it at Advance, on and off;
//   cleared  a null set takes the port out of the grain; the buffer given next counts as given once again (repeats);
//   room     a context with no port (the timer path), queue depth 2, 85.3-ms grains, two blocking pushes: on, the second
//            push returns once a grain has played (level 1 of 2, ~85 ms); off, at once with the queue full (2 of 2).
// The device path (a port on an SDL device) is not reached here and is not changed by the edit.
// Build: the compile command of src/libs/libAudio2.cpp with this file as the source, linked with every emulator object but
// main.cpp.o (the private libAudio2.cpp.o among them) and the link line's libraries, as npgate0401.cpp.
// usage: KYTY_BC5_AUDIO_FIXES=1 aud0401 on      KYTY_BC5_AUDIO_FIXES=0 aud0401 off   (unset is off too). A value naming
//        parts (e.g. "set,room") is "on": the cases of the named parts expect on, the others off.
// Prints "aud0401: on|off N of N; end" and exits 0 only then.

#include "common/abi.h"
#include "common/logging/log.h"
#include "kernel/pthread.h"
#include "libs/audio.h"

#include <algorithm>
#include <chrono>
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <thread>
#include <vector>

namespace Libs::Audio::AudioOut2 {

// libAudio2.cpp's own definitions, token for token (audio.h only declares them).
struct AudioOut2ContextParam {
	uint32_t max_ports;
	uint32_t max_object_ports;
	uint32_t guarantee_object_ports;
	uint32_t queue_depth;
	uint32_t num_grains;
	uint32_t flags;
	uint32_t reserved[10];
};

struct AudioOut2PortParam {
	uint16_t            port_type;
	uint16_t            pad;
	uint32_t            data_format;
	uint32_t            sampling_freq;
	uint32_t            flags;
	AudioOut2UserHandle user_handle;
	uint32_t            reserved[10];
};

struct AudioOut2Attribute {
	uint32_t    attribute_id;
	int32_t     reserved;
	const void* value;
	size_t      value_size;
};

// mkaud0401.py's hook for this test (defined in the edited libAudio2.cpp).
int64_t Bc5AudioFixesPeekGrain(AudioOut2ContextHandle ctx, size_t index, AudioOut2PortHandle port, void* out, size_t size);

} // namespace Libs::Audio::AudioOut2

namespace aud0401 {

using namespace Libs::Audio::AudioOut2;

constexpr uint32_t kFrames      = 512;    // the grain of the cases set .. cleared
constexpr uint32_t kChannels    = 2;      // data_format 0x0200: float, 2 channels
constexpr uint32_t kRoomGrains  = 4096;   // the room case's grain: 85.3 ms at 48 kHz
constexpr double   kRoomWaitMs  = 30.0;   // on: the push that fills the queue waits ~85 ms; off: about 0
constexpr size_t   kFloats      = static_cast<size_t>(kFrames) * kChannels;
constexpr uint32_t kPartSet     = 1;
constexpr uint32_t kPartSilence = 2;
constexpr uint32_t kPartRoom    = 4;

struct Pcm { // the PCM attribute's value (libAudio2.cpp AudioOut2Pcm)
	const void* data;
};

int g_checks = 0;
int g_failed = 0;

void Check(bool ok, const char* what) {
	g_checks++;
	if (!ok) {
		g_failed++;
		std::printf("aud0401: FAIL %s\n", what);
	}
}

// The unit's reading of KYTY_BC5_AUDIO_FIXES (mkaud0401.py, Bc5AudioFixesParse), repeated: which cases expect on.
uint32_t Parts(const char* e) {
	if (e == nullptr || e[0] == '\0' || std::strcmp(e, "0") == 0) {
		return 0;
	}
	uint32_t    parts = 0;
	const char* p     = e;
	for (;;) {
		const char*  comma = std::strchr(p, ',');
		const size_t n     = comma != nullptr ? static_cast<size_t>(comma - p) : std::strlen(p);
		if (n == 3 && std::strncmp(p, "set", n) == 0) {
			parts |= kPartSet;
		} else if (n == 7 && std::strncmp(p, "silence", n) == 0) {
			parts |= kPartSilence;
		} else if (n == 4 && std::strncmp(p, "room", n) == 0) {
			parts |= kPartRoom;
		}
		if (comma == nullptr) {
			break;
		}
		p = comma + 1;
	}
	return parts != 0 ? parts : (kPartSet | kPartSilence | kPartRoom);
}

AudioOut2ContextHandle MakeContext(uint32_t depth, uint32_t grains) {
	AudioOut2ContextParam p {};
	(void)AudioOut2ContextResetParam(&p);
	p.queue_depth             = depth;
	p.num_grains              = grains;
	AudioOut2ContextHandle ctx = 0;
	const int              r   = AudioOut2ContextCreate(&p, nullptr, 0, &ctx);
	Check(r == 0 && ctx != 0, "a context is created");
	return ctx;
}

AudioOut2PortHandle MakePort(AudioOut2ContextHandle ctx) {
	AudioOut2PortParam p {};
	p.port_type             = 0;      // main
	p.data_format           = 0x0200; // float, 2 channels (Format::FloatStereo)
	p.sampling_freq         = 48000;
	AudioOut2PortHandle port = 0;
	const int           r    = AudioOut2PortCreate(ctx, &p, &port);
	Check(r == 0 && port != 0, "a port is created");
	return port;
}

void Set(AudioOut2PortHandle port, const void* buffer) {
	Pcm                pcm {buffer};
	AudioOut2Attribute a {};
	a.attribute_id = 0; // AUDIO_OUT2_PORT_ATTRIBUTE_ID_PCM
	a.value        = &pcm;
	a.value_size   = sizeof(pcm);
	(void)AudioOut2PortSetAttributes(port, &a, 1);
}

void Advance(AudioOut2ContextHandle ctx) {
	(void)AudioOut2ContextAdvance(ctx);
}

// The advanced grain `index` of `ctx` for `port`: 1 when it is one grain whose every sample is `v`, 0 when not, and the
// hook's -1 (no such grain) or -2 (nothing of the port in it).
int GrainIs(AudioOut2ContextHandle ctx, size_t index, AudioOut2PortHandle port, float v) {
	std::vector<float> got(kFloats, -9.0f);
	const int64_t      n = Bc5AudioFixesPeekGrain(ctx, index, port, got.data(), got.size() * sizeof(float));
	if (n < 0) {
		return static_cast<int>(n);
	}
	if (n != static_cast<int64_t>(kFloats * sizeof(float))) {
		return 0;
	}
	return std::all_of(got.begin(), got.end(), [v](float f) { return f == v; }) ? 1 : 0;
}

double Ms(std::chrono::steady_clock::time_point a, std::chrono::steady_clock::time_point b) {
	return std::chrono::duration<double, std::milli>(b - a).count();
}

void CaseSet(bool on) { // c34ab0258
	const auto         ctx  = MakeContext(4, kFrames);
	const auto         port = MakePort(ctx);
	std::vector<float> b(kFloats, 0.25f);
	Set(port, b.data());
	std::fill(b.begin(), b.end(), 0.0f); // cleared after the set, before Advance
	Advance(ctx);
	Check(GrainIs(ctx, 0, port, on ? 0.25f : 0.0f) == 1,
	      on ? "set: the grain holds the PCM given at the set" : "set: the grain holds the buffer as Advance read it (today)");
	(void)AudioOut2ContextDestroy(ctx);
}

void CaseSilence(bool on) { // 11f217b14
	const auto         ctx  = MakeContext(4, kFrames);
	const auto         port = MakePort(ctx);
	std::vector<float> b(kFloats, 0.5f);
	Set(port, b.data());
	Advance(ctx);
	Set(port, b.data()); // the same buffer given again
	Advance(ctx);
	std::fill(b.begin(), b.end(), 0.75f); // not set again; its memory reused
	Advance(ctx);
	Check(GrainIs(ctx, 0, port, 0.5f) == 1, "silence: grain 1 holds the first set's PCM");
	Check(GrainIs(ctx, 1, port, 0.5f) == 1, "silence: grain 2 holds the second set's PCM");
	Check(GrainIs(ctx, 2, port, on ? 0.0f : 0.75f) == 1,
	      on ? "silence: a buffer given twice and not set again plays silence" : "silence: it plays its reused memory (today)");
	(void)AudioOut2ContextDestroy(ctx);
}

void CaseOnce() { // 11f217b14 keeps the repeat of a buffer given once (rewritten in place)
	const auto         ctx  = MakeContext(4, kFrames);
	const auto         port = MakePort(ctx);
	std::vector<float> b(kFloats, 0.125f);
	Set(port, b.data());
	Advance(ctx);
	std::fill(b.begin(), b.end(), 0.375f);
	Advance(ctx);
	Check(GrainIs(ctx, 0, port, 0.125f) == 1, "once: grain 1 holds the set's PCM");
	Check(GrainIs(ctx, 1, port, 0.375f) == 1, "once: a buffer given once repeats, read at Advance");
	(void)AudioOut2ContextDestroy(ctx);
}

void CaseCleared() { // a null set; then a buffer given once again
	const auto         ctx  = MakeContext(4, kFrames);
	const auto         port = MakePort(ctx);
	std::vector<float> b(kFloats, 0.5f);
	Set(port, b.data());
	Advance(ctx);
	Set(port, b.data());
	Advance(ctx);
	Set(port, nullptr);
	Advance(ctx);
	std::fill(b.begin(), b.end(), 0.625f);
	Set(port, b.data());
	Advance(ctx);
	std::fill(b.begin(), b.end(), 0.875f);
	Advance(ctx);
	Check(GrainIs(ctx, 0, port, 0.5f) == 1, "cleared: grain 1");
	Check(GrainIs(ctx, 1, port, 0.5f) == 1, "cleared: grain 2");
	Check(GrainIs(ctx, 2, port, 0.0f) == -2, "cleared: after a null set the port is not in the grain");
	Check(GrainIs(ctx, 3, port, 0.625f) == 1, "cleared: the buffer given after it");
	Check(GrainIs(ctx, 4, port, 0.875f) == 1, "cleared: given once since cleared, it repeats, read at Advance");
	(void)AudioOut2ContextDestroy(ctx);
}

void CaseRoom(bool on) { // 42beeaa46, the timer path
	const auto ctx = MakeContext(2, kRoomGrains); // no port: no device, the timer level
	const auto t0  = std::chrono::steady_clock::now();
	Check(AudioOut2ContextPush(ctx, 1) == 0, "room: the first blocking push");
	const auto t1 = std::chrono::steady_clock::now();
	Check(AudioOut2ContextPush(ctx, 1) == 0, "room: the second blocking push");
	const auto t2    = std::chrono::steady_clock::now();
	uint32_t   level = 99;
	uint32_t   avail = 99;
	(void)AudioOut2ContextGetQueueLevel(ctx, &level, &avail);
	std::printf("aud0401: room: pushes took %.1f and %.1f ms, then level %u of 2 (available %u)\n", Ms(t0, t1), Ms(t1, t2),
	            static_cast<unsigned>(level), static_cast<unsigned>(avail));
	Check(Ms(t0, t1) < kRoomWaitMs, "room: the first push returns at once (the queue had room)");
	if (on) {
		Check(level == 1 && avail == 1, "room: after the push that filled the queue it has room again (level 1 of 2)");
		Check(Ms(t1, t2) >= kRoomWaitMs, "room: that push waited for a grain to play (~85 ms)");
	} else {
		Check(level == 2 && avail == 0, "room: the queue is full after it (2 of 2, today)");
		Check(Ms(t1, t2) < kRoomWaitMs, "room: that push returned at once (today)");
	}
	(void)AudioOut2ContextDestroy(ctx);
}

} // namespace aud0401

int main(int argc, char** argv) {
	using namespace aud0401;
	if (argc != 2 || (std::strcmp(argv[1], "on") != 0 && std::strcmp(argv[1], "off") != 0)) {
		std::printf("usage: aud0401 on|off (with KYTY_BC5_AUDIO_FIXES set to match)\n");
		return 2;
	}
	const bool     want  = std::strcmp(argv[1], "on") == 0;
	const char*    v     = std::getenv("KYTY_BC5_AUDIO_FIXES");
	const uint32_t parts = Parts(v);
	if (want != (parts != 0)) {
		std::printf("aud0401: the argument says %s but KYTY_BC5_AUDIO_FIXES is %s\n", argv[1], v != nullptr ? v : "unset");
		return 2;
	}
	std::printf("aud0401: parts on:%s%s%s%s\n", parts == 0 ? " none" : "", (parts & kPartSet) != 0 ? " set" : "",
	            (parts & kPartSilence) != 0 ? " silence" : "", (parts & kPartRoom) != 0 ? " room" : "");

	setenv("SDL_AUDIODRIVER", "bc5-no-device-0401", 1); // no sound device: SDL's audio init fails, ports open without one
	::Log::Bc5SetLogging(false);                         // the unit's LOGF lines are not needed here
	(void)Libs::LibKernel::KernelGetProcessTime();       // the process clock starts at its first read
	std::this_thread::sleep_for(std::chrono::milliseconds(2));
	Libs::Audio::AudioSubsystem::Instance()->Init(nullptr);

	CaseSet((parts & kPartSet) != 0);
	CaseSilence((parts & kPartSilence) != 0);
	CaseOnce();
	CaseCleared();
	CaseRoom((parts & kPartRoom) != 0);

	Libs::Audio::AudioSubsystem::Instance()->Destroy(nullptr);

	if (g_failed != 0) {
		std::printf("aud0401: %s %d of %d; %d failures\n", argv[1], g_checks - g_failed, g_checks, g_failed);
		return 1;
	}
	std::printf("aud0401: %s %d of %d; end\n", argv[1], g_checks, g_checks);
	return 0;
}
