"""Exp 0413: the switch defaults, one commit per audit item. Edits the replay tree (step 52), regenerates patch 0001
after each item and commits it in the integration worktree."""
import os
import subprocess
import sys

TREE, REPO, WORK = sys.argv[1], sys.argv[2], sys.argv[3]
PATCH = os.path.join(REPO, "backend", "kytyplus-patches", "0001-bc5-lle-agc.patch")
HDR = os.path.join(TREE, "src", "bc5", "switch_defaults.hpp")
MAIN = os.path.join(TREE, "src", "main.cpp")

# (audit row, title, [(name, value)], note) in the audit's order (experiments/0413-np-session-v2-shared/audit-unintegrated.md)
ITEMS = [
    ("A2", "acb state restore (exp 0381, 0401 series c)", [("BC5_DIRECT_ACB_STATE_RESTORE", "1")],
     "3 of 3 starts clean with it, 3 of 3 faulted without (F685); on in every play since 11-03"),
    ("A3", "pthread rwlock prefer-reader", [("KYTY_BC5_PTHREAD_FIXES", "1")], "CPU 10/10; on daily since 11-04"),
    ("A4", "SaveData mount result, event callback, mtime sort",
     [("KYTY_BC5_SAVEDATA_FIXES", "1"), ("KYTY_BC5_SAVEDATA_EVENT_CB", "1"), ("KYTY_BC5_SAVEDATA_SORT", "1")],
     "CPU 20/33/20; on daily since 11-04"),
    ("A5", "AudioOut2 fixes, set and room only", [("KYTY_BC5_AUDIO_FIXES", "set,room")],
     "=1 would also take the blocking push and silences the haptics port; set,room passed the replug check"),
    ("A6", "AMPR WaitOnAddress/Counter NIDs (PRT and extra AMM commands stay off: a cost on every map, no user)",
     [("KYTY_BC5_AMPR_WAITS", "1")], "CPU 317/63; swaits clean"),
    ("A7", "VideoOutGetOutputStatus", [("KYTY_BC5_VIDEOOUT_STATUS", "1")], "CPU 27/27; on daily since 11-04"),
    ("A8", "equeue and mmap shim fixes", [("KYTY_BC5_EQUEUE_FIXES", "1"), ("KYTY_BC5_MMAP_SHIM_FIXES", "1")],
     "CPU 21/18; on daily since 11-04"),
    ("A9", "soft-CP fixes (the rewind and drop catchers stay off)",
     [("BC5_R3_MEMSEM_SIGNAL", "1"), ("BC5_R3_SUBMIT_EOP_EVENT", "1"), ("BC5_R3_COND_WRITE", "1"),
      ("BC5_R3_WAIT_IDLE", "1"), ("BC5_R3_TS_100MHZ", "1")], "CPU 72/68; tgpu clean; on daily since 11-04"),
    ("A11", "TLS stub fixes", [("KYTY_BC5_TLS_FIXES", "1")],
     "CPU 19/19, 15-min route clean; ASTRO BOT start still to be run before the swap is kept"),
    ("A12", "thread sync and semaphores", [("KYTY_BC5_THREAD_SYNC_FIXES", "1"), ("KYTY_BC5_SEMA_FIXES", "1")],
     "CPU 9/9; on daily since 11-04"),
    ("A13", "memory-call fixes",
     [("BC5_R3_MPROTECT_GAPS", "1"), ("BC5_R3_NULL_ARGS", "1"), ("BC5_R3_RELEASE_HOLES", "1"),
      ("BC5_R3_MUNMAP_HOLES", "1"), ("BC5_R3_FLEX_HINT", "1"), ("BC5_R3_DMQ_END", "1"), ("BC5_R3_EXEC_EINVAL", "1"),
      ("BC5_R3_QUERY_SIZE", "1")], "CPU 8/8; on daily since 11-04"),
    ("A14", "file system and POSIX returns", [("KYTY_BC5_FS_FIXES", "1"), ("KYTY_BC5_POSIX_RET_FIXES", "1")],
     "CPU 23/19; on daily since 11-04"),
    ("A15", "SaveData memory, Http2, scePadOpenExt",
     [("KYTY_BC5_SAVEDATA_MEMORY_FIXES", "1"), ("KYTY_BC5_SAVEDATA_DELETE_BUSY", "1"),
      ("KYTY_BC5_SAVEDATA_ALIASES", "1"), ("KYTY_BC5_HTTP2_FIXES", "1"), ("KYTY_BC5_PAD_OPEN_EXT", "1")],
     "CPU 21/21; on daily since 11-04"),
    ("A16", "Json2, Ult, UserService, SystemService",
     [("KYTY_BC5_JSON2_FIXES", "1"), ("KYTY_BC5_ULT_FIXES", "1"), ("KYTY_BC5_USERSERVICE_VALUES", "1"),
      ("KYTY_BC5_SYSTEMSERVICE_VALUES", "1"), ("KYTY_BC5_SYSTEMSERVICE_PARAMS_7_1000", "1")],
     "CPU 38/22; on daily since 11-04"),
    ("A17", "AudioOut/AudioIn checks, Ngs2 rack",
     [("KYTY_BC5_AUDIOOUT_CHECKS", "1"), ("KYTY_BC5_AUDIOIN_CHECKS", "1"), ("KYTY_BC5_NGS2_RACK_FIX", "1")],
     "CPU 30/20; on daily since 11-04"),
    ("A18", "firmware behaviour: net and system", [("KYTY_BC5_FW_NET", "1")], "CPU 33/33; on daily since 11-04"),
    ("A19", "firmware behaviour: audio", [("KYTY_BC5_FW_AUDIO", "1")], "CPU 50/28; on daily since 11-04"),
    ("A20", "JIT shared memory, kernel notify", [("KYTY_BC5_JIT_SHM", "1"), ("KYTY_BC5_FW_KERNEL", "1")],
     "CPU 8/3; on daily since 11-04"),
    ("A21", "firmware behaviour: pad", [("KYTY_BC5_FW_PAD", "1")], "CPU 71/4; on daily since 11-04"),
    ("A22", "dead tables, batch 1",
     [("KYTY_BC5_LOAD_ZLIB", "1"), ("KYTY_BC5_LOAD_JPEG", "1"), ("KYTY_BC5_LOAD_IME", "1"),
      ("KYTY_BC5_LOAD_NPCOMMON", "1"), ("KYTY_BC5_LOAD_NPMANAGER", "1"), ("KYTY_BC5_LOAD_NPTROPHY", "1")],
     "CPU 108/165/9; on daily since 11-04"),
    ("B16", "quiet journal and inherit-map caps", [("BC5_DIRECT_JOURNAL_QUIET", "1")],
     "journal 24 MB instead of 385 MB; on his shortcut since e8/e9"),
    ("C1", "graphics event pending cap", [("KYTY_BC5_EVENT_PENDING_CAP", "64")],
     "ASTRO BOT's host leak 217.8 -> 0.1 MiB/min (0412 section 11); in fast7/lean7"),
    ("C2", "fast AMM range query", [("KYTY_BC5_RANGES_FAST", "1")],
     "same answers as the old lookup (CPU test memfast0412.cpp); about +30 % frames in the loads"),
    ("C3", "sorted physical-mapping table", [("KYTY_BC5_PHYSMAP_SORTED", "1")],
     "same answers (CPU test physmap0412.cpp); with C2 about +47 % frames in the loads"),
]

