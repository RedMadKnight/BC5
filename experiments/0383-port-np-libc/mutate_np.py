"""PORT-NP: do the tests catch a damaged fix? Each mutant undoes one part of the fix in a copy of the fixed unit.

usage: mutate_np.py <fixed libNpCppWebApi.cpp> <host tree> <out dir>
Exit 0 if every mutant fails at least one case of NpAliasTests.
"""
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
MUTANTS = {
    "m1-leak-on-failed-growth": ("\t\tstd::free(copy.buffer);\n\t\treturn -1;", "\t\treturn -1;"),
    "m2-no-reference-taken": ("if (copy.object != nullptr) ReferenceCount(copy.object, ReferenceCountOffset).fetch_add(1);\n", "\n"),
    "m3-reference-through-element": ("if (copy.object != nullptr) ReferenceCount(copy.object, ReferenceCountOffset).fetch_add(1);",
                                     "if (element->object != nullptr) ReferenceCount(element->object, ReferenceCountOffset).fetch_add(1);"),
    "m4-grow-branch-falls-through": ("        self->bufferSize = capacity;\n        return 0;\n", "        self->bufferSize = capacity;\n"),
    "m5-memcpy-without-growth": ("    std::memmove(self->buffer + oldLength, text, textLength + 1);", "    std::memcpy(self->buffer + oldLength, text, textLength + 1);"),
    "m6-copy-after-free": ("        std::memmove(buffer + oldLength, text, textLength + 1);\n        std::free(self->buffer);",
                           "        std::free(self->buffer);\n        std::memmove(buffer + oldLength, text, textLength + 1);"),
    "m7-shallow-string-copy": ("\tcopy.buffer         = nullptr;\n\tcopy.bufferSize     = 0;\n\tif (element->buffer != nullptr) {",
                               "\tif (false) {"),
}


def main():
    fixed, host, out = sys.argv[1:4]
    out = pathlib.Path(out)
    text = pathlib.Path(fixed).read_bytes().decode("utf-8")
    survivors = []
    for name, (old, new) in MUTANTS.items():
        assert text.count(old) == 1, name
        unit = out / name / "unit" / "libs"
        unit.mkdir(parents=True, exist_ok=True)
        (unit / "libNpCppWebApi.cpp").write_bytes(text.replace(old, new).encode("utf-8"))
        r = subprocess.run([sys.executable, str(HERE / "run_np_laptop.py"), name, str(unit.parent), host, str(out / name), "--no-0328"],
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace")
        failed = [line.split()[0] for line in r.stdout.splitlines() if " FAIL " in line]
        print(f"{name}: rc={r.returncode}, {len(failed)} case(s) fail: {' '.join(failed[:6])}")
        if r.returncode == 3 or not failed:
            survivors.append(name)
    print("all mutants caught" if not survivors else f"SURVIVED: {survivors}")
    return 1 if survivors else 0


if __name__ == "__main__":
    sys.exit(main())
