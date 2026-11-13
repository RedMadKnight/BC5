#!/usr/bin/env python3
"""BC5 experiment 0417: CPU tests of the edited set-buffer code (mk0417.py ampr), with exp 0416's stand-ins.
It writes two test sources from the edited src/libs/libAmpr.cpp:
  <out>-plain.cpp  exp 0416's test (mktest0416sb.py, run as it is) with the hook compiled OUT, as in a shared build:
                   the same four runs must pass; only the text of exp 0416's line changed (the needle follows it).
  <out>-hook.cpp   the same real functions with the hook compiled IN (KYTY_BC5_SETBUFFER_TEST_HOOK 1). The stand-in
                   for ExecuteAmmMapCommand also marks the range committed, so the hook's "after" query can see a map.
                   One process per configuration; the test reads the same environment to know what to expect:
                     hook unset            three ordinary calls: no hook line, nothing forced
                     mapped:2              the second call gets a4 = -1: with the guard on, exp 0413's line and an
                                           attach; with GUARD=0 and MAP=1 it is mapped (the old bug, on purpose)
                     unmapped              before the first call one synthetic call on the test va: map opt-in off ->
                                           exp 0416's line, nothing mapped, "after no"; MAP=1 -> one map of the test
                                           page, "after YES"; the title's own calls attach as always
                     unmapped + TEST_VA on a committed page   "is committed, nothing done", no synthetic call
usage: mktest0417sb.py <mktest0416sb.py> <edited libAmpr.cpp> <out prefix>"""
import sys

old_gen, unit, out = sys.argv[1:4]
src = open(old_gen, encoding="utf-8").read()
OLD_NEEDLE = '"exp 0416: set-buffer with the map signature on a target that is not mapped"'
NEW_NEEDLE = '"exp 0416: set-buffer with the map signature that the guard did not take"'
assert src.count(OLD_NEEDLE) == 1
src = src.replace(OLD_NEEDLE, NEW_NEEDLE)
ns = {"__name__": "gen0416"}
argv = sys.argv
sys.argv = [old_gen, unit, out + "-plain.cpp"]
exec(compile(src, old_gen, "exec"), ns)
sys.argv = argv
s, PRE, body = ns["s"], ns["PRE"], ns["body"]
assert "Bc5SbTestApply(reinterpret_cast<uint64_t>(command_buffer), va, size, &a3, &a4);" in body

a = s.index("struct Bc5SbTest {")
hook = s[a:s.index("\n#endif\n", a) + 1]
assert "static void Bc5SbTestApply(" in hook and "CommandBufferSetBuffer(header," in hook
SIG = "static int KYTY_SYSV_ABI CommandBufferSetBuffer(void* command_buffer, void* buffer, uint32_t size,"
assert body.count(SIG) == 1
body = body.replace(SIG, hook + "\n" + SIG)
STANDIN = "static int  ExecuteAmmMapCommand(const CommandBufferState::AmmMapCommand& command) { g_maps.push_back(command); return OK; }"
assert PRE.count(STANDIN) == 1
PRE = PRE.replace(STANDIN, "static int  ExecuteAmmMapCommand(const CommandBufferState::AmmMapCommand& command) {\n"
                  "\tg_maps.push_back(command);\n\tLibKernel::Memory::g_ranges.push_back({command.va, command.va + command.size, true}); // the map is visible to the query\n\treturn OK;\n}")
PRE = PRE.replace("#include <cinttypes>", "#define KYTY_BC5_SETBUFFER_TEST_HOOK 1\n#include <atomic>\n#include <cinttypes>", 1)

