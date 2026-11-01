# BC5 exp 0388: sourced by the derived launcher after its last settings load and before every emulator start, the
# restart of the F2 menu too. The launcher reads bc5-pkg.env after the private exports, so anything in it could undo them.
# Here the private paths, the arm, the guards and this run's lock line must still be exactly what s6n0388.sh wrote to
# run/prestart.want, and no forbidden name may be set. Any doubt returns 1 and the launcher exits 97, before any emulator.
# The name list is d19manifest.py's FORBIDDEN; test_prestart.sh compares them.
E0388_DENY="BC5_DIRECT_ARGS_COPY BC5_DIRECT_ARGS_WB BC5_DIRECT_ARGS_FLUSH BC5_DIRECT_ARGS_FLUSH_DRAWS BC5_DIRECT_FORCE_START_000 BC5_DIRECT_GPU_CHECK_ZERO BC5_DIRECT_GPU_CHECK_YZ BC5_DIRECT_REBASE_DISPATCH BC5_DIRECT_CHAIN_BREAK_AT BC5_DIRECT_DRAW_ARGS_JOURNAL BC5_DIRECT_BO_JOURNAL BC5_DIRECT_ARGS_HISTOGRAM BC5_DIRECT_ZERO_SKIP BC5_DIRECT_ZEROSCAN_AT BC5_DIRECT_ZEROSCAN_OUT BC5_DIRECT_ACB_STATE_RESTORE BC5_DIRECT_PIECES_NO_CLEAR BC5_DIRECT_INDEX_BASE_DUP BC5_DIRECT_NO_CARRY KYTY_BC5_RT"
e0388_prestart() {
  local f=~/bc5-work/exp0388/run/prestart.want l k v n=0
  e0388_no() { echo "$(date '+%F %T') prestart stop: $*" >> ~/bc5-work/exp0388/run/prestart.out; return 1; }
  [ -f "$f" ] && [ ! -L "$f" ] || { e0388_no "no want file"; return 1; }
  for k in $E0388_DENY; do [ -z "${!k+x}" ] || { e0388_no "$k is set"; return 1; }; done
  while IFS= read -r l; do
    case "$l" in
      lock=*) [ -f ~/bc5-work/BOX-LOCK ] && [ ! -L ~/bc5-work/BOX-LOCK ] && [ "$(cat ~/bc5-work/BOX-LOCK 2> /dev/null)" = "${l#lock=}" ] || { e0388_no "the lock is not this run's"; return 1; } ;;
      want=*) l=${l#want=}; k=${l%%=*}; v=${l#*=}; [ "${!k-}" = "$v" ] && [ -n "${!k+x}" ] || { e0388_no "$k is not the run's value"; return 1; }; n=$((n + 1)) ;;
      *) e0388_no "bad want line"; return 1 ;;
    esac
  done < "$f"
  [ "$n" -ge 12 ] || { e0388_no "only $n wanted values"; return 1; }
}
e0388_prestart
