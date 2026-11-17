#!/usr/bin/env python3
"""BC5 experiment 0430: the shared swap's unit (the fix of the second title's GPU hang, his play of 2026-11-16 21:38).
    mkswap0430.py <tree root>
src/libs/bc5LleAgc.cpp of the shared tree (patch a8717e53, md5 0cda79b5) edited in place: ho430.cpp (beside this script)
compiled as HO430_SHARED (F2 BC5_DIRECT_XQ_PENDING and F3 BC5_DIRECT_XQ_ACQUIRE, each on unless "0"; G off) and its five
hooks: the wait in submit_split, a job's submit, its completion, the GIVEN UP / CYCLE line, and F3 before the device call.
None of the exp 0430 catchers (dj430: the dispatch journal, args, waves, snapshots, tables) goes into the shared unit.
Every anchor must match exactly once, or nothing is written."""
import hashlib
import os
import sys

BASE_MD5 = "0cda79b5"
U = "src/libs/bc5LleAgc.cpp"


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: mkswap0430.py <tree root>")
        return 2
    path = os.path.join(sys.argv[1], U)
    data = open(path, "rb").read()
    md5 = hashlib.md5(data).hexdigest()[:8]
    if md5 != BASE_MD5:
        print(f"mkswap0430: {path} is {md5}, not the base {BASE_MD5}")
        return 1
    text = data.decode("utf-8", "surrogateescape")
    here = os.path.dirname(os.path.abspath(__file__))
    ho = open(os.path.join(here, "ho430.cpp"), encoding="utf-8").read()
    ho = ("// BC5 experiment 0430 (tag ho430, the shared form): the fix of the second title's GPU hang of 2026-11-16 21:38.\n"
          "#define HO430_SHARED 1\n") + ho
    edits = [
        ("static void forget_label_writes(uint64_t seq, int ring, bool all) {\n\tstd::lock_guard lk(g_plw_mutex);\n",
         ho + "static void forget_label_writes(uint64_t seq, int ring, bool all) {\n\tstd::lock_guard lk(g_plw_mutex);\n"
         "\tho430::job_done(seq, ring, all); // exp 0430 (tag ho430)\n"),
        ("\tif (!wait_satisfied(p, op == 0x93)) chain_flush(1); // ADR 0010: what the chain holds may write this label\n",
         "\tho430::at_wait(p, op == 0x93, label, kind, job_ring(kind), ib, num_dwords, i); // exp 0430 (tag ho430): F2 and F3\n"
         "\t\t\t\t\tif (!wait_satisfied(p, op == 0x93)) chain_flush(1); // ADR 0010: what the chain holds may write this label\n"),
        ("\t\tregister_label_writes(ib, num_dwords, r.executed_offsets, r.seq_no, r.ring); // experiment 0055\n",
         "\t\tregister_label_writes(ib, num_dwords, r.executed_offsets, r.seq_no, r.ring); // experiment 0055\n"
         "\t\tho430::job_submitted(ib, num_dwords, r.executed_offsets, r.seq_no, r.ring, kind); // exp 0430 (tag ho430)\n"),
        ("\tif (!ok) t_wait_given_up = true;\n",
         "\tif (!ok) t_wait_given_up = true;\n"
         "\t\t\t\t\tif (!ok) ho430::given_up(broken, label, kind, job_ring(kind), i); // exp 0430 (tag ho430)\n"),
        ("\tauto r = g_dev->submit(std::span<const uint32_t>(sub_ib, sub_n), opt, 2'000'000'000ull, true, qring);\n",
         "\tif (sub_ib == ib) ho430::f3_before_submit(ib, num_dwords, opt.drop_offsets, qring, kind, *maps_p); // exp 0430 (tag ho430): F3\n"
         "\tauto r = g_dev->submit(std::span<const uint32_t>(sub_ib, sub_n), opt, 2'000'000'000ull, true, qring);\n"),
    ]
    for i, (old, new) in enumerate(edits):
        c = text.count(old)
        if c != 1:
            print(f"mkswap0430: anchor {i} matches {c} times")
            return 1
        text = text.replace(old, new)
    out = text.encode("utf-8", "surrogateescape")
    open(path, "wb").write(out)
    print(f"mkswap0430: 5 hooks + ho430 (shared), {BASE_MD5} -> {hashlib.md5(out).hexdigest()[:8]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
