#!/usr/bin/env python3
# BC5 experiment 0337 (the maintainer: "dodanie w konsoli wyboru języka jakim domyślnie emulator się posługuje tak jak w
# ps5"): the console's system language as a setting, like the PS5's Settings > System > Language. One-file changes of four
# shared-tree files (each md5-checked):
#   graphics/presentation/window/hostInput.h    the declarations below
#   graphics/presentation/window/hostInput.cpp  SystemLanguage=<name|number> in the input configuration (a name compared on
#                                               its letters, any case; the numbering is SystemServiceParamGetInt's), written
#                                               back by name; HostInputSystemLanguage() (-1 not set; before the input map
#                                               exists it reads the file alone), and the language list for the overlay
#   libs/libSystemService.cpp                   PARAM_ID_LANG answers SystemLanguage when it is set, else
#                                               --console-language (English (United States) by default), as before
#   graphics/presentation/settingsOverlay.cpp   a System tab in the settings overlay (F2): the language list, Save; the
#                                               game reads the language when it starts, so the choice applies from its
#                                               next start (Restart game, Video tab), as on the console
# usage: patch0337.py <tree src dir> <out dir> <out .diff>   (the tree is only read)
import difflib, hashlib, os, sys

FILES = {
    'graphics/presentation/window/hostInput.h': 'a98cd3587a38376c936b7d24d18ab303',
    'graphics/presentation/window/hostInput.cpp': '47f83afbf00f5cd1c9f8386a6433c8c0',
    'libs/libSystemService.cpp': 'c67a08e699de3a1500480bcb5be1d73a',
    'graphics/presentation/settingsOverlay.cpp': '813dd1c9064c92a2a709a5adb69e616e',
}

LANGS = r'''// Experiment 0337: the system languages in SystemServiceParamGetInt's numbering (PARAM_ID_LANG), as KytyPlus's
// launcher lists them (launcher/src/configurationEditDialog.cpp CONSOLE_LANGUAGE_NAMES at f266548;
// Config::MAX_CONSOLE_LANGUAGE is 29).
constexpr std::array<const char*, 30> LANGUAGE_NAMES = {
    "Japanese",          "English (United States)", "French (France)",   "Spanish (Spain)",          "German",
    "Italian",           "Dutch",                   "Portuguese (Portugal)", "Russian",              "Korean",
    "Chinese (Traditional)", "Chinese (Simplified)", "Finnish",           "Swedish",                  "Danish",
    "Norwegian",         "Polish",                  "Portuguese (Brazil)", "English (United Kingdom)", "Turkish",
    "Spanish (Latin America)", "Arabic",            "French (Canada)",   "Czech",                    "Hungarian",
    "Greek",             "Romanian",                "Thai",              "Vietnamese",               "Indonesian",
};

std::string LanguageKey(std::string_view s) { // letters and digits only, lower case
	std::string k;
	for (const char c: s) {
		if (std::isalnum(static_cast<unsigned char>(c)) != 0) k.push_back(static_cast<char>(std::tolower(static_cast<unsigned char>(c))));
	}
	return k;
}

// A number 0..29, or a name compared on its letters and digits, any case ("Polish", "polish", "english-united-states");
// -1 if neither.
int LanguageFromName(std::string_view s) {
	while (!s.empty() && std::isspace(static_cast<unsigned char>(s.front())) != 0) s.remove_prefix(1);
	while (!s.empty() && std::isspace(static_cast<unsigned char>(s.back())) != 0) s.remove_suffix(1);
	if (s.empty()) return -1;
	if (std::all_of(s.begin(), s.end(), [](char c) { return std::isdigit(static_cast<unsigned char>(c)) != 0; })) {
		const int n = s.size() <= 2 ? std::atoi(std::string(s).c_str()) : -1;
		return n >= 0 && n < static_cast<int>(LANGUAGE_NAMES.size()) ? n : -1;
	}
	const std::string key = LanguageKey(s);
	for (std::size_t i = 0; i < LANGUAGE_NAMES.size(); i++) {
		if (LanguageKey(LANGUAGE_NAMES[i]) == key) return static_cast<int>(i);
	}
	return -1;
}

class InputMap {
'''

