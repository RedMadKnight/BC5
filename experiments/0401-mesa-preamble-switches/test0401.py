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
               "src/loader/systemContent.h", "src/libs/libSaveData.cpp", "src/kernel/pthread.cpp",
               "src/libs/libAudio2.cpp", "src/libs/audio.cpp", "src/bc5/pad_audio_route.hpp", "src/graphics/presentation/videoOut.cpp",
               "src/libs/libAmpr.cpp",
               "src/kernel/eventQueue.cpp", "src/libs/bc5LleAgc.cpp", "src/kernel/semaphore.cpp", "src/kernel/fileSystem.cpp", "src/libs/libKernel.cpp", "src/libs/libNet.cpp", "src/libs/libPad.cpp", "src/libs/libJson2.cpp", "src/libs/libUlt.cpp", "src/libs/libUserService.cpp", "src/libs/libSystemService.cpp", "src/loader/jit.h", "src/loader/runtimeLinker.cpp",
               "src/libs/libRtc.cpp", "src/libs/libRudp.cpp", "src/libs/network.cpp", "src/libs/avPlayer.cpp", "src/libs/libZlib.cpp", "src/libs/libJpeg.cpp", "src/libs/libIme.cpp", "src/libs/libNp.cpp", "src/libs/libs.cpp")
KIT = ("mkunit0401.py", "check0401.py", "build0401.py", "launcher0401.py", "unit0401.cpp", "env_flag.hpp", "mknp0401.py", "mkmem0401.py",
       "npgate0401.cpp", "inh0401.cpp", "mksav0401.py", "sav0401.cpp", "mkpth0401.py", "pth0401.cpp", "mkaud0401.py", "aud0401.cpp", "mkvo0401.py", "vo0401.cpp", "mkfl0401.py", "fl0401.cpp", "mkamm0401.py", "amm0401.cpp",
       "mkeq0405.py", "mkgpu0405.py", "mkthr0405.py", "mkmem0405.py", "mkfs0405.py", "mksvc0405.py", "mklib0405.py", "mkao0405.py", "mktls0405.py", "ao0405.cpp", "eq0405.cpp", "fs0405.cpp", "gpu0405.cpp", "lib0405.cpp", "mem0405.cpp", "svc0405.cpp", "thr0405.cpp", "tls0405.cpp",
       "mkpred0405.py", "backend0405.md5",
       "mkfwn0405.py", "mkfwa0405.py", "mkjit0405.py", "mktbc0405.py", "mktbn0405.py", "mktld0405.py", "mkpad0405.py", "pad0405.cpp", "fwn0405.cpp", "fwa0405.cpp", "jit0405.cpp", "tbc0405.cpp", "tbn0405.cpp", "tld0405.cpp")
