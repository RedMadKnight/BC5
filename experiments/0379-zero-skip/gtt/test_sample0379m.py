# exp 0379, GTT growth: runs the per-client fdinfo pipeline exactly as gtt/sample0379m.sh has it (the "fd=$(...)" line,
# extracted from the script) on stand-in fdinfo files, through bash and awk. Codex review (REVIEW-02) found that the
# first version's awk program held a literal newline and printed nothing; this test runs the script's own text.
# usage: python test_sample0379m.py   (Git Bash's bash, or BASH_EXE; Windows' own bash.exe is WSL, not used)
import os, pathlib, subprocess, tempfile
here = pathlib.Path(__file__).resolve().parent
text = (here / "sample0379m.sh").read_text(encoding="utf-8")
start = text.index("  fd=$(for f in /proc/$EP/fdinfo/*;")
end = text.index("\n", text.index(r"| tr '\n' ' ')", start))
pipeline = text[start:end].replace("/proc/$EP/fdinfo/*", "$D/*")
cases = {
    "5": "pos:\t0\ndrm-client-id:\t29\ndrm-memory-gtt:\t1024 KiB\ndrm-total-gtt:\t11610112 KiB\ndrm-shared-gtt:\t11610112 KiB\ndrm-resident-gtt:\t11610112 KiB\n",  # 7.2.9 prints both keys: total wins
    "6": "drm-client-id:\t29\ndrm-total-gtt:\t11610112 KiB\ndrm-memory-gtt:\t1024 KiB\ndrm-shared-gtt:\t11610112 KiB\ndrm-resident-gtt:\t11610112 KiB\n",  # a second fd of client 29, the other key order
    "7": "drm-client-id:\t30\ndrm-memory-gtt:\t655 MiB\n",  # the older key, no resident field
    "8": "pos:\t0\nflags:\t02\n",  # not a DRM fd
    "9": "drm-client-id:\t31\ndrm-engine-gfx:\t5 ns\n",  # a client with no GTT field
}
with tempfile.TemporaryDirectory() as d:
    for name, body in cases.items():
        pathlib.Path(d, name).write_text(body, encoding="utf-8", newline="\n")
    script = pathlib.Path(d, "run.sh")
    script.write_text(f'D="$1"\n{pipeline}\nprintf "%s\n" "$fd"\n', encoding="utf-8", newline="\n")
    bash = os.environ.get("BASH_EXE") or ("C:/Program Files/Git/bin/bash.exe" if os.path.exists("C:/Program Files/Git/bin/bash.exe") else "bash")
    p = subprocess.run([bash, str(script), d.replace("\\", "/")], capture_output=True, text=True)
out = p.stdout.strip()
print("exit", p.returncode, "out", repr(out), "err", repr(p.stderr))
assert p.returncode == 0 and p.stderr == "", p.stderr
assert out == "c29=11338/11338/11338 c30=655/?/? c31=?/?/?", out
print("pass")
