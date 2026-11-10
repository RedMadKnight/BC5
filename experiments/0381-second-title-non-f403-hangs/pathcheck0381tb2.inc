# exp 0381 test build 2: is each private path what its name says? Used by the smoke's starter before it deletes or copies anything, and by the smoke launcher before its mkdir and before every start.
# Each path is walked from the canonical home, the only alias allowed: every part that exists must be a real directory (or the file it names), not a link or junction. A tree must hold no link at all. Absent parts pass: nothing is there to follow.
tb2_private() {
  local h p r c
  h=$(readlink -f "${TB2_ROOT:-$HOME}") && [ -n "$h" ] || return 1
  p=$h; r=$1/
  while [ -n "$r" ]; do
    c=${r%%/*}; r=${r#*/}
    case "$c" in ''|.|..) return 1 ;; esac
    p=$p/$c
    [ ! -L "$p" ] || return 1
    [ -e "$p" ] || continue
    [ "$(readlink -f "$p")" = "$p" ] || return 1
    if [ -n "$r" ] || [ "$2" != file ]; then [ -d "$p" ] || return 1; else [ -f "$p" ] || return 1; fi
  done
  [ "$2" != tree ] || [ ! -e "$p" ] || [ -z "$(find "$p" -type l -print -quit 2>&1)" ]
}
# wd itself is a real directory that holds setup0381j.sh's links to the title's files, so only its save directories are trees.
# Every place the smoke writes, then the private paths against their live twins, which catches a mount or a hard link that a walk cannot see. Prints what failed.
tb2_private_all() {
  local t a b h
  for t in bc5-work/exp0381/wd:dir bc5-work/exp0381/wd/_SaveData:tree bc5-work/exp0381/wd/_SaveData/PPSA03671:tree bc5-work/exp0381/wd/_SaveData-pkg-play:tree \
           bc5-work/exp0381/direct-learned-pkg.txt:file bc5-work/exp0381/input-rton.cfg:file bc5-work/exp0381/tb2:dir bc5-work/exp0381/tb2/raw:dir bc5-work/exp0381/tb2/play:dir; do
    tb2_private "${t%:*}" "${t##*:}" || { echo "${t%:*}"; return 1; }
  done
  h=$(readlink -f "${TB2_ROOT:-$HOME}")/bc5-work
  for t in wd: wd/_SaveData:_SaveData wd/_SaveData-pkg-play:_SaveData-pkg-play direct-learned-pkg.txt:direct-learned-pkg.txt; do
    a=$h/exp0381/${t%:*}; b=$h/${t##*:}
    [ ! "$a" -ef "$b" ] || { echo "$a is $b"; return 1; }
  done
}
# end of exp 0381 test build 2's path check
