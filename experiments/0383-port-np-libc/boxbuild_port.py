# Exp 0383, PORT-NP / PORT-LIBC, the box's CPU check: run inside the ubuntu distrobox by boxcheck_port.sh, as exp 0328's
# build0328.py did. Compiles the two fixed units from the patched tree and the two unfixed ones from the shared tree, with
# the shared build's own flags, relinks a private kyty_emulator (never run), then builds and runs three test programs.
# Nothing shared is written. A pass is the last line of its output, "== PASS: ...", and exit 0; anything else is a failure.
# rc 0 from a program proves nothing here: each must also print its final line, and the NP cases must be the 30 of the
# manifest, 30 listed and 30 passed (Codex review REVIEW-PORTS-01).
# usage: boxbuild_port.py <compdb.json> <patched tree> <out dir> <shared build> <test dir> <shared tree>
import collections
import json
import os
import re
import shlex
import subprocess
import sys

UNITS = {
    "src/libs/libC.cpp": "src/CMakeFiles/kyty_emulator.dir/libs/libC.cpp.o",
    "src/libs/libNpCppWebApi.cpp": "src/CMakeFiles/kyty_emulator.dir/libs/libNpCppWebApi.cpp.o",
}
NP_OBJ = UNITS["src/libs/libNpCppWebApi.cpp"]
EXPECTED_CASES = 30
FINAL_0328 = "NpCppWebApiTests: all checks passed"
FINAL_LIBC = "LibcNidTests: all checks passed"
FINAL_CASE = "NpAliasTests: all checks passed (1 cases)"
WARNING = re.compile(r"^(?:.*[/\\])?([^/\\:]+):\d+:\d+: warning: (.*)$")


def read_manifest(path):
    with open(path, encoding="utf-8") as f:
        names = [line.strip() for line in f if line.strip()]
    if len(names) != EXPECTED_CASES or len(set(names)) != EXPECTED_CASES:
        raise SystemExit(f"== FAIL: the manifest holds {len(names)} names, {len(set(names))} unique, not {EXPECTED_CASES}")
    return names


def listing_error(manifest, listing):
    """None if the listing is exactly the manifest's names, once each; otherwise what is wrong."""
    names = listing.split()
    counts = collections.Counter(names)
    duplicates = sorted(n for n, c in counts.items() if c > 1)
    missing = sorted(set(manifest) - set(names))
    extra = sorted(set(names) - set(manifest))
    if len(names) == EXPECTED_CASES and not duplicates and not missing and not extra:
        return None
    return f"{len(names)} names listed, duplicates {duplicates}, missing {missing}, extra {extra}"


def has_line(output, line):
    return line in (text.rstrip("\r") for text in output.splitlines())


def program_ok(rc, output, final_line):
    return rc == 0 and has_line(output, final_line) and "FAILED" not in output


def case_ok(case, rc, output):
    return program_ok(rc, output, FINAL_CASE) and has_line(output, f"NpAliasTests: ok: {case}")


def warnings_of(output):
    """The compiler's warnings without their line numbers, since the fix moves lines."""
    found = collections.Counter()
    for line in output.splitlines():
        m = WARNING.match(line.rstrip("\r"))
        if m:
            found[f"{m.group(1)}: {m.group(2)}"] += 1
    return found


class RealExec:
    def __init__(self, build):
        self.build = build

    def run(self, argv, env=None):
        """Merged stdout and stderr, echoed to the log."""
        print("+", " ".join(argv)[:220], "...", flush=True)
        r = subprocess.run(["nice", "-n", "19"] + argv, cwd=self.build, env=env, stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT, text=True, errors="replace")
        print(r.stdout, end="", flush=True)
        return r.returncode, r.stdout

    def listing(self, binary, env):
        """stdout alone: a sanitizer's notes on stderr are not case names."""
        r = subprocess.run([binary, "list"], env=env, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
                           errors="replace")
        return r.returncode, r.stdout

    def write(self, path, text):
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)


