// SPDX-License-Identifier: GPL-2.0-only
// BC5 experiment 0442 (tag tg442): a det test of switch_defaults.hpp. Built twice by test0442.sh, against the shared
// header (589ef163's) and against mk0442.py's, it runs Apply() the way the emulator does at start (the title id from
// "--game <dir>"/sce_sys/param.json through /proc/self/cmdline) and prints each word named in $TG_WORDS (comma list) as
// "NAME=value" or "NAME unset". With "--units" it checks the two readers exp 0442 changed instead: idraws0442.hpp and
// the backend's env_on (SHADOW_LABELS).
#include "bc5/switch_defaults.hpp"

#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>

#ifdef TG442_UNITS
#include "bc5/env_flag.hpp"
#include "bc5/idraws0442.hpp"
#endif

int main(int argc, char** argv) {
#ifdef TG442_UNITS
	if (argc > 1 && std::strcmp(argv[1], "--units") == 0) {
		int fail = 0;
		auto chk = [&](bool ok, const char* what) {
			std::printf("%s %s\n", ok ? "ok  " : "FAIL", what);
			fail += ok ? 0 : 1;
		};
		using bc5::IndirectDraws;
		chk(bc5::indirect_draws_mode(nullptr) == IndirectDraws::off, "INDIRECT_DRAWS unset: off (0x24, 0x2c, 0x38 dropped)");
		chk(bc5::indirect_draws_mode("") == IndirectDraws::off, "INDIRECT_DRAWS empty: off");
		chk(bc5::indirect_draws_mode("0") == IndirectDraws::off, "INDIRECT_DRAWS=0: off (was: DRAW_INDIRECT let through, given-up drop on)");
		chk(bc5::indirect_draws_mode("1") == IndirectDraws::draw, "INDIRECT_DRAWS=1: DRAW_INDIRECT only");
		chk(bc5::indirect_draws_mode("multi") == IndirectDraws::multi, "INDIRECT_DRAWS=multi: all");
		chk(!bc5::env_on(nullptr) && !bc5::env_on("") && !bc5::env_on("0"), "SHADOW_LABELS through env_on: unset, empty, 0 are off");
		chk(bc5::env_on("1"), "SHADOW_LABELS=1: on");
		std::printf("units: %d failed\n", fail);
		return fail == 0 ? 0 : 1;
	}
#endif
	(void)argc;
	(void)argv;
	bc5::switch_defaults::Apply();
	const char* list = std::getenv("TG_WORDS");
	if (list == nullptr) return 2;
	std::string w;
	for (const char* p = list;; p++) {
		if (*p == ',' || *p == 0) {
			if (!w.empty()) {
				const char* v = std::getenv(w.c_str());
				if (v != nullptr) {
					std::printf("%s=%s\n", w.c_str(), v);
				} else {
					std::printf("%s unset\n", w.c_str());
				}
			}
			w.clear();
			if (*p == 0) break;
		} else {
			w += *p;
		}
	}
	return 0;
}
