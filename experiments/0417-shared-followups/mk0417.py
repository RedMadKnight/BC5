#!/usr/bin/env python3
"""BC5 experiment 0417: the small follow-ups to the integration of 2026-11-13 (patch 0001 4651d1d3), as edits on
pinned inputs. They ride with the next swap of the shared builds, not their own (the top session, 2026-11-13).

  ampr     src/libs/libAmpr.cpp (md5 a2d09d32):
           1. Wording. With exp 0413's guard off, exp 0416's line said "a target that is not mapped" for mapped
              targets too. It now says what is known at that point: the guard did not take the call.
           2. The test hook for a forced a4 = -1 on a real call, KYTY_BC5_AMM_SETBUFFER_TEST. Compiled only when
              KYTY_BC5_SETBUFFER_TEST_HOOK is 1 (src/bc5/setbuffer_test.hpp says 0; a PRIVATE build's kit sets it
              to 1), so no shared binary has it. Off when unset.
                mapped[:N]    the Nth set-buffer call of the title (default the first) gets a4 = -1 and, if needed,
                              a3 != va: the map signature on the title's own, committed buffer. With the guard on the
                              guard's line must follow and the title must run on.
                unmapped[:N]  before the Nth call, one synthetic call with the map signature on an address nothing
                              is mapped at (KYTY_BC5_AMM_SETBUFFER_TEST_VA, hex, default 0x8ff0000000, inside the AMM
                              window; skipped with a line if something is there). With the map opt-in off exp 0416's
                              line must follow and nothing may be mapped; with KYTY_BC5_AMM_SETBUFFER_MAP=1 the real
                              ExecuteAmmMapCommand runs. The hook prints the result and the kernel query's answer
                              before and after. The title's own call is not changed.
  header   the new file src/bc5/setbuffer_test.hpp (written to <out>).
  memory   src/kernel/memory.cpp (md5 eff24b4c): one line, once, for each of the two code defaults that printed
           nothing when asked: KYTY_BC5_RANGES_FAST (C2) says "on" or "off" at its first use; KYTY_BC5_PHYSMAP_SORTED
           (C3) now also says "off". With these and the lines that exist (C1 "pending cap", A2's journal line
           "acb state restore", exp 0415's APR line) a log shows what KYTY_BC5_SWITCH_DEFAULTS=0 left on.
  agc      src/libs/bc5LleAgc.cpp (md5 a81efd2c): A2's line "exp 0401: acb state restore (exp 0381) on/off" also goes
           to stderr, once (the top session, 2026-11-13: the lean build has no journal, and KYTY_BC5_SWITCH_DEFAULTS=0
           must be checkable from a play log in both builds).
usage: mk0417.py ampr|memory|agc <in> <out>      mk0417.py header <out>"""
import hashlib
import sys

what = sys.argv[1]
if what == "header":
    open(sys.argv[2], "wb").write(b"""// Experiment 0417: the compile-time gate of the set-buffer test hook (libAmpr.cpp, KYTY_BC5_AMM_SETBUFFER_TEST).
// 0 here: no shared build has the hook. A private build's kit sets it to 1 (this file or -D).
#ifndef KYTY_BC5_SETBUFFER_TEST_HOOK
#define KYTY_BC5_SETBUFFER_TEST_HOOK 0
#endif
#if KYTY_BC5_SETBUFFER_TEST_HOOK
#include <atomic>
#endif
""")
    print("header ok")
    sys.exit(0)
src, dst = sys.argv[2:4]
s = open(src, "rb").read()
assert b"\r" not in s
md5 = hashlib.md5(s).hexdigest()


def rep(old, new):
    global s
    assert s.count(old) == 1, (old[:70], s.count(old))
    s = s.replace(old, new)