BACKEND = HERE.parent.parent / "backend"   # main's backend, the stand-in for the shared archive's source (series e6p)
BK_DIRS = ("CMakeLists.txt", "src", "include", "tests", "policy", "experiments")
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
        printf '%s\n' "$@" > "$BC5_0401_ROOT/build-args.txt"
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
                    [ -n "${FAKE_NO_INHERIT:-}" ] || echo BC5_DIRECT_ACB_INHERIT
                    echo 'exp 0403: acb inherit %s'; echo 'acb inherit (exp 0403)'; echo 'acb inherit census (exp 0403)'
                    [ -n "${FAKE_NO_MEMLINE:-}" ] || echo BC5_DIRECT_MEM_LINE
                    echo "the queue's live program"; echo 'prefixed with the queue'; echo 'never bound in a part of its own'; echo 'exp 0401: memory line %s'; echo 'memory (exp 0401)'
                    echo 'unknown, fallback ring'; echo 'UNSEEN (not observed in this wave mode)'
                    [ -n "${FAKE_NO_E4:-}" ] || echo KYTY_BC5_SAVEDATA_FIXES
                    echo BC5_DIRECT_FL_CRUMBS; echo BC5_DIRECT_FL_SKIP_ES; echo 'exp 0404: fl crumbs %s'; echo 'exp 0404: fl skip es'
                    echo KYTY_BC5_AMM_PRT_CMDS; echo KYTY_BC5_AMM_EXTRA_CMDS; echo KYTY_BC5_AMPR_WAITS; echo 'exp 0401 prt: zero pages'
                    echo KYTY_BC5_SAVEDATA_EVENT_CB; echo 'exp 0401: savedata event callback'; echo KYTY_BC5_SAVEDATA_SORT; echo 'exp 0401: savedata sort'
                    echo '[bc5] exp 0401: savedata fixes %s'; echo KYTY_BC5_PTHREAD_FIXES; echo '[bc5] exp 0401: pthread fixes %s'
                    echo KYTY_BC5_AUDIO_FIXES; echo '[bc5] exp 0401: audio fixes %s'; echo KYTY_BC5_VIDEOOUT_STATUS; echo '[bc5] exp 0401: videoout status %s'
                    [ -n "${FAKE_NO_E6:-}" ] || for x in KYTY_BC5_FW_PAD KYTY_BC5_FW_NET KYTY_BC5_FW_AUDIO KYTY_BC5_JIT_SHM KYTY_BC5_FW_KERNEL KYTY_BC5_LOAD_ZLIB KYTY_BC5_LOAD_JPEG KYTY_BC5_LOAD_IME KYTY_BC5_LOAD_NPCOMMON KYTY_BC5_LOAD_NPMANAGER KYTY_BC5_LOAD_NPTROPHY; do echo "$x"; done
                    [ -n "${FAKE_NO_E6P:-}" ] || { echo BC5_R3_PREDICATION; echo 'exp 0405: set predication %s'; echo 'exp 0405: G7 SET_PREDICATION %s %s'; }
                    [ -n "${FAKE_NO_E5:-}" ] || for x in KYTY_BC5_EQUEUE_FIXES KYTY_BC5_MMAP_SHIM_FIXES KYTY_BC5_AUDIOOUT_CHECKS KYTY_BC5_AUDIOIN_CHECKS KYTY_BC5_NGS2_RACK_FIX BC5_R3_MPROTECT_GAPS BC5_R3_NULL_ARGS BC5_R3_RELEASE_HOLES BC5_R3_MUNMAP_HOLES BC5_R3_FLEX_HINT BC5_R3_DMQ_END BC5_R3_EXEC_EINVAL BC5_R3_QUERY_SIZE KYTY_BC5_THREAD_SYNC_FIXES KYTY_BC5_SEMA_FIXES KYTY_BC5_SAVEDATA_MEMORY_FIXES KYTY_BC5_SAVEDATA_DELETE_BUSY KYTY_BC5_SAVEDATA_ALIASES KYTY_BC5_HTTP2_FIXES KYTY_BC5_PAD_OPEN_EXT BC5_R3_MEMSEM_SIGNAL BC5_R3_REWIND_CATCH BC5_R3_DROP_CATCH BC5_R3_SUBMIT_EOP_EVENT BC5_R3_COND_WRITE BC5_R3_WAIT_IDLE BC5_R3_TS_100MHZ KYTY_BC5_FS_FIXES KYTY_BC5_POSIX_RET_FIXES KYTY_BC5_JSON2_FIXES KYTY_BC5_ULT_FIXES KYTY_BC5_USERSERVICE_VALUES KYTY_BC5_SYSTEMSERVICE_VALUES KYTY_BC5_SYSTEMSERVICE_PARAMS_7_1000 KYTY_BC5_TLS_FIXES; do echo "$x"; done
                  fi; } > "$out"
        chmod +x "$out"
        while [ $# -gt 0 ]; do   # each gate program: a stand-in that answers as the real one would
          [ "$1" = --gate ] || { shift; continue; }
          u=$2; g=$3; shift 3; [ "${1:-}" != --like ] || shift 2
          [ -f "$u" ] || { echo "no gate source $u"; exit 2; }
          case $g in
            */npgate0401)
              { echo '#!/bin/bash'
                echo 'v=${KYTY_BC5_NP_SESSION_V2:-}; [ -n "$v" ] && [ "$v" != 0 ] && on=on || on=off'
                echo '[ "$1" = "$on" ] || { echo "npgate0401: the argument says $1 but the switch is ${v:-unset}"; exit 1; }'
                echo '[ -z "${FAKE_GATE_FAIL:-}" ] || { echo "npgate0401: FAIL eVU3cXIJz0w"; echo "npgate0401: $1 1 failures"; exit 1; }'
                echo 'if [ "$1" = on ]; then echo "npgate0401: on 10 of 10 registered as their functions in x, 9 of 9 NOT_SIGNED_IN, initialize 1 of 1; end"'
                echo 'else echo "npgate0401: off 10 of 10 unregistered, 9 of 9 NOT_SIGNED_IN, initialize 1 of 1; end"; fi'; } > "$g" ;;
            *)
              n=${g##*/}
              { echo '#!/bin/bash'
                echo "[ -z \"\${KYTY_BC5_SAVEDATA_DIR:-}\" ] || { echo '$n: FAIL the save directory is set'; exit 1; }"
                echo "[ -z \"\${FAKE_E4_FAIL:-}\" ] || { echo '$n: FAIL stand-in'; exit 1; }"
                echo "[ \"$n\" != amm0401 ] || [ \"\$1\" != on ] || [ \"\${KYTY_BC5_AMM_PRT_CMDS:-}\${KYTY_BC5_AMM_EXTRA_CMDS:-}\${KYTY_BC5_AMPR_WAITS:-}\" = 111 ] || { echo '$n: FAIL the three switches are not all on'; exit 1; }"
                echo "pwd > where.txt; echo \"$n: \$1 3 of 3; end\""; } > "$g" ;;
          esac
          chmod +x "$g"
        done
        exit 0 ;;
    esac ;;
  env) exec "$@" ;;
  */fl0401) [ -z "${FAKE_FL_FAIL:-}" ] || { echo "fl0401: FAIL stand-in"; echo "fl0401: 1 of 74 cases failed"; exit 1; }; echo "fl0401: 74 of 74 cases; end"; exit 0 ;;
  */inh0401)   # series e3's CPU test: a stand-in that answers as the real one would
    [ -z "${FAKE_INH_FAIL:-}" ] || { echo "inh0401: FAIL B inherits W32: not bound: state -1 (want -1), 1 dispatches: [at 3 end 6 W32 bound]"; echo "inh0401: 1 of 25 cases failed"; exit 1; }
    echo "inh0401: 25 of 25 cases; end"; exit 0 ;;
  sh)
    if [ "${2:-}" = -c ] && [ "${4:-}" = run ]; then shift; exec sh "$@"; fi   # box0401.sh's own script runs the test
    if [ "${2:-}" = -c ] && [ "${4:-}" = bkbuild ]; then   # series e6p: the private backend's configure and build
      s=$5; b=$6
      [ "$(md5sum < "$s/src/policy.cpp" | cut -c1-32)" = 8e22ce87d7a7491e448e39edc9fad6e6 ] || { echo "policy.cpp is not mkpred0405.py's"; exit 1; }
      [ -z "${FAKE_BK_FAIL:-}" ] || { echo "FAILED: src/policy.cpp.o"; echo "policy.cpp:1:1: error: stand-in"; exit 1; }
      mkdir -p "$b" && echo "private archive" > "$b/libbc5_backend.a"
      { echo '#!/bin/bash'
        echo '[ -z "${FAKE_BKTEST_FAIL:-}" ] || { echo "policy_test.cpp:9: FAILED:"; echo "test cases: 160 | 159 passed | 1 failed"; exit 1; }'
        echo 'case "${1:-}" in'
        echo '  "") echo "All tests passed (32077 assertions in 160 test cases)" ;;'
        echo '  "[predication]") echo "All tests passed (190 assertions in ${FAKE_PRED_CASES:-4} test cases)" ;;'
        echo '  "G7: BC5_R3_PREDICATION is read once from the environment")'
        echo '    v=${BC5_R3_PREDICATION-unset}; case "$v" in unset | "") got=off ;; 0) got=census ;; bool) got=bool ;; *) got=all ;; esac'
        echo '    if [ "$got" = "${BC5_TEST_EXPECT_PREDICATION:-}" ]; then echo "All tests passed (3 assertions in 1 test case)"; else echo "test cases: 1 | 1 failed"; exit 1; fi ;;'
        echo '  *) echo "No test cases matched"; exit 2 ;;'
        echo 'esac'; } > "$b/bc5_backend_tests"
      chmod +x "$b/bc5_backend_tests"; exit 0
    fi
    echo '[]'; exit 0 ;;
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
        bs = self.root / "src/bc5/backend"   # series e6p: the shared archive's source, named in the shared build's cache
        for d in BK_DIRS:
            if (BACKEND / d).is_dir():
                shutil.copytree(BACKEND / d, bs / d)
            else:
                bs.mkdir(parents=True, exist_ok=True)
                shutil.copy(BACKEND / d, bs / d)
        (self.w / "kytyplus-build/CMakeCache.txt").write_text(f"KYTY_BC5_BACKEND_SRC:PATH={posix(bs)}\n", newline="\n")
        (self.w / "backend-ubuntu/CMakeCache.txt").write_text("CMAKE_BUILD_TYPE:STRING=Release\nCMAKE_CXX_COMPILER:FILEPATH=/usr/bin/clang++\n", newline="\n")
        self.bs = bs
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
        return subprocess.run([BASH, posix(self.e / "box0401.sh"), *a], env=dict(self.env, **env), text=True, capture_output=True, timeout=600)

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


