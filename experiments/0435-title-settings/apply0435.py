#!/usr/bin/env python3
# BC5 experiment 0435: apply the per-title settings change to a KytyPlus tree that carries patch 0001 59f00d27.
#   python3 apply0435.py <tree> <title_settings.hpp>
# Every edit is an exact-text replacement that must match exactly once (else nothing is written and the script fails);
# files are read and written as bytes, LF. Run it on a COPY of the tree (the shared tree changes only on his word).
import sys
from pathlib import Path

tree = Path(sys.argv[1])
header = Path(sys.argv[2])

EDITS = {
    "src/graphics/presentation/window/hostInput.cpp": [
        (
            '#include "graphics/presentation/window.h"\n',
            '#include "graphics/presentation/window.h"\n'
            '#include "bc5/title_settings.hpp" // exp 0435: each title keeps its own input.cfg and window mode\n',
        ),
        (
            "std::unique_ptr<InputMap> g_map;\nstd::string               g_config_path;\n",
            "std::unique_ptr<InputMap> g_map;\nstd::string               g_config_path;\n"
            "std::string               g_title_dir; // exp 0435: the title's store (window mode), \"\" when none\n"
            "std::string               g_save_path; // exp 0435: where Save writes (HostInputConfigPath), \"\" when nowhere\n"
            "\n"
            "// Experiment 0435: the input configuration this run reads and saves: the title's own file,\n"
            "// <menu dir>/titles/<TITLE_ID>/input.cfg, seeded from KYTY_BC5_INPUT_CONFIG on the title's first start; the\n"
            "// shared file without a title id or with KYTY_BC5_TITLE_SETTINGS=0 (kSoft default 1). Empty: no file at all.\n"
            "bc5::title_settings::Resolved ResolveConfig() {\n"
            "\tconst char* shared = std::getenv(\"KYTY_BC5_INPUT_CONFIG\");\n"
            "\tif (shared == nullptr || *shared == 0) return {};\n"
            "\tif (!bc5::env_rule::on(std::getenv(\"KYTY_BC5_TITLE_SETTINGS\"))) return {shared, shared, \"\", \"KYTY_BC5_TITLE_SETTINGS off: the shared file\"};\n"
            "\tnamespace ts = bc5::title_settings;\n"
            "\treturn ts::Resolve(ts::TitlesRoot(std::getenv(\"KYTY_BC5_MENU_DIR\"), shared), HostInputTitleId(), shared);\n"
            "}\n",
        ),
        (
            '\t\tif (const char* path = std::getenv("KYTY_BC5_INPUT_CONFIG"); path != nullptr && *path != 0) {\n'
            "\t\t\tg_config_path = path;\n",
            "\t\tif (const auto where = ResolveConfig(); !where.config.empty()) { // exp 0435\n"
            "\t\t\tg_config_path = where.config;\n"
            "\t\t\tg_title_dir   = where.title_dir;\n"
            "\t\t\tg_save_path   = where.save;\n"
            '\t\t\tstd::fprintf(stderr, "Title settings (exp 0435): %s: %s\\n", HostInputTitleId().c_str(), where.note.c_str());\n',
        ),
        (
            "\t\tif (map->Fullscreen() >= 0) WindowSetFullscreen(map->Fullscreen() == 1);\n\t\tg_map = std::move(map);\n",
            "\t\tif (map->Fullscreen() >= 0) WindowSetFullscreen(map->Fullscreen() == 1);\n"
            "\t\t// exp 0435: the mode the title's window last changed to wins over Fullscreen= and --fullscreen.\n"
            "\t\tif (const int mode = bc5::title_settings::ReadWindowMode(g_title_dir); mode >= 0) WindowRestoreFullscreen(mode == 1);\n"
            "\t\tg_map = std::move(map);\n",
        ),
        (
            "\tMap();\n\treturn g_config_path;\n}\n",
            "\tMap();\n\treturn g_save_path; // exp 0435: a title's own file; never the shared one for a title (top, 2026-11-19)\n}\n",
        ),
        (
            "std::vector<std::string> HostInputStatements() {\n"
            "\tstd::lock_guard<std::mutex> lock(g_input_mutex);\n"
            "\treturn Map().Statements();\n"
            "}\n",
            "std::vector<std::string> HostInputStatements() {\n"
            "\tstd::lock_guard<std::mutex> lock(g_input_mutex);\n"
            "\tauto lines = Map().Statements();\n"
            "\tif (!g_title_dir.empty()) { // exp 0435: the window's mode as it is now, so a Save or Apply never undoes an F11\n"
            "\t\tlines.erase(std::remove_if(lines.begin(), lines.end(),\n"
            "\t\t                           [](const std::string& l) { return l.rfind(\"Fullscreen=\", 0) == 0; }),\n"
            "\t\t            lines.end());\n"
            "\t\tlines.insert(lines.begin(), WindowIsFullscreen() ? \"Fullscreen=on\" : \"Fullscreen=off\");\n"
            "\t}\n"
            "\treturn lines;\n"
            "}\n"
            "\n"
            "// Experiment 0435: the window thread, after the mode really changed (F11, the menu, the Video tab, a remembered mode).\n"
            "void HostInputRememberFullscreen(bool on) {\n"
            "\tstd::string dir;\n"
            "\t{\n"
            "\t\tstd::lock_guard<std::mutex> lock(g_input_mutex);\n"
            "\t\tdir = g_title_dir;\n"
            "\t}\n"
            "\tif (!dir.empty() && !bc5::title_settings::WriteWindowMode(dir, on)) {\n"
            '\t\tstd::fprintf(stderr, "Title settings (exp 0435): cannot write %s/window\\n", dir.c_str());\n'
            "\t}\n"
            "}\n",
        ),
        (
            '\tconst char* path = std::getenv("KYTY_BC5_INPUT_CONFIG");\n'
            "\tif (path == nullptr || *path == 0) {\n"
            "\t\treturn -1;\n"
            "\t}\n"
            "\tstd::string error;\n"
            "\tconst auto  lines = ReadConfigLines(path, &error);\n",
            "\tconst std::string path = ResolveConfig().config; // exp 0435: the title's file when it has one\n"
            "\tif (path.empty()) {\n"
            "\t\treturn -1;\n"
            "\t}\n"
            "\tstd::string error;\n"
            "\tconst auto  lines = ReadConfigLines(path, &error);\n",
        ),
    ],
    "src/graphics/presentation/window/hostInput.h": [
        (
            "void HostInputReleaseAll();\n",
            "void HostInputReleaseAll();\n"
            "// Experiment 0435: the window's mode changed; the title's store (<menu dir>/titles/<TITLE_ID>/window) keeps it.\n"
            "void HostInputRememberFullscreen(bool on);\n",
        ),
    ],
    "src/graphics/presentation/window.h": [
        (
            "bool WindowIsFullscreen();\n",
            "bool WindowIsFullscreen();\n"
            "// Experiment 0435: the title's remembered mode; unlike WindowSetFullscreen it also wins over --fullscreen.\n"
            "void WindowRestoreFullscreen(bool on);\n",
        ),
    ],
    "src/graphics/presentation/window/window.cpp": [
        (
            "std::atomic<int>               g_fullscreen_pending {-1}; // BC5: asked for before the window existed\n",
            "std::atomic<int>               g_fullscreen_pending {-1}; // BC5: asked for before the window existed\n"
            "std::atomic<bool>              g_fullscreen_remembered {false}; // exp 0435: the pending mode is the title's own\n"
            "\n"
            "// Before the window exists: a remembered mode decides (exp 0435); else --fullscreen or a Fullscreen=on line.\n"
            "bool FullscreenBeforeWindow() {\n"
            "\tconst int want = g_fullscreen_pending.load();\n"
            "\tif (g_fullscreen_remembered.load() && want >= 0) return want == 1;\n"
            "\treturn Config::FullscreenEnabled() || want == 1;\n"
            "}\n",
        ),
        (
            "\t\tif (SDL_SetWindowFullscreen(window, want == 1 ? SDL_WINDOW_FULLSCREEN_DESKTOP : 0) != 0) {\n"
            '\t\t\tLOGF("Fullscreen %s: %s\\n", want == 1 ? "on" : "off", SDL_GetError());\n'
            "\t\t}\n",
            "\t\tif (SDL_SetWindowFullscreen(window, want == 1 ? SDL_WINDOW_FULLSCREEN_DESKTOP : 0) != 0) {\n"
            '\t\t\tLOGF("Fullscreen %s: %s\\n", want == 1 ? "on" : "off", SDL_GetError());\n'
            "\t\t} else {\n"
            "\t\t\tHostInputRememberFullscreen(want == 1); // exp 0435: the title starts in this mode next time\n"
            "\t\t}\n",
        ),
        (
            "\tconst bool fullscreen = Config::FullscreenEnabled() || g_fullscreen_pending.load() == 1; // BC5: or Fullscreen=on\n",
            "\tconst bool fullscreen = FullscreenBeforeWindow(); // BC5: or Fullscreen=on; exp 0435: the remembered mode first\n",
        ),
        (
            "\t\treturn Config::FullscreenEnabled() || g_fullscreen_pending.load() == 1;\n",
            "\t\treturn FullscreenBeforeWindow(); // exp 0435\n",
        ),
        (
            "void WindowSetPaused(bool on) {\n",
            "void WindowRestoreFullscreen(bool on) { // exp 0435\n"
            "\tg_fullscreen_remembered.store(true);\n"
            "\tWindowSetFullscreen(on);\n"
            "}\n"
            "\n"
            "void WindowSetPaused(bool on) {\n",
        ),
    ],
    "src/bc5/switch_defaults.hpp": [
        (
            '    {"BC5_GC_MODE", "direct"},\n',
            '    {"BC5_GC_MODE", "direct"},\n'
            "    // exp 0435 (the maintainer, 2026-11-19): each title keeps its own input.cfg and window mode under\n"
            "    // <menu dir>/titles/<TITLE_ID>/ (hostInput.cpp); KYTY_BC5_TITLE_SETTINGS=0: the one shared file as before.\n"
            '    {"KYTY_BC5_TITLE_SETTINGS", "1"},\n',
        ),
    ],
}

out = {}
bad = 0
for rel, edits in EDITS.items():
    p = tree / rel
    data = p.read_bytes().decode("latin-1")  # byte-preserving; the anchors are ASCII
    lines = data.split("\n")[:-1]
    crlf = sum(1 for l in lines if l.endswith("\r"))
    if crlf not in (0, len(lines)):
        print(f"FAIL {rel}: mixed line endings ({crlf} of {len(lines)} CRLF)")
        bad += 1
        continue
    eol = "\r\n" if crlf else "\n"  # window.cpp is CRLF upstream: the edits follow the file
    for i, (old, new) in enumerate(edits):
        old, new = old.replace("\n", eol), new.replace("\n", eol)
        n = data.count(old)
        if n != 1:
            print(f"FAIL {rel} edit {i + 1}: anchor found {n} times")
            bad += 1
            continue
        data = data.replace(old, new)
    out[p] = data
if bad:
    print(f"{bad} problem(s): nothing written")
    sys.exit(1)
for p, data in out.items():
    p.write_bytes(data.encode("latin-1"))
dst = tree / "src/bc5/title_settings.hpp"
dst.write_bytes(header.read_bytes())
print(f"applied: {len(out)} files edited, {dst} written")
