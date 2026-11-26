#!/usr/bin/env python3
"""BC5 Task 2 Part C: add "Install game..." to the emulator's menu.

Edit script (same style as work/mkpool0401.py): each anchor matched exactly once,
rerun refused with exit 1.

usage: mkmenu.py <in hostMenu.cpp> <out dir>
"""
import hashlib
import os
import sys

INPUT_MD5 = "d3810c9f"


def md5(data):
    return hashlib.md5(data).hexdigest()


def main():
    if len(sys.argv) != 3:
        print(f"usage: {sys.argv[0]} <in hostMenu.cpp> <out dir>", file=sys.stderr)
        sys.exit(1)

    cpp_path = sys.argv[1]
    out_dir = sys.argv[2]

    # Read input hostMenu.cpp
    with open(cpp_path, "r") as f:
        content = f.read()

    # Check if already edited (marker present)
    if "// ---- BEGIN bc5-install-menu ----" in content:
        print("has the edit already", file=sys.stderr)
        sys.exit(1)

    # Check md5
    with open(cpp_path, "rb") as f:
        data = f.read()
    if md5(data)[:8] != INPUT_MD5:
        print(f"input md5 {md5(data)[:8]} != expected {INPUT_MD5}", file=sys.stderr)
        sys.exit(1)

    # EDIT 1: Add EXIT_CODE_INSTALL after EXIT_CODE_CLOSE
    edit1_old = 'constexpr int EXIT_CODE_CLOSE   = 77; // ADR 0011: the launcher comes back with --menu'
    edit1_new = edit1_old + "\nconstexpr int EXIT_CODE_INSTALL = 78; // ADR 0011: the launcher installs the image"
    count1 = content.count(edit1_old)
    if count1 != 1:
        print(f"edit1: expected 1 match for EXIT_CODE_CLOSE, got {count1}", file=sys.stderr)
        sys.exit(1)
    content = content.replace(edit1_old, edit1_new, 1)

    # EDIT 2: Add Kind::Install to the Kind enum
    edit2_old = "enum class Kind {\n\tImage,\n\tPackage,\n};"
    edit2_new = "enum class Kind {\n\tImage,\n\tPackage,\n\tInstall,\n};"
    count2 = content.count(edit2_old)
    if count2 != 1:
        print(f"edit2: expected 1 match for Kind enum, got {count2}", file=sys.stderr)
        sys.exit(1)
    content = content.replace(edit2_old, edit2_new, 1)

    # EDIT 3: Add "Install game..." menu item after "Open package (.pkg)..." (Fix 12: enabled only on launcher page).
    edit3_old = '\t\t\tif (ImGui::MenuItem("Open package (.pkg)...", nullptr, false, has_dir)) {\n\t\t\t\ts.browser.Start(Kind::Package);\n\t\t\t}\n\t\t\tif (ImGui::BeginMenu("Recent"'
    edit3_new = '\t\t\tif (ImGui::MenuItem("Open package (.pkg)...", nullptr, false, has_dir)) {\n\t\t\t\ts.browser.Start(Kind::Package);\n\t\t\t}\n\t\t\tif (ImGui::MenuItem("Install game...", nullptr, false, launcher && MenuDir() != nullptr)) {\n\t\t\t\ts.browser.Start(Kind::Install);\n\t\t\t}\n\t\t\tif (ImGui::BeginMenu("Recent"'
    count3 = content.count(edit3_old)
    if count3 != 1:
        print(f"edit3: expected 1 match for Open package+Recent, got {count3}", file=sys.stderr)
        sys.exit(1)
    content = content.replace(edit3_old, edit3_new, 1)

    # EDIT 4: Mark Recent entries with " [installed]" suffix (Fix 9: only mark entries whose image path is listed).
    edit4_old = '\t\t\t\tfor (size_t i = 0; i < s.recent.size(); i++) {\n\t\t\t\t\tconst auto label = s.recent[i] + "##r" + std::to_string(i);\n\t\t\t\t\tif (ImGui::MenuItem(label.c_str())) {\n\t\t\t\t\t\tOpenPath(s, s.recent[i]);\n\t\t\t\t\t}\n\t\t\t\t}'
    edit4_new = '\t\t\t\tfor (size_t i = 0; i < s.recent.size(); i++) {\n\t\t\t\t\tconst auto& p = s.recent[i];\n\t\t\t\t\tconst bool is_installed = (MenuDir() != nullptr &&\n\t\t\t\t\t                         std::filesystem::exists(MenuFile("installed.txt")) &&\n\t\t\t\t\t                         [&]() -> bool {\n\t\t\t\t\t\t\tstd::ifstream f(MenuFile("installed.txt")); std::string line;\n\t\t\t\t\t\t\twhile (std::getline(f, line)) {\n\t\t\t\t\t\t\t\tsize_t tab = line.find(\'\\t\');\n\t\t\t\t\t\t\t\tif (tab != std::string::npos && line.substr(0, tab) == p) return true;\n\t\t\t\t\t\t\t}\n\t\t\t\t\t\t\treturn false;\n\t\t\t\t\t\t}());\n\t\t\t\t\tconst auto label = p + (is_installed ? " [installed]" : "") + "##r" + std::to_string(i);\n\t\t\t\t\tif (ImGui::MenuItem(label.c_str())) {\n\t\t\t\t\t\tOpenPath(s, p);\n\t\t\t\t\t}\n\t\t\t\t}'
    count4 = content.count(edit4_old)
    if count4 != 1:
        print(f"edit4: expected 1 match for Recent loop, got {count4}", file=sys.stderr)
        sys.exit(1)
    content = content.replace(edit4_old, edit4_new, 1)

    # EDIT 5: Add Install-specific browser behavior — write "install" to action.txt
    edit5_old = '\t\t\tif (b.selected == i && (ImGui::IsMouseDoubleClicked(0) || ImGui::IsKeyPressed(ImGuiKey_Enter) ||\n\t\t\t                        ImGui::IsKeyPressed(ImGuiKey_GamepadFaceDown))) {\n\t\t\t\tOpenPath(s, (b.dir / e.name).string());\n\t\t\t}'
    edit5_new = '\t\t\tif (b.selected == i && (ImGui::IsMouseDoubleClicked(0) || ImGui::IsKeyPressed(ImGuiKey_Enter) ||\n\t\t\t                        ImGui::IsKeyPressed(ImGuiKey_GamepadFaceDown))) {\n\t\t\t\tif (b.kind == Kind::Install) {\n\t\t\t\t\t// Install: write path to choice.txt, "install" to action.txt, exit 78.\n\t\t\t\t\tif (MenuDir() != nullptr) {\n\t\t\t\t\t\tWriteLines(MenuFile("choice.txt"), {(b.dir / e.name).string()});\n\t\t\t\t\t\tWriteLines(MenuFile("action.txt"), {"install"});\n\t\t\t\t\t}\n\t\t\t\t\tstd::fprintf(stderr, "host menu: install %s (exit %d)\\n", (b.dir / e.name).string().c_str(), 78);\n\t\t\t\t\tExitWith(78);\n\t\t\t\t}\n\t\t\t\tOpenPath(s, (b.dir / e.name).string());\n\t\t\t}'
    count5 = content.count(edit5_old)
    if count5 != 1:
        print(f"edit5: expected 1 match for browser select, got {count5}", file=sys.stderr)
        sys.exit(1)
    content = content.replace(edit5_old, edit5_new, 1)

    # EDIT 6: Update browser description for Install kind
    edit6_old = '\tImGui::TextWrapped("%s", b.kind == Kind::Image ? "A game image (.ffpfsc): the launcher mounts it with bc5-mount and starts the game."\n\t                                                : "A PS5 package (.pkg): the launcher mounts it with bc5-mount at ~/bc5-data/mnt/pkg-play and starts the game.");'
    edit6_new = '\tImGui::TextWrapped("%s", b.kind == Kind::Image ? "A game image (.ffpfsc): the launcher mounts it with bc5-mount and starts the game."\n\t                                                : b.kind == Kind::Package ? "A PS5 package (.pkg): the launcher mounts it with bc5-mount at ~/bc5-data/mnt/pkg-play and starts the game."\n\t                                                : "A game image (.pkg or .ffpfsc): the launcher installs it to ~/bc5-data/games/<TITLE_ID> and starts from there.");'
    count6 = content.count(edit6_old)
    if count6 != 1:
        print(f"edit6: expected 1 match for browser description, got {count6}", file=sys.stderr)
        sys.exit(1)
    content = content.replace(edit6_old, edit6_new, 1)

    # EDIT 7: Update browser filter to accept both .pkg and .ffpfsc for Install
    edit7_old = '\t\tconst std::string ext = KindExt(kind);\n\t\tfor (const auto& e: std::filesystem::directory_iterator(dir, std::filesystem::directory_options::skip_permission_denied, ec)) {\n\t\t\tconst auto name = e.path().filename().string();\n\t\t\tif (name.empty() || name[0] == \'.\') {\n\t\t\t\tcontinue;\n\t\t\t}\n\t\t\tstd::error_code tec;\n\t\t\tif (e.is_directory(tec)) {\n\t\t\t\tentries.push_back({name, true});\n\t\t\t} else if (e.is_regular_file(tec)) {\n\t\t\t\tconst auto lname = Lower(name);\n\t\t\t\tif (lname.size() > ext.size() && lname.compare(lname.size() - ext.size(), ext.size(), ext) == 0) {\n\t\t\t\t\tentries.push_back({name, false});\n\t\t\t\t}\n\t\t\t}\n\t\t}'
    edit7_new = '\t\tif (kind == Kind::Install) {\n\t\t\t// Install: accept both .pkg and .ffpfsc files.\n\t\t\tfor (const auto& e: std::filesystem::directory_iterator(dir, std::filesystem::directory_options::skip_permission_denied, ec)) {\n\t\t\t\tconst auto name = e.path().filename().string();\n\t\t\t\tif (name.empty() || name[0] == \'.\') {\n\t\t\t\t\tcontinue;\n\t\t\t\t}\n\t\t\t\tstd::error_code tec;\n\t\t\t\tif (e.is_directory(tec)) {\n\t\t\t\t\tentries.push_back({name, true});\n\t\t\t\t} else if (e.is_regular_file(tec)) {\n\t\t\t\t\tconst auto lname = Lower(name);\n\t\t\t\t\tif (lname.ends_with(".pkg") || lname.ends_with(".ffpfsc")) {\n\t\t\t\t\t\tentries.push_back({name, false});\n\t\t\t\t\t}\n\t\t\t\t}\n\t\t\t}\n\t\t} else {\n\t\t\tconst std::string ext = KindExt(kind);\n\t\t\tfor (const auto& e: std::filesystem::directory_iterator(dir, std::filesystem::directory_options::skip_permission_denied, ec)) {\n\t\t\t\tconst auto name = e.path().filename().string();\n\t\t\t\tif (name.empty() || name[0] == \'.\') {\n\t\t\t\t\tcontinue;\n\t\t\t\t}\n\t\t\t\tstd::error_code tec;\n\t\t\t\tif (e.is_directory(tec)) {\n\t\t\t\t\tentries.push_back({name, true});\n\t\t\t\t} else if (e.is_regular_file(tec)) {\n\t\t\t\t\tconst auto lname = Lower(name);\n\t\t\t\t\tif (lname.size() > ext.size() && lname.compare(lname.size() - ext.size(), ext.size(), ext) == 0) {\n\t\t\t\t\t\tentries.push_back({name, false});\n\t\t\t\t\t}\n\t\t\t\t}\n\t\t\t}\n\t\t}'
    count7 = content.count(edit7_old)
    if count7 != 1:
        print(f"edit7: expected 1 match for browser filter, got {count7}", file=sys.stderr)
        sys.exit(1)
    content = content.replace(edit7_old, edit7_new, 1)

    # Write output
    out_path = os.path.join(out_dir, "hostMenu.cpp")
    os.makedirs(out_dir, exist_ok=True)
    with open(out_path, "w") as f:
        f.write(content)

    print(f"patched -> {out_path}")


if __name__ == "__main__":
    main()
