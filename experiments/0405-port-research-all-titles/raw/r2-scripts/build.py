# Build the merged, ranked tables and the e4-now spec collection from the six part files.
# Output: tables.md (ranked e4-now + later + done + skips), specs.md (port specs in rank order), stats.txt.
import re, os, sys
from collections import OrderedDict, Counter

R = sys.argv[1]
P = os.path.join(R, 'parts')
PARTS = ['KK', 'KL', 'KA', 'KS', 'SK', 'SS']
PART_SRC = {'KK': 'KytyPS5 dfec14a', 'KL': 'KytyPS5 dfec14a', 'KA': 'KytyPS5 dfec14a', 'KS': 'KytyPS5 dfec14a',
            'SK': 'sharpemu 514d766', 'SS': 'sharpemu 514d766'}

def split_row(line):
    cells, cur, tick, i = [], '', False, 0
    s = line.strip()
    if s.startswith('|'):
        s = s[1:]
    if s.endswith('|'):
        s = s[:-1]
    while i < len(s):
        c = s[i]
        if c == '`':
            tick = not tick
        if c == '\\' and i + 1 < len(s) and s[i + 1] == '|':
            cur += '|'; i += 2; continue
        if c == '|' and not tick:
            cells.append(cur.strip()); cur = ''
        else:
            cur += c
        i += 1
    cells.append(cur.strip())
    if len(cells) > 9:  # an unescaped pipe in the What cell (KS35)
        extra = len(cells) - 9
        cells = [cells[0], ' | '.join(cells[1:2 + extra])] + cells[2 + extra:]
    return cells

rows = OrderedDict()
order_in_part = {}
for n in PARTS:
    k = 0
    for line in open(os.path.join(P, n + '.md'), encoding='utf-8'):
        m = re.match(r'^\|\s*\**(' + n + r'\d+)\**\s*\|', line)
        if m:
            c = split_row(line)
            rid = m.group(1)
            rows[rid] = {'id': rid, 'part': n, 'what': c[1], 'src': c[2], 'lic': c[3], 'ours': c[4],
                         'eff': c[5], 'risk': c[6], 'cls': c[7], 'val': c[8] if len(c) > 8 else ''}
            order_in_part[rid] = k
            k += 1

def cls_of(r):
    c = r['cls']
    if c.startswith('e4-now'):
        return 'e4-now'
    if c.startswith('later'):
        return 'later'
    if 'provenance' in c:
        return 'skip-prov'
    if 'already' in c:
        return 'skip-match'
    if 'done' in c:
        return 'done'
    return '?'

# overrides
OVR = {'KK05': ('later', 'later (downgraded at merge: the 36-byte guest struct tm is KytyPS5\'s assertion, unverified; verify the layout first)'),
       'KS35': ('e4-now', 'e4-now')}
for rid, (c, txt) in OVR.items():
    rows[rid]['cls'] = txt

# merges: primary -> secondaries (secondary rows fold into the primary; their source is appended)
MERGE = OrderedDict([
    ('KK02', ['SK01']), ('KK04', ['SK02']), ('KK03', ['SK11']), ('KK20', ['KL07']), ('KK23', ['SK12']),
    ('KK24', ['SK16']), ('SK13', ['KK22']), ('SK08', ['KK14']), ('SK04', ['KK09']), ('KS03', ['SS01', 'KS02']),
    ('KS09', ['SS02']), ('KS06', ['SS03']), ('KS15', ['SS04']), ('SS05', ['KS19']), ('KL12', ['SS06']),
    ('KS27', ['SS23']), ('SS25', ['KS29']), ('KS30', ['SS31']), ('KS33', ['SS41']), ('KA36', ['SS40']),
    ('KS26', ['SK10']), ('SS22', ['KS69']), ('KA31', ['SS51']), ('KS14', ['SS10']), ('SK05', ['KK35']),
    ('KK19', ['KL08']), ('KK37', ['KL20']), ('SK24', ['KS38']), ('KA37', ['SS07']), ('KS56', ['SS46']),
    ('KS67', ['SS61']), ('KL26', ['SS62']), ('SS63', ['KS65']), ('KS66', ['SS50']),
    ('KA49', ['KS48']), ('KS39', ['SS14']),
])
DROP = {'KL27'}  # pointer row only (libs.cpp init list), not a candidate
secondary = {s: p for p, ss in MERGE.items() for s in ss}

E4_ORDER = ['KK02', 'KK01', 'KL01', 'KL02', 'KK06', 'KK03', 'KK04', 'SK04', 'SK03', 'KS03', 'KS09', 'KA01', 'KA02',
            'KA03', 'KS01', 'SS22', 'KK25', 'KK10', 'SK06', 'KS10', 'SK07', 'KS05', 'KS04', 'SK08', 'KA04', 'KA05',
            'KS06', 'KS14', 'KS17', 'KL03', 'SK09', 'KK07', 'KK08', 'KA06', 'KA07', 'KA08', 'KS13', 'KS15', 'KS16',
            'SK05', 'KK23', 'KK21', 'KK24', 'KS27', 'KS26']
