#!/usr/bin/env python3
"""BC5 experiment 0413: exp 0401 series e's NpCppWebApi SessionManager V2 (mknp0401.py) for both shared builds, on by
default. The ten functions and their registration are mknp0401.py's, byte for byte; only the switch changes: the ten
are registered unless KYTY_BC5_NP_SESSION_V2 is set to 0 (the rollback without a rebuild). The input is the patched
tree's src/libs/libNpCppWebApi.cpp (exp 0328's port, md5 7c40b784). Prints the output's md5.
usage: mknp0413.py <unit in> <unit out>"""
import hashlib
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "0401-mesa-preamble-switches"))
import mknp0401 as np  # noqa: E402

IN_MD5 = "7c40b784e36ef45e816be07b0a3fb0a8"

OLD_HEAD = np.HEAD.encode()
NEW_HEAD = OLD_HEAD.replace(
    b"// taken from 27c88a8, does not have; at 27c88a8 its body was `return 0`. Registered only with KYTY_BC5_NP_SESSION_V2\n"
    b"// on (InitNpCppWebApi_1). Lesson R32: name -> NID (nid0401.py) -> SymbolDatabase after InitAll -> function\n"
    b"// (npgate0401.cpp).",
    b"// taken from 27c88a8, does not have; at 27c88a8 its body was `return 0`. In both shared builds since exp 0413,\n"
    b"// registered unless KYTY_BC5_NP_SESSION_V2=0 (InitNpCppWebApi_1). Lesson R32: name -> NID (nid0401.py) ->\n"
    b"// SymbolDatabase after InitAll -> function (npgate0401.cpp).")

OLD_SWITCH = np.REG_HEAD.encode()
NEW_SWITCH = (
    "\n"
    "\t// Experiment 0413 (both shared builds; from exp 0401 series e): the ten SessionManager V2 entry points above, on\n"
    "\t// by default. KYTY_BC5_NP_SESSION_V2=0 leaves the ten NIDs unregistered, so the loader answers them with its\n"
    "\t// return-0 stub as before 0413. Read here, not cached.\n"
    "\t{\n"
    "\t\tconst char* v2 = std::getenv(\"KYTY_BC5_NP_SESSION_V2\");\n"
    "\t\tconst bool  on = v2 == nullptr || std::strcmp(v2, \"0\") != 0;\n"
    "\t\t{\n"
    "\t\t\tCommon::HostException::RawLog log;\n"
    "\t\t\tlog.Append(on ? \"[bc5] NpCppWebApi SessionManager V2 on (10 exports registered)\\n\"\n"
    "\t\t\t              : \"[bc5] NpCppWebApi SessionManager V2 off (KYTY_BC5_NP_SESSION_V2=0, the loader's stubs)\\n\");\n"
    "\t\t\tlog.Flush();\n"
    "\t\t}\n"
    "\t\tif (on) {\n").encode()


def edit(s):
    assert hashlib.md5(s).hexdigest() == IN_MD5, ("not exp 0328's unit", hashlib.md5(s).hexdigest())
    s = np.edit(s)
    assert s.count(OLD_HEAD) == 1 and s.count(OLD_SWITCH) == 1
    assert NEW_HEAD != OLD_HEAD, "the head's switch sentence moved in mknp0401.py"
    s = s.replace(OLD_HEAD, NEW_HEAD).replace(OLD_SWITCH, NEW_SWITCH)
    assert b"default off" not in s.split(b"// ---- experiment 0401 series e", 1)[1][:4000]
    return s


def main():
    assert len(sys.argv) == 3, __doc__
    with open(sys.argv[1], "rb") as f:
        s = f.read()
    out = edit(s)
    with open(sys.argv[2], "wb") as f:
        f.write(out)
    print(hashlib.md5(out).hexdigest())


if __name__ == "__main__":
    main()
