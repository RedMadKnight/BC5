# r1-anyps5-inventory.py -- NID-level inventory of AnyPS5 core/libs/prx exports against our host.
# Successor of exp 0402 inventory.py (same NID calculator, self-checked below), with these changes:
#  - only exported definitions count: inside an extern "C" block or with an extern "C" prefix, not static
#    (0402 also counted internal APS5_VABI helpers such as SaveData's DeliverEvents);
#  - _nid_disambig<N> is stripped like core/libs/nid/include/nid/NidPatcherUtils.hpp StripNidPostfix;
#  - APS5_ASM_FUNCTION("<name>_nid_postfix") exports are counted (implemented);
#  - each export gets its file:line, body size and a kind: pending (NotImplemented stub), const (no call,
#    <= 3 statements), logic (anything else);
#  - our side counts LIB_FUNC and LIB_OBJECT with file:line and library.
# Usage: python -I r1-anyps5-inventory.py <AnyPS5 root> <our src dir> <out.json>
import hashlib, base64, re, os, sys, json
from collections import defaultdict

SALT = bytes.fromhex('518d64a635ded8c1e6b039b1c3e55230')
def nid(name):
    h = hashlib.sha1(name.encode() + SALT).digest()
    return base64.b64encode(h[:8][::-1]).decode().rstrip('=').replace('/', '-')
for n, k in {'sceKernelSyncOnAddressWait8': 'dFym5b41JLU', 'getrusage': 'hHlZQUnlxSM', 'fsync': 'juWbTNM+8hw'}.items():
    assert nid(n) == k, (n, nid(n))

any_root, ours_src, out = sys.argv[1:4]

def strip_code(txt):
    """Blank out comments and string/char literals, keeping offsets and newlines."""
    out = list(txt); i = 0; n = len(txt)
    while i < n:
        c = txt[i]
        if c == '/' and i + 1 < n and txt[i+1] == '/':
            j = txt.find('\n', i);  j = n if j < 0 else j
            for k in range(i, j): out[k] = ' '
            i = j
        elif c == '/' and i + 1 < n and txt[i+1] == '*':
            j = txt.find('*/', i + 2); j = n if j < 0 else j + 2
            for k in range(i, j):
                if txt[k] != '\n': out[k] = ' '
            i = j
        elif c == 'R' and txt.startswith('R"', i) and (i == 0 or not (txt[i-1].isalnum() or txt[i-1] == '_')):
            m = re.match(r'R"([^(\s]{0,16})\(', txt[i:])
            if not m: i += 1; continue
            term = ')' + m.group(1) + '"'
            j = txt.find(term, i + m.end()); j = n if j < 0 else j + len(term)
            for k in range(i, j):
                if txt[k] != '\n': out[k] = ' '
            i = j
        elif c == '"' or (c == "'" and not (i > 0 and txt[i-1].isalnum())):
            q = c; j = i + 1
            while j < n and txt[j] != q and txt[j] != '\n':
                j += 2 if txt[j] == '\\' else 1
            j = min(n, j + 1)
            for k in range(i + 1, j - 1): out[k] = ' '
            i = j
        else:
            i += 1
    return ''.join(out)

def match_brace(s, i, o='{', c='}'):
    d = 0
    for j in range(i, len(s)):
        if s[j] == o: d += 1
        elif s[j] == c:
            d -= 1
            if d == 0: return j
    return len(s) - 1

def base_name(name):
    if name.endswith('_nid_postfix'): name = name[:-len('_nid_postfix')]
    m = re.search(r'_nid_disambig\d+$', name)
    if m: name = name[:m.start()]
    return name

rx_def = re.compile(r'APS5_VABI\s+(?:\*\s*)*([A-Za-z_][A-Za-z0-9_]*)\s*\(')
rx_exp = re.compile(r'APS5_EXPORT\(\s*"([^"]+)"\s*,\s*([A-Za-z0-9_]+)')
rx_asm = re.compile(r'APS5_ASM_FUNCTION\(\s*"([^"]+)"')
rx_data = re.compile(r'(?:alignas\([^)]*\)\s*)?\bextern\s+(?:const\s+)?[A-Za-z_][\w:<>]*(?:\s*\*)*\s+(?:const\s+)?([A-Za-z_]\w*)\s*(?:\[[^\]]*\])*\s*=')
rx_call = re.compile(r'\b([A-Za-z_][A-Za-z0-9_:]*)\s*(?:<[^;(){}]*>)?\s*\(')
NOT_CALLS = {'return', 'if', 'while', 'for', 'switch', 'sizeof', 'static_cast', 'reinterpret_cast',
             'const_cast', 'alignof', 'decltype', 'catch', 'int', 'uint32_t', 'int32_t', 'uint64_t',
             'int64_t', 'std::uint32_t', 'std::int32_t', 'std::uint64_t', 'std::int64_t', 'void', 'bool'}

