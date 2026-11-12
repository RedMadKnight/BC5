#!/usr/bin/env bash
# exp 0413: after the shared swap (int0413b.log shows its "after:" line and the lock released): one ASTRO BOT start and
# one second-title run (RT on, no zero skip, 240 s after G) on the SHARED normal binary, through the 0413 private
# launchers' copies (private working directories; the shared launchers are not used or changed).
set -u; ulimit -c 0; export LC_ALL=C
W=$HOME/bc5-work; N=$W/exp0413/n; L=$W/exp0413/swap/int0413b.log
for _ in $(seq 1 240); do grep -q "^lock released\|STOP\|INCOMPLETE\|restored and read back" "$L" && break; sleep 5; done
grep -q " after: normal " "$L" && grep -q "^lock released" "$L" || { echo "post: the swap did not end clean"; tail -5 "$L"; exit 1; }
B=$W/kytyplus-build/src/kyty_emulator; M=$(md5sum < "$B" | cut -d' ' -f1)
echo "post: shared normal $M"
cd "$N" || exit 1
export P_BIN=$B P_WANT=$M
bash ./sweep0413g.sh s1sh 30 "0"
grep -a -h "SessionManager V2\|KYTY_BC5_AMM_SETBUFFER_GUARD o" raw/s1sh0-play.log | sort | uniq -c
sleep 4
P_WORDS=$N/words0413nz.txt bash ./run0413p.sh s2sh nozeroskip 240
echo "post done $(date +%T)"
