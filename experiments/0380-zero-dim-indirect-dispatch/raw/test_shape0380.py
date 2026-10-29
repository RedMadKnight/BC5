#!/usr/bin/env python3
# BC5 experiment 0380 (F608): synthetic checks of shape0380.py's prefix boundary and draw test, CPU only, no private
# data. The first two cases are the Codex review's counterexamples (REVIEW-01 R2, test_review01_shape.py), which the
# F601 version of the script failed.
# usage: python test_shape0380.py
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).with_name("shape0380.py")


def pkt(op, *payload):
    return [0xC0000000 | ((len(payload) - 1) << 16) | (op << 8), *payload]


HEAD = pkt(0x28, 0x80000000, 0x80000000) + pkt(0x12, 0)  # the host prefix's CONTEXT_CONTROL and CLEAR_STATE


def run(words):
    with tempfile.TemporaryDirectory(prefix="bc5-shape-") as temp:
        f = Path(temp) / "synthetic.bin"
        f.write_bytes(struct.pack("<%dI" % len(words), *words))
        return subprocess.check_output([sys.executable, str(SCRIPT), str(f)], text=True)


class Shape(unittest.TestCase):
    def test_review_case_restored_tf_high_in_the_register_replay(self):
        w = HEAD + pkt(0x79, 0x261, 0x11)  # a stored UCONFIG 0x261 replayed with the registers
        w += pkt(0x11, 1, 0x1000, 0x11) + pkt(0x26, 0x2000, 0x12)  # the packet state
        w += pkt(0x79, 0x250, 0x200000) + pkt(0x79, 0x261, 0x11)  # tf_ring_prefix
        w += pkt(0x16, 0, 0x41)  # the title: a dispatch with no SET_BASE of its own
        r = run(w)
        self.assertIn("title_at=21 amb=0", r)
        self.assertIn("first_sb1=- shapeB=1", r)

    def test_review_case_dispatch_direct_is_not_a_draw(self):
        self.assertIn("draws=0", run(pkt(0x15, 1, 1, 1, 0x41)))

    def test_the_b_dumps_layout(self):
        # the B dumps: replay, SET_BASE 1, INDEX_BASE, INDEX_BUFFER_SIZE, NUM_INSTANCES, then 0x24e, 0x250, 0x261
        w = HEAD + pkt(0x79, 0x383, 1, 2) + pkt(0x79, 0x41D, 1, 2, 3)
        tail = pkt(0x11, 1, 0x1000, 0x11) + pkt(0x26, 0x2000, 0x12) + pkt(0x13, 0xFFFFFFFF) + pkt(0x2F, 1)
        tail += pkt(0x79, 0x24E, 0x3FFF) + pkt(0x79, 0x250, 0x200000) + pkt(0x79, 0x261, 0x11)
        title = pkt(0x58, 0, 0, 0, 0, 0, 0x280) + pkt(0x16, 0, 0x41) + pkt(0x11, 1, 0x3000, 0x11) + pkt(0x16, 0x40, 0x41)
        r = run(w + tail + title)
        self.assertIn("title_at=%d amb=0" % (len(w) + len(tail)), r)
        self.assertIn("shapeB=1", r)

    def test_a_title_that_opens_with_its_own_set_base(self):
        w = HEAD + pkt(0x11, 1, 0x1000, 0x11) + pkt(0x79, 0x24E, 0x3FFF, 0) + pkt(0x79, 0x250, 0x200000) + pkt(0x79, 0x261, 0x11)
        at = len(w)
        w += pkt(0x11, 1, 0x3000, 0x11) + pkt(0x16, 0, 0x41)
        r = run(w)
        self.assertIn("title_at=%d amb=0" % at, r)
        self.assertIn("first_sb1=%d shapeB=0" % at, r)

    def test_no_tf_registers_is_ambiguous(self):
        w = HEAD + pkt(0x11, 1, 0x1000, 0x11) + pkt(0x26, 0x2000, 0x12) + pkt(0x16, 0, 0x41)
        self.assertIn("amb=1", run(w))


if __name__ == "__main__":
    unittest.main(verbosity=2)
