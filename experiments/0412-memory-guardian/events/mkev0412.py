#!/usr/bin/env python3
"""BC5 experiment 0412, tag ev412: the bound on an event's pending queue (event_cap0412.hpp), as edits of two host
units of the shared source the shared build 4d2b1b1d was made from (~/src/KytyPlus, read only; the edited copies go to
<out dir>):
  src/kernel/eventQueue.cpp (c45e6a72...)                  three places: two includes more; KernelEventPendingPush before
                                                           AmprEventTriggerFunc; that function's push_back through it
  src/graphics/host_gpu/renderer/sync.cpp (68733b6c...)    two places: the declaration before the unit's namespace;
                                                           EopEventTriggerFunc's push_back through it
Two switches, default off (unset, empty and "0"): KYTY_BC5_EVENT_PENDING_CAP=<n>, KYTY_BC5_EVENT_PENDING_LOG=1. With
both off KernelEventPendingPush does the push_back the two functions did. No header of the tree changes, so no other unit
is recompiled (KernelEqueueEvent keeps its layout: the log's per-event state is a map in eventQueue.cpp).
Every anchor occurs exactly once; the inserted text is ASCII with LF line ends; a unit that has the edit already is
refused, and so is an input that is not the pinned one (--any-input lifts only the md5 pins). After editing, the script
undoes its edits and asserts that this gives the inputs back byte for byte. Prints "<relpath> <md5>" per unit.
CPU test: evcap0412.cpp (event_cap0412.hpp alone).
usage: mkev0412.py [--any-input] <tree root in> <out dir>"""
import hashlib
import os
import sys

EQ = "src/kernel/eventQueue.cpp"
SY = "src/graphics/host_gpu/renderer/sync.cpp"
PINS = {EQ: "c45e6a72c8e419d98059c3477a9373cc", SY: "68733b6c5be980f238571723296f7d05"}
MARKS = (b"ev412", b"KernelEventPendingPush", b"KYTY_BC5_EVENT_PENDING", b"event_cap0412")

PUSH = b"\t\tevent->pending_events.push_back(triggered_event);\n"
PUSH_NEW = b"\t\tKernelEventPendingPush(event, triggered_event); // exp 0412 (tag ev412): KYTY_BC5_EVENT_PENDING_CAP, _LOG\n"
PUSH_NEW_SY = b"\t\tLibKernel::EventQueue::KernelEventPendingPush(event, triggered_event); // exp 0412 (tag ev412): KYTY_BC5_EVENT_PENDING_CAP, _LOG\n"

HOST = b'''// Experiment 0412 (tag ev412, mkev0412.py; README section 10): the one place an already triggered event gets one more
// pending entry. With KYTY_BC5_EVENT_PENDING_CAP the queue is bounded (a trigger past the bound replaces the newest entry);
// with KYTY_BC5_EVENT_PENDING_LOG the event whose queue grows is named on stderr. Both off: the push_back as before.
// The callers hold the queue's mutex.
void KernelEventPendingPush(KernelEqueueEvent* event, const KernelEvent& triggered_event) {
	EXIT_IF(event == nullptr);
	static const bc5::evcap::Cfg cfg = [] {
		const bc5::evcap::Cfg c = bc5::evcap::parse(std::getenv("KYTY_BC5_EVENT_PENDING_CAP"), std::getenv("KYTY_BC5_EVENT_PENDING_LOG"));
		if (c.on() || c.bad) {
			std::fprintf(stderr, "[bc5] exp 0412 events: pending cap %zu (0: none), log %s%s (tag ev412)\\n", c.cap, c.log ? "on" : "off",
			             c.bad ? "; a value was not understood and is off" : "");
		}
		return c;
	}();
	if (!cfg.on()) {
		auto& q = event->pending_events;
		q.push_back(triggered_event);
		return;
	}
	const bool grew = bc5::evcap::push(event->pending_events, triggered_event, cfg.cap);
	if (!cfg.log) {
		return;
	}
	static std::mutex                                                 m;
	static std::map<std::pair<uintptr_t, int>, bc5::evcap::Seen> seen;
	std::lock_guard                                                   lock(m);
	bc5::evcap::Seen& s = seen[{triggered_event.ident, static_cast<int>(triggered_event.filter)}];
	const uint64_t    len = event->pending_events.size();
	if (grew) {
		if (bc5::evcap::due_len(s, len)) {
			std::fprintf(stderr, "[bc5] exp 0412 events: ident 0x%" PRIx64 " filter %d udata %p: %" PRIu64 " pending entries (the longest so far), %" PRIu64 " coalesced\\n",
			             static_cast<uint64_t>(triggered_event.ident), static_cast<int>(triggered_event.filter), triggered_event.udata, len, s.coalesced);
		}
	} else if (bc5::evcap::due_coalesced(s)) {
		std::fprintf(stderr, "[bc5] exp 0412 events: ident 0x%" PRIx64 " filter %d udata %p: %" PRIu64 " triggers coalesced at the cap of %zu pending entries\\n",
		             static_cast<uint64_t>(triggered_event.ident), static_cast<int>(triggered_event.filter), triggered_event.udata, s.coalesced, cfg.cap);
	}
}

'''


