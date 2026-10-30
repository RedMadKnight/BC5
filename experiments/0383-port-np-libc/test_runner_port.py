"""Exp 0383: synthetic tests of the box runner (REVIEW-PORTS-01). Laptop only: no SSH, no compiler, no box, no emulator.

usage: test_runner_port.py

Part A runs the real main() of boxbuild_port.py with a stand-in executor, so the whole flow runs with no compiler.
Part B runs the real boxcheck_port.sh in Git Bash inside a temporary directory: HOME there, stand-ins first on PATH for
pgrep, distrobox, ninja, python3 and the compilers, its own small KytyPlus repository and its own pins.env. Its
boxbuild_port.py is a stub, so part B tests the shell's gates; part A tests the build step's. The real HOME is not
touched: the harness refuses a HOME that is not under its temporary directory.

Every case states the outcome it needs; the table gives the real rc. Exit 0 if every case came out as expected.
"""
import hashlib
import importlib.util
import json
import os
import pathlib
import shutil
import subprocess
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
BASH = r"C:\Program Files\Git\bin\bash.exe"
spec = importlib.util.spec_from_file_location("boxbuild_port", HERE / "boxbuild_port.py")
bb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bb)
CASES = (HERE / "np-cases.manifest").read_text(encoding="utf-8").split()
rows = []


def record(part, name, expected, got, detail):
    ok = (got == 0) if expected == "pass" else (got != 0)
    rows.append(ok)
    print(f"{part} {name:44} want {expected:4} rc={got:<3} {'as expected' if ok else 'WRONG'}  {detail}")


class FakeExec:
    """The build step's world. The defaults are a run in which everything passes."""

    def __init__(self, listing=None, list_rc=0, outputs=None, warn_base="", warn_fixed="", link_rc=0, compile_rc=0):
        self.listing_text = "\n".join(CASES) + "\n" if listing is None else listing
        self.list_rc, self.outputs = list_rc, outputs or {}
        self.warn_base, self.warn_fixed = warn_base, warn_fixed
        self.link_rc, self.compile_rc = link_rc, compile_rc
        self.log, self.ran = [], []

    def run(self, argv, env=None):
        joined = " ".join(argv)
        if "-c" in argv:
            source = argv[argv.index("-c") + 1]
            text = self.warn_base if "/shared/" in source.replace("\\", "/") else self.warn_fixed
            return self.compile_rc, text if source.endswith(("libC.cpp", "libNpCppWebApi.cpp")) else ""
        if "-o" in argv:
            return self.link_rc, ""
        name = os.path.basename(argv[0])
        self.ran.append(argv)
        if name in ("np_cpp_web_api_tests", "libc_nid_tests"):
            final = bb.FINAL_0328 if name.startswith("np") else bb.FINAL_LIBC
            return self.outputs.get(name, (0, f"lots of output\n{final}\n"))
        case = argv[1]
        return self.outputs.get(case, (0, f"NpAliasTests: ok: {case}\n{bb.FINAL_CASE}\n"))

    def listing(self, binary, env):
        return self.list_rc, self.listing_text

    def write(self, path, text):
        pass


def part_a(tmp):
    root = tmp / "a"
    tests = root / "tests"
    tests.mkdir(parents=True)
    shutil.copy(HERE / "np-cases.manifest", tests)
    db = [{"output": unit, "command": f"cc -MD -MT x -MF y -o {unit} -c {rel}"} for rel, unit in bb.UNITS.items()]
    objects = " ".join(bb.UNITS.values())
    db.append({"output": "src/kyty_emulator", "command": f"cc {objects} src/CMakeFiles/kyty_emulator.dir/main.cpp.o -lz -o src/kyty_emulator"})
    (root / "compdb.json").write_text(json.dumps(db), encoding="utf-8")
    args = [str(root / "compdb.json"), str(root / "tree"), str(root / "out"), str(root / "build"), str(tests), str(root / "shared")]
    warn = "/x/src/libs/libC.cpp:{}:3: warning: unused thing [-Wunused]\n"

    def case(name, expected, **kw):
        ex = FakeExec(**kw)
        got = bb.main(args, ex)
        record("A", name, expected, got, f"{sum(1 for r in ex.ran if len(r) == 2)} case runs")
        return ex

    ex = case("correct result", "pass")
    assert sum(1 for r in ex.ran if len(r) == 2) == 30
    case("empty listing, rc 0", "fail", listing="")
    case("listing with a duplicate name", "fail", listing="\n".join(CASES[:29] + [CASES[0]]))
    case("listing with a name missing (29)", "fail", listing="\n".join(CASES[:29]))
    case("listing with a foreign name", "fail", listing="\n".join(CASES[:29] + ["not_in_the_manifest"]))
    case("listing with 31 names", "fail", listing="\n".join(CASES + ["not_in_the_manifest"]))
    case("listing's own rc non-zero", "fail", list_rc=1)
    case("one case fails, rc 1", "fail", outputs={CASES[3]: (1, f"NpAliasTests: FAILED: {CASES[3]}\n")})
    case("one case rc 0 without its final line", "fail", outputs={CASES[3]: (0, f"NpAliasTests: ok: {CASES[3]}\n")})
    case("one case rc 0 with another case's ok", "fail", outputs={CASES[3]: (0, f"NpAliasTests: ok: {CASES[4]}\n{bb.FINAL_CASE}\n")})
    case("libc interrupted: rc 0, no final line", "fail", outputs={"libc_nid_tests": (0, "guest EXIT before the checks\n")})
    case("libc FAILED line with the final line", "fail", outputs={"libc_nid_tests": (0, f"LibcNidTests: FAILED: x\n{bb.FINAL_LIBC}\n")})
    case("libc rc 1", "fail", outputs={"libc_nid_tests": (1, "")})
    case("0328 interrupted: rc 0, no final line", "fail", outputs={"np_cpp_web_api_tests": (0, "NpCppWebApiTests: ok: x\n")})
    case("a new warning in a fixed unit", "fail", warn_base=warn.format(1), warn_fixed=warn.format(1) + "/x/src/libs/libC.cpp:9:1: warning: fresh [-Wfresh]\n")
    case("the same warning on a moved line", "pass", warn_base=warn.format(1), warn_fixed=warn.format(5))
    case("the same warning once more", "fail", warn_base=warn.format(1), warn_fixed=warn.format(1) + warn.format(2))
    case("a unit does not compile", "fail", compile_rc=1)
    case("the private link fails", "fail", link_rc=1)


