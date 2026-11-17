#!/usr/bin/env bash
# BC5 exp 0432 (laptop): t432.diff from a tree that is KytyPlus f266548 + patch bc39a035, committed in git.
#   mktree432.sh <tree> <exp 0415 kit/0415-l6-on-B.diff> <out t432.diff>
# Steps: reset the tree; exp 0415's L6 diff with --reject (semaphore.cpp and load_stat.hpp are put back, the rejected
# hunks of bc5LleAgc.cpp are dropped: a journal line and a statistic); mkt432.py; git diff.
set -eu
T=${1:?tree}; L6=${2:?the L6 diff}; OUT=${3:?out}; HERE=$(cd "$(dirname "$0")" && pwd)
cd "$T"
git checkout -q -- . && git clean -q -fd
git -c core.autocrlf=false apply --reject --whitespace=nowarn "$L6" > /dev/null 2>&1 || true
git checkout -q -- src/kernel/semaphore.cpp src/bc5/load_stat.hpp
find . -name '*.rej' -delete
python "$HERE/mkt432.py" src/libs/bc5LleAgc.cpp
git -c core.autocrlf=false diff > "$OUT" 2> /dev/null
git status --short
md5sum src/libs/bc5LleAgc.cpp src/common/platform/sysLinuxVirtual.cpp src/libs/libAmpr.cpp src/bc5/anon_sync.hpp | cut -c1-8,33-
