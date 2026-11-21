#!/usr/bin/env bash
# BC5 exp 0438 (tag cpy438): the shim's offline test, on the box in the ubuntu distrobox (gcc, glibc; no title, no GPU).
# A dummy program, built with frame pointers, copies 1 MiB from a named function (big_copy_here) through memcpy and
# memmove and 1 KiB once (below the bar); under LD_PRELOAD the record must show 2 copies of 1048576 bytes, from the
# thread "cpyworker", and big_copy_here in the frames (addr2line on the dummy). Then the dummy without CPY438_OUT: no file.
# usage: bash test_cpy438.sh <dir with cpy438.c>
set -eu
D=${1:?dir}; T=$(mktemp -d "$D/t.XXXX")
gcc -O2 -fno-omit-frame-pointer -fPIC -shared -o "$T/cpy438.so" "$D/cpy438.c" -ldl -lpthread
cat > "$T/dummy.c" << 'EOF'
#define _GNU_SOURCE
#include <pthread.h>
#include <stdlib.h>
#include <string.h>
#include <sys/prctl.h>
static char a[1 << 20], b[1 << 20];
__attribute__((noinline)) void big_copy_here(size_t n) { memcpy(a, b, n); memmove(a + 1, a, n - 1); }
static void* th(void* x) { (void)x; prctl(PR_SET_NAME, "cpyworker"); big_copy_here(sizeof(a)); char s[1024], t[1024]; memcpy(s, t, sizeof(s)); return 0; }
int main(void) { pthread_t t; pthread_create(&t, 0, th, 0); pthread_join(t, 0); return 0; }
EOF
gcc -O1 -fno-omit-frame-pointer -fno-builtin -o "$T/dummy" "$T/dummy.c" -lpthread
CPY438_OUT="$T/out" LD_PRELOAD="$T/cpy438.so" "$T/dummy"
f=$(ls "$T"/out.*.txt)
cat "$f"
n=$(grep -c ' cpyworker 1048575\| cpyworker 1048576' "$f" || true)
fr=$(grep ' cpyworker 104857' "$f" | head -1 | cut -d' ' -f7-)
hit=0
for a in $fr; do addr2line -f -e "$T/dummy" "$(printf '0x%x' $((0x$a - 0x$(grep -m1 "$T/dummy" "$(ls "$T"/out.*.maps)" | cut -d- -f1) )))" 2> /dev/null | head -1 | grep -q big_copy_here && hit=1; done
CPY438_OUT= LD_PRELOAD="$T/cpy438.so" "$T/dummy"
extra=$(ls "$T" | grep -c '^out\.' || true)
echo "records of the 1-MiB copies: $n (want 2); big_copy_here in the frames: $hit (want 1); files $extra (want 2: one run's txt + maps)"
[ "$n" = 2 ] && [ "$hit" = 1 ] && [ "$extra" = 2 ] && echo "test_cpy438 PASS" || echo "test_cpy438 FAIL"
rm -rf "$T"
