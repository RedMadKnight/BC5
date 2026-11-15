#!/usr/bin/env python3
r"""BC5 experiment 0420: the menu's games (patch 0001, src/graphics/presentation/hostMenu.cpp; adds src/bc5/games_list.hpp).
File: Open game... (one browser: .ffpfsc, .pkg and a game folder), Installed games >, Install game...,
Uninstall game >, Recent >, Quit. "Close session" moves to Emulation. The launcher page shows the same three
actions and the installed list. Install and uninstall go to the launcher with exit 78 and action.txt (install or
uninstall); the launcher writes install-progress.txt while an install runs and result.txt with its outcome, which
the menu shows in its status line. The same code in the normal and the lean build.
usage: mkmenu0420.py <tree root>"""
import os, shutil, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "0419-switch-cleanup"))
from ed0419g import File

root = sys.argv[1]
here = os.path.dirname(os.path.abspath(__file__))
shutil.copyfile(os.path.join(here, "games_list.hpp"), os.path.join(root, "src", "bc5", "games_list.hpp"))
f = File(os.path.join(root, "src", "graphics", "presentation", "hostMenu.cpp"))
f.gone("games_list.hpp", "Kind::Game")

f.sub('#include "kytyGitVersion.h"\n', '#include "kytyGitVersion.h"\n#include "bc5/games_list.hpp" // experiment 0420: the installed games\n')
f.sub("#include <vector>\n\n#include \"graphics/presentation/window/hostInput.h\"",
      "#include <vector>\n#include <SDL_timer.h>\n\n#include \"graphics/presentation/window/hostInput.h\"")
f.sub("constexpr int EXIT_CODE_INSTALL = 78; // ADR 0011: the launcher installs the image\n",
      "constexpr int EXIT_CODE_INSTALL = 78; // ADR 0011: the launcher installs or (exp 0420) uninstalls, by action.txt\n")

# the browser: one kind for opening (images, packages, game folders)
f.sub("enum class Kind {\n\tImage,\n\tPackage,\n\tInstall,\n};\n",
      "enum class Kind {\n\tImage,\n\tPackage,\n\tInstall,\n\tGame, // experiment 0420: Open game... (.ffpfsc, .pkg, a game folder)\n};\n")
f.sub('const char* KindExt(Kind k) {\n\treturn k == Kind::Image ? ".ffpfsc" : ".pkg";\n}\n',
      'const char* KindExt(Kind k) {\n\treturn k == Kind::Image ? ".ffpfsc" : (k == Kind::Package ? ".pkg" : ".ffpfsc or .pkg");\n}\n')
f.sub('\treturn k == Kind::Image ? "lastdir-image.txt" : "lastdir-package.txt";\n',
      '\treturn k == Kind::Package ? "lastdir-package.txt" : "lastdir-image.txt";\n')
f.sub("struct Entry {\n\tstd::string name;\n\tbool        dir;\n};\n",
      "struct Entry {\n\tstd::string name;\n\tbool        dir;\n\tbool        game = false; // experiment 0420: a folder that holds sce_sys/param.json, opened rather than entered\n};\n")
f.sub("\t\tif (kind == Kind::Install) {\n\t\t\t// Install: accept both .pkg and .ffpfsc files.\n",
      "\t\tif (kind == Kind::Install || kind == Kind::Game) {\n\t\t\t// Install and Open game: both .pkg and .ffpfsc files (Open game: game folders too).\n")
f.sub("\t\t\t\tif (e.is_directory(tec)) {\n\t\t\t\t\tentries.push_back({name, true});\n\t\t\t\t} else if (e.is_regular_file(tec)) {\n\t\t\t\t\tconst auto lname = Lower(name);\n\t\t\t\t\tif (lname.ends_with(\".pkg\") || lname.ends_with(\".ffpfsc\")) {\n",
      "\t\t\t\tif (e.is_directory(tec)) {\n\t\t\t\t\tstd::error_code gec;\n\t\t\t\t\tentries.push_back({name, true, kind == Kind::Game && std::filesystem::is_regular_file(e.path() / \"sce_sys\" / \"param.json\", gec)});\n\t\t\t\t} else if (e.is_regular_file(tec)) {\n\t\t\t\t\tconst auto lname = Lower(name);\n\t\t\t\t\tif (lname.ends_with(\".pkg\") || lname.ends_with(\".ffpfsc\")) {\n")

