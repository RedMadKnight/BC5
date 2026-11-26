#!/usr/bin/env bash
# bc5-toolchain.sh: the private build toolchain on the host (the maintainer's order of 2026-11-24: "build a compile
# environment in the system without the distro"). Nothing is installed into the system: no rpm-ostree layering, no
# Homebrew library in the link, no sudo. Everything lives in $T (default ~/bc5-toolchain):
#   - the compiler: clang/lld 21.1.8 from LLVM's own release (the compiler the container builds used, Ubuntu clang
#     21.1.8, so a host-built binary differs from a container-built one only by its environment); the host's GCC 16 is
#     recorded, not used (KytyPlus's GCC path builds with RTTI, static libstdc++ and GNU ld: another experiment);
#   - the host's own C library and kernel headers (glibc-devel, libstdc++-devel, kernel-headers are on the image);
#   - a sysroot of -devel content: the Fedora 45 (and Terra, for Mesa) RPMs whose version-release equals the installed
#     runtime library's (rpm -q), extracted with rpm2cpio, never installed. Its unversioned lib*.so links point at the
#     host's real /usr/lib64 libraries, its .pc files at the sysroot's headers;
#   - build tools: cmake 4.2.3, ninja 1.13.2 (upstream releases, sha256 recorded), glslang (its Fedora RPM, run against
#     the host's spirv-tools-libs), wayland-scanner (from wayland-devel), Rust 1.93.1 through rustup (RUSTUP_HOME and
#     CARGO_HOME in $T);
#   - $T/env.sh: what a build sources (PATH, CC/CXX, PKG_CONFIG_PATH, CMAKE_PREFIX_PATH, cargo/rustup homes).
# A re-run after an image update rebuilds the sysroot when an installed NVR changed (the sysroot is named by the hash of
# its NVR list; env.sh points at the current one). host-deps-check.sh stays the gate for what gets built.
#   bc5-toolchain.sh check    the host side only: compiler base present, the NVRs it would fetch; no network, no write
#   bc5-toolchain.sh fetch    the downloads only, each verified (published sha256, or rpm -K against the host's imported
#                             Fedora / Terra keys, plus Terra's primary.xml sha256); $T/dl/MANIFEST lists them; nothing unpacked
#   bc5-toolchain.sh          everything (downloads: see the list printed by `check`)
set -euo pipefail
export LC_ALL=C
T=${BC5_TOOLCHAIN:-$HOME/bc5-toolchain}
FED=${BC5_FEDORA_MIRROR:-https://dl.fedoraproject.org/pub/fedora/linux}
TERRA=${BC5_TERRA:-https://repos.fyralabs.com/terra45-mesa}  # Terra keeps Mesa in its own repo (key "Terra 45 - Mesa")
CMAKE_V=4.2.3 NINJA_V=1.13.2 LLVM_V=21.1.8 RUST_V=1.93.1
say() { echo "bc5-toolchain: $*"; }
die() { echo "bc5-toolchain: $*" >&2; exit 1; }
[ -e /run/.containerenv ] || [ -e /.dockerenv ] && die "runs inside a container: run it on the host"
[ "$(id -u)" != 0 ] || die "run it as your user, not root"

# ---- the -devel RPMs. MATCH rows: <devel package> <installed runtime package whose version-release it must equal>.
# Taken from what the shared builds include today (ninja -t deps of kytyplus-build, -lean and backend-ubuntu,
# 2026-11-24: 1,293 system headers in ~30 Ubuntu packages, mapped to their Fedora names).
MATCH="glib2-devel:glib2 ibus-devel:ibus-libs pipewire-devel:pipewire-libs
pipewire-jack-audio-connection-kit-devel:pipewire-jack-audio-connection-kit-libs pulseaudio-libs-devel:pulseaudio-libs
alsa-lib-devel:alsa-lib dbus-devel:dbus-libs wayland-devel:libwayland-client libdrm-devel:libdrm libX11-devel:libX11
libxcb-devel:libxcb libXau-devel:libXau libXext-devel:libXext libXrender-devel:libXrender libXrandr-devel:libXrandr
libXi-devel:libXi libXfixes-devel:libXfixes libXcursor-devel:libXcursor libXScrnSaver-devel:libXScrnSaver
libglvnd-devel:libglvnd libglvnd-core-devel:libglvnd libxkbcommon-devel:libxkbcommon opus-devel:opus xz-devel:xz-libs
systemd-devel:systemd-libs libsamplerate-devel:libsamplerate libdecor-devel:libdecor mesa-libgbm-devel:mesa-libgbm"
# PINNED rows: no runtime package to match (headers or a build tool only).
PINNED="xorg-x11-proto-devel-2025.1-3.fc45.noarch glslang-16.3.0-2.fc45.x86_64"
# The host's compiler base (on the image; recorded, checked, never fetched).
BASE="gcc gcc-c++ glibc-devel libstdc++-devel kernel-headers binutils make spirv-tools-libs expat libffi"

nvr_list() { # every RPM file name the sysroot needs, from the installed NVRs
    local e d r vr
    for e in $MATCH; do d=${e%%:*}; r=${e##*:}
        vr=$(rpm -q --qf '%{VERSION}-%{RELEASE}' "$r.x86_64" 2> /dev/null) || die "$r is not installed on this host"
        echo "$d-$vr.x86_64.rpm"
    done
    for e in $PINNED; do echo "$e.rpm"; done
}
url_of() { # Fedora: the release tree, then updates; Terra (Mesa) through its primary metadata
    local f=$1 c p
    case "$f" in mesa-*)
        [ -s "$T/dl/terra-primary.xml" ] || return 1
        # Terra's file names carry the epoch (mesa-libgbm-devel-1:26.3.1-2.fc45.x86_64.rpm): compare without it
        p=$(grep -oE 'location href="[^"]*"' "$T/dl/terra-primary.xml" | cut -d'"' -f2 | while read -r h; do
            [ "$(basename "$h" | sed -E 's/-[0-9]+:/-/')" = "$f" ] && { echo "$h"; break; }; done)
        [ -n "$p" ] && echo "$TERRA/$p"; return ;;
    esac
    c=$(printf '%s' "${f:0:1}" | tr 'A-Z' 'a-z')
    for p in releases/45/Everything/x86_64/os/Packages updates/45/Everything/x86_64/Packages; do
        curl -sfIL --max-time 20 "$FED/$p/$c/$f" > /dev/null && { echo "$FED/$p/$c/$f"; return 0; }
    done
    return 1
}
check() {
    say "host: $(rpm -E '%{fedora}' 2> /dev/null | sed 's/^/Fedora /'), kernel $(uname -r), image $(rpm-ostree status --booted --json 2> /dev/null | grep -oE '"version" *: *"[^"]+"' | head -1 | cut -d'"' -f4)"
    local p bad=0
    for p in $BASE; do rpm -q "$p.x86_64" > /dev/null 2>&1 || rpm -q "$p" > /dev/null 2>&1 || { say "MISSING on the image: $p"; bad=1; }; done
    say "compiler base: $(gcc --version | head -1); $(ld --version | head -1); glibc-devel $(rpm -q --qf '%{VERSION}-%{RELEASE}' glibc-devel.x86_64)"
    say "the sysroot would hold:"; nvr_list | sed 's/^/  /'
    say "downloads: cmake-$CMAKE_V-linux-x86_64.tar.gz (58 MB), ninja-linux.zip v$NINJA_V (0.1 MB), LLVM-$LLVM_V-Linux-X64.tar.xz (2.0 GB),"
    say "  rustup-init (21 MB) + Rust $RUST_V minimal (~200 MB), $(nvr_list | wc -l) RPMs (~12 MB), Terra's primary metadata, bc5-mount's crates (cargo fetch, --locked)"
    return $bad
}
[ "${1:-all}" = check ] && { check; exit $?; }
case "${1:-all}" in all | fetch) ;; *) die "usage: bc5-toolchain.sh [check|fetch|all]" ;; esac
check || die "the compiler base is incomplete on this image (see above)"

MODE=${1:-all}
mkdir -p "$T/dl/rpms" "$T/bin"
M=$T/dl/MANIFEST  # every file fetched: sha256, source, how it was verified
note() { grep -qF "  $2  " "$M" 2> /dev/null || printf '%s  %s  %s  %s\n' "$1" "$2" "$3" "$4" >> "$M"; }
get() { # url file: download once (resumable), into $T/dl
    [ -s "$T/dl/$2" ] && return 0
    nice -n 19 ionice -c 3 curl -fL --retry 3 --max-time 7200 -C - -o "$T/dl/$2.part" "$1" || die "download failed: $1"
    mv -f "$T/dl/$2.part" "$T/dl/$2"
}
must() { # file published-sha256 source how
    local x; x=$(nice -n 19 ionice -c 3 sha256sum < "$T/dl/$1" | cut -d' ' -f1)
    [ -n "$2" ] || die "$1: no published sha256 to check against"
    [ "$x" = "$2" ] || die "$1: sha256 $x, not the published $2"
    note "$x" "$1" "$3" "$4"
}
gh_digest() { # repo tag asset: the sha256 GitHub records for a release asset
    curl -fsL --max-time 60 "https://api.github.com/repos/$1/releases/tags/$2" | python3 -I -c '
import json, sys
for a in json.load(sys.stdin).get("assets", []):
    if a.get("name") == sys.argv[1] and str(a.get("digest", "")).startswith("sha256:"):
        print(a["digest"][7:]); break' "$3"
}
# ---- 1. downloads, each verified before it is used
cm=cmake-$CMAKE_V-linux-x86_64.tar.gz
get "https://github.com/Kitware/CMake/releases/download/v$CMAKE_V/cmake-$CMAKE_V-SHA-256.txt" "cmake-$CMAKE_V-SHA-256.txt"
get "https://github.com/Kitware/CMake/releases/download/v$CMAKE_V/$cm" "$cm"
must "$cm" "$(grep " $cm\$" "$T/dl/cmake-$CMAKE_V-SHA-256.txt" | cut -d' ' -f1)" "github.com/Kitware/CMake v$CMAKE_V" "Kitware's cmake-$CMAKE_V-SHA-256.txt"
nz=ninja-$NINJA_V-linux.zip
get "https://github.com/ninja-build/ninja/releases/download/v$NINJA_V/ninja-linux.zip" "$nz"
must "$nz" "$(gh_digest ninja-build/ninja "v$NINJA_V" ninja-linux.zip)" "github.com/ninja-build/ninja v$NINJA_V" "the release asset's GitHub sha256 digest"
ll=LLVM-$LLVM_V-Linux-X64.tar.xz
get "https://github.com/llvm/llvm-project/releases/download/llvmorg-$LLVM_V/$ll" "$ll"
must "$ll" "$(gh_digest llvm/llvm-project "llvmorg-$LLVM_V" "$ll")" "github.com/llvm/llvm-project llvmorg-$LLVM_V" "the release asset's GitHub sha256 digest"
get "https://static.rust-lang.org/rustup/dist/x86_64-unknown-linux-gnu/rustup-init.sha256" rustup-init.sha256
get "https://static.rust-lang.org/rustup/dist/x86_64-unknown-linux-gnu/rustup-init" rustup-init
must rustup-init "$(cut -d' ' -f1 "$T/dl/rustup-init.sha256")" "static.rust-lang.org rustup" "rustup-init.sha256 (the toolchain itself: rustup checks each component)"
# Terra's metadata: the Mesa RPM's location and its checksum
rm -f "$T/dl/terra-repomd.xml"; get "$TERRA/repodata/repomd.xml" terra-repomd.xml
pr=$(grep -oE 'href="[^"]*primary\.xml[^"]*"' "$T/dl/terra-repomd.xml" | head -1 | cut -d'"' -f2)
rm -f "$T/dl/terra-primary.raw"; get "$TERRA/$pr" terra-primary.raw
case "$pr" in *.gz) gzip -dc "$T/dl/terra-primary.raw" ;; *.zst) zstd -qdc "$T/dl/terra-primary.raw" ;; *.xz) xz -dc "$T/dl/terra-primary.raw" ;; *) cat "$T/dl/terra-primary.raw" ;; esac > "$T/dl/terra-primary.xml"
terra_sum() { python3 -I -c '
import re, sys, xml.etree.ElementTree as E
ns = {"c": "http://linux.duke.edu/metadata/common"}
for p in E.parse(sys.argv[1]).getroot().findall("c:package", ns):
    if re.sub(r"-[0-9]+:", "-", p.find("c:location", ns).get("href").rsplit("/", 1)[-1]) == sys.argv[2]:
        c = p.find("c:checksum", ns); print(c.get("type"), c.text); break' "$T/dl/terra-primary.xml" "$1"; }
LIST=$(nvr_list)
for f in $LIST; do
    u=$(url_of "$f") || die "no mirror holds $f"
    get "$u" "rpms/$f"
    k=$(rpm -K "$T/dl/rpms/$f" 2>&1); case "$k" in *"digests signatures OK"*) ;; *) die "rpm -K $f: $k" ;; esac
    how="rpm -K: digests and signature OK against the host's imported key"
    case "$f" in mesa-*) read -r ty cs <<< "$(terra_sum "$f")"; [ "$ty" = sha256 ] && [ "$cs" = "$(sha256sum < "$T/dl/rpms/$f" | cut -d' ' -f1)" ] || die "$f: not the sha256 of Terra's primary.xml ($ty $cs)"; how="$how; sha256 = Terra's primary.xml" ;; esac
    note "$(sha256sum < "$T/dl/rpms/$f" | cut -d' ' -f1)" "rpms/$f" "$u" "$how"
