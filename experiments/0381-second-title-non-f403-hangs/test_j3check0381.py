#!/usr/bin/env python3
# BC5 exp 0381: j3check0381.py on synthetic journals: the same opener with and without the restore, mid-chain, and a
# journal without identity (REVIEW-06-J2's probe, extended). usage: python test_j3check0381.py
import j3check0381 as c


def dis(kind, at, pgm, job, seg, orig, ud0="00000011"):
    return "  %s dispatch op 16 at %d: pgm 0x%s ud0-3 %s 0 0 0 ud4-7 0 base1 0x0 +0x0 len 3 job %d seg %d orig %d" % (kind, at, pgm, ud0, job, seg, orig)


ACB = ["job 1 acb: 100 dwords, 1 segments, ring 0, previous job dcb", "  job 1 seg 0: off 0 prefix 0 n 100 prefix ud0 none", dis("acb", 42, "11d03a3500", 1, 0, 42, "11d00860")]


def head(prefix, ud0):
    return ["job 2 dcb: %d dwords, 1 segments, ring 0, previous job acb" % (15083 + prefix),
            "  job 2 seg 0: off 0 prefix %d n 15083 prefix ud0 %s" % (prefix, ud0),
            dis("dcb", 13 + prefix, "909977100", 2, 0, 13)]


# Without the restore, the J1 shape.
out = c.report(ACB + head(0, "none"))
assert out[-1] == "targets 1, eligible 1", out
assert "prefix ud0 none" in out[1], out
# With it: the same opener at chain offset 71, still eligible, with the restore attributed to it.
out = c.report(ACB + head(58, "00000011"))
assert out[-1] == "targets 1, eligible 1", out
assert "orig 13" in out[1] and "prefix 58 dwords, prefix ud0 00000011" in out[1], out
# Mid-chain, as J2's offsets suggest: found, not eligible.
mid = ["job 2 dcb: 103865 dwords, 2 segments, ring 0, previous job acb",
       "  job 2 seg 0: off 0 prefix 0 n 88000 prefix ud0 none",
       "  job 2 seg 1: off 88000 prefix 58 n 15083 prefix ud0 00000011",
       dis("dcb", 500, "909974400", 2, 0, 500),
       dis("dcb", 88071, "909977100", 2, 1, 13)]
out = c.report(ACB + mid)
assert out[-1] == "targets 1, eligible 0", out
assert "not eligible" in out[1], out
# Behind a dcb job: not eligible.
out = c.report(ACB + ["job 3 dcb: 15083 dwords, 1 segments, ring 0, previous job dcb", "  job 3 seg 0: off 0 prefix 0 n 15083 prefix ud0 none", dis("dcb", 13, "909977100", 3, 0, 13)])
assert out[-1] == "targets 1, eligible 0", out
# Not the segment's first dispatch: no target.
out = c.report(ACB + ["job 4 dcb: 15083 dwords, 1 segments, ring 0, previous job acb", "  job 4 seg 0: off 0 prefix 0 n 15083 prefix ud0 none",
                      dis("dcb", 5, "909974400", 4, 0, 5), dis("dcb", 13, "909977100", 4, 0, 13)])
assert out[-1] == "targets 0, eligible 0", out
# An old journal: no identity, no verdict.
old = ["  dcb dispatch op 16 at 13: pgm 0x909977100 ud0-3 00000011 0 0 0 ud4-7 0 base1 0x0 +0x0 len 3"]
out = c.report(old)
assert out[-1].startswith("verdict: eligibility unverified"), out
print("ok: 6 cases")