# the state: the installed list, the uninstall confirmation, the launcher's progress and result files
f.sub("\tstd::vector<std::string> recent;\n\tbool                     recent_loaded     = false;\n};\n",
      "\tstd::vector<std::string> recent;\n\tbool                     recent_loaded     = false;\n"
      "\t// experiment 0420\n"
      "\tstd::vector<bc5::games::Installed> installed;\n"
      "\tuint32_t                 installed_at      = 0;     // SDL ticks of the last scan (0: never)\n"
      "\tint                      uninstall_pick    = -1;    // the game the confirmation is about\n"
      "\tbool                     want_uninstall    = false;\n"
      "\tstd::string              progress;                // install-progress.txt's line while an install runs\n"
      "\tuint32_t                 progress_at       = 0;\n"
      "};\n")
f.sub("void LoadRecent(State& s) {\n",
      r'''// Experiment 0420: the installed games, read from the folders (bc5/games_list.hpp) at most once a second, and the
// launcher's files: install-progress.txt while an install runs in the background, result.txt once (then removed).
void LoadInstalled(State& s, bool now = false) {
	const uint32_t t = SDL_GetTicks();
	if (!now && s.installed_at != 0 && t - s.installed_at < 1000) {
		return;
	}
	s.installed_at = t == 0 ? 1 : t;
	s.installed    = bc5::games::scan(bc5::games::default_root(std::getenv("HOME")));
	if (MenuDir() == nullptr) {
		return;
	}
	const auto progress = ReadLines(MenuFile("install-progress.txt"));
	s.progress          = progress.empty() ? std::string() : progress.back();
	const auto result   = ReadLines(MenuFile("result.txt"));
	if (!result.empty()) {
		s.status = result.back();
		std::error_code ec;
		std::filesystem::remove(MenuFile("result.txt"), ec);
	}
}

const bc5::games::Installed* InstalledFor(const State& s, const std::string& path) {
	for (const auto& g: s.installed) {
		if (g.image == path || g.dir.string() == path) return &g;
	}
	return nullptr;
}

std::string InstalledLabel(const bc5::games::Installed& g) {
	return g.name == g.title_id ? g.title_id : g.name + "  (" + g.title_id + ")";
}

void LoadRecent(State& s) {
''')

# Install and uninstall leave through exit 78 with action.txt
f.sub("void CloseSession() {\n",
      r'''// Experiment 0420: the launcher installs the image (in the background, the menu comes back at once) or removes an
// installed game with bc5-mount uninstall; action.txt says which, choice.txt names the image or the folder.
void LauncherAction(State& s, const char* action, const std::string& path) {
	if (MenuDir() == nullptr) {
		s.status = "No launcher: start the emulator through play-any.sh to install or uninstall games.";
		return;
	}
	if (!WriteLines(MenuFile("choice.txt"), {path}) || !WriteLines(MenuFile("action.txt"), {action})) {
		s.status = "Cannot write " + MenuFile("action.txt").string();
		return;
	}
	std::fprintf(stderr, "host menu: %s %s (exit %d)\n", action, path.c_str(), EXIT_CODE_INSTALL);
	ExitWith(EXIT_CODE_INSTALL);
}

void CloseSession() {
''')
f.sub("\t\t\t\tif (b.kind == Kind::Install) {\n\t\t\t\t\t// Install: write path to choice.txt, \"install\" to action.txt, exit 78.\n\t\t\t\t\tif (MenuDir() != nullptr) {\n\t\t\t\t\t\tWriteLines(MenuFile(\"choice.txt\"), {(b.dir / e.name).string()});\n\t\t\t\t\t\tWriteLines(MenuFile(\"action.txt\"), {\"install\"});\n\t\t\t\t\t}\n\t\t\t\t\tstd::fprintf(stderr, \"host menu: install %s (exit %d)\\n\", (b.dir / e.name).string().c_str(), 78);\n\t\t\t\t\tExitWith(78);\n\t\t\t\t}\n",
      "\t\t\t\tif (b.kind == Kind::Install) {\n\t\t\t\t\tLauncherAction(s, \"install\", (b.dir / e.name).string()); // experiment 0420: through the one helper\n\t\t\t\t}\n")
