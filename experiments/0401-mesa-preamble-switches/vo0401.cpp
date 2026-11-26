// SPDX-License-Identifier: GPL-2.0-only
// BC5 experiment 0401 series e4 (KYTY_BC5_VIDEOOUT_STATUS): a CPU test of the `resolution` answer of
// src/graphics/presentation/videoOut.cpp as mkvo0401.py leaves it, without a window, a GPU or the game.
// Why not the real call: VideoOutGetOutputStatus needs the VideoOut driver (DriverState() exits without it), and the
// driver needs a Graphics::Presenter, which is built from a WindowContext (a window and Vulkan) and whose Impl starts the
// present thread. So the test calls the two functions the edit adds, which hold the whole switch and the whole answer:
//   Bc5VideoOutStatusOn()                         the switch, read once;
//   Bc5VideoOutStatusResolution(today, w, h, n)   what VideoOutGetOutputStatus writes to `resolution`, given today's
//                                                 answer for the port size w x h and n registered buffer sets.
// First, 1 check: the switch's first read is the argument's setting. Then a port's life as VideoOutGetOutputStatus sees
// it, for six port sizes (1280x720 is the launcher's, --screen-width/height
// unset; 1920x1080, 2560x1440, 3840x2160, 3840x1, 1x2160): open (0 sets), RegisterBuffers2 of set 0 (1 set), of set 1
// (2 sets), UnregisterBuffers of both (0 sets). This stand-in registration is exact for the answer's inputs:
// RegisterBuffers2 and UnregisterBuffers change only the port's sets, and Impl::Init is the only writer of the port size
// (mkvo0401.py asserts both on the tree). Expected: on, 2 at every step (sharpemu b1ec286 before registration, AnyPS5
// 4f41f4c37 after it); off, today's class of the port size at every step, the value passed in unchanged. 24 checks.
// Then the switch is read once: with the variable set to the other setting, the switch and an answer stay as they were
// (2 checks). 27 checks in all.
// Exit 0 only after the end line "vo0401: on|off 27 of 27; end"; a failed check prints a FAIL line and exits 1. Each run
// also prints the unit's one line "[bc5] exp 0401: videoout status on|off: ..." on stderr.
// Build (box): the compile command of src/graphics/presentation/videoOut.cpp (compdb entry
// src/CMakeFiles/kyty_emulator.dir/graphics/presentation/videoOut.cpp.o; build0401.py --gate vo0401.cpp <out> --like
// src/graphics/presentation/videoOut.cpp), cleaned as build0401.py cleans it; it includes standard headers only. Link: the
// src/kyty_emulator link command with every emulator object but main.cpp.o, the private videoOut.cpp.o (mkvo0401.py's
// output compiled with that same command) in place of the shared one, plus this object. With the shared videoOut.cpp.o
// the link fails (Libs::VideoOut::Bc5VideoOutStatusOn() is undefined): the link is what shows the private object is in.
// Runtime init: none. The two functions read only the environment and their own function-local statics; no subsystem,
// Config, driver or log needs to be up. The emulator objects' static initialisers run as in npgate0401 and sav0401.
// usage: KYTY_BC5_VIDEOOUT_STATUS=1 ./vo0401 on   KYTY_BC5_VIDEOOUT_STATUS=0 ./vo0401 off   (empty or unset: off too)

#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>

namespace Libs::VideoOut {
// Declared exactly as mkvo0401.py defines them in videoOut.cpp (no header declares them; a mismatch fails the link).
bool     Bc5VideoOutStatusOn();
uint32_t Bc5VideoOutStatusResolution(uint32_t today, uint32_t port_width, uint32_t port_height, int registered_sets);
} // namespace Libs::VideoOut