EDITS = {
    'graphics/presentation/window/hostInput.h': [
        ('void HostInputReleaseAll();\n', '''void HostInputReleaseAll();

// Experiment 0337: the console's system language (PS5: Settings > System > Language), SystemLanguage=<name|number> in the
// input configuration, in SystemServiceParamGetInt's numbering (PARAM_ID_LANG). -1: not set.
int         HostInputSystemLanguage();
int         HostInputLanguageCount();
const char* HostInputLanguageName(int language);              // "" outside 0..count-1
int         HostInputLanguageFromName(const std::string& name); // a number or a name, any case; -1 if neither
'''),
    ],
    'graphics/presentation/window/hostInput.cpp': [
        ('class InputMap {\n', LANGS),
        ('''		std::vector<std::string> out;
		if (m_fullscreen >= 0) {
			out.emplace_back(m_fullscreen == 1 ? "Fullscreen=on" : "Fullscreen=off");
		}
''', '''		std::vector<std::string> out;
		if (m_fullscreen >= 0) {
			out.emplace_back(m_fullscreen == 1 ? "Fullscreen=on" : "Fullscreen=off");
		}
		if (m_system_language >= 0) out.emplace_back(std::string("SystemLanguage=") + LANGUAGE_NAMES[m_system_language]); // experiment 0337
'''),
        ('''	[[nodiscard]] int    Fullscreen() const { return m_fullscreen; }
''', '''	[[nodiscard]] int    Fullscreen() const { return m_fullscreen; }
	[[nodiscard]] int    SystemLanguage() const { return m_system_language; } // experiment 0337: -1 not set
'''),
        ('''		if (EqualNoCase(left, "DefaultKeys")) {
''', '''		if (EqualNoCase(left, "SystemLanguage")) { // experiment 0337: the console's system language
			const int v = LanguageFromName(right);
			if (v < 0) {
				return Fail(error, where + ": SystemLanguage takes a language name or a number from 0 to 29, got: " + std::string(right));
			}
			m_system_language = v;
			return true;
		}

		if (EqualNoCase(left, "DefaultKeys")) {
'''),
        ('''	int                  m_fullscreen       = -1;  // -1: not set (--fullscreen or windowed)
''', '''	int                  m_fullscreen       = -1;  // -1: not set (--fullscreen or windowed)
	int                  m_system_language  = -1;  // experiment 0337: -1 not set (--console-language, English (United States) by default)
'''),
        ('''void HostInputReleaseAll() {
	std::lock_guard<std::mutex> lock(g_input_mutex);
	Map();
	ReleaseAll();
	g_pending.clear();
}
''', '''void HostInputReleaseAll() {
	std::lock_guard<std::mutex> lock(g_input_mutex);
	Map();
	ReleaseAll();
	g_pending.clear();
}

// Experiment 0337: the title may ask for the language before the window builds the map, so before it exists only the file
// is read here, without the map's side effects (a bad line leaves -1 here; Map() reports it when it is built).
int HostInputSystemLanguage() {
	std::lock_guard<std::mutex> lock(g_input_mutex);
	if (g_map != nullptr) {
		return g_map->SystemLanguage();
	}
	const char* path = std::getenv("KYTY_BC5_INPUT_CONFIG");
	if (path == nullptr || *path == 0) {
		return -1;
	}
	std::string error;
	const auto  lines = ReadConfigLines(path, &error);
	InputMap    probe;
	return error.empty() && probe.Load(lines, &error) ? probe.SystemLanguage() : -1;
}

int HostInputLanguageCount() {
	return static_cast<int>(LANGUAGE_NAMES.size());
}

const char* HostInputLanguageName(int language) {
	return language >= 0 && language < HostInputLanguageCount() ? LANGUAGE_NAMES[language] : "";
}

int HostInputLanguageFromName(const std::string& name) {
	return LanguageFromName(name);
}
'''),
    ],
    'libs/libSystemService.cpp': [
        ('#include "common/emulatorConfig.h"\n', '#include "common/emulatorConfig.h"\n#include "graphics/presentation/window/hostInput.h" // experiment 0337\n'),
        ('''		case PARAM_ID_LANG: v = static_cast<int>(Config::GetConsoleLanguage()); break;
''', '''		case PARAM_ID_LANG: { // experiment 0337: the input configuration's SystemLanguage, else --console-language
			const int system_language = Graphics::HostInputSystemLanguage();
			v                         = system_language >= 0 ? system_language : static_cast<int>(Config::GetConsoleLanguage());
			break;
		}
'''),
    ],
    'graphics/presentation/settingsOverlay.cpp': [
        ('''		char b[64];
		std::snprintf(b, sizeof(b), "%s=%.2f", key.c_str(), k);
		lines.insert(lines.begin(), b);
	}
};
''', '''		char b[64];
		std::snprintf(b, sizeof(b), "%s=%.2f", key.c_str(), k);
		lines.insert(lines.begin(), b);
	}

	// Experiment 0337: SystemLanguage=<name>, the console's system language (-1: no line).
	[[nodiscard]] int SystemLanguage() const {
		int v = -1;
		for (const auto& l: lines) {
			if (EqualNoCase(StatementLeft(l), "SystemLanguage")) v = HostInputLanguageFromName(std::string(StatementRight(l)));
		}
		return v;
	}

	void SetSystemLanguage(int language) {
		lines.erase(std::remove_if(lines.begin(), lines.end(),
		                           [&](const std::string& l) { return EqualNoCase(StatementLeft(l), "SystemLanguage"); }),
		            lines.end());
		lines.insert(lines.begin(), std::string("SystemLanguage=") + HostInputLanguageName(language));
	}
};
'''),
        ('''			if (ImGui::BeginTabItem("Video")) {
				DrawVideo();
				ImGui::EndTabItem();
			}
''', '''			if (ImGui::BeginTabItem("Video")) {
				DrawVideo();
				ImGui::EndTabItem();
			}
			if (ImGui::BeginTabItem("System")) { // experiment 0337
				DrawSystem();
				ImGui::EndTabItem();
			}
'''),
        ('''	// Experiment 0047: the title picks its 3D resolution itself, from the GPU time its timestamps
''', '''	// Experiment 0337: the console's system language, as the PS5's Settings > System > Language. The game reads it once,
	// when it starts (SystemServiceParamGetInt, PARAM_ID_LANG), so a new choice applies from its next start: Save, then
	// Restart game (Video tab). Without a SystemLanguage line the emulator's --console-language stays (English (United
	// States) by default).
	void DrawSystem() {
		const int saved   = HostInputSystemLanguage();
		const int chosen  = draft.SystemLanguage();
		const int current = chosen >= 0 ? chosen : (saved >= 0 ? saved : 1);
		ImGui::TextWrapped("System language, as on the console (Settings > System > Language). Games read it when they "
		                   "start: Save, then Restart game (Video tab).");
		if (ImGui::BeginCombo("Language", HostInputLanguageName(current))) {
			for (int i = 0; i < HostInputLanguageCount(); i++) {
				if (ImGui::Selectable(HostInputLanguageName(i), i == current)) {
					draft.SetSystemLanguage(i);
					dirty         = true;
					system_status = std::string(HostInputLanguageName(i)) + ": Save, then Restart game (Video tab)";
				}
				if (i == current) {
					ImGui::SetItemDefaultFocus();
				}
			}
			ImGui::EndCombo();
		}
		ImGui::BeginDisabled(path.empty());
		if (ImGui::Button("Save##system")) {
			std::string error;
			if (!HostInputSave(path, draft.lines, &error)) {
				system_status = "not saved: " + error;
			} else if (!HostInputApply(draft.lines, &error)) {
				system_status = "saved, not applied: " + error;
			} else {
				system_status = "saved; the game uses it from its next start (Restart game, Video tab)";
				dirty         = false;
			}
		}
		ImGui::EndDisabled();
		ImGui::SameLine();
		if (ImGui::Button("Close##system")) {
			SettingsOverlayToggle();
		}
		ImGui::TextUnformatted(system_status.c_str());
	}

	// Experiment 0047: the title picks its 3D resolution itself, from the GPU time its timestamps
'''),
        ('''	std::string                           video_status;
''', '''	std::string                           video_status;
	std::string                           system_status; // experiment 0337
'''),
    ],
}


