# Extract LIB_FUNC/LIB_OBJECT NIDs with library context from a Kyty-family src tree.
import os, re, sys
root = sys.argv[1]
out = sys.argv[2]
re_ver = re.compile(r'LIB_(?:VERSION|NAME)\(\s*"([^"]+)"')
re_func = re.compile(r'LIB_(FUNC|OBJECT)\(\s*"([^"]+)"\s*,\s*([^)]*)\)')
rows = []
for dp, dn, fn in os.walk(root):
    for f in fn:
        if not f.endswith(('.cpp', '.h', '.inc', '.hpp')):
            continue
        p = os.path.join(dp, f)
        try:
            txt = open(p, encoding='utf-8', errors='replace').read()
        except Exception:
            continue
        lib = None
        rel = os.path.relpath(p, root).replace(os.sep, '/')
        for i, line in enumerate(txt.split('\n'), 1):
            m = re_ver.search(line)
            if m:
                lib = m.group(1)
            for m in re_func.finditer(line):
                rows.append((m.group(2), lib, rel, i, m.group(3).strip()))
with open(out, 'w', encoding='utf-8') as fo:
    for r in rows:
        fo.write('\t'.join(str(x) for x in r) + '\n')
print(len(rows), len(set(r[0] for r in rows)))
