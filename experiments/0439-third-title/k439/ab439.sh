#!/usr/bin/env bash
# BC5 exp 0439 (tag ab439; AB439_ARMS="name[:pin[:words]] ..." overrides the arm list, AB439_SHOTS the shot times; 11-22 ~23:58, the top session's order): which of the bake-2 rows (or the base) makes the
# maintainer's "in-game much better" on 28ae20cf. One st439.sh start per arm, each on a fresh save root, no pad input,
# 120 s, shots at 45, 60, 90 and 115 s (the name-writing scene, reached by itself on a fresh save): an image comparison
# (imgm439.py on the laptop), not a performance measurement. Arms, in order:
#   ctl   7277b404 as it is
#   mec   7277b404, BC5_DIRECT_DMA_SYNC_MEC=0      lab  BC5_DIRECT_DMA_SYNC_LABEL=0
#   cw    7277b404, BC5_DIRECT_CHAIN_WRITERS=0     pc   BC5_DIRECT_PREFIX_CHAINS=0
#   d3    5f582a73 (the build of his d3r1/d3r2 plays)
#   aft   c82fe3b0 (an afternoon build; unpacked from its .gz first; last, an older build may stall)
# A GPU kernel line after any arm stops the series (st439.sh reports the count).
set -u
K=$HOME/bc5-work/exp0439/k439; cd "$K" || exit 1
[ -f normal/kyty_emulator.c82fe3b0 ] || { gunzip -k normal/kyty_emulator.c82fe3b0.gz && chmod a-w normal/kyty_emulator.c82fe3b0; } || { echo "ab439 STOP: unpack c82fe3b0"; exit 1; }
ARMS=${AB439_ARMS:-"ctl mec lab cw pc d3 aft"}
for spec in $ARMS; do
	arm=${spec%%:*}
	case $arm in
	ctl) P=7277b404; M="" ;;
	mec) P=7277b404; M="BC5_DIRECT_DMA_SYNC_MEC=0" ;;
	lab) P=7277b404; M="BC5_DIRECT_DMA_SYNC_LABEL=0" ;;
	cw) P=7277b404; M="BC5_DIRECT_CHAIN_WRITERS=0" ;;
	pc) P=7277b404; M="BC5_DIRECT_PREFIX_CHAINS=0" ;;
	d3) P=5f582a73; M="" ;;
	aft) P=c82fe3b0; M="" ;;
	tp0*) P=7277b404; M="KYTY_BC5_0439_PAD_TIME=0" ;;
	tc0*) P=7277b404; M="KYTY_BC5_0439_PAD_TOUCH=0" ;;
	ctl*) P=7277b404; M="" ;;
	lab*) P=7277b404; M="BC5_DIRECT_DMA_SYNC_LABEL=0" ;;
	cw*) P=7277b404; M="BC5_DIRECT_CHAIN_WRITERS=0" ;;
	pw*) P=7277b404; M="BC5_0439_PIECE_WAITS=2" ;;
	m3*) P=7277b404; M="BC5_0439_PIECE_WAITS=3 BC5_0439_PIECE_HOLD=0" ;;
	ph*) P=7277b404; M="BC5_0439_PIECE_WAITS=3" ;;
	dk*) P=7277b404; M="BC5_0439_DCC_UNCOMPRESSED=1" ;;
	gw*) P=7277b404; M="BC5_DIRECT_GPU_WAITS=1" ;;
	esac
	# "name:pin" or "name:pin:words" (words "+"-separated) override the case's pin and words
	case $spec in *:*) r=${spec#*:}; P=${r%%:*}; case $r in *:*) M=$(echo "${r#*:}" | tr + ' ') ;; esac ;; esac
	out=$(ST_MORE="$M" ST_SHOTS="${AB439_SHOTS:-45 60 90 115}" ST_BOUND=${AB439_BOUND:-120} bash st439.sh "$P" 2>&1 | tail -1)
	echo "$arm [$P $M]: $out"
	case "$out" in *"GPU kernel lines "*) a=$(echo "$out" | sed 's/.*GPU kernel lines \([0-9]*\) -> \([0-9]*\).*/\1 \2/'); [ "${a% *}" = "${a#* }" ] || { echo "ab439 STOP: a GPU kernel line after $arm"; exit 1; } ;; *) echo "ab439 STOP: $arm did not finish"; exit 1 ;; esac
	sleep 5
done
echo "ab439: done"
