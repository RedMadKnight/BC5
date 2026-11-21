#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0
"""BC5 experiment 0438 (tag a2): the host unit reads Device::sorted_mappings() as a MappingIndex (mapping_index.hpp).
Usage: mka2host.py IN.cpp OUT.cpp   (IN: the bake unit ff9e8fe2..., or a unit made from it whose md5 is given with
                                    --any; the two replacements must then still match the expected counts)
- every holder "std::shared_ptr<const std::vector<bc5::direct::Mapping>>" (9) becomes
  "std::shared_ptr<const bc5::direct::MappingIndex>";
- every parameter "const std::vector<bc5::direct::Mapping>& maps" (15) becomes "const bc5::direct::MappingIndex& maps";
  a plain vector passed to one (the diagnostic callers' g_dev->mappings(), an empty "none") converts to a one-chunk
  index. Plain vectors the unit edits (have, have_insert, scratch_fill) stay vectors.
The behaviour is unchanged: the index reads like the sorted vector it replaces (size, operator[], random-access
iterators, so std::upper_bound and range-for work as before).
"""
import hashlib
import sys

args = [a for a in sys.argv[1:] if not a.startswith('--')]
IN, OUT = args[0], args[1]
src = open(IN, 'rb').read()
if '--any' not in sys.argv:
    assert hashlib.md5(src).hexdigest() == 'ff9e8fe2e4139264ebaf74f9e84bd892', 'not the bake unit'
s = src.decode('utf-8')
assert '\r' not in s
for old, new, n in (('std::shared_ptr<const std::vector<bc5::direct::Mapping>>', 'std::shared_ptr<const bc5::direct::MappingIndex>', 9),
                    ('const std::vector<bc5::direct::Mapping>& maps', 'const bc5::direct::MappingIndex& maps', 15)):
    assert s.count(old) == n, (s.count(old), old)
    s = s.replace(old, new)
out = s.encode('utf-8')
open(OUT, 'wb').write(out)
print('mka2host:', hashlib.md5(out).hexdigest())
