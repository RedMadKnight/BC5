#!/usr/bin/env python3
"""BC5 experiment 0401 series e, switch 1, lesson R32 on the laptop: each of the ten mangled names mknp0401.py adds hashes
to the NID it is registered under. The calculator is exp 0327's (the public host algorithm: SHA-1 of the name and the
salt, the first 8 bytes little-endian in a 64-character alphabet), self-checked first on a known pair.
usage: python nid0401.py   (beside mknp0401.py)"""
import hashlib
import importlib.util
import pathlib

SALT = bytes.fromhex("518d64a635ded8c1e6b039b1c3e55230")
CODES = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+-"


def nid(name):
    digest = int.from_bytes(hashlib.sha1(name.encode() + SALT).digest()[:8], "little")
    return "".join(CODES[(digest >> (58 - i * 6)) & 63] for i in range(10)) + CODES[(digest & 15) * 4]


def main():
    for name, want in (("strcmp", "Ovb2dSJOAuE"), ("strncmp", "aesyjrHVWy4"), ("strcpy_s", "5Xa2ACNECdo")):
        assert nid(name) == want, (name, nid(name), want)
    spec = importlib.util.spec_from_file_location("mknp0401", pathlib.Path(__file__).resolve().parent / "mknp0401.py")
    mk = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mk)
    ok = 0
    for want, name, _, _ in mk.TEN:
        got = nid(name)
        if got == want:
            ok += 1
        else:
            print("MISMATCH", want, got, name[:80])
    assert len(mk.TEN) == 10
    print(f"nid0401: {ok} of {len(mk.TEN)}" + ("; end" if ok == len(mk.TEN) else ""))
    raise SystemExit(0 if ok == len(mk.TEN) else 1)


if __name__ == "__main__":
    main()
