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
static int test_unsetenv(const char* n) {
	g_env.erase(n);
	return 0;
}
#define setenv test_setenv
#define unsetenv test_unsetenv
#define getenv bc5_test_getenv
#include "switch_defaults.hpp"
#undef getenv
#undef unsetenv
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
		for (const Default* d = kSoft; d->name != nullptr; d++) std::printf("* %s %s\n", d->name, d->value);
		for (const char* const* n = kIgnored; *n != nullptr; n++) std::printf("- %s (ignored)\n", *n);
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
	expect("42 rows (45 before exp 0418 took its three start-state words out)", rows == 42);
	expect("40 taken", took == 40);
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
	for (const Default* d = kSoft; d->name != nullptr; d++) {
		chain = chain || (std::strcmp(d->name, "BC5_DIRECT_CHAIN") == 0 && std::strcmp(d->value, "2") == 0);
		mode  = mode || (std::strcmp(d->name, "BC5_GC_MODE") == 0 && std::strcmp(d->value, "direct") == 0);
		for (const TitleDefault* t = kTitleDefaults; t->name != nullptr; t++) both = both || std::strcmp(d->name, t->name) == 0;
	}
	expect("CHAIN=2 and GC_MODE=direct are general, with their option", chain && mode && !both);
	// Apply: the fixes and the long-standing defaults are forced, the ignored words are removed, the soft ones yield
	g_env.clear();
	g_env["KYTY_BC5_SWITCH_DEFAULTS"]  = "0";      // gone: ignored
	g_env["KYTY_BC5_APR_POSIX"]        = "0";      // a fix: forced back
	g_env["KYTY_BC5_FS_FIXES"]         = "0";      // a long-standing default: forced back
	g_env["BC5_FAULT_RECORD"]          = "0";      // ignored: the read site sees "unset" (on)
	g_env["KYTY_BC5_NP_SESSION_V2"]    = "0";
	g_env["BC5_DIRECT_CHAIN"]          = "0";      // soft: the environment wins
	g_env["BC5_DIRECT_JOURNAL_QUIET"]  = "0";      // soft
	g_env["KYTY_BC5_SOMETHING_ELSE"]   = "kept";   // not ours
	Apply(); // no /proc/self/cmdline here, or no --game: no title rows
	expect("the fix is forced", g_env["KYTY_BC5_APR_POSIX"] == "direct");
	expect("the default is forced", g_env["KYTY_BC5_FS_FIXES"] == "1" && g_env["KYTY_BC5_AUDIO_FIXES"] == "set,room");
	expect("the ignored words are gone", g_env.count("BC5_FAULT_RECORD") == 0 && g_env.count("KYTY_BC5_NP_SESSION_V2") == 0 &&
	                                         g_env.count("KYTY_BC5_SWITCH_DEFAULTS") == 0);
	expect("the soft defaults yield", g_env["BC5_DIRECT_CHAIN"] == "0" && g_env["BC5_DIRECT_JOURNAL_QUIET"] == "0" && g_env["BC5_GC_MODE"] == "direct");
	expect("other words are untouched", g_env["KYTY_BC5_SOMETHING_ELSE"] == "kept");
	expect("no title rows without a game", g_env.count("BC5_DIRECT_GPU_CHECK") == 0);
	// no word is in two of the general tables or both forced and ignored
	std::map<string, int> gen;
	for (const Default* d = kFixes; d->name != nullptr; d++) gen[d->name]++;
	for (const Default* d = kDefaults; d->name != nullptr; d++) gen[d->name]++;
	for (const Default* d = kSoft; d->name != nullptr; d++) gen[d->name]++;
	for (const char* const* n = kIgnored; *n != nullptr; n++) gen[*n]++;
	bool dup = false;
	for (const auto& [k, n]: gen) dup = dup || n != 1;
	expect("no general word twice", !dup);
	std::printf("test0419defs: %s\n", g_fail == 0 ? "all ok" : "FAILED");
	return g_fail == 0 ? 0 : 1;
}