# a game folder is opened, not entered
f.sub("\t\tif (ImGui::Selectable(label.c_str(), b.selected == i, ImGuiSelectableFlags_AllowDoubleClick)) {\n\t\t\tif (e.dir) {\n",
      "\t\tif (ImGui::Selectable(label.c_str(), b.selected == i, ImGuiSelectableFlags_AllowDoubleClick)) {\n\t\t\tif (e.dir && !e.game) {\n")
f.sub('\t\tconst auto  label = (e.dir ? "[" + e.name + "]" : e.name) + "##" + std::to_string(i);\n',
      '\t\tconst auto  label = (e.game ? e.name + "   (game folder)" : (e.dir ? "[" + e.name + "]" : e.name)) + "##" + std::to_string(i);\n')
f.sub("\tconst bool has_file = b.selected >= 0 && b.selected < static_cast<int>(b.entries.size()) && !b.entries[b.selected].dir;\n",
      "\tconst bool has_file = b.selected >= 0 && b.selected < static_cast<int>(b.entries.size()) &&\n\t                      (!b.entries[b.selected].dir || b.entries[b.selected].game);\n")
f.sub('\tif (ImGui::Button("Open", {120.0f * scale, 0.0f})) {\n\t\tOpenPath(s, (b.dir / b.entries[b.selected].name).string());\n\t}\n',
      '\tif (ImGui::Button(b.kind == Kind::Install ? "Install" : "Open", {120.0f * scale, 0.0f})) {\n'
      '\t\tif (b.kind == Kind::Install) {\n\t\t\tLauncherAction(s, "install", (b.dir / b.entries[b.selected].name).string()); // experiment 0420: the button installed nothing before\n'
      '\t\t} else {\n\t\t\tOpenPath(s, (b.dir / b.entries[b.selected].name).string());\n\t\t}\n\t}\n')
f.sub('''	ImGui::TextWrapped("%s", b.kind == Kind::Image ? "A game image (.ffpfsc): the launcher mounts it with bc5-mount and starts the game."
	                                                : b.kind == Kind::Package ? "A PS5 package (.pkg): the launcher mounts it with bc5-mount at ~/bc5-data/mnt/pkg-play and starts the game."
	                                                : "A game image (.pkg or .ffpfsc): the launcher installs it to ~/bc5-data/games/<TITLE_ID> and starts from there.");
''', '''	ImGui::TextWrapped("%s", b.kind == Kind::Install ? "A game image (.ffpfsc) or package (.pkg): the launcher unpacks it to ~/bc5-data/games/<TITLE_ID>; "
	                                                    "it shows on Installed games when it is done, and the image can then be moved or deleted."
	                                                  : "A game image (.ffpfsc), a package (.pkg), or a game folder (one that holds sce_sys/param.json): "
	                                                    "the launcher mounts the image or uses the folder and starts the game with its settings.");
''')

# the uninstall confirmation
f.sub("void DrawAboutPopup(State& s, float scale) {\n",
      r'''// Experiment 0420: the confirmation before an installed game is removed.
void DrawUninstallPopup(State& s, float scale) {
	if (s.want_uninstall) {
		ImGui::OpenPopup("Uninstall game##uninstall");
		s.want_uninstall = false;
	}
	if (ImGui::BeginPopupModal("Uninstall game##uninstall", nullptr, ImGuiWindowFlags_AlwaysAutoResize | ImGuiWindowFlags_NoSavedSettings)) {
		if (s.uninstall_pick < 0 || s.uninstall_pick >= static_cast<int>(s.installed.size())) {
			ImGui::CloseCurrentPopup();
			ImGui::EndPopup();
			return;
		}
		const auto& g = s.installed[static_cast<size_t>(s.uninstall_pick)];
		ImGui::Text("%s", InstalledLabel(g).c_str());
		ImGui::Text("Folder: %s", g.dir.string().c_str());
		ImGui::Text("Frees: %s", bc5::games::human_size(g.bytes).c_str());
		ImGui::Separator();
		ImGui::TextWrapped("The game's folder is deleted. Its saves are kept (they are not in that folder).");
		if (!g.image_present) {
			ImGui::TextColored({1.0f, 0.5f, 0.4f, 1.0f}, "The image it was installed from is not at %s:", g.image.c_str());
			ImGui::TextColored({1.0f, 0.5f, 0.4f, 1.0f}, "to play it again you will need that image again.");
		}
		if (ImGui::Button("Uninstall", {120.0f * scale, 0.0f})) {
			LauncherAction(s, "uninstall", g.dir.string());
		}
		ImGui::SameLine();
		if (ImGui::Button("Cancel", {120.0f * scale, 0.0f})) {
			s.uninstall_pick = -1;
			ImGui::CloseCurrentPopup();
		}
		ImGui::EndPopup();
	}
}

void DrawAboutPopup(State& s, float scale) {
''')

