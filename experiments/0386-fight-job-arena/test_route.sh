#!/usr/bin/env bash
# REVIEW-PORTS-31: box0386.sh's real route_sum and its check, on a stand-in copy of the route saves.
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
T=$(mktemp -d "${TMPDIR:-/tmp}/d19-test-XXXXXX") || exit 1
trap 'rm -rf "$T"' EXIT
P=0; N=0
ok() { P=$((P+1)); echo "ok   $1"; }
bad() { N=$((N+1)); echo "FAIL $1"; }
W=$T/w; C=$W/exp0358/saves-live-47aefd45
base() { rm -rf "$W"; mkdir -p "$C/sub"; echo one > "$C/a"; echo two > "$C/Z"; echo three > "$C/sub/b"; }
sed -n '/^route_sum() {/p' "$HERE/box0386.sh" > "$T/fn.sh"
sed -n 's/^\(    \)\(\[ "\$(route_sum)" = "\$ROUTE_SAVES" \] || die .*\)$/\2/p' "$HERE/box0386.sh" > "$T/check.sh"
[ -s "$T/fn.sh" ] && [ -s "$T/check.sh" ] && ok "the real lines are found" || bad "lines not found"
grep -q 'LC_ALL=C' "$T/fn.sh" && ok "route_sum names its locale" || bad "no LC_ALL=C"
if grep -q 'unset LC_ALL' "$T/fn.sh"; then bad "route_sum still unsets LC_ALL"; else ok "no default locale left"; fi
[ "$(sed -n 's/^ROUTE_SAVES=//p' "$HERE/pins0386.env")" = 9347496fbaf30f25 ] && ok "the pin is the measured C form" || bad "pin"
sum() { W=$W bash -c '. "$1"; route_sum' _ "$T/fn.sh"; }
check() { W=$W ROUTE_SAVES=$1 bash -c 'die() { echo "STOP: $*"; exit 1; }; . "$2"; . "$3"; echo pass' _ x "$T/fn.sh" "$T/check.sh"; }
base; S=$(sum)
[ -n "$S" ] && [ "${#S}" = 16 ] && ok "a 16 digit sum" || bad "sum [$S]"
want=$(cd "$C" && find . -type f -exec md5sum {} + | LC_ALL=C sort -k2 | md5sum | cut -c1-16)
[ "$S" = "$want" ] && ok "the form is C and dot" || bad "form $S $want"
out=$(check "$S" 2>&1); [ "$out" = pass ] && ok "positive: the pin passes" || bad "positive: $out"
base; echo changed > "$C/a"; out=$(check "$S" 2>&1); case "$out" in STOP:*) ok "changed content stops" ;; *) bad "changed: $out" ;; esac
base; touch "$C/new"; out=$(check "$S" 2>&1); case "$out" in STOP:*) ok "an added file stops" ;; *) bad "added: $out" ;; esac
base; rm "$C/sub/b"; out=$(check "$S" 2>&1); case "$out" in STOP:*) ok "a removed file stops" ;; *) bad "removed: $out" ;; esac
base; rm -rf "$C"; out=$(check "$S" 2>&1); case "$out" in *STOP:*) ok "a missing copy stops" ;; *) bad "missing: $out" ;; esac
base; out=$(check 47aefd4567e6d346 2>&1); case "$out" in STOP:*) ok "another pin stops" ;; *) bad "mismatch: $out" ;; esac
echo "== $P passed, $N failed"
[ "$N" = 0 ]