def clean_compile(cmd):
    clean, skip = [], 0
    for a in shlex.split(cmd):
        if skip:
            skip -= 1
            continue
        if a in ("-MT", "-MF"):
            skip = 1
            continue
        if a == "-MD":
            continue
        clean.append(a)
    return clean


def compile_unit(ex, command, tree, rel, obj):
    clean = clean_compile(command)
    clean[clean.index("-o") + 1] = obj
    clean[clean.index("-c") + 1] = os.path.join(tree, rel)
    clean.insert(1, "-I" + os.path.join(tree, "src"))
    rc, output = ex.run(clean)
    return rc, output, clean


def main(args, ex):
    db_path, tree, out_dir, build, test_dir, shared_tree = args
    obj_dir = os.path.join(out_dir, "obj")
    os.makedirs(obj_dir, exist_ok=True)
    manifest = read_manifest(os.path.join(test_dir, "np-cases.manifest"))

    with open(db_path, encoding="utf-8") as f:
        db = json.load(f)
    commands = {e.get("output", ""): e["command"] for e in db}
    if "src/kyty_emulator" not in commands or any(unit not in commands for unit in UNITS.values()):
        print("== FAIL: the compdb lacks the link or a unit", flush=True)
        return 1

    objs, flags = {}, None
    base_warnings, fixed_warnings = collections.Counter(), collections.Counter()
    for rel, unit in UNITS.items():
        name = os.path.basename(rel)
        rc, output, _ = compile_unit(ex, commands[unit], shared_tree, rel, os.path.join(obj_dir, "base-" + name + ".o"))
        if rc != 0:
            print(f"== FAIL: baseline {name} does not compile, rc {rc}", flush=True)
            return 1
        base_warnings += warnings_of(output)
        obj = os.path.join(obj_dir, name + ".o")
        rc, output, flags = compile_unit(ex, commands[unit], tree, rel, obj)
        if rc != 0:
            print(f"== FAIL: {name} does not compile, rc {rc}", flush=True)
            return 1
        fixed_warnings += warnings_of(output)
        objs[unit] = obj

    new_warnings = fixed_warnings - base_warnings
    report = [f"baseline {sum(base_warnings.values())}, fixed {sum(fixed_warnings.values())}, new {sum(new_warnings.values())}"]
    report += [f"new: {count} x {text}" for text, count in sorted(new_warnings.items())]
    report += [f"baseline: {count} x {text}" for text, count in sorted(base_warnings.items())]
    ex.write(os.path.join(out_dir, "warnings.txt"), "\n".join(report) + "\n")
    print("== warnings:", report[0], flush=True)

    argv = [a for a in shlex.split(commands["src/kyty_emulator"]) if a not in (":", "&&")]
    replaced = 0
    for k, a in enumerate(argv):
        if a in objs:
            argv[k] = objs[a]
            replaced += 1
        elif a.startswith("-Wl,-Map="):
            argv[k] = "-Wl,-Map=" + os.path.join(out_dir, "kyty_emulator.map")
        elif a.startswith("--dependency-file="):
            argv[k] = "--dependency-file=" + os.path.join(out_dir, "link.d")
    if replaced != len(UNITS):
        print(f"== FAIL: units replaced {replaced} times", flush=True)
        return 1
    argv[argv.index("-o") + 1] = os.path.join(out_dir, "kyty_emulator")
    rc, _ = ex.run(argv)
    if rc != 0:
        print(f"== FAIL: the private emulator does not link, rc {rc}", flush=True)
        return 1
    print("== emulator linked (not run)", flush=True)

    cxx = argv[0]
    libs = [a for a in argv if a.startswith("-l") or a.startswith("-L") or a.endswith(".a") or a.endswith(".so")
            or a.startswith("-Wl,-rpath") or a.startswith("-pthread")]
    all_objs = [a for a in argv if a.endswith(".o") and not a.endswith("/main.cpp.o")]
    np_private = objs[NP_OBJ]

    def compile_test(src, extra=()):
        obj = os.path.join(obj_dir, os.path.basename(src) + "".join(e.strip("-=") for e in extra) + ".o")
        tc = list(flags) + list(extra)
        tc[tc.index("-o") + 1] = obj
        tc[tc.index("-c") + 1] = src
        rc, _ = ex.run(tc)
        return obj if rc == 0 else None

    def link_test(name, obj, objects, extra=()):
        if obj is None:
            return None
        binary = os.path.join(out_dir, name)
        rc, _ = ex.run([cxx, *extra, "-o", binary, obj] + objects + libs + ["-lpthread"])
        return binary if rc == 0 else None

    failures = []

    def run_program(name, src, final_line):
        binary = link_test(name, compile_test(os.path.join(test_dir, src)), all_objs)
        if binary is None:
            print(f"== {name} NO LINK", flush=True)
            failures.append(f"{name} did not build")
            return
        rc, output = ex.run([binary])
        ok = program_ok(rc, output, final_line)
        print(f"== {name} exit {rc}, final line {'seen' if has_line(output, final_line) else 'MISSING'}", flush=True)
        if not ok:
            failures.append(f"{name} rc {rc} without a clean final line")

    # 1. exp 0328's tests, untouched, against the fixed unit
    run_program("np_cpp_web_api_tests", "NpCppWebApiTests.cpp", FINAL_0328)
    # 2. the libc registrations through InitAll on the real SymbolDatabase
    run_program("libc_nid_tests", "LibcNidTests.cpp", FINAL_LIBC)

    # 3. the aliasing tests: the unit is inside the test, so its object stays out of the link. ASan where it links.
    others = [o for o in all_objs if o != np_private]
    src = os.path.join(test_dir, "NpAliasTests.cpp")
    asan = ("-fsanitize=address", "-fno-omit-frame-pointer")
    binary = link_test("np_alias_tests_asan", compile_test(src, asan), others, asan)
    sanitized = binary is not None
    if binary is None:
        print("== ASan link failed: the same tests with the tracker alone", flush=True)
        binary = link_test("np_alias_tests", compile_test(src), others)
    if binary is None:
        print("== np_alias_tests NO LINK", flush=True)
        failures.append("np_alias_tests did not build")
    else:
        env = dict(os.environ, ASAN_OPTIONS="detect_leaks=0:detect_odr_violation=0")  # the tracker counts leaks
        rc, listing = ex.listing(binary, env)
        error = f"the listing's rc is {rc}" if rc != 0 else listing_error(manifest, listing)
        if error is not None:
            print(f"== np_alias_tests listing: {error}", flush=True)
            failures.append(f"np_alias_tests listing: {error}")
        else:
            passed = []
            for case in manifest:
                rc, output = ex.run([binary, case], env=env)
                ok = case_ok(case, rc, output)
                print(f"== {case} exit {rc} {'pass' if ok else 'FAIL'}", flush=True)
                if ok:
                    passed.append(case)
            print(f"== np_alias_tests {'ASan' if sanitized else 'no ASan'}: {len(passed)}/{len(manifest)} cases pass", flush=True)
            if len(passed) != EXPECTED_CASES or set(passed) != set(manifest):
                failures.append(f"np_alias_tests {len(passed)}/{EXPECTED_CASES}")

    if new_warnings:
        failures.append(f"{sum(new_warnings.values())} new warning(s) in the two units")
    if failures:
        print("== FAIL: " + "; ".join(failures), flush=True)
        return 1
    print(f"== PASS: 0328 and libc final lines seen, np_alias_tests 30/30 {'ASan' if sanitized else 'no ASan'}, "
          f"new warnings 0 of {sum(fixed_warnings.values())}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:], RealExec(sys.argv[4])))
