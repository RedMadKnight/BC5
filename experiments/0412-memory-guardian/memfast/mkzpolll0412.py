#!/usr/bin/env python3
"""BC5 experiment 0412, the lean build (README section 43): mkzpoll0412.py's edit (the zero skip's poll before every
submission, tag zp412) applied straight to g412d's unit, without the catchers and counters that stand between g412d
and g412u in the normal build (lock, sections, gaps, buffers, return-aware release, use, zero-skip catcher, protection
bits, no-GPU unpin, no-GPU scan). The glue's text is mkzpoll0412.py's own; only the anchors differ.
usage: mkzpolll0412.py <bc5LleAgc.cpp in (g412d, 5361c8ba)> <bc5LleAgc.cpp out>"""
import hashlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mkzpoll0412 import GLUE, T  # noqa: E402


def main():
    assert len(sys.argv) == 3 and sys.argv[1] != sys.argv[2], __doc__
    s = open(sys.argv[1], "rb").read()
    assert hashlib.md5(s).hexdigest() == "5361c8baac7690e5167e89a27cc7b4c7", "refused: not g412d's unit"
    assert b"tag zp412" not in s and b"\r" not in s
    edits = []
    a = b"static void submit_one(const uint32_t* ib, uint32_t num_dwords, const char* kind);\n"
    edits.append((a, GLUE + a))
    a = b"\taliases_apply(false); // experiment 0056\n"
    edits.append((a, b"\tzpoll412_submit();" + T + a))
    out = s
    for old, new in edits:
        assert out.count(old) == 1, ("an anchor does not occur exactly once", old[:60], out.count(old))
        out = out.replace(old, new)
    back = out
    for old, new in reversed(edits):
        assert back.count(new) == 1, ("undo", new[:60], back.count(new))
        back = back.replace(new, old)
    assert back == s, "undoing the edits does not give the input back"
    g = out.index(b"static void zpoll412_submit() {")
    for need in (b"static void zskip_take_back(DState& S, int fd) {", b"static void direct_sync_one(DState& S, bool force) {", b"static uint64_t g_zstat_cpu = 0", b"g_submits {0};"):
        assert out.index(need) < g, ("must be defined before the glue", need[:40])
    call = out.index(b"\tzpoll412_submit();")
    sn = out.index(b"static void submit_now(const uint32_t* ib, uint32_t num_dwords, const char* kind, int ring, const Chain* chain) {")
    assert sn < call < out.index(b"std::shared_ptr<const std::vector<bc5::direct::Mapping>> maps_p = g_dev->sorted_mappings();", sn), "the call is not before submit_now's mapping list"
    open(sys.argv[2], "wb").write(out)
    print(f"bc5LleAgc.cpp {hashlib.md5(out).hexdigest()}")


if __name__ == "__main__":
    main()
