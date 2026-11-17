#!/usr/bin/env bash
# BC5 exp 0432, item X: cut the by-diff body out of the edited unit and run test_x432.cpp on it.
#   test_x432.sh <edited bc5LleAgc.cpp> [compiler, default c++]
set -eu
U=${1:?the edited unit}; CXX=${2:-c++}; HERE=$(cd "$(dirname "$0")" && pwd)
W=$(mktemp -d); trap 'rm -rf "$W"' EXIT
python3 - "$U" "$W/x432_body.inc" << 'EOF' || python - "$U" "$W/x432_body.inc" << 'EOF2'
import sys
s = open(sys.argv[1], encoding="utf-8").read()
a = s.index("\t\t\tconst std::vector<DView>&                   ov = x432_prev[x432_k]->v;\n")
b = s.index("\t\t\td432::g_x_diff++;\n", a)
b = s.index("\n", s.index("d432::g_x_views += nv.size();", b)) + 1
open(sys.argv[2], "w", encoding="utf-8", newline="\n").write(s[a:b])
EOF
import sys
s = open(sys.argv[1], encoding="utf-8").read()
a = s.index("\t\t\tconst std::vector<DView>&                   ov = x432_prev[x432_k]->v;\n")
b = s.index("\t\t\td432::g_x_diff++;\n", a)
b = s.index("\n", s.index("d432::g_x_views += nv.size();", b)) + 1
open(sys.argv[2], "w", encoding="utf-8", newline="\n").write(s[a:b])
EOF2
cp "$HERE/test_x432.cpp" "$W/"
"$CXX" -std=c++20 -O1 -Wall -Wextra -o "$W/t" "$W/test_x432.cpp"
"$W/t"
