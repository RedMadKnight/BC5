#!/usr/bin/env python3
# BC5 exp 0381: j4check0381.py on synthetic journals. usage: python test_j4check0381.py
import j4check0381 as c


def dis(kind, at, pgm, job, seg, orig, ud0="00000011"):
    return "  %s dispatch op 16 at %d: pgm 0x%s ud0-3 %s 0 0 0 ud4-7 0 base1 0x0 +0x0 len 3 job %d seg %d orig %d" % (kind, at, pgm, ud0, job, seg, orig)


ACB = ["job 1 acb: 100 dwords, 1 segments, ring 0, previous job dcb", "  job 1 seg 0: off 0 prefix 0 n 100 prefix ud0 none", dis("acb", 42, "11d03a3500", 1, 0, 42, "11d00860")]


def job(prefix, ud0, n=12673, orig=13, prev="acb", seg_count=1):
    return ["job 2 dcb: %d dwords, %d segments, ring 0, previous job %s" % (n + prefix, seg_count, prev),
            "  job 2 seg 0: off 0 prefix %d n %d prefix ud0 %s" % (prefix, n, ud0),
            dis("dcb", orig + prefix, "909977100", 2, 0, orig)]


# OFF and ON at the head after an acb.
out = c.report(ACB + job(0, "none"))
assert out[-1] == "buffers 1, direct 1", out
assert "prefix 0 dwords, prefix ud0 none, last acb ud0 0x11d00860: DIRECT" in out[0], out
out = c.report(ACB + job(58, "00000011"))
assert out[-1] == "buffers 1, direct 1", out
assert "prefix 58 dwords, prefix ud0 00000011" in out[0], out
# A dcb in front: not direct.
out = c.report(ACB + job(0, "none", prev="dcb"))
assert out[-1] == "buffers 1, direct 0", out
# Another buffer at offset 22 behind the CS prefix: J3 counted it, J4 does not.
out = c.report(ACB + job(58, "00000011", n=3899, orig=22))
assert out[-1] == "buffers 0, direct 0", out
# The right offset in a buffer of another size: not this buffer.
out = c.report(ACB + job(0, "none", n=9000))
assert out[-1] == "buffers 0, direct 0", out
# Mid-chain.
mid = ["job 2 dcb: 13000 dwords, 2 segments, ring 0, previous job acb", "  job 2 seg 0: off 0 prefix 0 n 300 prefix ud0 none",
       "  job 2 seg 1: off 300 prefix 0 n 12673 prefix ud0 none", dis("dcb", 5, "909974400", 2, 0, 5), dis("dcb", 313, "909977100", 2, 1, 13)]
out = c.report(ACB + mid)
assert out[-1] == "buffers 1, direct 0", out
# No identity.
assert c.report(["  dcb dispatch op 16 at 13: pgm 0x909977100 ud0-3 00000011 0 0 0 ud4-7 0 base1 0x0 +0x0 len 3"])[-1].startswith("verdict: eligibility unverified")
print("ok: 7 cases")
