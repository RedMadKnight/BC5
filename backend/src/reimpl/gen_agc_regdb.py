#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Generate backend/include/bc5/reimpl/agc_regdb.hpp from Mesa's gfx10 register database.

The own-source tables (agc_tables.cpp, agc_fill_shader.cpp) name every
register, field and enum value. This script collects the names they use and writes their
offsets, field positions and enum values from tools/bc5-agc/regdb/gfx10.json (Mesa, MIT), so the
header holds nothing but facts of that database for the names the sources ask for.

Names used in the sources:
  ctx::NAME, sh::NAME, uc::NAME   register dword offset relative to its space base
                                  (context 0xA000, SH 0x2C00, uconfig 0xC000)
  a lower-case n in NAME          a family: std::array indexed by n (n replaced by 0, 1, ...;
                                  "_n" falls back to no suffix for n = 0, as Mesa names
                                  PA_CL_VPORT_XSCALE, PA_CL_VPORT_XSCALE_1, ...); the length is
                                  the number of consecutive members that exist
  f::NAME                         struct with every field of NAME as a Field {lo, hi}
  e::NAME                         enum value (unique across gfx10.json's enums, or unique among
                                  the enums of the fields it is written into with fld())
It also checks that each fld(f::REG::FIELD, e::ENUM) uses an enum of that field.

usage: python gen_agc_regdb.py   (paths are relative to this file)
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.normpath(os.path.join(HERE, '..', '..'))
REPO = os.path.dirname(BACKEND)
DB = os.path.join(REPO, 'tools', 'bc5-agc', 'regdb', 'gfx10.json')
OUT = os.path.join(BACKEND, 'include', 'bc5', 'reimpl', 'agc_regdb.hpp')
SOURCES = ['agc_tables.cpp', 'agc_fill_shader.cpp']
SPACES = {'ctx': (0xA000, 0xB000), 'sh': (0x2C00, 0x3000), 'uc': (0xC000, 0x10000)}


def die(msg):
    sys.exit('gen_agc_regdb: ' + msg)


