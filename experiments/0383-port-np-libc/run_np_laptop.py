"""PORT-NP on the laptop: build NpAliasTests and exp 0328's NpCppWebApiTests against one version of the real unit.

usage: run_np_laptop.py <label> <dir holding libs/libNpCppWebApi.cpp> <host tree> <out dir> [--no-0328]

Compiler: the LLVM of Visual Studio 18 (x86_64-pc-windows-msvc), so KYTY_SYSV_ABI is the real SysV attribute, with
AddressSanitizer. The host headers the unit needs beyond common/abi.h come from laptop-shim/ (the tree has no
submodules here), so this is not the Linux host build: that is the box plan in README.md.
One process per case: an ASan abort ends only that case. Exit 0 only if every case and exp 0328's tests passed.
"""
import os
import pathlib
import re
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
LLVM = pathlib.Path(r"C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\Llvm\x64")
CLANG = LLVM / "bin" / "clang++.exe"
REPO = HERE.parent.parent
os.environ["PATH"] = str(LLVM / "lib" / "clang" / "22" / "lib" / "windows") + os.pathsep + os.environ["PATH"]


def run(args, out, **kw):
    r = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace", **kw)
    out.write_text(r.stdout, encoding="utf-8")
    return r.returncode, r.stdout


def main():
    label, unit_dir, host, out = sys.argv[1:5]
    with_0328 = "--no-0328" not in sys.argv
    out = pathlib.Path(out)
    out.mkdir(parents=True, exist_ok=True)
    flags = ["-std=c++20", "-O1", "-g", "-fsanitize=address", "-Wall", "-Wextra", "-Wno-unused-function",
             "-Wno-unused-parameter", "-Wno-unused-variable", "-Wno-return-type-c-linkage", "-Wno-deprecated-declarations",
             "-Wno-macro-redefined", "-D_CRT_SECURE_NO_WARNINGS", "-I", unit_dir, "-I", str(HERE / "laptop-shim"),
             "-I", str(pathlib.Path(host) / "src")]
    symdb = str(pathlib.Path(host) / "src" / "loader" / "symbolDatabase.cpp")
    exe = out / f"NpAliasTests-{label}.exe"
    rc, text = run([str(CLANG), *flags, str(HERE / "NpAliasTests.cpp"), symdb, "-o", str(exe)], out / f"{label}-build.txt")
    print(f"{label}: NpAliasTests build rc={rc}")
    if rc != 0:
        print(text[:3000])
        return 3
    rc, listing = run([str(exe), "list"], out / f"{label}-list.txt")
    cases = listing.split()
    failures = 0
    lines = []
    for case in cases:
        rc, text = run([str(exe), case], out / f"{label}-case-{case}.txt", timeout=300)
        m = re.search(r"AddressSanitizer: ([\w-]+)", text)
        verdict = "PASS" if rc == 0 else "FAIL"
        lines.append(f"{case:48} {verdict} rc={rc}" + (f" asan={m.group(1)}" if m else ""))
        failures += rc != 0
    summary = f"{label}: {len(cases) - failures}/{len(cases)} cases pass"
    (out / f"{label}-summary.txt").write_text("\n".join(lines + [summary]) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print(summary)
    if with_0328:
        # exp 0328's own tests, untouched, against the same unit
        test = REPO / "experiments" / "0328-npcppwebapi-port" / "NpCppWebApiTests.cpp"
        unit = pathlib.Path(unit_dir) / "libs" / "libNpCppWebApi.cpp"
        exe2 = out / f"NpCppWebApiTests-{label}.exe"
        rc, text = run([str(CLANG), *flags, str(test), str(unit), symdb, "-o", str(exe2)], out / f"{label}-0328-build.txt")
        print(f"{label}: 0328 build rc={rc}")
        if rc != 0:
            print(text[:3000])
            return 4
        rc, text = run([str(exe2)], out / f"{label}-0328-run.txt")
        print(f"{label}: 0328 run rc={rc}: {(text.strip().splitlines() or ['<no output>'])[-1]}")
        failures += rc != 0
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
