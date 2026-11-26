#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0
"""BC5 experiment 0438 (tag bake438b): the shared bake of A1 + A1b + A1P (memory.cpp), A2 (the backend's MappingIndex
and the host's reading of it) and the acb gate (BC5_0438_INFLIGHT_NG, BC5_0438_OPEN_NG) WITHOUT Q438 (no SUBMITQ, no
labelmap, no BC5_0438_R438_LWM). Every switch is kept and is ON unless "0" (as r438 was baked).

Usage: python -I mkbake438b.py MEMORY_CPP PATCH_0001 OUT_DIR
  MEMORY_CPP  the shared tree's src/kernel/memory.cpp (aa7d7f5b; the private copy is
              $HOME/Documents/bc5-private-0438/kyty-src/src/kernel/memory.cpp)
  PATCH_0001  backend/kytyplus-patches/0001-bc5-lle-agc.patch at 0fede35d (the shared tree's patch); its
              src/bc5/switch_defaults.hpp (a new file in the patch) is the tree's file
  OUT_DIR     scratch: old/ and new/ trees, then the two patches are written beside this script
Fixed inputs beside this script: ../r438o/r438o.cpp (2e6168de, the tree's unit), ../../../backend (main's backend:
direct.cpp eacf8d2a, direct.hpp 9256f3b9), the generators (md5-pinned below, except mkq438x.py: see GATE).

Steps (every generator is run as it is, with python -I; every own replacement must match exactly once):
  memory.cpp: a1/mka1.py -> a1b/mka1b.py -> a1p/mka1p.py -> a1/mka1c.py (counters and A1J: normal build only, already
              under #if !defined(BC5_LEAN)); then KYTY_BC5_0438_A1 and KYTY_BC5_0438_A1P read "on unless 0".
              A1P also needs exp 0412's sorted physmap (Pm412Mode() == 1): KYTY_BC5_PHYSMAP_SORTED is "1" in kFixes
              (forced in normal) and BC5_FIXED_ENV(..., "1") in lean, so A1P is on by default in both builds.
  bc5LleAgc.cpp: a2/mka2host.py --any on r438o.cpp, then GATE (below), then BC5_0438_INFLIGHT_NG / BC5_0438_OPEN_NG
              read "on unless 0".
  switch_defaults.hpp: unchanged (48ae1cd6; read from patch 0001 only to pin it).
  backend: a2/mka2be.py on main's backend; then BC5_DIRECT_0438_A2 reads "on unless 0", and A2's compare-only check
              (BC5_DIRECT_0438_A2_CHECK, its compare block, the tag a2c438 counters and 60-s line) becomes a compile-time
              option of the backend, #if defined(BC5_0438_A2_CHECK_BUILD): not defined in the bake, so neither its code
              nor its word nor its line is in the shared archive; a private diagnosis build may define it.
GATE: q438/mkq438x.py's own replacement list, read with ast (not copied): every top-level rep(old, new) call in order.
  Taken out: its labelmap steps LM2-LM6 (r438_scan / q438_scan / submit_now / opt.mapped) and, from the kept text,
  the Q438 pieces (q438_writer_queued, the q438_on() test). Moved: LM1's anchor is a Q438 line; only its
  inflight_ng_on() and g_inflight_ng are kept, placed after r438o's t_r438_own. The q438 block does not exist here:
  every step that appends before "// ---- end of exp 0438 (tag q438) ---" goes to a new block of its own,
  "tag ng438w", at the place the q438 block sits in stack438 (before exp 0401 e11's m11 block). Every other step
  (NG1, NG2, ng438, wd438, open_ng, the busy counts, the fallback, the tick, ho430's records, the fault dump) is
  applied as mkq438x.py writes it. A step this script does not know is applied as it is and printed.
Prints every md5. Writes OUT_DIR/{old,new}/..., 0004-bc5-0438-bake438b.patch (host: memory.cpp, bc5LleAgc.cpp) and 0004-backend-0438-bake438b.patch (backend: direct.cpp, direct.hpp, new mapping_index.hpp),
both a/ b/ labelled unified diffs, and pins438b.inc (the md5s the kit's scripts check).
"""
import ast
import hashlib
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
REPO = os.path.dirname(os.path.dirname(EXP))
MEM, P0001, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
PY = sys.executable


def md5b(b):
    return hashlib.md5(b).hexdigest()


def md5f(p):
    return md5b(open(p, 'rb').read())


