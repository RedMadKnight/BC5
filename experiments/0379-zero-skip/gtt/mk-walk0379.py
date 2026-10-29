# BC5 experiment 0379, moving route (G3/G4): an input script (KYTY_BC5_INPUT_CMD lines) that loads the S6N route save as
# exp 0203's o2-continue.cmd does, then walks for the rest of the run so the title streams new areas: a cycle of the
# left stick fully forward for <walk> ms, a right-stick camera turn of <turn> ms (alternating right and left every
# fourth cycle, so the path sweeps instead of circling), and a short pause. No cross or other button after the menu,
# so the character neither talks to anyone nor opens a menu. Stick values 0-255 with 128 centred, as in
# exp 0061's route.cmd and exp 0180's record-run.sh; "stick l 128 0 <ms>" holds forward for <ms>.
# usage: python mk-walk0379.py <o2-continue.cmd> <out.cmd> [secs=1200] [walk ms=15000] [turn ms=1200]
import sys
src, out = sys.argv[1], sys.argv[2]
secs = int(sys.argv[3]) if len(sys.argv) > 3 else 1200
walk = int(sys.argv[4]) if len(sys.argv) > 4 else 15000
turn = int(sys.argv[5]) if len(sys.argv) > 5 else 1200
menu = [l.rstrip("\n") for l in open(src) if l.strip()]
t = sum(int(l.split()[1]) for l in menu if l.startswith("wait "))
lines = ["# exp 0379 G3/G4 walk route (mk-walk0379.py): o2-continue.cmd's menu, then walk cycles"] + menu
lines += ["wait 30000"]  # the Continue load (S6N: ~15-20 s), then gameplay
t += 30000
i = 0
while t < secs * 1000:
    side = 255 if (i // 4) % 2 == 0 else 0
    lines += [f"stick l 128 0 {walk}", f"wait {walk}", f"stick r {side} 128 {turn}", f"wait {turn + 300}"]
    t += walk + turn + 300
    i += 1
lines += ["stick l 128 128", "stick r 128 128"]
open(out, "w", newline="\n").write("\n".join(lines) + "\n")
print(f"{out}: {len(lines)} lines, menu {len(menu)} lines, {i} walk cycles of {walk}+{turn}+300 ms, ends at {t / 1000:.0f} s")
