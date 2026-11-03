#!/usr/bin/env python3
"""BC5 experiment 0401: the kit on the laptop, against stand-ins: no box, no compiler, no GPU. The function itself is compiled
and run on the box by box0401.sh build. A failing case prints its name; exit 0 only after the last marker.
usage: python test0401.py <unit-main.cpp> <work dir> <zero-skip unit: main's plus exp 0388's patch-z-bc5LleAgc.diff>
                          <tree root holding the box tree's src/libs/libNpCppWebApi.cpp, src/kernel/memory.cpp,
                          src/loader/systemContent.cpp and src/loader/systemContent.h (series e)>"""
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
ZUNIT = pathlib.Path(sys.argv[3])
ETREE = pathlib.Path(sys.argv[4])
ETREE_FILES = ("src/libs/libNpCppWebApi.cpp", "src/kernel/memory.cpp", "src/kernel/memoryAddressSpace.inc", "src/loader/systemContent.cpp",
               "src/loader/systemContent.h")
KIT = ("mkunit0401.py", "check0401.py", "build0401.py", "launcher0401.py", "unit0401.cpp", "env_flag.hpp", "mknp0401.py", "mkmem0401.py",
       "npgate0401.cpp")
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
                  echo BC5_DIRECT_ARGS_WB; echo BC5_DIRECT_GC_HS_OFFCHIP; [ -n "${FAKE_NO_SWITCH:-}" ] || echo BC5_DIRECT_SPI_REQ_CTRL_PS
                  echo BC5_DIRECT_CS_PREFIX; echo 'acb cs prefix (exp 0401)'; echo 'exp 0401: acb CS prefix %s'
                  [ -n "${FAKE_NO_ACB:-}" ] || echo BC5_DIRECT_ACB_CS_PREFIX
                  echo 'exp 0401: acb state restore (exp 0381) %s'; echo 'acb state restore (exp 0381)'
                  [ -n "${FAKE_NO_RESTORE:-}" ] || echo BC5_DIRECT_ACB_STATE_RESTORE; echo 'job-arena fix APPLIED'
                  [ ! -f "${6:-/nonexistent}/bc5/zero_skip.hpp" ] || { echo BC5_DIRECT_ZERO_SKIP; echo BC5_DIRECT_ZERO_SLICES; echo 'zero skip: list %s'; }
                  if [ -f "${6:-/nonexistent}/loader/systemContent.h" ]; then
                    [ -n "${FAKE_NO_CATCHER:-}" ] || echo BC5_DIRECT_TABLE_CATCHER
                    echo 'exp 0401: table catcher %s'; echo 'table catcher (exp 0401)'; echo KYTY_BC5_NP_SESSION_V2; echo KYTY_BC5_MEMORY_FROM_PARAM
                    echo '[bc5] exp 0401: memory from param.json %s: total'
                  fi; } > "$out"
        chmod +x "$out"
        n=0; for a in "$@"; do n=$((n + 1)); [ "$a" = --gate ] && break; done
        if [ "$n" -lt "$#" ]; then   # the gate program: a stand-in that answers as the real one would
          g="${@: -1}"; u="${@: -2:1}"; [ -f "$u" ] || { echo "no gate source $u"; exit 2; }
          { echo '#!/bin/bash'
            echo 'v=${KYTY_BC5_NP_SESSION_V2:-}; [ -n "$v" ] && [ "$v" != 0 ] && on=on || on=off'
            echo '[ "$1" = "$on" ] || { echo "npgate0401: the argument says $1 but the switch is ${v:-unset}"; exit 1; }'
            echo '[ -z "${FAKE_GATE_FAIL:-}" ] || { echo "npgate0401: FAIL eVU3cXIJz0w"; echo "npgate0401: $1 1 failures"; exit 1; }'
            echo 'if [ "$1" = on ]; then echo "npgate0401: on 10 of 10 registered as their functions in x, 9 of 9 NOT_SIGNED_IN, initialize 1 of 1; end"'
            echo 'else echo "npgate0401: off 10 of 10 unregistered, 9 of 9 NOT_SIGNED_IN, initialize 1 of 1; end"; fi'; } > "$g"
          chmod +x "$g"
        fi
        exit 0 ;;
    esac ;;
  env) exec "$@" ;;
  sh) echo '[]'; exit 0 ;;
