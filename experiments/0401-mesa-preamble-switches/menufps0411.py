# BC5 exp 0401 e11 menu series (2026-11-10): frame rate inside the scripted in-game menu windows against the walk, per arm.
# Input: the arm's "fps counter" lines reduced to "t flips secs longest_gap_ms" (raw/night/<tag>-fps.txt, from the box's
# ~/bc5-work/exp0401t/raw/<tag>-play.log), and G in runner seconds. The windows are run0401t.sh wk()'s menu cycles (every
# BC5_0401T_MENU=4 walk cycles of 16.5 s, 15 s each); the emulator's t starts a few seconds after the runner's, so each
# window is trimmed by 1 s at the start and 2 s at the end. usage: python menufps0411.py <fps file> <G>
import sys

# usage: menu_fps.py <fps file: "t flips secs longest_gap_ms" per line> <G seconds (runner time)> <offset: emulator t minus runner t>
rows = []
for l in open(sys.argv[1]):
    p = l.split()
    if len(p) == 4:
        try:
            rows.append((float(p[0]), int(p[1]), float(p[2]), float(p[3])))
        except ValueError:
            pass
G = float(sys.argv[2])
wins = []
t = c = 0
while t + 16500 <= 600000:
    c += 1
    t += 16500
    if c % 4 == 0 and t + 15000 <= 600000:
        wins.append((G + t / 1000, G + (t + 15000) / 1000))
        t += 15000


def agg(lo, hi):
    s = [r for r in rows if lo <= r[0] < hi]
    secs = sum(r[2] for r in s)
    return (sum(r[1] for r in s) / secs if secs else 0.0, max([r[3] for r in s] or [0.0]), sum(1 for r in s if r[3] > 100))


inm = [agg(lo + 1, hi - 2) for lo, hi in wins]
walk = [r for r in rows if r[0] >= G and r[0] < G + 600 and not any(lo <= r[0] < hi for lo, hi in wins)]
wsecs = sum(r[2] for r in walk)
print(f"menu windows: {len(wins)}; in menu {sum(a[0] for a in inm)/len(inm):.1f} fps, longest gap {max(a[1] for a in inm):.0f} ms, "
      f"{sum(a[2] for a in inm)} s with a gap over 100 ms; walking {sum(r[1] for r in walk)/wsecs:.1f} fps, "
      f"longest gap {max(r[3] for r in walk):.0f} ms, {sum(1 for r in walk if r[3] > 100)} s with a gap over 100 ms")
top = sorted(rows, key=lambda r: -r[3])[:3]
for r in top:
    where = "menu" if any(lo <= r[0] < hi for lo, hi in wins) else ("before G" if r[0] < G else "walk")
    print(f"  gap {r[3]:.0f} ms at t {r[0]:.1f} s (G{r[0]-G:+.1f}, {where})")
