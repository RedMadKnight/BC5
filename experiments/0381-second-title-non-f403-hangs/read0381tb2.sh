# BC5 exp 0381: test build 2's pin read, under its own claim, the first step of the cycle. Sent after lock0381tb2.inc, with TB2_TOKEN set (tb2run0381.sh read).
# It writes only its claim and queue lines. It prints md5s and the canonical home: no settings, logs or game data.
pgrep '^kyty_emulator' > /dev/null && { echo "TB2 STOP: an emulator runs"; exit 3; }
tb2_hook before-claim
trap tb2_held_release EXIT
tb2_claim
tb2_own
pgrep '^kyty_emulator' > /dev/null && { echo "TB2 STOP: an emulator runs"; exit 3; }
tb2_queue "$TB2_LINE: pin read | $(date '+%F %T')"
tb2_hook after-claim
tb2_own
cd "$W/.." || exit 1
readlink -f .
md5sum bc5-work/play-pkg.sh src/KytyPlus/src/libs/libC.cpp src/KytyPlus/src/libs/bc5LleAgc.cpp src/KytyPlus/src/libs/libNpCppWebApi.cpp bc5-work/kytyplus-build/src/kyty_emulator bc5-work/kytyplus-build-lean/src/kyty_emulator bc5-work/backend-ubuntu/libbc5_backend.a
ls -ld bc5-work bc5-work/exp0381 bc5-work/exp0381/wd
tb2_own
tb2_queue "$TB2_LINE: pin read done | $(date '+%F %T')"
