#!/usr/bin/env python3
"""BC5 experiment 0430, F5 (the precise form) in the shared form, 2026-11-17.
    mkf5.py <tree root>
src/libs/bc5LleAgc.cpp of the shared tree as the swap of 07:10 left it (md5 b8afba59: patch a7c1653d's unit, unchanged by
exps 0431 and 0429) edited in place: its ho430 block (ho430.b8.cpp beside this script, the deployed text) replaced by
ho430.f5.cpp beside this script (F5 added: BC5_DIRECT_XQ_PRECISE, on unless "0"). No hook changes: F5 rides on F3's
f3_before_submit and job_submitted. Every anchor must match exactly once, or nothing is written."""
import hashlib
import os
import sys

BASE_MD5 = "b8afba59"
U = "src/libs/bc5LleAgc.cpp"


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: mkf5.py <tree root>")
        return 2
    path = os.path.join(sys.argv[1], U)
    data = open(path, "rb").read()
    md5 = hashlib.md5(data).hexdigest()[:8]
    if md5 != BASE_MD5:
        print(f"mkf5: {path} is {md5}, not the base {BASE_MD5}")
        return 1
    text = data.decode("utf-8", "surrogateescape")
    here = os.path.dirname(os.path.abspath(__file__))
    old = open(os.path.join(here, "ho430.b8.cpp"), encoding="utf-8").read()
    new = open(os.path.join(here, "ho430.f5.cpp"), encoding="utf-8").read()  # F5 alone (61bbe443); ho430.cpp has F6 since 12:20
    if hashlib.md5(old.encode()).hexdigest()[:8] != "c7dbe70b":
        print("mkf5: ho430.b8.cpp is not the deployed c7dbe70b")
        return 1
    if text.count(old) != 1:
        print(f"mkf5: the deployed ho430 block is found {text.count(old)} times, not once")
        return 1
    if "BC5_DIRECT_XQ_PRECISE" not in new or "kF5Skip" not in new:
        print("mkf5: ho430.cpp has no F5")
        return 1
    text = text.replace(old, new)
    out = text.encode("utf-8", "surrogateescape")
    open(path, "wb").write(out)
    print(f"mkf5: {BASE_MD5} -> {hashlib.md5(out).hexdigest()[:8]} (ho430 {hashlib.md5(new.encode()).hexdigest()[:8]})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