if what == "ampr":
    assert md5 == "a2d09d3244eeb93af0322d5f1abe755f", md5
    rep(b'#include "bc5/apr_posix.hpp" // experiment 0415 (ls415b/c): KYTY_BC5_APR_POSIX\n',
        b'#include "bc5/apr_posix.hpp" // experiment 0415 (ls415b/c): KYTY_BC5_APR_POSIX\n'
        b'#include "bc5/setbuffer_test.hpp" // experiment 0417: the gate of the set-buffer test hook (0 in shared builds)\n')
    rep(b'"[bc5] exp 0416: set-buffer with the map signature on a target that is not mapped (cb 0x%016" PRIx64 " va 0x%016" PRIx64\n',
        b'"[bc5] exp 0416: set-buffer with the map signature that the guard did not take (target not mapped, or guard off) (cb 0x%016" PRIx64 " va 0x%016" PRIx64\n')
    rep(b"""static int KYTY_SYSV_ABI CommandBufferSetBuffer(void* command_buffer, void* buffer, uint32_t size,
                                                uint64_t a3, uint64_t a4, uint64_t a5) {
	PRINT_NAME();
""", b"""#if KYTY_BC5_SETBUFFER_TEST_HOOK
// Experiment 0417, private builds only (bc5/setbuffer_test.hpp): KYTY_BC5_AMM_SETBUFFER_TEST=mapped[:N]|unmapped[:N].
// No title of ours passes a4 = -1 on purpose, and chance stopped producing it (exp 0416), so the guard and the map
// opt-in are exercised by forcing the signature on the Nth call (mapped) or by one synthetic call before it (unmapped).
struct Bc5SbTest {
	int      mode = 0; // 0 off, 1 mapped, 2 unmapped
	int      nth  = 1;
	uint64_t va   = 0x8ff0000000ull;
};
static const Bc5SbTest& Bc5SbTestCfg() {
	static const Bc5SbTest cfg = [] {
		Bc5SbTest   t;
		const char* e = std::getenv("KYTY_BC5_AMM_SETBUFFER_TEST");
		if (e == nullptr || e[0] == '\\0' || std::strcmp(e, "0") == 0) {
			return t;
		}
		if (std::strncmp(e, "unmapped", 8) == 0) {
			t.mode = 2;
			e += 8;
		} else if (std::strncmp(e, "mapped", 6) == 0) {
			t.mode = 1;
			e += 6;
		} else {
			std::fprintf(stderr, "[bc5] exp 0417 hook: KYTY_BC5_AMM_SETBUFFER_TEST not understood, off\\n");
			return t;
		}
		if (e[0] == ':' && std::atoi(e + 1) >= 1) {
			t.nth = std::atoi(e + 1);
		}
		if (const char* v = std::getenv("KYTY_BC5_AMM_SETBUFFER_TEST_VA"); v != nullptr && v[0] != '\\0') {
			t.va = std::strtoull(v, nullptr, 16) & ~(AMM_PAGE_SIZE - 1u);
		}
		std::fprintf(stderr, "[bc5] exp 0417 hook: KYTY_BC5_AMM_SETBUFFER_TEST %s on set-buffer call %d (test va 0x%" PRIx64 ")\\n", t.mode == 1 ? "mapped" : "unmapped",
		             t.nth, t.va);
		return t;
	}();
	return cfg;
}
static int KYTY_SYSV_ABI CommandBufferSetBuffer(void* cb, void* buffer, uint32_t size, uint64_t a3, uint64_t a4, uint64_t a5); // defined below
static bool Bc5SbTestCommitted(uint64_t va) {
	LibKernel::Memory::VirtualQueryInfo info {};
	return LibKernel::Memory::KernelVirtualQuery(reinterpret_cast<const void*>(va), 0, &info, sizeof(info)) == OK && info.is_committed != 0;
}
static void Bc5SbTestApply(uint64_t cb, uint64_t va, uint32_t size, uint64_t* a3, uint64_t* a4) {
	const Bc5SbTest& c = Bc5SbTestCfg();
	if (c.mode == 0) {
		return;
	}
	static thread_local bool inside = false; // the synthetic call below comes through here again
	static std::atomic<int>  calls {0};
	if (inside || ++calls != c.nth) {
		return;
	}
	if (c.mode == 1) {
		std::fprintf(stderr, "[bc5] exp 0417 hook: call %d (cb 0x%016" PRIx64 " va 0x%016" PRIx64 " len 0x%x a3 0x%" PRIx64 " a4 0x%" PRIx64 "): a4 forced to -1%s; the target is %s\\n",
		             c.nth, cb, va, size, *a3, *a4, *a3 == va ? ", a3 changed" : "", Bc5SbTestCommitted(va & ~(AMM_PAGE_SIZE - 1u)) ? "committed" : "NOT committed");
		if (*a3 == va) {
			*a3 = va ^ 0x10u;
		}
		*a4 = ~0ull;
		return;
	}
	if (Bc5SbTestCommitted(c.va)) {
		std::fprintf(stderr, "[bc5] exp 0417 hook: the test va 0x%" PRIx64 " is committed, nothing done (set KYTY_BC5_AMM_SETBUFFER_TEST_VA)\\n", c.va);
		return;
	}
	alignas(16) static unsigned char header[0x100] = {}; // a scratch command-buffer header: the buffer flavour may write its pointers here
	inside        = true;
	const int rc  = CommandBufferSetBuffer(header, reinterpret_cast<void*>(c.va), static_cast<uint32_t>(AMM_PAGE_SIZE), 1, ~0ull, 0);
	inside        = false;
	std::fprintf(stderr, "[bc5] exp 0417 hook: before call %d, a synthetic set-buffer with the map signature on va 0x%" PRIx64 " len 0x%x returned 0x%08x; committed before no, after %s\\n",
	             c.nth, c.va, static_cast<unsigned>(AMM_PAGE_SIZE), static_cast<unsigned>(rc), Bc5SbTestCommitted(c.va) ? "YES (mapped)" : "no (nothing mapped)");
}
#endif

static int KYTY_SYSV_ABI CommandBufferSetBuffer(void* command_buffer, void* buffer, uint32_t size,
                                                uint64_t a3, uint64_t a4, uint64_t a5) {
	PRINT_NAME();
""")
    rep(b"""	const auto va = reinterpret_cast<uint64_t>(buffer);
	if (AmmTrace()) {
		AmmTraceStamp(), std::fprintf(stderr, "amm trace: set-buffer cb 0x%016" PRIx64 " va 0x%016" PRIx64 " len 0x%x a3 0x%" PRIx64 " a4 0x%" PRIx64 " a5 0x%" PRIx64 "\\n",
""", b"""	const auto va = reinterpret_cast<uint64_t>(buffer);
#if KYTY_BC5_SETBUFFER_TEST_HOOK
	Bc5SbTestApply(reinterpret_cast<uint64_t>(command_buffer), va, size, &a3, &a4); // experiment 0417
#endif
	if (AmmTrace()) {
		AmmTraceStamp(), std::fprintf(stderr, "amm trace: set-buffer cb 0x%016" PRIx64 " va 0x%016" PRIx64 " len 0x%x a3 0x%" PRIx64 " a4 0x%" PRIx64 " a5 0x%" PRIx64 "\\n",
""")
elif what == "memory":
    assert md5 == "eff24b4c626b67d65e91b99307fa84bf", md5
    rep(b"""			const char* e = std::getenv("KYTY_BC5_RANGES_FAST");
			return e != nullptr && e[0] != 0 && !(e[0] == '0' && e[1] == 0);
""", b"""			const char* e  = std::getenv("KYTY_BC5_RANGES_FAST");
			const bool  on = e != nullptr && e[0] != 0 && !(e[0] == '0' && e[1] == 0);
			std::fprintf(stderr, "[bc5] exp 0412 ranges fast: %s (tag mf412)\\n", on ? "on" : "off"); // exp 0417: said once, either way
			return on;
""")
    rep(b"""		if (e == nullptr || e[0] == 0 || (e[0] == '0' && e[1] == 0)) return 0;
		const int m = std::strcmp(e, "verify") == 0 ? 2 : std::strcmp(e, "1") == 0 ? 1 : 0;
""", b"""		if (e == nullptr || e[0] == 0 || (e[0] == '0' && e[1] == 0)) {
			std::fprintf(stderr, "[bc5] exp 0412 physmap sorted: off (tag ps412)\\n"); // exp 0417: said once, also when off
			return 0;
		}
		const int m = std::strcmp(e, "verify") == 0 ? 2 : std::strcmp(e, "1") == 0 ? 1 : 0;
""")
elif what == "agc":
    assert md5 == "a81efd2c86878357207032270eb8b291", md5
    rep(b'''	if (!told.exchange(true))
		journal("exp 0401: acb state restore (exp 0381) %s\\n", on ? "on (a graphics buffer that dispatches gets the graphics queue's tracked compute registers in front)" : "off");
''', b'''	if (!told.exchange(true)) {
		journal("exp 0401: acb state restore (exp 0381) %s\\n", on ? "on (a graphics buffer that dispatches gets the graphics queue's tracked compute registers in front)" : "off");
		std::fprintf(stderr, "[bc5] exp 0401: acb state restore (exp 0381) %s\\n", on ? "on" : "off"); // exp 0417: also in the play log (lean has no journal)
	}
''')
else:
    raise SystemExit(__doc__)
open(dst, "wb").write(s)
print("%s %s -> %s" % (what, md5[:8], hashlib.md5(s).hexdigest()[:8]))
