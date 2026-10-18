#!/usr/bin/env python3
# Experiment 0157, fourteenth step: the full-state prefix in front of the graphics buffers that draw becomes
# the default (BC5_DIRECT_PREFIX_ALL unset = draws; 0 turns it off).
p = "/home/kjaniszewski/src/KytyPlus/src/libs/bc5LleAgc.cpp"
s = open(p, encoding="utf-8", newline="").read()


def rep(a, b):
    global s
    assert s.count(a) == 1, (s.count(a), a[:80])
    s = s.replace(a, b)


rep("""// Experiment 0157: BC5_DIRECT_PREFIX_ALL: 1|all = the full-state prefix (as the pieces') in front of
// every graphics buffer; draws = in front of the graphics buffers that draw; sx = in front of those, a
// SET_CONTEXT_REG of SX_PS_DOWNCONVERT..SX_MRT7_BLEND_OPT (ctx 0x1d5-0x1df) alone, with the tracked values.
static int prefix_mode() {
	static const int v = [] {
		const char* e = std::getenv("BC5_DIRECT_PREFIX_ALL");
		if (e == nullptr || *e == 0 || std::strcmp(e, "0") == 0) return 0;
		if (std::strcmp(e, "draws") == 0) return 2;
		if (std::strcmp(e, "sx") == 0) return 3;
		return 1;
	}();
	return v;
}""",
    """// Experiment 0157 (F204): other processes' work on the GFX ring (the desktop compositor's RADV jobs
// between the title's submissions) leaves context registers the title set once and never again per
// buffer -- the second title's menu redraws then ran with RADV's RB+ blend optimisation
// (SX_MRT*_BLEND_OPT) and left their element rectangles transparent. BC5_DIRECT_PREFIX_ALL:
// draws (the default) = the pieces' full-state prefix (CLEAR_STATE, then every tracked context, SH and
// uconfig register) in front of every graphics buffer that draws (run 690: 0 of 88 flagged, 43.9 fps
// against 45.0 without); sx = in front of those, one SET_CONTEXT_REG of SX_PS_DOWNCONVERT..
// SX_MRT7_BLEND_OPT (ctx 0x1d5-0x1df) with the tracked values (run 689: 0 of 88, 45.0 fps); 1|all =
// the full prefix in front of every graphics buffer (run 684: half the frame rate); 0 = off.
static int prefix_mode() {
	static const int v = [] {
		const char* e = std::getenv("BC5_DIRECT_PREFIX_ALL");
		if (e == nullptr || *e == 0 || std::strcmp(e, "draws") == 0) return 2;
		if (std::strcmp(e, "0") == 0) return 0;
		if (std::strcmp(e, "sx") == 0) return 3;
		return 1;
	}();
	return v;
}""")

open(p, "w", encoding="utf-8", newline="").write(s)
print("ok")
