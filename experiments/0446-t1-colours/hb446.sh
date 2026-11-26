#!/usr/bin/env bash
# exp 0446 (tag hb446, 2026-11-26): halve exp 0439's priv61 (f21bfa76), which hangs the second title at ~51 s with every
# switched word off (x446n4N, x446zZ), into its two sides, both linked from the shared normal build's own compile and link
# commands (a private copy of exp 0439's build0438.py; nothing shared is written; no lock line, nice 19, ionice idle):
#   A  the shared unit objects as built + priv61's backend archive (9bd790af)
#   B  priv61's unit files (d2/priv61/src/kyty, 11 units) + the shared backend archive (+ two diagnostic stubs)
#   A1 the shared archive with priv61's direct.cpp.o only; A2 with its policy, full_state and state_stack objects only
#   hb446.sh A|B|A1|A2 ...    (on the box, from ~/bc5-work/exp0446; waits for an empty lock and no emulator first)
set -u
export LC_ALL=C LANGUAGE=C
W=$HOME/bc5-work; X=$W/exp0446; H=$X/hb; P=$W/exp0439/d2/priv61; NB=$W/kytyplus-build
UNITS="src/libs/bc5LleAgc.cpp src/graphics/presentation/videoOut.cpp src/libs/ajm.cpp src/main.cpp src/kernel/pthread.cpp src/libs/libAmpr.cpp src/graphics/presentation/window/window.cpp src/libs/controller.cpp src/libs/videoDec2Decoder.cpp src/libs/libVideoDec2.cpp src/kernel/memory.cpp"
m8() { md5sum < "$1" 2> /dev/null | cut -c1-8; }
stop() { echo "hb446 STOP: $*"; exit 1; }
. "$HOME/bc5-toolchain/env.sh" || stop "toolchain env"
[ "$(m8 "$P/normal/kyty_emulator")" = f21bfa76 ] && [ "$(m8 "$P/backend/libbc5_backend.a")" = 9bd790af ] || stop "priv61 is not f21bfa76 / 9bd790af"
[ "$(m8 "$NB/src/kyty_emulator")" = 5727b07f ] || stop "the shared normal is not 5727b07f"
for u in $UNITS; do [ -f "$P/src/kyty/$u" ] || stop "priv61 has no $u"; done
mkdir -p "$H" && cp "$W/exp0439/k439/build0438.py" "$H/build0438.py" || stop "copy build0438.py"
t0=$(date +%s); while { [ -s "$W/BOX-LOCK" ] || pgrep '^kyty_emulator' > /dev/null; } && [ $(( $(date +%s) - t0 )) -lt 3600 ]; do sleep 20; done
{ [ -s "$W/BOX-LOCK" ] || pgrep '^kyty_emulator' > /dev/null; } && stop "box busy for an hour"
(cd "$NB" && ninja -t compdb -x) > "$H/compdb-normal.json" 2> "$H/compdb.err" < /dev/null || stop "compdb"
for a in "$@"; do
    o=$H/$a; rm -rf "$o"; mkdir -p "$o"
    case "$a" in
        A) args="ARCHIVE=$P/backend/libbc5_backend.a" ;;
        B) # the shared archive plus two stubs for priv61's diagnostic entry points, returning what priv61's backend returns
           # with them off (bc5_sr439c_arena: -19, no census device; bc5_fn439_write: -1, fn439 off)
           mkdir -p "$o/stub" && cat > "$o/stub/hb446_stub.cpp" << 'STUB'
#include <cstdint>
// exp 0446 (tag hb446): stubs for half B (priv61's units on the shared backend); the values priv61's backend returns when off
extern "C" int bc5_sr439c_arena(std::uint64_t, void**, std::uint64_t*) { return -19; }
extern "C" int bc5_fn439_write(const char*) { return -1; }
STUB
           "$CXX" -O2 -fPIC -c "$o/stub/hb446_stub.cpp" -o "$o/stub/hb446_stub.o" && cp "$W/backend-ubuntu/libbc5_backend.a" "$o/stub/libbc5_backend.a"                && ar r "$o/stub/libbc5_backend.a" "$o/stub/hb446_stub.o" || stop "stub archive"
           args="ARCHIVE=$o/stub/libbc5_backend.a $UNITS" ;;
        A1|A2) # the shared archive with priv61's direct.cpp.o alone (A1) or its policy/full_state/state_stack objects (A2)
           [ "$a" = A1 ] && mem="direct.cpp.o" || mem="policy.cpp.o full_state.cpp.o state_stack.cpp.o"
           mkdir -p "$o/arch/m" && cp "$W/backend-ubuntu/libbc5_backend.a" "$o/arch/libbc5_backend.a" || stop "copy archive"
           for m in $mem; do (cd "$o/arch/m" && ar p "$P/backend/libbc5_backend.a" "$m" > "$m" && ar r "$o/arch/libbc5_backend.a" "$m") || stop "member $m"; done
           for m in $(ar t "$o/arch/libbc5_backend.a"); do x=$(ar p "$o/arch/libbc5_backend.a" "$m" | md5sum | cut -c1-8)
               case " $mem " in *" $m "*) y=$(ar p "$P/backend/libbc5_backend.a" "$m" | md5sum | cut -c1-8) ;; *) y=$(ar p "$W/backend-ubuntu/libbc5_backend.a" "$m" | md5sum | cut -c1-8) ;; esac
               [ "$x" = "$y" ] || stop "$a: member $m is not the intended one"; done
           echo "$a: archive $(m8 "$o/arch/libbc5_backend.a"), priv61 members [$mem]"
           args="ARCHIVE=$o/arch/libbc5_backend.a" ;;
        *) stop "arm $a" ;;
    esac
    echo "$(date +%T) hb446 $a: start"
    # shellcheck disable=SC2086
    nice -n 19 ionice -c 3 python3 -I "$H/build0438.py" emu "$H/compdb-normal.json" "$P/src/kyty" "$o" "$NB" "$o/kyty_emulator" $args > "$o/build.out" 2>&1 < /dev/null
    rc=$?
    echo "$(date +%T) hb446 $a: rc $rc, errors $(grep -c 'error:' "$o/build.out"), undefined $(grep -c 'undefined' "$o/build.out")"
    grep -n "error:\|undefined reference\|COMPILE FAILED" "$o/build.out" | head -12
    [ "$rc" = 0 ] && [ -x "$o/kyty_emulator" ] && echo "$(date +%T) hb446 $a: binary $(m8 "$o/kyty_emulator")" && m8 "$o/kyty_emulator" > "$o/binary.md5"
done
[ "$(m8 "$NB/src/kyty_emulator")" = 5727b07f ] && echo "shared normal unchanged"
