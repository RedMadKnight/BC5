#!/usr/bin/env bash
# Exp 0388: box0388.sh's claim and release in a temporary HOME with a stand-in pgrep. No SSH, no box.
set -u
T=$(mktemp -d); mkdir -p "$T/bc5-work" "$T/bin"; printf '#!/bin/sh\nexit %s\n' '${FAKE_PGREP:-1}' > "$T/bin/pgrep"; chmod +x "$T/bin/pgrep"
export HOME=$T PATH=$T/bin:$PATH; L=$T/bc5-work/BOX-LOCK; S=$(cd "$(dirname "$0")" && pwd)/box0388.sh; bad=0
want() { if [ "$2" = "$3" ]; then echo "ok: $1"; else echo "FAIL: $1 (got $2, want $3)"; bad=1; fi; }
: > "$L"
FAKE_PGREP=0 bash "$S" claim > /dev/null; want "emulator stops the claim" "$?" 1
want "the lock stays empty" "$(wc -c < "$L" | tr -d ' ')" 0
echo "foreign | x" > "$L"
bash "$S" claim > /dev/null; want "a foreign lock stops the claim" "$?" 1
want "the foreign line stays" "$(cat "$L")" "foreign | x"
bash "$S" release > /dev/null; want "release refuses a foreign line" "$?" 1
want "the foreign line still stays" "$(cat "$L")" "foreign | x"
: > "$L"
bash "$S" claim > /dev/null; want "an empty lock is claimed" "$?" 0
case "$(cat "$L")" in "top exp 0388 | token "*) r=yes ;; *) r=no ;; esac; want "the line is ours" "$r" yes
want "no claim leftovers" "$(ls -A "$T/bc5-work" | grep -c '0388-\|d19-claim')" 0
bash "$S" claim > /dev/null; want "a second claim stops" "$?" 1
line=$(cat "$L"); echo "foreign | y" > "$L"
bash "$S" release > /dev/null; want "a replaced line is not released" "$?" 1
printf '%s\n' "$line" > "$L"
bash "$S" release > /dev/null; want "our line is released" "$?" 0
want "the lock is empty" "$(wc -c < "$L" | tr -d ' ')" 0
rm -f "$L"
bash "$S" claim > /dev/null; want "a missing lock is claimed" "$?" 0
rm -rf "$T"; exit $bad
