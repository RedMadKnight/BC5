#!/usr/bin/env python3
"""BC5 experiment 0401, series e4 (exp 0402 Top 10 item 10, sceVideoOutGetOutputStatus before buffer registration): the
`resolution` field of VideoOutGetOutputStatus behind the switch KYTY_BC5_VIDEOOUT_STATUS, on main's tree (KytyPlus f266548
+ patch 0001; src/graphics/presentation/videoOut.cpp md5 f848f5c6b81196e9722f3c7caf3984ec, 2,087 lines).
On (set, non-empty and not "0", F767's reading, read once): resolution 2, the UHD class, on every call before and after
buffer registration, whatever the port size: a PS5 on a 4K display with its resolution on Automatic. Before registration
that is sharpemu b1ec286's answer (GPL-2.0-or-later, src/SharpEmu.Libs/VideoOut/VideoOutExports.cs) and the console's as
AnyPS5 4f41f4c37 cites it (GPL-2.0-only, bfeeed4ef: a payload on a PS5, firmware 12.70); after registration it follows
AnyPS5 (the display's class, not the buffers'), where sharpemu takes the registered set's size: see vo0401-notes.md.
Off is today's path and today's answer (the class of the port size, --screen-width/height, default 1280x720: 1); the only
additions then are a count of the port's registered buffer sets and one stderr line at the first call,
"[bc5] exp 0401: videoout status off: ...". dynamicRange, refreshRate and flags are not touched (vo0401-notes.md).
Edits src/graphics/presentation/videoOut.cpp only; no header (vo0401.cpp declares the two functions it tests itself).
Each anchor must occur exactly once; a tree that has the edit already is refused. Also asserted, for the CPU test's
stand-in registration (vo0401.cpp): Impl::Init is the only writer of a port's size, and RegisterBuffers2 changes only the
port's sets. Prints "<md5>  <relpath>" for the output.
usage: mkvo0401.py <tree root in> <out dir>"""
import hashlib
import os
import re
import sys

REL = "src/graphics/presentation/videoOut.cpp"
MARK = b"KYTY_BC5_VIDEOOUT_STATUS"
MARK_FN = b"Bc5VideoOutStatus"

# ---- the switch, the answer and the comment block, just before VideoOutGetOutputStatus ------------------------------
FUNC_ANCHOR = b"KYTY_SYSV_ABI int VideoOutGetOutputStatus(int handle, VideoOutOutputStatus* status) {\n\tPRINT_NAME();\n"
BLOCK = b"""// ---- experiment 0401 series e4: sceVideoOutGetOutputStatus's resolution (exp 0402 Top 10 item 10), switch
// KYTY_BC5_VIDEOOUT_STATUS ----
// On (set, non-empty and not "0", read once): `resolution` is 2, the UHD class, on every call from the port's open to its
// close, before and after buffer registration, whatever the port size: the answer of a PS5 on a 4K display with its
// resolution on Automatic. Sources (their authors keep the copyright of the rule ported here):
//  - sharpemu (GPL-2.0-or-later), src/SharpEmu.Libs/VideoOut/VideoOutExports.cs at b1ec286
//    (b1ec2866575bf72ffcef92cd639c580bf5bf0c61, "[VideoOut] Report UHD output status before buffers are registered", #1125;
//    the same at 514d766): 2 on a Gen5 port while no buffer set is registered. From one title's behaviour (it read HD and
//    laid its viewport out for 4K over 1080p buffers), not from a console measurement.
//  - AnyPS5 (boykopovar/AnyPS5, GPL-2.0-only) at 4f41f4c37, core/libs/prx/libSceVideoOut/src/Output.cpp:22-30 and
//    src/VideoOutDriver.cpp:73-91, 558-570 (bfeeed4ef41228321f8e2664cfa93f7c9d9e19d6, 983a81d91): the class of the host
//    display's mode (>= 3840 wide or >= 2160 high: 2, else 1), independent of the registered buffers. Its commit and
//    docs/dev/debt/libSceVideoOut.md:27 cite a payload on a PS5 (firmware 12.70) with no buffer registered: 2 with the
//    console's resolution on Automatic on a 4K display, 1 with it set to 1080p.
//  - After registration the two disagree and neither is measured: sharpemu answers the class of the last registered (or
//    changed) set's size, AnyPS5 keeps the display's class (its tests/Flip.cpp:1221-1253 check that a flipped buffer does
//    not change it). This follows AnyPS5: what was measured is that the field reports the console's output setting,
//    which a buffer registration does not change.
// Off (unset, empty or "0"): today's answer, the class of the port size (Impl::Init, from --screen-width/height, default
// 1280x720: 1), before and after registration. On the box's 1920x1080 display (HANDOFF F67) that is AnyPS5's answer too.
// Not changed, reasons in experiments/0401-mesa-preamble-switches/vo0401-notes.md: dynamicRange 1 and flags 0 (this
// host's swapchain is SDR only; AnyPS5 e604020013 measured flags 0 even with HDR output on, where sharpemu sets bit 0) and
// refreshRate (each of the three reports its own vblank rate, which here follows --vblank-frequency).
// One stderr line at the first call, either way. GPL-2.0-only, as the rest of this file.
bool     Bc5VideoOutStatusOn();
uint32_t Bc5VideoOutStatusResolution(uint32_t today, uint32_t port_width, uint32_t port_height, int registered_sets);

bool Bc5VideoOutStatusOn() {
\tstatic const bool on = [] {
\t\tconst char* e = std::getenv("KYTY_BC5_VIDEOOUT_STATUS");
\t\treturn e != nullptr && e[0] != '\\0' && std::strcmp(e, "0") != 0;
\t}();
\treturn on;
}

// today: the answer of today's code (the class of the port size). Off returns it as it is; on returns the UHD class.
uint32_t Bc5VideoOutStatusResolution(uint32_t today, uint32_t port_width, uint32_t port_height, int registered_sets) {
\tconstexpr uint32_t bc5_resolution_uhd = 2; // AnyPS5 VIDEO_OUT_RESOLUTION_2160P; sharpemu's class of 3840x2160
\tconst bool         on                 = Bc5VideoOutStatusOn();
\tconst uint32_t     answer             = on ? bc5_resolution_uhd : today;
\tstatic std::atomic_bool told {false};
\tif (!told.exchange(true)) {
\t\tstd::fprintf(stderr,
\t\t             "[bc5] exp 0401: videoout status %s: resolution %u at the first sceVideoOutGetOutputStatus (port size %ux%u, %d "
\t\t             "buffer sets registered; today's answer %u)\\n",
\t\t             on ? "on" : "off", static_cast<unsigned>(answer), static_cast<unsigned>(port_width),
\t\t             static_cast<unsigned>(port_height), registered_sets, static_cast<unsigned>(today));
\t}
\treturn answer;
}

static int Bc5VideoOutRegisteredSets(const VideoOutConfig& cfg) { // under cfg.mutex
\tint sets = 0;
\tfor (const auto& group: cfg.groups) {
\t\tsets += group.occupied ? 1 : 0;
\t}
\treturn sets;
}

"""