def t_series_e2():
    b = Box("sere2", series="e2").up()
    r = b.box("build", b.token, FAKE_NO_INHERIT="1")
    assert r.returncode == 1 and "lacks [BC5_DIRECT_ACB_INHERIT]" in r.stdout, r.stdout
    b.send()
    assert b.box("setup", b.token).returncode == 0
    r = b.box("build", b.token)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "unit 73e8e4e0a9d05e5deae426238a24c91d" in r.stdout and "libNpCppWebApi.cpp 935fcc7e4ab1108f3d2d8b33eaf65bf6" in r.stdout, r.stdout
    assert md5(b.e / "src/bc5LleAgc.cpp") == "73e8e4e0a9d05e5deae426238a24c91d"
    assert (b.e / "raw/npgate-unset.out").read_text().rstrip().endswith("; end")
    assert "EMU=~/bc5-work/exp0401e2/bin/kyty_emulator" in (b.e / "play-pkg-0401.sh").read_text()
    assert not (b.w / "exp0401e").exists()
    assert b.box("release", b.token).stdout.strip() == "released" and b.lock() == ""


def t_series_e3():
    b = Box("sere3", series="e3").up()
    r = b.box("build", b.token, FAKE_INH_FAIL="1")
    assert r.returncode == 1 and "the inherit test failed" in r.stdout and "B inherits W32" in r.stdout, r.stdout
    assert (b.e / "src/inherit_scan.inc").read_bytes() == load("mkunit0401").INHERIT_SCAN3
    assert (b.e / "src/memline_parse.inc").read_bytes() == load("mkunit0401").MEMLINE_PARSE
    b.send()
    assert b.box("setup", b.token).returncode == 0
    r = b.box("build", b.token, FAKE_NO_MEMLINE="1")
    assert r.returncode == 1 and "lacks [BC5_DIRECT_MEM_LINE]" in r.stdout, r.stdout
    b.send()
    assert b.box("setup", b.token).returncode == 0
    r = b.box("build", b.token)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "unit d3b7f9b0ab43184ee11de83e9e233ff8" in r.stdout and "inherit test: inh0401: 25 of 25 cases; end" in r.stdout, r.stdout
    assert "EMU=~/bc5-work/exp0401e3/bin/kyty_emulator" in (b.e / "play-pkg-0401.sh").read_text()
    assert b.box("release", b.token).stdout.strip() == "released" and b.lock() == ""