def scan_file(path, rel):
    raw = open(path, encoding='utf-8', errors='replace').read()
    s = strip_code(raw)
    line_of = lambda off: raw.count('\n', 0, off) + 1
    # extern "C" blocks (detect on raw, the literal "C" is blanked in s)
    blocks = []
    for m in re.finditer(r'extern\s*"C"\s*\{', raw):
        b = m.end() - 1
        blocks.append((b, match_brace(s, b)))
    defs = []
    for m in rx_def.finditer(s):
        name = m.group(1)
        if name in ('operator',): continue
        par = s.find('(', m.end() - 1)
        pe = match_brace(s, par, '(', ')')
        # next '{' or ';' after the parameter list
        k = pe + 1
        while k < len(s) and s[k] not in '{;': k += 1
        if k >= len(s) or s[k] == ';': continue  # declaration
        if '=' in s[pe+1:k]: continue  # e.g. a function-pointer variable initialiser
        be = match_brace(s, k)
        ls = s.rfind('\n', 0, m.start()) + 1
        prefix = s[max(0, ls - 200):m.start()]
        linepre = s[ls:m.start()]
        is_static = re.search(r'\bstatic\b', linepre) is not None
        in_block = any(b0 < m.start() < b1 for b0, b1 in blocks)
        has_prefix = re.search(r'extern\s*"C"\s*[^;{}]*$', raw[max(0, ls - 120):m.start()]) is not None
        # crude namespace/class check: is the definition nested inside braces that are not an extern "C" block?
        body = s[k+1:be]
        lines = [l for l in body.split('\n') if l.strip()]
        stmts = body.count(';')
        calls = [c for c in rx_call.findall(body) if c not in NOT_CALLS]
        pending = 'NotImplemented_nid_no_patch' in body and len(lines) <= 6 and \
            len([c for c in calls if c != 'NotImplemented_nid_no_patch']) == 0
        if pending: kind = 'pending'
        elif not calls and stmts <= 3: kind = 'const'
        else: kind = 'logic'
        defs.append(dict(name=name, file=rel, line=line_of(m.start()), body_lines=line_of(be) - line_of(k) + 1,
                         kind=kind, exported=(in_block or has_prefix) and not is_static,
                         ret=re.sub(r'\s+', ' ', linepre.strip())[:60]))
    # literals are blanked in s, so match on raw and keep only matches that are code in s
    exps = [(m.group(1), m.group(2), line_of(m.start())) for m in rx_exp.finditer(raw) if s[m.start()] == 'A']
    asms = [(m.group(1), line_of(m.start())) for m in rx_asm.finditer(raw) if s[m.start()] == 'A']
    # data exports: extern variable definitions inside extern "C" blocks
    datas = []
    for m in rx_data.finditer(s):
        if any(b0 < m.start() < b1 for b0, b1 in blocks):
            datas.append((m.group(1), line_of(m.start())))
    return defs, exps, asms, datas

def header_c_decls(root):
    """Names declared with APS5_VABI in headers inside an extern "C" block or with an extern "C" prefix."""
    names = set()
    for dp, dn, fn in os.walk(root):
        for f in fn:
            if not f.endswith(('.hpp', '.h', '.inc')): continue
            raw = open(os.path.join(dp, f), encoding='utf-8', errors='replace').read()
            s = strip_code(raw)
            blocks = [(m.end() - 1, match_brace(s, m.end() - 1)) for m in re.finditer(r'extern\s*"C"\s*\{', raw)]
            for m in rx_def.finditer(s):
                ls = s.rfind('\n', 0, m.start()) + 1
                if any(b0 < m.start() < b1 for b0, b1 in blocks) or \
                        re.search(r'extern\s*"C"\s*[^;{}]*$', raw[max(0, ls - 120):m.start()]):
                    names.add(m.group(1))
    return names

