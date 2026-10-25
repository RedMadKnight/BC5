#!/usr/bin/env python3
# BC5 experiment 0301: the launcher side of "MangoHud in every build".
#   1. The proposed change to play-pkg.sh and play-astro.sh: the BC5_MANGOHUD=1 block (MANGOHUD=1,
#      MANGOHUD_CONFIGFILE=~/bc5-work/mangohud-bc5.conf, KYTY_BC5_OSD_FPS=1; 2026-10-21) goes; the emulator now loads
#      MangoHud itself, hidden, and the Emulation menu's MangoHud switch shows it (patch_0301.diff).
#   2. The private test launcher play-pkg-0301.sh: the changed play-pkg.sh in exp 0299's pattern — its own log, its own
#      working directory (with its own _SaveData and save-data mount slots), its own input configuration (the menu's
#      switches are saved into it) and its own input recording, so the maintainer's saves, input.cfg and
#      route-record.txt are never read or written.
# Every anchor must occur exactly once; the script refuses otherwise. The inputs are only read.
# usage: launchers0301.py <dir with play-pkg.sh and play-astro.sh> <out dir>
#   writes <out>/play-pkg.sh, <out>/play-astro.sh (the proposal), <out>/play-pkg-0301.sh (the test launcher)
#   and <out>/launchers_0301.diff (the proposal against the inputs)
import difflib, os, re, sys

src, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)

BLOCK = re.compile(
    r"# 2026-10-21 \(the maintainer asked, for recordings\): BC5_MANGOHUD=1 shows MangoHud's overlay \(hardware:\n"
    r"(?:#.*\n){3}"
    r'if \[ "\$\{BC5_MANGOHUD:-0\}" = 1 \]; then\n'
    r"  export MANGOHUD=1 MANGOHUD_CONFIGFILE=\$\{MANGOHUD_CONFIGFILE:-\$HOME/bc5-work/mangohud-bc5.conf\} KYTY_BC5_OSD_FPS=1\n"
    r"fi\n")
NEW = ("# Experiment 0301 (the maintainer asked, 2026-10-25): MangoHud is part of the emulator: it loads hidden and\n"
       "# Emulation > MangoHud shows its hardware figures and the title's frame rate (saved per title in the input\n"
       "# configuration). KYTY_BC5_MANGOHUD=0 keeps MangoHud out, =1 shows it from the start; KYTY_BC5_OSD_FPS=1 the\n"
       "# frame rate alone. The former BC5_MANGOHUD=1 switch and its shortcut are gone.\n")


def once(text, old, new, what):
    n = text.count(old)
    if n != 1:
        sys.exit(f"{what}: the anchor occurs {n} times, not once")
    return text.replace(old, new)


diffs = []
proposal = {}
for name in ("play-pkg.sh", "play-astro.sh"):
    with open(os.path.join(src, name), newline="") as f:
        text = f.read()
    found = BLOCK.findall(text)
    if len(found) != 1:
        sys.exit(f"{name}: the BC5_MANGOHUD block occurs {len(found)} times, not once")
    new = BLOCK.sub(lambda m: NEW, text)
    proposal[name] = new
    with open(os.path.join(out, name), "w", newline="") as f:
        f.write(new)
    diffs += difflib.unified_diff(text.splitlines(True), new.splitlines(True), "a/" + name, "b/" + name)
with open(os.path.join(out, "launchers_0301.diff"), "w", newline="") as f:
    f.writelines(diffs)

t = proposal["play-pkg.sh"]
t = once(t, "LOG=~/bc5-work/play-pkg-last.log\n",
         "LOG=~/bc5-work/exp0301/play-last.log  # exp 0301: private\n", "LOG")
t = once(t, 'done < "$ENVF"\n',
         'done < "$ENVF"\n'
         '[ -n "${BC5_0301_INPUT_CONFIG:-}" ] && export KYTY_BC5_INPUT_CONFIG=$BC5_0301_INPUT_CONFIG  # exp 0301: a private copy (the menu saves into it)\n'
         'export KYTY_BC5_INPUT_RECORD=$HOME/bc5-work/exp0301/wd/route-record.txt  # exp 0301: private\n', "ENVF")
t = once(t, "export KYTY_BC5_SAVEDATA_DIR=$HOME/bc5-work/_SaveData-pkg-play\n",
         "export KYTY_BC5_SAVEDATA_DIR=$HOME/bc5-work/exp0301/wd/_SaveData-pkg-play  # exp 0301: private\n", "SAVEDATA")
t = once(t, "\ncd ~/bc5-work\n",
         "\ncd ~/bc5-work/exp0301/wd  # exp 0301: the private working directory (its own _SaveData)\n", "cd")
t = t.replace("#!/usr/bin/env bash\n",
              "#!/usr/bin/env bash\n# BC5 experiment 0301: play-pkg.sh with the proposed change, in a private working directory (launchers0301.py).\n", 1)
with open(os.path.join(out, "play-pkg-0301.sh"), "w", newline="") as f:
    f.write(t)
os.chmod(os.path.join(out, "play-pkg-0301.sh"), 0o755)
print("ok:", ", ".join(sorted(proposal)), "and play-pkg-0301.sh written;", sum(1 for l in diffs if l.startswith(("+", "-")) and not l.startswith(("+++", "---"))), "diff lines")