# the launcher page: the three actions and the installed list
f.sub('''	ImGui::TextWrapped("Open a game image or a PS5 package: the launcher mounts it with bc5-mount, keeps the title's "
	                   "settings, and starts the game in this window. Close session brings this page back.");
	ImGui::Separator();
	if (ImGui::Button("Open game image...", {-1.0f, 0.0f})) {
		s.browser.Start(Kind::Image);
	}
	if (ImGui::Button("Open package (.pkg)...", {-1.0f, 0.0f})) {
		s.browser.Start(Kind::Package);
	}
	ImGui::Separator();
	ImGui::TextDisabled("Recent");
''', '''	ImGui::TextWrapped("Start an installed game, open a game image, package or folder, or install one: the launcher keeps "
	                   "the title's settings and starts the game in this window. Close session (Emulation) brings this page back.");
	ImGui::Separator();
	if (ImGui::Button("Open game...", {-1.0f, 0.0f})) {
		s.browser.Start(Kind::Game);
	}
	if (ImGui::Button("Install game...", {-1.0f, 0.0f})) {
		s.browser.Start(Kind::Install);
	}
	ImGui::Separator();
	ImGui::TextDisabled("Installed games");
	if (s.installed.empty()) {
		ImGui::TextDisabled("(none in ~/bc5-data/games)");
	}
	for (size_t i = 0; i < s.installed.size(); i++) {
		const auto& g     = s.installed[i];
		const auto  label = InstalledLabel(g) + "   " + bc5::games::human_size(g.bytes) + "##inst" + std::to_string(i);
		if (ImGui::Selectable(label.c_str(), false)) {
			OpenPath(s, g.dir.string());
		}
	}
	ImGui::Separator();
	ImGui::TextDisabled("Recent");
''')
f.sub('''	if (!s.status.empty()) {
		ImGui::TextColored({1.0f, 0.8f, 0.2f, 1.0f}, "%s", s.status.c_str());
	} else {
		ImGui::TextDisabled("Pad: d-pad or left stick, Cross = choose, Square = the menu bar. Keyboard: F1 hides the menu.");
	}
	ImGui::End();
''', '''	if (!s.progress.empty()) {
		ImGui::TextColored({0.5f, 0.8f, 1.0f, 1.0f}, "%s", s.progress.c_str()); // experiment 0420: an install running
	}
	if (!s.status.empty()) {
		ImGui::TextColored({1.0f, 0.8f, 0.2f, 1.0f}, "%s", s.status.c_str());
	} else if (s.progress.empty()) {
		ImGui::TextDisabled("Pad: d-pad or left stick, Cross = choose, Square = the menu bar. Keyboard: F1 hides the menu.");
	}
	ImGui::End();
''')

