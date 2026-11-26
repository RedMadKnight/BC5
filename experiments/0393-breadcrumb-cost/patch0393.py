#!/usr/bin/env python3
# BC5 experiment 0393: exp 0277's breadcrumbs on today's tree, as one private binary for the same-route cost test. The
# tree's bc5LleAgc.cpp is 29b3d8c6, the unit in main's patch 0001 at 5b22f700. patch0277.py is loaded unchanged from this
# directory and md5-checked; its 18 edits are applied as they are, each anchor exactly once. The input is only read.
# usage: patch0393.py <shared bc5LleAgc.cpp, md5 29b3d8c6> <out .cpp> <out .diff>
import difflib, hashlib, importlib.util, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
P0277 = 'b2fdb2e95d5d97bb82ef53cdde9557bd'
TREE = '29b3d8c602c92c84fa7731d3902fcc48'    # bc5LleAgc.cpp in main's patch 0001 at 5b22f700
RESULT = '1ed25bdfab48521854033f702b3bfc20'  # plus exp 0277's edits


def main():
    src_path, out_path, diff_path = sys.argv[1:4]
    path = os.path.join(HERE, 'patch0277.py')
    if hashlib.md5(open(path, 'rb').read()).hexdigest() != P0277:
        sys.exit(f'patch0277.py: not the script of exp 0277 (md5 {P0277})')
    spec = importlib.util.spec_from_file_location('patch0277', path)
    p77 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(p77)
    raw = open(src_path, 'rb').read()
    if hashlib.md5(raw).hexdigest() != TREE:
        sys.exit(f'{src_path}: md5 {hashlib.md5(raw).hexdigest()}, expected {TREE} (main at 5b22f700)')
    src = raw.decode('utf-8')
    text = src
    for k, (old, new) in enumerate(p77.EDITS, 1):
        n = text.count(old)
        if n != 1:
            sys.exit(f'edit {k}: anchor found {n} times')
        text = text.replace(old, new)
    out = text.encode('utf-8')
    if hashlib.md5(out).hexdigest() != RESULT:
        sys.exit(f'result md5 {hashlib.md5(out).hexdigest()}, expected {RESULT}')
    open(out_path, 'wb').write(out)
    diff = difflib.unified_diff(src.splitlines(keepends=True), text.splitlines(keepends=True),
                                'a/src/libs/bc5LleAgc.cpp', 'b/src/libs/bc5LleAgc.cpp', n=3)
    open(diff_path, 'w', encoding='utf-8', newline='\n').write(''.join(diff))
    print(f'{out_path}: md5 {RESULT}, {len(p77.EDITS)} edits')


if __name__ == '__main__':
    main()
