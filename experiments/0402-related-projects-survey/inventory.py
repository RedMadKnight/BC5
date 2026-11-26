import hashlib, base64, re, os, sys, json
from collections import defaultdict
SALT = bytes.fromhex('518d64a635ded8c1e6b039b1c3e55230')
def nid(name):
    h = hashlib.sha1(name.encode() + SALT).digest()
    return base64.b64encode(h[:8][::-1]).decode().rstrip('=').replace('/', '-')
for n, k in {'sceKernelSyncOnAddressWait8':'dFym5b41JLU','getrusage':'hHlZQUnlxSM','fsync':'juWbTNM+8hw'}.items():
    assert nid(n) == k, (n, nid(n))
any_root, ours_root, stub_list, out = sys.argv[1:5]
# --- ours
ours = defaultdict(set); ours_all = {}
rx_ver = re.compile(r'LIB_VERSION\("([^"]+)"')
rx_func = re.compile(r'LIB_FUNC\("([^"]+)",\s*([A-Za-z0-9_:]+)')
for dp, dn, fn in os.walk(os.path.join(ours_root, 'src')):
    for f in fn:
        if not f.endswith(('.cpp', '.inc', '.h')): continue
        txt = open(os.path.join(dp, f), encoding='utf-8', errors='replace').read()
        mod = None
        for line in txt.splitlines():
            m = rx_ver.search(line)
            if m: mod = m.group(1)
            for m in rx_func.finditer(line):
                ours[mod].add(m.group(1)); ours_all[m.group(1)] = (mod, m.group(2), f)
# --- AnyPS5
rx_def = re.compile(r'APS5_VABI\s+\*?\s*([A-Za-z_][A-Za-z0-9_]*)\s*\(')
rx_exp = re.compile(r'APS5_EXPORT\("([^"]+)",\s*([A-Za-z0-9_]+)')
lib = {}
prx = os.path.join(any_root, 'core/libs/prx')
for l in sorted(os.listdir(prx)):
    d = os.path.join(prx, l)
    if not os.path.isdir(d): continue
    funcs = {}; exports = {}
    for dp, dn, fn in os.walk(d):
        if 'test' in dp.lower(): continue
        for f in fn:
            if not f.endswith('.cpp'): continue
            txt = open(os.path.join(dp, f), encoding='utf-8', errors='replace').read()
            ms = list(rx_def.finditer(txt))
            for i, m in enumerate(ms):
                end = ms[i+1].start() if i+1 < len(ms) else len(txt)
                body = txt[m.end():end]
                # definition only if '{' appears before ';'
                b = body.find('{'); s = body.find(';')
                if b < 0 or (0 <= s < b): continue
                funcs[m.group(1)] = 'NotImplemented_nid_no_patch' in body[:4000] and body[:4000].count('\n') < 15
            for m in rx_exp.finditer(txt): exports[m.group(1)] = m.group(2)
    entries = {}
    for name, pend in funcs.items():
        if name.endswith('_nid_no_patch') or name.endswith('_nid_no_patch_cut'): continue
        base = name[:-len('_nid_postfix')] if name.endswith('_nid_postfix') else name
        entries[nid(base)] = (base, pend)
    for n, fn_ in exports.items():
        entries[n] = (fn_, funcs.get(fn_, True))
    lib[l] = entries
# --- title stubs
stubs = []
for line in open(stub_list):
    if line.startswith('#') or not line.strip(): continue
    p = line.split(None, 2); stubs.append((p[0], p[1], p[2].strip() if len(p) > 2 else ''))
any_by_nid = {}
for l, e in lib.items():
    for n, (name, pend) in e.items(): any_by_nid.setdefault(n, (l, name, pend))
rows = []
for l, e in lib.items():
    tot = len(e); impl = sum(1 for v in e.values() if not v[1])
    in_ours = sum(1 for n in e if n in ours_all)
    impl_missing = sorted(v[0] for n, v in e.items() if not v[1] and n not in ours_all)
    rows.append((l, tot, impl, in_ours, len(impl_missing), impl_missing))
json.dump({'rows': rows, 'stubs': [(s, m, nm, n in ours_all, any_by_nid.get(s)) for s, m, nm in stubs for n in [s]],
           'ours_mods': {k: len(v) for k, v in ours.items()}, 'ours_total': len(ours_all)}, open(out, 'w'), indent=0)
print('ours NIDs', len(ours_all), 'modules', len(ours))
print('anyps5 libs', len(lib), 'exports', sum(r[1] for r in rows), 'implemented', sum(r[2] for r in rows))