def t_series_e4():
    b = Box("sere4", series="e4").up()
    r = b.box("build", b.token, FAKE_FL_FAIL="1")
    assert r.returncode == 1 and "the fl test failed" in r.stdout, r.stdout
    assert md5(b.e / "src/bc5LleAgc.cpp") == "df12bb2de3e90b8c82a234eedf0babb5" and (b.e / "src/fl_scan.inc").is_file()
    b.send()
    assert b.box("setup", b.token).returncode == 0
    r = b.box("build", b.token, FAKE_E4_FAIL="1")
    assert r.returncode == 1 and "the sav0401 test (on) failed" in r.stdout, r.stdout
    b.send()
    assert b.box("setup", b.token).returncode == 0
    r = b.box("build", b.token, FAKE_NO_E4="1")
    assert r.returncode == 1 and "lacks [KYTY_BC5_SAVEDATA_FIXES]" in r.stdout, r.stdout
    b.send()
    assert b.box("setup", b.token).returncode == 0
    r = b.box("build", b.token, KYTY_BC5_SAVEDATA_DIR="/must/not/be/used")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "e4 unit with exp 0404's switches: df12bb2de3e90b8c82a234eedf0babb5; fl test: fl0401: 74 of 74 cases; end" in r.stdout, r.stdout
    assert "e4 sav mksav0401.py src/libs/libSaveData.cpp:" in r.stdout and "e4 test sav0401: sav0401: on 3 of 3; end" in r.stdout, r.stdout
    assert md5(b.e / "x-sav/src/libs/libSaveData.cpp") == "04f4c5bb05179b80fd7cf1e41832cdd9"
    assert md5(b.e / "x-pth/src/kernel/pthread.cpp") == "0363847bd540883467dee22797475031" and "e4 test pth0401: pth0401: on 3 of 3; end / pth0401: off 3 of 3; end / pth0401: off 3 of 3; end" in r.stdout
    assert md5(b.e / "x-aud/src/libs/libAudio2.cpp") == "7a1914c898e62e1e6ce699807aafbc74" and "e4 test aud0401: aud0401: on 3 of 3; end" in r.stdout
    assert md5(b.e / "x-amm/src/libs/libAmpr.cpp") == "0a1762f6440f421586b56767d27d0770" and "e4 test amm0401: amm0401: on 3 of 3; end" in r.stdout
    assert "e4 test savcb0401: sav0401: on 3 of 3; end" in r.stdout and "e4 test savsort0401: sav0401: on 3 of 3; end" in r.stdout, r.stdout
    assert (b.e / "run-savcb0401-on" / "where.txt").is_file() and not (b.e / "raw/savcb0401").exists()   # one program, run per switch
    for g in ("on", "off", "unset"):   # each run in its own fresh directory under exp0401e4
        assert (b.e / f"run-sav0401-{g}" / "where.txt").read_text().strip().endswith(f"run-sav0401-{g}"), g
    d = (b.e / "play-pkg-0401.sh").read_text()
    assert "EMU=~/bc5-work/exp0401e4/bin/kyty_emulator" in d and 'mv "$LOG" "${LOG%.log}-$(date -r "$LOG"' in d, d
    assert b.box("release", b.token).stdout.strip() == "released" and b.lock() == ""
    b = Box("sere4p", series="e4")
    (b.root / "src/KytyPlus/src/libs/libSaveData.cpp").write_bytes(b"changed\n")
    r = b.claim()
    assert r.returncode == 1 and "the tree's src/libs/libSaveData.cpp is not" in r.stdout, r.stdout


