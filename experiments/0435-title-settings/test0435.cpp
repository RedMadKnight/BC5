// BC5 experiment 0435: CPU test of title_settings.hpp (per-title input.cfg and window mode). Synthetic files only.
// build: clang++ -std=c++20 -Wall -Wextra -Werror -I. test0435.cpp -o t && ./t
#include "title_settings.hpp"

#include <cstdio>
#include <fstream>
#include <sstream>

namespace fs = std::filesystem;
using namespace bc5::title_settings;

static int g_bad = 0;
#define CHECK(c)                                                                                                       \
	do {                                                                                                               \
		if (!(c)) {                                                                                                    \
			std::printf("FAIL line %d: %s\n", __LINE__, #c);                                                           \
			g_bad++;                                                                                                   \
		}                                                                                                              \
	} while (0)

static void put(const fs::path& p, const std::string& text) {
	fs::create_directories(p.parent_path());
	std::ofstream(p, std::ios::binary) << text;
}

static std::string get(const fs::path& p) {
	std::ifstream      f(p, std::ios::binary);
	std::ostringstream s;
	s << f.rdbuf();
	return s.str();
}

int main() {
	const fs::path base = fs::temp_directory_path() / "bc5-test0435";
	fs::remove_all(base);
	const fs::path shared = base / "bc5-work" / "input.cfg";
	const std::string shared_text = "# shared\nFullscreen=off\nRenderScale.PPSA21567=1.70\nCross=Space2\n";
	put(shared, shared_text);

	// ids
	CHECK(ValidTitleId("PPSA03671"));
	CHECK(!ValidTitleId(""));
	CHECK(!ValidTitleId("UNKNOWN"));
	CHECK(!ValidTitleId("../etc"));
	CHECK(!ValidTitleId("PPSA0367/1"));
	CHECK(!ValidTitleId("ABCDEFGHIJKLMNOP")); // 16 characters

	// root: the menu dir wins; else <shared dir>/menu/titles; nothing without either
	CHECK(TitlesRoot("/m", shared.string()) == fs::path("/m") / "titles");
	CHECK(TitlesRoot("", shared.string()) == base / "bc5-work" / "menu" / "titles");
	CHECK(TitlesRoot(nullptr, shared.string()) == base / "bc5-work" / "menu" / "titles");
	CHECK(TitlesRoot(nullptr, "").empty());

	const fs::path root = TitlesRoot(nullptr, shared.string());

	// first start: seeded by copying the shared file byte for byte
	Resolved a = Resolve(root, "PPSA03671", shared.string());
	CHECK(a.config == (root / "PPSA03671" / "input.cfg").string());
	CHECK(a.title_dir == (root / "PPSA03671").string());
	CHECK(get(a.config) == shared_text);
	CHECK(a.note.rfind("seeded", 0) == 0);
	CHECK(!fs::exists(root / "PPSA03671" / "input.cfg.seed.tmp"));

	// the title's own file is never overwritten by a later shared change
	put(a.config, "Cross=Return\n");
	put(shared, "Cross=X\n");
	Resolved a2 = Resolve(root, "PPSA03671", shared.string());
	CHECK(a2.config == a.config);
	CHECK(get(a2.config) == "Cross=Return\n");
	CHECK(a2.note.rfind("title file", 0) == 0);

	// a second title gets its own copy of the shared file as it is now
	Resolved b = Resolve(root, "PPSA21567", shared.string());
	CHECK(get(b.config) == "Cross=X\n");
	CHECK(b.title_dir != a.title_dir);

	// no title, no shared file, a bad id: the shared path and no store
	Resolved u = Resolve(root, "UNKNOWN", shared.string());
	CHECK(u.config == shared.string() && u.title_dir.empty());
	Resolved n = Resolve(root, "PPSA03671", "");
	CHECK(n.config.empty() && n.title_dir.empty());
	Resolved t = Resolve(root, "..", shared.string());
	CHECK(t.config == shared.string() && t.title_dir.empty());

	// a missing shared file and no title file yet: the shared path (fails as before), nothing created
	const fs::path missing = base / "nowhere" / "input.cfg";
	Resolved m = Resolve(root, "PPSA99999", missing.string());
	CHECK(m.config == missing.string() && m.title_dir.empty());
	CHECK(!fs::exists(root / "PPSA99999" / "input.cfg"));

	// the root cannot be created (a file in its place): the shared path
	put(base / "blocked", "x");
	Resolved k = Resolve(base / "blocked" / "titles", "PPSA03671", shared.string());
	CHECK(k.config == shared.string() && k.title_dir.empty());

	// window mode
	CHECK(ReadWindowMode(a.title_dir) == -1);
	CHECK(ReadWindowMode("") == -1);
	CHECK(!WriteWindowMode("", true));
	CHECK(WriteWindowMode(a.title_dir, false));
	CHECK(ReadWindowMode(a.title_dir) == 0);
	CHECK(get(fs::path(a.title_dir) / "window") == "windowed\n");
	CHECK(WriteWindowMode(a.title_dir, true));
	CHECK(ReadWindowMode(a.title_dir) == 1);
	CHECK(!fs::exists(fs::path(a.title_dir) / "window.tmp"));
	const auto t1 = fs::last_write_time(fs::path(a.title_dir) / "window");
	CHECK(WriteWindowMode(a.title_dir, true)); // unchanged: no rewrite
	CHECK(fs::last_write_time(fs::path(a.title_dir) / "window") == t1);
	CHECK(ReadWindowMode(b.title_dir) == -1); // per title
	put(fs::path(b.title_dir) / "window", "maybe\n");
	CHECK(ReadWindowMode(b.title_dir) == -1);
	put(fs::path(b.title_dir) / "window", "fullscreen"); // no newline (a hand edit)
	CHECK(ReadWindowMode(b.title_dir) == 1);

	fs::remove_all(base);
	std::printf("%s (%d failed)\n", g_bad == 0 ? "PASS" : "FAIL", g_bad);
	return g_bad == 0 ? 0 : 1;
}