HEAD = """// SPDX-License-Identifier: GPL-2.0-only
// Experiment 0413: the defaults of switches that went from the private test builds (exps 0401, 0405, 0409, 0412) into
// both shared builds. Each row is applied at process start with setenv(name, value, 0), before any static initializer
// reads a switch, so a value set in the environment always wins and NAME=0 restores the old behaviour of that row.
// KYTY_BC5_SWITCH_DEFAULTS=0 skips the whole table (the code then behaves as in the private builds with nothing set).
// One audit row of experiments/0413-np-session-v2-shared/audit-unintegrated.md per block, in the audit's order.
// Left out on purpose (the top session's rules, 2026-11-12): the zero skip and its poll, the orphan release, split and
// forget (launcher only); CP_COHER_START_DELAY (never A/B'd; the second title's launcher keeps it); NOGPU_UNPIN,
// SET_PREDICATION, the catchers and journals (off).
#pragma once

#include <cstdlib>
#include <cstring>

namespace bc5::switch_defaults {

struct Default {
	const char* name;
	const char* value;
};

inline constexpr Default kDefaults[] = {
"""
TAIL = """    {nullptr, nullptr}};

inline void Apply() {
	const char* all = std::getenv("KYTY_BC5_SWITCH_DEFAULTS");
	if (all != nullptr && std::strcmp(all, "0") == 0) return;
	for (const Default* d = kDefaults; d->name != nullptr; d++) {
		setenv(d->name, d->value, 0);
	}
}

} // namespace bc5::switch_defaults
"""

