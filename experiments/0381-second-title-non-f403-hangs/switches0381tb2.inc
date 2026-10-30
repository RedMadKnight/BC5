# exp 0381 test build 2: the switches, read from tb2/switches.env at every start; only these names, and the log's first line names them
TB2_SW=""
for l in $(grep -E '^BC5_DIRECT_[A-Z0-9_]+=[A-Za-z0-9:]+$' "$HOME/bc5-work/exp0381/tb2/switches.env" 2> /dev/null); do
  case "${l%%=*}" in
    BC5_DIRECT_GPU_CHECK_YZ|BC5_DIRECT_FORCE_START_000|BC5_DIRECT_ARGS_WB|BC5_DIRECT_ARGS_FLUSH|BC5_DIRECT_ARGS_FLUSH_DRAWS|BC5_DIRECT_GPU_CHECK_ZERO|BC5_DIRECT_ARGS_COPY)
      export "$l"; TB2_SW="$TB2_SW $l" ;;
    *) TB2_SW="$TB2_SW IGNORED:$l" ;;
  esac
done
