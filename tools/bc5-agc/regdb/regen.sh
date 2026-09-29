#!/usr/bin/env bash
# Regenerates the TSV lookup tables from the vendored Mesa files. Run after
# updating gfx10.json or sid.h; record the Mesa commit in NOTICE.md.
set -euo pipefail
cd "$(dirname "$0")"
SID="${1:?usage: regen.sh <path to Mesa src/amd/common/sid.h>}"
grep -E '^#define PKT3_[A-Z0-9_]+ +0x[0-9a-fA-F]+' "$SID" \
  | awk '{n=$2; sub(/^PKT3_/,"",n); v=strtonum($3); if (v<=255 && !(v in seen)) {seen[v]=1; printf "0x%02x\t%s\n", v, n}}' \
  | sort > pm4-opcodes.tsv
awk '/"map": \{"at": [0-9]+, "to": "mm"\}/ {match($0, /"at": [0-9]+/); at=substr($0, RSTART+6, RLENGTH-6); have=1; next}
     have && /"name": "/ {match($0, /"name": "[^"]+"/); n=substr($0, RSTART+9, RLENGTH-10); printf "0x%05x\t%s\n", at/4, n; have=0}' gfx10.json \
  | sort > gfx10-registers.tsv
wc -l pm4-opcodes.tsv gfx10-registers.tsv
