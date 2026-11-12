"""Exp 0413: the defaults reach the process through its initial environment (one re-exec) instead of setenv."""
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import defaults as d  # noqa: E402

TREE, REPO, WORK = sys.argv[1], sys.argv[2], sys.argv[3]
d.TREE, d.REPO, d.WORK = TREE, REPO, WORK
d.PATCH = os.path.join(REPO, "backend", "kytyplus-patches", "0001-bc5-lle-agc.patch")
d.HDR = os.path.join(TREE, "src", "bc5", "switch_defaults.hpp")
d.MAIN = os.path.join(TREE, "src", "main.cpp")

d.HEAD = d.HEAD.replace(
    "// both shared builds. Each row is applied at process start with setenv(name, value, 0), before any static initializer\n"
    "// reads a switch, so a value set in the environment always wins and NAME=0 restores the old behaviour of that row.\n",
    "// both shared builds. A value set in the environment always wins and NAME=0 restores the old behaviour of that row.\n"
    "// The rows reach the process through its INITIAL environment: if any is missing, the priority-101 constructor runs\n"
    "// /proc/self/exe again, once, with the same arguments and the missing rows added (KYTY_BC5_SWITCH_DEFAULTS_EXEC=1 marks\n"
    "// the second start). Not setenv: in exp 0413 ASTRO BOT's start crashed at eboot+0x48f whenever the rows were added by\n"
    "// setenv (the environ array grown on the heap at start), and passed with the same rows in the initial environment, and\n"
    "// also with setenv plus 20 unrelated variables at start: a layout effect, not a row. If the exec fails, the process goes\n"
    "// on without the defaults and says so on stderr.\n")
assert "INITIAL environment" in d.HEAD
d.HEAD = d.HEAD.replace("#include <cstdlib>\n#include <cstring>\n",
                        "#include <cstdio>\n#include <cstdlib>\n#include <cstring>\n#include <string>\n#include <vector>\n\n#include <unistd.h>\n")
d.TAIL = """    {nullptr, nullptr}};

// The command line of this process, from /proc/self/cmdline (NUL-separated); empty on failure.
inline std::vector<std::string> OwnArgs() {
	std::vector<std::string> args;
	FILE*                    f = std::fopen("/proc/self/cmdline", "rb");
	if (f == nullptr) return args;
	std::string cur;
	for (int c = std::fgetc(f); c != EOF; c = std::fgetc(f)) {
		if (c == 0) {
			args.push_back(cur);
			cur.clear();
		} else {
			cur.push_back(static_cast<char>(c));
		}
	}
	std::fclose(f);
	if (!cur.empty()) args.push_back(cur);
	return args;
}

inline void Apply() {
	const char* all = std::getenv("KYTY_BC5_SWITCH_DEFAULTS");
	if (all != nullptr && std::strcmp(all, "0") == 0) return;
	if (std::getenv("KYTY_BC5_SWITCH_DEFAULTS_EXEC") != nullptr) return; // the second start: the rows are in the environment
	std::vector<std::string> add;
	for (const Default* d = kDefaults; d->name != nullptr; d++) {
		if (std::getenv(d->name) == nullptr) add.push_back(std::string(d->name) + "=" + d->value);
	}
	if (add.empty()) return;
	add.emplace_back("KYTY_BC5_SWITCH_DEFAULTS_EXEC=1");
	const std::vector<std::string> args = OwnArgs();
	if (args.empty()) {
		std::fprintf(stderr, "[bc5] switch defaults: no /proc/self/cmdline, going on without them\\n");
		return;
	}
	std::vector<char*> argv;
	for (const std::string& a: args) argv.push_back(const_cast<char*>(a.c_str()));
	argv.push_back(nullptr);
	std::vector<char*> envp;
	for (char** e = environ; e != nullptr && *e != nullptr; e++) envp.push_back(*e);
	for (const std::string& a: add) envp.push_back(const_cast<char*>(a.c_str()));
	envp.push_back(nullptr);
	execve("/proc/self/exe", argv.data(), envp.data());
	std::fprintf(stderr, "[bc5] switch defaults: the exec failed, going on without them\\n");
}

} // namespace bc5::switch_defaults
"""
keep = [it for it in d.ITEMS if it[0] not in ("A15", "A16", "A17", "A21", "A22")]
d.ITEMS = keep
d.write_header(len(keep))
d.commit("int(0413): the switch defaults reach the process through its initial environment (one re-exec), not setenv\n\n"
         "ASTRO BOT's start crashed (eboot+0x48f, a null out-pointer) with the rows added by setenv and passed with the same 55\n"
         "rows in the real environment (run e2env), with setenv minus 20 rows (e3env) and with setenv plus 20 dummy variables at\n"
         "start (e4dum): the crash follows the start's memory layout, not a row. The constructor now runs /proc/self/exe once\n"
         "more with the missing rows in its environment; KYTY_BC5_SWITCH_DEFAULTS_EXEC=1 marks the second start.")
print("committed")
