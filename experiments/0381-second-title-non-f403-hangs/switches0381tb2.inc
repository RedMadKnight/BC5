# exp 0381 test build 2: the switches, read from a data file at every start, after bc5-run.env and bc5-pkg.env, so this file beats both.
# Each is reset first, so a value from either file or from outside never survives a commented line. BC5_DIRECT_REBASE_DISPATCH is refuted: reset, never accepted.
# The file is not sourced: a line counts only if it is a name with one of its documented values. The last valid line for a name wins, and the log names the effective state.
SWF=$HOME/bc5-work/exp0381/tb2/switches.env
TB2_NAMES="BC5_DIRECT_GPU_CHECK_YZ BC5_DIRECT_FORCE_START_000 BC5_DIRECT_ARGS_WB BC5_DIRECT_ARGS_FLUSH BC5_DIRECT_ARGS_FLUSH_DRAWS BC5_DIRECT_GPU_CHECK_ZERO BC5_DIRECT_ARGS_COPY BC5_DIRECT_DRAW_ARGS_JOURNAL BC5_DIRECT_REBASE_DISPATCH"
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
TB2_KEPT_NAMES="BC5_DIRECT_ACB_STATE_RESTORE BC5_CRASH_FRAMES BC5_0380_REC BC5_DIRECT_PIECES_NO_CLEAR BC5_DIRECT_ZERO_SKIP KYTY_BC5_SAVEDATA_DIR BC5_DIRECT_LEARNED KYTY_BC5_INPUT_CONFIG BC5_DIRECT_COMPUTE_RING BC5_DIRECT_CROSS_RING_WAITS BC5_DIRECT_GPU_CHECK BC5_DIRECT_GPU_CHECK_PRODUCT BC5_DIRECT_SHADOW_LABELS BC5_DIRECT_HOST_INDIRECT BC5_DIRECT_SOFT_WAIT_MS"
tb2_env() {
  local n v
  for n in $1; do
    v=$(printenv "$n") && printf ' %s=%s' "$n" "$v"
  done
}
TB2_ENV=$(tb2_env "$TB2_NAMES")
TB2_KEPT=$(tb2_env "$TB2_KEPT_NAMES")
TB2_SW=$TB2_ENV
[ -z "$TB2_BAD" ] || TB2_SW="$TB2_SW REJECTED-LINES:$TB2_BAD"
# Called right before each emulator start: what the log says is what the emulator gets, each required value is exact, and each private path is itself, not a link elsewhere. If not, it does not start.
tb2_check() {
  local r v w=""
  [ "$(tb2_env "$TB2_NAMES")" = "$TB2_ENV" ] || w="$w switches:$(tb2_env "$TB2_NAMES")"
  [ "$(tb2_env "$TB2_KEPT_NAMES")" = "$TB2_KEPT" ] || w="$w settings:$(tb2_env "$TB2_KEPT_NAMES")"
  for r in "${TB2_REQ[@]}" "${TB2_PRIVATE[@]}"; do
    v=$(printenv "${r%%=*}"); [ "$v" = "${r#*=}" ] || w="$w ${r%%=*}=$v"
  done
  for r in "${TB2_PATHS[@]}"; do
    v=$(printenv "$r"); [ "$(readlink -f "$v")" = "$(readlink -f "$HOME")${v#"$HOME"}" ] || w="$w link:$r"
  done
  [ -z "$TB2_WD" ] || [ "$(pwd -P)" = "$(readlink -f "$TB2_WD")" ] || w="$w wd:$(pwd -P)"
  [ -z "$w" ] && return 0
  echo "== $(date '+%F %T') exp 0381: changed after the settings were read, not started:$w" >> "$LOG"
  say "The settings changed after they were read; not started (see $LOG)."
  exit 1
}
# end of exp 0381 test build 2's switches
