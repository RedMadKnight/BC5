#!/usr/bin/env bash
# BC5 exp 0417: OUR checks of three of Codex's remarks against the OLD code (the maintainer, 2026-11-13: verify,
# do not accept). Laptop only; every file comes from git history, nothing from Codex's audit directory is run.
#   V2  int0413.sh (exp 0413's first swap): its restore() when a copy fails. Claim: it releases the lock anyway.
#   V3a fault0416.py at 4a344b00 (the first version): fresh() selects lines by the time they are RECEIVED.
#   V3b the same file: scan() looks at its time limit only when a line arrives.
#   V3c fault0416.py at 5913958d (my first fix): end_child() with a child that writes nothing.
# usage: verify0417.sh <repo root>       (needs python; a temporary directory is made and removed)
set -u
ROOT=$(cd "${1:?the repo root}" && pwd)
T=$(mktemp -d "${TMPDIR:-/tmp}/verify0417-XXXXXX") || exit 1
trap 'rm -rf "$T"' EXIT
cd "$ROOT" || exit 1

echo "== V2: int0413.sh restore() with the copies missing"
a=$(grep -n '^restore() {' experiments/0413-np-session-v2-shared/int0413.sh | cut -d: -f1)
{ echo 'I=$1/nowhere; NB=$1/nb; LB=$1/lb; K=$1; UNIT=unit.cpp; PIN_NORMAL=aaa; PIN_LEAN=bbb; PIN_UNIT_OLD=ccc'
  echo 'm() { md5sum < "$1" 2> /dev/null | cut -d" " -f1; }'
  echo 'release() { echo "RELEASE CALLED"; }'
  sed -n "${a},/^}/p" experiments/0413-np-session-v2-shared/int0413.sh
  echo 'restore'; } > "$T/v2.sh"
out=$(bash "$T/v2.sh" "$T" 2>&1); rc=$?
echo "$out" | sed 's/^/   /' | cut -c1-200
case "$out" in *"RELEASE CALLED"*) echo "V2 CONFIRMED: three copies failed, no 'restored' line was printed, and the lock was released all the same (exit $rc)" ;; *) echo "V2 REFUTED: the lock was kept" ;; esac

echo "== V3a, V3b: fault0416.py at 4a344b00"
git show 4a344b00:experiments/0416-emufive-switches/fault0416.py > "$T/fault_old1.py" || exit 1
cat > "$T/v3ab.py" <<'PYEOF'
import importlib.util, sys, time, types
spec = importlib.util.spec_from_file_location("old1", sys.argv[1])
src = open(sys.argv[1]).read()
main_at = src.index('if __name__ == "__main__":')
# fresh() is defined inside the main block: cut its text out as it is
a = src.index("    def fresh():", main_at); b = src.index("\n\n", a)
fresh_src = "\n".join(l[4:] for l in src[a:b].splitlines())
ns = {}
exec(src[:main_at], ns)
new = "[  500.000000] amdgpu 0000:01:00.0: amdgpu:   in page starting at address 0x0000000000001000 from client 0x1b\n"
old = "[    5.000000] amdgpu 0000:01:00.0: amdgpu:   in page starting at address 0x0000000000002000 from client 0x1b\n"
# V3a: a fault of THIS run received 1 s after the start, and a line of the old backlog received at 3 s
clock = iter([1.0, 3.0])
env = {"p": types.SimpleNamespace(stdout=iter([new, old])), "t0": 0.0, "time": types.SimpleNamespace(time=lambda: next(clock))}
exec(fresh_src, env)
got = list(env["fresh"]())
print("   kept:", [l[1:13].strip() for l in got])
print("V3a CONFIRMED: the run's own fault (kernel time 500) received at +1 s was dropped and the old line (kernel time 5) received at +3 s was kept"
      if got == [old] else "V3a REFUTED: " + repr(got))
# V3b: a limit of 0.05 s; the only line arrives after 0.5 s of silence
def quiet():
    time.sleep(0.5); yield new
t = time.monotonic()
ns["scan"](quiet(), lambda s: None, lambda a: "x", lambda: time.monotonic() - t < 0.05)
el = time.monotonic() - t
print("   a 0.05 s limit; scan() returned after %.2f s" % el)
print("V3b CONFIRMED: the limit was looked at only when the line came" if el >= 0.45 else "V3b REFUTED")
PYEOF
python "$T/v3ab.py" "$T/fault_old1.py"

echo "== V3c: fault0416.py at 5913958d, end_child() with a silent child"
git show 5913958d:experiments/0416-emufive-switches/fault0416.py > "$T/fault_old2.py" || exit 1
cat > "$T/v3c.py" <<'PYEOF'
import importlib.util, queue, subprocess, sys, threading, time
spec = importlib.util.spec_from_file_location("old2", sys.argv[1]); f = importlib.util.module_from_spec(spec); spec.loader.exec_module(f)
p = subprocess.Popen([sys.executable, "-u", "-c", "import time; print('ready', flush=True); time.sleep(30)"], stdout=subprocess.PIPE, text=True)
q = queue.Queue(); threading.Thread(target=f.reader, args=(p.stdout, q), daemon=True).start()
q.get(timeout=5); time.sleep(0.2)                 # the reader now blocks in its read; the child writes nothing more
box = []
w = threading.Thread(target=lambda: box.append(f.end_child(p)), daemon=True); t = time.monotonic(); w.start(); w.join(timeout=4)
hung = w.is_alive()
print("   end_child() %s after %.1f s; the child is %s" % ("had NOT returned" if hung else "returned", time.monotonic() - t, "still alive" if p.poll() is None else "ended"))
print("V3c CONFIRMED: end_child() blocked and the child was never ended (killed now by this test)" if hung and p.poll() is None else "V3c REFUTED: " + repr(box))
p.kill()
PYEOF
python "$T/v3c.py" "$T/fault_old2.py"