esac
echo "fakebox: $*"; exit 9
"""


def md5(p):
    return hashlib.md5(pathlib.Path(p).read_bytes()).hexdigest()


def posix(p):
    return str(p).replace("\\", "/")


class Box:
    def __init__(self, name, value="00000020", series=""):
        self.root = pathlib.Path(tempfile.mkdtemp(prefix=f"0401-test-{name}-", dir=WORK))
        self.w = self.root / "bc5-work"
        self.e = self.w / f"exp0401{series}"
        for rel, data in (("kytyplus-build/src/kyty_emulator", b"normal"), ("kytyplus-build-lean/src/kyty_emulator", b"lean"),
                          ("backend-ubuntu/libbc5_backend.a", b"archive"), ("play-pkg.sh", LAUNCHER.encode()), ("BOX-LOCK", b""), ("BOX-QUEUE", b"")):
            f = self.w / rel
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_bytes(data)
        tree = self.root / "src/KytyPlus/src/libs/bc5LleAgc.cpp"
        tree.parent.mkdir(parents=True)
        shutil.copy(UNIT, tree)
        for rel in ETREE_FILES:   # series e's three more units, the box tree's own
            f = self.root / "src/KytyPlus" / rel
            f.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(ETREE / rel, f)
        z = self.w / "exp0388/z/src/src"   # series d's zero-skip unit and a stand-in header
        (z / "libs").mkdir(parents=True)
        (z / "bc5").mkdir()
        shutil.copy(ZUNIT, z / "libs/bc5LleAgc.cpp")
        (z / "bc5/zero_skip.hpp").write_bytes(b"// zero skip stand-in\n")
        (self.root / "fakeunit.py").write_text(FAKEUNIT.replace("@V@", value), newline="\n")
        (self.root / "fakebox").write_text(FAKEBOX, newline="\n")
        r = posix(self.root)
        fake = self.root / "stand-ins.sh"
        fake.write_text(f"""DBX=(bash {r}/fakebox); PY=(python); CXX=clang-fake