def t_series_e5():
    b = Box("sere5", series="e5").up()
    r = b.box("build", b.token, FAKE_NO_E5="1")
    assert r.returncode == 1 and "lacks [" in r.stdout, r.stdout
    b.send()
    assert b.box("setup", b.token).returncode == 0
    r = b.box("build", b.token, KYTY_BC5_SAVEDATA_DIR="/must/not/be/used")
    assert r.returncode == 0, r.stdout + r.stderr
    for e in [['eq', 'mkeq0405.py', '-', 'src/kernel/eventQueue.cpp:c45e6a72c8e419d98059c3477a9373cc:d8eaa6d22e3e415ea8331dced30867c0', 'src/libs/bc5LleAgc.cpp:df12bb2de3e90b8c82a234eedf0babb5:09770e46272ed52107f055c6f1af2332'], ['gpu', 'mkgpu0405.py', '--chain', 'src/libs/bc5LleAgc.cpp:09770e46272ed52107f055c6f1af2332:d1cfd9bb1f1b3485bed4207a7f064d4f'], ['thr', 'mkthr0405.py', '-', 'src/kernel/pthread.cpp:0363847bd540883467dee22797475031:81ee12c4fa3e61df4f4b7239356b9f60', 'src/kernel/semaphore.cpp:c9c4aaf56492434eb84dc6e899260ae8:3aa9c8b441438483d124115d3961c9b0'], ['mem', 'mkmem0405.py', '-', 'src/kernel/memory.cpp:43713ef677ec887a8ca273f7ab5cee90:95d9ca880d01db26d51f0ecabcdfa7e1'], ['fs', 'mkfs0405.py', '-', 'src/kernel/fileSystem.cpp:f1b5f5288faddd78deff2dbd1b613e1f:a7201a1ab20dc60d876ad64f0dd4d086', 'src/libs/libKernel.cpp:3bf94a6168d176d591730bac33dff5b1:b353287342a8eb82305a4592a4021e3d'], ['svc', 'mksvc0405.py', '-', 'src/libs/libSaveData.cpp:04f4c5bb05179b80fd7cf1e41832cdd9:0e0c5d409286893e9956df9aeba845f5', 'src/libs/libNet.cpp:f7a26ceb10a4cf669c33ed592eb1e89d:35773d6e769b85be74012a86c0f02e89', 'src/libs/libPad.cpp:dbe268d7dff6134db45ad4328aace716:89a047a4f1ad39847bf76c15fa0d4c14'], ['lib', 'mklib0405.py', '-', 'src/libs/libJson2.cpp:d38d30582b49f57f9ef3fea6d84584be:85144ef10cbfe295d24ab7096710aa10', 'src/libs/libUlt.cpp:9198f40703960fe46e9ba066a6c58ac3:191fe8b19bf663af73f48cfc85535a5d', 'src/libs/libUserService.cpp:4f90ba6b94167d9b857c8efa89f1cf47:e3d34e9896ac5e6568f691f7c9699a06', 'src/libs/libSystemService.cpp:6c2a2925078d2facd4abe9412408dd57:4aa00c539657776620a49e222f3f8fa2'], ['ao', 'mkao0405.py', '-', '+src/bc5/pad_audio_route.hpp:51131854822a629c2b24739e3603ef5d', 'src/libs/audio.cpp:f58ec0105874173a9f84954706a17e96:230f732dbc20b9b196b28cb007ba95ec'], ['tls', 'mktls0405.py', '-', '+src/loader/jit.h:8b5a53504af3ca127c1ab4fe9b55ee45', 'src/loader/runtimeLinker.cpp:e94b25b8b37d36d97a074ea02723b733:aba94c24ad35a1c944ad3bd5843b13ef']]:   # each script's outputs as pinned, and the chain: each unit's last writer is the one built
        for f in e[3:]:
            if f.startswith("+"):
                continue
            rel, _, out = f.split(":")
            assert md5(b.e / ("x5-" + e[0]) / rel) == out, (e[0], rel)
    for n in ['eq0405', 'ao0405', 'mem0405', 'thr0405', 'svc0405', 'gpu0405', 'fs0405', 'lib0405', 'tls0405'] + ["sav0401", "pth0401", "aud0401", "vo0401", "amm0401"]:   # e5's tests and e4's, over e5's objects
        assert ("test %s: " % n) in r.stdout and ("%s: on 3 of 3; end" % n) in r.stdout, (n, r.stdout)
    bu = load("build0401")
    args = (b.root / "build-args.txt").read_text().splitlines()
    incs, units, gts = bu.parse_rest(args[5:])   # no unit twice (parse_rest asserts it), and each the last writer's
    last = {}
    for e in [['eq', 'mkeq0405.py', '-', 'src/kernel/eventQueue.cpp:c45e6a72c8e419d98059c3477a9373cc:d8eaa6d22e3e415ea8331dced30867c0', 'src/libs/bc5LleAgc.cpp:df12bb2de3e90b8c82a234eedf0babb5:09770e46272ed52107f055c6f1af2332'], ['gpu', 'mkgpu0405.py', '--chain', 'src/libs/bc5LleAgc.cpp:09770e46272ed52107f055c6f1af2332:d1cfd9bb1f1b3485bed4207a7f064d4f'], ['thr', 'mkthr0405.py', '-', 'src/kernel/pthread.cpp:0363847bd540883467dee22797475031:81ee12c4fa3e61df4f4b7239356b9f60', 'src/kernel/semaphore.cpp:c9c4aaf56492434eb84dc6e899260ae8:3aa9c8b441438483d124115d3961c9b0'], ['mem', 'mkmem0405.py', '-', 'src/kernel/memory.cpp:43713ef677ec887a8ca273f7ab5cee90:95d9ca880d01db26d51f0ecabcdfa7e1'], ['fs', 'mkfs0405.py', '-', 'src/kernel/fileSystem.cpp:f1b5f5288faddd78deff2dbd1b613e1f:a7201a1ab20dc60d876ad64f0dd4d086', 'src/libs/libKernel.cpp:3bf94a6168d176d591730bac33dff5b1:b353287342a8eb82305a4592a4021e3d'], ['svc', 'mksvc0405.py', '-', 'src/libs/libSaveData.cpp:04f4c5bb05179b80fd7cf1e41832cdd9:0e0c5d409286893e9956df9aeba845f5', 'src/libs/libNet.cpp:f7a26ceb10a4cf669c33ed592eb1e89d:35773d6e769b85be74012a86c0f02e89', 'src/libs/libPad.cpp:dbe268d7dff6134db45ad4328aace716:89a047a4f1ad39847bf76c15fa0d4c14'], ['lib', 'mklib0405.py', '-', 'src/libs/libJson2.cpp:d38d30582b49f57f9ef3fea6d84584be:85144ef10cbfe295d24ab7096710aa10', 'src/libs/libUlt.cpp:9198f40703960fe46e9ba066a6c58ac3:191fe8b19bf663af73f48cfc85535a5d', 'src/libs/libUserService.cpp:4f90ba6b94167d9b857c8efa89f1cf47:e3d34e9896ac5e6568f691f7c9699a06', 'src/libs/libSystemService.cpp:6c2a2925078d2facd4abe9412408dd57:4aa00c539657776620a49e222f3f8fa2'], ['ao', 'mkao0405.py', '-', '+src/bc5/pad_audio_route.hpp:51131854822a629c2b24739e3603ef5d', 'src/libs/audio.cpp:f58ec0105874173a9f84954706a17e96:230f732dbc20b9b196b28cb007ba95ec'], ['tls', 'mktls0405.py', '-', '+src/loader/jit.h:8b5a53504af3ca127c1ab4fe9b55ee45', 'src/loader/runtimeLinker.cpp:e94b25b8b37d36d97a074ea02723b733:aba94c24ad35a1c944ad3bd5843b13ef']]:
        for f in e[3:]:
            if not f.startswith("+"):
                last[f.split(":")[0]] = "x5-" + e[0]
    for rel, x in last.items():
        if rel == "src/libs/bc5LleAgc.cpp":
            assert md5(b.e / "src/bc5LleAgc.cpp") == md5(b.e / x / rel) and (b.e / "src/bc5LleAgc-e4.cpp").is_file()
            assert md5(b.e / "src/bc5LleAgc-e4.cpp") == "df12bb2de3e90b8c82a234eedf0babb5"
        else:
            assert units[rel].replace("\\", "/").endswith("%s/%s" % (x, rel)), (rel, units.get(rel))
    assert units["src/libs/libAudio2.cpp"].endswith("x-aud/src/libs/libAudio2.cpp")   # e4's units stay where e5 left them alone
    if "src/kernel/memory.cpp" in last:
        assert (b.e / last["src/kernel/memory.cpp"] / "src/kernel/memoryAddressSpace.inc").is_file()   # beside the unit
    assert len(gts) == len(set(g[1] for g in gts)), gts
    d = (b.e / "play-pkg-0401.sh").read_text()
    assert "EMU=~/bc5-work/exp0401e5/bin/kyty_emulator" in d and 'mv "$LOG" "${LOG%.log}-$(date -r "$LOG"' in d, d
    assert b.box("release", b.token).stdout.strip() == "released" and b.lock() == ""

