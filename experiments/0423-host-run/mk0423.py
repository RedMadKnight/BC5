#!/usr/bin/env python3
r"""BC5 experiment 0423: run0423p.sh from exp0413's run0413p.sh (md5 fc4fe47c, read from the box, not edited there).
    mk0423.py <run0413p.sh> <run0423p.sh>
Edits, each must match exactly once:
  1. P_HOST=1: the launch line runs the same `/usr/bin/bash -c 'ulimit -l unlimited; exec /usr/bin/env "$@"'` with the
     same environment words and the same derived launcher directly on the Bazzite host, without `distrobox enter
     ubuntu --`. P_HOST unset or 0: the line as it was (the container).
  2. Once, at 30 s or later, the emulator's /proc/<pid>/maps is read for the Vulkan driver and MangoHud mappings
     (path, device:inode) and written to the run's start file: which Mesa the run used, read from the process itself.
  3. The run's start file names the place (host or container).
Everything else (the private working directory and its reset from exp 0412's named snapshot, the route, the walk, the
kernel-line stop, the summary) is run0413p.sh's own."""
import hashlib, sys

src, dst = sys.argv[1], sys.argv[2]
b = open(src, "rb").read()
assert hashlib.md5(b).hexdigest() == "fc4fe47c09671667c0037535c1e84bea", "run0413p.sh is not the one read on 2026-11-15"
s = b.decode("utf-8")
assert "\r" not in s


def sub(old, new):
    global s
    assert s.count(old) == 1, "%d matches of %r" % (s.count(old), old[:80])
    s = s.replace(old, new)


L = """setsid nohup bash -c 'distrobox enter ubuntu -- /usr/bin/bash -c '\\''ulimit -l unlimited 2> /dev/null; exec /usr/bin/env "$@"'\\'' guard0412n "$@"; echo "launcher exit $?"' _ "${ENVS[@]}" "$LAUNCH" < /dev/null > "$R/$TAG-launch.out" 2>&1 &\n"""
H = """if [ "${P_HOST:-0}" = 1 ]; then  # exp 0423: the same command on the Bazzite host, no distrobox
setsid nohup bash -c '/usr/bin/bash -c '\\''ulimit -l unlimited 2> /dev/null; exec /usr/bin/env "$@"'\\'' guard0412n "$@"; echo "launcher exit $?"' _ "${ENVS[@]}" "$LAUNCH" < /dev/null > "$R/$TAG-launch.out" 2>&1 &
else
""" + L + "fi\n"
sub(L, H)

sub("""  echo "boot $(cut -c1-8 /proc/sys/kernel/random/boot_id), up since $(uptime -s)";""",
    """  echo "exp 0423 place: $([ "${P_HOST:-0}" = 1 ] && echo "HOST (no distrobox)" || echo "container (distrobox enter ubuntu)")"
  echo "boot $(cut -c1-8 /proc/sys/kernel/random/boot_id), up since $(uptime -s)";""")

sub("""  NOW=$(($(date +%s) - T0))
  [ -d "/proc/$EP" ] || { ENDED="ended by itself at $NOW s"; break; }
""", """  NOW=$(($(date +%s) - T0))
  [ -d "/proc/$EP" ] || { ENDED="ended by itself at $NOW s"; break; }
  if [ -z "${MAPS0423:-}" ] && [ "$NOW" -ge 30 ]; then  # exp 0423: which Vulkan driver and MangoHud the process mapped
    MAPS0423=1
    echo "maps at $NOW s: $(awk '/libvulkan_radeon|[Mm]ango[Hh]ud/ {print $4, $5, $6}' "/proc/$EP/maps" 2> /dev/null | sort -u | tr '\\n' ';')" >> "$R/$TAG-start.txt"
  fi
""")

open(dst, "w", encoding="utf-8", newline="\n").write(s)
print("run0423p.sh written")
