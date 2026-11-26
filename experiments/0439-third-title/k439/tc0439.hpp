// BC5 exp 0439 (tag tc439): the DualSense touchpad's fingers for the pad data the title reads.
//
// Why: the third title's name-writing scene ("use the touchpad to write their names") needs finger positions. The host
// gave none since exp 0419 removed exp 0193's opt-in KYTY_BC5_PAD_TOUCH: pad_fill_data zeroed PadData and set only the
// touch ids 1 and 2, so the title always read touch_num 0. Now on for every title (KYTY_BC5_0439_PAD_TOUCH, on unless
// "0"; 11-22, the top session's order with the maintainer's report of the scene).
//
// The path: SDL's HIDAPI PS5 driver parses the DualSense's input report itself, USB report 0x01 (the state at data[1])
// and Bluetooth report 0x31 (the state at data[2]), into the same PS5StatePacket_t; each of the two touch points is a
// counter byte (bit 7 set = no finger, bits 0-6 the pad's contact counter) and 12-bit x / 12-bit y, and SDL hands them on
// as finger 0/1 events with x / 1920 and y / 1070 (SDL_hidapi_ps5.c, HIDAPI_DriverPS5_HandleStatePacket and its
// TOUCHPAD_SCALEX/Y, InoriRus/Kyty 4733b7e source/3rdparty/sdl2, l. 889-1010 and 1053-1068; TODO(verify) the same lines in
// the box's SDL 2.33.0). SDL drops the contact counter, so the id is made here: a new one per new contact, 7 bits, one
// counter per pad, as the counter byte runs. A BT pad in SDL's simple mode (10-byte report 0x01) carries no touch at all.
//
// Units: the positions are the pad's own (SDL's scale undone: x = nx * 1920, y = ny * 1070, which gives back the
// report's 12-bit values), clamped to the resolution this host answers in scePadGetControllerInformation: 1920 x 1080
// (AnyPS5 27c88a8d75 core/libs/prx/libScePad/include/PadState.hpp:9-10; KytyPlus f266548 answered 1920 x 943, a DS4's;
// TODO(verify) the console's answer for a DualSense). Nothing is invented: no finger down, touch_num 0 and zero points.
// Header-only, no host types: det-tested by k439/test_tc0439.cpp on synthetic USB and BT reports.
#pragma once

#include <cstdint>

namespace bc5::tc439 {

constexpr int   kResX   = 1920; // the answer in scePadGetControllerInformation
constexpr int   kResY   = 1080;
constexpr float kSdlX   = 1920.0f; // SDL's TOUCHPAD_SCALEX = 1 / 1920
constexpr float kSdlY   = 1070.0f; // SDL's TOUCHPAD_SCALEY = 1 / 1070

struct Finger {
	bool          down = false;
	std::uint16_t x    = 0;
	std::uint16_t y    = 0;
	std::uint8_t  id   = 0;
};

struct Track {
	Finger       f[2];
	std::uint8_t counter = 0; // the last contact id given (7 bits)
};

struct Points {
	std::uint8_t  num  = 0;
	std::uint16_t x[2] = {0, 0};
	std::uint16_t y[2] = {0, 0};
	std::uint8_t  id[2] = {0, 0};
};

inline std::uint16_t to_pad(float n, float sdl_scale, int res) {
	const float v = n * sdl_scale + 0.5f;
	const int   p = v <= 0.0f ? 0 : static_cast<int>(v);
	return static_cast<std::uint16_t>(p >= res ? res - 1 : p);
}

// One SDL controller-touchpad event (DOWN, MOTION or UP) of touchpad 0. Returns 1 for a new contact, -1 for a lift,
// 0 otherwise (a motion, or an event for a finger outside 0..1).
inline int on_event(Track& t, int finger, bool down, float nx, float ny) {
	if (finger < 0 || finger > 1) {
		return 0;
	}
	Finger&   f       = t.f[finger];
	const int change  = down && !f.down ? 1 : (!down && f.down ? -1 : 0);
	if (change == 1) {
		t.counter = static_cast<std::uint8_t>((t.counter + 1) & 0x7f);
		f.id      = t.counter;
	}
	f.down = down;
	if (down) {
		f.x = to_pad(nx, kSdlX, kResX);
		f.y = to_pad(ny, kSdlY, kResY);
	} else {
		f.x = 0;
		f.y = 0;
		f.id = 0;
	}
	return change;
}

inline void clear(Track& t) {
	t.f[0] = Finger();
	t.f[1] = Finger();
}

// The fingers down, finger 0 first, packed from point 0 (the console's touch_num counts the valid points).
inline Points points(const Track& t) {
	Points p;
	for (const Finger& f : t.f) {
		if (!f.down) {
			continue;
		}
		p.x[p.num]  = f.x;
		p.y[p.num]  = f.y;
		p.id[p.num] = f.id;
		p.num++;
	}
	return p;
}

} // namespace bc5::tc439
