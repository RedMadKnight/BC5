// ---- experiment 0419: the defaults of ONE title, by its title id ------------------------------------------------------
// Until 2026-11-13 these words lived in the second title's launcher (play-pkg.sh 47426d8e): a new launcher or a desktop
// shortcut that forgot one silently lost a fix. They are applied like the tables above (setenv(name, value, 0): a value
// in the environment wins, NAME=0 turns one off), after the title id is read from the game directory on the command
// line, which is all this needs before any static initializer runs. KYTY_BC5_TITLE_DEFAULTS=0 skips the table, and so
// does KYTY_BC5_SWITCH_DEFAULTS=0.
// Why per title and not general: for 14 of the direct-path words no ASTRO BOT run is on record, and four or more of the
// twenty library words together end ASTRO BOT at 5-6 s (exp 0413). A word moves up to kDefaults when it has a run on
// both titles. The heap-name lists, the RT program list and every path stay in the launcher (title data and paths).
struct TitleDefault {
	const char* title;
	const char* name;
	const char* value;
};

#define BC5_T2 "PPSA03671"
inline constexpr TitleDefault kTitleDefaults[] = {
    // the direct path (launcher lines 54-56, 75-148)
    {BC5_T2, "BC5_DIRECT_CP_COHER_START_DELAY", "1"}, // on in every play since 11-03; never A/B'd
    {BC5_T2, "BC5_DIRECT_LAZY_RELEASE", "30,eager"},  // orphan release (exp 0412)
    {BC5_T2, "BC5_GUARD_SPLIT", "1"},
    {BC5_T2, "BC5_GUARD_FORGET", "10"},
    {BC5_T2, "BC5_GUARD_LEARN_LOG", "2"},
    {BC5_T2, "BC5_DIRECT_MEC_INDIRECT", "1"},      // F91
    {BC5_T2, "BC5_DIRECT_GPU_CHECK", "1"},         // F106
    {BC5_T2, "BC5_DIRECT_DMA_SYNC", "1"},          // F107
    {BC5_T2, "BC5_DIRECT_REMEMBER_UNMAPPED", "1"}, // F163
    {BC5_T2, "KYTY_BC5_APR_PARALLEL", "8"},        // F166
    {BC5_T2, "BC5_DIRECT_DMA_SNAPSHOT", "4096"},   // F172
    {BC5_T2, "BC5_DIRECT_GC_TF_RING", "1"},        // F248
    {BC5_T2, "BC5_DIRECT_GC_HS_OFFCHIP", "1"},     // F786
    {BC5_T2, "BC5_DIRECT_FLAT_APERTURE", "1"},     // F249
    {BC5_T2, "BC5_DIRECT_AMM_PRT", "1"},           // F260
    {BC5_T2, "BC5_DIRECT_SKIP_PGM", "0"},          // as the launcher had it
    {BC5_T2, "BC5_DIRECT_CS_PREFIX", "1"},         // F321
    {BC5_T2, "BC5_DIRECT_INDIRECT_DRAWS", "multi"},
    {BC5_T2, "BC5_DIRECT_ALIASES", "1"},
    {BC5_T2, "BC5_DIRECT_CROSS_RING_WAITS", "all"},  // F412, F415
    {BC5_T2, "BC5_DIRECT_GPU_CHECK_PRODUCT", "1"},   // F414, F415
    {BC5_T2, "BC5_DIRECT_SHADOW_LABELS", "1"},       // F414, F415
    {BC5_T2, "BC5_DIRECT_HOST_INDIRECT", "learn:1100000000"}, // F432
    {BC5_T2, "BC5_DIRECT_RING_DEPS", "dcb"},         // F385
    {BC5_T2, "BC5_DIRECT_TWO_RING_WAIT_MS", "4"},
    // the twenty library words of audit rows A15, A16, A17, A21, A22 (launcher lines 59-67)
    {BC5_T2, "KYTY_BC5_SAVEDATA_MEMORY_FIXES", "1"},
    {BC5_T2, "KYTY_BC5_SAVEDATA_DELETE_BUSY", "1"},
    {BC5_T2, "KYTY_BC5_SAVEDATA_ALIASES", "1"},
    {BC5_T2, "KYTY_BC5_HTTP2_FIXES", "1"},
    {BC5_T2, "KYTY_BC5_PAD_OPEN_EXT", "1"},
    {BC5_T2, "KYTY_BC5_JSON2_FIXES", "1"},
    {BC5_T2, "KYTY_BC5_ULT_FIXES", "1"},
    {BC5_T2, "KYTY_BC5_USERSERVICE_VALUES", "1"},
    {BC5_T2, "KYTY_BC5_SYSTEMSERVICE_VALUES", "1"},
    {BC5_T2, "KYTY_BC5_SYSTEMSERVICE_PARAMS_7_1000", "1"},
    {BC5_T2, "KYTY_BC5_AUDIOOUT_CHECKS", "1"},
    {BC5_T2, "KYTY_BC5_AUDIOIN_CHECKS", "1"},
    {BC5_T2, "KYTY_BC5_NGS2_RACK_FIX", "1"},
    {BC5_T2, "KYTY_BC5_FW_PAD", "1"},
    {BC5_T2, "KYTY_BC5_LOAD_ZLIB", "1"},
    {BC5_T2, "KYTY_BC5_LOAD_JPEG", "1"},
    {BC5_T2, "KYTY_BC5_LOAD_IME", "1"},
    {BC5_T2, "KYTY_BC5_LOAD_NPCOMMON", "1"},
    {BC5_T2, "KYTY_BC5_LOAD_NPMANAGER", "1"},
    {BC5_T2, "KYTY_BC5_LOAD_NPTROPHY", "1"},
    {nullptr, nullptr, nullptr}};
