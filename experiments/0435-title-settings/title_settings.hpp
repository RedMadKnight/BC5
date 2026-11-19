// SPDX-License-Identifier: GPL-2.0-only
// BC5 experiment 0435: each game keeps its own settings and its last window mode (the maintainer, 2026-11-19: "zrób aby
// każda gra zapamiętywała swoje Settings oraz czy był fullscreen czy nie").
//
//   <titles root>/<TITLE_ID>/input.cfg   the title's input configuration: the file the settings overlay (F2) and the
//                                        Emulation menu save. Seeded on the title's first start by copying the shared
//                                        file (KYTY_BC5_INPUT_CONFIG, ~/bc5-work/input.cfg); same grammar, old keys too.
//   <titles root>/<TITLE_ID>/window      "fullscreen" or "windowed": the mode the window last changed to (F11, the menu,
//                                        the Video tab). It wins over --fullscreen, which is only the first-run default.
//
// The titles root is $KYTY_BC5_MENU_DIR/titles (play-any.sh exports ~/bc5-work/menu), else <directory of the shared
// file>/menu/titles: both give ~/bc5-work/menu/titles on the box. No title id (the empty menu window, "UNKNOWN") or
// KYTY_BC5_TITLE_SETTINGS=0: the shared file as before (read and saved), no window file. A real title whose store cannot
// be made reads the shared file and saves nothing (top's condition, 2026-11-19: a title's Save never rewrites the shared
// file).
// Pure C++ (no host types): tested by experiments/0435-title-settings/test0435.cpp.
#pragma once

#include <cstdio>
#include <filesystem>
#include <fstream>
#include <string>
#include <system_error>

namespace bc5::title_settings {

namespace fs = std::filesystem;

// A TITLE_ID as param.sfo spells it (PPSA03671): letters and digits only, so it is a safe directory name.
inline bool ValidTitleId(const std::string& id) {
	if (id.empty() || id.size() > 15 || id == "UNKNOWN") return false;
	for (const char c: id) {
		if (!((c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z') || (c >= '0' && c <= '9'))) return false;
	}
	return true;
}

inline fs::path TitlesRoot(const char* menu_dir, const std::string& shared_cfg) {
	if (menu_dir != nullptr && *menu_dir != 0) return fs::path(menu_dir) / "titles";
	if (shared_cfg.empty()) return {};
	return fs::path(shared_cfg).parent_path() / "menu" / "titles";
}

struct Resolved {
	std::string config;    // the input configuration to read
	std::string save;      // the file Save writes ("" : Save is off)
	std::string title_dir; // the title's directory (window file), "" when the title has no store
	std::string note;      // one line for the log
};

// The title's files, the store created and its input.cfg seeded from the shared file when missing. Never throws; on
// any problem the shared file to read, no title directory, and no Save for a real title.
inline Resolved Resolve(const fs::path& root, const std::string& title_id, const std::string& shared_cfg) {
	Resolved r {shared_cfg, shared_cfg, "", ""};
	if (shared_cfg.empty()) {
		r.note = "no shared input configuration: no title store";
		return r;
	}
	if (!ValidTitleId(title_id) || root.empty()) {
		r.note = "no title id: the shared file";
		return r;
	}
	r.save = ""; // from here on a failure reads the shared file and saves nothing
	std::error_code ec;
	const fs::path  dir = root / title_id;
	const fs::path  cfg = dir / "input.cfg";
	fs::create_directories(dir, ec);
	if (ec || !fs::is_directory(dir, ec)) {
		r.note = "cannot create " + dir.string() + ": the shared file";
		return r;
	}
	if (!fs::exists(cfg, ec)) {
		if (!fs::is_regular_file(shared_cfg, ec)) {
			// Nothing to seed from: keep the old path, so a missing shared file fails as it always did.
			r.note = "no " + shared_cfg + " to seed " + cfg.string() + " from: the shared file";
			return r;
		}
		const fs::path tmp = dir / "input.cfg.seed.tmp";
		fs::remove(tmp, ec);
		ec.clear();
		fs::copy_file(shared_cfg, tmp, fs::copy_options::overwrite_existing, ec);
		if (!ec) fs::rename(tmp, cfg, ec);
		if (ec) {
			fs::remove(tmp, ec);
			r.note = "cannot seed " + cfg.string() + ": the shared file";
			return r;
		}
		r.note = "seeded " + cfg.string() + " from " + shared_cfg;
	} else {
		r.note = "title file " + cfg.string();
	}
	r.config    = cfg.string();
	r.save      = r.config;
	r.title_dir = dir.string();
	return r;
}

// -1: none (or unreadable or not one of the two words), 0: windowed, 1: fullscreen.
inline int ReadWindowMode(const std::string& title_dir) {
	if (title_dir.empty()) return -1;
	std::ifstream f(fs::path(title_dir) / "window");
	std::string   word;
	if (!(f >> word)) return -1;
	if (word == "fullscreen") return 1;
	if (word == "windowed") return 0;
	return -1;
}

inline bool WriteWindowMode(const std::string& title_dir, bool fullscreen) {
	if (title_dir.empty()) return false;
	if (ReadWindowMode(title_dir) == (fullscreen ? 1 : 0)) return true; // unchanged: no write
	const fs::path tmp = fs::path(title_dir) / "window.tmp";
	{
		std::ofstream f(tmp, std::ios::trunc | std::ios::binary);
		if (!f) return false;
		f << (fullscreen ? "fullscreen" : "windowed") << '\n';
		if (!f.flush()) return false;
	}
	std::error_code ec;
	fs::rename(tmp, fs::path(title_dir) / "window", ec);
	if (ec) {
		fs::remove(tmp, ec);
		return false;
	}
	return true;
}

} // namespace bc5::title_settings
