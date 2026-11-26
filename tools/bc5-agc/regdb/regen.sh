#!/usr/bin/env bash
# Regenerates the TSV lookup tables from the vendored Mesa files. Run after
# updating gfx10.json or sid.h; record the Mesa commit in NOTICE.md.
set -euo pipefail
cd "$(dirname "$0")"
SID="${1:?usage: regen.sh <path to Mesa src/amd/common/sid.h>}"
grep -E '^#define PKT3_[A-Z0-9_]+ +0x[0-9a-fA-F]+' "$SID" \
  | awk '{n=$2; sub(/^PKT3_/,"",n); v=strtonum($3); if (v<=255 && !(v in seen)) {seen[v]=1; printf "0x%02x\t%s\n", v, n}}' \
  | sort > pm4-opcodes.tsv
# Registers, fields and enums are read straight from gfx10.json at run time
# (src/regdb.rs, serde_json); only the opcode table is derived here.
wc -l pm4-opcodes.tsv
