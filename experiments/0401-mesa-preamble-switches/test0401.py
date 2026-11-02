#!/usr/bin/env python3
"""BC5 experiment 0401: the kit on the laptop, against stand-ins: no box, no compiler, no GPU. The function itself is compiled
and run on the box by box0401.sh build. A failing case prints its name; exit 0 only after the last marker.
usage: python test0401.py <unit-main.cpp> <work dir>"""
import hashlib
import importlib.util
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

BASH = "C:/Program Files/Git/bin/bash.exe"
HERE = pathlib.Path(__file__).resolve().parent
UNIT = pathlib.Path(sys.argv[1])
WORK = pathlib.Path(sys.argv[2])
KIT = ("mkunit0401.py", "check0401.py", "build0401.py", "launcher0401.py", "unit0401.cpp", "env_flag.hpp")
LAUNCHER = """#!/bin/bash
# the output goes to ~/bc5-work/play-pkg-last.log
EMU=~/bc5-work/kytyplus-build/src/kyty_emulator
LOG=~/bc5-work/play-pkg-last.log
MLOG=~/bc5-work/play-pkg-mount.log
if [ "${BC5_LEAN:-0}" = 1 ]; then
  EMU=~/bc5-work/kytyplus-build-lean/src/kyty_emulator LOG=~/bc5-work/play-pkg-lean-last.log
fi
echo "$EMU $LOG $MLOG"
"""
FAKEUNIT = """import os, sys
c = os.environ.get("BC5_DIRECT_CP_COHER_START_DELAY", "") not in ("", "0")
r = os.environ.get("BC5_DIRECT_SPI_REQ_CTRL_PS", "") not in ("", "0")
print("exp 0401: CP_COHER_START_DELAY " + ("0x20 in every prefix (SET_UCONFIG_REG 0x7b)" if c else "off"))
print("exp 0401: SPI_SHADER_REQ_CTRL_PS " + ("0x7 in every prefix (SET_SH_REG 0x30)" if r else "off"))
p = (("c0017900 0000007b @V@ " if c else "") + ("c0017600 00000030 00000007 " if r else "")) * 2
print("000000aa " + p)
print("end")
"""
FAKEBOX = r"""#!/bin/bash
case "$1" in
  clang-fake)
    out="${@: -1}"
    [ -z "${FAKE_CXX_FAIL:-}" ] || { echo "unit.cpp:1:1: error: boom"; exit 1; }
    cp "$BC5_0401_ROOT/fakeunit.py" "$out"; exit 0 ;;
  python3)
    shift 2; s=$1; shift
    case "$s" in
      *check0401.py) exec python "$s" python "$1" ;;
      *build0401.py)
        [ -z "${FAKE_BUILD_FAIL:-}" ] || { echo "x.cpp:9:9: error: nope"; echo "== COMPILE FAILED"; exit 2; }
        printf '\033[1mwarning:\033[0m one\n'
        [ -z "${FAKE_SHARED_CHANGES:-}" ] || echo changed >> "$BC5_0401_ROOT/bc5-work/kytyplus-build/src/kyty_emulator"
        out=$5; { echo '#!/bin/sh'; echo BC5_DIRECT_CP_COHER_START_DELAY; echo 'exp 0401: CP_COHER_START_DELAY %s'; echo 'exp 0401: SPI_SHADER_REQ_CTRL_PS %s'
                  echo BC5_DIRECT_ARGS_WB; echo BC5_DIRECT_GC_HS_OFFCHIP; [ -n "${FAKE_NO_SWITCH:-}" ] || echo BC5_DIRECT_SPI_REQ_CTRL_PS; } > "$out"
        chmod +x "$out"; exit 0 ;;
    esac ;;
  sh) echo '[]'; exit 0 ;;
esac
echo "fakebox: $*"; exit 9
"""


def md5(p):
    return hashlib.md5(pathlib.Path(p).read_bytes()).hexdigest()


def posix(p):
    return str(p).replace("\\", "/")