def need(path, want, what):
    got = md5f(path)
    assert got.startswith(want), f'{what}: {path} is {got}, not {want}'
    print(f'in   {got}  {what}')


def run(*args):
    r = subprocess.run([PY, '-I', *args], capture_output=True)
    sys.stdout.write(r.stdout.decode('utf-8', 'replace').replace('\r', ''))
    if r.returncode != 0:
        sys.stdout.write(r.stderr.decode('utf-8', 'replace').replace('\r', ''))
        raise SystemExit(f'FAILED: {args[0]}')


def rep1(s, old, new, what):
    n = s.count(old)
    assert n == 1, f'{what}: {n} matches for {old[:100]!r}'
    return s.replace(old, new)


def write(p, data):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, 'wb').write(data)


# ---- pinned inputs -------------------------------------------------------------------------------------------------
G = {'a1': os.path.join(EXP, 'a1', 'mka1.py'), 'a1b': os.path.join(EXP, 'a1b', 'mka1b.py'), 'a1p': os.path.join(EXP, 'a1p', 'mka1p.py'),
     'a1c': os.path.join(EXP, 'a1', 'mka1c.py'), 'a2be': os.path.join(EXP, 'a2', 'mka2be.py'), 'a2host': os.path.join(EXP, 'a2', 'mka2host.py'),
     'mi': os.path.join(EXP, 'a2', 'mapping_index.hpp'), 'q438x': os.path.join(EXP, 'q438', 'mkq438x.py')}
UNIT = os.path.join(EXP, 'r438o', 'r438o.cpp')
BE = os.path.join(REPO, 'backend')
need(MEM, 'aa7d7f5b', 'the tree\'s memory.cpp')
need(P0001, '0fede35d', 'patch 0001 (the shared tree)')
need(UNIT, '2e6168de', 'the tree\'s bc5LleAgc.cpp (r438o)')
need(os.path.join(BE, 'src', 'direct.cpp'), 'eacf8d2a', 'main\'s backend direct.cpp (archive d6638808)')
need(os.path.join(BE, 'include', 'bc5', 'direct.hpp'), '9256f3b9', 'main\'s backend direct.hpp')
need(G['mi'], '39952c48', 'a2/mapping_index.hpp')
need(G['a2be'], '48596978', 'a2/mka2be.py')
need(G['a2host'], '1c91b106', 'a2/mka2host.py')
for k in ('a1', 'a1b', 'a1p', 'a1c'):
    print(f'in   {md5f(G[k])}  {os.path.relpath(G[k], EXP)} (its own input pin is checked by it)')
q438x_md5 = md5f(G['q438x'])
print(f'in   {q438x_md5}  q438/mkq438x.py (the gate text; not pinned here, it follows the file{"; MKQ438X_MD5 pins it" if os.environ.get("MKQ438X_MD5") else ""})')
if os.environ.get('MKQ438X_MD5'):
    assert q438x_md5.startswith(os.environ['MKQ438X_MD5']), f'mkq438x.py is {q438x_md5}, not {os.environ["MKQ438X_MD5"]}'

T = os.path.join(OUT, 'tmp')
os.makedirs(T, exist_ok=True)
OLD, NEW = os.path.join(OUT, 'old'), os.path.join(OUT, 'new')

# ---- switch_defaults.hpp from patch 0001 (a new file there) ---------------------------------------------------------
p = open(P0001, 'rb').read().decode('utf-8')
i = p.index('diff --git a/src/bc5/switch_defaults.hpp b/src/bc5/switch_defaults.hpp\n')
j = p.index('\ndiff --git ', i + 1)
sec = p[i:j + 1].split('\n')
assert sec[1] == 'new file mode 100644' and sec[3] == '--- /dev/null' and sec[5].startswith('@@ -0,0 +1,'), sec[:6]
nlines = int(sec[5].split('+1,')[1].split(' ')[0])
body = [ln[1:] for ln in sec[6:] if ln.startswith('+')]
assert len(body) == nlines and all(ln.startswith('+') or ln == '' for ln in sec[6:]), 'switch_defaults.hpp section'
swd_old = ('\n'.join(body) + '\n').encode('utf-8')