def t_series_e6p():
    b = Box("sere6p", series="e6p").up()
    r = b.box("build", b.token, FAKE_BKTEST_FAIL="1")
    assert r.returncode == 1 and "the backend's tests failed" in r.stdout and not (b.e / "bin/kyty_emulator").exists(), r.stdout
    for env, why in ((dict(FAKE_PRED_CASES="3"), "G7's cases are not the four"), (dict(FAKE_BK_FAIL="1"), "the private backend did not build"),
                     (dict(FAKE_NO_E6P="1"), "lacks [BC5_R3_PREDICATION]")):
        b.send()
        assert b.box("setup", b.token).returncode == 0
        r = b.box("build", b.token, **env)
        assert r.returncode == 1 and why in r.stdout, (env, r.stdout)
    b.send()
    assert b.box("setup", b.token).returncode == 0
    r = b.box("build", b.token, KYTY_BC5_SAVEDATA_DIR="/must/not/be/used", BC5_R3_PREDICATION="1")
    assert r.returncode == 0, r.stdout + r.stderr
    for rel, want in (("src/policy.cpp", "8e22ce87d7a7491e448e39edc9fad6e6"), ("include/bc5/policy.hpp", "89f098bec587eb630b174bbb002ae482"),
                      ("tests/policy_test.cpp", "7f81a28ad3b171ecbd6389b5257fd6a4")):
        assert md5(b.e / "bk" / rel) == want and md5(b.bs / rel) != want, rel   # the copy is edited, the shared source is not
    assert "e6p backend tests: All tests passed (32077 assertions in 160 test cases); G7: All tests passed (190 assertions in 4 test cases)" in r.stdout, r.stdout
    assert "e6p switch: unset All tests passed (3 assertions in 1 test case); empty All tests passed" in r.stdout and "bool All tests passed" in r.stdout, r.stdout
    assert "private archive" in r.stdout and "e5 unit:" in r.stdout and "e4 unit with exp 0404's switches" in r.stdout, r.stdout
    for n in ["eq0405", "gpu0405", "tls0405", "sav0401", "amm0401"]:   # e5's and e4's tests still run
        assert ("%s: on 3 of 3; end" % n) in r.stdout, (n, r.stdout)
    bu = load("build0401")
    args = (b.root / "build-args.txt").read_text().splitlines()
    rest, archive = bu.split_archive(args[5:])
    assert archive is not None and archive[0].endswith("bc5-work/backend-ubuntu/libbc5_backend.a") and archive[1].endswith("exp0401e6p/bk-build/libbc5_backend.a"), archive
    bu.parse_rest(rest)   # the rest is e5's list, no unit twice
    d = (b.e / "play-pkg-0401.sh").read_text()
    assert "EMU=~/bc5-work/exp0401e6p/bin/kyty_emulator" in d, d
    assert b.box("release", b.token).stdout.strip() == "released" and b.lock() == ""
    b = Box("sere6pa", series="e6p").up()   # the shared source differs from main's in one file: nothing built
    (b.bs / "src/pm4.cpp").write_bytes((b.bs / "src/pm4.cpp").read_bytes() + b"// changed\n")
    r = b.box("build", b.token)
    assert r.returncode == 1 and "the shared backend source is not main's" in r.stdout and "pm4.cpp" in r.stdout, r.stdout
    assert b.box("release", b.token).stdout.strip() == "released"
    b = Box("sere6pb", series="e6p").up()   # one file more than main's
    (b.bs / "src/extra.cpp").write_bytes(b"// extra\n")
    r = b.box("build", b.token)
    assert r.returncode == 1 and "files more or less than main's" in r.stdout and "extra.cpp" in r.stdout, r.stdout
    assert b.box("release", b.token).stdout.strip() == "released"


