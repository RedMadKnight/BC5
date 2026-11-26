#!/usr/bin/env python3
# BC5 exp 0439 (tag tc439, 11-22 evening, the top session's order after the name-writing scene went black under the
# maintainer's touchpad strokes): the DualSense touchpad's fingers reach the title, for every title, on unless
# KYTY_BC5_0439_PAD_TOUCH=0. bc5/tc0439.hpp holds the logic (det-tested, k439/test_tc0439.cpp); this script wires it in.
#   controller.cpp: the touch points in ControllerState, a Track per pad slot, GameController::Touch and ControllerTouch,
#                   the points put into every state read (as the motion sample is), cleared at a disconnect, filled into
#                   PadData (touch_num, x/y/id of both points; nothing when no finger is down), and the resolution answer
#                   1920 x 1080. With "0": exp 0419's behaviour (no points, ids 1 and 2, 1920 x 943).
#                   tp439 (KYTY_BC5_0439_PAD_TIME, on unless "0"): a state read with no new input event carries the read's
#                   own time, not the last event's (a pad samples about 250 times a second, each sample its own time;
#                   until now a touch stroke or a still pad read the same timestamp frame after frame).
#   window.cpp:     SDL's controller-touchpad events of touchpad 0 go to ControllerTouch (they were dropped).
# Usage: python mktc439.py controller.cpp window.cpp OUT_DIR   (window.cpp after mkwt439.py; every anchor exactly once)
import os
import sys

ctl, win, out = sys.argv[1], sys.argv[2], sys.argv[3]


def load(p):
    s = open(p, 'rb').read().decode('utf-8', 'surrogateescape')
    assert 'tc439' not in s, p
    return s, '\r\n' in s


def save(p, s, crlf):
    if crlf:
        s = s.replace('\n', '\r\n')
    open(p, 'wb').write(s.encode('utf-8', 'surrogateescape'))
    print('mktc439: wrote', p)


s, crlf_c = load(ctl)
s = s.replace('\r\n', '\n')


def rep(a, b):
    global s
    assert s.count(a) == 1, (a[:70], s.count(a))
    s = s.replace(a, b)