class Box:
    def __init__(self, name, value="00000020"):
        self.root = pathlib.Path(tempfile.mkdtemp(prefix=f"0401-test-{name}-", dir=WORK))
        self.w = self.root / "bc5-work"
        self.e = self.w / "exp0401"
        for rel, data in (("kytyplus-build/src/kyty_emulator", b"normal"), ("kytyplus-build-lean/src/kyty_emulator", b"lean"),
                          ("backend-ubuntu/libbc5_backend.a", b"archive"), ("play-pkg.sh", LAUNCHER.encode()), ("BOX-LOCK", b""), ("BOX-QUEUE", b"")):
            f = self.w / rel
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_bytes(data)
        tree = self.root / "src/KytyPlus/src/libs/bc5LleAgc.cpp"
        tree.parent.mkdir(parents=True)
        shutil.copy(UNIT, tree)
        (self.root / "fakeunit.py").write_text(FAKEUNIT.replace("@V@", value), newline="\n")
        (self.root / "fakebox").write_text(FAKEBOX, newline="\n")
        r = posix(self.root)
        fake = self.root / "stand-ins.sh"
        fake.write_text(f"""DBX=(bash {r}/fakebox); PY=(python); CXX=clang-fake
disk_pct() {{ echo 5; }}
BIN_MD5={md5(self.w / 'kytyplus-build/src/kyty_emulator')}; LEAN_MD5={md5(self.w / 'kytyplus-build-lean/src/kyty_emulator')}
ARCHIVE_MD5={md5(self.w / 'backend-ubuntu/libbc5_backend.a')}; LAUNCHER_MD5={md5(self.w / 'play-pkg.sh')}
""", newline="\n")
        self.env = dict(os.environ, BC5_0401_ROOT=r, BC5_0401_FAKE=posix(fake))
        self.token = ""

    def claim(self):
        with open(HERE / "box0401.sh", "rb") as f:
            return subprocess.run([BASH, "-s", "--", "claim"], env=self.env, stdin=f, capture_output=True, timeout=60, text=True)

    def send(self):
        for k in KIT:
            shutil.copy(HERE / k, self.e / k)
        shutil.copy(HERE / "box0401.sh", self.e / "box0401.sh")
        lines = [f"{hashlib.sha256((self.e / k).read_bytes()).hexdigest()}  {k}" for k in KIT]
        (self.e / "kit.sha256").write_text("\n".join(lines) + "\n", newline="\n")

    def box(self, *a, **env):
        return subprocess.run([BASH, posix(self.e / "box0401.sh"), *a], env=dict(self.env, **env), text=True, capture_output=True, timeout=120)

    def up(self):
        r = self.claim()
        assert r.returncode == 0, r.stdout + r.stderr
        self.token = next(l for l in r.stdout.split("\n") if l.startswith("TOKEN=")).split("=")[1]
        self.send()
        r = self.box("setup", self.token)
        assert r.returncode == 0, r.stdout + r.stderr
        return self

    def lock(self):
        return (self.w / "BOX-LOCK").read_text()


def t_happy():
    b = Box("happy").up()
    assert "private normal build" in b.lock()
    r = b.box("build", b.token)
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout.rstrip().endswith("built: shared binaries, archive, tree and launcher unchanged"), r.stdout
    assert "warnings in the unit's compile: 1" in r.stdout, r.stdout
    assert (b.e / "state").read_text().strip() == "built"
    assert md5(b.e / "bin/kyty_emulator") == (b.e / "bin.md5").read_text().strip()
    d = (b.e / "play-pkg-0401.sh").read_text()
    assert "EMU=~/bc5-work/exp0401/bin/kyty_emulator" in d and "LOG=~/bc5-work/exp0401/play-last.log" in d and "no private lean build" in d
    assert b.box("status", b.token).stdout.startswith("state built")
    r = b.box("release", b.token)
    assert r.stdout.strip() == "released", r.stdout + r.stderr
    assert b.lock() == "", repr(b.lock())
    q = (b.w / "BOX-QUEUE").read_text()
    assert "claimed: private normal build" in q and "released: the release command" in q
    assert (b.w / "kytyplus-build/src/kyty_emulator").read_bytes() == b"normal"
    assert b.box("release", b.token).stdout.strip() == "released already"


def t_foreign_lock():
    b = Box("foreign")
    (b.w / "BOX-LOCK").write_text("top | build\n", newline="\n")
    r = b.claim()
    assert r.returncode == 1 and "foreign lock" in r.stdout, r.stdout + r.stderr
    assert b.lock() == "top | build\n" and not b.e.exists()


def t_pin_wrong():
    b = Box("pin")
    (b.w / "play-pkg.sh").write_text(LAUNCHER + "# changed\n", newline="\n")
    r = b.claim()
    assert r.returncode == 1 and "the launcher is not" in r.stdout and "our lock line is out" in r.stdout, r.stdout + r.stderr
    assert b.lock() == "" and not b.e.exists()


def t_kit_tampered():
    b = Box("kit")
    r = b.claim()
    b.token = r.stdout.split("TOKEN=")[1].split()[0]
    b.send()
    with open(b.e / "check0401.py", "a") as f:
        f.write("# changed\n")
    r = b.box("setup", b.token)
    assert r.returncode == 1 and "not what was sent" in r.stdout, r.stdout


def t_wrong_token():
    b = Box("token").up()
    r = b.box("build", "123")
    assert r.returncode == 1 and "is not this series'" in r.stdout, r.stdout


def t_build_order_gate():
    b = Box("order")
    r = b.claim()
    b.token = r.stdout.split("TOKEN=")[1].split()[0]
    b.send()
    r = b.box("build", b.token)
    assert r.returncode == 1 and "want setup" in r.stdout, r.stdout


def t_function_fails():
    b = Box("cxx").up()
    r = b.box("build", b.token, FAKE_CXX_FAIL="1")
    assert r.returncode == 1 and "did not compile" in r.stdout and "boom" in r.stdout, r.stdout
    assert not (b.e / "bin/kyty_emulator").exists()
    assert b.box("release", b.token).stdout.strip() == "released" and b.lock() == ""


