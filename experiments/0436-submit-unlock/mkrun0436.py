# BC5 exp 0436: the private copy of exp 0430's run0430f.sh (9d53dccc) for this experiment's route chain, with ONE change:
# the "any GPU reset since boot" gate becomes a baseline gate (the top session's ruling of 2026-11-20 ~01:00: the box
# could not be rebooted, sudo needs a password and polkit refused systemctl reboot; the 51 old lines are exp 0434's ASTRO
# faults of 11-19 14:06-14:14, all recovered). The run starts only if the count of matching lines equals
# R0436_BASE (set by chain0436.sh from its own count at the chain's start). The original is not edited.
#   python -I mkrun0436.py run0430f-9d53dccc.sh run0430f-0436.sh
import sys

src, dst = sys.argv[1:3]
s = open(src, encoding="utf-8", newline="").read()
old = """if sudo -n dmesg 2> /dev/null | grep -E 'amdgpu [0-9a-f]{4}:[0-9a-f]{2}:' | grep -qiE 'ring .* timeout|reset (succeeded|failed)|GPU reset|device wedged'; then
  echo "a GPU reset or ring timeout since this boot (sudo dmesg): reboot the box first: not started"; exit 1
fi"""
new = """# exp 0436 (the top session's ruling, 2026-11-20): a baseline instead of "none since boot": the count of these lines must
# still be the chain's starting count R0436_BASE; one more means a new timeout or reset, and nothing starts.
R0436_NOW=$(sudo -n dmesg 2> /dev/null | grep -E 'amdgpu [0-9a-f]{4}:[0-9a-f]{2}:' | grep -ciE 'ring .* timeout|reset (succeeded|failed)|GPU reset|device wedged')
if [ "$R0436_NOW" != "${R0436_BASE:?the chain baseline count}" ]; then
  echo "GPU reset/timeout lines since boot: $R0436_NOW, the chain's baseline $R0436_BASE: a new one: not started"; exit 1
fi"""
assert s.count(old) == 1
s = s.replace(old, new)
open(dst, "w", encoding="utf-8", newline="").write(s)
print("mkrun0436: ok")