# ---- VideoOutGetOutputStatus: today's line stays, its value goes through the switch ----------------------------------
RES_OLD = b"""\tctx->mutex.Lock();
\tstatus->resolution   = (ctx->width >= 3840 || ctx->height >= 2160 ? 2u : 1u);
\tstatus->dynamicRange = 1;
"""
RES_NEW = b"""\tctx->mutex.Lock();
\tstatus->resolution   = (ctx->width >= 3840 || ctx->height >= 2160 ? 2u : 1u);
\tstatus->resolution   = Bc5VideoOutStatusResolution(status->resolution, ctx->width, ctx->height, // experiment 0401 series e4
\t                                                   Bc5VideoOutRegisteredSets(*ctx));
\tstatus->dynamicRange = 1;
"""

# ---- what the block and the test rely on -----------------------------------------------------------------------------
NEEDS = (
    (b"#include <atomic>\n", "<atomic> (std::atomic_bool)"),
    (b"#include <cstdio>\n", "<cstdio> (std::fprintf)"),
    (b"#include <cstdlib>\n", "<cstdlib> (std::getenv)"),
    (b"#include <cstring>\n", "<cstring> (std::strcmp)"),
    (b"\tstd::array<BufferAttributeGroup, VIDEO_OUT_BUFFER_ATTRIBUTE_NUM_MAX> groups;\n", "VideoOutConfig's sets"),
    (b"\tbool                     occupied = false;\n", "BufferAttributeGroup::occupied"),
    (b"\tctx->groups[set_index] = group;\n", "RegisterBuffers2's write of the set"),
    (b"\tfor (auto& ctx: m_video_out_ctx) {\n\t\tctx.width  = width;\n\t\tctx.height = height;\n\t}\n", "Impl::Init's size"),
)
# Every write of a port's width or height (VideoOutConfig is named ctx, cfg, config or video_out in this file).
SIZE_WRITE = re.compile(rb"\b(?:ctx|cfg|config|video_out|m_video_out_ctx\[[^\]]*\])(?:->|\.)(?:width|height)\s*=(?!=)")


def once(s, anchor, new, what):
    assert s.count(anchor) == 1, (what, anchor[:70], s.count(anchor))
    return s.replace(anchor, new)


def edit(s):
    assert MARK not in s and MARK_FN not in s and b"Bc5VideoOutRegisteredSets" not in s, "videoOut.cpp has the edit already"
    for anchor, what in NEEDS:
        assert s.count(anchor) == 1, (what, s.count(anchor))
    writes = SIZE_WRITE.findall(s)
    assert writes == [b"ctx.width  =", b"ctx.height ="], ("a port's size is written outside Impl::Init", writes)
    assert s.index(b"struct VideoOutConfig {\n") < s.index(FUNC_ANCHOR), "VideoOutConfig must come before the block"
    s = once(s, FUNC_ANCHOR, BLOCK + FUNC_ANCHOR, "VideoOutGetOutputStatus")
    s = once(s, RES_OLD, RES_NEW, "VideoOutGetOutputStatus's resolution")
    assert s.index(BLOCK) < s.index(RES_NEW)
    return s


def main():
    assert len(sys.argv) == 3, __doc__
    root, out = sys.argv[1], sys.argv[2]
    with open(os.path.join(root, REL), "rb") as f:
        s = f.read()
    o = edit(s)
    p = os.path.join(out, REL)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "wb") as f:
        f.write(o)
    print(f"{hashlib.md5(o).hexdigest()}  {REL}")


if __name__ == "__main__":
    main()
