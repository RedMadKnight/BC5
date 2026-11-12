"""One commit per replay step: copy steps/NN-tag.patch over patch 0001 and commit (step 04 is empty: skipped)."""
import os
import shutil
import subprocess
import sys

R, repo = sys.argv[1], sys.argv[2]
P = os.path.join(repo, "backend", "kytyplus-patches", "0001-bc5-lle-agc.patch")
rows = [l.rstrip("\r\n").split("\t") for l in open(os.path.join(R, "steps.tsv"), encoding="utf-8")][1:]
for r in rows:
    nn, tag, series, script, units, md5s, switches, verified, note = r[:9]
    src = os.path.join(R, "steps", f"{nn}-{tag}.patch")
    shutil.copyfile(src, P)
    st = subprocess.run(["git", "-C", repo, "status", "--porcelain"], capture_output=True, text=True).stdout.strip()
    if not st:
        print(nn, tag, "no change, skipped")
        continue
    msg = (f"int(0413): step {nn} {tag} ({series}) into patch 0001\n\n"
           f"Replays {script} on the shared tree as the private build did.\n"
           f"Units: {md5s}\n"
           f"Switches: {switches} (defaults as in the private build)\n"
           f"Verified against the box's private source: {verified}. {note}\n\n"
           "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\n")
    mf = os.path.join(R, "msg.txt")
    open(mf, "w", encoding="utf-8", newline="\n").write(msg)
    subprocess.run(["git", "-C", repo, "-c", "core.autocrlf=false", "add", P], check=True)
    subprocess.run(["git", "-C", repo, "-c", "core.autocrlf=false", "commit", "-q", "-F", mf], check=True)
    print(nn, tag, "committed")