LATER_ORDER = ['KK05', 'KK19', 'KL09', 'SK22', 'SK23', 'KK30', 'KK29', 'KS40', 'KA17', 'KA18', 'KL13', 'KL16',
               'SK26', 'SK27', 'SK28', 'SK29', 'KA37', 'SK24', 'KS39', 'KK37', 'KL21']
AREA = {'KK': 0, 'SK': 0, 'KL': 1, 'KA': 2, 'KS': 3, 'SS': 3}
# media rows of SS go with audio/media
SS_MEDIA = {'SS08', 'SS13', 'SS15', 'SS16', 'SS17', 'SS19', 'SS21', 'SS34', 'SS35', 'SS39', 'SS40', 'SS49', 'SS54',
            'SS55', 'SS56', 'SS57'}
AREA_NAME = ['kernel / libKernel / libc / Ult', 'loader / process services', 'audio / media', 'system services']

def area(rid):
    if rid in SS_MEDIA:
        return 2
    return AREA[rows[rid]['part']]

def is_regonly(r):
    t = (r['what'] + ' ' + r['val'] + ' ' + r['cls']).lower()
    return 'registration only' in t or 'registration-only' in t or 'stub-equivalent' in t or 'equivalent to loader' in t

def eff_letter(r):
    m = re.match(r'\s*([SML])\b', r['eff'])
    return m.group(1) if m else '-'

primaries = [rid for rid in rows if rid not in secondary and rid not in DROP]
by_cls = {}
for rid in primaries:
    by_cls.setdefault(cls_of(rows[rid]), []).append(rid)

def ranked(cls, explicit, regonly_last=False):
    ids = list(by_cls.get(cls, []))
    first = [i for i in explicit if i in ids]
    rest = [i for i in ids if i not in first]
    if regonly_last:
        rest.sort(key=lambda i: (is_regonly(rows[i]), {'S': 0, 'M': 1, 'L': 2}.get(eff_letter(rows[i]), 3), area(i),
                                 PARTS.index(rows[i]['part']), order_in_part[i]))
    else:
        rest.sort(key=lambda i: (area(i), PARTS.index(rows[i]['part']), order_in_part[i]))
    return first, rest

e4_first, e4_rest = ranked('e4-now', E4_ORDER)
lt_first, lt_rest = ranked('later', LATER_ORDER, regonly_last=True)

def esc(s):
    return s.replace('|', '\\|')

def ids_cell(rid):
    s = MERGE.get(rid, [])
    return rid + (' (+' + ', '.join(s) + ')' if s else '')

def src_cell(rid):
    r = rows[rid]
    out = '[' + PART_SRC[r['part']] + '] ' + r['src']
    for s in MERGE.get(rid, []):
        rs = rows[s]
        out += ' **+ ' + s + '** [' + PART_SRC[rs['part']] + '] ' + rs['src']
    return out

def ours_cell(rid):
    r = rows[rid]
    out = r['ours']
    for s in MERGE.get(rid, []):
        if rows[s]['ours'] and rows[s]['ours'] != r['ours']:
            out += ' / ' + s + ': ' + rows[s]['ours']
    return out

def lic(rid):
    ls = {rows[rid]['lic']} | {rows[s]['lic'] for s in MERGE.get(rid, [])}
    return ' + '.join(sorted(ls))

HDR = '| Rank | ID | What | Source | Licence | Ours | Effort | Risk | Class | Value |\n|---|---|---|---|---|---|---|---|---|---|\n'

def table(ids, start, label=None):
    out = HDR
    n = start
    for rid in ids:
        r = rows[rid]
        cls = r['cls']
        out += '| ' + ' | '.join(esc(x) for x in [str(n), ids_cell(rid), r['what'], src_cell(rid), lic(rid),
                                                   ours_cell(rid), r['eff'], r['risk'], cls, r['val']]) + ' |\n'
        n += 1
    return out, n

tables = []
t, n = table(e4_first, 1)
tables.append('### 4.1 e4-now, ranked across both projects (ranks 1-%d)\n\n' % (n - 1) + t)
start = n
sect = []
for a in range(4):
    ids = [i for i in e4_rest if area(i) == a]
    t, n2 = table(ids, n)
    sect.append('#### e4-now, ranks %d-%d: %s (in the part\'s own value order)\n\n' % (n, n2 - 1, AREA_NAME[a]) + t)
    n = n2
