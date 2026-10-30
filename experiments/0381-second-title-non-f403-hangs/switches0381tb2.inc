# exp 0381 test build 2: the switches, read from a data file at every start. Each is reset first, so an inherited value never survives a commented line.
# The file is not sourced: a line counts only if it is a name with one of its documented values. The last valid line for a name wins, and the log names the effective state.
SWF=$HOME/bc5-work/exp0381/tb2/switches.env
TB2_NAMES="BC5_DIRECT_GPU_CHECK_YZ BC5_DIRECT_FORCE_START_000 BC5_DIRECT_ARGS_WB BC5_DIRECT_ARGS_FLUSH BC5_DIRECT_ARGS_FLUSH_DRAWS BC5_DIRECT_GPU_CHECK_ZERO BC5_DIRECT_ARGS_COPY BC5_DIRECT_DRAW_ARGS_JOURNAL"
unset $TB2_NAMES
TB2_BAD=""; TB2_N=0
if [ -f "$SWF" ] && [ -r "$SWF" ]; then
  while IFS= read -r l || [ -n "$l" ]; do
    TB2_N=$((TB2_N + 1))
    case "$l" in
      ''|'#'*) ;;
      BC5_DIRECT_FORCE_START_000=1|BC5_DIRECT_ARGS_FLUSH_DRAWS=1|BC5_DIRECT_GPU_CHECK_ZERO=1|BC5_DIRECT_ARGS_COPY=1) export "$l" ;;
      BC5_DIRECT_ARGS_WB=first|BC5_DIRECT_ARGS_WB=all|BC5_DIRECT_ARGS_FLUSH=first|BC5_DIRECT_ARGS_FLUSH=all) export "$l" ;;
      BC5_DIRECT_GPU_CHECK_YZ=*)
        if printf '%s\n' "${l#*=}" | grep -qE '^[1-9][0-9]{0,4}(:[1-9][0-9]{0,4})?$'; then export "$l"; else TB2_BAD="$TB2_BAD $TB2_N"; fi ;;
      *) TB2_BAD="$TB2_BAD $TB2_N" ;;
    esac
  done < "$SWF"
fi
TB2_SW=""
for n in $TB2_NAMES; do
  v=$(printenv "$n") && TB2_SW="$TB2_SW $n=$v"
done
[ -z "$TB2_BAD" ] || TB2_SW="$TB2_SW REJECTED-LINES:$TB2_BAD"
# end of exp 0381 test build 2's switches
