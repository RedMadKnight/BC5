#!/usr/bin/env python3
"""BC5 experiment 0419, step 3: ONE reading rule. Fourteen words were on at any value, "=0" and an empty value
included (`std::getenv(NAME) != nullptr`), and two more read "=0" as on. After this script each of them is off when
unset, empty or "0", as every other switch of the patch (bc5::env_on, or the new src/bc5/env_rule.hpp for the units
that have no such helper). Nothing else changes: with the word unset, or set to the value a launcher uses today
(1, a list, all, dcb), each read gives what it gave.
NOT changed here: BC5_DIRECT_SHADOW_LABELS, read in backend/src/direct.cpp (a change of the shared backend archive).
usage: mkrule0419.py <tree root (candidate B, patch 27b6416f)>   (edits in place; each anchor must occur exactly once)"""
import sys

root = sys.argv[1]
HDR = """// SPDX-License-Identifier: GPL-2.0-only
// Experiment 0419: the one reading rule of a BC5 switch. Off: unset, empty, or exactly "0". Anything else: on.
#pragma once

namespace bc5::env_rule {
inline bool on(const char* e) {
	return e != nullptr && e[0] != 0 && !(e[0] == '0' && e[1] == 0);
}
} // namespace bc5::env_rule
"""
EDITS = {
    "src/libs/bc5LleAgc.cpp": [
        ('std::getenv("BC5_DIRECT_ALIASES") == nullptr || guard0412_split();', '!bc5::env_on(std::getenv("BC5_DIRECT_ALIASES")) || guard0412_split();'),
        ('static const bool on = std::getenv("BC5_DIRECT_ALIASES") != nullptr;', 'static const bool on = bc5::env_on(std::getenv("BC5_DIRECT_ALIASES")); // exp 0419: "=0" and empty are off'),
        ('const bool amm_prt = std::getenv("BC5_DIRECT_AMM_PRT") != nullptr;', 'const bool amm_prt = bc5::env_on(std::getenv("BC5_DIRECT_AMM_PRT")); // exp 0419: "=0" is off;'),
        ('static const bool dma_sync = std::getenv("BC5_DIRECT_DMA_SYNC") != nullptr;', 'static const bool dma_sync = bc5::env_on(std::getenv("BC5_DIRECT_DMA_SYNC")); // exp 0419: "=0" is off'),
        ('static const bool gpu_check = std::getenv("BC5_DIRECT_GPU_CHECK") != nullptr;', 'static const bool gpu_check = bc5::env_on(std::getenv("BC5_DIRECT_GPU_CHECK")); // exp 0419: "=0" is off'),
        ('mec_on     = std::getenv("BC5_DIRECT_MEC_INDIRECT") != nullptr;', 'mec_on     = bc5::env_on(std::getenv("BC5_DIRECT_MEC_INDIRECT")); // exp 0419: "=0" is off'),
        ('static const bool remember_unmapped = std::getenv("BC5_DIRECT_REMEMBER_UNMAPPED") != nullptr;', 'static const bool remember_unmapped = bc5::env_on(std::getenv("BC5_DIRECT_REMEMBER_UNMAPPED")); // exp 0419: "=0" is off'),
        ('static const bool defer = std::getenv("BC5_DIRECT_FLIP_DEFER") != nullptr && Bc5Gc::Direct::async_on();', 'static const bool defer = bc5::env_on(std::getenv("BC5_DIRECT_FLIP_DEFER")) && Bc5Gc::Direct::async_on(); // exp 0419: "=0" is off'),
        ('static const bool second = std::getenv("BC5_DIRECT_OFFCHIP_SECOND") != nullptr;', 'static const bool second = bc5::env_on(std::getenv("BC5_DIRECT_OFFCHIP_SECOND")); // exp 0419: "=0" is off'),
        ('\t\tconst char* e = std::getenv("BC5_DIRECT_CROSS_RING_WAITS");\n\t\tif (e == nullptr) return 0;\n', '\t\tconst char* e = std::getenv("BC5_DIRECT_CROSS_RING_WAITS");\n\t\tif (!bc5::env_on(e)) return 0; // exp 0419: "=0" and empty are off\n'),
        ('\tconst char* e = std::getenv("BC5_DIRECT_RING_DEPS");\n\tif (e == nullptr) return 0;\n', '\tconst char* e = std::getenv("BC5_DIRECT_RING_DEPS");\n\tif (!bc5::env_on(e)) return 0; // exp 0419: "=0" and empty are off\n'),
    ],
    "src/libs/libAmpr.cpp": [
        ('static const bool sync = std::getenv("KYTY_BC5_APR_SYNC") != nullptr;', 'static const bool sync = bc5::env_rule::on(std::getenv("KYTY_BC5_APR_SYNC")); // exp 0419: "=0" is off'),
    ],
    "src/libs/audio.cpp": [
        ('port->pad_want = std::getenv("KYTY_BC5_NO_PAD_AUDIO") == nullptr &&', 'port->pad_want = !bc5::env_rule::on(std::getenv("KYTY_BC5_NO_PAD_AUDIO")) && /* exp 0419: "=0" is off */'),
        ('if (type != AUDIO_OUT_PORT_TYPE_VIBRATION || std::getenv("KYTY_BC5_NO_PAD_AUDIO") == nullptr) {', 'if (type != AUDIO_OUT_PORT_TYPE_VIBRATION || !bc5::env_rule::on(std::getenv("KYTY_BC5_NO_PAD_AUDIO"))) { // exp 0419'),
    ],
    "src/graphics/presentation/window/window.cpp": [
        ('static const bool on = std::getenv("KYTY_BC5_PAUSE_ON_BACKGROUND") != nullptr;', 'static const bool on = bc5::env_rule::on(std::getenv("KYTY_BC5_PAUSE_ON_BACKGROUND")); // exp 0419: "=0" is off'),
    ],
    "src/graphics/presentation/settingsOverlay.cpp": [
        ('std::atomic<bool>     g_active {std::getenv("KYTY_BC5_SETTINGS_OPEN") != nullptr};', 'std::atomic<bool>     g_active {bc5::env_rule::on(std::getenv("KYTY_BC5_SETTINGS_OPEN"))}; // exp 0419: "=0" is off'),
    ],
}
INC = '#include "bc5/env_rule.hpp" // exp 0419: the one reading rule\n'
n = 0
for rel, edits in EDITS.items():
    p = root + "/" + rel
    s = open(p, encoding="utf-8", newline="").read()
    assert "exp 0419" not in s, rel
    crlf = "\r\n" in s  # window.cpp is upstream's, with CRLF: every file is written back with its own line ends
    for old, new in edits:
        assert s.count(old) == 1, (rel, old[:60], s.count(old))
        s = s.replace(old, new)
        n += 1
    if "bc5::env_rule::on(" in s:
        i = s.index("#include ")
        s = s[:i] + (INC.replace("\n", "\r\n") if crlf else INC) + s[i:]
    open(p, "w", encoding="utf-8", newline="").write(s)
open(root + "/src/bc5/env_rule.hpp", "w", encoding="utf-8", newline="\n").write(HDR)
print("rule: %d read sites, 15 words; src/bc5/env_rule.hpp added" % n)