POST = r'''
static int g_fail = 0;
#define CHECK(c, ...) do { if (!(c)) { g_fail++; std::printf("FAIL line %d: ", __LINE__); std::printf(__VA_ARGS__); std::printf("\n"); } } while (0)
static bool env_on(const char* name, bool unset) {
	const char* e = std::getenv(name);
	return e == nullptr ? unset : (e[0] != '\0' && std::strcmp(e, "0") != 0);
}
static int count(const std::string& hay, const char* needle) {
	int n = 0;
	for (size_t p = hay.find(needle); p != std::string::npos; p = hay.find(needle, p + 1)) n++;
	return n;
}

int main(int argc, char** argv) {
	const bool  guard = env_on("KYTY_BC5_AMM_SETBUFFER_GUARD", true);
	const bool  map   = env_on("KYTY_BC5_AMM_SETBUFFER_MAP", false);
	const char* h     = std::getenv("KYTY_BC5_AMM_SETBUFFER_TEST");
	const std::string hook = h != nullptr ? h : "";
	const char* tv    = std::getenv("KYTY_BC5_AMM_SETBUFFER_TEST_VA");
	const uint64_t test_va = tv != nullptr ? std::strtoull(tv, nullptr, 16) : 0x8ff0000000ull;
	const char* errfile = argc > 1 ? argv[1] : "sb0417.err";
	std::printf("guard %s, map opt-in %s, hook [%s], test va 0x%" PRIx64 "\n", guard ? "on" : "off", map ? "on" : "off", hook.c_str(), test_va);
	if (std::freopen(errfile, "w", stderr) == nullptr) { std::printf("FAIL: cannot redirect stderr\n"); return 2; }
	using LibKernel::Memory::g_ranges;
	g_ranges.push_back({0x300a80000ull, 0x300a84000ull, true}); // the title's buffers live here: committed
	const bool test_va_committed = test_va >= 0x300a80000ull && test_va < 0x300a84000ull;

	// three ordinary calls of a title: three arguments meant, the rest leftovers (a3 = a pointer, a4 = a small number)
	const uint64_t va[3] = {0x300a80100ull, 0x300a80900ull, 0x300a81100ull};
	size_t maps_at[4], att_at[4];
	for (int i = 0; i < 3; i++) {
		alignas(16) unsigned char header[64] = {};
		maps_at[i] = g_maps.size(); att_at[i] = g_attached.size();
		const int r = CommandBufferSetBuffer(header, reinterpret_cast<void*>(va[i]), 0x400, 0x300a82be0ull, 0xdull, 0);
		CHECK(r == OK, "call %d returned 0x%x", i + 1, static_cast<unsigned>(r));
	}
	maps_at[3] = g_maps.size(); att_at[3] = g_attached.size();
	std::fflush(stderr);
	std::string err;
	if (FILE* f = std::fopen(errfile, "rb")) { char buf[4096]; size_t n; while ((n = std::fread(buf, 1, sizeof(buf), f)) > 0) err.append(buf, n); std::fclose(f); }
	const int l13   = count(err, "exp 0413: set-buffer with the map signature on mapped memory");
	const int l16   = count(err, "exp 0416: set-buffer with the map signature that the guard did not take");
	const int lhook = count(err, "exp 0417 hook:");
	std::printf("lines: exp 0413 %d, exp 0416 %d, hook %d; maps %zu, attached %zu\n", l13, l16, lhook, g_maps.size(), g_attached.size());

	if (hook.empty()) {
		CHECK(lhook == 0 && l13 == 0 && l16 == 0, "hook unset: no line at all");
		CHECK(g_maps.empty() && g_attached.size() == 3, "hook unset: three attaches, no map");
	} else if (hook == "mapped:2") {
		const bool bug = !guard && map; // the map flavour on the title's own buffer: exp 0413's crash, reachable on purpose
		CHECK(lhook == 2 && count(err, "KYTY_BC5_AMM_SETBUFFER_TEST mapped on set-buffer call 2") == 1 && count(err, "hook: call 2 (") == 1 && count(err, "a4 forced to -1; the target is committed") == 1,
		      "mapped:2: the announcement and one forced call");
		CHECK(l13 == (guard ? 1 : 0), "mapped:2: exp 0413 lines %d", l13);
		CHECK(l16 == (!guard && !map ? 1 : 0), "mapped:2: exp 0416 lines %d", l16);
		CHECK(maps_at[1] == 0 && att_at[1] == 1, "mapped:2: the first call is untouched");
		if (bug) CHECK(maps_at[2] == 1 && att_at[2] == 1 && g_maps[0].va == 0x300a80000ull, "mapped:2 without guard, with the opt-in: the second call maps");
		else CHECK(maps_at[2] == 0 && att_at[2] == 2 && g_attached[1] == va[1], "mapped:2: the second call attaches its buffer, nothing mapped");
		CHECK(maps_at[3] == maps_at[2] && att_at[3] == att_at[2] + 1, "mapped:2: the third call is untouched");
	} else if (hook == "unmapped") {
		CHECK(count(err, "KYTY_BC5_AMM_SETBUFFER_TEST unmapped on set-buffer call 1") == 1, "unmapped: the announcement");
		if (test_va_committed) {
			CHECK(lhook == 2 && count(err, "is committed, nothing done") == 1 && g_maps.empty() && g_attached.size() == 3 && l16 == 0, "unmapped on a committed test va: nothing done");
		} else if (map) {
			CHECK(lhook == 2 && count(err, "returned 0x00000000; committed before no, after YES (mapped)") == 1, "unmapped with the opt-in: the result line");
			CHECK(g_maps.size() == 1 && g_maps[0].va == test_va && g_maps[0].size == 0x4000 && g_maps[0].prot == 0x33 && l16 == 0, "unmapped with the opt-in: one map of the test page");
			CHECK(g_attached.size() == 3 && maps_at[1] == 1, "unmapped with the opt-in: the synthetic call came before the first call; the title's three calls attach");
		} else {
			CHECK(lhook == 2 && count(err, "committed before no, after no (nothing mapped)") == 1, "unmapped without the opt-in: the result line");
			CHECK(g_maps.empty() && l16 == 1, "unmapped without the opt-in: nothing mapped, exp 0416's line once (%d)", l16);
			CHECK(g_attached.size() == 4 && g_attached[0] == test_va, "unmapped without the opt-in: the synthetic call took the buffer flavour on the scratch header, then the title's three");
		}
		CHECK(l13 == 0, "unmapped: no guard refusal (%d)", l13);
	} else {
		CHECK(false, "unknown hook configuration for this test");
	}
	std::printf("%s: %d failed checks\n", g_fail == 0 ? "PASS" : "FAIL", g_fail);
	return g_fail == 0 ? 0 : 1;
}
'''
open(out + "-hook.cpp", "w", encoding="utf-8", newline="\n").write(PRE + "\n" + body + POST)
print("ok")
