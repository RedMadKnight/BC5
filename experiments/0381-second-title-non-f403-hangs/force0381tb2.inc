# exp 0381 test build 2: what this build is, set again right after both settings files, so that neither can turn it off. In the smoke launcher TB2_PRIVATE also fixes
# its private paths and the RT guards. In the player's launcher it is empty: bc5-pkg.env may move those there, as in r1, and the log's first line says where they went.
TB2_REQ=(BC5_DIRECT_ACB_STATE_RESTORE=1 BC5_CRASH_FRAMES=1 BC5_0380_REC=1 BC5_DIRECT_PIECES_NO_CLEAR=1 "BC5_DIRECT_ZERO_SKIP=$HOME/bc5-work/exp0381/tb2/zero-list-20261029-120000.txt")
TB2_PRIVATE=()
TB2_WD=""
export "${TB2_REQ[@]}" "${TB2_PRIVATE[@]}"
if [ -n "$TB2_WD" ]; then
  # Not in $LOG: the log's own directory may be what is wrong. The starter keeps this in raw/<tag>-launch.out, or stops first.
  TB2_W=$(tb2_private_all) || { say "A private path is not itself: $TB2_W; not started."; exit 1; }
fi
# end of exp 0381 test build 2's required settings
