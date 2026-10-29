#!/usr/bin/env python3
# BC5 experiment 0380 (F611): a private copy of the shared tree's src/loader/runtimeLinker.cpp (96e03695) with one
# counted edit: after the access-violation stack trace, BC5_CRASH_FRAMES=1 (default off) dumps every frame of the
# saved-rbp chain: 0x100 bytes below each saved rbp and its two qwords above (the frame's locals and the callee-saved
# registers its callee pushed), then 8 qwords at each value in that window that is an aligned, readable address (at
# most 24 per frame). CPU only, inside the exception handler, read through IsReadableRange; nothing is written to guest
# memory. The 23:15 crash's descriptor sat in a saved local one frame up (F610); this names it in the next crash's log.
# usage: python3 mk-crash0380.py <shared runtimeLinker.cpp> <private runtimeLinker.cpp>
import sys

src, out = sys.argv[1:3]
t = open(src, encoding="utf-8").read()
anchor = "\t\t\t\t                         .c_str()));\n\t\t\t}\n\t\t}\n\n\t\tauto dump_guest_qwords"
assert t.count(anchor) == 1, t.count(anchor)
block = r'''			// Experiment 0380 (F611): BC5_CRASH_FRAMES=1 dumps each frame of the saved-rbp chain and the structs its
			// locals point to (CPU only, read through IsReadableRange; default off).
			if (std::getenv("BC5_CRASH_FRAMES") != nullptr) {
				uint64_t fp = info->rbp;
				for (int f = 0; f < 8 && fp >= 0x100 && IsReadableRange(fp - 0x100, 0x110); f++) {
					const auto* q = reinterpret_cast<const uint64_t*>(fp - 0x100);
					for (int r = 0; r < 34; r += 2) {
						Bc5CrashLog("frame %d rbp %016" PRIx64 " %+5d: %016" PRIx64 " %016" PRIx64 "\n", f, fp, r * 8 - 0x100, q[r], q[r + 1]);
					}
					int shown = 0;
					for (int r = 0; r < 34 && shown < 24; r++) {
						const uint64_t v = q[r];
						if (v < 0x10000 || v >= 0x800000000000ull || (v & 7u) != 0 || !IsReadableRange(v, 64)) continue;
						const auto* p = reinterpret_cast<const uint64_t*>(v);
						Bc5CrashLog("frame %d %+5d -> %016" PRIx64 ": %016" PRIx64 " %016" PRIx64 " %016" PRIx64 " %016" PRIx64 " %016" PRIx64 " %016" PRIx64 " %016" PRIx64 " %016" PRIx64 "\n",
						            f, r * 8 - 0x100, v, p[0], p[1], p[2], p[3], p[4], p[5], p[6], p[7]);
						shown++;
					}
					const uint64_t next = q[0x100 / 8];
					if (next <= fp) break;
					fp = next;
				}
			}
'''
t = t.replace(anchor, "\t\t\t\t                         .c_str()));\n\t\t\t}\n" + block + "\t\t}\n\n\t\tauto dump_guest_qwords")
assert t.count("BC5_CRASH_FRAMES") == 2
if "#include <cstdlib>" not in t:
    t = t.replace("#include <cinttypes>\n", "#include <cinttypes>\n#include <cstdlib> // experiment 0380\n", 1)
open(out, "w", encoding="utf-8", newline="\n").write(t)
print(f"{out} written")
