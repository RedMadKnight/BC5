// SPDX-License-Identifier: GPL-2.0
// Experiment 0193: which SDL driver opens the DualSense under the launch environment, and what a
// touchpad press looks like to SDL. Built against the emulator's own SDL2 (KytyPlus 3rdparty,
// libSDL2.a from ~/bc5-work/kytyplus-build), so the answer is the one kyty_emulator gets.
//
//   padprobe [seconds]   lists every joystick, opens the game controllers, then prints button,
//                        touchpad-finger and raw joystick-button events for <seconds> (default 0).
#include <SDL.h>
#include <stdio.h>
#include <stdlib.h>

static const char* driver_of(SDL_JoystickGUID g) {
	// SDL 2.26+: byte 14 of a GUID names the driver that made it ('h' HIDAPI, 'v' virtual,
	// 'r' raw input, 'w' WGI, 'x' XInput); Linux evdev GUIDs carry the device version there.
	switch (g.data[14]) {
		case 'h': return "HIDAPI";
		case 'v': return "virtual";
		default: return "evdev (linux joystick)";
	}
}

int main(int argc, char** argv) {
	const int seconds = argc > 1 ? atoi(argv[1]) : 0;
	SDL_version v;
	SDL_GetVersion(&v);
	printf("SDL %d.%d.%d, SDL_JOYSTICK_DISABLE_UDEV=%s SDL_JOYSTICK_HIDAPI=%s\n", v.major, v.minor,
	       v.patch, getenv("SDL_JOYSTICK_DISABLE_UDEV") ? getenv("SDL_JOYSTICK_DISABLE_UDEV") : "(unset)",
	       getenv("SDL_JOYSTICK_HIDAPI") ? getenv("SDL_JOYSTICK_HIDAPI") : "(unset)");
	if (SDL_Init(SDL_INIT_GAMECONTROLLER | SDL_INIT_JOYSTICK | SDL_INIT_EVENTS) < 0) {
		printf("SDL_Init: %s\n", SDL_GetError());
		return 1;
	}
	// Give SDL a moment to enumerate (HIDAPI devices are found on a later pump).
	for (int i = 0; i < 20; i++) {
		SDL_PumpEvents();
		SDL_Delay(50);
	}
	SDL_FlushEvents(SDL_FIRSTEVENT, SDL_LASTEVENT);
	const int n = SDL_NumJoysticks();
	printf("%d joystick(s)\n", n);
	for (int i = 0; i < n; i++) {
		char guid[64];
		SDL_JoystickGUID g = SDL_JoystickGetDeviceGUID(i);
		SDL_JoystickGetGUIDString(g, guid, sizeof(guid));
		printf("[%d] \"%s\" path %s guid %s driver %s gamecontroller %d\n", i, SDL_JoystickNameForIndex(i),
		       SDL_JoystickPathForIndex(i) ? SDL_JoystickPathForIndex(i) : "?", guid, driver_of(g),
		       SDL_IsGameController(i));
		if (!SDL_IsGameController(i)) continue;
		SDL_GameController* pad = SDL_GameControllerOpen(i);
		if (pad == NULL) {
			printf("    open: %s\n", SDL_GetError());
			continue;
		}
		char* mapping = SDL_GameControllerMapping(pad);
		printf("    type %d, mapping: %s\n", SDL_GameControllerGetType(pad), mapping ? mapping : "(none)");
		SDL_free(mapping);
		static const SDL_GameControllerButton probe[] = {
		    SDL_CONTROLLER_BUTTON_BACK, SDL_CONTROLLER_BUTTON_GUIDE, SDL_CONTROLLER_BUTTON_START,
		    SDL_CONTROLLER_BUTTON_MISC1, SDL_CONTROLLER_BUTTON_TOUCHPAD};
		for (size_t k = 0; k < sizeof(probe) / sizeof(probe[0]); k++) {
			printf("    has button %-8s (%2d): %d\n", SDL_GameControllerGetStringForButton(probe[k]),
			       probe[k], SDL_GameControllerHasButton(pad, probe[k]));
		}
		printf("    touchpads %d (fingers on the first: %d), accel %d gyro %d, raw buttons %d\n",
		       SDL_GameControllerGetNumTouchpads(pad),
		       SDL_GameControllerGetNumTouchpads(pad) > 0 ? SDL_GameControllerGetNumTouchpadFingers(pad, 0) : 0,
		       SDL_GameControllerHasSensor(pad, SDL_SENSOR_ACCEL), SDL_GameControllerHasSensor(pad, SDL_SENSOR_GYRO),
		       SDL_JoystickNumButtons(SDL_GameControllerGetJoystick(pad)));
	}
	if (seconds <= 0) {
		SDL_Quit();
		return 0;
	}
	printf("listening %d s: press the touchpad (left half, right half), then Create, PS, mic\n", seconds);
	fflush(stdout);
	const Uint32 end = SDL_GetTicks() + (Uint32)seconds * 1000u;
	while (SDL_GetTicks() < end) {
		SDL_Event e;
		while (SDL_PollEvent(&e)) {
			const double t = e.common.timestamp / 1000.0;
			switch (e.type) {
				case SDL_CONTROLLERBUTTONDOWN:
				case SDL_CONTROLLERBUTTONUP:
					printf("%8.3f controller %d button %-8s (%2d) %s\n", t, e.cbutton.which,
					       SDL_GameControllerGetStringForButton((SDL_GameControllerButton)e.cbutton.button),
					       e.cbutton.button, e.type == SDL_CONTROLLERBUTTONDOWN ? "down" : "up");
					break;
				case SDL_CONTROLLERTOUCHPADDOWN:
				case SDL_CONTROLLERTOUCHPADUP:
					printf("%8.3f controller %d touchpad %d finger %d %s at x %.3f y %.3f\n", t,
					       e.ctouchpad.which, e.ctouchpad.touchpad, e.ctouchpad.finger,
					       e.type == SDL_CONTROLLERTOUCHPADDOWN ? "down" : "up", e.ctouchpad.x, e.ctouchpad.y);
					break;
				case SDL_JOYBUTTONDOWN:
				case SDL_JOYBUTTONUP:
					printf("%8.3f joystick %d raw button %d %s\n", t, e.jbutton.which, e.jbutton.button,
					       e.type == SDL_JOYBUTTONDOWN ? "down" : "up");
					break;
				case SDL_CONTROLLERDEVICEADDED:
				case SDL_CONTROLLERDEVICEREMOVED:
					printf("%8.3f controller %d %s\n", t, e.cdevice.which,
					       e.type == SDL_CONTROLLERDEVICEADDED ? "added" : "removed");
					break;
				default: break;
			}
			fflush(stdout);
		}
		SDL_Delay(5);
	}
	SDL_Quit();
	return 0;
}