def t_function_mutant():
    b = Box("mutant", value="00000021").up()
    r = b.box("build", b.token)
    assert r.returncode == 1 and "check failed" in r.stdout, r.stdout + r.stderr
    assert not (b.e / "bin/kyty_emulator").exists()


def t_build_fails():
    b = Box("link").up()
    r = b.box("build", b.token, FAKE_BUILD_FAIL="1")
    assert r.returncode == 1 and "the private build failed" in r.stdout and "nope" in r.stdout, r.stdout
    assert (b.e / "state").read_text().strip() == "building"
    assert b.box("release", b.token).stdout.strip() == "released" and b.lock() == ""


def t_binary_lacks_switch():
    b = Box("strings").up()
    r = b.box("build", b.token, FAKE_NO_SWITCH="1")
    assert r.returncode == 1 and "lacks [BC5_DIRECT_SPI_REQ_CTRL_PS]" in r.stdout, r.stdout


def t_shared_changed_in_build():
    b = Box("shared").up()
    r = b.box("build", b.token, FAKE_SHARED_CHANGES="1")
    assert r.returncode == 1 and "the shared normal binary is not" in r.stdout, r.stdout


def t_foreign_line_kept():
    b = Box("keep").up()
    with open(b.w / "BOX-LOCK", "a", newline="\n") as f:
        f.write("MAINTAINER PLAYING\n")
    r = b.box("build", b.token)
    assert r.returncode == 1 and "the lock is not ours" in r.stdout, r.stdout
    assert b.box("release", b.token).stdout.strip() == "released"
    assert b.lock() == "MAINTAINER PLAYING\n", repr(b.lock())


def load(name):
    spec = importlib.util.spec_from_file_location(name, HERE / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def t_unit_edit():
    mk = load("mkunit0401")
    s = UNIT.read_bytes()
    out = mk.edit(s)
    assert out.count(b"mesa_preamble_prefix(p); // experiment 0401\n") == 1
    at = out.index(b"tf_ring_prefix(p); // experiment 0160\n")
    assert out[at:].split(b"\n")[1] == b"\tmesa_preamble_prefix(p); // experiment 0401" and out.index(b"static void mesa_preamble_prefix") < at
    for bad in (s.replace(mk.ANCHOR, b""), s.replace(mk.CALL, b""), s + mk.CALL, out):
        try:
            mk.edit(bad)
        except AssertionError:
            continue
        raise SystemExit("a bad unit passed")


def t_launcher_edit():
    la = load("launcher0401")
    d = la.derive(LAUNCHER)
    assert "exp0401/bin/kyty_emulator" in d
    for bad in (LAUNCHER.replace("MLOG=~/bc5-work/play-pkg-mount.log\n", ""), LAUNCHER + LAUNCHER, LAUNCHER + "x=~/bc5-work/kytyplus-build/src/kyty_emulator\n"):
        try:
            la.derive(bad)
        except AssertionError:
            continue
        raise SystemExit("a bad launcher passed")


def t_build_commands():
    bu = load("build0401")
    db = [{"output": bu.UNIT, "command": f"clang++ -I/a -MD -MT {bu.UNIT} -MF x.d -o {bu.UNIT} -c ../src/libs/bc5LleAgc.cpp"},
          {"output": "src/kyty_emulator", "command": f": && clang++ -Wl,-Map=m --dependency-file=d {bu.UNIT} other.o /a/libbc5_backend.a -o src/kyty_emulator && :"}]
    assert bu.compile_argv(db, "/e/u.cpp", "/e/u.o") == ["clang++", "-I/a", "-o", "/e/u.o", "-c", "/e/u.cpp"]
    l = bu.link_argv(db, "/e/u.o", "/e/bin/k")
    assert l == ["clang++", "-Wl,-Map=/e/bin/k.map", "--dependency-file=/e/bin/k.d", "/e/u.o", "other.o", "/a/libbc5_backend.a", "-o", "/e/bin/k"], l
    db[1]["command"] = db[1]["command"].replace(bu.UNIT + " ", bu.UNIT + " " + bu.UNIT + " ")
    try:
        bu.link_argv(db, "/e/u.o", "/e/k")
    except AssertionError:
        return
    raise SystemExit("a doubled object passed")


def main():
    cases = [v for k, v in sorted(globals().items()) if k.startswith("t_")]
    assert len(cases) == 15, len(cases)
    bad = 0
    for c in cases:
        try:
            c()
            print("ok  ", c.__name__)
        except (AssertionError, subprocess.TimeoutExpired, StopIteration, IndexError) as e:
            bad += 1
            print("FAIL", c.__name__, str(e)[:600])
    print(f"test0401: {len(cases) - bad} of {len(cases)}" + ("; end" if not bad else ""))
    sys.exit(1 if bad else 0)


main()
