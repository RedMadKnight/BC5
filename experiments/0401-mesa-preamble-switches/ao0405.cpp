// SPDX-License-Identifier: GPL-2.0-only
// BC5 experiment 0401 series e5, tag ao: the CPU test of mkao0405.py's edit of src/libs/audio.cpp (exp 0405's KA01, KA02,
// KA03 and the extras KA06, KA07, KA08, ported from KytyPS5 dfec14a; notes ao0405-notes.md). It calls the unit's own
// exports, linked with every emulator object but main.cpp.o and the private audio.cpp.o in place of the shared one.
// No game, no GPU, no window, no network and no sound device:
//   - SDL_AUDIODRIVER is set to a driver that does not exist, so SDL_InitSubSystem(SDL_INIT_AUDIO) fails in
//     Audio::OpenSdlDevice and every AudioOut port opens without a device (Audio::AudioOutOpen keeps the port, LOGF only;
//     QueueSdlAudio drops the frames). aud0401.cpp (e4) relies on the same path.
//   - AudioIn has no device in the unit at all; Ngs2 is host memory only.
// Switches, set together by the box script: KYTY_BC5_AUDIOOUT_CHECKS (ka01, ka02), KYTY_BC5_AUDIOIN_CHECKS (ka06, ka07),
// KYTY_BC5_NGS2_RACK_FIX (ka03, ka08); a value naming items turns on only those, and each case expects its item's state.
// With an item off, a case whose today's path ends the process (EXIT, a stack overflow, a render that follows a canary as
// a pointer) is not run: it prints a "skipped" line and is not counted. Every other case runs on and off; off it checks
// today's behaviour.
// Build: build0401.py --gate ao0405.cpp <out> --like src/libs/audio.cpp (the unit's own compile command).
// usage: ao0405 on|off, with the switches set to match ("on": at least one item on; "off": none). Prints one line per case
// and finally "ao0405: on|off N of N; end", exit 0 only then. A watchdog ends a hang with a FAIL line (exit 3).

#include "common/abi.h"
#include "common/logging/log.h"
#include "kernel/pthread.h"
#include "libs/audio.h"

#include <atomic>
#include <chrono>
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

// The unit's own definitions of the types the test passes, token for token (audio.h only declares them).
namespace Libs::Audio::AudioOut {

struct AudioOutOutputParam {
	int         handle;
	const void* ptr;
};

} // namespace Libs::Audio::AudioOut

namespace Libs::Audio::Ngs2 {

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

struct Ngs2VoiceState {
	uint32_t state_flags;
	int32_t  error_code;
};

using Ngs2BufferAllocHandler = int32_t KYTY_SYSV_ABI (*)(Ngs2ContextBufferInfo*);
using Ngs2BufferFreeHandler  = int32_t  KYTY_SYSV_ABI (*)(Ngs2ContextBufferInfo*);

struct Ngs2BufferAllocator {
	Ngs2BufferAllocHandler alloc_handler = nullptr;
	Ngs2BufferFreeHandler  free_handler  = nullptr;
	uintptr_t              user_data     = 0;
};

static_assert(sizeof(Ngs2SystemOption) == 144);
static_assert(sizeof(Ngs2RackOption) == 176);
static_assert(sizeof(Ngs2ContextBufferInfo) == 64);

} // namespace Libs::Audio::Ngs2

