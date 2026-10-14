import re

def patch(p, pairs):
    s = open(p, encoding="utf-8", newline="").read()
    nl = "\r\n" if "\r\n" in s else "\n"
    for a, b in pairs:
        a = a.replace("\n", nl)
        b = b.replace("\n", nl)
        assert s.count(a) == 1, (p, s.count(a), a[:80])
        s = s.replace(a, b)
    open(p, "w", encoding="utf-8", newline="").write(s)

vo = "/home/kjaniszewski/src/KytyPlus/src/graphics/presentation/videoOut.cpp"
patch(vo, [
("""void FlipQueue::GetFlipStatus(VideoOutConfig& cfg, VideoOutFlipStatus& out) {
	Common::LockGuard lock(cfg.mutex);

	out = cfg.flip_status;
}
""", """// BC5 (experiment 0082): flips the direct-mode host has deferred behind their frame's GPU jobs
// (BC5_DIRECT_FLIP_DEFER) and not yet handed to VideoOutSubmitFlip. They count as pending: the
// second title waits for flipPendingNum to drop before it rewrites the previous frame's data.
static std::atomic<int> g_bc5_deferred_flips {0};
void Bc5VideoOutDeferredFlip(int delta) {
	g_bc5_deferred_flips += delta;
}

void FlipQueue::GetFlipStatus(VideoOutConfig& cfg, VideoOutFlipStatus& out) {
	Common::LockGuard lock(cfg.mutex);

	out = cfg.flip_status;
	static const bool hidden = std::getenv("BC5_DIRECT_FLIP_DEFER_HIDDEN") != nullptr;
	if (!hidden) out.flipPendingNum += g_bc5_deferred_flips.load();
}
"""),
])
s = open(vo, encoding="utf-8", newline="").read()
nl = "\r\n" if "\r\n" in s else "\n"
for inc in ("#include <atomic>", "#include <cstdlib>"):
    if inc not in s:
        s = s.replace("#include", inc + nl + "#include", 1)
open(vo, "w", encoding="utf-8", newline="").write(s)

vh = "/home/kjaniszewski/src/KytyPlus/src/graphics/presentation/videoOut.h"
patch(vh, [
("""void Bc5VideoOutWaitFlipCopied(int handle, int index);
""", """void Bc5VideoOutWaitFlipCopied(int handle, int index);
// BC5 (experiment 0082): +1 when the host defers a flip, -1 once it has been submitted.
void Bc5VideoOutDeferredFlip(int delta);
"""),
])

ag = "/home/kjaniszewski/src/KytyPlus/src/libs/bc5LleAgc.cpp"
patch(ag, [
("""		Bc5Gc::Direct::post([handle, index, flip_mode, flip_arg](bool) {
			VideoOut::VideoOutSubmitFlip(handle, index, flip_mode, flip_arg);
""", """		VideoOut::Bc5VideoOutDeferredFlip(1); // experiment 0082: pending for the game until submitted
		Bc5Gc::Direct::post([handle, index, flip_mode, flip_arg](bool) {
			VideoOut::VideoOutSubmitFlip(handle, index, flip_mode, flip_arg);
			VideoOut::Bc5VideoOutDeferredFlip(-1);
"""),
])
print("ok")
