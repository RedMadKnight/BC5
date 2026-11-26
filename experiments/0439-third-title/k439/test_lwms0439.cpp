// SPDX-License-Identifier: GPL-2.0-only
// BC5 experiment 0439 (tag lw439): det test of the word parser lw439_ms (a copy of the generated unit's, mkpa439.py):
// unset or empty gives the default; a number in [lo, hi] is taken; out of range, a sign, trailing text or junk gives the
// default. BC5_LW439_PLANT_NORANGE (the range check left out) must FAIL.
#include <cstdint>
#include <cstdio>
#include <cstdlib>
static uint64_t lw439_ms(const char* name, uint64_t def, uint64_t lo, uint64_t hi) {
	const char* e = std::getenv(name);
	if (e == nullptr || *e == 0) return def;
	char*          end = nullptr;
	const uint64_t v   = std::strtoull(e, &end, 10);
#ifdef BC5_LW439_PLANT_NORANGE
	(void)lo, (void)hi;
	return end != nullptr && *end == 0 ? v : def;
#else
	return end != nullptr && *end == 0 && v >= lo && v <= hi ? v : def;
#endif
}
int main() {
	int f = 0;
	struct C { const char* v; uint64_t want; } cs[] = {{nullptr, 2000}, {"", 2000}, {"12000", 12000}, {"100", 100}, {"60000", 60000},
	                                                   {"50", 2000}, {"70000", 2000}, {"12000ms", 2000}, {"abc", 2000}, {"-5", 2000}};
	for (const auto& c : cs) {
		if (c.v) setenv("BC5_0439_WAIT_MS", c.v, 1); else unsetenv("BC5_0439_WAIT_MS");
		const uint64_t got = lw439_ms("BC5_0439_WAIT_MS", 2000, 100, 60000);
		if (got != c.want) { std::printf("FAIL [%s]: %llu, want %llu\n", c.v ? c.v : "(unset)", (unsigned long long)got, (unsigned long long)c.want); f++; }
	}
	std::printf("%s (%d failures)\n", f == 0 ? "PASS" : "FAIL", f);
	return f == 0 ? 0 : 1;
}