# ---- memory.cpp ------------------------------------------------------------------------------------------------------
m1, m2, m3, m4 = (os.path.join(T, f'memory_m{k}.cpp') for k in (1, 2, 3, 4))
run(G['a1'], MEM, m1)
run(G['a1b'], m1, m2)
run(G['a1p'], m2, m3)
run(G['a1c'], m3, m4)
mem = open(m4, 'rb').read().decode('utf-8')
assert '\r' not in mem
mem = rep1(mem, '\t\t\tconst char* e  = std::getenv("KYTY_BC5_0438_A1");\n\t\t\tconst bool  v  = e != nullptr && std::strcmp(e, "1") == 0;\n',
           '\t\t\tconst char* e  = std::getenv("KYTY_BC5_0438_A1");\n'
           '\t\t\tconst bool  v  = !(e != nullptr && std::strcmp(e, "0") == 0); // exp 0438 (bake438b): on unless "0"\n', 'A1 default')
mem = rep1(mem, '\t\tconst char* e = std::getenv("KYTY_BC5_0438_A1P");\n\t\tconst bool  v = e != nullptr && std::strcmp(e, "1") == 0;\n',
           '\t\tconst char* e = std::getenv("KYTY_BC5_0438_A1P");\n'
           '\t\tconst bool  v = !(e != nullptr && std::strcmp(e, "0") == 0); // exp 0438 (bake438b): on unless "0"\n', 'A1P default')
assert mem.count('std::getenv("KYTY_BC5_0438_A1")') == 1 and mem.count('std::getenv("KYTY_BC5_0438_A1P")') == 1
assert 'KYTY_BC5_0438_A1J' in mem and 'BC5_DIAG_ENV("KYTY_BC5_0438_A1J")' in mem

# ---- bc5LleAgc.cpp: A2's host change, then the gate ---------------------------------------------------------------
u1 = os.path.join(T, 'unit_a2.cpp')
run(G['a2host'], UNIT, u1, '--any')
s = open(u1, 'rb').read().decode('utf-8')
assert '\r' not in s

END_Q = '// ---- end of exp 0438 (tag q438) ---'
END_W = '// ---- end of exp 0438 (tag ng438w) ---'
BLOCK_W = ('// ---- BC5 experiment 0438 (tag ng438w): the acb gate\'s writer tests and wd438\'s ring (mkbake438b.py, the text of\n'
           '// q438/mkq438x.py\'s q438-block steps; the shared unit has no q438 block). Defined after ChainSlot and g_plw.\n'
           + END_W + '\n\n')
M11 = '// Experiment 0401 series e11 (tag m11): the label writes the jobs in flight had pending at a timeout'
LABELMAP_KEYS = ('if ((h >> 30u) == 3) { // as register_label_writes reads them', 'r438_scan(s1, n1, found);',
                 '\t\tif ((h >> 30u) == 3) {\n\t\t\tif (op == 0x49 && len >= 8) {\n', 'q438_scan(c.buf, found);',
                 'opt.mapped = [&maps_p, fl_area]', 'static void submit_now(const uint32_t* ib, uint32_t num_dwords, const char* kind, int ring, const Chain* chain) {\n')
QW_DECL = 'static bool q438_writer_queued(uint64_t label);\n'
QW_TEST = '\tif (!unready) unready = q438_on() && q438_writer_queued(label);\n'
QW_FN_A = '// exp 0438 (tag q438ng): a queued chain\'s early write of the label is pending (not yet submittable)\n'
QW_FN_B = '// exp 0438 (tag inflight_ng): a writer of the label is taken but not yet registered for real'
NG1_C = ('// satisfy it. With Q438 on, also while a queued chain writes the label: that write is not in g_plw for this thread\n'
         '// (ring_will_satisfy skips early entries off the game threads) and a stale value in memory would pass the wait.\n')
NG1_C2 = ('// satisfy it. (exp 0438 bake438b: the shared unit has no Q438; the gate\'s two writer tests, INFLIGHT_NG and OPEN_NG,\n'
          '// are added below.)\n')

src = open(G['q438x'], 'rb').read().decode('utf-8')
tree = ast.parse(src)
consts = {}
steps = []
for node in tree.body:
    if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
        try:
            consts[node.targets[0].id] = ast.literal_eval(node.value)
        except ValueError:
            pass
    if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call) and getattr(node.value.func, 'id', '') == 'rep':
        a = node.value.args
        assert len(a) == 2, f'mkq438x.py line {node.lineno}: rep with {len(a)} arguments'
        ev = [consts[x.id] if isinstance(x, ast.Name) else ast.literal_eval(x) for x in a]
        steps.append((node.lineno, ev[0], ev[1]))