done
say "fetched and verified: $(grep -c . "$M") files, $(du -sh "$T/dl" | cut -f1) in $T/dl; manifest $M"
[ "$MODE" = fetch ] && exit 0
# ---- 2. install into $T (unpack, rustup, sysroot)
[ -x "$T/cmake-$CMAKE_V/bin/cmake" ] || { mkdir -p "$T/cmake-$CMAKE_V" && tar xzf "$T/dl/$cm" -C "$T/cmake-$CMAKE_V" --strip-components=1; }
[ -x "$T/bin/ninja" ] || python3 -I -c 'import sys, zipfile; zipfile.ZipFile(sys.argv[1]).extract("ninja", sys.argv[2])' "$T/dl/$nz" "$T/bin"
chmod +x "$T/bin/ninja"
if [ ! -x "$T/llvm-$LLVM_V/bin/clang" ]; then  # only what a build runs: the drivers, lld, binutils-like tools, clang's headers
    mkdir -p "$T/llvm-$LLVM_V"
    tar xJf "$T/dl/$ll" -C "$T/llvm-$LLVM_V" --strip-components=1 --wildcards \
        "*/bin/clang" "*/bin/clang++" "*/bin/clang-21" "*/bin/lld" "*/bin/ld.lld" "*/bin/llvm-ar" "*/bin/llvm-ranlib" \
        "*/bin/llvm-nm" "*/bin/llvm-objcopy" "*/bin/llvm-strip" "*/lib/clang/*"
