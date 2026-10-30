#!/usr/bin/env bash
# BC5 exp 0381: a J4 series on the laptop (README §17): off and on alternating, off first. It stops on §17's stop list:
# F443 in an ON start, a fault or timeout of another class, a failed reset, or a start that did not run.
# usage: j3series0381.sh <stage tag, e.g. S1> <first start number> <last> <hold_us|default> <out-dir>
ST=$1; A=$2; Z=$3; HOLD=$4; OUT=$5; HERE=$(cd "$(dirname "$0")" && pwd)
for n in $(seq "$A" "$Z"); do
    for sw in 0 1; do
        TAG=J4-$ST-$([ $sw = 1 ] && echo on || echo off)-$n
        echo "=== $TAG $(date +%T)"
        bash "$HERE/j4run0381.sh" "$TAG" "$sw" "$HOLD" "$OUT"
        K=$OUT/kern-$TAG.txt
        f=$(grep -c 'in page starting' "$K"); t=$(grep -c 'ring gfx_0.0.0 timeout' "$K"); r=$(grep -c 'reset succeeded' "$K")
        other=$(grep -o 'address 0x[0-9a-f]*' "$K" | grep -vc 'address 0x000008608c')
        [ -s "$OUT/start-$TAG.txt" ] && { echo "STOP: the start said: $(cat "$OUT/start-$TAG.txt")"; exit 2; }
        [ "$t" -gt "$r" ] && { echo "STOP: a timeout without a successful reset"; exit 2; }
        [ "$other" -gt 0 ] && { echo "STOP: a fault of another class"; exit 2; }
        [ "$t" -gt 0 ] && [ "$f" = 0 ] && { echo "STOP: a timeout without page faults"; exit 2; }
        [ "$sw" = 1 ] && [ "$f" -gt 0 ] && { echo "STOP: F443 in an ON start"; exit 2; }
    done
done
echo "=== series done $(date +%T)"
