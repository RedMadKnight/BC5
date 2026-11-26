#!/usr/bin/env python3
"""BC5 experiment 0419, candidate G, step e: eight more approved deletes, FIRST PHASE ONLY: the option goes (the word is
read by nothing), the code behind it stays in the source, dead, for the phase that cuts it:
  BC5_GUARD_MLOCK, BC5_GUARD_PIN_CAP, BC5_GUARD_CAP_ACT, BC5_GUARD_CAP_NAMES   exp 0412's guardian (g412): its parser
      gets no value for them, so mlock = 0, cap = 0, cap_act = false;
  BC5_GUARD_MAP_RULE, BC5_GUARD_PRT_BG                                         exp 0412's mr412: rule() = 0, prt_bg() = false
      (K1r, default on, is the rule that replaced them);
  KYTY_BC5_AMM_PRT_CMDS, KYTY_BC5_AMM_EXTRA_CMDS                               libAmpr.cpp: both false (audit row A6).
Why not the code too, tonight: the guardian's code sits inside the block its own laptop test compiles
(G412_PURE_BEGIN..END, test0412.cpp, parse()'s nine arguments) and the unit cannot be compiled on the laptop; exp 0412
named what goes and what stays with MAP_RULE and PRT_BG, and that cut is better made with its test at hand.
usage: mkg0419_e.py <src dir>"""
import sys
from ed0419g import File

src = sys.argv[1]
f = File(src + "/libs/bc5LleAgc.cpp")
f.sub('    static const Cfg c = parse(std::getenv("BC5_GUARD_LEDGER"), std::getenv("BC5_GUARD_MLOCK"), nullptr, nullptr, /* exp 0419: option removed */\n'
      '                               nullptr, std::getenv("BC5_GUARD_PIN_CAP"), nullptr, /* exp 0419: option removed */\n'
      '                               std::getenv("BC5_GUARD_CAP_ACT"), std::getenv("BC5_GUARD_CAP_NAMES"));\n',
      '    // exp 0419: only the ledger still has a word; BC5_GUARD_MLOCK, _FILE, _PSI, _PIN_CAP, _APPLY_MIN_MS, _CAP_ACT and\n'
      '    // _CAP_NAMES are gone (candidates E/F and G), their code is dead until it is cut.\n'
      '    static const Cfg c = parse(std::getenv("BC5_GUARD_LEDGER"), nullptr, nullptr, nullptr, nullptr, nullptr, nullptr, nullptr, nullptr);\n')
f.sub('\t\tconst bool r = std::getenv("BC5_GUARD_PIN_CAP") != nullptr /* exp 0419: option removed */;\n',
      '\t\tconst bool r = false; /* exp 0419: BC5_DIRECT_ZERO_SKIP and BC5_GUARD_PIN_CAP are gone */\n')
f.sub('\tstatic const int v = env_digit("BC5_GUARD_MAP_RULE", 2);\n\treturn v;\n',
      '\treturn 0; /* exp 0419 (candidate G): BC5_GUARD_MAP_RULE is gone; K1r replaced it */\n')
f.sub('\tstatic const bool v = env_digit("BC5_GUARD_PRT_BG", 1) == 1 && rule() != 0;\n\treturn v;\n',
      '\treturn false; /* exp 0419 (candidate G): BC5_GUARD_PRT_BG is gone */\n')
f.gone('getenv("BC5_GUARD_MLOCK")', 'getenv("BC5_GUARD_PIN_CAP")', 'getenv("BC5_GUARD_CAP_ACT")', 'getenv("BC5_GUARD_CAP_NAMES")',
       'env_digit("BC5_GUARD_MAP_RULE"', 'env_digit("BC5_GUARD_PRT_BG"')
f.save()

f = File(src + "/libs/libAmpr.cpp")
f.sub('\tstatic const bool on = Bc5Exp0401Switch("KYTY_BC5_AMM_PRT_CMDS");\n\treturn on;\n',
      '\treturn false; /* exp 0419 (candidate G): KYTY_BC5_AMM_PRT_CMDS is gone (audit row A6); its commands are dead code */\n')
f.sub('\tstatic const bool on = Bc5Exp0401Switch("KYTY_BC5_AMM_EXTRA_CMDS");\n\treturn on;\n',
      '\treturn false; /* exp 0419 (candidate G): KYTY_BC5_AMM_EXTRA_CMDS is gone (audit row A6); its commands are dead code */\n')
f.gone('Switch("KYTY_BC5_AMM_PRT_CMDS")', 'Switch("KYTY_BC5_AMM_EXTRA_CMDS")')
f.save()