def t_series_e6():
    b = Box("sere6", series="e6").up()
    r = b.box("build", b.token, FAKE_NO_E6="1")
    assert r.returncode == 1 and "lacks [KYTY_BC5_FW_PAD]" in r.stdout, r.stdout
    b.send()
    assert b.box("setup", b.token).returncode == 0
    r = b.box("build", b.token, KYTY_BC5_SAVEDATA_DIR="/must/not/be/used")
    assert r.returncode == 0, r.stdout + r.stderr
    for e in [['fwn', 'mkfwn0405.py', '-', 'src/libs/libRtc.cpp:e1689ac69353d76f206bd7bb7736d3b8:719561dd7cc51c965c9ae97a07df01fb', 'src/libs/libRudp.cpp:9fbe2847b2aa61564c9eea80ceb4617a:af8d0178fa63f7e5a2f5bf2d72d9690c', 'src/libs/network.cpp:98d501f4e09322ab8727dd65ff0ea45c:598cfe806da831d5a07a5f506d13a03c', 'src/libs/libSystemService.cpp:4aa00c539657776620a49e222f3f8fa2:252a35f9f9b482e9c9fb74b2c0740a2f', 'src/libs/libNpCppWebApi.cpp:935fcc7e4ab1108f3d2d8b33eaf65bf6:e613bc8fcc3f58fe5b5ff3be47a9cc46'], ['fwa', 'mkfwa0405.py', '-', 'src/libs/audio.cpp:230f732dbc20b9b196b28cb007ba95ec:1f90e7520a6641c8ff3affb06993372d', 'src/libs/avPlayer.cpp:966cb8a847467b64ce0486168f052a82:44203af3c14874fee232808fc4aa6568'], ['jit', 'mkjit0405.py', '-', 'src/kernel/memory.cpp:95d9ca880d01db26d51f0ecabcdfa7e1:ee24c888f976cc125502cf3a31006349', 'src/libs/libKernel.cpp:b353287342a8eb82305a4592a4021e3d:0a0d46657d8088b72a9ba67e2fbcc310'], ['tbc', 'mktbc0405.py', '-', 'src/libs/libZlib.cpp:f5d3aafebca0d202082365ee609f15b6:c7e165b9b288d71f874d5d6c6dbd363c', 'src/libs/libJpeg.cpp:a85a83b8d541f5e10c14d739ff56457f:c5fe947cc30001c49bd2b1f8af7a0e2c', 'src/libs/libIme.cpp:a572240f789088264b6e13850978b739:49fa46f1d8005245e7f0b266d8b29659'], ['tbn', 'mktbn0405.py', '-', 'src/libs/libNp.cpp:a2c5facee2708bed1556383b0f5bbdca:24e778261495abcd5a069396f14b28b4'], ['tld', 'mktld0405.py', '-', 'src/libs/libs.cpp:309aecf7c85a5b47217060bb87ec6512:903fa699db7c20b2b3f288ab572bce8d'], ['pad', 'mkpad0405.py', '-', 'src/libs/libPad.cpp:89a047a4f1ad39847bf76c15fa0d4c14:b9940ebe905e9ef1e31b117b531632fd']]:   # each e6 script's outputs as pinned
        for f in e[3:]:
            rel, _, out = f.split(":")
            assert md5(b.e / ("x5-" + e[0]) / rel) == out, (e[0], rel)
    for n in ['fwn0405', 'fwa0405', 'jit0405', 'tbc0405', 'tbn0405', 'tld0405', 'pad0405'] + ["eq0405", "gpu0405", "tls0405", "sav0401", "amm0401"]:   # e6's tests, e5's and e4's
        assert ("%s: on 3 of 3; end" % n) in r.stdout, (n, r.stdout)
    assert "e6 fwn mkfwn0405.py" in r.stdout and "e6 test tld0405: tld0405: on 3 of 3; end" in r.stdout, r.stdout
    bu = load("build0401")
    args = (b.root / "build-args.txt").read_text().splitlines()
    rest, archive = bu.split_archive(args[5:])
    assert archive is None   # e6 links the shared archive
    incs, units, gts = bu.parse_rest(rest)   # no unit twice
    for e in [['fwn', 'mkfwn0405.py', '-', 'src/libs/libRtc.cpp:e1689ac69353d76f206bd7bb7736d3b8:719561dd7cc51c965c9ae97a07df01fb', 'src/libs/libRudp.cpp:9fbe2847b2aa61564c9eea80ceb4617a:af8d0178fa63f7e5a2f5bf2d72d9690c', 'src/libs/network.cpp:98d501f4e09322ab8727dd65ff0ea45c:598cfe806da831d5a07a5f506d13a03c', 'src/libs/libSystemService.cpp:4aa00c539657776620a49e222f3f8fa2:252a35f9f9b482e9c9fb74b2c0740a2f', 'src/libs/libNpCppWebApi.cpp:935fcc7e4ab1108f3d2d8b33eaf65bf6:e613bc8fcc3f58fe5b5ff3be47a9cc46'], ['fwa', 'mkfwa0405.py', '-', 'src/libs/audio.cpp:230f732dbc20b9b196b28cb007ba95ec:1f90e7520a6641c8ff3affb06993372d', 'src/libs/avPlayer.cpp:966cb8a847467b64ce0486168f052a82:44203af3c14874fee232808fc4aa6568'], ['jit', 'mkjit0405.py', '-', 'src/kernel/memory.cpp:95d9ca880d01db26d51f0ecabcdfa7e1:ee24c888f976cc125502cf3a31006349', 'src/libs/libKernel.cpp:b353287342a8eb82305a4592a4021e3d:0a0d46657d8088b72a9ba67e2fbcc310'], ['tbc', 'mktbc0405.py', '-', 'src/libs/libZlib.cpp:f5d3aafebca0d202082365ee609f15b6:c7e165b9b288d71f874d5d6c6dbd363c', 'src/libs/libJpeg.cpp:a85a83b8d541f5e10c14d739ff56457f:c5fe947cc30001c49bd2b1f8af7a0e2c', 'src/libs/libIme.cpp:a572240f789088264b6e13850978b739:49fa46f1d8005245e7f0b266d8b29659'], ['tbn', 'mktbn0405.py', '-', 'src/libs/libNp.cpp:a2c5facee2708bed1556383b0f5bbdca:24e778261495abcd5a069396f14b28b4'], ['tld', 'mktld0405.py', '-', 'src/libs/libs.cpp:309aecf7c85a5b47217060bb87ec6512:903fa699db7c20b2b3f288ab572bce8d'], ['pad', 'mkpad0405.py', '-', 'src/libs/libPad.cpp:89a047a4f1ad39847bf76c15fa0d4c14:b9940ebe905e9ef1e31b117b531632fd']]:   # every unit an e6 script writes is built from e6's output, e5's own outputs included
        for f in e[3:]:
            rel = f.split(":")[0]
            assert units[rel].replace("\\", "/").endswith("x5-%s/%s" % (e[0], rel)), (rel, units.get(rel))
    assert units["src/libs/libJson2.cpp"].endswith("x5-lib/src/libs/libJson2.cpp")   # e5's units stay where e6 left them alone
    assert len(gts) == len(set(g[1] for g in gts)) and any(g[1].endswith("tld0405") for g in gts), gts
    d = (b.e / "play-pkg-0401.sh").read_text()
    assert "EMU=~/bc5-work/exp0401e6/bin/kyty_emulator" in d, d
    assert b.box("release", b.token).stdout.strip() == "released" and b.lock() == ""