print(f'gate: mkq438x.py has {len(steps)} replacement steps')
s = rep1(s, M11, BLOCK_W + M11, 'the ng438w block')
used = {'skipped labelmap': [], 'moved LM1': [], 'to ng438w': [], 'as is': []}
# Q438-only steps of the ngcount guard (the queue's flight union, its early registration, its early entries' end): not here
Q438_ONLY_KEYS = ('for (const auto& e: s.q_sets) s.f10_flight.insert', 'r438o_trim_locked(); // exp 0438 (stack438)', 't_q438_real.begin(), t_q438_real.end(), it->label)')
# steps anchored on a Q438 line: the same addition after the shared unit's line at that place
F16_LINE = [x + '\n' for x in s.split('\n') if x.startswith('\tstd::atomic<int>             f16_phase {0}; // exp 0430 F16:')]
assert len(F16_LINE) == 1, 'ChainSlot\'s f16_phase line'
ANCHOR_MAP = {'\tuint64_t                     q_nested = 0; // the submitter thread\'s own: nested inline takes\n': F16_LINE[0],
              '\tif (q438_on()) q438_stop(*this); // exp 0438 (q438): out of g_chains, then the submitter drains its queue and stops\n':
                  'ChainSlot::~ChainSlot() {\n\tif (!registered) return;\n'}
used['skipped Q438-only'] = []
used['re-anchored'] = []
for ln, old, new in steps:
    if any(k in old for k in LABELMAP_KEYS):
        used['skipped labelmap'].append(ln)
        continue
    if any(k in old for k in Q438_ONLY_KEYS):
        used['skipped Q438-only'].append(ln)
        continue
    if old in ANCHOR_MAP:
        assert new.startswith(old), f'line {ln}: not an insertion after its anchor'
        s = rep1(s, ANCHOR_MAP[old], ANCHOR_MAP[old] + new[len(old):], f're-anchored step (line {ln})')
        used['re-anchored'].append(ln)
        continue
    if 't_q438_early = 0;' in old:  # LM1: keep inflight_ng_on() and g_inflight_ng only
        a, b = new.index('static bool inflight_ng_on() {'), new.index('static std::atomic<uint64_t> g_inflight_ng {0};')
        b = new.index('\n', b) + 1
        anchor = 'static thread_local uint64_t              t_r438_own = 0;           // exp 0438 (r438o): the taken slice\'s own early seq (0: none)\n'
        s = rep1(s, anchor, anchor + new[a:b], f'LM1 (line {ln})')
        used['moved LM1'].append(ln)
        continue
    if old == END_Q:
        assert new.endswith(END_Q), f'line {ln}: a step at the q438 end that does not keep the end'
        add = new[:-len(END_Q)]
        if QW_FN_A in add:  # NG3: q438_writer_queued goes, inflight_ng_writer stays
            add = add[:add.index(QW_FN_A)] + add[add.index(QW_FN_B):]
        s = rep1(s, END_W, add + END_W, f'q438-block step (line {ln}) into ng438w')
        used['to ng438w'].append(ln)
        continue
    s = rep1(s, old, new, f'mkq438x.py step at line {ln}')
    used['as is'].append(ln)
for k, v in used.items():
    print(f'gate: {k}: mkq438x.py lines {v}')
assert len(used['skipped labelmap']) == 6, ('labelmap steps', used['skipped labelmap'])
assert len(used['moved LM1']) == 1
assert len(used['skipped Q438-only']) == len(Q438_ONLY_KEYS) and len(used['re-anchored']) == len(ANCHOR_MAP), used
s = rep1(s, QW_DECL, '', 'the q438_writer_queued declaration')
s = rep1(s, QW_TEST, '', 'the Q438 test in acb_wait_unready')
s = rep1(s, NG1_C, NG1_C2, 'NG1\'s Q438 comment')
s = rep1(s, 'static bool open_ng_writer(uint64_t label); // exp 0438 (open_ng), defined in the q438 block\n',
         'static bool open_ng_writer(uint64_t label); // exp 0438 (open_ng), defined in the ng438w block\n', 'open_ng_writer\'s comment')
for w in ('q438_on(', 'q438_writer_queued', 'kQ438Early', 't_lwm', 'BC5_0438_R438_LWM', 'BC5_0438_SUBMITQ', 'lw_packet_mapped', 'label_write_mapped',
          'g_q438', 'tag labelmap', 'tag q438)'):
    assert w not in s, f'Q438 or labelmap text left in the gate-only unit: {w}'