#undef BC5_T2

// The game path of a command line: the argument after "--game" (NUL-separated, as /proc/self/cmdline). Empty: none.
inline std::string GamePathOf(const std::string& cmdline) {
	size_t i = 0;
	bool   next = false;
	while (i < cmdline.size()) {
		const size_t      e = cmdline.find('\0', i);
		const std::string a = cmdline.substr(i, e == std::string::npos ? std::string::npos : e - i);
		if (next) return a;
		next = (a == "--game");
		if (e == std::string::npos) break;
		i = e + 1;
	}
	return {};
}

// The value of "titleId" in a param.json text: the first quoted string after the key and a colon. Empty: none.
inline std::string TitleIdOf(const std::string& json) {
	const size_t k = json.find("\"titleId\"");
	if (k == std::string::npos) return {};
	const size_t c = json.find(':', k + 9);
	if (c == std::string::npos) return {};
	const size_t a = json.find('"', c + 1);
	if (a == std::string::npos) return {};
	const size_t b = json.find('"', a + 1);
	if (b == std::string::npos || b - a - 1 > 16) return {};
	for (size_t i = c + 1; i < a; i++) {
		if (json[i] != ' ' && json[i] != '\t' && json[i] != '\r' && json[i] != '\n') return {};
	}
	return json.substr(a + 1, b - a - 1);
}

inline std::string ReadSmallFile(const std::string& path) {
	std::string out;
	if (std::FILE* f = std::fopen(path.c_str(), "rb")) {
		char   buf[4096];
		size_t n = 0;
		while (out.size() < (1u << 20) && (n = std::fread(buf, 1, sizeof(buf), f)) > 0) out.append(buf, n);
		std::fclose(f);
	}
	return out;
}

// The title id of this process: --game names the game directory, or a file in it (main.cpp's two forms).
inline std::string DetectTitle() {
	std::string game = GamePathOf(ReadSmallFile("/proc/self/cmdline"));
	if (game.empty()) return {};
	std::string id = TitleIdOf(ReadSmallFile(game + "/sce_sys/param.json"));
	if (id.empty()) {
		const size_t s = game.find_last_of('/');
		if (s != std::string::npos) id = TitleIdOf(ReadSmallFile(game.substr(0, s) + "/sce_sys/param.json"));
	}
	return id;
}

// Applies the rows of `title`; returns how many rows the title has and, in *took, how many were not set before.
inline int ApplyTitle(const std::string& title, int* took) {
	int rows = 0;
	*took    = 0;
	for (const TitleDefault* d = kTitleDefaults; d->name != nullptr; d++) {
		if (title != d->title) continue;
		rows++;
		if (std::getenv(d->name) == nullptr) (*took)++;
		setenv(d->name, d->value, 0);
	}
	return rows;
}
