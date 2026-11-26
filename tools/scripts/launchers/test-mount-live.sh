#!/usr/bin/env bash
# exp 0439 (2026-11-21): stand-in test of the launchers' live-mount check (play-t1.sh, play-pkg.sh). No FUSE: stub
# mountpoint (a mount is a file .mounted in the directory), fusermount3 (removes it; FUSER_STUCK=1 makes -u and -u -z
# fail) and bc5-mount (marks the mount and writes sce_sys/param.json). The helpers and each launcher's mount block are
# taken from the launcher itself between its markers.
#   bash test-mount-live.sh        -> PASS/FAIL per case
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
mkdir -p "$T/bin"
cat > "$T/bin/mountpoint" <<'EOF'
#!/usr/bin/env bash
d=${@: -1}; [ -e "$d/.mounted" ]
EOF
cat > "$T/bin/fusermount3" <<'EOF'
#!/usr/bin/env bash
d=${@: -1}; echo "fusermount3 $*" >> "$CALLS"; [ "${FUSER_STUCK:-0}" = 1 ] && exit 1; rm -f "$d/.mounted"
EOF
cat > "$T/bin/bm" <<'EOF'
#!/usr/bin/env bash
d=${@: -1}; echo "bm $*" >> "$CALLS"; mkdir -p "$d/sce_sys"; echo '{"titleId":"X"}' > "$d/sce_sys/param.json"; touch "$d/.mounted"
EOF
chmod +x "$T/bin/"*
export PATH="$T/bin:$PATH" CALLS="$T/calls"
fail=0
block() { # $1 launcher -> the helpers and its mount block as a script
  local f=$HERE/$1
  sed -n '/^# --- mount (exp 0439) ---$/,/^}$/p' "$f"
  if [ "$1" = play-t1.sh ]; then sed -n '/^mkdir -p "\$M"$/,/^# --- end mount ---$/p' "$f"
  else sed -n '/^if \[ -n "\${BC5_GAME_DIR:-}" \]; then M=\$BC5_GAME_DIR/,/^# --- end mount ---$/p' "$f"; fi
}
run() { # $1 launcher, $2 case name, $3 setup, $4 expected: ok|fail, $5 expected calls (grep -c patterns, ;-separated)
  local M=$T/m-$2 out rc
  rm -rf "$M" "$CALLS"; mkdir -p "$M"; : > "$CALLS"
  eval "$3"
  { echo 'say() { echo "SAY: $*"; }'; echo "M='$M' C=img PKG=img BM=bm ALOG=$T/alog MLOG=$T/mlog MP="; block "$1"; echo 'echo "MOUNTED-LIVE"'; } > "$T/s.sh"
  out=$(bash "$T/s.sh" 2>&1); rc=$?
  local got=ok; echo "$out" | grep -q MOUNTED-LIVE || got=fail
  local res=PASS
  [ "$got" = "$4" ] || res=FAIL
  IFS=';' read -r -a pats <<< "$5"
  for pt in "${pats[@]}"; do
    [ -z "$pt" ] && continue
    local want=${pt##*=} pat=${pt%=*}
    [ "$(grep -c -- "$pat" "$CALLS")" = "$want" ] || { res=FAIL; echo "   calls '$pat' = $(grep -c -- "$pat" "$CALLS"), want $want"; }
  done
  [ $res = PASS ] || fail=1
  echo "$res $1 $2: $got (rc $rc) $(echo "$out" | grep SAY | head -1)"
}
for L in play-t1.sh play-pkg.sh; do
  run $L fresh   ''                                                         ok   'bm mount=1;fusermount3=0'
  run $L live    'mkdir -p $M/sce_sys; echo x > $M/sce_sys/param.json; touch $M/.mounted' ok 'bm mount=0;fusermount3=0'
  run $L dead    'touch $M/.mounted'                                        ok   'bm mount=1;fusermount3 -u=1'
  run $L stuck   'touch $M/.mounted; export FUSER_STUCK=1'                  fail 'bm mount=0;fusermount3=2'
  unset FUSER_STUCK
done
[ $fail = 0 ] && echo "PASS (all cases)" || { echo "FAIL"; exit 1; }
