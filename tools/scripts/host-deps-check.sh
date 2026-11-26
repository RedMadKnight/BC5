#!/usr/bin/env bash
# host-deps-check.sh: the build stays in the `ubuntu` distrobox, the emulator and bc5-mount run on the host
# (2026-11-24). Checks, ON THE HOST, that a binary built in the container needs nothing the host does not give:
#   1. ldd: no "not found", and every library from the host's own /usr/lib64 or /lib64 (none from a container path,
#      ~/.linuxbrew or the build tree);
#   2. symbol versions: the highest GLIBC_ needed <= the host's glibc, the highest GLIBCXX_ / CXXABI_ needed <= what
#      the host's libstdc++ defines (a container update to a newer glibc than the host's fails here, loudly);
#   3. libraries the binary opens at run time (SDL is linked in statically and dlopens its backends): the ones BC5 uses
#      (Vulkan, Wayland, xkbcommon, EGL/gbm, PulseAudio, D-Bus, udev) must be known to the host's ldconfig; the
#      optional rest (jack, sndio, renderdoc, the GLES1 names, X11 extras) are listed when missing, not failed.
# usage (on the host, not in a container): bash host-deps-check.sh <binary>...      exit 0 = every binary passes
set -u
export LC_ALL=C
if [ -e /run/.containerenv ] || [ -e /.dockerenv ]; then echo "host-deps-check: runs inside a container: run it on the host"; exit 2; fi
[ $# -ge 1 ] || { echo "usage: host-deps-check.sh <binary>..."; exit 2; }
for t in ldd objdump strings ldconfig; do command -v "$t" > /dev/null || [ -x "/usr/sbin/$t" ] || { echo "host-deps-check: no $t on this host"; exit 2; }; done
LDC=$(command -v ldconfig || echo /usr/sbin/ldconfig)
host_glibc=$(getconf GNU_LIBC_VERSION | awk '{print $2}')
STDCXX=$(ls /usr/lib64/libstdc++.so.6 2> /dev/null || ls /lib64/libstdc++.so.6 2> /dev/null)
[ -n "$host_glibc" ] && [ -n "$STDCXX" ] || { echo "host-deps-check: cannot read the host's glibc / libstdc++"; exit 2; }
host_cxx=$(strings "$STDCXX" | grep -oE '^GLIBCXX_[0-9.]+$' | sort -Vu | tail -1)
host_abi=$(strings "$STDCXX" | grep -oE '^CXXABI_[0-9.]+$' | sort -Vu | tail -1)
REQUIRED="libvulkan.so.1 libwayland-client.so.0 libwayland-cursor.so.0 libwayland-egl.so.1 libxkbcommon.so.0 libEGL.so.1 libgbm.so.1 libpulse.so.0 libdbus-1.so.3 libudev.so.1"
known=$("$LDC" -p | awk '{print $1}' | sort -u)
le() { [ "$(printf '%s\n%s\n' "$1" "$2" | sort -V | head -1)" = "$1" ]; } # $1 <= $2
fail=0
echo "host: glibc $host_glibc, libstdc++ $host_cxx $host_abi, kernel $(uname -r)"
for b in "$@"; do
    bad=0
    [ -f "$b" ] || { echo "FAIL $b: no such file"; fail=1; continue; }
    out=$(ldd "$b" 2>&1) || { echo "FAIL $b: ldd: $out"; fail=1; continue; }
    nf=$(printf '%s\n' "$out" | grep -c 'not found')
    [ "$nf" = 0 ] || { echo "FAIL $b: $nf libraries not found: $(printf '%s\n' "$out" | grep 'not found' | awk '{print $1}' | tr '\n' ' ')"; bad=1; }
    foreign=$(printf '%s\n' "$out" | awk '$2 == "=>" && $3 ~ /^\// {print $3}' | grep -vE '^/(usr/)?lib64/' || true)
    [ -z "$foreign" ] || { echo "FAIL $b: libraries from outside the host's /usr/lib64: $(echo $foreign)"; bad=1; }
    syms=$(objdump -T "$b" 2> /dev/null)
    need_glibc=$(printf '%s\n' "$syms" | grep -oE 'GLIBC_[0-9.]+' | sed 's/GLIBC_//' | sort -Vu | tail -1)
    need_cxx=$(printf '%s\n' "$syms" | grep -oE 'GLIBCXX_[0-9.]+' | sort -Vu | tail -1)
    need_abi=$(printf '%s\n' "$syms" | grep -oE 'CXXABI_[0-9.]+' | sort -Vu | tail -1)
    [ -z "$need_glibc" ] || le "$need_glibc" "$host_glibc" || { echo "FAIL $b: needs GLIBC_$need_glibc, the host has $host_glibc"; bad=1; }
    [ -z "$need_cxx" ] || le "${need_cxx#GLIBCXX_}" "${host_cxx#GLIBCXX_}" || { echo "FAIL $b: needs $need_cxx, the host has $host_cxx"; bad=1; }
    [ -z "$need_abi" ] || le "${need_abi#CXXABI_}" "${host_abi#CXXABI_}" || { echo "FAIL $b: needs $need_abi, the host has $host_abi"; bad=1; }
    dl=$(strings "$b" | grep -E '^lib[A-Za-z0-9_+-]+\.so(\.[0-9]+)*$' | sort -u)
    miss_req=""; miss_opt=""
    for l in $dl; do
        grep -qxF "$l" <<< "$known" && continue  # a here-string: grep -q ends early without a broken pipe
        case " $REQUIRED " in *" $l "*) miss_req="$miss_req $l" ;; *) miss_opt="$miss_opt $l" ;; esac
    done
    [ -z "$miss_req" ] || { echo "FAIL $b: run-time libraries BC5 uses are missing on the host:$miss_req"; bad=1; }
    md=$(md5sum < "$b" | cut -c1-8)
    if [ $bad = 0 ]; then
        echo "PASS $b ($md): $(printf '%s\n' "$out" | grep -c '=>') libraries from /usr/lib64, GLIBC_${need_glibc:-none} ${need_cxx:-} ${need_abi:-}; dlopen names $(printf '%s\n' "$dl" | grep -c .)${miss_opt:+, optional ones not on the host:$miss_opt}"
    else
        fail=1
    fi
done
exit $fail
