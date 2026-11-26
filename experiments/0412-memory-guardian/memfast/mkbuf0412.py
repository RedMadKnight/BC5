#!/usr/bin/env python3
"""BC5 experiment 0412, tag bf412 (README section 26): the per-buffer time line's stamps in the main unit.
Input: the main unit after mklock0412.py, mksect0412.py and mkgap0412.py. buf0412.inc goes in after gap0412.inc, and:
  - submit_split's entry: bf412::handed (line B);
  - chain_submit, where the chain is taken: bf412::chain_taken(s.open_ns, why);
  - submit_now: bf412::kernel_has_it() right after Device::submit, bf412::submitted(n, ...) where the submission's
    number n is taken (line S);
  - the completion thread, after Device::finish: bf412::done (line D);
  - VideoOutSubmitEopFlip: bf412::flip_mark('f') before the drain, ('F') after it;
  - submit_split's four 50 us label polls: gp412::poll_sleep(50, kLabel) becomes bf412::label_sleep(50, label), the
    same sleep with the label's address noted (line W).
BC5_GUARD_BUF_STAT unset: every call is one test of a constant. No statement of the unit is removed or reordered.
Each anchor's count is asserted; the script undoes its edits and asserts that this gives the input back.
usage: mkbuf0412.py <bc5LleAgc.cpp in> <bc5LleAgc.cpp out>"""
import hashlib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
T = b" // exp 0412 (tag bf412)\n"


def main():
    assert len(sys.argv) == 3 and sys.argv[1] != sys.argv[2], __doc__
    s = open(sys.argv[1], "rb").read()
    inc = open(os.path.join(HERE, "buf0412.inc"), "rb").read()
    assert b"namespace gp412" in s and b"namespace bf412" not in s, "refused: not the expected input"
    assert b"\r" not in s and b"\r" not in inc
    inc.decode("ascii")
    edits = []
    a = b"// Experiment 0412 (tag lk412): BC5_GUARD_LOCK_STAT, the device mutex with per-thread hold and wait counters.\n"
    edits.append((a, b"// Experiment 0412 (tag bf412): BC5_GUARD_BUF_STAT, the per-buffer time line.\n" + inc + a))
    a = b"\tgp412::Scope gs412_body(gp412::kSplit); // exp 0412 (tag gp412)\n"
    edits.append((a, a + b"\tbf412::handed(kind, num_dwords);" + T))
    a = b"\t\tmine.compute = c.compute;\n\t\ts.open_ns    = 0;\n"
    edits.append((a, b"\t\tmine.compute = c.compute;\n\t\tbf412::chain_taken(s.open_ns, why);" + T + b"\t\ts.open_ns    = 0;\n"))
    a = b"\tg_dev_mutex.mark(7); // exp 0412 (tag lk412)\n"
    edits.append((a, a + b"\tbf412::kernel_has_it();" + T))
    a = b"\t\t\t\t\tif (g_dev) r = g_dev->finish(j.seq, j.slot, fence_ns);\n\t\t\t\t}\n"
    edits.append((a, a + b"\t\t\t\tbf412::done(j.n, j.kind, j.num_dwords, r.ok);" + T))
    a = b"\tif (!defer) Bc5Gc::Direct::drain(); // nothing of the frame may still be in flight\n"
    edits.append((a, b"\tBc5Gc::Direct::bf412::flip_mark('f');" + T + a))
    a = b"\tBc5Gc::Direct::gp412::flip(); // exp 0412 (tag gp412)\n"
    edits.append((a, a + b"\tBc5Gc::Direct::bf412::flip_mark('F');" + T))
    out = s
    for old, new in edits:
        assert out.count(old) == 1, ("an anchor does not occur exactly once", old[:60], out.count(old))
        out = out.replace(old, new)
    # the submission's number, inside submit_now only
    lo = out.index(b"static void submit_now(const uint32_t* ib, uint32_t num_dwords, const char* kind, int ring, const Chain* chain) {\n")
    hi = out.index(b"\n}\n", lo)
    body = out[lo:hi]
    N_OLD = b"\tconst uint64_t n = g_submits.fetch_add(1);\n"
    N_NEW = N_OLD + b"\tbf412::submitted(n, kind, num_dwords, chain != nullptr ? chain->segs.size() : static_cast<size_t>(1));" + T
    assert body.count(N_OLD) == 1, ("the submission number in submit_now", body.count(N_OLD))
    out = out[:lo] + body.replace(N_OLD, N_NEW) + out[hi:]
    L_OLD = b"gp412::poll_sleep(50, gp412::kLabel); /* exp 0412 (tag gp412) */"
    L_NEW = b"bf412::label_sleep(50, label); /* exp 0412 (tag gp412, bf412) */"
    assert out.count(L_OLD) == 4, out.count(L_OLD)
    out = out.replace(L_OLD, L_NEW)
    back = out.replace(L_NEW, L_OLD)
    assert back.count(N_NEW) == 1
    back = back.replace(N_NEW, N_OLD)
    for old, new in reversed(edits):
        assert back.count(new) == 1, ("undo", new[:60], back.count(new))
        back = back.replace(new, old)
    assert back == s, "undoing the edits does not give the input back"
    open(sys.argv[2], "wb").write(out)
    print(f"bc5LleAgc.cpp {hashlib.md5(out).hexdigest()}")


if __name__ == "__main__":
    main()