HOOK = (b'#include "bc5/switch_defaults.hpp"\r\n'
        b"// BC5 (experiment 0413): the shared builds' switch defaults, set before any static initializer can read a switch\r\n"
        b"// (priority 101, as the lean build's environment cleanup below; the two touch different names).\r\n"
        b"__attribute__((constructor(101))) static void Bc5SwitchDefaults() {\r\n"
        b"\tbc5::switch_defaults::Apply();\r\n"
        b"}\r\n\r\n")
ANCHOR = b"#ifdef BC5_LEAN\r\n#include <cstdlib>\r\n"


def write_header(n):
    rows = ""
    for row, title, sw, _ in ITEMS[:n]:
        rows += f"    // {row}: {title}\n"
        for name, value in sw:
            rows += f'    {{"{name}", "{value}"}},\n'
    open(HDR, "w", encoding="utf-8", newline="\n").write(HEAD + rows + TAIL)


def git(*a, cwd):
    return subprocess.run(["git", "-c", "core.autocrlf=false", *a], cwd=cwd, check=True, capture_output=True)


def commit(msg):
    git("add", "-A", cwd=TREE)
    d = git("diff", "--cached", "--no-color", "base", cwd=TREE).stdout
    open(PATCH, "wb").write(d)
    mf = os.path.join(WORK, "dmsg.txt")
    open(mf, "w", encoding="utf-8", newline="\n").write(msg + "\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\n")
    git("add", PATCH, cwd=REPO)
    git("commit", "-q", "-F", mf, cwd=REPO)


def main():
    m = open(MAIN, "rb").read()
    assert m.count(ANCHOR) == 1 and b"switch_defaults" not in m
    open(MAIN, "wb").write(m.replace(ANCHOR, HOOK + ANCHOR))
    write_header(0)
    commit("int(0413): the switch-defaults table (empty) and its constructor in main.cpp\n\n"
           "src/bc5/switch_defaults.hpp holds one row per switch that the shared builds turn on by default; main.cpp applies it\n"
           "at priority 101 with setenv(name, value, 0). Rows follow in one commit per audit item; KYTY_BC5_SWITCH_DEFAULTS=0\n"
           "skips them all.")
    print("mechanism committed")
    for i, (row, title, sw, note) in enumerate(ITEMS, 1):
        write_header(i)
        names = ", ".join(f"{n}={v}" for n, v in sw)
        commit(f"int(0413): default on, audit {row}: {title}\n\n{names}\nEvidence: {note}.\nOld behaviour: set each to 0.")
        print(row, "committed")


if __name__ == "__main__":
    main()
