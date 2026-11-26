#!/usr/bin/env python3
# BC5 experiment 0212: does a shader program write memory other than its render targets (GPU feedback such as a
# "requested LOD" map)? Disassembles a program from a private memory dump of the title (~/bc5-data/priv, never
# committed: the title's code) with llvm-mc -mcpu=gfx1013 (as exps 0039, 0056, 0058), writes the full listing next to
# the dump (private), and prints only counts: memory writes and atomics by mnemonic, exports by target, and the
# number of instructions up to the first s_endpgm. No instruction text leaves the box except mnemonics and counts.
# usage (in the ubuntu container): python3 -I prog0212.py <dump file> <dump base hex> <program address hex> <out dir>
#        [bytes to decode, default 0x4000]
import collections, os, re, subprocess, sys

dump, base, addr, outdir = sys.argv[1], int(sys.argv[2], 16), int(sys.argv[3], 16), sys.argv[4]
n = int(sys.argv[5], 16) if len(sys.argv) > 5 else 0x4000
with open(dump, "rb") as f:
    f.seek(addr - base)
    code = f.read(n)
if len(code) < 8:
    sys.exit("0x%x is outside %s" % (addr, dump))
text = " ".join("0x%02x" % b for b in code)
llvm = next((p for p in ("llvm-mc", "/usr/lib/llvm-21/bin/llvm-mc", "/usr/bin/llvm-mc-21") if
             subprocess.run(["sh", "-c", "command -v " + p], capture_output=True).returncode == 0), "llvm-mc")
r = subprocess.run([llvm, "--disassemble", "-triple=amdgcn-amd-amdhsa", "-mcpu=gfx1013"], input=text,
                   capture_output=True, text=True)
lines = [l.strip() for l in r.stdout.splitlines() if l.strip() and not l.strip().startswith(".")]
os.makedirs(outdir, exist_ok=True)
with open(os.path.join(outdir, "%x.s" % addr), "w") as f:
    f.write(r.stdout)
end = next((i for i, l in enumerate(lines) if l.startswith("s_endpgm")), len(lines))
body = lines[:end + 1]
writes = collections.Counter()
exports = collections.Counter()
for l in body:
    m = l.split()[0] if l.split() else ""
    if re.match(r"(image|buffer|global|flat|scratch)_(store|atomic)|(image|buffer|global|flat)_.*atomic|ds_(write|store|.*atomic)", m):
        writes[m] += 1
    if m == "exp":
        tgt = l.split()[1].rstrip(",") if len(l.split()) > 1 else "?"
        exports[re.sub(r"\d+$", "", tgt)] += 1
print("program 0x%x: %d instructions to the first s_endpgm (of %d decoded); llvm-mc errors: %d" % (
    addr, len(body), len(lines), r.stderr.count("error")))
print("  memory writes/atomics: %s" % (dict(writes) or "none"))
print("  exports: %s" % (dict(exports) or "none"))
other = [i for i, l in enumerate(lines[end + 1:]) if l.startswith("s_endpgm")]
if other:
    print("  note: %d more s_endpgm in the decoded window (not counted)" % len(other))
