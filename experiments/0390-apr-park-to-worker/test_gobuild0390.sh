#!/usr/bin/env bash
# Exp 0390: gobuild0390.sh with stand-ins for ssh, scp and timeout's targets, on a copy under a d19-test- path. No box.
# The stand-in ssh records every command; a plan file sets the build's exit code and output.
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
T=$(mktemp -d "${TMPDIR:-/tmp}/d19-test-XXXXXX") || exit 1
trap 'rm -rf "$T"' EXIT
FILES="box0390.sh build0390.py patch0390.py units0390.sha256 patched0390.sha256"
for f in $FILES gobuild0390.sh pins0390.env; do cp "$HERE/$f" "$T/"; done
cat > "$T/ssh" <<EOF
#!/usr/bin/env bash
c=\${!#}
echo "\$c" >> "$T/calls"
case "\$c" in
  *" claim "*) cat > /dev/null; exit "\$(cat "$T/claim-rc" 2> /dev/null || echo 0)" ;;
  *" release"*) cat > /dev/null; echo "lock released"; exit 0 ;;
  *sha256sum*) cd "$T" && [ -e "$T/sum-bad" ] && echo "0000  box0390.sh" || (cd "$T" && sha256sum $FILES | sed 's/ \*/  /'); exit 0 ;;
  *" build"*) cat "$T/build-out" 2> /dev/null; exit "\$(cat "$T/build-rc" 2> /dev/null || echo 0)" ;;
esac
EOF
cat > "$T/scp" <<EOF
#!/usr/bin/env bash
echo "scp" >> "$T/calls"
[ ! -e "$T/scp-bad" ]
EOF
chmod +x "$T/ssh" "$T/scp"
printf 'SSH=%s/ssh; SCP=%s/scp\n' "$T" "$T" > "$T/fake.sh"
P=0; N=0
ok() { P=$((P + 1)); echo "ok   $1"; }
bad() { N=$((N + 1)); echo "FAIL $1"; }
reset() {
    rm -f "$T/calls" "$T/claim-rc" "$T/build-rc" "$T/build-out" "$T/scp-bad" "$T/sum-bad"
    cp "$HERE/pins0390.env" "$T/pins0390.env"
}
go() { out=$(D19_RUN_FAKE=$T/fake.sh bash "$T/gobuild0390.sh" 15 2>&1); rc=$?; }
n() { grep -c -- "$1" "$T/calls" 2> /dev/null; }
good='private binary 0123456789abcdef0123456789abcdef, shared before aa, after aa'

reset; echo "$good" > "$T/build-out"; go
[ "$rc" = 0 ] && grep -q '^NORMAL=0123456789abcdef0123456789abcdef$' "$T/pins0390.env" && [ "$(n ' release')" = 1 ] && ok "built: pinned, released" || bad "built: rc $rc $out"
reset; echo 1 > "$T/claim-rc"; go
[ "$rc" = 2 ] && [ "$(n scp)" = 0 ] && [ "$(n 'box0390.sh build$')" = 0 ] && [ "$(n ' release')" = 0 ] && ok "not claimed: nothing sent, nothing released" || bad "no claim: rc $rc"
reset; touch "$T/scp-bad"; go
[ "$rc" = 2 ] && [ "$(n 'box0390.sh build$')" = 0 ] && [ "$(n ' release')" = 1 ] && ok "a failed send gives the lock back" || bad "send: rc $rc"
reset; touch "$T/sum-bad"; go
[ "$rc" = 2 ] && [ "$(n 'box0390.sh build$')" = 0 ] && [ "$(n ' release')" = 1 ] && ok "sent files that differ give the lock back" || bad "sum: rc $rc"
reset; echo 1 > "$T/build-rc"; echo "0390 STOP: patch failed" > "$T/build-out"; go
[ "$rc" = 2 ] && [ "$(n ' release')" = 1 ] && grep -q '^NORMAL=FILL$' "$T/pins0390.env" && ok "a stopped build gives the lock back, no pin" || bad "stop: rc $rc"
reset; echo 255 > "$T/build-rc"; go
[ "$rc" = 3 ] && [ "$(n ' release')" = 0 ] && grep -q '^NORMAL=FILL$' "$T/pins0390.env" && ok "a lost connection: unknown, the lock stays" || bad "lost: rc $rc"
reset; echo "no such line" > "$T/build-out"; go
[ "$rc" = 2 ] && [ "$(n ' release')" = 1 ] && grep -q '^NORMAL=FILL$' "$T/pins0390.env" && ok "no binary line: no pin, the lock back" || bad "no line: rc $rc"
echo "== $P passed, $N failed"
[ "$N" = 0 ]