def md5(b):
    return hashlib.md5(b).hexdigest()


def edits(rel):
    if rel == EQ:
        a1 = b"#include <unordered_map>\n"
        a2 = b"static void AmprEventTriggerFunc(KernelEqueueEvent* event, void* trigger_data) {\n"
        return [("the includes", a1, b"#include <map>   // exp 0412 (tag ev412)\n#include <mutex> // exp 0412 (tag ev412)\n" + a1 + b"#include \"event_cap0412.hpp\" // exp 0412 (tag ev412)\n"),
                ("the function", a2, HOST + a2),
                ("the AMPR push", PUSH, PUSH_NEW)]
    a1 = b"#include <optional>\n\nnamespace Libs::Graphics::Sync {\n"
    return [("the declaration", a1, b"#include <optional>\n\nnamespace Libs::LibKernel::EventQueue {\n"
             b"void KernelEventPendingPush(KernelEqueueEvent* event, const KernelEvent& triggered_event); // exp 0412 (tag ev412): eventQueue.cpp\n"
             b"} // namespace Libs::LibKernel::EventQueue\n\nnamespace Libs::Graphics::Sync {\n"),
            ("the EOP push", PUSH, PUSH_NEW_SY)]


def balance(b):
    return (b.count(b"{") - b.count(b"}"), b.count(b"(") - b.count(b")"), b.count(b"[") - b.count(b"]"))


def apply(rel, s):
    for m in MARKS:
        assert m not in s, ("refused: the unit has the edit already", rel, m.decode())
    assert b"\r" not in s, "a CR in the LF unit"
    out, at, done = s, -1, []
    for name, old, new in edits(rel):
        assert out.count(old) == 1, ("an anchor does not occur exactly once", rel, name, out.count(old))
        assert balance(old) == balance(new), ("the edit changes the balance", rel, name)
        new.decode("ascii")
        assert b"\r" not in new
        pos = out.index(old)
        assert pos > at, ("the edits are not in file order", rel, name)
        at = pos
        out = out.replace(old, new)
        done.append((name, old, new))
    back = out
    for name, old, new in reversed(done):
        assert back.count(new) == 1, ("undo", rel, name)
        back = back.replace(new, old)
    assert back == s, "undoing the edits does not give the input back"
    assert out.count(b"pending_events.push_back(triggered_event)") == 0, ("a direct push is left", rel)
    assert out.count(b"KernelEventPendingPush(") == 2, ("the function's uses", rel)
    return out


def main():
    args = sys.argv[1:]
    any_input = "--any-input" in args
    args = [a for a in args if a != "--any-input"]
    assert len(args) == 2, __doc__
    root, outdir = args
    assert os.path.abspath(root) != os.path.abspath(outdir), "the out dir must not be the tree"
    for rel in (EQ, SY):
        with open(os.path.join(root, rel), "rb") as f:
            s = f.read()
        if not any_input:
            assert md5(s) == PINS[rel], ("refused: not the pinned input", rel, md5(s))
        out = apply(rel, s)
        dst = os.path.join(outdir, rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        with open(dst, "wb") as f:
            f.write(out)
        print(f"{rel} {md5(out)}")


if __name__ == "__main__":
    main()
