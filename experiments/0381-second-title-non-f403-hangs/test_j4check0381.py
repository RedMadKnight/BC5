#!/usr/bin/env python3
# BC5 exp 0381: j4check0381.py on synthetic journals, with Codex's interleaving case. usage: python test_j4check0381.py
import j4check0381 as c


def dis(kind, at, pgm, job, seg, orig, ud0="00000011"):
    return "  %s dispatch op 16 at %d: pgm 0x%s ud0-3 %s 0 0 0 ud4-7 0 base1 0x0 +0x0 len 3 job %d seg %d orig %d" % (kind, at, pgm, ud0, job, seg, orig)


def acb(j, final, prev="dcb"):
    return ["job %d acb: 100 dwords, 1 segments, ring 0, previous job %s %d, final ud0 %s" % (j, prev, j - 1, final),
            "  job %d seg 0: off 0 prefix 0 n 100 prefix ud0 none" % j]


def dcbhead(j, prefix, ud0, n=12673, prev="acb", segs=1):
    return ["job %d dcb: %d dwords, %d segments, ring 0, previous job %s %d, final ud0 -" % (j, n + prefix, segs, prev, j - 1),
            "  job %d seg 0: off 0 prefix %d n %d prefix ud0 %s" % (j, prefix, n, ud0)]


def target(j, prefix=0, orig=13):
    return [dis("dcb", orig + prefix, "909977100", j, 0, orig)]


A = acb(1, "11d00860") + [dis("acb", 42, "11d03a3500", 1, 0, 42, "11d00860")]
# OFF and ON at the head after an acb.
out = c.report(A + dcbhead(2, 0, "none") + target(2))
assert out[-1] == "buffers 1, direct 1, exposed 1", out
assert "prefix 0 dwords, prefix ud0 none, inherited 11d00860: EXPOSED" in out[0], out
out = c.report(A + dcbhead(2, 58, "00000011") + target(2, 58))
assert out[-1] == "buffers 1, direct 1, exposed 1", out
assert "prefix 58 dwords, prefix ud0 00000011, inherited 11d00860" in out[0], out
# Codex's case: a later acb between the header and the dispatch line: job 2's predecessor is job 1, not job 3.
out = c.report(A + dcbhead(2, 0, "none") + acb(3, "00000022") + [dis("acb", 42, "11d03a3500", 3, 0, 42, "00000022")] + target(2))
assert "inherited 11d00860: EXPOSED" in out[0], out
# The final state, not the last dispatch: the dispatch line says 11d00860, the job ends on 0x11: not exposed.
out = c.report(acb(1, "00000011") + [dis("acb", 42, "11d03a3500", 1, 0, 42, "11d00860")] + dcbhead(2, 0, "none") + target(2))
assert out[-1] == "buffers 1, direct 1, exposed 0", out
assert "inherited 00000011: DIRECT" in out[0], out
# A small acb with no write in front: walk back to the one that wrote.
out = c.report(A + acb(2, "none", prev="acb") + dcbhead(3, 0, "none") + target(3))
assert "inherited 11d00860: EXPOSED" in out[0], out
# Unknown stays unknown, and never counts as exposed.
out = c.report(acb(1, "unknown") + dcbhead(2, 0, "none") + target(2))
assert "inherited UNKNOWN: DIRECT" in out[0] and out[-1].endswith("exposed 0"), out
# The predecessor job missing from the journal: unknown.
out = c.report(acb(5, "11d00860")[:0] + dcbhead(2, 0, "none") + target(2))
assert "inherited UNKNOWN: DIRECT" in out[0], out
# A dcb behind the empty acb: no acb's value is carried.
out = c.report(["job 1 dcb: 9 dwords, 1 segments, ring 0, previous job none 0, final ud0 -"] + acb(2, "none") + dcbhead(3, 0, "none") + target(3))
assert "inherited dcb: DIRECT" in out[0] and out[-1].endswith("exposed 0"), out
# A dcb in front: not direct.
out = c.report(A + dcbhead(2, 0, "none", prev="dcb") + target(2))
assert out[-1] == "buffers 1, direct 0, exposed 0", out
# Another buffer at offset 22 behind the CS prefix, and offset 13 in a buffer of another size: not this buffer.
assert c.report(A + dcbhead(2, 58, "00000011", n=3899) + target(2, 58, 22))[-1] == "buffers 0, direct 0, exposed 0"
assert c.report(A + dcbhead(2, 0, "none", n=9000) + target(2))[-1] == "buffers 0, direct 0, exposed 0"
# Mid-chain.
mid = ["job 2 dcb: 13000 dwords, 2 segments, ring 0, previous job acb 1, final ud0 -", "  job 2 seg 0: off 0 prefix 0 n 300 prefix ud0 none",
       "  job 2 seg 1: off 300 prefix 0 n 12673 prefix ud0 none", dis("dcb", 5, "909974400", 2, 0, 5), dis("dcb", 313, "909977100", 2, 1, 13)]
assert c.report(A + mid)[-1] == "buffers 1, direct 0, exposed 0"
# No identity.
assert c.report(["  dcb dispatch op 16 at 13: pgm 0x909977100 ud0-3 00000011 0 0 0 ud4-7 0 base1 0x0 +0x0 len 3"])[-1].startswith("verdict: eligibility unverified")
print("ok: 13 cases")
