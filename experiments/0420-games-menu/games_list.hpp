// SPDX-License-Identifier: GPL-2.0-only
// BC5 experiment 0420: the installed games the host's menu lists. An installed game is a directory directly under the
// games root (~/bc5-data/games) that is not a symbolic link and holds the record `bc5-mount install` or `adopt` writes,
// .bc5-install.json. The list is read from the folders each time it is asked for (never from recent.txt), so a game
// installed or removed by the launcher shows at once. Pure C++ (no host types): tested by test0420games.cpp.
#pragma once

#include <algorithm>
#include <cstdint>
#include <cstdio>
#include <filesystem>
#include <string>
#include <system_error>
#include <vector>

namespace bc5::games {

struct Installed {
	std::filesystem::path dir;           // the installed game's directory
	std::string           title_id;      // from sce_sys/param.json, else the directory's name
	std::string           name;          // the game's name from sce_sys/param.json, else the title id
	std::string           image;         // the image it was installed from (the record)
	uint64_t              bytes  = 0;    // what the install wrote (the record's total_bytes)
	bool                  image_present = false; // the image is still at its path
};

inline std::string read_small(const std::filesystem::path& p, size_t cap = 4u << 20) {
	std::string out;
	if (std::FILE* f = std::fopen(p.string().c_str(), "rb")) {
		char   buf[8192];
		size_t n = 0;
		while (out.size() < cap && (n = std::fread(buf, 1, sizeof(buf), f)) > 0) out.append(buf, n);
		std::fclose(f);
	}
	return out;
}

// A JSON string at s[i] == '"'; *end is set past its closing quote. Empty and *ok false when it is not one.
inline std::string json_string_at(const std::string& s, size_t i, size_t* end, bool* ok) {
	*ok = false;
	std::string out;
	if (i >= s.size() || s[i] != '"') return out;
	for (size_t k = i + 1; k < s.size(); k++) {
		const char c = s[k];
		if (c == '"') {
			*end = k + 1;
			*ok  = true;
			return out;
		}
		if (static_cast<unsigned char>(c) < 0x20) return {};
		if (c != '\\') {
			out.push_back(c);
			continue;
		}
		if (++k >= s.size()) return {};
		switch (s[k]) {
			case '"': out.push_back('"'); break;
			case '\\': out.push_back('\\'); break;
			case '/': out.push_back('/'); break;
			case 'n': out.push_back('\n'); break;
			case 't': out.push_back('\t'); break;
			case 'r': out.push_back('\r'); break;
			case 'b': out.push_back('\b'); break;
			case 'f': out.push_back('\f'); break;
			case 'u': {
				if (k + 4 >= s.size()) return {};
				unsigned v = 0;
				for (int j = 1; j <= 4; j++) {
					const char h = s[k + static_cast<size_t>(j)];
					v = v * 16 + static_cast<unsigned>(h >= '0' && h <= '9' ? h - '0' : (h >= 'a' && h <= 'f' ? h - 'a' + 10 : (h >= 'A' && h <= 'F' ? h - 'A' + 10 : 99)));
				}
				if (v > 0xffff) return {};
				if (v < 0x80) {
					out.push_back(static_cast<char>(v));
				} else if (v < 0x800) {
					out.push_back(static_cast<char>(0xc0 | (v >> 6)));
					out.push_back(static_cast<char>(0x80 | (v & 0x3f)));
				} else {
					out.push_back(static_cast<char>(0xe0 | (v >> 12)));
					out.push_back(static_cast<char>(0x80 | ((v >> 6) & 0x3f)));
					out.push_back(static_cast<char>(0x80 | (v & 0x3f)));
				}
				k += 4;
				break;
			}
			default: return {};
		}
	}
	return {};
}

// The first string value of "key" anywhere in the text (param.json's titleId and titleName).
inline std::string json_field(const std::string& text, const std::string& key) {
	const std::string needle = "\"" + key + "\"";
	for (size_t k = text.find(needle); k != std::string::npos; k = text.find(needle, k + 1)) {
		size_t c = k + needle.size();
		while (c < text.size() && (text[c] == ' ' || text[c] == '\t' || text[c] == '\r' || text[c] == '\n')) c++;
		if (c >= text.size() || text[c] != ':') continue;
		c++;
		while (c < text.size() && (text[c] == ' ' || text[c] == '\t' || text[c] == '\r' || text[c] == '\n')) c++;
		size_t end = 0;
		bool   ok  = false;
		const std::string v = json_string_at(text, c, &end, &ok);
		if (ok) return v;
	}
	return {};
}

// A top-level key of the record: it sits at the start of a line, two spaces in (as bc5-mount writes it), so a file
// named like a key inside the sha256 map is not taken for it. The text after the colon, white space skipped.
inline bool record_value(const std::string& text, const std::string& key, size_t* at) {
	const std::string needle = "  \"" + key + "\":";
	for (size_t k = 0; k < text.size();) {
		const size_t e = text.find('\n', k);
		const size_t n = (e == std::string::npos ? text.size() : e) - k;
		if (n >= needle.size() && text.compare(k, needle.size(), needle) == 0 && (n == needle.size() || text[k + 2] == '"')) {
			size_t c = k + needle.size();
			while (c < text.size() && text[c] == ' ') c++;
			*at = c;
			return true;
		}
		if (e == std::string::npos) break;
		k = e + 1;
	}
	return false;
}

// The record's image and total_bytes; false when the text is not a record bc5-mount wrote (the same rule as its
// `uninstall`: an image that is a non-empty string, a file count and a byte count).
inline bool parse_record(const std::string& text, std::string* image, uint64_t* bytes) {
	size_t first = text.find_first_not_of(" \t\r\n");
	size_t last  = text.find_last_not_of(" \t\r\n");
	if (first == std::string::npos || text[first] != '{' || text[last] != '}') return false;
	size_t at = 0, end = 0;
	bool   ok = false;
	if (!record_value(text, "image", &at)) return false;
	*image = json_string_at(text, at, &end, &ok);
	if (!ok || image->empty()) return false;
	for (const char* key: {"file_count", "total_bytes"}) {
		if (!record_value(text, key, &at) || at >= text.size() || text[at] < '0' || text[at] > '9') return false;
		uint64_t v = 0;
		while (at < text.size() && text[at] >= '0' && text[at] <= '9') v = v * 10 + static_cast<uint64_t>(text[at++] - '0');
		if (std::string(key) == "total_bytes") *bytes = v;
	}
	return true;
}

// The installed games under `root`, sorted by name.
inline std::vector<Installed> scan(const std::filesystem::path& root) {
	std::vector<Installed> out;
	std::error_code        ec;
	for (const auto& e: std::filesystem::directory_iterator(root, std::filesystem::directory_options::skip_permission_denied, ec)) {
		std::error_code tec;
		if (e.is_symlink(tec) || !e.is_directory(tec)) continue;
		const auto rec = e.path() / ".bc5-install.json";
		std::error_code rec_ec;
		if (!std::filesystem::is_regular_file(std::filesystem::symlink_status(rec, rec_ec))) continue;
		Installed g;
		if (!parse_record(read_small(rec), &g.image, &g.bytes)) continue;
		g.dir                    = e.path();
		const std::string param  = read_small(e.path() / "sce_sys" / "param.json", 1u << 20);
		g.title_id               = json_field(param, "titleId");
		g.name                   = json_field(param, "titleName");
		if (g.title_id.empty()) g.title_id = e.path().filename().string();
		if (g.name.empty()) g.name = g.title_id;
		std::error_code iec;
		g.image_present = std::filesystem::is_regular_file(g.image, iec);
		out.push_back(std::move(g));
	}
	std::sort(out.begin(), out.end(), [](const Installed& a, const Installed& b) { return a.name != b.name ? a.name < b.name : a.dir < b.dir; });
	return out;
}

// The games root: $HOME/bc5-data/games.
inline std::filesystem::path default_root(const char* home) {
	return std::filesystem::path(home != nullptr && home[0] != 0 ? home : "/") / "bc5-data" / "games";
}

// "196.7 GB" (decimal units, as the file manager shows them).
inline std::string human_size(uint64_t bytes) {
	char        buf[32];
	const double b = static_cast<double>(bytes);
	if (b >= 1e9) std::snprintf(buf, sizeof(buf), "%.1f GB", b / 1e9);
	else if (b >= 1e6) std::snprintf(buf, sizeof(buf), "%.1f MB", b / 1e6);
	else std::snprintf(buf, sizeof(buf), "%llu bytes", static_cast<unsigned long long>(bytes));
	return buf;
}

} // namespace bc5::games
