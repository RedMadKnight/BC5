"""PORT-LIBC: names against NIDs, independent of the host's C++.

usage: check_nids.py <host tree>

Recomputes each NID from the public algorithm (the salt and the method of exp 0328's nidcalc.pl; 4 known pairs as a
self-check) and reads the registrations from src/libs. For every LIB_FUNC in InitLibcInternal_1 whose wrapper carries a
plain C name it says whether the NID is that name's. Then the four NIDs of PORT-LIBC: each must appear exactly as
expected, in one place only, in all of src/libs. Exit 0 if the four are right; other mismatches are printed and not
fixed (they are outside PORT-LIBC).
"""
import base64
import collections
import hashlib
import pathlib
import re
import sys

SALT = bytes.fromhex("518d64a635ded8c1e6b039b1c3e55230")
EXPECTED = {"Ovb2dSJOAuE": "strcmp", "aesyjrHVWy4": "strncmp", "kiZSXIWd9vg": "strcpy"}
NOT_REGISTERED = {"5Xa2ACNECdo": "strcpy_s"}


def nid(name):
    digest = hashlib.sha1(name.encode() + SALT).digest()
    return base64.b64encode(digest[:8][::-1]).decode().rstrip("=").replace("/", "-")


def main():
    for name, value in {"sceKernelSyncOnAddressWait8": "dFym5b41JLU", "getrusage": "hHlZQUnlxSM",
                        "sceKernelTruncate": "WlyEA-sLDf0", "fsync": "juWbTNM+8hw", **{v: k for k, v in EXPECTED.items()},
                        "strcpy_s": "5Xa2ACNECdo"}.items():
        assert nid(name) == value, (name, nid(name), value)
    print("self-check ok: 4 known pairs and the 4 PORT-LIBC names")

    src = pathlib.Path(sys.argv[1]) / "src" / "libs"
    registrations = collections.defaultdict(list)
    for path in sorted(src.rglob("*")):
        if path.suffix not in (".cpp", ".h", ".inc"):
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            m = re.match(r'\s*LIB_(?:FUNC|OBJECT)\("([^"]+)",\s*([^)]+)\)', line)
            if m:
                registrations[m.group(1)].append((path.name, number, m.group(2).strip()))

    bad = 0
    for value, name in EXPECTED.items():
        got = registrations.get(value, [])
        ok = got and len(got) == 1 and got[0][0] == "libC.cpp" and got[0][2] == f"LibcInternal::{name}"
        print(f"{value} {name}: {'ok' if ok else 'WRONG'} {got}")
        bad += not ok
    for value, name in NOT_REGISTERED.items():
        got = registrations.get(value, [])
        print(f"{value} {name}: {'not registered: ok' if not got else f'WRONG {got}'}")
        bad += bool(got)

    table = (src / "libC.cpp").read_text(encoding="utf-8", errors="replace")
    block = re.search(r"LIB_DEFINE\(InitLibcInternal_1\) \{(.*?)^\}", table, re.S | re.M).group(1)
    checked, others = 0, []
    for value, wrapper in re.findall(r'LIB_FUNC\("([^"]+)",\s*LibcInternal::(\w+)\)', block):
        checked += 1
        if nid(wrapper) != value:
            others.append(f"{value} -> {wrapper} (its NID would be {nid(wrapper)})")
    print(f"InitLibcInternal_1: {checked} LibcInternal:: registrations, {len(others)} not under their wrapper's name:")
    for line in others:
        print("  " + line)
    print("PASS" if bad == 0 else "FAIL")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