def main():
    src, out_dir, diff_path = sys.argv[1:4]
    diffs = []
    for rel, want in FILES.items():
        raw = open(os.path.join(src, rel), 'rb').read()
        md5 = hashlib.md5(raw).hexdigest()
        if want is not None and md5 != want:
            sys.exit(f'{rel}: md5 {md5}, expected {want}')
        crlf = b'\r\n' in raw
        text = raw.decode('utf-8').replace('\r\n', '\n')
        orig = text
        for k, (old, new) in enumerate(EDITS[rel], 1):
            n = text.count(old)
            if n != 1:
                sys.exit(f'{rel} edit {k}: anchor found {n} times')
            text = text.replace(old, new)
        out = (text.replace('\n', '\r\n') if crlf else text).encode('utf-8')
        os.makedirs(os.path.join(out_dir, os.path.dirname(rel)), exist_ok=True)
        open(os.path.join(out_dir, rel), 'wb').write(out)
        diffs += difflib.unified_diff(orig.splitlines(keepends=True), text.splitlines(keepends=True), f'a/src/{rel}', f'b/src/{rel}', n=3)
        print(f'{rel}: {len(EDITS[rel])} edits, {"CRLF" if crlf else "LF"}, md5 {md5[:8]} -> {hashlib.md5(out).hexdigest()[:8]}')
    open(diff_path, 'w', encoding='utf-8', newline='\n').write(''.join(diffs))


if __name__ == '__main__':
    main()
