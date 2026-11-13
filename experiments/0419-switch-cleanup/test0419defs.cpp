// BC5 exp 0419: an own test of the new src/bc5/switch_defaults.hpp (the header as mkdefs0419.py leaves it).
// Windows has no setenv; the stand-in keeps a map and getenv reads it first (test only).
//   usage: test0419defs            the checks
//          test0419defs table     prints "title name value" per row, and the general tables as "* name value"
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <map>
#include <string>

static std::map<std::string, std::string> g_env;
static int test_setenv(const char* n, const char* v, int overwrite) {
	if (!overwrite && g_env.count(n) != 0) return 0;
	g_env[n] = v;
	return 0;
}
static const char* test_getenv(const char* n) {
	const auto it = g_env.find(n);
	return it == g_env.end() ? nullptr : it->second.c_str();
}
namespace std {
static const char* bc5_test_getenv(const char* n) {
	return test_getenv(n);
}
} // namespace std
#define setenv test_setenv
#define getenv bc5_test_getenv
#include "switch_defaults.hpp"
#undef getenv
#undef setenv

static int g_fail = 0;
static void expect(const char* what, bool ok) {
	if (!ok) {
		g_fail++;
		std::printf("FAIL %s\n", what);
	}
}

int main(int argc, char** argv) {
	using namespace bc5::switch_defaults;
	if (argc > 1 && std::strcmp(argv[1], "table") == 0) {
		for (const Default* d = kFixes; d->name != nullptr; d++) std::printf("* %s %s\n", d->name, d->value);
		for (const Default* d = kDefaults; d->name != nullptr; d++) std::printf("* %s %s\n", d->name, d->value);
		for (const TitleDefault* d = kTitleDefaults; d->name != nullptr; d++) std::printf("%s %s %s\n", d->title, d->name, d->value);
		return 0;
	}
	using std::string;
	expect("game dir", GamePathOf(string("emu\0--game\0/a/b\0--x\0y\0", 22)) == "/a/b");
	expect("game last, no NUL", GamePathOf(string("emu\0--game\0/a/b", 15)) == "/a/b");
	expect("no game", GamePathOf(string("emu\0--menu\0", 11)).empty());
	expect("game without a value", GamePathOf(string("emu\0--game\0", 11)).empty());
	expect("title", TitleIdOf("{\n  \"x\": 1,\n  \"titleId\": \"PPSA03671\",\n  \"y\": 2\n}") == "PPSA03671");
	expect("title, no spaces", TitleIdOf("{\"titleId\":\"ABCD12345\"}") == "ABCD12345");
	expect("no title", TitleIdOf("{\"contentId\": \"x\"}").empty());
	expect("title not a string", TitleIdOf("{\"titleId\": 5, \"a\": \"b\"}").empty());
	expect("title too long", TitleIdOf("{\"titleId\": \"01234567890123456789\"}").empty());
	expect("empty text", TitleIdOf("").empty());

	int took = 0;
	expect("an unknown title has no rows", ApplyTitle("PPSA21564", &took) == 0 && took == 0);
	expect("nothing was set for it", g_env.empty());
	g_env["BC5_DIRECT_GPU_CHECK"] = "0";  // the environment wins
	g_env["KYTY_BC5_LOAD_ZLIB"]   = "";   // an empty value counts as set, as in the launcher
	const int rows = ApplyTitle("PPSA03671", &took);
	expect("45 rows", rows == 45);
	expect("43 taken", took == 43);
	expect("the environment's 0 stays", g_env["BC5_DIRECT_GPU_CHECK"] == "0");
	expect("the empty value stays", g_env["KYTY_BC5_LOAD_ZLIB"].empty());
	expect("a row is set", g_env["BC5_DIRECT_HOST_INDIRECT"] == "learn:1100000000" && g_env["BC5_DIRECT_RING_DEPS"] == "dcb");
	// no name twice in one title, none of a title's names in the general tables
	std::map<string, int> seen;
	for (const TitleDefault* d = kTitleDefaults; d->name != nullptr; d++) seen[string(d->title) + " " + d->name]++;
	bool twice = false;
	for (const auto& [k, n]: seen) twice = twice || n != 1;
	expect("no row twice", !twice);
	bool both = false;
	for (const TitleDefault* t = kTitleDefaults; t->name != nullptr; t++) {
		for (const Default* d = kFixes; d->name != nullptr; d++) both = both || std::strcmp(d->name, t->name) == 0;
		for (const Default* d = kDefaults; d->name != nullptr; d++) both = both || std::strcmp(d->name, t->name) == 0;
	}
	expect("no title word in the general tables", !both);
	bool chain = false, mode = false;
	for (const Default* d = kDefaults; d->name != nullptr; d++) {
		chain = chain || (std::strcmp(d->name, "BC5_DIRECT_CHAIN") == 0 && std::strcmp(d->value, "2") == 0);
		mode  = mode || (std::strcmp(d->name, "BC5_GC_MODE") == 0 && std::strcmp(d->value, "direct") == 0);
	}
	expect("CHAIN=2 and GC_MODE=direct are general", chain && mode);
	// Apply: KYTY_BC5_SWITCH_DEFAULTS=0 keeps the fixes and skips the rest
	g_env.clear();
	g_env["KYTY_BC5_SWITCH_DEFAULTS"] = "0";
	Apply();
	expect("fixes with the table off", g_env.count("KYTY_BC5_APR_POSIX") == 1 && g_env.count("BC5_DIRECT_CHAIN") == 0);
	g_env.clear();
	Apply(); // no /proc/self/cmdline here, or no --game: no title rows
	expect("defaults", g_env["BC5_DIRECT_CHAIN"] == "2" && g_env.count("BC5_DIRECT_GPU_CHECK") == 0);
	std::printf("test0419defs: %s\n", g_fail == 0 ? "all ok" : "FAILED");
	return g_fail == 0 ? 0 : 1;
}
