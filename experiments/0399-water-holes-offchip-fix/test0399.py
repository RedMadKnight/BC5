#!/usr/bin/env python3
"""BC5 experiment 0399: local tests of the real box0399.sh and gates0399.py, on the laptop, with no box.
usage: python test0399.py <work dir> [case name part]
Every case gets a synthetic root under <work dir>/0399-test-<pid>/, the only place box0399.sh accepts stand-ins from. Stand-ins
sit at the box's edge alone (clock, dmesg, container, shots, poller); locks, queue, claim, process marks, deadline, paths,
launcher derivation, route steps, gates and cleanup are the real code. Real processes stand in for the emulator (a copy of
sleep.exe named kyty_emulator), so the identity checks read a real /proc. HOME and PATH are never changed; no launcher, game,
SSH or GPU is touched. Symlinks are real to Git Bash through MSYS=winsymlinks:sys; junctions cover the Windows link kind.
Not reachable here, stated in the README: a real distrobox/podman chain, /proc/PID/mem (the poller's reads), foreign uids
and a second file system."""
import hashlib, importlib.util, json, os, re, shutil, subprocess, sys, time, traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASH = "C:/Program Files/Git/bin/bash.exe"
KIT = ["box0399.sh", "gates0399.py", "pl0399.py", "sn0399.py", "tz0399.py", "bt0362.sh", "patch0399.py", "swz0248-z4.json", "input-0399.cfg",
       "arms0399.txt", "relink0399.py", "zp0399.py", "K4.zp.txt"]
K3_TZ = HERE.parent / "0369-lake-last-burst-writer/raw/K3.tz.txt"
K2_TZ = HERE.parent / "0369-lake-last-burst-writer/raw/K2.tz.txt"
PL_OK = "# frozen view, emulator at 212.0 s: polling begins\n# 1355441 polls in 85.0 s (mean period 0.063 ms, largest gap 2436.1 ms); polls with a change: D 20335, P 2816; 2228 frames; 34 captures, 408 snapshots (1 torn)\n"
PL_FEW = "# frozen view, emulator at 212.0 s: polling begins\n# 1355441 polls in 85.0 s (mean period 0.063 ms, largest gap 2436.1 ms); polls with a change: D 3, P 2; 2 frames; 1 captures, 2 snapshots (0 torn)\n"
BASE = FRESH = READY = None
spec = importlib.util.spec_from_file_location("gates0399", HERE / "gates0399.py")
gates = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gates)


def posix(p):
    v = Path(p).resolve().as_posix()
    return "/" + v[0].lower() + v[2:]


FAKE = r'''# stand-ins for one test case, at the box's edge only
ROOT=$BC5_0399_ROOT
. "$ROOT/pins.sh"
DBX=(env); PY=(python); KS=(sleep 300)
REAP_TERM=8; REAP_KILL=4; REAP_WAIT=30; WATCH_NAP=1; WATCH_WAIT=1200; SLOTWAIT=1; LOADWAIT=1; KEYWAIT=4000; STEP=1; EMU_WAIT=1200
[ ! -f "$ROOT/tune.sh" ] || . "$ROOT/tune.sh"
exec 9<>"$ROOT/nap.fifo"
now() { local c; if [ -s "$ROOT/clock" ]; then read -r c < "$ROOT/clock"; echo "$c"; else printf '%(%s)T
' -1; fi; }
nap() { read -r -t 0.05 -u 9 _; return 0; }
private_dir() { mkdir "$@"; }
hook() { printf '%s\n' "$1" >> "$ROOT/order.log"; if [ -f "$ROOT/hook-$1.sh" ]; then . "$ROOT/hook-$1.sh"; fi; return 0; }
session() { "$@"; }
boot_id() { echo test-boot; }
dmesg_read() { [ ! -e "$ROOT/no-dmesg" ] && cat "$ROOT/dmesg.txt"; }
compress_idle() { [ ! -e "$ROOT/compress-runs" ]; }
atime_ok() { [ ! -e "$ROOT/noatime" ]; }
save_read_since() { [ ! -e "$ROOT/no-route-read" ]; }
disk_pct() { if [ -e "$ROOT/disk-full" ]; then echo 90; else echo 50; fi; }
shot() { [ -e "$ROOT/no-shot" ] || printf png > "$1"; }
bundle() { [ ! -e "$ROOT/tar-fails" ] || return 1; tar cf "$@"; }
poller() {   # the real one reads /proc/PID/mem, which this laptop has not got
    local out=$3
    [ ! -e "$ROOT/poller-fails" ] || { echo "snapshot read error: stop"; return 1; }
    printf '1.000 2.0 D0 P1\n1.006 2.1 D1 P0\n1.033 2.2 D0 P1\n1.040 2.3 D1 P0\n1.066 2.4 D0 P1\n' > "$out/events.txt"
    printf 'c00 f0\n' > "$out/snaps.txt"; printf x > "$out/c00.f0.sF.bin"
    cat "$ROOT/pl-fixture.txt"
}
in_box() {
    shift
    case "$*" in
        *--selftest*) [ ! -e "$ROOT/selftest-fails" ] ;;
        *"cmake -S"*) [ ! -e "$ROOT/backend-fails" ] || { echo "x.cpp:1: error: no"; return 1; } ;;
        *bc5_backend_tests*) [ ! -e "$ROOT/tests-fail" ] ;;
        *"ninja -t compdb"*) echo '[]' ;;
        *relink0399.py*) [ ! -e "$ROOT/link-fails" ] || return 1
            cp "$ROOT/bin/kyty_emulator.exe" "$TB_BIN.exe"
            [ -e "$ROOT/no-switches" ] || printf BC5_DIRECT_LAKE_CTL >> "$TB_BIN.exe" ;;
        *patch0399.py*) [ ! -e "$ROOT/patch-fails" ] || return 1
            local f; shift 2; for f in "$@"; do echo "$f: patch  $(cat "$ROOT/patch-value") %"; done ;;
        *sn0399.py*) [ ! -e "$ROOT/sn-fails" ] || return 1; echo '{}' > "$7"; echo "# sF: fixture" ;;
        *tz0399.py*) [ ! -e "$ROOT/tz-fails" ] || return 1; cat "$ROOT/tz-fixture.txt" ;;
        *) echo "unknown in_box: $*"; return 1 ;;
    esac
}
'''
ANCHORS = '''#!/bin/bash
: <<'ANCHORS'
LOG=~/bc5-work/play-pkg-last.log
  EMU=~/bc5-work/kytyplus-build-lean/src/kyty_emulator LOG=~/bc5-work/play-pkg-lean-last.log
MLOG=~/bc5-work/play-pkg-mount.log
done < "$ENVF"
export KYTY_BC5_SAVEDATA_DIR=$HOME/bc5-work/_SaveData-pkg-play
export BC5_DIRECT_LEARNED=$HOME/bc5-work/direct-learned-pkg.txt
cd ~/bc5-work
ANCHORS
. "$BC5_0399_ROOT/launcher-body.sh"
'''
BODY = r'''ROOT=$BC5_0399_ROOT
cd "$ROOT/bc5-work/exp0399/wd" || exit 9
J=$ROOT/bc5-data/captures/play-$(date +%Y%m%d-%H%M)/gc
mkdir -p "$J"
[ -e "$ROOT/no-journal" ] || cp "$ROOT/journal-fixture.log" "$J/direct.log"
[ ! -e "$ROOT/journal-is-dir" ] || { rm -f "$J/direct.log"; mkdir "$J/direct.log"; }
[ ! -e "$ROOT/journal-stale" ] || touch -d '2020-01-01 00:00:00' "$J/direct.log"
. "$ROOT/env-fixture.sh"
( exec 9<>"$ROOT/nap.fifo"; while :; do mapfile -t L < "$KYTY_BC5_INPUT_CMD"; echo "${#L[@]}" > "$KYTY_BC5_INPUT_CMD.done"; read -r -t 0.05 -u 9 _; done ) &
H=$!
env -i PATH="$PATH" SYSTEMROOT="${SYSTEMROOT:-}" WINDIR="${WINDIR:-}" HOME="$ROOT" "BC5_0399_OWNER=$BC5_0399_OWNER" BC5_GC_DUMP_DIR="$J" \
    KYTY_BC5_INPUT_CMD="$KYTY_BC5_INPUT_CMD" KYTY_BC5_INPUT_CONFIG="$BC5_0399_INPUT_CONFIG" BC5_0399_INPUT_CONFIG="$BC5_0399_INPUT_CONFIG" \
    BC5_EMU="$BC5_EMU" BC5_DIRECT_LAKE_CTL="$BC5_DIRECT_LAKE_CTL" BC5_DIRECT_LAKE_OUT="$BC5_DIRECT_LAKE_OUT" BC5_DIRECT_GC_HS_OFFCHIP="$BC5_DIRECT_GC_HS_OFFCHIP" \
    "${ENVV[@]}" "$BC5_EMU" 300 &
EP=$!
trap 'kill "$EP" 2> /dev/null' TERM
wait "$EP"; rc=$?
kill "$H" 2> /dev/null
exit "$rc"
'''