rep('#include "libs/padData.h"\n', '#include "libs/padData.h"\n#include "bc5/tc0439.hpp" // exp 0439 (tag tc439)\n')
rep(' // BC5: x, y, z, w\n};\n', ''' // BC5: x, y, z, w
	bc5::tc439::Points touch {}; // exp 0439 (tag tc439): the fingers on the touchpad at read time
};
''')
rep('''static constexpr int PAD_TOUCH_RESOLUTION_Y = 943;
''', '''static constexpr int PAD_TOUCH_RESOLUTION_Y = 943;

// exp 0439 (tag tc439): KYTY_BC5_0439_PAD_TOUCH, the touchpad's fingers for every title, on unless "0" (bc5/tc0439.hpp).
static bool tc439_on() {
	static const bool on = [] {
		const char* e = std::getenv("KYTY_BC5_0439_PAD_TOUCH");
		return !(e != nullptr && e[0] == '0' && e[1] == 0);
	}();
	return on;
}
// exp 0439 (tag tp439): KYTY_BC5_0439_PAD_TIME, a state read with no new event carries the read's time; on unless "0".
static bool tp439_on() {
	static const bool on = [] {
		const char* e = std::getenv("KYTY_BC5_0439_PAD_TIME");
		return !(e != nullptr && e[0] == '0' && e[1] == 0);
	}();
	return on;
}
''')
rep('''	void Motion(int id, bool gyro, const float* xyz);
''', '''	void Motion(int id, bool gyro, const float* xyz);
	void Touch(int id, int finger, bool down, float x, float y); // exp 0439 (tag tc439)
''')
rep('''		bool                                  gyro_seen = false;
	};
''', '''		bool                                  gyro_seen = false;
		bc5::tc439::Track                     touch; // exp 0439 (tag tc439): the two fingers, the latest sample
	};
''')
rep('''			state->orient[k] = s.orient[k];
		}
	}
''', '''			state->orient[k] = s.orient[k];
		}
		if (tc439_on()) { // exp 0439 (tag tc439)
			state->touch = bc5::tc439::points(s.touch);
		}
	}
''')
rep('''	data->touch_data_touch0_id   = 1;
	data->touch_data_touch1_id   = 2;
''', '''	if (!tc439_on()) { // exp 0439 (tag tc439): KYTY_BC5_0439_PAD_TOUCH=0, exp 0419's placeholder ids
		data->touch_data_touch0_id = 1;
		data->touch_data_touch1_id = 2;
	} else { // the fingers down, packed from point 0; no finger: touch_num 0 and zero points (the memset above)
		data->touch_data_touch_num = state.touch.num;
		data->touch_data_touch0_x  = state.touch.x[0];
		data->touch_data_touch0_y  = state.touch.y[0];
		data->touch_data_touch0_id = state.touch.id[0];
		data->touch_data_touch1_x  = state.touch.x[1];
		data->touch_data_touch1_y  = state.touch.y[1];
		data->touch_data_touch1_id = state.touch.id[1];
	}
''')
rep('''void ControllerMotion(int id, bool gyro, const float* xyz) {
	if (g_controller != nullptr && xyz != nullptr) {
		g_controller->Motion(id, gyro, xyz);
	}
}
''', '''void ControllerMotion(int id, bool gyro, const float* xyz) {
	if (g_controller != nullptr && xyz != nullptr) {
		g_controller->Motion(id, gyro, xyz);
	}
}

// exp 0439 (tag tc439): one SDL controller-touchpad event of touchpad 0 (x, y in 0..1 as SDL gives them).
void ControllerTouch(int id, int finger, bool down, float x, float y) {
	if (g_controller != nullptr && tc439_on()) {
		g_controller->Touch(id, finger, down, x, y);
	}
}
''')
rep('''void GameController::ResetOrientation(int index) {
''', '''void GameController::Touch(int id, int finger, bool down, float x, float y) { // exp 0439 (tag tc439)
	Common::LockGuard lock(m_mutex);

	int slot = OwnerSlot(id);
	if (slot == -1) {
		slot = FallbackSlot();
	}
	EnsureSlot(slot);
	auto&     s      = m_slots[static_cast<size_t>(slot)];
	const int change = bc5::tc439::on_event(s.touch, finger, down, x, y);
	static const bool trace_env = BC5_DIAG_ENV("KYTY_BC5_INPUT_TRACE") != nullptr;
	if (change != 0 && trace_env && ::Log::Bc5LoggingOn()) {
		const auto& f = s.touch.f[finger];
		std::fprintf(stderr, "input trace: t=%.3f touch finger %d %s at %u,%u id %u -> slot %d\\n", InputTraceSeconds(), finger,
		             change > 0 ? "down" : "up", f.x, f.y, f.id, slot);
		std::fflush(stderr);
	}
}

void GameController::ResetOrientation(int index) {
''')
rep('''	s.last_state  = ControllerState();
}

ControllerState GameController::GetLastState(int index) const {
''', '''	s.last_state  = ControllerState();
	bc5::tc439::clear(s.touch); // exp 0439 (tag tc439): no finger stays down on an unplugged pad
}

ControllerState GameController::GetLastState(int index) const {
''')
rep('''	*state = GetLastState(index);
	ApplyMotion(index, state);
''', '''	*state = GetLastState(index);
	ApplyMotion(index, state);
	if (tp439_on()) { // exp 0439 (tag tp439): the read's own time (TODO(verify) the console's unit and its sampling period)
		state->time = LibKernel::KernelGetProcessTime();
	}
''')
rep('''	info->touch_resolution_x    = PAD_TOUCH_RESOLUTION_X;
	info->touch_resolution_y    = PAD_TOUCH_RESOLUTION_Y;
''', '''	info->touch_resolution_x    = tc439_on() ? bc5::tc439::kResX : PAD_TOUCH_RESOLUTION_X; // exp 0439 (tag tc439)
	info->touch_resolution_y    = tc439_on() ? bc5::tc439::kResY : PAD_TOUCH_RESOLUTION_Y;
''')
assert s.count('tag tc439') == 11 and s.count('tag tp439') == 2, (s.count('tag tc439'), s.count('tag tp439'))
save(os.path.join(out, 'controller.cpp'), s, crlf_c)

s, crlf_w = load(win)
s = s.replace('\r\n', '\n')
rep('#include "graphics/presentation/window.h"\n', '''#include "graphics/presentation/window.h"

namespace Libs::Controller { // exp 0439 (tag tc439): src/libs/controller.cpp
void ControllerTouch(int id, int finger, bool down, float x, float y);
} // namespace Libs::Controller
''')
rep('''		case SDL_CONTROLLERTOUCHPADDOWN:
		case SDL_CONTROLLERTOUCHPADMOTION:
		case SDL_CONTROLLERTOUCHPADUP: // exp 0419 phase 2: KYTY_BC5_PAD_TOUCH is gone; touch points are not forwarded
			break;
''', '''		case SDL_CONTROLLERTOUCHPADDOWN:
		case SDL_CONTROLLERTOUCHPADMOTION:
		case SDL_CONTROLLERTOUCHPADUP: // exp 0439 (tag tc439): the fingers go to the pad data (KYTY_BC5_0439_PAD_TOUCH)
			if (event->ctouchpad.touchpad == 0) {
				::Libs::Controller::ControllerTouch(event->ctouchpad.which, event->ctouchpad.finger,
				                                    event->type != SDL_CONTROLLERTOUCHPADUP, event->ctouchpad.x, event->ctouchpad.y);
			}
			break;
''')
save(os.path.join(out, 'window.cpp'), s, crlf_w)