namespace ao0405 {

namespace AO = Libs::Audio::AudioOut;
namespace AI = Libs::Audio::AudioIn;
namespace N2 = Libs::Audio::Ngs2;

// The expected codes, from public headers (not from the unit): our tree's libs/errno.h:333-338 and 354-359 (the same
// values as shadPS4 60c42b9 src/core/libraries/audio/audioout_error.h and audioin_error.h); the two Ngs2 codes are
// KytyPS5 dfec14a src/libs/ngs2.cpp:1457 and 2803 (TODO(verify), ao0405-notes.md).
const int kOutInvalidPort  = static_cast<int>(0x80260003u);
const int kOutInvalidSize  = static_cast<int>(0x80260006u);
const int kOutInvalidFreq  = static_cast<int>(0x80260008u);
const int kInInvalidHandle = static_cast<int>(0x80260101u);
const int kInInvalidSize   = static_cast<int>(0x80260102u);
const int kInInvalidFreq   = static_cast<int>(0x80260103u);
const int kInInvalidType   = static_cast<int>(0x80260104u);
const int kInInvalidParam  = static_cast<int>(0x80260106u);
const int kNgs2BadRack     = static_cast<int>(0x804a8202u);
const int kNgs2StateSize   = static_cast<int>(0x804a8011u);

constexpr int      kWatchdogSeconds = 120;
constexpr uint8_t  kCanary          = 0xCC;
constexpr uint32_t kFrames          = 256;
constexpr uint32_t kKa01 = 1u << 0, kKa02 = 1u << 1, kKa06 = 1u << 2, kKa07 = 1u << 3, kKa03 = 1u << 4, kKa08 = 1u << 5;

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
	std::printf("ao0405: case %d %s: %s (%s)\n", g_cases.load(), name, ok ? "ok" : "FAIL", info.c_str());
	std::fflush(stdout);
}

void Skip(const char* name, const char* why) {
	std::printf("ao0405: case - %s: skipped with the item off (%s)\n", name, why);
	std::fflush(stdout);
}

[[noreturn]] void SetupFail(const char* what) {
	std::printf("ao0405: FAIL setup: %s\n", what);
	std::fflush(stdout);
	_exit(2);
}