tables.append('### 4.2 e4-now, the rest by area (ranks %d-%d)\n\n' % (start, n - 1) + '\n'.join(sect))
e4_total = n - 1
t, n2 = table(lt_first + lt_rest, n)
tables.append('### 4.3 later (ranks %d-%d): the named larger items first, then S before M before L, registration-only stubs last\n\n' % (n, n2 - 1) + t)
later_total = n2 - n
n = n2
done = by_cls.get('done', [])
t, n2 = table(done, n)
tables.append('### 4.4 in e4 / done (not re-specified)\n\n' + t +
              '| - | sharpemu 11506fc | Submit-time DCB / SET_*_REG_INDIRECT table capture | [sharpemu 514d766] src/SharpEmu.Libs/Agc/AgcExports.Submissions.cs @ 11506fc | GPL-2.0-or-later | built as BC5_DIRECT_TABLE_CATCHER | - | - | in e4 / done | GPU-side catcher, listed for completeness |\n')
n = n2
skips = by_cls.get('skip-match', []) + by_cls.get('skip-prov', [])
t, n2 = table(skips, n)
tables.append('### 4.5 valid skips (already match, or provenance)\n\n' + t)

open(os.path.join(R, 'tables.md'), 'w', encoding='utf-8').write('\n'.join(tables))

# ---- specs ----
spec_blocks = {}
preamble = {}
hdr_re = re.compile(r'^\s*(?:-\s+)?(?:###\s+|\*\*)((?:KK|KL|KA|KS|SK|SS)\d+)')
for n_ in PARTS:
    txt = open(os.path.join(P, n_ + '.md'), encoding='utf-8').read()
    m3 = re.search(r'^## 3\..*$', txt, re.M)
    m4 = re.search(r'^## 4\..*$', txt, re.M)
    sec = txt[m3.end():m4.start()]
    cur, buf, pre = None, [], []
    for line in sec.split('\n'):
        h = hdr_re.match(line)
        if h:
            if cur:
                spec_blocks[cur] = '\n'.join(buf).strip()
            cur, buf = h.group(1), [line]
        elif cur:
            buf.append(line)
        else:
            pre.append(line)
    if cur:
        spec_blocks[cur] = '\n'.join(buf).strip()
    preamble[n_] = '\n'.join(pre).strip()

spec_out = []
spec_out.append('### Conventions from each part (read the one for the item\'s source part)\n')
for n_ in PARTS:
    if preamble[n_]:
        spec_out.append('**%s (%s):** ' % (n_, PART_SRC[n_]) + ' '.join(preamble[n_].split()) + '\n')
rank = 1
missing_specs = []
for rid in e4_first + [i for a in range(4) for i in e4_rest if area(i) == a]:
    spec_out.append('#### %d. %s\n' % (rank, ids_cell(rid)))
    for x in [rid] + MERGE.get(rid, []):
        if x in spec_blocks:
            b = spec_blocks[x]
            if x != rid:
                b = '*Second source, ' + x + ':* ' + b
            spec_out.append(b + '\n')
        elif cls_of(rows[x]) == 'e4-now':
            missing_specs.append(x)
    rank += 1
open(os.path.join(R, 'specs.md'), 'w', encoding='utf-8').write('\n'.join(spec_out))

# ---- stats ----
st = []
st.append('rows parsed %d, primaries %d, merged secondaries %d, dropped %d' % (len(rows), len(primaries), len(secondary), len(DROP)))
st.append('e4-now %d (explicit %d), later %d, done %d, skip-match %d, skip-prov %d' % (
    e4_total, len(e4_first), later_total, len(done), len(by_cls.get('skip-match', [])), len(by_cls.get('skip-prov', []))))
ce = Counter(eff_letter(rows[i]) for i in by_cls.get('later', []))
st.append('later effort ' + str(dict(ce)))
st.append('later reg-only %d' % sum(1 for i in by_cls.get('later', []) if is_regonly(rows[i])))
ce4 = Counter(eff_letter(rows[i]) for i in by_cls.get('e4-now', []))
st.append('e4 effort ' + str(dict(ce4)))
for a in range(4):
    st.append('e4 area %s: %d' % (AREA_NAME[a], sum(1 for i in by_cls.get('e4-now', []) if area(i) == a)))
    st.append('later area %s: %d' % (AREA_NAME[a], sum(1 for i in by_cls.get('later', []) if area(i) == a)))
st.append('by source e4: ' + str(Counter(PART_SRC[rows[i]['part']] for i in by_cls.get('e4-now', []))))
st.append('missing specs: ' + ','.join(missing_specs))
st.append('unknown class: ' + ','.join(by_cls.get('?', [])))
open(os.path.join(R, 'stats.txt'), 'w', encoding='utf-8').write('\n'.join(st) + '\n')
print('\n'.join(st))