fi
export RUSTUP_HOME=$T/rustup CARGO_HOME=$T/cargo
[ -x "$CARGO_HOME/bin/cargo" ] || { cp "$T/dl/rustup-init" "$T/rustup-init" && chmod +x "$T/rustup-init" && "$T/rustup-init" -y --no-modify-path --profile minimal --default-toolchain "$RUST_V"; }
"$CARGO_HOME/bin/rustup" toolchain list | grep -q "^$RUST_V" || "$CARGO_HOME/bin/rustup" toolchain install "$RUST_V" --profile minimal
ID=$(printf '%s\n' "$LIST" | sha256sum | cut -c1-12); S=$T/sysroot-$ID
if [ ! -e "$S/.done" ]; then
    rm -rf "$S.part"; mkdir -p "$S.part"
    for f in $LIST; do (cd "$S.part" && rpm2cpio "$T/dl/rpms/$f" | cpio -idm --quiet) || die "cannot extract $f"; done
    # unversioned .so links -> the host's real library; .pc files -> the sysroot's headers
    find "$S.part/usr/lib64" -maxdepth 1 -name 'lib*.so' -type l | while read -r l; do
        t=$(readlink "$l"); t=${t##*/}; [ -e "/usr/lib64/$t" ] || die "$(basename "$l") points at $t, which the host does not have"
        ln -sfn "/usr/lib64/$t" "$l"; done
    find "$S.part/usr/lib64/pkgconfig" "$S.part/usr/share/pkgconfig" -name '*.pc' 2> /dev/null | while read -r p; do
        sed -i "s#^prefix=/usr\$#prefix=$S/usr#; s#^includedir=/usr/#includedir=$S/usr/#" "$p"; done
    printf '%s\n' "$LIST" > "$S.part/NVRS"; touch "$S.part/.done"; mv -T "$S.part" "$S"
fi
ln -sfn "$S" "$T/sysroot"
# Stubs for modules that the sysroot's .pc files name ONLY under Requires.private (static links): pkgconf checks them
# even for a shared build. Their headers are not used by BC5's builds (ninja -t deps of the container builds,
# 2026-11-24: no libffi, pcre2, selinux, mount or sysprof header). Each stub: the highest version a requirer asks for,
# empty Cflags and Libs; refused if any .pc lists the module under plain Requires.
PRIV_STUBS="libffi libpcre2-8 libselinux mount sysprof-capture-4"
for m in $PRIV_STUBS; do
    pcs=$(ls "$S"/usr/lib64/pkgconfig/*.pc "$S"/usr/share/pkgconfig/*.pc 2> /dev/null)
    # shellcheck disable=SC2086
    if grep -h '^Requires:' $pcs | tr ',' '\n' | grep -qE "(^|[: ])$m( |$|>|<|=)"; then die "$m is a plain Requires of a sysroot .pc: it needs its -devel RPM, not a stub"; fi
    [ -e "$S/usr/lib64/pkgconfig/$m.pc" ] && continue
    # shellcheck disable=SC2086
    v=$(grep -h '^Requires.private:' $pcs | tr ',' '\n' | grep -oE "(^|[: ])$m *>=? *[0-9][0-9.]*" | grep -oE '[0-9][0-9.]*$' | sort -V | tail -1)
    printf 'Name: %s\nDescription: bc5-toolchain.sh stub: only a Requires.private of the sysroot (static links); no header of it is used\nVersion: %s\nCflags:\nLibs:\n' "$m" "${v:-0}" > "$S/usr/lib64/pkgconfig/$m.pc"
    grep -qF "  stub:$m.pc  " "$T/dl/MANIFEST" || printf '%s  stub:%s.pc  %s  %s\n' "-" "$m" "written by bc5-toolchain.sh" "Requires.private only, version ${v:-0}" >> "$T/dl/MANIFEST"
done
# Libraries Fedora keeps in a subdirectory, which SDL's configure looks for by name in the main one (Ubuntu's layout):
# PipeWire's JACK. Linked to the host's real library; SDL loads it at run time (SDL_JACK_SHARED), as in the container.
for e in libjack.so:/usr/lib64/pipewire-0.3/jack/libjack.so.0; do
    l=${e%%:*}; t=${e#*:}
    [ -e "$t" ] || die "the host has no $t"
    ln -sfn "$t" "$S/usr/lib64/$l"
done
find "$S/usr/lib64" -mindepth 2 -name 'lib*.so' -type l | while read -r l; do  # the -devel .so links in subdirectories too
    r=${l#"$S"}; t=$(readlink "$l"); t=${t##*/}; [ -e "$(dirname "$r")/$t" ] && ln -sfn "$(dirname "$r")/$t" "$l"; done
# glslang and wayland-scanner from the sysroot, run against the host's libraries
ln -sfn "$T/sysroot/usr/bin/glslang" "$T/bin/glslangValidator"
ln -sfn "$T/sysroot/usr/bin/wayland-scanner" "$T/bin/wayland-scanner"
cat > "$T/env.sh" << EOF
# bc5-toolchain.sh $(date '+%F %T'): source this before a host build
export BC5_TOOLCHAIN=$T
export PATH=$T/bin:$T/cmake-$CMAKE_V/bin:$T/llvm-$LLVM_V/bin:$T/cargo/bin:/usr/bin:/bin
export CC=$T/llvm-$LLVM_V/bin/clang CXX=$T/llvm-$LLVM_V/bin/clang++
export RUSTUP_HOME=$T/rustup CARGO_HOME=$T/cargo RUSTUP_TOOLCHAIN=$RUST_V  # over tools/rust-toolchain.toml (stable): the pinned, verified one
export PKG_CONFIG_PATH=$T/sysroot/usr/lib64/pkgconfig:$T/sysroot/usr/share/pkgconfig PKG_CONFIG_LIBDIR=/usr/lib64/pkgconfig:/usr/share/pkgconfig
export CMAKE_PREFIX_PATH=$T/sysroot/usr CMAKE_LIBRARY_PATH=$T/sysroot/usr/lib64 CMAKE_INCLUDE_PATH=$T/sysroot/usr/include
EOF
. "$T/env.sh"
say "versions: $(clang --version | head -1); $(ld.lld --version); cmake $(cmake --version | head -1 | awk '{print $3}'); ninja $(ninja --version); $(rustc --version); $(cargo --version); glslang $(glslangValidator --version 2>&1 | head -1); $(wayland-scanner --version 2>&1)"
say "sysroot $S ($(du -sh "$S" | cut -f1)), $(wc -l < "$S/NVRS") packages; downloads in $T/dl ($(du -sh "$T/dl" | cut -f1)), sums in $T/dl/SHA256SUMS"
# smoke: every module pkg-config knows, and a C++ program against libdrm_amdgpu linked with lld
for m in glib-2.0 gio-2.0 ibus-1.0 libpipewire-0.3 libpulse alsa dbus-1 wayland-client wayland-cursor wayland-egl libdrm libdrm_amdgpu x11 xkbcommon egl gbm opus liblzma libudev samplerate libdecor-0 jack; do
    pkg-config --exists "$m" || die "pkg-config does not find $m"; done
printf '#include <amdgpu.h>\nint main(){amdgpu_device_handle d; (void)d; return 0;}\n' > "$T/smoke.cpp"
clang++ -fuse-ld=lld $(pkg-config --cflags libdrm_amdgpu) "$T/smoke.cpp" $(pkg-config --libs libdrm_amdgpu) -o "$T/smoke" && "$T/smoke" && ldd "$T/smoke" | grep -q '/usr/lib64/libdrm_amdgpu' || die "the smoke build does not link the host's libdrm_amdgpu"
say "OK: source $T/env.sh before a build; bash host-deps-check.sh checks what it builds"
