#!/usr/bin/env python3
"""BC5 experiment 0401: the private launcher, the shared play-pkg.sh with its binary and its two logs moved. Saves, settings
and the learned file stay the shared ones: this is for the maintainer's play. There is no private lean build, so the lean
branch refuses. Each line must occur exactly once.
usage: launcher0401.py <play-pkg.sh> <out>"""
import sys

E = "~/bc5-work/exp0401"
EDITS = (
    ("EMU=~/bc5-work/kytyplus-build/src/kyty_emulator", f"EMU={E}/bin/kyty_emulator  # exp 0401: the private build"),
    ("LOG=~/bc5-work/play-pkg-last.log", f"LOG={E}/play-last.log  # exp 0401: own log"),
    ("MLOG=~/bc5-work/play-pkg-mount.log", f"MLOG={E}/play-pkg-mount.log  # exp 0401: own mount log"),
    ("  EMU=~/bc5-work/kytyplus-build-lean/src/kyty_emulator LOG=~/bc5-work/play-pkg-lean-last.log",
     '  echo "exp 0401: there is no private lean build"; exit 1'),
)


def derive(text):
    lines = text.split("\n")
    for old, new in EDITS:
        at = [k for k, l in enumerate(lines) if l == old]
        assert len(at) == 1, (old, len(at))
        lines[at[0]] = new
    out = "\n".join(lines)
    for shared in ("kytyplus-build/src/kyty_emulator", "kytyplus-build-lean/src/kyty_emulator", "bc5-work/play-pkg-last.log", "bc5-work/play-pkg-mount.log"):
        code = "\n".join(l for l in out.split("\n") if not l.lstrip().startswith("#"))
        assert shared not in code, (shared, "is still used")
    return out


def main():
    with open(sys.argv[1], encoding="utf-8", newline="") as f:
        text = f.read()
    with open(sys.argv[2], "w", encoding="utf-8", newline="") as f:
        f.write(derive(text))


if __name__ == "__main__":
    main()
