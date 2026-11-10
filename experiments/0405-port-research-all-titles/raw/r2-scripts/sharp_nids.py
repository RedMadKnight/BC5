# Extract sharpemu [SysAbiExport(...)] NIDs: nid, export name, library, file, line, method.
# Each attribute is paired with the next method declaration after it (stacked attributes share one).
import os, re, sys
root, out = sys.argv[1], sys.argv[2]
re_attr = re.compile(r'\[SysAbiExport\((.*?)\)\]', re.S)
re_meth = re.compile(r'(?:public|internal|private)\s+(?:static\s+)?(?:unsafe\s+)?[\w<>\[\]?.]+\s+(\w+)\s*\(')
re_kv = re.compile(r'(\w+)\s*=\s*"([^"]*)"')
rows = []
for dp, dn, fn in os.walk(root):
    for f in fn:
        if not f.endswith('.cs'):
            continue
        p = os.path.join(dp, f)
        txt = open(p, encoding='utf-8', errors='replace').read()
        rel = os.path.relpath(p, root).replace(os.sep, '/')
        for m in re_attr.finditer(txt):
            kv = dict(re_kv.findall(m.group(1)))
            line = txt.count('\n', 0, m.start()) + 1
            mm = re_meth.search(txt, m.end())
            meth = mm.group(1) if mm else '?'
            rows.append((kv.get('Nid', ''), kv.get('ExportName', ''), kv.get('LibraryName', ''), rel, str(line), meth))
with open(out, 'w', encoding='utf-8') as fo:
    for r in rows:
        fo.write('\t'.join(r) + '\n')
print(len(rows), len(set(r[0] for r in rows)))
