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
    # --compare: B's dot at (40,40) sits at one of A's dots (A = 0002 alone), the other B shot's (16,16) does not
    a, b = root / "a", root / "b"
    a.mkdir(); b.mkdir()
    Image.fromarray(second).save(a / "0001.png")
    Image.fromarray(first).save(b / "0001.png")
    Image.fromarray(second).save(b / "0002.png")
    out = run("--compare", str(a), str(b))
    assert "0001.png: dots 1, 0 of them" in out and "0002.png: dots 1, 1 of them" in out, out
    assert "median share of B's dots at A's dots 0.50" in out, out
    # SHEET: a contact sheet of the dots is written where asked (a synthetic image here)
    p = subprocess.run([sys.executable, str(script), str(b)], capture_output=True, text=True, env={**os.environ, "SHEET": str(root / "sheet.png")})
    assert p.returncode == 0 and "# sheet: 2 dots" in p.stdout and (root / "sheet.png").stat().st_size > 0, p.stdout + p.stderr
    assert "# reading: few or no dots" in p.stdout, p.stdout
    # --transient: lamps that drift with the camera are matched after alignment; a dot of one frame is alone
    rng = np.random.default_rng(382)
    bg = np.clip(40 + 14 * rng.standard_normal((180, 320)), 0, 255)
    bg[30:60, 40:120] = 90
    bg[110:140, 200:280] = 15
    lamps = [(30, 30), (60, 150), (90, 250), (150, 90), (140, 300)]
    t3 = root / "t"
    t3.mkdir()
    for i, ((dy, dx), one) in enumerate(zip([(0, 0), (2, -3), (-1, 4), (3, 1)], [(20, 200), (100, 60), (170, 180), (50, 300)])):
        f = bg.copy()
        for yy, xx in lamps:
            f[yy, xx] = 255
        f = np.roll(f, (dy, dx), axis=(0, 1))
        f[one] = 255
        Image.fromarray(np.repeat(f[:, :, None], 3, 2).astype(np.uint8)).save(t3 / ("%04d.png" % i))
    out = run("--transient", str(t3))
    assert all(": dots 6, alone 1 (neutral 1, size <= 3: 1)" in l for l in out.splitlines() if l.startswith("  000")), out
    assert "alone per shot median 1, max 1 of median 6 dots" in out and "+2,-3" in out, out
print("test_dots0382 ok: two different frames with equal mean and count both used; an exact repeat dropped; ROI counts"
      " inside its region only; --compare; SHEET; --transient; selftest ok")