void Watchdog() {
	const auto start = std::chrono::steady_clock::now();
	while (!g_finished.load()) {
		std::this_thread::sleep_for(std::chrono::milliseconds(50));
		if (std::chrono::steady_clock::now() - start > std::chrono::seconds(kWatchdogSeconds)) {
			std::printf("ao0405: FAIL watchdog: case \"%s\" still running after %d s (a hang); %d of %d cases passed before it\n",
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

// The unit's reading of a group's value (mkao0405.py, Bc5AoParse), repeated: which items the case expects on.
uint32_t Parse(const char* e, const char* const* names, const uint32_t* bits, int n) {
	if (e == nullptr || e[0] == '\0' || std::strcmp(e, "0") == 0) {
		return 0;
	}
	uint32_t all = 0;
	for (int k = 0; k < n; k++) {
		all |= bits[k];
	}
	uint32_t    on = 0;
	const char* p  = e;
	for (;;) {
		const char*  comma = std::strchr(p, ',');
		const size_t len   = comma != nullptr ? static_cast<size_t>(comma - p) : std::strlen(p);
		for (int k = 0; k < n; k++) {
			if (len == std::strlen(names[k]) && std::strncmp(p, names[k], len) == 0) {
				on |= bits[k];
			}
		}
		if (comma == nullptr) {
			break;
		}
		p = comma + 1;
	}
	return on != 0 ? on : all;
}

// Bytes [from, to) of `p` all equal `v`.
bool All(const uint8_t* p, size_t from, size_t to, uint8_t v) {
	for (size_t i = from; i < to; i++) {
		if (p[i] != v) {
			return false;
		}
	}
	return true;
}

size_t Changed(const uint8_t* p, size_t from, size_t to, uint8_t v) {
	size_t n = 0;
	for (size_t i = from; i < to; i++) {
		n += p[i] != v ? 1 : 0;
	}
	return n;
}

// ---- AudioOut: ka01, ka02 --------------------------------------------------------------------------------------------

void CasesAudioOut() {
	g_case = "audioout";
	const int h = AO::AudioOutOpen(255, 0 /* main */, 0, kFrames, 48000, 1 /* S16 stereo */);
	Report("out: a port opens (no device)", h > 0, "handle " + std::to_string(h));
	if (h <= 0) {
		return;
	}

	g_case = "ka02 freq 0";
	{
		const int r = AO::AudioOutOpen(255, 0, 0, kFrames, 0, 1);
		if (On(kKa02)) {
			Report("ka02: AudioOutOpen with freq 0 -> AUDIO_OUT_ERROR_INVALID_SAMPLE_FREQ", r == kOutInvalidFreq, Hex(r));
		} else {
			const int c = r > 0 ? AO::AudioOutClose(r) : -1;
			Report("ka02 off: AudioOutOpen with freq 0 opens a port (today); closed again, its output (a division by 0) not run",
			       r > 0 && c == 0, "handle " + std::to_string(r) + ", close " + std::to_string(c));
		}
	}

	std::vector<int16_t>         pcm(static_cast<size_t>(kFrames) * 2, 0);
	std::vector<AO::AudioOutOutputParam> p(33);
	for (auto& e: p) {
		e.handle = h;
		e.ptr    = pcm.data();
	}

	g_case = "ka01 num 0";
	if (On(kKa01)) {
		const int r = AO::AudioOutOutputs(p.data(), 0);
		Report("ka01: AudioOutOutputs with num 0 -> AUDIO_OUT_ERROR_INVALID_SIZE", r == kOutInvalidSize, Hex(r));
	} else {
		Skip("ka01 off: AudioOutOutputs with num 0", "today's Audio::AudioOutOutputs exits the process on num 0");
	}

	g_case = "ka01 num 33";
	if (On(kKa01)) {
		const int r = AO::AudioOutOutputs(p.data(), 33);
		Report("ka01: AudioOutOutputs with num 33 (all valid) -> AUDIO_OUT_ERROR_INVALID_SIZE, params[] not written",
		       r == kOutInvalidSize, Hex(r));
	} else {
		Skip("ka01 off: AudioOutOutputs with num 33 (all valid)", "today's loop writes params[32], past its 32-entry stack array");
	}

	g_case = "ka01 num 33 bad first";
	{
		std::vector<AO::AudioOutOutputParam> q = p;
		q[0].handle                            = 0; // not a port: today's loop returns at i = 0, before it overflows
		const int r                            = AO::AudioOutOutputs(q.data(), 33);
		if (On(kKa01)) {
			Report("ka01: num 33 with an invalid first handle -> AUDIO_OUT_ERROR_INVALID_SIZE", r == kOutInvalidSize, Hex(r));
		} else {
			Report("ka01 off: num 33 with an invalid first handle -> AUDIO_OUT_ERROR_INVALID_PORT (today)", r == kOutInvalidPort,
			       Hex(r));
		}
	}

	g_case = "outputs num 1";
	{
		const int r = AO::AudioOutOutputs(p.data(), 1);
		Report("out: AudioOutOutputs with num 1 returns the port's frames, on and off", r == static_cast<int>(kFrames),
		       std::to_string(r));
	}

	g_case = "outputs num 32";
	{
		const int r = AO::AudioOutOutputs(p.data(), 32);
		Report("out: AudioOutOutputs with num 32 (the limit) returns the port's frames, on and off",
		       r == static_cast<int>(kFrames), std::to_string(r));
	}

	g_case = "audioout close";
	{
		const int r = AO::AudioOutClose(h);
		Report("out: the port closes", r == 0, std::to_string(r));
	}
}

// ---- AudioIn: ka06, ka07 ---------------------------------------------------------------------------------------------

void CasesAudioIn() {
	g_case = "audioin open";
	const int h = AI::AudioInOpen(255, 1, 0, kFrames, 16000, 0 /* S16 mono */);
	Report("in: a type-1 port opens, on and off", h > 0, "handle " + std::to_string(h));
	if (h <= 0) {
		return;
	}

	g_case = "ka07";
	if (On(kKa07)) {
		const int t0 = AI::AudioInOpen(255, 0, 0, kFrames, 16000, 0);
		Report("ka07: type 0 opens a port", t0 > 0, "handle " + std::to_string(t0));
		const int t2 = AI::AudioInOpen(255, 2, 0, kFrames, 16000, 0);
		Report("ka07: type 2 -> AUDIO_IN_ERROR_INVALID_TYPE", t2 == kInInvalidType, Hex(t2));
		const int i1 = AI::AudioInOpen(255, 1, 1, kFrames, 16000, 0);
		Report("ka07: index 1 -> AUDIO_IN_ERROR_INVALID_PARAM", i1 == kInInvalidParam, Hex(i1));
		const int l0 = AI::AudioInOpen(255, 1, 0, 0, 16000, 0);
		Report("ka07: len 0 -> AUDIO_IN_ERROR_INVALID_SIZE", l0 == kInInvalidSize, Hex(l0));
		const int f0 = AI::AudioInOpen(255, 1, 0, kFrames, 0, 0);
		Report("ka07: freq 0 -> AUDIO_IN_ERROR_INVALID_FREQ", f0 == kInInvalidFreq, Hex(f0));
	} else {
		Skip("ka07 off: AudioInOpen with type 0, type 2, index 1", "today's EXIT_NOT_IMPLEMENTED(type != 1 / index != 0)");
		const int l0 = AI::AudioInOpen(255, 1, 0, 0, 16000, 0);
		Report("ka07 off: len 0 opens a port (today)", l0 > 0, "handle " + std::to_string(l0));
		const int f0 = AI::AudioInOpen(255, 1, 0, kFrames, 0, 0);
		Report("ka07 off: freq 0 opens a port (today; its input, a division by 0, not run)", f0 > 0,
		       "handle " + std::to_string(f0));
	}

	g_case = "ka06 input";
	{
		std::vector<uint8_t> buf(static_cast<size_t>(kFrames) * 4, 0xAA); // twice one mono grain
		const int            r = AI::AudioInInput(h, buf.data());
		if (On(kKa06)) {
			Report("ka06: AudioInInput writes one grain of silence (256 frames x 2 bytes), nothing past it",
			       r == static_cast<int>(kFrames) && All(buf.data(), 0, kFrames * 2, 0) &&
			           All(buf.data(), kFrames * 2, buf.size(), 0xAA),
			       "return " + std::to_string(r) + ", zero bytes " + std::to_string(kFrames * 2 - Changed(buf.data(), 0, kFrames * 2, 0)));
		} else {
			Report("ka06 off: AudioInInput leaves dest as it was (today)",
			       r == static_cast<int>(kFrames) && All(buf.data(), 0, buf.size(), 0xAA), "return " + std::to_string(r));
		}
	}

	g_case = "in bad handle";
	{
		std::vector<uint8_t> buf(64, 0);
		const int            r = AI::AudioInInput(99, buf.data());
		Report("in: AudioInInput with a bad handle -> AUDIO_IN_ERROR_INVALID_HANDLE, on and off", r == kInInvalidHandle, Hex(r));
	}

	g_case = "ka06 null dest";
	if (On(kKa06)) {
		const int r = AI::AudioInInput(h, nullptr);
		Report("ka06: AudioInInput with a null dest returns 0", r == 0, std::to_string(r));
		const int b = AI::AudioInInput(99, nullptr);
		Report("ka06: a null dest with a bad handle -> AUDIO_IN_ERROR_INVALID_HANDLE", b == kInInvalidHandle, Hex(b));
	} else {
		Skip("ka06 off: AudioInInput with a null dest", "today's EXIT_NOT_IMPLEMENTED(dest == nullptr)");
	}
}

// ---- Ngs2: ka03, ka08 ------------------------------------------------------------------------------------------------

constexpr uintptr_t kUserData = 0x0405;

struct Block {
	uint8_t* p    = nullptr;
	size_t   size = 0;
};

std::vector<Block> g_blocks; // every allocation; kept to the end, so that the canary can be read after a "free"
int                g_frees      = 0;
void*              g_freed      = nullptr;
size_t             g_freed_size = 0;
uintptr_t          g_freed_user = 0;

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
	g_blocks.push_back({p, info->host_buffer_size});
	info->host_buffer = p;
	return 0;
}

// The title's free handler: counts and records; the memory stays readable for the canary check.
int32_t KYTY_SYSV_ABI TestFree(N2::Ngs2ContextBufferInfo* info) {
	g_frees++;
	g_freed      = info->host_buffer;
	g_freed_size = info->host_buffer_size;
	g_freed_user = info->user_data;
	return 0;
}

int Render(uintptr_t sys) {
	static std::vector<float> out(512 * 2, 1.0f);
	N2::Ngs2RenderBufferInfo  rb {};
	rb.buffer        = out.data();
	rb.buffer_size   = out.size() * sizeof(float);
	rb.waveform_type = 0;
	rb.num_channels  = 2;
	return N2::Ngs2SystemRender(sys, &rb, 1);
}

void CasesNgs2() {
	g_case = "ngs2 setup";
	// The rack's header and voice sizes, from Ngs2RackQueryBufferSize (header + voice size x max_voices).
	N2::Ngs2RackOption    q {};
	N2::Ngs2ContextBufferInfo i1 {};
	N2::Ngs2ContextBufferInfo i2 {};
	q.max_voices = 1;
	(void)N2::Ngs2RackQueryBufferSize(0x1000, &q, &i1);
	q.max_voices = 2;
	(void)N2::Ngs2RackQueryBufferSize(0x1000, &q, &i2);
	const size_t voice  = i2.host_buffer_size - i1.host_buffer_size;
	const size_t header = i1.host_buffer_size - voice;
	if (voice < 8 || header < 16) {
		SetupFail("Ngs2RackQueryBufferSize gives no usable sizes");
	}

	N2::Ngs2BufferAllocator alloc {};
	alloc.alloc_handler = TestAlloc;
	alloc.free_handler  = TestFree;
	alloc.user_data     = kUserData;
	uintptr_t sys       = 0;
	const int rs        = N2::Ngs2SystemCreateWithAllocator(nullptr, &alloc, &sys);
	Report("ngs2: a system is made with the test allocator", rs == 0 && sys != 0 && g_blocks.size() == 1,
	       "result " + std::to_string(rs));
	uintptr_t rack = 0;
	const int rr   = N2::Ngs2RackCreateWithAllocator(sys, 0x1000, nullptr, &alloc, &rack); // sampler, 256 voices
	const bool made = rr == 0 && rack != 0 && g_blocks.size() == 2 && rack == reinterpret_cast<uintptr_t>(g_blocks[1].p);
	Report("ngs2: a sampler rack is made with the test allocator, in the block it allocated", made,
	       "result " + std::to_string(rr) + ", rack size " + std::to_string(made ? g_blocks[1].size : 0) + " = " +
	           std::to_string(header) + " + 256 x " + std::to_string(voice));
	if (!made || g_blocks[1].size != header + 256 * voice) {
		SetupFail("the rack is not where or as large as expected");
	}
	uint8_t* const rb   = g_blocks[1].p;
	const size_t   size = g_blocks[1].size;

	g_case = "ka03 destroy";
	{
		N2::Ngs2ContextBufferInfo out {};
		std::memset(&out, 0xFF, sizeof(out));
		const int  r      = N2::Ngs2RackDestroy(rack, &out);
		const bool zeroed = All(reinterpret_cast<const uint8_t*>(&out), 0, sizeof(out), 0);
		if (On(kKa03)) {
			Report("ka03: Ngs2RackDestroy calls the free handler once with the rack's buffer, size and user data",
			       r == 0 && g_frees == 1 && g_freed == rb && g_freed_size == size && g_freed_user == kUserData && zeroed,
			       "result " + std::to_string(r) + ", frees " + std::to_string(g_frees) + ", size " + std::to_string(g_freed_size));
		} else {
			Report("ka03 off: Ngs2RackDestroy only zeroes *buffer_info; the free handler is not called (today)",
			       r == 0 && g_frees == 0 && zeroed, "result " + std::to_string(r) + ", frees " + std::to_string(g_frees));
		}
	}

	g_case = "ka03 render, voices canary";
	{
		std::memset(rb + header, kCanary, size - header); // the voices only: the rack's header (its next pointer) kept
		const int    r = Render(sys);
		const size_t n = Changed(rb, header, size, kCanary);
		if (On(kKa03)) {
			Report("ka03: a render after the destroy leaves the freed rack's voices alone", r == 0 && n == 0,
			       std::to_string(n) + " bytes changed");
		} else {
			Report("ka03 off: a render after the destroy writes into the destroyed rack's voices (today's use after free)",
			       r == 0 && n != 0, std::to_string(n) + " bytes changed");
		}
	}

	g_case = "ka03 render, whole canary";
	if (On(kKa03)) {
		std::memset(rb, kCanary, size);
		const int    r = Render(sys);
		const size_t n = Changed(rb, 0, size, kCanary);
		Report("ka03: the whole freed buffer filled with a canary, a render leaves it intact", r == 0 && n == 0,
		       std::to_string(n) + " of " + std::to_string(size) + " bytes changed");
	} else {
		Skip("ka03 off: a render with the whole freed buffer as a canary", "today's walk would follow the canary as the rack's next pointer");
	}

	g_case = "ka03 destroy again";
	{
		const int r1 = N2::Ngs2RackDestroy(rack, nullptr);
		const int r0 = N2::Ngs2RackDestroy(0, nullptr);
		if (On(kKa03)) {
			Report("ka03: a second destroy and a destroy of handle 0 -> 0x804a8202; no second free", r1 == kNgs2BadRack &&
			       r0 == kNgs2BadRack && g_frees == 1, Hex(r1) + ", " + Hex(r0));
		} else {
			Report("ka03 off: a second destroy and a destroy of handle 0 return OK (today)", r1 == 0 && r0 == 0 && g_frees == 0,
			       Hex(r1) + ", " + Hex(r0));
		}
	}

	g_case = "ka03 no allocator";
	{
		N2::Ngs2ContextBufferInfo info {};
		(void)N2::Ngs2RackQueryBufferSize(0x3000, nullptr, &info); // mastering, its default option (1 voice)
		const size_t bytes = (info.host_buffer_size + 63) / 64 * 64;
		auto*        buf   = AlignedBytes(bytes);
		if (buf == nullptr) {
			SetupFail("no memory");
		}
		std::memset(buf, 0, bytes);
		g_blocks.push_back({buf, info.host_buffer_size});
		info.host_buffer = buf;
		info.user_data   = 7;
		uintptr_t r2     = 0;
		const int rc     = N2::Ngs2RackCreate(sys, 0x3000, nullptr, &info, &r2);
		N2::Ngs2ContextBufferInfo out {};
		std::memset(&out, 0xFF, sizeof(out));
		const int r = rc == 0 ? N2::Ngs2RackDestroy(r2, &out) : -1;
		if (On(kKa03)) {
			Report("ka03: a rack made in the title's buffer returns that buffer in *buffer_info", rc == 0 && r == 0 &&
			       out.host_buffer == buf && out.host_buffer_size == info.host_buffer_size && out.user_data == 7 && g_frees == 1,
			       "create " + std::to_string(rc) + ", destroy " + std::to_string(r));
		} else {
			Report("ka03 off: *buffer_info comes back zeroed (today)", rc == 0 && r == 0 &&
			       All(reinterpret_cast<const uint8_t*>(&out), 0, sizeof(out), 0), "create " + std::to_string(rc) + ", destroy " +
			       std::to_string(r));
		}
	}

	// ka08: a custom mastering rack configured with a 16-byte voice state, and a custom sampler rack with a 48-byte one.
	g_case = "ka08 setup";
	N2::Ngs2CustomMasteringRackOption cm {};
	cm.custom_rack_option.rack_option.size              = sizeof(cm);
	cm.custom_rack_option.rack_option.max_grain_samples = 512;
	cm.custom_rack_option.rack_option.max_voices        = 1;
	cm.custom_rack_option.state_size                    = 16;
	cm.custom_rack_option.num_buffers                   = 1;
	cm.max_channels                                     = 2;
	N2::Ngs2CustomSamplerRackOption cs {};
	cs.custom_rack_option.rack_option.size              = sizeof(cs);
	cs.custom_rack_option.rack_option.max_grain_samples = 512;
	cs.custom_rack_option.rack_option.max_voices        = 1;
	cs.custom_rack_option.state_size                    = 48;
	cs.custom_rack_option.num_buffers                   = 1;
	uintptr_t voices[2] = {0, 0};
	const uint32_t ids[2] = {0x4003, 0x4001};
	const N2::Ngs2RackOption* opts[2] = {&cm.custom_rack_option.rack_option, &cs.custom_rack_option.rack_option};
	for (int k = 0; k < 2; k++) {
		uintptr_t r = 0;
		const int c = N2::Ngs2RackCreateWithAllocator(sys, ids[k], opts[k], &alloc, &r);
		const int v = c == 0 ? N2::Ngs2RackGetVoiceHandle(r, 0, &voices[k]) : -1;
		if (c != 0 || v != 0 || voices[k] == 0) {
			SetupFail("a custom rack or its voice was not made");
		}
	}

	g_case = "ka08 mastering";
	{
		alignas(8) uint8_t s[32];
		auto*     st = reinterpret_cast<N2::Ngs2VoiceState*>(s);
		std::memset(s, kCanary, sizeof(s));
		const int r16 = N2::Ngs2VoiceGetState(voices[0], st, 16);
		Report("ka08: custom mastering, a 16-byte buffer as configured: 16 bytes written, on and off",
		       r16 == 0 && All(s, 0, 16, 0) && All(s, 16, 32, kCanary), Hex(r16));
		if (On(kKa08)) {
			std::memset(s, kCanary, sizeof(s));
			const int r32 = N2::Ngs2VoiceGetState(voices[0], st, 32);
			Report("ka08: custom mastering, a 32-byte buffer: OK, 16 bytes written, the rest untouched",
			       r32 == 0 && All(s, 0, 16, 0) && All(s, 16, 32, kCanary), Hex(r32));
			std::memset(s, kCanary, sizeof(s));
			const int r8 = N2::Ngs2VoiceGetState(voices[0], st, 8);
			Report("ka08: custom mastering, an 8-byte buffer -> 0x804a8011, nothing written", r8 == kNgs2StateSize &&
			       All(s, 0, 32, kCanary), Hex(r8));
		} else {
			Skip("ka08 off: custom mastering with a 32- or 8-byte buffer", "today's EXIT_NOT_IMPLEMENTED(state_size != configured_size)");
		}
	}

	g_case = "ka08 sampler";
	{
		alignas(8) uint8_t s[64];
		auto*   st = reinterpret_cast<N2::Ngs2VoiceState*>(s);
		std::memset(s, kCanary, sizeof(s));
		const int r56 = N2::Ngs2VoiceGetState(voices[1], st, 56);
		float     envelope = 0.0f;
		std::memcpy(&envelope, s + 8, sizeof(envelope));
		if (On(kKa08)) {
			Report("ka08: custom sampler (48 configured), a 56-byte buffer: 48 bytes written, the rest untouched",
			       r56 == 0 && All(s, 0, 48, 0) && All(s, 48, 64, kCanary), Hex(r56));
			std::memset(s, kCanary, sizeof(s));
			const int r40 = N2::Ngs2VoiceGetState(voices[1], st, 40);
			Report("ka08: custom sampler, a 40-byte buffer -> 0x804a8011, nothing written", r40 == kNgs2StateSize &&
			       All(s, 0, 64, kCanary), Hex(r40));
		} else {
			Report("ka08 off: custom sampler, a 56-byte buffer gets the sampler layout (envelope 1.0 at byte 8; today)",
			       r56 == 0 && envelope == 1.0f && All(s, 56, 64, kCanary), Hex(r56));
			std::memset(s, kCanary, sizeof(s));
			const int r40 = N2::Ngs2VoiceGetState(voices[1], st, 40);
			Report("ka08 off: custom sampler, a 40-byte buffer: OK, 40 bytes zeroed but the flags (today)",
			       r40 == 0 && All(s, 4, 40, 0) && All(s, 40, 64, kCanary), Hex(r40));
		}
	}
}

} // namespace ao0405

int main(int argc, char** argv) {
	using namespace ao0405;
	if (argc != 2 || (std::strcmp(argv[1], "on") != 0 && std::strcmp(argv[1], "off") != 0)) {
		std::printf("usage: ao0405 on|off (with KYTY_BC5_AUDIOOUT_CHECKS, KYTY_BC5_AUDIOIN_CHECKS, KYTY_BC5_NGS2_RACK_FIX set to match)\n");
		return 2;
	}
	const bool        want    = std::strcmp(argv[1], "on") == 0;
	const char* const out[2]  = {"ka01", "ka02"};
	const uint32_t    outb[2] = {kKa01, kKa02};
	const char* const in[2]   = {"ka06", "ka07"};
	const uint32_t    inb[2]  = {kKa06, kKa07};
	const char* const n2[2]   = {"ka03", "ka08"};
	const uint32_t    n2b[2]  = {kKa03, kKa08};
	const char*       e1      = std::getenv("KYTY_BC5_AUDIOOUT_CHECKS");
	const char*       e2      = std::getenv("KYTY_BC5_AUDIOIN_CHECKS");
	const char*       e3      = std::getenv("KYTY_BC5_NGS2_RACK_FIX");
	g_items = Parse(e1, out, outb, 2) | Parse(e2, in, inb, 2) | Parse(e3, n2, n2b, 2);
	if (want != (g_items != 0)) {
		std::printf("ao0405: the argument says %s but the switches are %s, %s, %s\n", argv[1], e1 != nullptr ? e1 : "unset",
		            e2 != nullptr ? e2 : "unset", e3 != nullptr ? e3 : "unset");
		return 2;
	}
	std::printf("ao0405: items on:%s%s%s%s%s%s%s\n", g_items == 0 ? " none" : "", On(kKa01) ? " ka01" : "",
	            On(kKa02) ? " ka02" : "", On(kKa03) ? " ka03" : "", On(kKa06) ? " ka06" : "", On(kKa07) ? " ka07" : "",
	            On(kKa08) ? " ka08" : "");
	std::fflush(stdout);
	std::thread(Watchdog).detach();

	setenv("SDL_AUDIODRIVER", "bc5-no-device-0405", 1); // no sound device: SDL's audio init fails, ports open without one
	std::printf("ao0405: SDL_AUDIODRIVER=bc5-no-device-0405 (SDL's audio init fails; AudioOut ports open without a device)\n");
	::Log::Bc5SetLogging(false);                   // the unit's LOGF lines are not needed here
	(void)Libs::LibKernel::KernelGetProcessTime(); // the process clock starts at its first read
	std::this_thread::sleep_for(std::chrono::milliseconds(2));
	Libs::Audio::AudioSubsystem::Instance()->Init(nullptr); // prints the three "[bc5] exp 0405: ..." lines (stderr)

	CasesAudioOut();
	CasesAudioIn();
	CasesNgs2();

	g_case = "teardown";
	Libs::Audio::AudioSubsystem::Instance()->Destroy(nullptr);
	g_finished = true;

	const int cases  = g_cases.load();
	const int passed = g_passed.load();
	if (passed != cases || cases == 0) {
		std::printf("ao0405: %s %d of %d; %d failures\n", argv[1], passed, cases, cases - passed);
		return 1;
	}
	std::printf("ao0405: %s %d of %d; end\n", argv[1], passed, cases);
	return 0;
}
