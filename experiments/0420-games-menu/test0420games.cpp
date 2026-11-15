// BC5 experiment 0420: CPU test of games_list.hpp (the menu's installed games). Synthetic folders only.
// build: clang++ -std=c++20 -Wall -Wextra -Werror -I. test0420games.cpp -o t && ./t
#include "games_list.hpp"

#include <cstdio>
#include <fstream>

namespace fs = std::filesystem;
using namespace bc5::games;

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

// what bc5-mount's write_install_json writes (its layout, two spaces before each top-level key)
static std::string record(const std::string& image_escaped, uint64_t bytes) {
	return "{\n  \"image\": \"" + image_escaped + "\",\n  \"image_size\": 10,\n  \"file_count\": 2,\n  \"total_bytes\": " +
	       std::to_string(bytes) + ",\n  \"sha256\": {\n    \"a.bin\": \"00\"\n  },\n  \"date\": \"1\"\n}\n";
}

int main() {
	// the parsers
	std::string img;
	uint64_t    bytes = 0;
	CHECK(parse_record(record("/a/b.pkg", 196702588158ull), &img, &bytes) && img == "/a/b.pkg" && bytes == 196702588158ull);
	CHECK(parse_record(record("/a/we \\\"q\\\" \\\\ c.pkg", 5), &img, &bytes) && img == "/a/we \"q\" \\ c.pkg");
	CHECK(!parse_record("", &img, &bytes));
	CHECK(!parse_record("{}", &img, &bytes));
	CHECK(!parse_record("{\n  \"image\": \"\",\n  \"file_count\": 1,\n  \"total_bytes\": 1\n}", &img, &bytes));
	CHECK(!parse_record("{\n  \"image\": \"/x\",\n  \"file_count\": 1\n}", &img, &bytes));
	CHECK(!parse_record("{\n  \"file_count\": 1,\n  \"total_bytes\": 1,\n  \"sha256\": {\n    \"image\": \"/fake\"\n  }\n}\n", &img, &bytes));
	CHECK(json_field("{\"a\": {\"titleId\" : \"PPSA03671\", \"titleName\": \"Some \\u00e9 Game\"}}", "titleId") == "PPSA03671");
	CHECK(json_field("{\"titleName\": \"Some \\u00e9 Game\"}", "titleName") == "Some \xc3\xa9 Game");
	CHECK(json_field("{\"titleId\": 5, \"x\": {\"titleId\": \"AB\"}}", "titleId") == "AB");
	CHECK(json_field("{}", "titleId").empty());
	CHECK(json_field_ascii("{\"pl-PL\": {\"titleName\": \"Gra \\u00e9\"}, \"en-US\": {\"titleName\": \"The Game\"}}", "titleName") == "The Game");
	CHECK(json_field_ascii("{\"titleName\": \"\\u00e9\"}", "titleName").empty());
	CHECK(human_size(196702588158ull) == "196.7 GB" && human_size(52000000) == "52.0 MB" && human_size(10) == "10 bytes");

	// a synthetic games root
	const fs::path root = fs::temp_directory_path() / ("bc5-test0420-" + std::to_string(std::rand()));
	fs::remove_all(root);
	put(root / "src.ffpfsc", "img");
	put(root / "PPSA00001" / ".bc5-install.json", record((root / "src.ffpfsc").generic_string(), 11));
	put(root / "PPSA00001" / "sce_sys" / "param.json", "{\"localizedParameters\": {\"en-US\": {\"titleName\": \"Zeta\"}}, \"titleId\": \"PPSA00001\"}");
	put(root / "PPSA00002" / ".bc5-install.json", record("/nowhere/game.pkg", 22));                 // no param.json
	put(root / "noinstall" / "a.bin", "x");                                                         // no record
	put(root / "broken" / ".bc5-install.json", "{\n  \"image\": 5\n}\n");                            // a broken record
	put(root / "PPSA21567 - ASTRO BOT.ffpfsc", "an image file, not a folder");
	put(root / "PPSA00003" / ".bc5-install.json", record("/x.pkg", 33));
	put(root / "PPSA00003" / "sce_sys" / "param.json", "{\"titleId\": \"PPSA00003\", \"titleName\": \"Alpha\"}");
	put(root / "deep" / "PPSA00004" / ".bc5-install.json", record("/x.pkg", 44));                  // one level too deep
	const auto list = scan(root);
	CHECK(list.size() == 3);
	if (list.size() == 3) {
		CHECK(list[0].name == "Alpha" && list[0].title_id == "PPSA00003" && list[0].bytes == 33 && !list[0].image_present);
		CHECK(list[1].name == "PPSA00002" && list[1].title_id == "PPSA00002" && list[1].image == "/nowhere/game.pkg");
		CHECK(list[2].name == "Zeta" && list[2].bytes == 11 && list[2].image_present);
	}
	CHECK(scan(root / "absent").empty());
	CHECK(default_root("/home/u") == fs::path("/home/u") / "bc5-data" / "games");
	fs::remove_all(root);
	std::printf(g_bad == 0 ? "test0420games: all ok\n" : "test0420games: %d FAILED\n", g_bad);
	return g_bad == 0 ? 0 : 1;
}
