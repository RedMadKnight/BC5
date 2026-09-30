#!/usr/bin/env bash
# BC5: build KytyPlus (GPL-2.0) emulator target only, inside the ubuntu distrobox. Log: ~/bc5-work/kytyplus-build.log
set -u
cd ~/src/KytyPlus
S=$(date +%s)
sudo apt-get install --no-install-recommends --yes clang lld ninja-build glslang-tools libasound2-dev libdbus-1-dev libgl1-mesa-dev libpulse-dev libudev-dev libwayland-dev libx11-dev libxcursor-dev libxext-dev libxfixes-dev libxi-dev libxkbcommon-dev libxrandr-dev libxss-dev wayland-protocols libedit-dev libevdev-dev libjack-dev libopenal-dev libpng-dev libsdl2-dev libsndio-dev libssl-dev libvulkan-dev zlib1g-dev > ~/bc5-work/kytyplus-deps.log 2>&1
echo "deps exit $? after $(( $(date +%s) - S )) s"
git submodule update --init --recursive --depth 1 2>&1 | tail -2
cmake -S . -B ~/bc5-work/kytyplus-build -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_C_COMPILER=clang -DCMAKE_CXX_COMPILER=clang++ -DKYTY_BUILD_LAUNCHER=OFF > ~/bc5-work/kytyplus-configure.log 2>&1
echo "configure exit $? after $(( $(date +%s) - S )) s"
cmake --build ~/bc5-work/kytyplus-build --target kyty_emulator -j8 2>&1 | tail -30
echo "build exit ${PIPESTATUS[0]} after $(( $(date +%s) - S )) s"
ls -la ~/bc5-work/kytyplus-build/kyty_emulator ~/bc5-work/kytyplus-build/src/kyty_emulator 2>/dev/null