class Box:
    def __init__(self, name, template=None):
        self.root = BASE / name
        self.root.mkdir(parents=True)
        self.r = posix(self.root)
        self.w = self.root / "bc5-work"
        self.e = self.w / "exp0399"
        self.env = dict(os.environ, BC5_0399_ROOT=self.r, BC5_0399_FAKE=self.r + "/fake.sh", MSYS="winsymlinks:sys")
        self.token = None
        self.deadline = None
        self.procs = []
        if template is None:
            self.build()
        else:
            self.copy_of(template)

    def bashc(self, cmd, timeout=60):
        return subprocess.run([BASH, "-c", cmd], env=self.env, text=True, capture_output=True, timeout=timeout)

    def write(self, rel, text):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)

    def build(self):
        r = self.r
        for rel, text in [("fake.sh", FAKE), ("launcher-body.sh", BODY), ("bc5-work/play-pkg.sh", ANCHORS), ("dmesg.txt", "boot line\n"),
                          ("pl-fixture.txt", PL_OK), ("patch-value", "9.5\n"), ("bc5-work/BOX-LOCK", ""), ("bc5-work/BOX-QUEUE", "somebody | an old line\n"),
                          ("bc5-work/bc5-run.env", "BC5_GC_MODE=direct\n"), ("bc5-work/backend-ubuntu/libbc5_backend.a", "archive\n"),
                          ("bc5-work/direct-learned-pkg.txt", "0x1\n"), ("bc5-work/exp0389/direct-learned-pkg.txt", "0x0\n"), ("bc5-work/_SaveData/PPSA03671/SAVE1/data.bin", "live save\n"),
                          ("bc5-work/saves-lake-1153/SAVE3/data.bin", "lake save\n"), ("bc5-work/exp0299/wd/_SaveData/PPSA03671/sentinel", "exp 0299's save\n"),
                          ("bc5-work/resource", "a work file\n"),
                          ("bc5-work/backend-ubuntu/CMakeCache.txt", "CMAKE_BUILD_TYPE:STRING=Release\nCMAKE_CXX_COMPILER:FILEPATH=/usr/bin/clang++\n")]:
            self.write(rel, text)
        shutil.copy(K3_TZ, self.root / "tz-fixture.txt")
        (self.root / "journal-fixture.log").write_text("[bc5-direct] learned regions: 1 from /priv/learned.txt\n" + "VideoOutSubmitFlip took 1 ms\n" * 1200, newline="\n")
        (self.root / "bc5-data/captures/devcoredump").mkdir(parents=True)
        (self.w / "exp0330/wd/_SaveData").mkdir(parents=True)
        self.write_env()
        rc = self.bashc(f'''set -e
            cd {r}; mkfifo nap.fifo; mkdir -p bin bc5-work/kytyplus-build/src
            cp /usr/bin/sleep.exe bc5-work/kytyplus-build/src/kyty_emulator.exe
            cp /usr/bin/sleep.exe bin/kyty_emulator.exe; cp /usr/bin/sleep.exe bin/bc5-mount.exe
            cd bc5-work; ln -s {r}/bc5-work/resource exp0330/wd/resource
            {{ m() {{ md5sum < "$1" | cut -d' ' -f1; }}
              echo BIN_MD5=$(m kytyplus-build/src/kyty_emulator); echo ARCHIVE_MD5=$(m backend-ubuntu/libbc5_backend.a)
              echo LAUNCHER_MD5=$(m play-pkg.sh); echo RUN_ENV_MD5=$(m bc5-run.env); echo LEARNED_Z1_MD5=$(m exp0389/direct-learned-pkg.txt); echo LEARNED_Z2_MD5=$(m direct-learned-pkg.txt); }} > ../pins.sh''')
        assert rc.returncode == 0, rc.stderr

    def copy_of(self, t):
        # the fixture built once, with its one link made again for this root
        rc = self.bashc(f"""set -e
            cp -a {t.r}/. {self.r}/
            cd {self.r}; rm -f nap.fifo bc5-work/exp0330/wd/resource; mkfifo nap.fifo
            ln -s {self.r}/bc5-work/resource bc5-work/exp0330/wd/resource""", timeout=120)
        assert rc.returncode == 0, rc.stderr
        self.write_env()

    def write_env(self, drop=(), add=()):
        vals = dict(gates.COMMON)
        vals.update(gates.SYSTEM_BACKGROUND)
        vals.update(gates.NORMAL)
        lines = []
        skip = {"BC5_0399_OWNER", "BC5_0399_INPUT_CONFIG", "KYTY_BC5_INPUT_CONFIG", "KYTY_BC5_INPUT_CMD", "BC5_GC_DUMP_DIR"} | set(drop)
        fixed = {"XDG_RUNTIME_DIR": "/run/user/1000", "WAYLAND_DISPLAY": "wayland-0", "DISPLAY": ":0"}
        for k, v in vals.items():
            if k in skip:
                continue
            v = fixed.get(k, v)
            assert isinstance(v, str), k
            lines.append("  '" + f"{k}={v.replace('{HOME}', self.r)}".replace("'", "'\\''") + "'")
        for x in add:
            lines.append("  '" + x + "'")
        self.write("env-fixture.sh", "ENVV=(\n" + "\n".join(lines) + "\n)\n")

    def flag(self, *names):
        for n in names:
            (self.root / n).write_text("")

    def tune(self, text):
        self.write("tune.sh", text + "\n")

    def hook(self, name, text):
        self.write(f"hook-{name}.sh", text + "\n")

    def box(self, *args, timeout=500):
        script = posix(self.e / "box0399.sh")
        return subprocess.run([BASH, script, *args], env=self.env, text=True, capture_output=True, timeout=timeout)

    def popen(self, *args):
        return subprocess.Popen([BASH, posix(self.e / "box0399.sh"), *args], env=self.env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

    def claim(self, ok=True):
        with open(HERE / "box0399.sh", "rb") as f:
            r = subprocess.run([BASH, "-s", "--", "claim"], env=self.env, stdin=f, capture_output=True, timeout=60)
        out = (r.stdout + r.stderr).decode("utf-8", "replace")
        m = re.search(r"^TOKEN=(\d+)$", out, re.M)
        if ok:
            assert r.returncode == 0 and m, out
            self.token = m.group(1)
            self.deadline = int(self.read("bc5-work/exp0399/deadline"))
        else:
            assert r.returncode != 0 and not m, out
        return out

    def kit(self):
        for f in KIT:
            shutil.copy(HERE / f, self.e / f)
        rc = self.bashc(f"""cd {posix(self.e)} && sha256sum {' '.join(KIT)} > kit.sha256 && mkdir t && echo x > t/CMakeLists.txt &&
            tar cf testbuild.tar -C t CMakeLists.txt && rm -rf t && sha256sum testbuild.tar > tb.sha256""")
        assert rc.returncode == 0, rc.stderr

    def real_ready(self):
        self.claim()
        self.kit()
        r = self.box("setup", self.token)
        assert r.returncode == 0, r.stdout + r.stderr
        r = self.box("build", self.token)
        assert r.returncode == 0, r.stdout + r.stderr

    def ready(self):
        """The state the real claim and setup leave, from READY (made by them, once), with this case's own deadline and watchdog."""
        rc = self.bashc(f"""set -e
            rm -rf {self.r}/bc5-work {self.r}/bc5-data
            cp -a {READY.r}/bc5-work {READY.r}/bc5-data {self.r}/""", timeout=120)
        assert rc.returncode == 0, rc.stderr
        self.token = READY.token
        self.deadline = int(time.time()) + 1800
        self.write("bc5-work/exp0399/deadline", f"{self.deadline}\n")
        (self.e / "watch.id").unlink()
        self.procs.append(self.popen("watch", self.token))
        self.wait_for(lambda: (self.e / "watch.id").exists(), what="the watchdog")

    def read(self, rel):
        return (self.root / rel).read_text(encoding="utf-8", errors="replace")

    def lock(self):
        # a release moves the file aside for a moment
        for _ in range(100):
            try:
                return self.read("bc5-work/BOX-LOCK")
            except FileNotFoundError:
                time.sleep(0.1)
        return "<no lock file>"

    def queue(self):
        return self.read("bc5-work/BOX-QUEUE")

    def state(self):
        return self.read("bc5-work/exp0399/state").strip()

    def order(self):
        return self.read("order.log").split()

    def spawn(self, what="kyty_emulator", mark=""):
        p = subprocess.Popen([BASH, "-c", f'echo $$; exec env {mark} "{self.r}/bin/{what}" 200'], env=self.env, text=True, stdout=subprocess.PIPE)
        pid = p.stdout.readline().strip()
        self.procs.append(p)
        time.sleep(0.3)
        return pid

    def alive(self, pid):
        return self.bashc(f"[ -d /proc/{pid} ]").returncode == 0

    def signal(self, pid, sig):
        self.bashc(f"kill -{sig} {pid}")

    def ids(self, rel):
        return self.read(rel).split()

    def wait_for(self, fn, secs=200, what="the condition"):
        end = time.time() + secs
        while time.time() < end:
            if fn():
                return
            time.sleep(0.1)
        raise AssertionError("timed out waiting for " + what)

    def own_count(self):
        r = self.box("call", self.token, "own_pids")
        return len([l for l in r.stdout.splitlines() if re.match(r"\d+:", l)])

    def snapshots(self, tag):
        return (self.root / f"bc5-data/priv/exp0399/{tag}").exists()

    def shots(self, tag):
        return (self.e / f"r-{tag}/shots").exists()

    def clean(self):
        for p in self.procs:
            p.kill()
        script = f'''for p in /proc/[0-9]*; do n=${{p#/proc/}}; [ "$n" = "$$" ] && continue
            {{ mapfile -d "" -t c < "$p/cmdline"; }} 2> /dev/null || continue
            case "${{c[*]}}" in *"{self.r}"*) kill -9 "$n" 2> /dev/null ;; esac; done; exit 0'''
        self.bashc(script, timeout=120)


def assert_evidence_kept(b, tag):
    assert b.snapshots(tag) and b.shots(tag), "the evidence was deleted"


def assert_stopped(b, r, tag, text):
    out = r.stdout + r.stderr
    assert r.returncode == 1, (r.returncode, out[-600:])
    assert text in out, (text, out[-600:])
    assert b.state() == "stopped", b.state()
    assert_evidence_kept(b, tag)
    assert b.token in b.lock(), "our lock line went without a release"


CASES = []


def case(f):
    CASES.append(f)
    return f


# 1. the claim
@case
def claim_valid_over_stdin_exact_line_and_queue(b):
    b.claim()
    lines = b.lock().splitlines()
    assert len(lines) == 1 and b.token in lines[0] and lines[0] == b.read("bc5-work/exp0399/lock.line").strip()
    q = b.queue().splitlines()
    assert q[0] == "somebody | an old line" and b.token in q[1] and len(q) == 2
    assert b.state() == "claimed"
    assert b.order() == ["before-claim", "after-aside", "after-pins", "claimed"]    # the file is written first, the claim's own


@case
def claim_refused_by_a_foreign_line(b):
    b.write("bc5-work/BOX-LOCK", "foreign | x\n")
    b.claim(ok=False)
    assert b.lock() == "foreign | x\n" and not b.e.exists()


@case
def claim_foreign_after_the_early_look(b):
    b.hook("before-claim", 'printf "foreign\\n" > "$LOCK"')
    b.claim(ok=False)
    assert b.lock() == "foreign\n" and not b.e.exists()


@case
def claim_foreign_file_during_the_claim(b):
    b.hook("after-aside", 'printf "foreign\\n" > "$LOCK"')
    out = b.claim(ok=False)
    assert b.lock() == "foreign\n" and not b.e.exists() and "lost the claim" in out


@case
def claim_foreign_line_in_the_aside(b):
    b.hook("after-aside", 'printf "foreign\\n" >> "$a"')
    out = b.claim(ok=False)
    assert b.lock() == "foreign\n" and not b.e.exists() and "arrived during the claim" in out


@case
def claim_competing_claimants_one_wins(b):
    src = open(HERE / "box0399.sh", "rb").read()
    ps = [subprocess.Popen([BASH, "-s", "--", "claim"], env=b.env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT) for _ in range(6)]
    for p in ps:
        p.stdin.write(src)
        p.stdin.close()
    outs = [p.stdout.read().decode("utf-8", "replace") for p in ps]
    rcs = [p.wait() for p in ps]
    won = [o for o in outs if re.search(r"^TOKEN=", o, re.M)]
    assert len(won) == 1 and rcs.count(0) == 1, (rcs, outs)
    t = re.search(r"^TOKEN=(\d+)", won[0], re.M).group(1)
    assert len(b.lock().splitlines()) == 1 and t in b.lock()
    assert len([l for l in b.queue().splitlines() if "claimed" in l]) == 1


@case
def claim_lock_is_a_symlink(b):
    (b.w / "BOX-LOCK").unlink()
    b.write("elsewhere", "a target\n")
    assert b.bashc(f"ln -s {b.r}/elsewhere {b.r}/bc5-work/BOX-LOCK && [ -L {b.r}/bc5-work/BOX-LOCK ]").returncode == 0
    out = b.claim(ok=False)
    assert "not a plain file" in out and b.read("elsewhere") == "a target\n" and not b.e.exists()


@case
def claim_left_behind_is_a_stop(b):
    (b.w / "BOX-LOCK.0399-claim").mkdir()
    assert "left behind" in b.claim(ok=False)


@case
def claim_refuses_an_existing_or_linked_directory(b):
    b.e.mkdir()
    assert "exists" in b.claim(ok=False)
    b.e.rmdir()
    b.write("elsewhere/x", "x\n")
    assert b.bashc(f"ln -s {b.r}/elsewhere {b.r}/bc5-work/exp0399 && [ -L {b.r}/bc5-work/exp0399 ]").returncode == 0
    assert "exists" in b.claim(ok=False)
    assert b.lock() == ""


@case
def claim_any_failed_pin_gives_the_lock_back(b):
    def again(text):
        out = b.claim(ok=False)
        assert text in out, (text, out)
        assert b.lock() == "" and not b.e.exists(), out
    orig = b.read("bc5-work/bc5-run.env")
    b.write("bc5-work/bc5-run.env", "changed\n")
    again("bc5-run.env is not")
    b.write("bc5-work/bc5-run.env", orig)
    orig = b.read("bc5-work/play-pkg.sh")
    b.write("bc5-work/play-pkg.sh", orig + "# edited\n")
    again("the launcher is not")
    b.write("bc5-work/play-pkg.sh", orig)
    orig = b.read("bc5-work/backend-ubuntu/libbc5_backend.a")
    b.write("bc5-work/backend-ubuntu/libbc5_backend.a", "other\n")
    again("the archive is not")
    b.write("bc5-work/backend-ubuntu/libbc5_backend.a", orig)
    for flag, text in (("compress-runs", "compression"), ("disk-full", "disk"), ("no-dmesg", "dmesg")):
        b.flag(flag)
        again(text)
        (b.root / flag).unlink()
    shutil.rmtree(b.root / "bc5-data/captures/devcoredump")
    again("devcoredump")


@case
def the_live_saves_are_no_gate_and_are_never_touched(b):
    b.write("bc5-work/_SaveData/PPSA03671/SAVE1/data.bin", "the maintainer played\n")
    b.claim()
    assert not (b.e / "live.sum").exists()
    assert b.read("bc5-work/_SaveData/PPSA03671/SAVE1/data.bin") == "the maintainer played\n"


@case
def live_saves_that_change_during_a_run_stop_nothing_and_stay_as_they_are(b):
    b.hook("after-manifest", '''echo "played" > "$W/_SaveData/PPSA03671/SAVE1/data.bin"''')
    b.ready()
    r = b.box("run", b.token, "Z1")
    assert r.returncode == 0, r.stdout[-500:]
    assert b.read("bc5-work/_SaveData/PPSA03671/SAVE1/data.bin") == "played\n"


@case
def claim_a_different_binary_gives_the_lock_back(b):
    b.bashc(f"printf x >> {b.r}/bc5-work/kytyplus-build/src/kyty_emulator.exe")
    out = b.claim(ok=False)
    assert "the binary is not" in out and b.lock() == "" and not b.e.exists()


@case
def claim_queue_failure_and_queue_link(b):
    (b.w / "BOX-QUEUE").unlink()
    (b.w / "BOX-QUEUE").mkdir()
    assert "queue write failed" in b.claim(ok=False)
    assert b.lock() == ""


@case
def claim_refused_while_an_emulator_runs_and_leaves_it(b):
    pid = b.spawn()
    assert "work runs on the box" in b.claim(ok=False)
    assert b.alive(pid) and b.lock() == ""


# 2. setup
@case
def setup_derives_the_launcher_exactly_and_starts_the_watchdog(b):
    built_to_setup(b)
    d = b.read("bc5-work/exp0399/play-pkg-0399.diff")
    assert len(re.findall(r"^[-+][^-+]", d, re.M)) == 13
    L = b.read("bc5-work/exp0399/play-pkg-0399.sh")
    for x in ("LOG=~/bc5-work/exp0399/play-last.log", "MLOG=~/bc5-work/exp0399/play-pkg-mount.log", "cd ~/bc5-work/exp0399/wd",
              "KYTY_BC5_SAVEDATA_DIR=$HOME/bc5-work/exp0399/wd/_SaveData-pkg-play", "BC5_DIRECT_LEARNED=$HOME/bc5-work/exp0399/direct-learned-pkg.txt"):
        assert x in L, x
    assert b.state() == "setup"
    assert b.bashc(f"[ -L {b.r}/bc5-work/exp0399/wd/resource ]").returncode == 0
    assert (b.e / "wd-links.sha256").read_text().strip()
    p, s = b.ids("bc5-work/exp0399/watch.id")
    assert b.alive(p)
    assert b.read("bc5-work/exp0299/wd/_SaveData/PPSA03671/sentinel") == "exp 0299's save\n"


@case
def setup_refuses_a_changed_kit(b):
    b.claim()
    b.kit()
    b.write("bc5-work/exp0399/gates0399.py", "tampered\n")
    r = b.box("setup", b.token)
    assert r.returncode == 1 and "not what was sent" in r.stdout and b.state() == "claimed"


@case
def setup_refuses_a_wrong_token_a_lost_lock_and_a_missing_anchor(b):
    b.claim()
    b.kit()
    r = b.box("setup", "123")
    assert r.returncode == 1 and "is not this series" in r.stdout
    keep = b.lock()
    b.write("bc5-work/BOX-LOCK", keep + "foreign\n")
    r = b.box("setup", b.token)
    assert r.returncode == 1 and "not ours" in r.stdout and b.lock() == keep + "foreign\n"
    b.write("bc5-work/BOX-LOCK", keep)
    b.write("bc5-work/play-pkg.sh", b.read("bc5-work/play-pkg.sh").replace("cd ~/bc5-work\n", "cd ~/elsewhere\n"))
    b.bashc(f"md5sum < {b.r}/bc5-work/play-pkg.sh | cut -d' ' -f1 > {b.r}/m; sed -i \"s/^LAUNCHER_MD5=.*/LAUNCHER_MD5=$(cat {b.r}/m)/\" {b.r}/pins.sh")
    r = b.box("setup", b.token)
    assert r.returncode == 1 and "anchor" in r.stdout


@case
def setup_refuses_a_wd_link_that_leaves_the_work_directory(b):
    b.write("outside/f", "x\n")
    assert b.bashc(f"ln -s {b.r}/outside/f {b.r}/bc5-work/exp0330/wd/escape").returncode == 0
    b.claim()
    b.kit()
    r = b.box("setup", b.token)
    assert r.returncode == 1 and "points outside" in r.stdout


@case
def setup_refuses_noatime_and_a_failed_selftest(b):
    b.claim()
    b.kit()
    b.flag("noatime")
    r = b.box("setup", b.token)
    assert r.returncode == 1 and "noatime" in r.stdout


# 3. a run from end to end
@case
def success_in_the_intended_order_and_the_series_runs_on_with_no_clean_frames(b):
    b.real_ready()
    b.write("patch-value", "9.5\n")
    r = b.box("run", b.token, "Z1")
    assert r.returncode == 0, r.stdout[-800:]
    assert "qualify no" in r.stdout and b.state() == "ready"
    assert not b.snapshots("Z1") and not b.shots("Z1")
    assert (b.e / "Z1.raw.tar").exists() and (b.e / "Z1.raw.sha256").read_text().strip()
    names = b.bashc(f"tar tf {b.r}/bc5-work/exp0399/Z1.raw.tar").stdout.split()
    assert "Z1.tz.txt" in names and "Z1.manifest.txt" in names and "Z1.journal.txt" in names and "play-pkg-0399.diff" in names
    assert b.read("bc5-data/priv/exp0399/evidence/Z1-environ.bin")                # the raw dump stays private, not in the tar
    assert not any("environ" in n for n in names)
    assert "PATH=" not in b.read("bc5-work/exp0399/Z1.manifest.txt") and "MANIFEST PASS" in b.read("bc5-work/exp0399/Z1.manifest.txt")
    assert re.search(r"^learned [0-9a-f]{32} lines 1$", b.read("bc5-work/exp0399/inputs.txt"), re.M)     # the version the run saw
    assert re.search(r"^private learned [0-9a-f]{32} lines 1$", b.read("bc5-work/exp0399/Z1.saves.txt"), re.M)
    assert "learned_host 1 from /priv/learned.txt" in b.read("bc5-work/exp0399/Z1.journal.txt")
    b.write("patch-value", "31.0\n")
    assert b.read("bc5-work/exp0399/direct-learned-pkg.txt") == "0x0\n"      # Z1 on exp 0389's copy
    r = b.box("run", b.token, "Z2")
    assert r.returncode == 0 and "qualify yes" in r.stdout and b.state() == "done", r.stdout[-600:]
    assert b.read("bc5-work/exp0399/direct-learned-pkg.txt") == "0x1\n"      # Z2 on today's
    r = b.box("run", b.token, "Z2")
    assert r.returncode == 1 and "no attempts left" in r.stdout
    r = b.box("release", b.token)
    assert r.returncode == 0, r.stdout
    assert b.lock() == "" and b.state() == "released"
    assert b.queue().splitlines()[-1].startswith("water exp 0399 | released")
    assert [x for x in b.order() if x != "tick-read"] == ["before-claim", "after-aside", "after-pins", "claimed", "before-setup", "before-watch", "before-build"] + \
        ["before-reset", "before-launch", "after-manifest", "after-watch-loop", "before-gates", "before-pack", "before-clean", "run-done"] * 2 + \
        ["before-release-queue", "after-release-aside", "after-release-link"]
    b.wait_for(lambda: not b.alive(b.ids("bc5-work/exp0399/watch.id")[0]), what="the watchdog's end")
    assert b.read("bc5-work/exp0299/wd/_SaveData/PPSA03671/sentinel") == "exp 0299's save\n"
    assert b.read("bc5-work/saves-lake-1153/SAVE3/data.bin") == "lake save\n"


@case
def tags_go_in_order_and_three_attempts_are_the_limit(b):
    b.ready()
    b.flag("no-route-read")
    r = b.box("run", b.token, "Z2")
    assert r.returncode == 1 and "the next tag is Z1" in r.stdout
    for t in ("Z1", "Z2"):
        r = b.box("run", b.token, t)
        assert r.returncode == 10, (t, r.returncode, r.stdout[-500:])
        assert b.snapshots(t) and b.shots(t), t
    assert b.state() == "done"
    r = b.box("run", b.token, "Z1")
    assert r.returncode == 1


# 4. a failed route uses the attempt, is no pass, and keeps the evidence
def route_case(b, what):
    b.ready()
    r = b.box("run", b.token, "Z1")
    assert r.returncode == 10, (r.returncode, r.stdout[-700:])
    assert what in r.stdout + b.read("bc5-work/exp0399/Z1.gates.txt"), r.stdout[-500:]
    assert "RESULT Z1: route failure" in r.stdout
    assert b.state() == "ready" and (b.e / "r-Z1").exists()
    assert b.shots("Z1") and b.snapshots("Z1"), "route evidence was deleted"
    assert "GATES PASS" not in b.read("bc5-work/exp0399/Z1.gates.txt")
    return r


@case
def route_the_lake_save_was_never_read(b):
    b.flag("no-route-read")
    route_case(b, "the lake save was not read")


@case
def route_shots_missing(b):
    b.flag("no-shot")
    route_case(b, "the bench exited 3")


@case
def route_the_poller_saw_a_still_image(b):
    b.write("pl-fixture.txt", PL_FEW)
    route_case(b, "the lake was not reached")


@case
def route_too_few_finals(b):
    b.write("tz-fixture.txt", "# 5 finals; one 256-byte block per 8x8 tile: 1.000 (n 5); hole share 0.000 (n 5)\n# tiles with a hole that are mixed: x\n# mid against the previous final: x\n# changed dwords by offset: x\n")
    route_case(b, "5 finals")


@case
def route_the_emulators_time_ran_out(b):
    b.tune("EMU_S=30; LOADWAIT=100000")
    route_case(b, "time ran out")


# 5. everything else stops the series and keeps the evidence
def stop_case(b, flag, text, tag="Z1"):
    b.ready()
    if flag:
        b.flag(flag)
    r = b.box("run", b.token, tag)
    assert_stopped(b, r, tag, text)
    assert b.box("run", b.token, "Z2").returncode == 1
    return r


@case
def stop_poller_failed(b):
    stop_case(b, "poller-fails", "the poller exited 1")


@case
def stop_patch_tool_failed(b):
    stop_case(b, "patch-fails", "the analysis failed")


@case
def stop_sn_failed(b):
    stop_case(b, "sn-fails", "sn0399.py failed")


@case
def stop_tz_failed(b):
    stop_case(b, "tz-fails", "tz0399.py failed")


@case
def stop_tz_summary_incomplete(b):
    b.write("tz-fixture.txt", "# 182 finals; only one summary line\n")
    stop_case(b, None, "tz's summary")


@case
def stop_archive_failed(b):
    stop_case(b, "tar-fails", "could not be packed")


@case
def stop_archive_short_a_file(b):
    b.hook("before-pack", 'rm -f "$E/$tag.bursts.txt"')
    stop_case(b, None, "could not be packed")


@case
def stop_journal_missing(b):
    stop_case(b, "no-journal", "no readable journal")


@case
def stop_journal_stale(b):
    stop_case(b, "journal-stale", "stale journal")


@case
def stop_journal_unreadable(b):
    stop_case(b, "journal-is-dir", "no readable journal")


@case
def stop_rt_off_line(b):
    with open(b.root / "journal-fixture.log", "a", newline="\n") as f:
        f.write("ray tracing off: 13 programs dropped\n")
    stop_case(b, None, "ray tracing off lines")


@case
def stop_skip_line(b):
    with open(b.root / "journal-fixture.log", "a", newline="\n") as f:
        f.write("  skip pgm 0x11d049aa00: dispatch dropped\n")
    stop_case(b, None, "skip pgm lines")


@case
def stop_timeout_line(b):
    with open(b.root / "journal-fixture.log", "a", newline="\n") as f:
        f.write("fence TIMEOUT\n")
    stop_case(b, None, "TIMEOUT lines")


def manifest_case(b, text, drop=(), add=()):
    b.write_env(drop=drop, add=add)
    b.ready()
    r = b.box("run", b.token, "Z1")
    assert r.returncode == 1 and "effective options" in r.stdout and text in r.stdout + b.read("bc5-work/exp0399/Z1.manifest.txt"), r.stdout[-700:]
    assert b.state() == "stopped" and b.own_count() == 0
    assert "after-manifest" not in b.order() and not (b.e / "Z1.out").exists()


@case
def stop_manifest_rt_switch(b):
    manifest_case(b, "forbidden name KYTY_BC5_RT", add=["KYTY_BC5_RT=0"])


@case
def stop_manifest_rt_switch_even_at_one(b):
    manifest_case(b, "forbidden name KYTY_BC5_RT", add=["KYTY_BC5_RT=1"])


@case
def stop_manifest_skip_list(b):
    manifest_case(b, "BC5_DIRECT_SKIP_PGM is not the chain", drop=["BC5_DIRECT_SKIP_PGM"], add=["BC5_DIRECT_SKIP_PGM=909974400"])


@case
def stop_manifest_unknown_option(b):
    manifest_case(b, "an option the chain does not set: BC5_DIRECT_NEW_THING", add=["BC5_DIRECT_NEW_THING=1"])


@case
def stop_manifest_missing_guard(b):
    manifest_case(b, "missing guard BC5_DIRECT_GPU_CHECK", drop=["BC5_DIRECT_GPU_CHECK"])


@case
def stop_kernel_line_during_the_run(b):
    b.tune("LOADWAIT=100000")
    b.hook("after-manifest", '''( sleep 1; echo "amdgpu 0000:01:00.0: ring gfx timeout" >> "$ROOT/dmesg.txt" ) &''')
    b.ready()
    r = b.box("run", b.token, "Z1")
    assert_stopped(b, r, "Z1", "no analysis, nothing deleted")
    assert not (b.e / "Z1.tz.txt").exists() and b.own_count() == 0


@case
def stop_on_any_amdgpu_line_even_one_that_names_no_fault(b):
    b.tune("LOADWAIT=100000")
    b.hook("after-manifest", '''( sleep 1; echo "amdgpu 0000:01:00.0: bo 000000 va 0x10-0x20f conflict with 0x10-0x1010" >> "$ROOT/dmesg.txt" ) &''')
    b.ready()
    r = b.box("run", b.token, "Z1")
    assert_stopped(b, r, "Z1", "no analysis, nothing deleted")      # F723: this line passed exp 0385's gate
    assert b.own_count() == 0


@case
def a_line_that_is_not_amdgpu_does_not_stop_the_run(b):
    b.hook("after-manifest", '''echo "IPv6: MLD: clamping QRV from 1 to 2!" >> "$ROOT/dmesg.txt"''')
    b.ready()
    r = b.box("run", b.token, "Z1")
    assert r.returncode == 0, r.stdout[-400:]


@case
def stop_kernel_log_unreadable_during_the_run(b):
    b.tune("LOADWAIT=100000")
    b.hook("after-manifest", '''touch "$ROOT/no-dmesg"''')
    b.ready()
    r = b.box("run", b.token, "Z1")
    assert_stopped(b, r, "Z1", "kernel")


@case
def stop_devcoredump_after_the_run(b):
    b.hook("after-watch-loop", '''echo dump > "$DATA/captures/devcoredump/x.txt"''')
    stop_case(b, None, "devcoredump")


@case
def stop_source_lake_save_changed(b):
    b.hook("after-manifest", '''echo "dirty" > "$LAKE/SAVE3/data.bin"''')
    stop_case(b, None, "lake changed")
    assert b.read("bc5-work/saves-lake-1153/SAVE3/data.bin") == "dirty\n"


@case
def stop_shared_learned_file_changed(b):
    b.hook("after-manifest", '''echo "0x2" >> "$W/direct-learned-pkg.txt"''')
    stop_case(b, None, "learned changed")


@case
def stop_the_disk_fills_during_the_run(b):
    b.tune("LOADWAIT=100000")
    b.hook("after-manifest", '''( sleep 1; touch "$ROOT/disk-full" ) &''')
    b.ready()
    r = b.box("run", b.token, "Z1")
    assert_stopped(b, r, "Z1", "the disk reached 90 %")
    assert b.own_count() == 0


@case
def stop_the_emulator_died(b):
    b.tune("LOADWAIT=100000")
    b.hook("after-manifest", '''( sleep 1; kill -9 "$EP" ) &''')
    b.ready()
    r = b.box("run", b.token, "Z1")
    assert_stopped(b, r, "Z1", "ended by itself")


# 6. ownership and processes
@case
def lost_ownership_mid_run_stops_ours_and_keeps_the_foreign_line(b):
    b.tune("LOADWAIT=100000")
    b.hook("after-manifest", '''( sleep 1; echo "foreign | x" >> "$LOCK" ) &''')
    b.ready()
    r = b.box("run", b.token, "Z1")
    assert_stopped(b, r, "Z1", "0399 STOP")          # the run's own check or the watchdog's, whichever comes first
    assert b.lock().splitlines()[1] == "foreign | x" and b.own_count() == 0
    b.wait_for(lambda: not b.alive(b.ids("bc5-work/exp0399/watch.id")[0]), what="the watchdog's end")
    r = b.box("release", b.token)
    assert r.returncode == 0 and b.lock() == "foreign | x\n", (r.stdout, b.lock())


@case
def a_lock_lost_before_the_save_reset_touches_nothing(b):
    b.hook("before-reset", 'echo "foreign | x" >> "$LOCK"')
    b.ready()
    (b.e / "wd/_SaveData/PPSA03671").mkdir()
    (b.e / "wd/_SaveData/PPSA03671/old").write_text("x")
    r = b.box("run", b.token, "Z1")
    assert r.returncode == 1 and "not ours" in r.stdout, r.stdout[-400:]
    assert (b.e / "wd/_SaveData/PPSA03671/old").exists() and b.state() == "stopped" and "foreign | x" in b.lock()


@case
def a_foreign_emulator_mid_run_is_never_touched(b):
    b.tune("LOADWAIT=100000")
    b.ready()
    p = b.popen("run", b.token, "Z1")
    b.wait_for(lambda: (b.e / "Z1.out").exists(), what="the bench")
    pid = b.spawn()
    p.wait(300)
    out = p.stdout.read()
    assert p.returncode == 1 and "not ours appeared" in out, out[-500:]
    assert b.alive(pid) and b.own_count() == 0


@case
def stop_and_release_touch_no_foreign_or_other_series_process(b):
    b.ready()
    a, c = b.spawn(), b.spawn(mark="BC5_0399_OWNER=999")
    d = b.spawn(what="bc5-mount", mark="BC5_0399_OWNER=999")
    r = b.box("stop", b.token)
    assert r.returncode == 0 and b.alive(a) and b.alive(c) and b.alive(d), r.stdout
    assert b.state() == "stopped"
    r = b.box("release", b.token)
    assert r.returncode == 0 and b.alive(a) and b.alive(c) and b.alive(d) and b.lock() == ""


@case
def a_reused_pid_is_not_signalled(b):
    b.ready()
    pid = b.spawn()
    r = b.box("call", b.token, "signal_own", "KILL", pid)
    assert r.returncode == 0 and b.alive(pid)
    b.write("bc5-work/exp0399/run.id", f"{pid} 1\n")        # the run's pid, now somebody else's: another start time
    assert b.box("call", b.token, "stop_run").returncode == 0
    time.sleep(0.3)
    assert b.alive(pid)
    r = b.box("call", b.token, "reap")
    assert r.returncode == 0 and b.alive(pid)


@case
def the_real_own_set_is_by_mark_and_finds_a_marked_process(b):
    b.ready()
    mine = b.spawn(mark=f"BC5_0399_OWNER={b.token}")
    other = b.spawn()
    assert mine in b.box("call", b.token, "own_emus").stdout
    assert other in b.box("call", b.token, "foreign_emus").stdout and mine not in b.box("call", b.token, "foreign_emus").stdout
    r = b.box("call", b.token, "reap")
    assert r.returncode == 0 and not b.alive(mine) and b.alive(other)


@case
def a_mount_of_ours_is_never_killed_and_keeps_the_lock(b):
    b.tune("REAP_WAIT=3; REAP_TERM=2; REAP_KILL=2")
    b.ready()
    mount = b.spawn(what="bc5-mount", mark=f"BC5_0399_OWNER={b.token}")
    r = b.box("release", b.token)
    assert r.returncode == 1 and "do not stop" in r.stdout and b.alive(mount) and b.token in b.lock(), r.stdout


@case
def term_during_the_run_cleans_up_ours_only(b):
    b.tune("LOADWAIT=100000")
    b.ready()
    p = b.popen("run", b.token, "Z1")
    b.wait_for(lambda: (b.e / "Z1.out").exists(), what="the bench")
    pid = b.spawn()
    run = b.ids("bc5-work/exp0399/run.id")[0]
    b.signal(run, "TERM")
    p.wait(300)
    out = p.stdout.read()
    assert p.returncode == 1 and "a signal during the run" in out, out[-500:]
    assert b.state() == "stopped" and b.own_count() == 0 and b.alive(pid) and b.token in b.lock()
    assert_evidence_kept(b, "Z1")


@case
def kill_of_the_run_is_cleaned_up_by_the_watchdog(b):
    b.tune("LOADWAIT=100000")
    b.ready()
    p = b.popen("run", b.token, "Z1")
    b.wait_for(lambda: (b.e / "Z1.out").exists(), what="the bench")
    pid = b.spawn()
    run = b.ids("bc5-work/exp0399/run.id")[0]
    emu = b.ids("bc5-work/exp0399/r-Z1/emu.id")[0]
    b.signal(run, "KILL")
    b.wait_for(lambda: b.state() == "stopped", what="the watchdog's stop")
    b.wait_for(lambda: not b.alive(emu), what="the emulator's end")
    b.wait_for(lambda: b.own_count() == 0, what="nothing of ours left")
    assert b.alive(pid) and b.token in b.lock()
    assert_evidence_kept(b, "Z1")
    r = b.box("release", b.token)
    assert r.returncode == 0 and b.lock() == ""


@case
def a_run_that_ends_as_the_watchdog_looks_is_not_stopped(b):
    b.ready()
    (b.root / "bc5-work/exp0399/run.id").write_text("1 1\n", newline="\n")       # no such process: the run has just left
    b.write("bc5-work/exp0399/state", "running\n")
    b.hook("tick-read", """if [ ! -e "$ROOT/once" ]; then touch "$ROOT/once"; try_put "$ST" ready; fi""")
    r = b.box("tick", b.token)
    assert r.returncode == 0 and b.state() == "ready", (r.stdout, b.state())


@case
def a_run_that_is_gone_is_stopped_by_the_watchdog(b):
    b.ready()
    (b.root / "bc5-work/exp0399/run.id").write_text("1 1\n", newline="\n")
    b.write("bc5-work/exp0399/state", "running\n")
    b.box("tick", b.token)
    b.wait_for(lambda: (b.e / "stop.log").exists() and "the run is gone" in b.read("bc5-work/exp0399/stop.log"), what="the stop's record")
    assert b.state() == "stopped"


@case
def a_dropped_ssh_does_not_stop_the_run(b):
    b.ready()
    p = b.popen("run", b.token, "Z1")
    first = p.stdout.readline()
    assert first.startswith("== Z1"), first
    p.stdout.close()
    p.wait(400)
    b.wait_for(lambda: "RESULT Z1" in b.read("bc5-work/exp0399/Z1.run.log"), what="the run's end")
    assert b.state() == "ready"


# 7. the one deadline
@case
def no_launch_without_the_time_for_it(b):
    b.ready()
    b.write("clock", f"{b.deadline - 700}\n")
    r = b.box("run", b.token, "Z1")
    assert r.returncode == 1 and "not left before the deadline" in r.stdout
    assert not (b.e / "r-Z1").exists() and b.state() == "ready"


@case
def the_deadline_stops_the_run_then_releases_ours_only(b):
    b.tune("LOADWAIT=100000")
    b.ready()
    p = b.popen("run", b.token, "Z1")
    b.wait_for(lambda: (b.e / "Z1.out").exists(), what="the bench")
    pid = b.spawn()
    b.write("clock", f"{b.deadline - 120}\n")
    p.wait(300)
    b.wait_for(lambda: b.state() == "stopped", what="the stop")
    b.wait_for(lambda: b.own_count() == 0, what="nothing of ours left")
    assert b.token in b.lock()
    b.write("clock", f"{b.deadline}\n")
    b.wait_for(lambda: b.lock() == "" and b.state() == "released", what="the release at the deadline")
    assert "the watchdog at the deadline" in b.queue() and b.alive(pid)
    assert_evidence_kept(b, "Z1")


@case
def recovery_still_works_past_the_deadline(b):
    b.ready()
    b.box("stop", b.token)
    b.write("clock", f"{b.deadline + 500}\n")
    r = b.box("release", b.token)
    assert r.returncode == 0 or "released already" in r.stdout, r.stdout
    assert b.lock() == ""


@case
def the_kernel_stream_ends_with_the_lock_and_with_the_deadline(b):
    b.ready()
    p = b.popen("kstream", b.token)
    time.sleep(1)
    assert p.poll() is None
    b.box("release", b.token)
    p.wait(120)
    b2 = Box("kstream-deadline", FRESH)
    try:
        b2.ready()
        b2.write("clock", f"{b2.deadline + 1}\n")
        p = b2.popen("kstream", b2.token)
        p.wait(120)
    finally:
        b2.clean()


# 8. exact release
@case
def release_keeps_every_foreign_line_in_order(b):
    b.ready()
    keep = b.lock()
    b.write("bc5-work/BOX-LOCK", "before | x\n" + keep + "after | y\n")
    r = b.box("release", b.token)
    assert r.returncode == 0 and b.lock() == "before | x\nafter | y\n", (r.stdout, b.lock())


@case
def release_keeps_a_line_written_to_the_aside_or_a_new_file(b):
    b.hook("after-release-aside", 'printf "held open | x\\n" >> "$a"; printf "new file | y\\n" > "$LOCK"')
    b.ready()
    r = b.box("release", b.token)
    assert r.returncode == 0, r.stdout
    assert sorted(b.lock().splitlines()) == ["held open | x", "new file | y"], b.lock()


@case
def release_after_the_aside_is_linked_keeps_a_late_line(b):
    b.hook("after-release-link", 'printf "late | z\\n" >> "$a"')
    b.ready()
    r = b.box("release", b.token)
    assert r.returncode == 0 and b.lock() == "late | z\n", (r.stdout, b.lock())
    assert not list(b.w.glob("BOX-LOCK.0399-*"))


@case
def release_without_our_line_leaves_the_lock(b):
    b.ready()
    b.write("bc5-work/BOX-LOCK", "somebody else | x\n")
    r = b.box("release", b.token)
    assert r.returncode == 1 and "no line of ours" in r.stdout and b.lock() == "somebody else | x\n"


@case
def release_with_a_linked_lock_leaves_it(b):
    b.ready()
    line = b.lock()
    (b.w / "BOX-LOCK").unlink()
    b.write("elsewhere", line)
    assert b.bashc(f"ln -s {b.r}/elsewhere {b.r}/bc5-work/BOX-LOCK").returncode == 0
    r = b.box("release", b.token)
    assert r.returncode == 1 and b.read("elsewhere") == line


@case
def a_second_release_changes_nothing(b):
    b.ready()
    assert b.box("release", b.token).returncode == 0
    q = b.queue()
    b.write("bc5-work/BOX-LOCK", "next owner | x\n")
    r = b.box("release", b.token)
    assert r.returncode == 0 and "released already" in r.stdout and b.queue() == q and b.lock() == "next owner | x\n"


@case
def a_wrong_token_is_refused_everywhere(b):
    b.ready()
    for cmd in ("setup", "run", "stop", "release", "kstream", "status", "watch"):
        r = b.box(cmd, "42", "Z1")
        assert r.returncode == 1 and "is not this series" in r.stdout, (cmd, r.stdout)
    assert b.token in b.lock()


# 9. paths
def refused(b, path, text):
    r = b.box("call", b.token, "own_rm", path)
    assert r.returncode != 0 and text in r.stdout, (path, r.stdout)


@case
def own_rm_allows_only_its_three_trees(b):
    b.ready()
    e = posix(b.e)
    (b.e / "r-Z1/shots").mkdir(parents=True)
    (b.e / "r-Z1/shots/a.png").write_text("x")
    assert b.box("call", b.token, "own_rm", e + "/r-Z1/shots").returncode == 0 and not (b.e / "r-Z1/shots").exists()
    p = b.root / "bc5-work/exp0299/wd/_SaveData/PPSA03671"
    for bad in (posix(p), e, e + "/wd", e + "/wd/_SaveData", e + "/r-Z1", e + "/r-Z1/shots/../..", b.r + "/bc5-work/_SaveData/PPSA03671",
                b.r + "/bc5-work/saves-lake-1153", b.r + "/bc5-data/priv/exp0399/evidence", e + "/wd/resource", "/"):
        refused(b, bad, "refusing to delete")
    assert (p / "sentinel").exists()


@case
def own_rm_refuses_links_at_every_level(b):
    b.ready()
    e, r = posix(b.e), b.r
    outside = b.root / "bc5-work/exp0299/wd/_SaveData/PPSA03671/sentinel"
    # the tree itself a link
    (b.e / "r-Z1").mkdir()
    assert b.bashc(f"ln -s {r}/bc5-work/exp0299/wd/_SaveData/PPSA03671 {e}/r-Z1/shots").returncode == 0
    refused(b, e + "/r-Z1/shots", "not a plain directory")
    # a junction, the Windows kind of link
    (b.e / "r-Z2").mkdir()
    win = str(b.e / "r-Z2/shots")
    subprocess.run(["cmd", "/c", "mklink", "/J", win, str(b.root / "bc5-work/exp0299/wd/_SaveData/PPSA03671")], capture_output=True)
    refused(b, e + "/r-Z2/shots", "not a plain directory")
    # a link inside
    (b.e / "r-N3/shots").mkdir(parents=True)
    assert b.bashc(f"ln -s {r}/bc5-work/resource {e}/r-N3/shots/inner").returncode == 0
    refused(b, e + "/r-N3/shots", "holds a link")
    assert (b.e / "r-N3/shots").exists()
    # a parent that is a link, so the path leaves its root
    shutil.rmtree(b.e / "wd/_SaveData")
    assert b.bashc(f"ln -s {r}/bc5-work/exp0299/wd/_SaveData {e}/wd/_SaveData").returncode == 0
    refused(b, e + "/wd/_SaveData/PPSA03671", "leaves")
    assert outside.read_text() == "exp 0299's save\n"
    assert (b.root / "bc5-work/resource").read_text() == "a work file\n"


@case
def own_rm_refuses_a_linked_root(b):
    b.ready()
    r = b.r
    shutil.rmtree(b.root / "bc5-data/priv/exp0399")
    b.write("elsewhere/Z1/keep", "keep\n")
    assert b.bashc(f"ln -s {r}/elsewhere {r}/bc5-data/priv/exp0399").returncode == 0
    refused(b, r + "/bc5-data/priv/exp0399/Z1", "not a plain directory")
    assert b.read("elsewhere/Z1/keep") == "keep\n"


@case
def a_hostile_save_copy_link_stops_the_run_and_writes_nothing_outside(b):
    b.ready()
    e, r = posix(b.e), b.r
    assert b.bashc(f"ln -s {r}/bc5-work/exp0299/wd/_SaveData/PPSA03671 {e}/wd/_SaveData/PPSA03671").returncode == 0
    rr = b.box("run", b.token, "Z1")
    assert rr.returncode == 1 and "not a plain directory" in rr.stdout, rr.stdout[-400:]
    assert b.state() == "stopped"
    assert sorted(os.listdir(b.root / "bc5-work/exp0299/wd/_SaveData/PPSA03671")) == ["sentinel"]


@case
def the_run_never_touches_exp0299_or_the_source_or_the_live_saves(b):
    b.ready()
    def snap():
        out = {}
        for d in ("bc5-work/exp0299", "bc5-work/saves-lake-1153", "bc5-work/_SaveData"):
            for p in sorted((b.root / d).rglob("*")):
                if p.is_file():
                    out[str(p)] = (p.read_bytes(), p.stat().st_mtime_ns)
        return out
    a = snap()
    assert b.box("run", b.token, "Z1").returncode == 0
    assert a == snap()


# 10. the test build
def built_to_setup(b):
    b.claim()
    b.kit()
    r = b.box("setup", b.token)
    assert r.returncode == 0, r.stdout


@case
def build_stops_on_a_failed_backend_and_links_nothing(b):
    built_to_setup(b)
    b.flag("backend-fails")
    r = b.box("build", b.token)
    assert r.returncode == 1 and "did not build" in r.stdout and b.state() == "setup", r.stdout
    assert not (b.e / "tb/kyty_emulator.exe").exists() and not (b.e / "tb.md5").exists()


@case
def build_stops_on_failed_tests_and_links_nothing(b):
    built_to_setup(b)
    b.flag("tests-fail")
    r = b.box("build", b.token)
    assert r.returncode == 1 and "tests failed" in r.stdout and b.state() == "setup", r.stdout
    assert not (b.e / "tb/kyty_emulator.exe").exists()


@case
def build_stops_on_a_failed_link(b):
    built_to_setup(b)
    b.flag("link-fails")
    r = b.box("build", b.token)
    assert r.returncode == 1 and "private link failed" in r.stdout and b.state() == "setup", r.stdout


@case
def build_refuses_a_binary_without_the_switches(b):
    built_to_setup(b)
    b.flag("no-switches")
    r = b.box("build", b.token)
    assert r.returncode == 1 and "no lake switches" in r.stdout and not (b.e / "tb.md5").exists(), r.stdout


@case
def build_refuses_a_changed_source_tar(b):
    built_to_setup(b)
    with open(b.e / "testbuild.tar", "ab") as f:
        f.write(b"x")
    r = b.box("build", b.token)
    assert r.returncode == 1 and "not what was sent" in r.stdout


@case
def build_refuses_a_lost_lock(b):
    built_to_setup(b)
    keep = b.lock()
    b.write("bc5-work/BOX-LOCK", keep + "foreign\n")
    r = b.box("build", b.token)          # refused by the lock, or by the watchdog's stop if that came first
    assert r.returncode == 1 and "0399 STOP" in r.stdout and not (b.e / "tb").exists(), r.stdout
    assert b.lock() == keep + "foreign\n"


@case
def build_touches_nothing_shared(b):
    built_to_setup(b)
    before = (b.w / "backend-ubuntu/libbc5_backend.a").read_bytes(), (b.w / "kytyplus-build/src/kyty_emulator.exe").read_bytes()
    assert b.box("build", b.token).returncode == 0
    assert before == ((b.w / "backend-ubuntu/libbc5_backend.a").read_bytes(), (b.w / "kytyplus-build/src/kyty_emulator.exe").read_bytes())
    assert b.state() == "ready"


@case
def a_run_needs_the_build(b):
    built_to_setup(b)
    r = b.box("run", b.token, "Z1")
    assert r.returncode == 1 and "want ready" in r.stdout and not (b.e / "r-Z1").exists()


@case
def a_changed_private_binary_is_refused_before_the_attempt(b):
    b.ready()
    b.bashc(f"printf x >> {b.r}/bc5-work/exp0399/tb/kyty_emulator.exe")
    r = b.box("run", b.token, "Z1")
    assert r.returncode == 1 and "not the one built" in r.stdout and not (b.e / "r-Z1").exists(), r.stdout


@case
def an_emulator_that_is_not_the_private_binary_stops_the_run(b):
    b.hook("before-launch", 'tb=deadbeef')
    b.ready()
    r = b.box("run", b.token, "Z1")
    assert r.returncode == 1 and "not the private binary" in r.stdout and b.state() == "stopped", r.stdout[-400:]
    assert b.own_count() == 0


@case
def the_arms_go_into_the_control_file_in_order(b):
    b.ready()
    assert b.box("run", b.token, "Z1").returncode == 0
    log = [l.split(None, 2) for l in b.read("bc5-work/exp0399/r-Z1/arms.log").splitlines()]
    assert [int(l[0]) for l in log] == [0, 24, 27, 30, 33, 36, 39, 42, 45, 48, 51, 54, 57, 60, 63, 66, 69, 72, 75, 78], log
    assert log[0][2] == "census=1 zpass=1" and "nohiz=1" in log[2][2]
    assert all(len(l) == 2 for l in log[1::2]), log                    # every other arm is all off
    assert b.read("bc5-work/exp0399/r-Z1/lake.ctl").strip() == ""     # all off at the end
    assert len(b.read("bc5-work/exp0399/Z1.arms.txt").splitlines()) == 20
    assert "no zpass records" in b.read("bc5-work/exp0399/Z1.zp.txt")  # a missing catcher loses nothing else
    names = b.bashc(f"tar tf {b.r}/bc5-work/exp0399/Z1.raw.tar").stdout.split()
    assert "Z1.arms.txt" in names and "Z1.zp.txt" in names and "tb.md5" in names and "Z1.jobs.tsv.gz" in names


@case
def every_token_in_the_arms_file_is_real(b):
    # the same tokens lake_probe.cpp's parse() takes; a wrong one would read as all off on the box
    src = (HERE.parent.parent / "backend/src/lake_probe.cpp").read_text(encoding="utf-8")
    flags = set(re.findall(r'flag\("(\w+)"', src))
    good = flags | {"cache", "cache_at"}
    seen = 0
    for line in (HERE / "arms0399.txt").read_text().splitlines():
        if line.startswith("#") or "|" not in line:
            continue
        for tok in line.split("|", 1)[1].split():
            name, value = tok.split("=")
            assert name in good, tok
            seen += 1
            if name == "cache":
                assert f'tok == "cache={value}"' in src, tok
            elif name == "cache_at":
                assert f'tok == "cache_at={value}"' in src, tok
            else:
                assert value == "1", tok
    assert seen > 10


@case
def the_arm_rule_matches_the_readme(b):
    arms = "0|census=1 zpass=1\n10|\n13|cull=1\n16|\n19|pfp=1\n22|\n"
    def lines(v):
        return "".join(f"x-ts{k:02d}.png: patch {x:5.1f} %\n" for k, x in enumerate(v))
    def desc(**on):
        d = dict(cache="off", cache_at="first", cull=0, pfp=0, dbmeta=0, idle=0, nohiz=0, trackercf=0, census=0, zpass=0)
        d.update(on)
        return " ".join(f"{k}={v}" for k, v in d.items())
    def period(words=0, cull=0):
        return f"bc5-direct: experiment 0387 period: jobs 9 writers 9 in_cond 0 inserted_words {words} refused 0 cull_barriers {cull} htile_fills 0 chain_stops 0 cond_exec 0 predication 0 nested_ibs 0\n"
    def at(**on):
        return f"bc5-direct: experiment 0387 at 1.5 ms: {desc(**on)}\n"
    good = at(census=1, zpass=1) + period(words=500) + at() + period() + at(cull=1) + period(words=20, cull=4) + at() + period() + at(pfp=1) + period(words=8) + at() + period()
    clears = [30.0] * 13 + [9.0, 10.0, 11.9] + [30.0] * 9
    rows = gates.arms(lines(clears), arms, good)
    assert [r[3] for r in rows] == ["catcher", "all off", "CLEARS", "all off", "no effect", "all off"], rows
    rows = gates.arms(lines([30.0] * 13 + [9.0, 12.1, 9.0] + [30.0] * 9), arms, good)
    assert rows[2][3] == "no effect"                                  # one shot above the clean level
    rows = gates.arms(lines([30.0] * 13 + [9.0, 9.0, 9.0] + [9.5] * 9), arms, good)
    assert rows[2][3].startswith("no verdict"), rows                  # Z1's lesson: clean after it, so the holes may have just ended
    rows = gates.arms(lines([9.5] * 10 + [9.5] * 3 + [9.0] * 3 + [30.0] * 9), arms, good)
    assert rows[2][3].startswith("no verdict"), rows                  # clean before it
    idle = good.replace("cull_barriers 4", "cull_barriers 0")
    rows = gates.arms(lines(clears), arms, idle)
    assert rows[2][3].startswith("NOT EFFECTIVE"), rows               # clean shots, but the barrier never ran
    rows = gates.arms(lines([30.0] * 25), arms, "no switch lines\n")
    assert all(r[3].startswith("NOT EFFECTIVE") for r in rows if r[1]), rows


@case
def a_run_qualifies_on_its_all_off_shots_only(b):
    d = b.root / "e"
    d.mkdir()
    def w(n, t):
        (d / ("Z1" + n)).write_text(t, newline="\n")
    w(".kernel.txt", "lines 0\ndevcoredumps 0\n")
    w(".saves.txt", "lake b want b\nlearned c want c\n")
    w(".manifest.txt", "MANIFEST PASS\n")
    w(".route.txt", "bench_rc 0\npoller_rc 0\nsave_read 1\ncapped 0\nana_rc 0\n")
    w(".journal.txt", "path /p\nrtoff 0\nskip 0\ntimeouts 0\nflips 2000\n")
    w(".pl.txt", PL_OK)
    w(".bursts.txt", "frames with 3 bursts: 1\n")
    w(".tz.txt", K3_TZ.read_text())
    w(".patch.txt", "".join(f"x-ts{k:02d}.png: patch   9.0 %\n" for k in range(17)) + "".join(f"x-ts{k:02d}.png: patch  40.0 %\n" for k in range(17, 81)))
    stop, route, mean = gates.run_check(str(d), "Z1", "post")
    assert (stop, route) == ([], []) and abs(mean - 9.0) < 1e-9, (stop, route, mean)
    w(".patch.txt", "x-ts00.png: patch   9.0 %\n" * 20)
    assert "20 patch values, want 81" in " ".join(gates.run_check(str(d), "Z1", "post")[0])


@case
def the_manifest_needs_the_test_builds_own_options(b):
    h = "/home/x"
    want = gates.table(h, "77", "Z1")
    def entries(**over):
        out = [("HOME", h)]
        fixed = {"XDG_RUNTIME_DIR": "/run/user/1000", "WAYLAND_DISPLAY": "w", "DISPLAY": ":0", "BC5_GC_DUMP_DIR": h + "/bc5-data/captures/play-20261031-1500/gc",
                 "KYTY_BC5_INPUT_CONFIG": h + "/bc5-work/exp0399/input-0399.cfg", "BC5_0399_INPUT_CONFIG": h + "/bc5-work/exp0399/input-0399.cfg",
                 "KYTY_BC5_INPUT_CMD": h + "/bc5-work/exp0399/r-Z1/input.cmd", "BC5_EMU": h + "/bc5-work/exp0399/tb/kyty_emulator",
                 "BC5_DIRECT_LAKE_CTL": h + "/bc5-work/exp0399/r-Z1/lake.ctl", "BC5_DIRECT_LAKE_OUT": h + "/bc5-data/priv/exp0399/Z1/zpass.dat"}
        fixed.update(over)
        for k, v in want.items():
            if k in fixed:
                if fixed[k] is not None:
                    out.append((k, fixed[k]))
            else:
                out.append((k, v))
        return out
    assert gates.check_manifest(entries(), "77", "Z1")[1] == []
    assert "missing chain name BC5_EMU" in gates.check_manifest(entries(BC5_EMU=None), "77", "Z1")[1]
    assert "BC5_EMU is not the chain's value" in gates.check_manifest(entries(BC5_EMU=h + "/bc5-work/kytyplus-build/src/kyty_emulator"), "77", "Z1")[1]
    assert "missing chain name BC5_DIRECT_LAKE_CTL" in gates.check_manifest(entries(BC5_DIRECT_LAKE_CTL=None), "77", "Z1")[1]
    assert "BC5_DIRECT_LAKE_OUT is not the chain's value" in gates.check_manifest(entries(BC5_DIRECT_LAKE_OUT="/tmp/x"), "77", "Z1")[1]


@case
def the_lake_candidate_leaves_audio_guards_and_patch_alone(b):
    repo = HERE.parent.parent
    def git(*a):
        return subprocess.run(["git", "-C", str(repo), *a], text=True, capture_output=True)
    # patch 0001, which carries exp 0372's pad audio route, is the host's source: the private binary links its objects as they are
    assert git("diff", "--quiet", "fab8660", "HEAD", "--", "backend/kytyplus-patches").returncode == 0
    assert (repo / "backend/kytyplus-patches/0001-bc5-lle-agc.patch").read_text(encoding="utf-8", errors="replace").count("exp 0372") == 5
    names = git("diff", "--name-only", "fab8660", "HEAD", "--", "backend").stdout.split()
    assert sorted(names) == ["backend/CMakeLists.txt", "backend/include/bc5/full_state.hpp", "backend/include/bc5/lake_probe.hpp",
                             "backend/src/direct.cpp", "backend/src/full_state.cpp", "backend/src/lake_probe.cpp", "backend/tests/lake_probe_test.cpp"], names
    d = git("diff", "fab8660", "HEAD", "--", "backend/src/direct.cpp").stdout
    assert [l for l in d.splitlines() if l.startswith("-") and not l.startswith("---")] == [], "direct.cpp lost a line"
    for f in ("backend/src/lake_probe.cpp", "backend/src/direct.cpp"):
        assert "REBASE_DISPATCH" not in (repo / f).read_text(encoding="utf-8")   # F765 stays removed
    assert "BC5_DIRECT_REBASE_DISPATCH" in gates.FORBIDDEN
    for g in ("BC5_DIRECT_GPU_CHECK", "BC5_DIRECT_GPU_CHECK_PRODUCT", "BC5_DIRECT_SHADOW_LABELS", "BC5_DIRECT_HOST_INDIRECT", "BC5_DIRECT_RING_DEPS"):
        assert g in gates.GUARDS and g in gates.COMMON, g                        # the functional guards stay required


def zp_module():
    spec2 = importlib.util.spec_from_file_location("zp0399", HERE / "zp0399.py")
    zp = importlib.util.module_from_spec(spec2)
    spec2.loader.exec_module(zp)
    return zp


def zp_fixture(frames, lose=None, side_lose=None, rb_lose=None, extra=None):
    """frames: [(job, ms, holes, side)]. Each job has 30 writers of one shader on two RBs; `lose` draws 30 % less in a hole frame,
    side_lose {side: writer} 30 % less in that side's frames, rb_lose {side: RB} 40 % less on that RB in that side's frames. extra
    {job: shader}: one more draw at the job's start, which shifts every order."""
    import struct
    v = 1 << 63
    data, meta, n = bytearray(), [], 0

    def put(job, ms, ps, a, b_):
        nonlocal n
        raw = bytearray(256)
        struct.pack_into("<QQ", raw, 0, v | 100, v | (100 + a))
        struct.pack_into("<QQ", raw, 16, v | 7, v | (7 + b_))
        data.extend(raw)
        meta.append(f"{n} {job} {ps} 0x24 0 {ms:.3f}")
        n += 1

    for job, ms, holes, side in frames:
        if extra and job in extra:
            put(job, ms, extra[job], 500, 500)
        for order in range(30):
            passed = 1000 + order
            if order == lose and holes >= 0.05:
                passed = int(passed * 0.7)
            if side_lose and side_lose.get(side) == order:
                passed = int(passed * 0.7)
            one = passed
            if rb_lose and rb_lose.get(side) == 1:
                one = int(passed * 0.6)
            put(job, ms + order * 0.01, "0x11d01ff900", passed, one)
    return bytes(data), "\n".join(meta) + "\n"


def zp_text(frames, sides=True):
    tz = "".join(f"  c00.f{k} w 2560 holes {f[2]:.3f} mixed true 0.3 shifted 0.3 one-block 1.000\n" for k, f in enumerate(frames))
    if sides:
        tz += "".join(f"side c00.f{k} {f[3]} 0.900 -0.300\n" for k, f in enumerate(frames))
    snaps = "".join(f"c00 f{k} frame mono {f[1] / 1000:.6f} end 33.00\n" for k, f in enumerate(frames))
    return tz, snaps


def coin(n, seed=1):
    """n frames 33 ms apart with a fair coin's sides."""
    import random
    r = random.Random(seed)
    return [(str(k), 1000.0 + 33 * k, 0.3, r.choice("AB")) for k in range(n)]


@case
def the_catchers_reader_tells_a_skipped_writer(b):
    zp = zp_module()
    import struct
    v = 1 << 63
    raw = bytearray(256)
    struct.pack_into("<QQ", raw, 0, v | 100, v | 175)
    struct.pack_into("<QQ", raw, 16, v | 5, v | 30)
    passed, began, ended = zp.record(bytes(raw))
    assert passed[:3] == [75, 25, 0] and began == 3 and ended
    assert zp.record(bytes(256)) == ([0] * 16, 0, False)
    half = bytearray(256)
    struct.pack_into("<Q", half, 8, v | 7)
    assert zp.record(bytes(half)) == ([0] * 16, 0, True)              # a COND_EXEC skipped the begin, not the end


@case
def the_catchers_reader_names_the_writer_that_loses_cells(b):
    zp = zp_module()
    frames = [(str(k), 1000.0 + 33 * k, 0.3 if k % 2 else 0.0, "A" if k % 2 else "-") for k in range(60)]
    data, meta = zp_fixture(frames, lose=7)
    tz, snaps = zp_text(frames)
    out = zp.summarise(data, meta, tz, snaps)[0]
    assert "60 finals, 60 joined" in out and "# lag 0: side A 30, B 0, hole 30, clean 30: 0 writers follow the side, 1 lose cells" in out, out
    assert "# 1 of 30 writers lose cells" in out and "# NO TEST by side" in out, out
    first = [l for l in out.splitlines() if l.startswith("ratio")][0]
    assert " occ 7 " in first, first


@case
def the_catchers_reader_names_the_writer_of_each_side_without_clean_frames(b):
    zp = zp_module()
    frames = coin(60)
    data, meta = zp_fixture(frames, side_lose={"A": 3, "B": 9})
    out = zp.summarise(data, meta, *zp_text(frames))[0]
    assert "# lag used: 0" in out and "# 2 of 30 writers follow the side" in out and "# NO TEST by holes" in out, out
    rows = [l for l in out.splitlines() if l.startswith("side ")]
    assert " low A ps 0x11d01ff900 occ 3 " in rows[0] + rows[1] and " low B ps 0x11d01ff900 occ 9 " in rows[0] + rows[1], rows[:2]
    assert len(rows) == 30                                             # every writer's row stays, not only the widest


@case
def the_catchers_reader_finds_a_job_off_by_one_frame_and_a_wrong_lag_names_nobody(b):
    zp = zp_module()
    frames = coin(80, seed=2)
    data, meta = zp_fixture(frames, side_lose={"A": 3})
    # the finals' clock runs one frame early: each is nearest to the job before the one that drew it
    late = [(j, ms - 33, h, side) for j, ms, h, side in frames]
    out = zp.summarise(data, meta, *zp_text(late))[0]
    assert "# lag used: 1" in out, out
    assert re.search(r"# lag 1: .*: 1 writers follow the side", out) and re.search(r"# lag 0: .*: 0 writers follow the side", out), out
    assert " low A ps 0x11d01ff900 occ 3 " in out, out


@case
def a_writer_with_two_levels_is_not_named_at_a_wrong_lag(b):
    zp = zp_module()
    frames = coin(200, seed=5)
    data, meta = zp_fixture(frames, side_lose={"A": 3})
    out = zp.summarise(data, meta, *zp_text(frames))[0]      # a median flips on any majority, and named it at every lag
    assert "# lag used: 0" in out, out
    for lag in (-2, -1, 1, 2):
        assert re.search(rf"# lag {lag}: .*: 0 writers follow the side", out), out


@case
def the_catchers_reader_keeps_one_draw_in_one_row_across_layouts(b):
    zp = zp_module()
    frames = coin(60, seed=3)
    # F772: one more draw at the start of a third of the jobs moved every order by one and mixed two draws in one row
    extra = {f[0]: "0x11d0aaaa00" for f in frames[::3]}
    data, meta = zp_fixture(frames, extra=extra)
    jobs = zp.jobs_of(data, meta)[0]
    assert ("0x11d01ff900", 29) in jobs["0"]["keys"] and jobs["0"]["n"] == 31 and jobs["1"]["n"] == 30
    out = zp.summarise(data, meta, *zp_text(frames))[0]
    assert "# 0 of " in out, out
    assert not [l for l in out.splitlines() if l.startswith("swing") and float(l.split()[1]) > 0.5], out


@case
def a_writer_in_a_small_job_of_the_frame_is_read_with_the_lake_job(b):
    zp = zp_module()
    import struct
    frames = coin(60, seed=6)
    data, meta = zp_fixture(frames)
    v = 1 << 63
    data, lines = bytearray(data), meta.splitlines()
    n = len(lines)
    for job, ms, _h, side in frames:
        for k, (kid, at, ps, count) in enumerate(((job + "a", ms - 6, "0x11d0dddd00", 1), (job + "b", ms + 6, "0x11d0cccc00", 9))):
            for o in range(count):
                passed = 7000 if not (kid.endswith("b") and o == 4 and side == "A") else 1000
                raw = bytearray(256)
                struct.pack_into("<QQ", raw, 0, v | 100, v | (100 + passed))
                data.extend(raw)
                lines.append(f"{n} {kid} {ps} 0x27 0 {at + o * 0.01:.3f}")
                n += 1
    out, tsv = zp.summarise(bytes(data), "\n".join(lines) + "\n", *zp_text(frames))
    assert "60 lake jobs" in out and "180 jobs" in out, out
    row = [l for l in out.splitlines() if l.startswith("side ")][0]
    assert " low A ps 0x11d0cccc00 occ 4 job 1 " in row, row           # exp 0387's reader never read this job
    assert "1:0x11d0cccc00.4" in tsv.splitlines()[0] and "-1:0x11d0dddd00.0" in tsv.splitlines()[0]


@case
def a_writer_that_draws_both_sets_is_caught_by_the_hole_share_and_not_by_the_sides(b):
    zp = zp_module()
    import random, struct
    r = random.Random(7)
    frames = [(str(k), 1000.0 + 33 * k, round(r.uniform(0.2, 0.42), 3), r.choice("AB")) for k in range(80)]
    v = 1 << 63
    data, meta, n = bytearray(), [], 0
    for job, ms, holes, _side in frames:
        for order in range(30):
            passed = int(40000 * (1 - holes)) if order == 5 else 1000 + order
            raw = bytearray(256)
            struct.pack_into("<QQ", raw, 0, v | 100, v | (100 + passed))
            data += raw
            meta.append(f"{n} {job} 0x11d01ff900 0x24 0 {ms + order * 0.01:.3f}")
            n += 1
    out = zp.summarise(bytes(data), "\n".join(meta) + "\n", *zp_text(frames))[0]
    assert "# lag used: 0" in out and re.search(r"# lag 0: .*: 0 writers follow the side, 0 lose cells, 1 follow the hole share", out), out
    row = [l for l in out.splitlines() if l.startswith("spread")][0]
    assert " occ 5 " in row and float(row.split()[1]) < -0.9, row
    assert "# NO TEST by hole share" in zp.summarise(bytes(data), "\n".join(meta) + "\n", *zp_text(frames[:0]))[0]


@case
def the_catchers_reader_reports_an_rb_that_follows_the_side(b):
    zp = zp_module()
    frames = coin(60, seed=4)
    data, meta = zp_fixture(frames, rb_lose={"B": 1})
    out = zp.summarise(data, meta, *zp_text(frames))[0]
    # with two RBs the one that keeps its samples moves too: shares add up to 1
    assert "2 RBs with a begin written ([0, 1])" in out and "# 2 of 2 RBs follow the side" in out, out
    row = [l for l in out.splitlines() if l.startswith("rb 1 ")][0].split()
    assert float(row[5]) < float(row[3]) * 0.8, row
    same = zp.summarise(*zp_fixture(frames), *zp_text(frames))[0]
    assert "# 0 of 2 RBs follow the side" in same, same


@case
def the_catchers_reader_says_no_test_without_labels_and_keeps_the_table(b):
    zp = zp_module()
    frames = [(str(k), 1000.0 + 33 * k, 0.3, "?") for k in range(40)]
    data, meta = zp_fixture(frames, lose=7)
    out, tsv = zp.summarise(data, meta, *zp_text(frames))
    assert "# NO TEST by side" in out and "# NO TEST by holes" in out and "# NO TEST of the RBs by side" in out, out
    rows = tsv.splitlines()
    assert len(rows) == 41 and rows[0].startswith("job\tms\tfinal\tw\tholes\tside\trb0\t") and rows[0].endswith("0x11d01ff900.29"), rows[0]
    assert rows[1].split("\t")[:6] == ["0", "1000.000", "c00.f0", "2560", "0.300", "?"], rows[1]


@case
def a_final_with_no_job_near_it_stays_unknown(b):
    zp = zp_module()
    frames = coin(30)
    data, meta = zp_fixture(frames)
    tz = "  c00.f0 w 2560 holes 0.300 mixed true 0.3 shifted 0.3 one-block 1.000\n"
    snaps = "c00 f0 frame mono 900.000000 end 33.00\n"                   # 899 s away from every job
    out, tsv = zp.summarise(data, meta, tz, snaps)
    assert "; 1 finals, 0 joined" in out, out
    assert len(tsv.splitlines()) == 1


@case
def the_reader_runs_as_the_box_runs_it_and_writes_its_table(b):
    zp = zp_module()
    frames = coin(30)
    data, meta = zp_fixture(frames, side_lose={"A": 3})
    tz, snaps = zp_text(frames)
    w = b.root / "zpcli"
    w.mkdir()
    (w / "z.dat").write_bytes(data)
    (w / "z.meta").write_text(meta, newline="\n")
    (w / "t.tz").write_text(tz, newline="\n")
    (w / "t.snaps").write_text(snaps, newline="\n")
    r = subprocess.run([sys.executable, "-I", str(HERE / "zp0399.py"), str(w / "z.dat"), str(w / "z.meta"), str(w / "t.tz"), str(w / "t.snaps"), str(w / "j.tsv.gz")],
                       capture_output=True, text=True)
    assert r.returncode == 0 and "# lag used: 0" in r.stdout, r.stdout + r.stderr
    import gzip
    assert gzip.open(w / "j.tsv.gz", "rt").readline().startswith("job\tms")


@case
def the_records_stay_private_even_when_the_reader_fails(b):
    b.hook("after-manifest", 'printf x > "$C/zpass.dat"; printf y > "$C/zpass.dat.meta"')
    b.ready()
    r = b.box("run", b.token, "Z1")
    assert r.returncode == 0, r.stdout[-600:]
    assert "zp0399.py failed" in b.read("bc5-work/exp0399/Z1.zp.txt")
    assert b.read("bc5-data/priv/exp0399/evidence/Z1-zpass.dat") == "x" and b.read("bc5-data/priv/exp0399/evidence/Z1-zpass.dat.meta") == "y"
    assert not b.snapshots("Z1") and not b.shots("Z1")
    names = b.bashc(f"tar tf {b.r}/bc5-work/exp0399/Z1.raw.tar").stdout.split()
    assert "Z1.jobs.tsv.gz" in names and "Z1.zp.txt" in names and not any("zpass" in n for n in names)


@case
def the_catchers_reader_compares_hole_frames_with_k4s_clean_table(b):
    zp = zp_module()
    frames = [(str(k), 1000.0 + 33 * k, 0.3, "?") for k in range(40)]
    data, meta = zp_fixture(frames, lose=12)
    ref = "".join(f"{o:4d} ps 0x11d0bbbb00 op 0x24 in_cond 0 frames 40 skipped 0 passed 1 {1000 + o} 9\n" for o in range(30))
    out = zp.summarise(data, meta, *zp_text(frames), ref)[0]
    assert "# 1 of 21 writers hold at most 0.8 of their share in K4's clean frames" in out, out
    first = [l for l in out.splitlines() if l.startswith("across")][0]
    assert " order 12 " in first and "K4 ps 0x11d0bbbb00" in first, first
    short = "".join(f"{o:4d} ps 0x11d0bbbb00 op 0x24 in_cond 0 frames 40 skipped 0 passed 1 {1000 + o} 9\n" for o in range(25))
    assert "# NO TEST against K4's clean frames: 0 jobs of 30 writers against K4's 25" in zp.summarise(data, meta, *zp_text(frames), short)[0] \
        or "against K4's 25" in zp.summarise(data, meta, *zp_text(frames), short)[0]
    assert "# NO TEST against K4's clean frames: no K4 table" in zp.summarise(data, meta, *zp_text(frames))[0]


@case
def the_real_k4_table_gives_a_clean_reference(b):
    zp = zp_module()
    ref, count = zp.reference((HERE / "K4.zp.txt").read_text())
    assert count > 90 and len(ref) > 50 and min(ref) >= zp.REF_ORDER, (count, len(ref))


@case
def a_wrong_learned_copy_stops_the_run_before_the_launch(b):
    b.ready()
    b.write("bc5-work/exp0389/direct-learned-pkg.txt", "0x9\n")
    r = b.box("run", b.token, "Z1")
    assert r.returncode != 0 and "the learned copy for Z1 is not" in r.stdout, r.stdout[-400:]
    assert "before-launch" not in b.order()


@case
def the_pad_moves_once_inside_the_catchers_window_and_six_shots_stay_private(b):
    b.ready()
    b.write("patch-value", "31.0\n")
    assert b.box("run", b.token, "Z1").returncode == 0
    pad = b.read("bc5-work/exp0399/Z1.pad.txt").split()
    assert pad[0] == "8" and "stick r 64 128 300" in b.read("bc5-work/exp0399/r-Z1/input.cmd") and "stick r 192 128 300" in b.read("bc5-work/exp0399/r-Z1/input.cmd")
    log = [l.split(None, 2) for l in b.read("bc5-work/exp0399/r-Z1/arms.log").splitlines()]
    assert log[0][0] == "0" and log[1][0] == "24"                      # the catcher's window holds it
    kept = b.bashc(f"ls {b.r}/bc5-data/priv/exp0399/evidence/shots-Z1").stdout.split()
    assert 1 <= len(kept) <= 6 and all(k.endswith(".png") for k in kept), kept
    assert not b.shots("Z1")


@case
def the_backend_changes_only_the_lake_module_and_the_logs_it_prints_still_match(b):
    repo = HERE.parent.parent
    git = lambda *a: subprocess.run(["git", "-C", str(repo), *a], capture_output=True, text=True)
    names = set(git("diff", "--name-only", "0348cc32", "--", "backend").stdout.split())
    assert names <= {"backend/include/bc5/lake_probe.hpp", "backend/src/lake_probe.cpp", "backend/tests/lake_probe_test.cpp"}, names
    src = (repo / "backend/src/lake_probe.cpp").read_text(encoding="utf-8")
    assert "experiment 0387 period:" in src and "experiment 0387 at %.3f ms:" in src
    assert "grep -a 'experiment 0387'" in (HERE / "box0399.sh").read_text(encoding="utf-8")


# 11. the gates and the guards on their own
@case
def gates_read_the_real_k2_and_k3_summaries(b):
    k3 = K3_TZ.read_text()
    assert gates.tz_summary(k3) == 182 and gates.tz_summary(K2_TZ.read_text()) == 37
    out, n = gates.decide(k3, 9.9)
    assert out == "No verdict from this run" and n["hole_finals"] == 14 and n["pairs"] == 7
    assert gates.decide(k3, 31.0)[0] == "Inconclusive"           # 14 finals are below the 30 the plan asks for


def synth(t, z, a, b_, finals=40):
    rows = []
    for i in range(finals):
        tail = f" | changed 0.15 hole tiles {a} drawn tiles {b_} off0-7 0.3" if i % 2 else ""
        rows.append(f"  c{i:02d}.f0 w 2560 holes 0.200 mixed true {t} shifted {z} one-block 1.000{tail}")
    return "\n".join(rows) + "\n"


@case
def the_decision_rule_matches_the_readme(b):
    d = gates.decide
    assert d(synth(0.37, 0.37, 0.000, 0.16), 30)[0] == "Confirmed"
    assert d(synth(0.10, 0.10, 0.005, 0.12), 30)[0] == "Confirmed"          # big cells: few mixed tiles on both grids
    assert d(synth(0.00, 0.99, 0.000, 0.16), 30)[0] == "Overturned"         # whole tiles
    assert d(synth(0.37, 0.37, 0.060, 0.16), 30)[0] == "Overturned"         # writes reach hole tiles
    assert d(synth(0.37, 0.50, 0.000, 0.16), 30)[0] == "Inconclusive"
    assert d(synth(0.37, 0.37, 0.020, 0.16), 30)[0] == "Inconclusive"
    assert d(synth(0.37, 0.37, 0.000, 0.05), 30)[0] == "Inconclusive"
    assert d(synth(0.37, 0.37, 0.000, 0.16, finals=20), 30)[0] == "Inconclusive"
    assert d(synth(0.37, 0.37, 0.000, 0.16), 19.9)[0] == "No verdict from this run"


@case
def a_damaged_environ_dump_never_passes(b):
    for data, why in ((b"", "empty"), (b"A=1", "no final NUL"), (b"NOEQUALS\0", "malformed"), (b"\0", "malformed"), (b"1BAD=1\0", "malformed"), (b"X" * (1 << 21) + b"=1\0", "over 1 MiB")):
        try:
            gates.parse_environ(data)
        except ValueError as e:
            assert why in str(e), (data[:20], e)
        else:
            raise AssertionError("passed: " + repr(data[:20]))
    fails = gates.check_manifest([("A", "1")], "1", "Z1")[1]
    assert fails == ["no HOME in the dump"]
    fails = gates.check_manifest([("HOME", "/h"), ("HOME", "/i")], "1", "Z1")[1]
    assert "duplicate entry HOME" in fails


@case
def an_empty_count_is_never_a_zero(b):
    d = b.root / "e"
    d.mkdir()
    def w(n, t):
        (d / ("Z1" + n)).write_text(t, newline="\n")
    w(".kernel.txt", "lines 0\ndevcoredumps 0\n")
    w(".saves.txt", "lake b want b\nlearned c want c\n")
    w(".manifest.txt", "x=1\nMANIFEST PASS\n")
    w(".route.txt", "bench_rc 0\npoller_rc 0\nsave_read 1\ncapped 0\n")
    w(".pl.txt", PL_OK)
    w(".journal.txt", "path /p\nrtoff 0\nskip 0\ntimeouts 0\nflips 2000\n")
    assert gates.run_check(str(d), "Z1", "pre")[:2] == ([], [])
    w(".journal.txt", "path /p\nrtoff \nskip 0\ntimeouts 0\nflips 2000\n")
    assert "could not be read" in " ".join(gates.run_check(str(d), "Z1", "pre")[0])
    w(".journal.txt", "path /p\nrtoff 0\nskip 0\ntimeouts 0\nflips 2000\n")
    w(".saves.txt", "lake  want b\nlearned c want c\n")
    assert gates.run_check(str(d), "Z1", "pre")[0]
    (d / "Z1.saves.txt").unlink()
    assert gates.run_check(str(d), "Z1", "pre")[0]
    w(".saves.txt", "lake b want b\nlearned c want c\n")
    w(".kernel.txt", "lines 0\n")
    assert gates.run_check(str(d), "Z1", "pre")[0]


@case
def the_pollers_lock_test_is_exact(b):
    s = (HERE / "pl0399.py").read_text(encoding="utf-8")
    m = re.search(r"def ours\(\):.*?return False\n", s, re.S)
    lock, line = b.root / "lk", "water exp 0399 | token 1"
    ns = dict(open=open, OSError=OSError, lock=str(lock), line=line)
    exec(m.group(0), ns)
    assert ns["ours"]() is False
    lock.write_text(line + "\n")
    assert ns["ours"]() is True
    lock.write_text(line + "\nforeign\n")
    assert ns["ours"]() is False
    assert "emulators()" not in s and "/comm" not in s
    compile(s, "pl0399.py", "exec")


@case
def stand_ins_load_only_from_a_test_path(b):
    flag = BASE.parent / "fake-was-loaded"
    other = BASE.parent / "not-a-marked-path"
    other.mkdir(exist_ok=True)
    (other / "fake.sh").write_text(f'touch "{posix(flag)}"\n', newline="\n")
    (other / "s.sh").write_bytes((HERE / "box0399.sh").read_bytes())
    env = dict(os.environ, BC5_0399_ROOT=posix(other), BC5_0399_FAKE=posix(other / "fake.sh"))
    r = subprocess.run([BASH, posix(other / "s.sh"), "status", "1"], env=env, text=True, capture_output=True)
    assert r.returncode == 1 and "no series at" in r.stdout and not flag.exists(), r.stdout
    env = dict(os.environ, BC5_0399_ROOT=b.r, BC5_0399_FAKE=posix(other / "fake.sh"))
    r = subprocess.run([BASH, posix(other / "s.sh"), "call", "1", "reap"], env=env, text=True, capture_output=True)
    assert r.returncode == 2 and "for the tests" in r.stdout and not flag.exists(), r.stdout


def main():
    global BASE, FRESH, READY
    base = Path(sys.argv[1]).resolve()
    want = sys.argv[2].split(",") if len(sys.argv) > 2 else [""]
    BASE = base / f"0399-test-{os.getpid()}"
    BASE.mkdir(parents=True)
    h = hashlib.sha256()
    for f in ("box0399.sh", "gates0399.py", "pl0399.py", "test0399.py"):
        h.update((HERE / f).read_bytes())
    t0 = time.time()
    FRESH = Box("tpl-fresh")
    FRESH.bashc(f"rm -f {FRESH.r}/nap.fifo")   # cp -a cannot copy it; each case makes its own
    READY = Box("tpl-ready", FRESH)
    READY.real_ready()
    READY.clean()
    print(f"templates ready in {time.time() - t0:.0f} s", flush=True)
    rows = []
    for i, f in enumerate(CASES):
        if not any(w in f.__name__ for w in want):
            continue
        b, t = None, time.time()
        try:
            b = Box(f"c{i:02d}", FRESH)
            f(b)
            rows.append((f.__name__, "PASS", time.time() - t, ""))
        except Exception:
            rows.append((f.__name__, "FAIL", time.time() - t, traceback.format_exc()[-1800:]))
        finally:
            if b:
                b.clean()
        print(f"{rows[-1][1]} {rows[-1][0]} ({rows[-1][2]:.1f} s)", flush=True)
        if rows[-1][1] == "FAIL":
            print(rows[-1][3], flush=True)
    n = sum(r[1] == "PASS" for r in rows)
    print(f"{n} of {len(rows)} cases pass in {time.time() - t0:.0f} s; HOME and PATH unchanged; sources sha256 {h.hexdigest()[:16]}", flush=True)
    return 0 if n == len(rows) else 1


if __name__ == "__main__":
    sys.exit(main())
