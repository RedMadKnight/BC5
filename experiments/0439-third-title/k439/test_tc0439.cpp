// BC5 exp 0439 (tag tc439): det test of tc0439.hpp on synthetic DualSense input reports, USB (0x01, 64 bytes) and
// Bluetooth (0x31, 78 bytes). The reports go through a copy of what SDL's HIDAPI PS5 driver does with them
// (SDL_hidapi_ps5.c, InoriRus/Kyty 4733b7e: the report-id switch l. 1053-1068, the touch decode l. 1002-1010) and of
// SDL_PrivateJoystickTouchpad's event rule (SDL_joystick.c l. 2793-2850: clamp to 0..1, an event only on a change,
// DOWN / MOTION / UP), then through tc439::on_event as window.cpp calls it, and the points are checked.
//   clang++ -std=c++20 -Wall -Wextra -Werror -o test_tc0439 test_tc0439.cpp && ./test_tc0439
#include "tc0439.hpp"

#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <vector>

namespace {

int g_fail = 0;
#define CHECK(c)                                                                                                       \
	do {                                                                                                               \
		if (!(c)) {                                                                                                    \
			std::printf("FAIL %s:%d %s\n", __FILE__, __LINE__, #c);                                                    \
			g_fail++;                                                                                                  \
		}                                                                                                              \
	} while (0)

struct RawTouch {
	bool     down;
	uint8_t  counter; // the pad's 7-bit contact counter (SDL drops it)
	uint16_t x, y;    // 12 bits each
};

// One input report as the pad sends it. The state packet's touch points are at its offsets 32..39
// (PS5StatePacket_t: ucTouchpadCounter1 at 32, rgucTouchpadData1 at 33, the second point at 36).
std::vector<uint8_t> report(bool bt, const RawTouch& a, const RawTouch& b) {
	std::vector<uint8_t> r(bt ? 78 : 64, 0);
	r[0]               = bt ? 0x31 : 0x01;
	const size_t state = bt ? 2 : 1;
	const RawTouch* t[2] = {&a, &b};
	for (int i = 0; i < 2; i++) {
		uint8_t* p = &r[state + 32 + static_cast<size_t>(i) * 4];
		p[0]       = static_cast<uint8_t>((t[i]->down ? 0x00 : 0x80) | (t[i]->counter & 0x7f));
		p[1]       = static_cast<uint8_t>(t[i]->x & 0xff);
		p[2]       = static_cast<uint8_t>(((t[i]->x >> 8) & 0x0f) | ((t[i]->y & 0x0f) << 4));
		p[3]       = static_cast<uint8_t>(t[i]->y >> 4);
	}
	return r;
}

// SDL's per-finger state and the events it posts (the copy described above).
struct SdlFinger {
	bool  state = false;
	float x = 0.0f, y = 0.0f;
};
struct SdlPad {
	SdlFinger f[2];
};

void sdl_touch(SdlPad& pad, bc5::tc439::Track& track, int finger, bool state, float x, float y) {
	SdlFinger& fi = pad.f[finger];
	if (!state && x == 0.0f && y == 0.0f) {
		x = fi.x;
		y = fi.y;
	}
	x = x < 0.0f ? 0.0f : (x > 1.0f ? 1.0f : x);
	y = y < 0.0f ? 0.0f : (y > 1.0f ? 1.0f : y);
	if (state == fi.state && (!state || (x == fi.x && y == fi.y))) {
		return; // no event
	}
	fi.state = state;
	fi.x     = x;
	fi.y     = y;
	// window.cpp: ControllerTouch(which, finger, type != SDL_CONTROLLERTOUCHPADUP, x, y)
	bc5::tc439::on_event(track, finger, state, x, y);
}

void sdl_report(SdlPad& pad, bc5::tc439::Track& track, const std::vector<uint8_t>& d) {
	const uint8_t* s = nullptr;
	if (d[0] == 0x01) {
		if (d.size() == 10 || d.size() == 78) {
			return; // the simple state packet: no touch points
		}
		s = &d[1];
	} else if (d[0] == 0x31) {
		s = &d[2];
	} else {
		return;
	}
	static const float sx = 1.0f / 1920;
	static const float sy = 1.0f / 1070;
	for (int i = 0; i < 2; i++) {
		const uint8_t* c    = s + 32 + i * 4;
		const bool     down = (c[0] & 0x80) == 0;
		const int      x    = c[1] | ((c[2] & 0x0f) << 8);
		const int      y    = (c[2] >> 4) | (c[3] << 4);
		sdl_touch(pad, track, i, down, static_cast<float>(x) * sx, static_cast<float>(y) * sy);
	}
}

const RawTouch kUp = {false, 0, 0, 0};

void run(bool bt) {
	using namespace bc5::tc439;
	SdlPad pad;
	Track  t;
	Points p = points(t);
	CHECK(p.num == 0 && p.x[0] == 0 && p.y[0] == 0 && p.id[0] == 0 && p.id[1] == 0); // nothing invented

	sdl_report(pad, t, report(bt, kUp, kUp));
	CHECK(points(t).num == 0);

	sdl_report(pad, t, report(bt, {true, 9, 100, 200}, kUp)); // finger 0 down
	p = points(t);
	CHECK(p.num == 1 && p.x[0] == 100 && p.y[0] == 200 && p.id[0] == 1);

	sdl_report(pad, t, report(bt, {true, 9, 1919, 1070}, kUp)); // a move to the pad's corner
	p = points(t);
	CHECK(p.num == 1 && p.x[0] == 1919 && p.y[0] == 1070 && p.id[0] == 1);

	sdl_report(pad, t, report(bt, {true, 9, 1919, 1079}, kUp)); // y above SDL's 1070: SDL clamps it
	p = points(t);
	CHECK(p.num == 1 && p.y[0] == 1070);

	// every raw x and y comes back exactly (SDL's scale undone)
	bool exact = true;
	for (int v = 0; v < 1920; v++) {
		sdl_report(pad, t, report(bt, {true, 9, static_cast<uint16_t>(v), static_cast<uint16_t>(v % 1071)}, kUp));
		p = points(t);
		exact = exact && p.x[0] == v && p.y[0] == v % 1071 && p.id[0] == 1;
	}
	CHECK(exact);

	sdl_report(pad, t, report(bt, {true, 9, 300, 400}, {true, 10, 5, 1000})); // finger 1 down too
	p = points(t);
	CHECK(p.num == 2 && p.x[0] == 300 && p.y[0] == 400 && p.id[0] == 1 && p.x[1] == 5 && p.y[1] == 1000 && p.id[1] == 2);

	sdl_report(pad, t, report(bt, {false, 9, 300, 400}, {true, 10, 6, 1001})); // finger 0 lifts
	p = points(t);
	CHECK(p.num == 1 && p.x[0] == 6 && p.y[0] == 1001 && p.id[0] == 2 && p.id[1] == 0 && p.x[1] == 0);

	sdl_report(pad, t, report(bt, {true, 11, 50, 60}, {true, 10, 6, 1001})); // a new contact on finger 0
	p = points(t);
	CHECK(p.num == 2 && p.x[0] == 50 && p.id[0] == 3 && p.id[1] == 2);

	sdl_report(pad, t, report(bt, kUp, kUp)); // both lift
	p = points(t);
	CHECK(p.num == 0 && p.x[0] == 0 && p.y[0] == 0 && p.id[0] == 0 && p.x[1] == 0 && p.id[1] == 0);

	for (int i = 0; i < 130; i++) { // 130 more contacts: the id runs over 7 bits
		sdl_report(pad, t, report(bt, {true, 0, 10, 10}, kUp));
		sdl_report(pad, t, report(bt, kUp, kUp));
	}
	sdl_report(pad, t, report(bt, {true, 0, 10, 10}, kUp));
	CHECK(points(t).id[0] == ((3 + 131) & 0x7f));

	clear(t); // a disconnect
	CHECK(points(t).num == 0);
}

} // namespace

int main() {
	run(false);
	run(true);
	{ // a Bluetooth pad in SDL's simple mode: the 10-byte report 0x01 has no touch points
		bc5::tc439::Track t;
		SdlPad            pad;
		std::vector<uint8_t> r(10, 0);
		r[0] = 0x01;
		sdl_report(pad, t, r);
		CHECK(bc5::tc439::points(t).num == 0);
	}
	{ // to_pad's ends
		CHECK(bc5::tc439::to_pad(-1.0f, 1920.0f, 1920) == 0);
		CHECK(bc5::tc439::to_pad(1.0f, 1920.0f, 1920) == 1919);
		CHECK(bc5::tc439::to_pad(1.0f, 1070.0f, 1080) == 1070);
		bc5::tc439::Track t; CHECK(bc5::tc439::on_event(t, 2, true, 0.5f, 0.5f) == 0 && bc5::tc439::points(t).num == 0);
	}
	std::printf("test_tc0439: %s (%d failed)\n", g_fail == 0 ? "PASS" : "FAIL", g_fail);
	return g_fail == 0 ? 0 : 1;
}