disk_pct() {{ echo 5; }}
BIN_MD5={md5(self.w / 'kytyplus-build/src/kyty_emulator')}; LEAN_MD5={md5(self.w / 'kytyplus-build-lean/src/kyty_emulator')}
ARCHIVE_MD5={md5(self.w / 'backend-ubuntu/libbc5_backend.a')}; LAUNCHER_MD5={md5(self.w / 'play-pkg.sh')}
ZHDR_MD5={md5(z / 'bc5/zero_skip.hpp')}
""", newline="\n")
        self.env = dict(os.environ, BC5_0401_ROOT=r, BC5_0401_FAKE=posix(fake), BC5_0401_SERIES=series)
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


def t_series_b():
    b = Box("serb", series="b").up()
    assert b.lock().startswith("water exp 0401b | private normal build"), b.lock()
    r = b.box("build", b.token)
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout.rstrip().endswith("built: shared binaries, archive, tree and launcher unchanged"), r.stdout
    assert "unit b1d96c719fda2ed048876fe119e89310" in r.stdout, r.stdout
    assert md5(b.e / "src/bc5LleAgc.cpp") == "b1d96c719fda2ed048876fe119e89310"
    d = (b.e / "play-pkg-0401.sh").read_text()
    assert "EMU=~/bc5-work/exp0401b/bin/kyty_emulator" in d and "LOG=~/bc5-work/exp0401b/play-last.log" in d, d
    assert not (b.w / "exp0401").exists()
    assert b.box("release", b.token).stdout.strip() == "released" and b.lock() == ""
    q = (b.w / "BOX-QUEUE").read_text()
    assert "water exp 0401b | claimed" in q and "water exp 0401b | released" in q, q


def t_series_b_rebuild():
    b = Box("serbre", series="b").up()
    r = b.box("build", b.token, FAKE_NO_ACB="1")
    assert r.returncode == 1 and "lacks [BC5_DIRECT_ACB_CS_PREFIX]" in r.stdout, r.stdout
    assert (b.e / "state").read_text().strip() == "building"
    r = b.box("build", b.token)
    assert r.returncode == 1 and "want setup" in r.stdout, r.stdout
    b.send()
    r = b.box("setup", b.token)
    assert r.returncode == 0, r.stdout + r.stderr
    r = b.box("build", b.token)
    assert r.returncode == 0, r.stdout + r.stderr
    assert b.box("release", b.token).stdout.strip() == "released" and b.lock() == ""


def t_series_c():
    b = Box("serc", series="c").up()
    r = b.box("build", b.token, FAKE_NO_RESTORE="1")
    assert r.returncode == 1 and "lacks [BC5_DIRECT_ACB_STATE_RESTORE]" in r.stdout, r.stdout
    b.send()
    assert b.box("setup", b.token).returncode == 0
    r = b.box("build", b.token)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "unit 29c88be321cc81908085b1cddcc70d2e" in r.stdout, r.stdout
    d = (b.e / "play-pkg-0401.sh").read_text()
    assert "EMU=~/bc5-work/exp0401c/bin/kyty_emulator" in d, d
    assert b.box("release", b.token).stdout.strip() == "released" and b.lock() == ""


def t_series_d():
    b = Box("serd", series="d").up()
    assert md5(b.e / "zbase/bc5LleAgc.cpp") == "3a77e0acef307865d1cd524951060422" and (b.e / "zinc/bc5/zero_skip.hpp").is_file()
    (b.e / "zinc/bc5/zero_skip.hpp").write_bytes(b"changed\n")
    r = b.box("build", b.token)
    assert r.returncode == 1 and "the zero-skip copies are not the pins" in r.stdout, r.stdout
    assert (b.e / "state").read_text().strip() == "setup"   # it stopped before the build began
    shutil.copy(b.w / "exp0388/z/src/src/bc5/zero_skip.hpp", b.e / "zinc/bc5/zero_skip.hpp")
    r = b.box("build", b.token)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "unit 0f18cf30cb85843cdbe9d5df68909e3d" in r.stdout, r.stdout
    assert md5(b.e / "src/bc5LleAgc.cpp") == "0f18cf30cb85843cdbe9d5df68909e3d"
    assert "EMU=~/bc5-work/exp0401d/bin/kyty_emulator" in (b.e / "play-pkg-0401.sh").read_text()
    assert md5(b.w / "exp0388/z/src/src/libs/bc5LleAgc.cpp") == "3a77e0acef307865d1cd524951060422"
    assert b.box("release", b.token).stdout.strip() == "released" and b.lock() == ""


def t_series_d_pins():
    b = Box("serdp", series="d")
    (b.w / "exp0388/z/src/src/libs/bc5LleAgc.cpp").write_bytes(UNIT.read_bytes())
    r = b.claim()
    assert r.returncode == 1 and "the zero-skip unit is not" in r.stdout, r.stdout
    assert b.lock() == "" and not b.e.exists()


def t_series_e():
    b = Box("sere", series="e").up()
    r = b.box("build", b.token, FAKE_NO_CATCHER="1")
    assert r.returncode == 1 and "lacks [BC5_DIRECT_TABLE_CATCHER]" in r.stdout, r.stdout
    assert (b.e / "raw/npgate-on.out").read_text().rstrip().endswith("; end") and (b.e / "raw/npgate-unset.out").exists()
    b.send()
    assert b.box("setup", b.token).returncode == 0
    r = b.box("build", b.token)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "unit 0d65c14d3705887717bac71dd97e05ab" in r.stdout and "libNpCppWebApi.cpp 935fcc7e4ab1108f3d2d8b33eaf65bf6" in r.stdout, r.stdout
    assert md5(b.e / "src/bc5LleAgc.cpp") == "0d65c14d3705887717bac71dd97e05ab" and md5(b.e / "src/libNpCppWebApi.cpp") == "935fcc7e4ab1108f3d2d8b33eaf65bf6"
    assert md5(b.e / "mem/src/kernel/memory.cpp") == "43713ef677ec887a8ca273f7ab5cee90" and md5(b.e / "mem/src/loader/systemContent.h") == "2b2b21eb1faf35c2a538917049aea85e"
    assert md5(b.e / "mem/src/kernel/memoryAddressSpace.inc") == "44586b1ee0e7edf12a0cd293ff9c141f"
    for rel in ETREE_FILES:   # the tree is only read
        assert md5(b.root / "src/KytyPlus" / rel) == md5(ETREE / rel), rel
    assert "EMU=~/bc5-work/exp0401e/bin/kyty_emulator" in (b.e / "play-pkg-0401.sh").read_text()
    assert b.box("release", b.token).stdout.strip() == "released" and b.lock() == ""


def t_series_e_gate():
    b = Box("sereg", series="e").up()
    r = b.box("build", b.token, FAKE_GATE_FAIL="1")
    assert r.returncode == 1 and "the NpCppWebApi gate (on) failed" in r.stdout and "FAIL eVU3cXIJz0w" in r.stdout, r.stdout
    assert b.box("release", b.token).stdout.strip() == "released" and b.lock() == ""
    b = Box("serep", series="e")
    (b.root / "src/KytyPlus/src/kernel/memory.cpp").write_bytes(b"changed\n")
    r = b.claim()
    assert r.returncode == 1 and "the tree's memory.cpp is not" in r.stdout, r.stdout
    assert b.lock() == "" and not b.e.exists()


def t_series_unknown():
    b = Box("serx", series="f")
    r = b.claim()
    assert r.returncode == 2 and "unknown series" in r.stdout, r.stdout
    assert b.lock() == ""


def t_unit_edit_acb():
    mk = load("mkunit0401")
    s = UNIT.read_bytes()
    a, out = mk.edit(s), mk.edit(s, acb=True)
    assert hashlib.md5(a).hexdigest() == "9eec0a3856bc1857ba7956b001c93aaf"
    assert hashlib.md5(out).hexdigest() == "b1d96c719fda2ed048876fe119e89310"
    for anchor, text, where in mk.ACB_EDITS:
        assert out.count(text) == 1, text[:60]
        if where == "before":
            assert out.index(text) + len(text) == out.index(anchor)
        elif where == "after":
            assert out.index(anchor) + len(anchor) == out.index(text)
    assert out.index(b"static std::vector<uint32_t> acb_cs_prefix(const uint32_t* part, uint32_t n) {") > out.index(b"static std::vector<uint32_t> cs_prefix(")
    assert out.index(b"static std::vector<uint32_t> acb_cs_prefix(const uint32_t* part, uint32_t n);") < out.index(b"static void submit_segment(")
    for anchor, _, _ in mk.ACB_EDITS:
        try:
            mk.edit(s.replace(anchor, b""), acb=True)
        except AssertionError:
            continue
        raise SystemExit("a unit without an acb anchor passed")
    c = mk.edit(s, acb=True, restore=True)
    assert hashlib.md5(c).hexdigest() == "29c88be321cc81908085b1cddcc70d2e"
    z = ZUNIT.read_bytes()   # series d: the same edit on the zero-skip unit
    assert hashlib.md5(z).hexdigest() == "3a77e0acef307865d1cd524951060422"
    d = mk.edit(z, acb=True, restore=True)
    assert hashlib.md5(d).hexdigest() == "0f18cf30cb85843cdbe9d5df68909e3d" and len(d) - len(z) == len(c) - len(s)
    e = mk.edit(s, acb=True, restore=True, catcher=True)   # series e: series c plus the table catcher
    assert hashlib.md5(e).hexdigest() == "0d65c14d3705887717bac71dd97e05ab"
    for anchor, text, where in mk.catcher_edits():
        assert e.count(text) == 1, text[:60]
        if where == "before":
            assert e.index(text) + len(text) == e.index(anchor)
        else:
            assert e.index(anchor) + len(anchor) == e.index(text)
    assert e.index(b"struct CatchSlot {") < e.index(b"struct PendingJob {") < e.index(b"std::vector<CatchSlot>   catch_slots;")
    assert e.index(b"const bool             catch_on = table_catcher_on();") < e.index(b"if (catch_on && type == 3) {")
    for anchor, _, _ in mk.catcher_edits():
        try:
            mk.edit(s.replace(anchor, b""), acb=True, restore=True, catcher=True)
        except AssertionError:
            continue
        raise SystemExit("a unit without a catcher anchor passed")
    assert c.count(mk.RESTORE_SPLIT + mk.ACB_SPLIT) == 1 and c.count(mk.RESTORE_FUNCTIONS) == 1
    assert c.count(b"|| acb_restore_on()) t_fs_before = tracker;") == 1
    assert c.index(b"static bool acb_restore_on()") < c.index(b"if (t_fs_valid || prefix_all() || cs_prefix_mode() != 0 || acb_restore_on())")
    try:
        mk.edit(s, restore=True)
    except AssertionError:
        return
    raise SystemExit("the restore passed without the acb CS prefix")


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
    db = la.derive(LAUNCHER, "b")
    assert "EMU=~/bc5-work/exp0401b/bin/kyty_emulator" in db and "MLOG=~/bc5-work/exp0401b/play-pkg-mount.log" in db, db
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
    assert bu.compile_argv(db, "/e/u.cpp", "/e/u.o", "/e/zinc") == ["clang++", "-I/e/zinc", "-I/a", "-o", "/e/u.o", "-c", "/e/u.cpp"]
    m = bu.unit_obj("src/kernel/memory.cpp")   # series e: more units, and the gate's link
    assert m == "src/CMakeFiles/kyty_emulator.dir/kernel/memory.cpp.o"
    db2 = [dict(db[0]), {"output": m, "command": f"clang++ -I/a -o {m} -c ../src/kernel/memory.cpp"},
           {"output": "src/kyty_emulator", "command": f": && clang++ -Wl,-Map=m --dependency-file=d {bu.MAIN} {bu.UNIT} {m} /a/libbc5_backend.a -o src/kyty_emulator && :"}]
    l2 = bu.link_argv(db2, "/e/u.o", "/e/bin/k", {m: "/e/mem.o"})
    assert l2 == ["clang++", "-Wl,-Map=/e/bin/k.map", "--dependency-file=/e/bin/k.d", bu.MAIN, "/e/u.o", "/e/mem.o", "/a/libbc5_backend.a", "-o", "/e/bin/k"], l2
    g = bu.gate_argv(l2, "/e/gate.o", "/e/raw/g")
    assert g == ["clang++", "-Wl,-Map=/e/raw/g.map", "--dependency-file=/e/raw/g.d", "/e/gate.o", "/e/u.o", "/e/mem.o", "/a/libbc5_backend.a", "-o", "/e/raw/g"], g
    assert bu.parse_rest(["/e/inc", "src/kernel/memory.cpp=/e/m.cpp", "--gate", "/e/g.cpp", "/e/g"]) == ("/e/inc", {"src/kernel/memory.cpp": "/e/m.cpp"}, ("/e/g.cpp", "/e/g"))
    assert bu.parse_rest(["/e/zinc"]) == ("/e/zinc", {}, None) and bu.parse_rest([]) == (None, {}, None)
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
    assert len(cases) == 24, len(cases)
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
