#!/usr/bin/env python3
"""BC5 experiment 0412, tag gp412 (README section 23): the gap classifier's stamps in the main unit.
Input: the main unit after mklock0412.py and mksect0412.py. gap0412.inc (the text lock0412.cpp tests) goes in before
the counting mutex, and these places get a stamp; no statement of the unit is removed or reordered:
  - the device mutex: lk412::Mutex::lock() opens gp412::Scope(kDevMutex) (in lock0412.inc itself);
  - the chain's flush mutex in chain_submit: Scope(kChainMutex) around taking it;
  - drain() at the flip, the in-flight cap in submit_now, the ring's wait-idle: their 50 us sleep becomes
    gp412::poll_sleep(50, cause), which is the same sleep inside a Scope;
  - the label waits in submit_split: its four 50 us sleeps and one 20 us sleep become poll_sleep(.., kLabel);
  - the completion thread: Scope(kIdle) around its wait for work, Scope(kFence) around Device::finish;
  - submit_now and submit_split: Scope(kSubmit) / Scope(kSplit) for their whole body (exclusive of the scopes inside);
  - VideoOutSubmitEopFlip: gp412::flip() after the drain.
BC5_GUARD_GAP_STAT unset: every Scope is one test of a constant and poll_sleep is the sleep it replaced.
Each anchor's count is asserted; the script undoes its edits and asserts that this gives the input back.
usage: mkgap0412.py <bc5LleAgc.cpp in> <bc5LleAgc.cpp out>"""
import hashlib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
S50 = b"std::this_thread::sleep_for(std::chrono::microseconds(50));"
S20 = b"std::this_thread::sleep_for(std::chrono::microseconds(20));"
HEAD = b"// Experiment 0412 (tag gp412): BC5_GUARD_GAP_STAT, the gap classifier's counters.\n#define GP412_PRINT journal\n#define GP412_NOW timing_now\n"


def main():
    assert len(sys.argv) == 3 and sys.argv[1] != sys.argv[2], __doc__
    s = open(sys.argv[1], "rb").read()
    inc = open(os.path.join(HERE, "gap0412.inc"), "rb").read()
    assert b"g_dev_mutex.mark(" in s and b"gp412::Scope gs(gp412::kDevMutex)" in s and b"namespace gp412" not in s, "refused: not the expected input"
    assert b"\r" not in s and b"\r" not in inc
    inc.decode("ascii")
    edits = []  # (old, new), each old exactly once in the text at the time it is applied

    def once(old, new):
        edits.append((old, new))

    a = b"// Experiment 0412 (tag lk412): BC5_GUARD_LOCK_STAT, the device mutex with per-thread hold and wait counters.\n"
    once(a, HEAD + inc + a)
    a = b"\tstd::lock_guard order(s.flush_mu);\n"
    once(a, b"\tgp412::Scope gs412(gp412::kChainMutex); // exp 0412 (tag gp412)\n" + a + b"\tgs412.end();\n")
    a = b"\twhile (g_cq_items.load() != 0) " + S50 + b"\n"
    once(a, b"\twhile (g_cq_items.load() != 0) gp412::poll_sleep(50, gp412::kDrain); // exp 0412 (tag gp412)\n")
    a = b"\t\twhile (g_cq_fences.load() >= max_in_flight || g_recovering.load()) " + S50 + b"\n"
    once(a, b"\t\twhile (g_cq_fences.load() >= max_in_flight || g_recovering.load()) gp412::poll_sleep(50, gp412::kCap); // exp 0412 (tag gp412)\n")
    a = b"\t\t\t\t\t\t\tgave_up = true;\n\t\t\t\t\t\t\tbreak;\n\t\t\t\t\t\t}\n\t\t\t\t\t\t" + S50 + b"\n"
    once(a, a.replace(S50, b"Direct::gp412::poll_sleep(50, Direct::gp412::kWaitIdle); // exp 0412 (tag gp412)"))
    a = b"\t\t\tcq.cv.wait(lk, [&cq] { return !cq.items.empty(); });\n"
    once(a, b"\t\t\tgp412::Scope gs412(gp412::kIdle); // exp 0412 (tag gp412)\n" + a)
    a = b"\t\t\t\tif (g_dev) r = g_dev->finish(j.seq, j.slot, fence_ns);\n"
    once(a, b"\t\t\t\t{\n\t\t\t\t\tgp412::Scope gs412(gp412::kFence); // exp 0412 (tag gp412)\n\t" + a + b"\t\t\t\t}\n")
    a = b"static void submit_now(const uint32_t* ib, uint32_t num_dwords, const char* kind, int ring, const Chain* chain) {\n"
    once(a, a + b"\tgp412::Scope gs412_body(gp412::kSubmit); // exp 0412 (tag gp412)\n")
    a = b"static void submit_split(const uint32_t* ib, uint32_t num_dwords, const char* kind) {\n"
    once(a, a + b"\tgp412::Scope gs412_body(gp412::kSplit); // exp 0412 (tag gp412)\n")
    a = b"\tif (!defer) Bc5Gc::Direct::drain(); // nothing of the frame may still be in flight\n"
    once(a, a + b"\tBc5Gc::Direct::gp412::flip(); // exp 0412 (tag gp412)\n")
    out = s
    for old, new in edits:
        assert out.count(old) == 1, ("an anchor does not occur exactly once", old[:60], out.count(old))
        out = out.replace(old, new)
    # the label waits: every 50 us and 20 us sleep inside submit_split
    lo = out.index(b"static void submit_split(const uint32_t* ib, uint32_t num_dwords, const char* kind) {\n")
    hi = out.index(b"\n}\n", lo)
    body = out[lo:hi]
    assert body.count(S50) == 4 and body.count(S20) == 1, ("the label waits are not the five known sleeps", body.count(S50), body.count(S20))
    L50 = b"gp412::poll_sleep(50, gp412::kLabel); /* exp 0412 (tag gp412) */"
    L20 = b"gp412::poll_sleep(20, gp412::kLabel); /* exp 0412 (tag gp412) */"
    out = out[:lo] + body.replace(S50, L50).replace(S20, L20) + out[hi:]
    # undo
    back = out
    assert back.count(L50) == 4 and back.count(L20) == 1
    back = back.replace(L50, S50).replace(L20, S20)
    for old, new in reversed(edits):
        assert back.count(new) == 1, ("undo", new[:60], back.count(new))
        back = back.replace(new, old)
    assert back == s, "undoing the edits does not give the input back"
    assert out.count(b"gp412::flip()") == 1 and out.index(b"namespace gp412") < out.index(b"namespace lk412")
    open(sys.argv[2], "wb").write(out)
    print(f"bc5LleAgc.cpp {hashlib.md5(out).hexdigest()}")


if __name__ == "__main__":
    main()
