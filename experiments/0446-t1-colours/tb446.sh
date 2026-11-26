#!/usr/bin/env bash
# BC5 exp 0446: the backend's unit tests (reimpl first) built from the shared builds' export with both toolchains.
#   tb446.sh build   four build dirs under ~/bc5-work/exp0446/tb/: host, host-san (UBSan+ASan), host-pat
#                    (-ftrivial-auto-var-init=pattern), cont (the ubuntu distrobox's clang, as before bake H)
#   tb446.sh test    runs bc5_backend_tests in each, logs in ~/bc5-work/exp0446/tb/<v>.test.log
# No emulator, no GPU. Run only with an exp 0446 BOX-LOCK line (the caller holds it).
set -uo pipefail
export LC_ALL=C
W=$HOME/bc5-work; X=$W/exp0446/tb; E=$W/d19/export/backend; T=$HOME/bc5-toolchain
CATCH=$W/exp0442/b2/catch2-3.7.1
AGCMOD=${AGCMOD:-}
mkdir -p "$X"
conf() { # $1 variant, $2 extra flags
    echo "-DCMAKE_BUILD_TYPE=RelWithDebInfo -DCMAKE_C_COMPILER=clang -DCMAKE_CXX_COMPILER=clang++ -DBC5_WITH_AMDGPU=ON \
-DBC5_BUILD_TESTS=ON -DBC5_REIMPL_NAME_TABLES=anyps5 -DFETCHCONTENT_SOURCE_DIR_CATCH2=$CATCH -DFETCHCONTENT_FULLY_DISCONNECTED=ON \
-DCMAKE_CXX_FLAGS=\"$2\" -DCMAKE_C_FLAGS=\"$2\" -DCMAKE_EXE_LINKER_FLAGS=\"$2\""
}
build_host() { # $1 variant, $2 flags
    ( . "$T/env.sh" && eval nice -n 10 cmake -S "$E" -B "$X/$1" -G Ninja $(conf "$1" "$2") && nice -n 10 cmake --build "$X/$1" --target bc5_backend_tests -j2 ) > "$X/$1.build.log" 2>&1
    echo "$1: build rc $?"
}
build_cont() {
    distrobox enter ubuntu -- bash -c "$(printf 'cd %q && eval nice -n 10 cmake -S %q -B %q -G Ninja %s && nice -n 10 cmake --build %q --target bc5_backend_tests -j2' "$X" "$E" "$X/cont" "$(conf cont "")" "$X/cont")" > "$X/cont.build.log" 2>&1 < /dev/null
    echo "cont: build rc $?"
}
case "${1:-}" in
  build)
    build_host host ""
    build_cont
    build_host host-pat "-ftrivial-auto-var-init=pattern"
    build_host host-san "-fsanitize=undefined,address -fno-omit-frame-pointer -fno-sanitize-recover=undefined" ;;
  test)
    for v in host host-san host-pat; do
        ( . "$T/env.sh"; cd "$X/$v" && ASAN_OPTIONS=detect_leaks=0 UBSAN_OPTIONS=print_stacktrace=1 BC5_TEST_AGC_MODULE=$AGCMOD timeout 900 ./bc5_backend_tests --reporter compact ) > "$X/$v.test.log" 2>&1
        echo "$v: tests rc $? ($(tail -1 "$X/$v.test.log" | cut -c1-120))"
    done
    distrobox enter ubuntu -- bash -c "cd $X/cont && BC5_TEST_AGC_MODULE=$AGCMOD timeout 900 ./bc5_backend_tests --reporter compact" > "$X/cont.test.log" 2>&1 < /dev/null
    echo "cont: tests rc $? ($(tail -1 "$X/cont.test.log" | cut -c1-120))" ;;
  *) echo "usage: tb446.sh build|test"; exit 2 ;;
esac
