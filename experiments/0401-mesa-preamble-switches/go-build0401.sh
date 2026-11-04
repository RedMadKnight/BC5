#!/usr/bin/env bash
# BC5 experiment 0401 (laptop): one private build of a series on the box through box0401.sh, start to end: claim (the lock
# and the pins, over stdin), send the kit (test0401.py's KIT list and box0401.sh) with its sha256 list, setup, build under
# the series deadline, fetch the text results into raw/<series>/, release. The build output and every CPU test's output come
# back; nothing else. A failed build is released with its reason; nothing is retried.
# usage (laptop): bash go-build0401.sh <series, e.g. e5>
set -u
SER=${1:?a series}
HERE=$(cd "$(dirname "$0")" && pwd); OUT=$HERE/raw/$SER; mkdir -p "$OUT"; OUTW=$(cygpath -w "$OUT")   # Windows Python takes Windows paths
SSH=(ssh -o ConnectTimeout=10 -o BatchMode=yes bc250)
E=bc5-work/exp0401$SER
mapfile -t KIT < <(cd "$HERE" && python -c "import ast,sys; t=ast.parse(open('test0401.py',encoding='utf-8').read()); [print(x) for n in t.body if isinstance(n,ast.Assign) and getattr(n.targets[0],'id','')=='KIT' for x in ast.literal_eval(n.value)]" | tr -d '\r')
[ "${#KIT[@]}" -gt 10 ] || { echo "no KIT list"; exit 1; }
for k in "${KIT[@]}" box0401.sh; do [ -f "$HERE/$k" ] || { echo "no $k"; exit 1; }; done
if [ -n "${GO0401_TOKEN:-}" ]; then   # resume a claim of ours whose send failed: the token, nothing else changes
    out="TOKEN=$GO0401_TOKEN"; rc=0
else
    out=$(timeout 120 "${SSH[@]}" "BC5_0401_SERIES=$SER bash -s -- claim" < "$HERE/box0401.sh"); rc=$?
fi
echo "$out" | tee "$OUT/claim.txt"
TOKEN=$(printf '%s\n' "$out" | sed -n 's/^TOKEN=\([0-9][0-9]*\)$/\1/p')
[ $rc = 0 ] && [ -n "$TOKEN" ] || { echo "not claimed: nothing else done"; exit 2; }
rel() { timeout 120 "${SSH[@]}" "BC5_0401_SERIES=$SER bash ~/$E/box0401.sh release $TOKEN '$1'" 2>&1 | tee -a "$OUT/release.txt"; }
(cd "$HERE" && python -c "
import hashlib,sys
ks=sys.argv[1:]
open(r'$OUTW/kit.sha256','w',newline='\n').write(''.join(hashlib.sha256(open(k,'rb').read()).hexdigest()+'  '+k+'\n' for k in ks))" "${KIT[@]}") || { rel "the kit list failed"; exit 2; }
(cd "$HERE" && timeout 300 scp -q -o ConnectTimeout=10 -o BatchMode=yes "${KIT[@]}" box0401.sh "$OUT/kit.sha256" "bc250:$E/") || { rel "the send failed"; exit 2; }
timeout 120 "${SSH[@]}" "BC5_0401_SERIES=$SER bash ~/$E/box0401.sh setup $TOKEN" 2>&1 | tee "$OUT/setup.txt"
grep -q '^set up$' "$OUT/setup.txt" || { rel "the setup failed"; exit 2; }
echo "$(date '+%F %T') building (token $TOKEN)"
BT=2500; case $SER in e6p | e6) BT=2900 ;; e7) BT=3200 ;; esac   # e6p: the backend's build and tests too (box0401.sh's SERIES_S 3000)
timeout "$BT" "${SSH[@]}" "BC5_0401_SERIES=$SER bash ~/$E/box0401.sh build $TOKEN" > "$OUT/build-out.txt" 2>&1; brc=$?
tail -40 "$OUT/build-out.txt"
timeout 120 "${SSH[@]}" "cd ~/$E && tar cf - build.txt raw/*.out raw/*.txt 2> /dev/null" | (cd "$OUT" && tar xf - 2> /dev/null)
if [ $brc = 0 ] && tail -1 "$OUT/build-out.txt" | grep -q '^built: '; then rel "built: $SER"; echo "BUILD OK"; exit 0; fi
rel "the build failed (rc $brc)"; echo "BUILD FAILED (rc $brc)"; exit 1
