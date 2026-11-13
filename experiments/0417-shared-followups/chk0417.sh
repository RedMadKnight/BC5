#!/usr/bin/env bash
# BC5 exp 0417: the private build with the set-buffer test hook, and ASTRO BOT starts that force a4 = -1 on a real
# call, in one short slot. Private directories only (~/bc5-work/exp0413/p and /n, exp 0413's tools); every step takes
# and releases BOX-LOCK by itself and refuses when an emulator runs. The chain stops at a failed build.
# A start that does not run its 30 s is a RESULT here (the hook forces a signature the title did not send), so the
# chain goes on after it, except after a kernel line: then it stops (the top's rule).
#   build   p0417.sh: the private tree 4651d1d3 -> P_NEW10 with the hook's gate on, normal only
#   ASTRO BOT, 30 s each:
#     h1 KYTY_BC5_AMM_SETBUFFER_TEST=mapped                       want: exp 0413's guard line, the run goes on
#     h2 mapped and KYTY_BC5_AMM_SETBUFFER_MAP=1                  want: the same (the guard is in front of the opt-in)
#     h3 KYTY_BC5_AMM_SETBUFFER_TEST=unmapped                     want: exp 0416's line, "after no", the run goes on
#     h4 unmapped and KYTY_BC5_AMM_SETBUFFER_MAP=1                want: the hook's result line of the real map command
#     h5 KYTY_BC5_SWITCH_DEFAULTS=0                               want: the lines of the code defaults (C1, C2, C3, APR)
#     h6 nothing set                                              want: no hook line, C2 and C3 lines "on"
#   NOT run: mapped with the guard off and the opt-in on (exp 0413's crash, already proved).
# usage (on the box, detached): P_NEW10=<patch md5> chk0417.sh
set -u
ulimit -c 0
export LC_ALL=C
W=$HOME/bc5-work; E=$W/exp0413; N=$E/n; P=$E/p; R=$N/raw
: "${P_NEW10:?the patch md5}"
cd "$N" || exit 1
(cd "$P/kit" && P_NEW10=$P_NEW10 bash ./p0417.sh) > "$P/p0417.log" 2>&1
tail -4 "$P/p0417.log"
grep -q "^lock released" "$P/p0417.log" && grep -q " done; normal " "$P/p0417.log" && grep -q "^gate back: #define KYTY_BC5_SETBUFFER_TEST_HOOK 0" "$P/p0417.log" ||
    { grep -m8 "error:\|STOP\|differs\|lacks" "$P/p0417.log" "$P"/build-normal.build.log 2> /dev/null | cut -c1-300; echo "chk0417 ended $(date +%T): the build did not end clean"; exit 1; }
BN=$P/build-normal/src/kyty_emulator
MN=$(md5sum < "$BN" | cut -d' ' -f1)
echo "0417 binary (private, with the hook): normal $MN"
export P_BIN=$BN P_WANT=$MN
one() {  # tag, words...
    local tag=$1; shift
    local line; line=$(bash ./sweep0413g.sh "$tag" 30 "0" "$@" | grep "^n=0:")
    echo "$line"
    echo "$tag lines: $(grep -a -h "exp 0417 hook\|set-buffer with the map\|SETBUFFER_GUARD o\|ranges fast|physmap sorted|acb state restore\|physmap sorted\|pending cap\|exp 0415: APR reads" "$R/${tag}0-play.log" 2> /dev/null | sed 's/\[bc5\] //' | cut -c1-230)"
    case "$line" in *"kernel lines 0,"*) ;; *) echo "chk0417 ended $(date +%T): STOPPED after $tag (a kernel line, or no result line)"; exit 1 ;; esac
}
T=KYTY_BC5_AMM_SETBUFFER_TEST
one h1x $T=mapped
one h2x $T=mapped KYTY_BC5_AMM_SETBUFFER_MAP=1
one h3x $T=unmapped
one h4x $T=unmapped KYTY_BC5_AMM_SETBUFFER_MAP=1
one h5x KYTY_BC5_SWITCH_DEFAULTS=0
one h6x
echo "chk0417 ended $(date +%T): all six starts made"
