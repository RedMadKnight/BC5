#!/usr/bin/env bash
# BC5 experiment 0380: slot0380m.sh's exit against a mock distrobox, laptop only: no ssh, no GPU, no build. A throwaway
# HOME holds a stand-in archive and lock; each case makes one step fail in one way and must end non-zero, naming the step.
# usage: bash test-slot0380m.sh
set -u
HERE=$(cd "$(dirname "$0")" && pwd); S=$HERE/slot0380m.sh
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
mkdir -p "$T/bin" "$T/home/bc5-work/exp0380/main-check/x" "$T/home/bc5-work/exp0380/other"
echo stand-in > "$T/home/bc5-work/exp0380/main-check/x/f"
tar -cf "$T/home/bc5-work/exp0380/main-check/main-backend.tar" -C "$T/home/bc5-work/exp0380/main-check/x" f
rm -rf "$T/home/bc5-work/exp0380/main-check/x"
cp "$T/home/bc5-work/exp0380/main-check/main-backend.tar" "$T/home/bc5-work/exp0380/other/"
MD5=$(md5sum < "$T/home/bc5-work/exp0380/main-check/main-backend.tar" | cut -d' ' -f1)
echo "top exp 0380 | test" > "$T/home/bc5-work/BOX-LOCK"
printf '#!/bin/sh\nexit 1\n' > "$T/bin/pgrep"
# MOCK names the step that misbehaves, MODE how: an rc, "none" (rc 0, Catch2's "No tests ran"), or "mute" (rc 0, no line)
cat > "$T/bin/distrobox" <<'MOCK'
#!/bin/bash
c=$6   # enter ubuntu -- sh -c <command>
case "$c" in
  *cmake*) s=build ;;
  *"'["*) s=$(printf %s "$c" | sed -E 's/.*\[([a-z_]+)\].*/\1/') ;;
  *bc5_backend_tests*) s=tests ;;
  *"direct-selftest --cp-check"*) s=selftest-checks ;;
  *direct-selftest*) s=selftest-plain ;;
  *) echo "unknown command: $c"; exit 99 ;;
esac
case "$c" in *--submit*) echo "SUBMIT PASSED"; exit 98 ;; esac
if [ "${MOCK:-}" = "$s" ]; then
  case "$MODE" in
    none) echo "No tests ran"; exit 0 ;;
    mute) echo "something else"; exit 0 ;;
    *) echo "mock failure"; exit "$MODE" ;;
  esac
fi
case "$s" in
  build) ;;
  selftest-*) echo "direct-selftest: nothing done without --submit" ;;
  *) echo "All tests passed (10 assertions in 1 test case)" ;;
esac
MOCK
chmod +x "$T/bin/pgrep" "$T/bin/distrobox"
BAD=0
run() { # <want rc 0 or not> <text wanted> <case name> [env...]
  local want=$1 text=$2 name=$3 out rc; shift 3
  # shellcheck disable=SC2086
  out=$(env HOME="$T/home" PATH="$T/bin:$PATH" "$@" bash "$S" "${ARG:-$MD5}" ${REST:-} 2>&1); rc=$?
  if { [ "$want" = 0 ] && [ "$rc" = 0 ]; } || { [ "$want" != 0 ] && [ "$rc" != 0 ]; } && printf '%s\n' "$out" | grep -qF -- "$text"; then echo "ok   $name (rc $rc)"
  else echo "BAD  $name (rc $rc): $out"; BAD=1; fi
}
run 0 "done: all passed" "everything passes"
for s in build tests indirect_check zero_skip selftest-plain selftest-checks; do run 1 "FAIL: $s rc 9" "$s rc 9" MOCK=$s MODE=9; done
for s in tests indirect_check zero_skip; do
  run 1 "ran no tests" "$s says No tests ran, rc 0" MOCK=$s MODE=none
  run 1 "ran no tests" "$s prints no summary, rc 0" MOCK=$s MODE=mute
done
for s in selftest-plain selftest-checks; do run 1 "did not report doing nothing" "$s silent, rc 0" MOCK=$s MODE=mute; done
TAGS="other draw_args acb_restore indirect_check zero_skip"
REST=$TAGS run 0 "acb_restore rc 0" "another directory and four subsets"
for s in draw_args acb_restore; do
  REST=$TAGS run 1 "FAIL: $s rc 9" "$s rc 9" MOCK=$s MODE=9
  REST=$TAGS run 1 "ran no tests" "$s says No tests ran, rc 0" MOCK=$s MODE=none
done
ARG=0123 run 1 "not 0123" "wrong archive md5"
: > "$T/home/bc5-work/BOX-LOCK"; run 1 "not this session's" "lock not ours"
exit $BAD
