#!/usr/bin/env python3
"""BC5 experiment 0412, tag lk412 (README section 21): the parts of submit_now's work under the device mutex.
Input: the main unit after mklock0412.py. Seven statements `g_dev_mutex.mark(<part>);` are added inside submit_now, so
that BC5_GUARD_LOCK_STAT=1 also prints the time held per part and thread:
  0 probe (from the lock to the mapping sync), 1 anon sync (sync_mappings), 2 direct sync (direct_sync and the
  remembered pages), 3 learned (learned_apply), 4 hints (hint_targets), 5 prepare (everything from there to the
  device call: aliases, the survey of the buffer, the split and state work), 6 device submit (bc5::direct::Device::
  submit: the filter and the ioctl), 7 tail (what follows the device call).
With the switch off mark() returns after one test of a constant. Every anchor occurs exactly once and lies inside
submit_now; the script undoes its edits and asserts that this gives the input back.
usage: mksect0412.py <bc5LleAgc.cpp in> <bc5LleAgc.cpp out>"""
import hashlib
import sys

M = lambda k: b"\tg_dev_mutex.mark(%d); // exp 0412 (tag lk412)\n" % k
EDITS = [
    (b"\tsync_mappings(force_sync, urgent_sync);\n", 1, True),
    (b"\tdirect_sync(force_sync);\n", 2, True),
    (b"\tif (!guard0412_defer_apply()) learned_apply(); // exp 0412 (tag g412): BC5_GUARD_APPLY_MIN_MS\n", 3, True),
    (b"\thint_targets(ib, num_dwords);\n", 4, True),
    (b"\thint_targets(ib, num_dwords);\n\tconst uint64_t t2 = SoftCp::now_ns();\n", 5, False),
    (b"\tauto r = g_dev->submit(std::span<const uint32_t>(sub_ib, sub_n), opt, 2'000'000'000ull, true, qring);\n", 6, True),
    (b"\tauto r = g_dev->submit(std::span<const uint32_t>(sub_ib, sub_n), opt, 2'000'000'000ull, true, qring);\n", 7, False),
]


def main():
    assert len(sys.argv) == 3 and sys.argv[1] != sys.argv[2], __doc__
    s = open(sys.argv[1], "rb").read()
    assert b"lk412::Mutex" in s and b"g_dev_mutex.mark(" not in s, "refused: not mklock0412.py's output, or edited already"
    lo = s.index(b"\nstatic void submit_now(const uint32_t* ib, uint32_t num_dwords, const char* kind, int ring, const Chain* chain) {\n")
    hi = s.index(b"\n}\n", lo)
    out = s
    for anchor, part, before in EDITS:
        assert s.count(anchor) == 1, ("an anchor does not occur exactly once", anchor[:40], s.count(anchor))
        assert lo < s.index(anchor) < hi, ("an anchor is outside submit_now", anchor[:40])
    # marks before an anchor first, then marks after: the two anchors used twice keep their text
    for anchor, part, before in EDITS:
        if before:
            assert out.count(anchor) == 1
            out = out.replace(anchor, M(part) + anchor)
    for anchor, part, before in EDITS:
        if not before:
            a = anchor.replace(b"\thint_targets", M(4) + b"\thint_targets") if part == 5 else anchor
            a = M(6) + a if part == 7 else a
            assert out.count(a) == 1, ("the second pass's anchor", part, out.count(a))
            out = out.replace(a, a + M(part))
    assert out.count(b"g_dev_mutex.mark(") == 7
    back = out
    for k in range(1, 8):
        assert back.count(M(k)) == 1, k
        back = back.replace(M(k), b"")
    assert back == s, "undoing the edits does not give the input back"
    order = [out.index(M(k)) for k in range(1, 8)]
    assert order == sorted(order), "the marks are not in order"
    open(sys.argv[2], "wb").write(out)
    print(f"bc5LleAgc.cpp {hashlib.md5(out).hexdigest()}")


if __name__ == "__main__":
    main()