def sh(command, cwd, env):
    return subprocess.run([BASH, "-c", command], cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          text=True, errors="replace")


def posix(path):
    return subprocess.run(["cygpath", "-u", str(path)], stdout=subprocess.PIPE, text=True, check=False).stdout.strip() or str(path)


STUB_PASS = 'print("compiled"); print("== PASS: 0328 and libc final lines seen, np_alias_tests 30/30 ASan, new warnings 0 of 2")\n'
STUB_CUT = 'print("compiled"); print("== np_alias_tests ASan: 12/30 cases pass")\n'
STUB_FAIL = 'import sys; print("== FAIL: libc"); sys.exit(1)\n'
STUB_TOUCH = 'import sys; open(sys.argv[4] + "/src/kyty_emulator", "a").write("x"); ' + STUB_PASS


def part_b(tmp):
    def world(name):
        root = tmp / "b" / name
        home = root / "home"
        repo = root / "archive"
        shim = root / "shim"
        for d in (home / "src" / "KytyPlus", home / "bc5-work" / "kytyplus-build" / "src", shim,
                  repo / "backend" / "kytyplus-patches", repo / "experiments" / "0383-port-np-libc",
                  repo / "experiments" / "0328-npcppwebapi-port"):
            d.mkdir(parents=True)
        for tool, body in {
            "pgrep": "exit ${FAKE_PGREP_RC:-1}\n",
            "distrobox": 'shift 3; exec "$@"\n',
            "ninja": "echo '[{\"output\": \"src/kyty_emulator\"}]'\n",
            "clang++": "echo clang stand-in\n",
            "g++": "echo g++ stand-in\n",
            "python3": 'shift; exec python "$@"\n',
        }.items():
            (shim / tool).write_bytes(("#!/bin/sh\n" + body).encode())
        env = {k: v for k, v in os.environ.items() if k not in ("HOME",)}
        env["HOME"] = posix(home)
        env["PATH"] = posix(shim) + ":/usr/bin:/mingw64/bin:" + os.environ["PATH"]
        env["GIT_CONFIG_NOSYSTEM"] = "1"
        kyty = home / "src" / "KytyPlus"
        (kyty / "src" / "libs").mkdir(parents=True)
        (kyty / "src" / "bc5").mkdir()
        files = {"src/libs/libC.cpp": "base libc\n", "src/libs/libNpCppWebApi.cpp": "base np\n", "src/libs/other.cpp": "other\n"}
        for rel, text in files.items():
            (kyty / rel).write_bytes(text.encode())
        script = ("git init -q; git config core.autocrlf false; git config core.filemode false; git config user.name x; "
                  "git config user.email x@x; git add -A; git commit -qm base; git tag f266548")
        assert sh(script, kyty, env).returncode == 0
        # the shared tree: the tag plus "patch 0001" with exp 0372's piece; the fixed tree: that and the two fixes
        (kyty / "src" / "bc5" / "pad_audio_route.hpp").write_bytes(b"route\n")
        fixed = root / "fixed"
        shutil.copytree(kyty, fixed)
        (fixed / "src" / "libs" / "libC.cpp").write_bytes(b"fixed libc\n")
        (fixed / "src" / "libs" / "libNpCppWebApi.cpp").write_bytes(b"fixed np\n")
        marks = "".join(f"// exp 0372 mark {i}\n" for i in range(5))
        (fixed / "src" / "bc5" / "pad_audio_route.hpp").write_bytes(("route\n" + marks).encode())
        result = sh("git add -A; git diff --cached --no-color f266548", fixed, env)
        patch = repo / "backend" / "kytyplus-patches" / "0001-bc5-lle-agc.patch"
        patch.write_bytes(result.stdout.encode())
        tree = sh("git write-tree --prefix=src/", fixed, env).stdout.strip()
        (kyty / "src" / "bc5" / "pad_audio_route.hpp").write_bytes(("route\n" + marks).encode())
        shared = home / "bc5-work" / "kytyplus-build" / "src" / "kyty_emulator"
        shared.write_bytes(b"the shared binary\n")
        exp = repo / "experiments" / "0383-port-np-libc"
        shutil.copy(HERE / "boxcheck_port.sh", exp)
        for name2 in ("NpAliasTests.cpp", "LibcNidTests.cpp", "np-cases.manifest"):
            shutil.copy(HERE / name2, exp)
        (repo / "experiments" / "0328-npcppwebapi-port" / "NpCppWebApiTests.cpp").write_bytes(b"test\n")
        md5 = lambda p: hashlib.md5(p.read_bytes()).hexdigest()  # noqa: E731
        sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()  # noqa: E731
        (exp / "pins.env").write_text(
            f"PIN_PATCH_MD5={md5(patch)}\nPIN_SRC_TREE={tree}\nPIN_SHARED_MD5={md5(shared)}\n"
            f"PIN_BASE_LIBC_SHA256={sha(kyty / 'src/libs/libC.cpp')}\nPIN_BASE_NP_SHA256={sha(kyty / 'src/libs/libNpCppWebApi.cpp')}\n",
            encoding="utf-8", newline="\n")
        (exp / "boxbuild_port.py").write_text(STUB_PASS, encoding="utf-8")
        assert str(tmp) in str(home) and pathlib.Path(env["HOME"]).name == "home"
        return root, home, exp, env, kyty, shared, patch

    def case(name, expected, change=None, stub=STUB_PASS, extra_env=None, want=None):
        root, home, exp, env, kyty, shared, patch = world(name.replace(" ", "-").replace(",", "").replace(":", ""))
        (exp / "boxbuild_port.py").write_text(stub, encoding="utf-8")
        if change:
            change(kyty=kyty, shared=shared, patch=patch, home=home)
        env.update(extra_env or {})
        r = sh("bash ./boxcheck_port.sh", exp, env)
        out = r.stdout.strip().splitlines()
        last = out[-1] if out else ""
        lock = home / "bc5-work" / "BOX-LOCK"
        lock_left = lock.exists() and lock.read_text().strip() != "" and "MAINTAINER" not in lock.read_text()
        expected_tail = (expected == "pass") == (last == "boxcheck: PASS")
        record("B", name, expected, r.returncode, last[:70])
        if not expected_tail or lock_left or (want and want not in r.stdout):
            rows.append(False)
            print(f"  WRONG: last line, lock left {lock_left}, or no {want!r}\n  " + "\n  ".join(out[-12:]))

    def foreign(**k):
        (k["kyty"] / "src" / "libs" / "other.cpp").write_bytes(b"changed\n")

    def extra(**k):
        (k["kyty"] / "src" / "libs" / "new.cpp").write_bytes(b"new\n")

    def near_name(**k):
        (k["kyty"] / "src" / "libs" / "libC.cpp.bak").write_bytes(b"new\n")

    def base_changed(**k):
        (k["kyty"] / "src" / "libs" / "libC.cpp").write_bytes(b"another libc\n")

    def shared_changed(**k):
        k["shared"].write_bytes(b"a newer shared binary\n")

    def patch_changed(**k):
        k["patch"].write_bytes(k["patch"].read_bytes() + b"\n")

    def locked(**k):
        (k["home"] / "bc5-work" / "BOX-LOCK").write_text("MAINTAINER PLAYING\n")

    case("correct result", "pass")
    case("shared hash changed before", "fail", shared_changed, want="stop")
    case("shared hash changed during the run", "fail", stub=STUB_TOUCH, want="the shared binary changed")
    case("env cannot move the shared pin", "fail", shared_changed, extra_env={"EXPECT_NORMAL": "x", "PIN_SHARED_MD5": "x"})
    case("foreign source diff", "fail", foreign, want="beyond the two approved")
    case("foreign new file", "fail", extra, want="beyond the two approved")
    case("near name libC.cpp.bak", "fail", near_name, want="beyond the two approved")
    case("ACCEPT_TREE_DIFF=1 does nothing", "fail", foreign, extra_env={"ACCEPT_TREE_DIFF": "1"}, want="beyond the two approved")
    case("baseline libC.cpp not the pin", "fail", base_changed, want="pinned baseline")
    case("patch md5 changed", "fail", patch_changed, want="stop")
    case("build step rc 0 without its final line", "fail", stub=STUB_CUT, want="without the build step's final line")
    case("build step fails", "fail", stub=STUB_FAIL, want="rc is 1")
    case("an emulator runs", "fail", extra_env={"FAKE_PGREP_RC": "0"}, want="an emulator runs")
    case("box locked", "fail", locked, want="box locked")


def main():
    with tempfile.TemporaryDirectory(prefix="t0383-") as name:
        tmp = pathlib.Path(name)
        part_a(tmp)
        part_b(tmp)
        os.chdir(HERE)
    bad = rows.count(False)
    print(f"{len(rows)} checks, {bad} wrong")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
