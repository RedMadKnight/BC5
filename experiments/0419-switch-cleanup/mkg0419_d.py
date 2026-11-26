#!/usr/bin/env python3
"""BC5 experiment 0419, candidate G, step d (the main unit and agc.cpp), approved by the maintainer on 2026-11-13:
  BC5_DIRECT_TF_DEFAULT       deleted with its code: the host's default tessellation-factor ring (exp 0189, "is not
                              needed by this title"). With it goes BC5_DIRECT_HS_OFFCHIP, which was read by
                              hs_offchip_force() only inside TF_DEFAULT's block (one more word than the list names).
                              VGT_HS_OFFCHIP_PARAM is still written from the title's own value (exp 0418's row and the
                              /dev/gc ring path); the HLE GraphicsDriverGetTFRing answers what the title set, else 0.
  BC5_DIRECT_PIECES_NO_CLEAR  deleted with its code (a mechanism test that "would not isolate CLEAR_STATE", F609).
  BC5_DIRECT_HEAP_GUARDS      constant on, no option: the 2 MiB zero guard behind each eager heap of 32 MiB or more.
usage: mkg0419_d.py <src dir>"""
import sys
from ed0419g import File

src = sys.argv[1]
f = File(src + "/libs/bc5LleAgc.cpp")

# TF_DEFAULT: the switch, the allocation, the HLE answer
f.cut("// Experiment 0189 (behaviour, off by default): BC5_DIRECT_TF_DEFAULT=1 gives the geometry engine a\n",
      "\t\tstd::fprintf(stderr, \"bc5-direct: default TF ring (exp 0189): %s at %p, 0x%\" PRIx64 \" bytes, ring size 0x%x (%d)\\n\", "
      "r == 0 ? \"ok\" : \"FAILED\", a, kTfDefaultBytes, kTfDefaultSize, r);\n\t});\n}\n")
f.cut("// For the HLE GraphicsDriverGetTFRing (agc.cpp): the host's default ring, 0 when BC5_DIRECT_TF_DEFAULT is off.\n",
      "\tif (size != nullptr) *size = va != 0 ? kTfDefaultSize : 0;\n\treturn va;\n}\n")
# the prefix: the comment block of the two exp 0189 switches, hs_offchip_force, the default-ring branch
f.cut("// Experiment 0189, behaviour switches, all off by default (docs/ports/related-projects-review.md section 7):\n"
      "// - BC5_DIRECT_TF_DEFAULT=1:",
      "//   dwords; RADV on the BC-250 sizes its offchip ring for 96 workgroups of 32 KiB, i.e. 0x5f).\n",
      "// Experiment 0189, a behaviour switch, off by default (docs/ports/related-projects-review.md section 7):\n")
f.cut("static bool hs_offchip_force(uint32_t* v) {\n", "\t*v = static_cast<uint32_t>(f);\n\treturn true;\n}\n")
f.sub("\tbool       host_default = false, gc_ring = false;\n", "\tbool       gc_ring      = false;\n")
f.cut("\tif ((base == 0 || size == 0) && tf_default_on()) { // experiment 0189\n",
      "\t\t\tjournal(\"tf ring (exp 0189): default ring at 0x%\" PRIx64 \" not mapped yet, not programmed\\n\", va);\n\t\t}\n\t}\n")
f.sub("\tif (host_default || gc_ring) {\n", "\tif (gc_ring) {\n")
f.sub("off_v, host_default ? \", host default ring\" : gc_ring ?", "off_v, gc_ring ?")
f.sub("// Experiment 0155 (diagnostic, BC5_DIRECT_PIECES_NO_CLEAR=1): a piece's prefix without its\n"
      "// CONTEXT_CONTROL and CLEAR_STATE (the first five dwords of Tracker::emit_prefix()).\n", "")
f.sub("\t\t\ttf_default_alloc(); // experiment 0189 (BC5_DIRECT_TF_DEFAULT=1; the driver's first request)\n", "")
f.gone("TF_DEFAULT", "tf_default", "kTfDefault", "hs_offchip_force", "BC5_DIRECT_HS_OFFCHIP\"", "host_default", "Bc5TfDefaultRing")

# PIECES_NO_CLEAR
f.sub("\tstatic const bool no_clear = bc5::env_on(std::getenv(\"BC5_DIRECT_PIECES_NO_CLEAR\"));\n"
      "\tif (no_clear && p.size() >= 5) p.erase(p.begin(), p.begin() + 5);\n", "")
f.gone("PIECES_NO_CLEAR", "no_clear")

# HEAP_GUARDS: always on
f.cut("\t// Experiment 0417: BC5_DIRECT_HEAP_GUARDS. =0 makes no guard",
      "\tif (!heap_guards) return; // nothing was ever put into g_scratch, so there is nothing to give back either\n",
      "\t// The 2 MiB zero guards behind the eager heaps (exp 0037) are always made: BC5_DIRECT_HEAP_GUARDS is gone (exp 0419, candidate G).\n")
f.gone("heap_guards", "getenv(\"BC5_DIRECT_HEAP_GUARDS\")")
f.save()

g = File(src + "/bc5/start_state.hpp")
g.sub("(3 dwords) and CLEAR_STATE (2 dwords), or at 0 when those were removed (BC5_DIRECT_PIECES_NO_CLEAR).",
      "(3 dwords) and CLEAR_STATE (2 dwords), or at 0 for a prefix without them.")
g.save()

f = File(src + "/libs/agc.cpp")
f.sub("extern \"C\" uint64_t Bc5TfDefaultRing(uint32_t* size);\n", "")
f.sub("\tif (b == 0 || s == 0) {\n\t\tb = Bc5TfDefaultRing(&s);\n\t}\n", "")
f.sub("what the title set, else the host's default ring (BC5_DIRECT_TF_DEFAULT=1,\n// bc5LleAgc.cpp).",
      "what the title set (the host's default ring of exp 0189 went in exp 0419).")
f.gone("Bc5TfDefaultRing", "TF_DEFAULT")
f.save()