prx = os.path.join(any_root, 'core', 'libs', 'prx')
c_decl = header_c_decls(prx)
lib = {}
dropped = defaultdict(list)
for l in sorted(os.listdir(prx)):
    d = os.path.join(prx, l)
    if not os.path.isdir(d): continue
    funcs = {}; alldefs = {}; exports = []; asms = []; datas = []
    for dp, dn, fn in os.walk(d):
        parts = os.path.relpath(dp, d).replace('\\', '/').split('/')
        if any(p.lower() in ('test', 'tests') for p in parts): continue
        for f in fn:
            if not f.endswith('.cpp'): continue
            p = os.path.join(dp, f)
            rel = os.path.relpath(p, any_root).replace('\\', '/')
            defs, exps, a, dt = scan_file(p, rel)
            datas += [(x[0], rel, x[1]) for x in dt]
            for df in defs:
                alldefs.setdefault(df['name'], df)
                if not df['exported'] and not (df['name'] in c_decl and not df['ret'].startswith('static')):
                    dropped[l].append(df); continue
                funcs.setdefault(df['name'], df)
            exports += [(e[0], e[1], rel, e[2]) for e in exps]
            asms += [(x[0], rel, x[1]) for x in a]
    entries = {}
    for name, df in funcs.items():
        if name.endswith('_nid_no_patch') or name.endswith('_nid_no_patch_cut') or name.startswith('SDL_'): continue
        b = base_name(name)
        entries[nid(b)] = dict(df, name=b)
    for n_, fname, rel, line in exports:
        df = funcs.get(fname) or alldefs.get(fname)
        e = dict(df) if df else dict(name=fname, file=rel, line=line, body_lines=0, kind='logic', ret='')
        e['export_line'] = '%s:%d' % (rel, line)
        entries[n_] = e
    for name, rel, line in asms:
        if name.endswith('_nid_no_patch'): continue
        b = base_name(name)
        entries.setdefault(nid(b), dict(name=b, file=rel, line=line, body_lines=0, kind='logic', ret='asm'))
    for name, rel, line in datas:
        if name.endswith('_nid_no_patch') or name.endswith('_nid_no_patch_cut'): continue
        b = base_name(name)
        entries.setdefault(nid(b), dict(name=b, file=rel, line=line, body_lines=1, kind='data', ret='data'))
    lib[l] = entries

# ---- ours
ours = {}
rx_ver = re.compile(r'LIB_VERSION\("([^"]+)",\s*\d+,\s*"([^"]+)"')
rx_func = re.compile(r'LIB_(FUNC|OBJECT)\(\s*"([^"]+)",\s*&?\s*([A-Za-z0-9_:]+)')
our_libs = set(); our_mods = set()
for dp, dn, fn in os.walk(ours_src):
    for f in fn:
        if not f.endswith(('.cpp', '.inc', '.h', '.hpp')): continue
        p = os.path.join(dp, f)
        rel = os.path.relpath(p, os.path.dirname(ours_src)).replace('\\', '/')
        txt = open(p, encoding='utf-8', errors='replace').read()
        marks = sorted([(m.start(), 'v', m) for m in rx_ver.finditer(txt)] + [(m.start(), 'f', m) for m in rx_func.finditer(txt)],
                       key=lambda x: x[0])
        libname = modname = None
        for off, t, m in marks:  # LIB_FUNC may span lines (libNet.cpp)
            if t == 'v':
                libname, modname = m.group(1), m.group(2); our_libs.add(libname); our_mods.add(modname)
            else:
                ours.setdefault(m.group(2), []).append(dict(lib=libname, mod=modname, sym=m.group(3),
                                                            at='%s:%d' % (rel, txt.count('\n', 0, off) + 1)))

json.dump(dict(lib=lib, ours=ours, our_libs=sorted(our_libs), our_mods=sorted(our_mods),
               dropped={k: [(d['name'], d['file'], d['line']) for d in v] for k, v in dropped.items()}),
          open(out, 'w'), indent=0)
print('ours NIDs', len(ours), 'libs', len(our_libs), 'mods', len(our_mods))
print('anyps5 libs', len(lib), 'exports', sum(len(e) for e in lib.values()),
      'implemented', sum(1 for e in lib.values() for v in e.values() if v['kind'] != 'pending'),
      'data', sum(1 for e in lib.values() for v in e.values() if v['kind'] == 'data'),
      'dropped non-exported defs', sum(len(v) for v in dropped.values()))