def main():
    db = json.load(open(DB, encoding='utf-8'))
    regs = {}
    for m in db['register_mappings']:
        if m['map']['to'] != 'mm':
            continue
        regs[m['name']] = (m['map']['at'] // 4, m.get('type_ref'))
    types = db['register_types']
    enums = {}
    for ename, e in db['enums'].items():
        for ent in e['entries']:
            enums.setdefault(ent['name'], set()).add((ename, ent['value']))

    text = ''
    for s in SOURCES:
        p = os.path.join(HERE, s)
        if os.path.exists(p):
            text += open(p, encoding='utf-8').read()

    def members(name):
        if 'n' not in name:
            return None
        out = []
        i = 0
        while True:
            cand = name.replace('n', str(i))
            if cand not in regs and i == 0 and '_n' in name:
                cand = name.replace('_n', '')
            if cand not in regs:
                break
            out.append(cand)
            i += 1
        if not out:
            die('no member of family %s' % name)
        return out

    def offset(space, name):
        if name not in regs:
            die('%s::%s not in gfx10.json' % (space, name))
        d = regs[name][0]
        lo, hi = SPACES[space]
        if not lo <= d < hi:
            die('%s is at dword 0x%X, outside the %s space' % (name, d, space))
        return d - lo

    def fields(name):
        if name not in regs or regs[name][1] is None:
            die('f::%s has no fields in gfx10.json' % name)
        return types[regs[name][1]]['fields']

    lines = []
    for space in SPACES:
        names = sorted(set(re.findall(r'\b%s::([A-Za-z0-9_]+)' % space, text)))
        lines.append('namespace %s {' % space)
        for n in names:
            fam = members(n)
            if fam is None:
                lines.append('inline constexpr std::uint32_t %s = 0x%03X;' % (n, offset(space, n)))
            else:
                vals = ['0x%03X' % offset(space, m) for m in fam]
                lines.append('// %s .. %s' % (fam[0], fam[-1]))
                lines.append('inline constexpr std::array<std::uint32_t, %d> %s = {' % (len(fam), n))
                for i in range(0, len(vals), 10):
                    lines.append('    ' + ', '.join(vals[i:i + 10]) + ',')
                lines.append('};')
        lines.append('} // namespace %s' % space)
        lines.append('')

    lines.append('namespace f {')
    fnames = sorted(set(re.findall(r'\bf::([A-Za-z0-9_]+)', text)))
    field_enums = {}
    for n in fnames:
        fam = members(n)
        src = fam[0] if fam else n
        flist = fields(src)
        if fam:
            for m in fam[1:]:
                if fields(m) != flist:
                    die('family %s: %s has other fields than %s' % (n, m, src))
        lines.append('struct %s { // %s' % (n, src if fam is None else '%s..%s' % (fam[0], fam[-1])))
        for fd in flist:
            lines.append('    static constexpr Field %s{%d, %d};' % (fd['name'], fd['bits'][0],
                                                                    fd['bits'][1]))
            field_enums[(n, fd['name'])] = fd.get('enum_ref')
        lines.append('};')
    lines.append('} // namespace f')
    lines.append('')

    aliases = dict(re.findall(r'using\s+(\w+)\s*=\s*f::(\w+)\s*;', text))
    used_in = {}  # enum value name -> enums of the fields it is written into
    for reg, fd, en in re.findall(r'fld\(\s*(?:f::)?(\w+)::(\w+),\s*e::(\w+)\s*\)', text):
        reg = aliases.get(reg, reg)
        ref = field_enums.get((reg, fd))
        if ref is None:
            die('fld(%s::%s, e::%s): the field has no enum in gfx10.json' % (reg, fd, en))
        if not any(e == ref for e, _ in enums.get(en, ())):
            die('fld(%s::%s, e::%s): %s is not in the field\'s enum %s' % (reg, fd, en, en, ref))
        used_in.setdefault(en, set()).add(ref)

    lines.append('namespace e {')
    for n in sorted(set(re.findall(r'\be::([A-Za-z0-9_]+)', text))):
        cands = enums.get(n, set())
        if n in used_in:  # a name shared by several enums: take the one of its fields
            cands = {(e, v) for e, v in cands if e in used_in[n]}
        vals = {v for _, v in cands}
        if len(vals) != 1:
            die('enum value %s: %s in gfx10.json' % (n, 'missing' if not vals else 'ambiguous'))
        owners = ', '.join(sorted(e for e, _ in cands))
        lines.append('// %s' % owners)
        lines.append('inline constexpr std::uint32_t %s = %d;' % (n, vals.pop()))
    lines.append('} // namespace e')

    head = '''// SPDX-License-Identifier: MIT
// GENERATED by backend/src/reimpl/gen_agc_regdb.py from tools/bc5-agc/regdb/gfx10.json (Mesa
// src/amd/registers, MIT, see tools/bc5-agc/regdb/NOTICE.md). Do not edit; re-run the script.
// Only the names used by the own-source tables: register dword offsets relative to their space
// (ctx: context, base 0xA000; sh: SH, base 0x2C00; uc: uconfig, base 0xC000), register families
// (a lower-case n in the name, indexed by n), the fields of the registers named under f:: and enum
// values under e::.
#pragma once

#include "bc5/reimpl/reg_fields.hpp"

#include <array>
#include <cstdint>

// NOLINTBEGIN(readability-identifier-naming)
namespace bc5::reimpl::regdb {

'''
    tail = '''
} // namespace bc5::reimpl::regdb
// NOLINTEND(readability-identifier-naming)
'''
    with open(OUT, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(head + '\n'.join(lines) + '\n' + tail)
    print('wrote', OUT)


if __name__ == '__main__':
    main()