# the File menu
a = f.b.index(b'\t\tif (ImGui::BeginMenu("File")) {\n')
e = f.b.index(b'\t\tif (ImGui::BeginMenu("Emulation")) {\n')
old_file = f.b[a:e].decode()
assert "Open package (.pkg)..." in old_file and "Close session" in old_file
new_file = r'''		if (ImGui::BeginMenu("File")) {
			// Experiment 0420: one Open, the installed games, install and uninstall, Recent, Quit.
			LoadInstalled(s);
			if (ImGui::MenuItem("Open game...", nullptr, false, has_dir)) {
				s.browser.Start(Kind::Game);
			}
			if (ImGui::BeginMenu("Installed games", has_dir)) {
				if (s.installed.empty()) {
					ImGui::TextDisabled("(none in ~/bc5-data/games)");
				}
				for (size_t i = 0; i < s.installed.size(); i++) {
					const auto label = InstalledLabel(s.installed[i]) + "##inst" + std::to_string(i);
					if (ImGui::MenuItem(label.c_str())) {
						OpenPath(s, s.installed[i].dir.string());
					}
				}
				ImGui::EndMenu();
			}
			if (ImGui::MenuItem("Install game...", nullptr, false, launcher && has_dir)) {
				s.browser.Start(Kind::Install);
			}
			if (ImGui::BeginMenu("Uninstall game", launcher && has_dir && !s.installed.empty())) {
				for (size_t i = 0; i < s.installed.size(); i++) {
					const auto label = InstalledLabel(s.installed[i]) + "   " + bc5::games::human_size(s.installed[i].bytes) + "##uninst" + std::to_string(i);
					if (ImGui::MenuItem(label.c_str())) {
						s.uninstall_pick = static_cast<int>(i);
						s.want_uninstall = true;
					}
				}
				ImGui::EndMenu();
			}
			if (ImGui::BeginMenu("Recent", has_dir && !s.recent.empty())) {
				for (size_t i = 0; i < s.recent.size(); i++) {
					const auto& p     = s.recent[i];
					const auto  label = p + (InstalledFor(s, p) != nullptr ? " [installed]" : "") + "##r" + std::to_string(i);
					if (ImGui::MenuItem(label.c_str())) {
						OpenPath(s, p);
					}
				}
				ImGui::Separator();
				if (ImGui::MenuItem("Clear list")) {
					s.recent.clear();
					WriteLines(MenuFile("recent.txt"), {});
				}
				ImGui::EndMenu();
			}
			if (!has_dir && ImGui::IsItemHovered(ImGuiHoveredFlags_AllowWhenDisabled)) {
				ImGui::SetTooltip("Start the emulator through play-any.sh to open games from here.");
			}
			ImGui::Separator();
			if (ImGui::MenuItem("Quit")) {
				Quit();
			}
			ImGui::EndMenu();
		}
'''
f.b = f.b[:a] + new_file.encode() + f.b[e:]
f.n += 1
f.sub('\t\tif (ImGui::BeginMenu("Emulation")) {\n\t\t\tconst bool paused = WindowIsPaused();\n',
      '\t\tif (ImGui::BeginMenu("Emulation")) {\n'
      '\t\t\tif (ImGui::MenuItem("Close session", nullptr, false, !launcher)) { // experiment 0420: moved here from File\n'
      '\t\t\t\tCloseSession();\n\t\t\t}\n'
      '\t\t\tconst bool paused = WindowIsPaused();\n')
f.sub("\tLoadRecent(s);\n\n\tif (ImGui::BeginMainMenuBar()) {\n",
      "\tLoadRecent(s);\n\tif (launcher) {\n\t\tLoadInstalled(s); // experiment 0420: the launcher page's list, the install progress and the launcher's result\n\t}\n\n\tif (ImGui::BeginMainMenuBar()) {\n")
f.sub("\tDrawRestartPopup(s, scale);\n\tDrawAboutPopup(s, scale);\n}\n",
      "\tDrawRestartPopup(s, scale);\n\tDrawUninstallPopup(s, scale); // experiment 0420\n\tDrawAboutPopup(s, scale);\n}\n")
# Recent lists only paths that exist (the maintainer, 2026-11-15 13:05: "recent nie może być elementów, które nie
# istnieją"): a moved or deleted image, a package gone, an uninstalled game's folder are dropped when the list is read,
# and recent.txt is written without them.
f.sub("\tif (MenuDir() != nullptr) {\n\t\ts.recent = ReadLines(MenuFile(\"recent.txt\"));\n\t}\n}\n",
      "\tif (MenuDir() != nullptr) {\n"
      "\t\t// experiment 0420: a path that no longer exists is dropped from the list and from recent.txt\n"
      "\t\tauto         lines  = ReadLines(MenuFile(\"recent.txt\"));\n"
      "\t\tconst size_t before = lines.size();\n"
      "\t\tlines.erase(std::remove_if(lines.begin(), lines.end(),\n"
      "\t\t                           [](const std::string& p) {\n"
      "\t\t\t                           std::error_code ec;\n"
      "\t\t\t                           return !std::filesystem::exists(p, ec);\n"
      "\t\t                           }),\n"
      "\t\t            lines.end());\n"
      "\t\tif (lines.size() != before) {\n"
      "\t\t\tWriteLines(MenuFile(\"recent.txt\"), lines);\n"
      "\t\t}\n"
      "\t\ts.recent = std::move(lines);\n"
      "\t}\n}\n")
f.gone('"Open package (.pkg)..."', "installed.txt")
f.save()
