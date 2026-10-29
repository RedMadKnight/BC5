#!/usr/bin/env python3
# BC5 experiment 0382: regression test for dots0382.py's frame identity, after the Codex review (REVIEW-03, R2), whose
# counterexample this is. Two different synthetic frames with the same mean luma and the same dot count (one dot at
# (16,16), one at (40,40)) were taken as "same as before" while the identity was the pair (mean, count); with the
# SHA-256 of the decoded RGB pixels both are used, and an exact repeat is still dropped. Synthetic images only, in a
# temporary directory; runs dots0382.py --selftest as well.
# usage: python test_dots0382.py   (numpy and PIL; on the laptop without -I, on the box in the ubuntu distrobox)
import os, subprocess, sys, tempfile
from pathlib import Path
import numpy as np
from PIL import Image

script = Path(__file__).resolve().parent / "dots0382.py"


def run(*args):
    p = subprocess.run([sys.executable, str(script), *args], capture_output=True, text=True)
    assert p.returncode == 0, p.stderr
    return p.stdout


out = run("--selftest")
assert "selftest ok" in out, out
with tempfile.TemporaryDirectory(prefix="bc5-dots0382-") as t:
    root = Path(t)
    first = np.full((64, 64, 3), 26, dtype=np.uint8)
    second = first.copy()
    first[16, 16, :] = 255
    second[40, 40, :] = 255
    assert not np.array_equal(first, second) and first.mean() == second.mean()
    Image.fromarray(first).save(root / "0001.png")
    Image.fromarray(second).save(root / "0002.png")
    out = run(str(root))
    assert "2 shots, 2 used" in out and "same as before" not in out, out
    assert "kept 0 of them" in out, out
    Image.fromarray(second).save(root / "0003.png")
    out = run(str(root))
    assert "3 shots, 2 used" in out and out.count("same as before") == 1, out
    # ROI: only the dot at (40,40) lies in x 32-64, y 32-64
    p = subprocess.run([sys.executable, str(script), str(root)], capture_output=True, text=True, env={**os.environ, "ROI": "32,32,64,64"})
    assert p.returncode == 0, p.stderr
    lines = [l for l in p.stdout.splitlines() if l.startswith("  000")]
    assert lines[0].split(": dots ")[1].startswith("0 ") and lines[1].split(": dots ")[1].startswith("1 "), p.stdout
    assert "ROI 32,32,64,64" in p.stdout, p.stdout
print("test_dots0382 ok: two different frames with equal mean and count both used; an exact repeat dropped; ROI counts"
      " inside its region only; selftest ok")