for w in ('INFLIGHT_NG', 'OPEN_NG'):
    s = rep1(s, f'\t\tconst char* e = std::getenv("BC5_0438_{w}");\n\t\treturn e != nullptr && e[0] == \'1\' && e[1] == 0;\n',
             f'\t\tconst char* e = std::getenv("BC5_0438_{w}");\n\t\treturn !(e != nullptr && e[0] == \'0\' && e[1] == 0); // exp 0438 (bake438b): on unless "0"\n', f'{w} default')
    s = rep1(s, f'BC5_0438_{w}, on only when "1"\n', f'BC5_0438_{w}, on unless "0" (bake438b)\n', f'{w} comment')
unit = s.encode('utf-8')

# ---- switch_defaults.hpp: unchanged in this bake (the A2 check is a build option now) ---------------------------
assert md5b(swd_old).startswith('48ae1cd6'), md5b(swd_old)

# ---- backend ---------------------------------------------------------------------------------------------------------
bo = os.path.join(T, 'be')
run(G['a2be'], BE, bo)
dc = open(os.path.join(bo, 'src', 'direct.cpp'), 'rb').read().decode('utf-8')
dc = rep1(dc, 'const bool a2 = [] { const char *e = std::getenv("BC5_DIRECT_0438_A2"); return e != nullptr && e[0] == \'1\' && e[1] == 0; }();',
          'const bool a2 = [] { const char *e = std::getenv("BC5_DIRECT_0438_A2"); return !(e != nullptr && e[0] == \'0\' && e[1] == 0); }(); // exp 0438 (bake438b): on unless "0"',
          'A2 default')
assert 'std::getenv("BC5_DIRECT_0438_A2_CHECK"); return e != nullptr && e[0] == \'1\' && e[1] == 0;' in dc
IFC = '#if defined(BC5_0438_A2_CHECK_BUILD) // exp 0438 (bake438b): A2\'s compare-only check, private diagnosis builds only\n'
ENDC = '#endif // BC5_0438_A2_CHECK_BUILD\n'
i = dc.index('    const bool a2_check = [] {')
j = dc.index('    // Experiment 0170: shared_maps is kept sorted by address', i)
blk = dc[i:j]
assert dc.count(blk) == 1 and blk.endswith('    }\n') and 'void a2_line() {' in blk
plain = ('    void a2_insert(const Mapping &m) { if (a2 && sorted) sorted = index_insert(sorted, m); }\n'
         '    void a2_erase(const Mapping &m) { if (a2 && sorted) sorted = index_erase(sorted, m); }\n')
dc = rep1(dc, blk, IFC + blk + '#else\n' + plain + ENDC, 'A2 check: members')
dc = rep1(dc, '    // BC5_DIRECT_0438_A2_CHECK=1 compares it with a full rebuild every 64th call (records only)\n',
          '    // with BC5_0438_A2_CHECK_BUILD defined, BC5_DIRECT_0438_A2_CHECK=1 compares it with a full rebuild every 64th call\n', 'A2 check: comment')
dc = rep1(dc, '    if (impl_->a2_check) impl_->a2_line(); // exp 0438 (tag a2c438)\n',
          IFC + '    if (impl_->a2_check) impl_->a2_line(); // exp 0438 (tag a2c438)\n' + ENDC, 'A2 check: the line')
i = dc.index('        if (impl_->a2_check && (impl_->a2_calls++ & 63u) == 0) {\n')
j = dc.index('        return impl_->sorted;\n    }\n', i)
blk = dc[i:j]
assert dc.count(blk) == 1 and blk.endswith('        }\n') and 'MISMATCH' in blk
dc = rep1(dc, blk, IFC + blk + ENDC, 'A2 check: the compare')
for c in ('        impl_->a2_rebuilds++; // exp 0438 (tag a2c438)\n', '        impl_->a2_drops++; // exp 0438 (tag a2c438)\n'):
    dc = rep1(dc, c, IFC + c + ENDC, 'A2 check: ' + c.strip())


def without_check(t):  # the text as the preprocessor sees it with BC5_0438_A2_CHECK_BUILD undefined
    out, skip = [], False
    for ln in t.split('\n'):
        if ln.startswith('#if defined(BC5_0438_A2_CHECK_BUILD)'):
            skip = True
            continue
        if skip and ln == '#else':
            skip = False
            continue
        if ln == '#endif // BC5_0438_A2_CHECK_BUILD':
            skip = False
            continue
        if not skip:
            out.append(ln.split('//')[0])
    return '\n'.join(out)


