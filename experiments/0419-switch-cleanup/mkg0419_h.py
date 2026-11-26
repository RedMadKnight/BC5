#!/usr/bin/env python3
"""BC5 experiment 0419, step h (the test build T): two live timing words become the constants they always had.
The top session's decision of 2026-11-14 inside the maintainer's approval of the proposals:
  BC5_DIRECT_CHAIN_HOLD_US  -> constant 2,000 us (never varied in any run)
  BC5_DIRECT_DCB_WAIT_MS    -> constant 8 ms, as today (the measurements at 100 ms contradict each other: F264/F265,
                               F271, F285; no new arm is opened)
Behaviour does not change: both were unset in every launcher and shortcut.
usage: mkg0419_h.py <src/libs/bc5LleAgc.cpp>"""
import sys
from ed0419g import File

f = File(sys.argv[1])
f.sub('\tstatic const uint64_t v = (std::getenv("BC5_DIRECT_CHAIN_HOLD_US") != nullptr ? std::strtoull(std::getenv("BC5_DIRECT_CHAIN_HOLD_US"), nullptr, 10) : 2000ull) * 1000ull;\n',
      '\tstatic const uint64_t v = 2000ull * 1000ull; /* exp 0419: a constant (was BC5_DIRECT_CHAIN_HOLD_US, never varied) */\n')
f.sub('// BC5_DIRECT_CHAIN_HOLD_US (default 2000) and whose owner', '// 2000 us (exp 0419: a constant) and whose owner')
f.sub('for up to %" PRIu64 " us (BC5_DIRECT_CHAIN_HOLD_US)\\n"', 'for up to %" PRIu64 " us\\n"')
f.sub('\t\t\t\t\t// Run 124 (BC5_DIRECT_DCB_WAIT_MS, default 8): a wait',
      '\t\t\t\t\t// Run 124 (8 ms; exp 0419: a constant, was BC5_DIRECT_DCB_WAIT_MS): a wait')
f.sub('\t\t\t\t\tstatic const uint64_t dcb_ns = (std::getenv("BC5_DIRECT_DCB_WAIT_MS") ? std::strtoull(std::getenv("BC5_DIRECT_DCB_WAIT_MS"), nullptr, 10) : 8u) * 1\'000\'000ull;\n',
      '\t\t\t\t\tstatic constexpr uint64_t dcb_ns = 8ull * 1\'000\'000ull;\n')
f.gone('"BC5_DIRECT_CHAIN_HOLD_US"', '"BC5_DIRECT_DCB_WAIT_MS"', "(BC5_DIRECT_CHAIN_HOLD_US)")
f.save()