namespace vo0401 {

constexpr const char* kSwitch = "KYTY_BC5_VIDEOOUT_STATUS";

static int g_checks = 0;
static int g_passed = 0;

static void Check(bool ok, const char* what, uint32_t w, uint32_t h, int sets, uint32_t got, uint32_t want) {
	g_checks++;
	if (ok) {
		g_passed++;
		return;
	}
	std::printf("vo0401: FAIL %s: port %ux%u, %d sets: resolution %u, want %u\n", what, static_cast<unsigned>(w),
	            static_cast<unsigned>(h), sets, static_cast<unsigned>(got), static_cast<unsigned>(want));
}

// Today's line in VideoOutGetOutputStatus (videoOut.cpp:1850 at f848f5c6, kept as it is by mkvo0401.py), copied.
static uint32_t Today(uint32_t w, uint32_t h) {
	return (w >= 3840 || h >= 2160 ? 2u : 1u);
}

static bool EnvOn() { // F767's reading, as the unit's
	const char* e = std::getenv(kSwitch);
	return e != nullptr && e[0] != '\0' && std::strcmp(e, "0") != 0;
}

static bool SetEnv(const char* value) {
#ifdef _WIN32
	return _putenv_s(kSwitch, value) == 0; // the laptop's stand-in run; "" removes it
#else
	return setenv(kSwitch, value, 1) == 0;
#endif
}

struct Port {
	uint32_t w;
	uint32_t h;
};

} // namespace vo0401

int main(int argc, char** argv) {
	using namespace vo0401;
	namespace VO = Libs::VideoOut;
	if (argc != 2 || (std::strcmp(argv[1], "on") != 0 && std::strcmp(argv[1], "off") != 0)) {
		std::printf("usage: vo0401 on|off (with KYTY_BC5_VIDEOOUT_STATUS set to match)\n");
		return 2;
	}
	const bool want = std::strcmp(argv[1], "on") == 0;
	if (want != EnvOn()) {
		const char* e = std::getenv(kSwitch);
		std::printf("vo0401: the argument says %s but KYTY_BC5_VIDEOOUT_STATUS is %s\n", argv[1], e != nullptr ? e : "unset");
		return 2;
	}

	// The switch's first read.
	const bool first = VO::Bc5VideoOutStatusOn();
	Check(first == want, "the switch does not read as the argument says", 0, 0, 0, first ? 1u : 0u, want ? 1u : 0u);

	// A port's life, the first call being the unit's first (its stderr line names port 1280x720 and 0 sets).
	static const Port kPorts[] = {{1280, 720}, {1920, 1080}, {2560, 1440}, {3840, 2160}, {3840, 1}, {1, 2160}};
	static const int  kSteps[] = {0, 1, 2, 0}; // open, set 0 registered, set 1 registered, both unregistered
	for (const Port& p: kPorts) {
		const uint32_t today  = Today(p.w, p.h);
		const uint32_t expect = want ? 2u : today;
		for (const int sets: kSteps) {
			const uint32_t got = VO::Bc5VideoOutStatusResolution(today, p.w, p.h, sets);
			Check(got == expect, sets == 0 ? "no set registered" : "after registration", p.w, p.h, sets, got, expect);
		}
	}

	// Read once: the other setting in the environment changes nothing now.
	if (!SetEnv(want ? "0" : "1")) {
		std::printf("vo0401: FAIL the environment could not be changed\n");
		return 1;
	}
	const bool after = VO::Bc5VideoOutStatusOn();
	Check(after == want, "the switch was read again", 0, 0, 0, after ? 1u : 0u, want ? 1u : 0u);
	const uint32_t again = VO::Bc5VideoOutStatusResolution(1u, 1280, 720, 0);
	Check(again == (want ? 2u : 1u), "the answer followed the changed environment", 1280, 720, 0, again, want ? 2u : 1u);

	if (g_passed != g_checks) {
		std::printf("vo0401: %s %d of %d failed\n", argv[1], g_checks - g_passed, g_checks);
		return 1;
	}
	std::printf("vo0401: %s %d of %d; end\n", argv[1], g_passed, g_checks);
	return 0;
}