bake_view = without_check(dc)
for w in ('BC5_DIRECT_0438_A2_CHECK', 'a2c438', 'a2_check', 'a2_calls', 'a2_mismatches', 'a2_compares', 'a2_rebuilds', 'a2_drops', 'a2_line', 'MISMATCH', 'a2_ins', 'a2_era', 'a2_skipped'):
    assert re.search(r'\b' + w + r'\b', bake_view) is None, f'A2 check text outside BC5_0438_A2_CHECK_BUILD: {w}'
assert dc.count(IFC) == 5 and dc.count(ENDC) == 5
print('A2 check: 5 blocks under BC5_0438_A2_CHECK_BUILD; none of its words, lines or counters outside them')
be_cpp = dc.encode('utf-8')
be_hpp = open(os.path.join(bo, 'include', 'bc5', 'direct.hpp'), 'rb').read()
be_mi = open(os.path.join(bo, 'include', 'bc5', 'mapping_index.hpp'), 'rb').read()

# ---- trees and patches -----------------------------------------------------------------------------------------------
files_k = {'src/kernel/memory.cpp': (open(MEM, 'rb').read(), mem.encode('utf-8')), 'src/libs/bc5LleAgc.cpp': (open(UNIT, 'rb').read(), unit),
}
files_b = {'src/direct.cpp': (open(os.path.join(BE, 'src', 'direct.cpp'), 'rb').read(), be_cpp),
           'include/bc5/direct.hpp': (open(os.path.join(BE, 'include', 'bc5', 'direct.hpp'), 'rb').read(), be_hpp),
           'include/bc5/mapping_index.hpp': (None, be_mi)}
for tag, files in (('kyty', files_k), ('backend', files_b)):
    for f, (o, n) in files.items():
        if o is not None:
            write(os.path.join(OLD, tag, f), o)
        write(os.path.join(NEW, tag, f), n)


def mkpatch(tag, files, name):
    parts = []
    for f in files:
        a = f'old/{tag}/{f}' if files[f][0] is not None else '/dev/null'
        r = subprocess.run(['git', 'diff', '--no-index', '--no-color', '--full-index', a, f'new/{tag}/{f}'], cwd=OUT, capture_output=True)
        assert r.returncode == 1, (f, r.returncode, r.stderr)
        d = r.stdout.decode('utf-8')
        d = d.replace(f'a/old/{tag}/{f}', f'a/{f}').replace(f'b/new/{tag}/{f}', f'b/{f}')
        if files[f][0] is None:
            d = d.replace(f'diff --git a/new/{tag}/{f} b/{f}', f'diff --git a/{f} b/{f}')
        lines = [x for x in d.split('\n') if not x.startswith('index ')]  # as 0003-bc5-0438-r438o.patch: no index line
        parts.append('\n'.join(lines))
    out = ''.join(parts).encode('utf-8')
    write(os.path.join(HERE, name), out)
    return md5b(out)


pk = mkpatch('kyty', files_k, '0004-bc5-0438-bake438b.patch')
pb = mkpatch('backend', files_b, '0004-backend-0438-bake438b.patch')
pins = {'KIT_PATCH': pk[:8], 'KIT_BE_PATCH': pb[:8], 'MEM_OLD': 'aa7d7f5b', 'MEM_NEW': md5b(files_k['src/kernel/memory.cpp'][1])[:8],
        'UNIT_OLD': '2e6168de', 'UNIT_NEW': md5b(unit)[:8], 'SWD': md5b(swd_old)[:8],
        'BE_CPP_OLD': 'eacf8d2a', 'BE_CPP_NEW': md5b(be_cpp)[:8], 'BE_HPP_OLD': '9256f3b9', 'BE_HPP_NEW': md5b(be_hpp)[:8], 'BE_MI_NEW': md5b(be_mi)[:8],
        'MKQ438X': q438x_md5[:8]}
txt = '# BC5 exp 0438 (tag bake438b): written by mkbake438b.py; sourced by swap0438b.sh (step 1)\n' + ''.join(f'{k}={v}\n' for k, v in pins.items())
write(os.path.join(HERE, 'pins438b.inc'), txt.encode('utf-8'))
for f, (o, n) in list(files_k.items()) + list(files_b.items()):
    print(f'out  {md5b(n)}  {f}  (was {md5b(o) if o is not None else "absent"})')
print(f'out  {pk}  0004-bc5-0438-bake438b.patch')
print(f'out  {pb}  0004-backend-0438-bake438b.patch')
print(f'out  {md5b(txt.encode())}  pins438b.inc')