def t_link_archive_swap():
    bu = load("build0401")
    db = [{"output": "src/kyty_emulator", "command": "/usr/bin/c++ -O2 src/CMakeFiles/kyty_emulator.dir/libs/bc5LleAgc.cpp.o -o src/kyty_emulator /home/u/bc5-work/backend-ubuntu/libbc5_backend.a -ldrm"}]
    a = bu.link_argv(db, "/p/unit.o", "/p/out", None, ("/home/u/bc5-work/backend-ubuntu/libbc5_backend.a", "/p/bk/libbc5_backend.a"))
    assert "/p/bk/libbc5_backend.a" in a and "/home/u/bc5-work/backend-ubuntu/libbc5_backend.a" not in a, a
    db[0]["command"] = db[0]["command"].replace("/home/u/bc5-work/backend-ubuntu/libbc5_backend.a", "../../backend-ubuntu/libbc5_backend.a")
    a = bu.link_argv(db, "/p/unit.o", "/p/out", None, ("/home/u/bc5-work/backend-ubuntu/libbc5_backend.a", "/p/bk/libbc5_backend.a"))
    assert "/p/bk/libbc5_backend.a" in a, a   # by its file name when the line names it relatively
    assert bu.split_archive(["x", "--archive", "s", "p", "--gate", "g", "o"]) == (["x", "--gate", "g", "o"], ("s", "p"))
    assert bu.split_archive(["x"]) == (["x"], None)


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
    e2 = mk.edit(s, acb=True, restore=True, catcher=True, inherit=True)   # series e2: e plus exp 0403's ACB_INHERIT
    assert hashlib.md5(e2).hexdigest() == "73e8e4e0a9d05e5deae426238a24c91d"
    assert e2.index(b"static thread_local uint32_t t_acb_from") < e2.index(b"static void submit_segment(") < e2.index(b"static int acb_inherit_mode() {")
    assert e2.index(b"static int acb_inherit_mode() {") < e2.index(b"&& acb_inherit_mode() == 0; // + exp 0403: ACB_INHERIT wins")
    assert e2.index(b"struct ChainSeg {") < e2.index(b"acb_inherit_take(gq)") and e2.count(b"acb_inherit_census(ib + q, len);") == 1
    for anchor, text, where in mk.inherit_edits():
        if where != "replace":
            assert e2.count(text) == 1, text[:60]
        if anchor not in s:   # text the acb edits add: their own anchors are checked above
            continue
        try:
            mk.edit(s.replace(anchor, b""), acb=True, restore=True, catcher=True, inherit=True)
        except AssertionError:
            continue
        raise SystemExit("a unit without an inherit anchor passed")
    try:
        mk.edit(s, inherit=True)
    except AssertionError:
        pass
    else:
        raise SystemExit("ACB_INHERIT passed without the acb CS prefix")
    e3w = mk.edit(s, acb=True, restore=True, catcher=True, inherit2=True, memline=True)   # the e3 draft (exp0401e3w), for the record
    assert hashlib.md5(e3w).hexdigest() == "989ca24b6e41843d0143ec0bbc53d15b" and e3w.count(mk.INHERIT_SCAN) == 1
    e3 = mk.edit(s, acb=True, restore=True, catcher=True, inherit3=True, memline=True)   # series e3: exp 0403's queue mode + the memory line
    assert hashlib.md5(e3).hexdigest() == "d3b7f9b0ab43184ee11de83e9e233ff8"
    assert e3.count(mk.INHERIT_SCAN3) == 1 and e3.count(mk.MEMLINE_FUNCTIONS2) == 1 and e3.count(mk.INHERIT_FUNCTIONS3) == 1
    assert e3.count(mk.MEMLINE_PARSE) == 1 and mk.MEMLINE_FUNCTIONS not in e3 and b"MISMATCH" not in e3
    assert e3.count(b"const bool  skip   = head && mode == 3; // the only mode that drops") == 1   # queue mode never drops
    assert e3w.count(mk.MEMLINE_FUNCTIONS) == 1   # the draft keeps its first memory line
    assert e3.index(mk.INHERIT_SCAN3) < e3.index(b"static void acb_inherit_track(") and b"ud32" not in e3 and b"\"wave\"" not in e3
    assert e3.count(b"std::strcmp(e, \"queue\") == 0") == 1
    assert e3.count(b"mem_line_start(); // experiment 0401 series e3") == 1
    assert e3.index(b"static void mem_line_start()") < e3.index(b"mem_line_start(); // experiment 0401 series e3")
    assert mk.edit(s, acb=True, restore=True, catcher=True, inherit=True) == e2   # e2 stays as it was built
    try:
        mk.edit(s, acb=True, inherit=True, inherit3=True)
    except AssertionError:
        pass
    else:
        raise SystemExit("both ACB_INHERIT versions passed")
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
    assert bu.parse_rest(["/e/inc", "src/kernel/memory.cpp=/e/m.cpp", "--gate", "/e/g.cpp", "/e/g"]) == (["/e/inc"], {"src/kernel/memory.cpp": "/e/m.cpp"}, [("/e/g.cpp", "/e/g", bu.GATE_LIKE)])
    assert bu.parse_rest(["/e/zinc"]) == (["/e/zinc"], {}, []) and bu.parse_rest([]) == ([], {}, [])
    assert bu.parse_rest(["/e/a", "--inc", "/e/b", "--gate", "/e/g.cpp", "/e/g", "--gate", "/e/p.cpp", "/e/p", "--like", "src/kernel/pthread.cpp"]) == (
        ["/e/a", "/e/b"], {}, [("/e/g.cpp", "/e/g", bu.GATE_LIKE), ("/e/p.cpp", "/e/p", "src/CMakeFiles/kyty_emulator.dir/kernel/pthread.cpp.o")])
    assert bu.compile_argv(db, "/e/u.cpp", "/e/u.o", ["/e/a", "/e/b"]) == ["clang++", "-I/e/a", "-I/e/b", "-I/a", "-o", "/e/u.o", "-c", "/e/u.cpp"]
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
    assert len(cases) == 31, len(cases)
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
