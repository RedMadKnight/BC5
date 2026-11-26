#!/usr/bin/env bash
# BC5 experiment 0442 (tag tg442): the det tests of the move. CPU only, nothing shared written.
#   test0442.sh <old include dir> <new include dir> <test0442.cpp> <work dir>
# <old include dir>/bc5/ holds the shared switch_defaults.hpp (48ae1cd6) and env_rule.hpp; <new include dir>/bc5/ holds
# mk0442.py's switch_defaults.hpp, env_rule.hpp, idraws0442.hpp and the backend's env_flag.hpp.
#   T1 units: idraws0442.hpp's modes and env_on (SHADOW_LABELS)
#   T2 every title: with a clean environment each of the 28 moved words has its value for the first title (TITLE1B), the
#      third title (TITLE3) and no title at all; the 5 rows left for TITLE2 are unset there
#   T3 off-words: for the first title, NAME=0 keeps each moved word at "0" (its reader's off, see the README's reader list)
#      and leaves the other 27 at their values; the whole G6+G7 group off by its five off-words
#   T4 the second title: word by word over the 38 table words, old header against new, with a clean environment (only
#      the five deleted rows differ: GUARD_LEARN_LOG, SKIP_PGM, and nl442's GUARD_SPLIT, ALIASES, HOST_INDIRECT) and
#      with play-pkg.sh's own words for the 38 (only the four gone learned words differ: set -> unset);
#      LAZY_RELEASE=0 now turns the orphan release off (the old header forced it)
#   T5 KYTY_BC5_TITLE_DEFAULTS=0 on the second title: the moved words stay (every title's), the left rows go
#   T6 (tag nl442) each gone learned word, set in the environment, is unset after Apply() and reported on stderr as
#      ignored; the old header kept it (or forced it)
# Bake 1a: KEEP="<names>" (the rows mk0442.py kept with MK0442_KEEP) are checked as rows left for TITLE2 (T2, T5),
# not as moved ones; LEAN_GONE=1 adds T7: the new header built with -DBC5_LEAN reports no gone word and leaves it set
# (nothing in lean reads it).
set -u
export LC_ALL=C
OLD=${1:?old include dir}; NEW=${2:?new include dir}; SRC=${3:?test0442.cpp}; WK=${4:?work dir}
PASS=0; FAIL=0
ok() { if [ "$2" = 1 ]; then PASS=$((PASS + 1)); [ -n "${VERBOSE:-}" ] && echo "ok   $1"; else FAIL=$((FAIL + 1)); echo "FAIL $1"; fi; }
mkdir -p "$WK" || exit 1
g++ -std=c++20 -O1 -Wall -Wextra -Werror -I "$OLD" -o "$WK/t_old" "$SRC" || { echo "FAIL compile old"; exit 1; }
g++ -std=c++20 -O1 -Wall -Wextra -Werror -DTG442_UNITS -I "$NEW" -o "$WK/t_new" "$SRC" || { echo "FAIL compile new"; exit 1; }
for t in TITLE2 TITLE1B TITLE3; do
    mkdir -p "$WK/g/$t/sce_sys" && printf '{\n  "titleId": "%s",\n  "x": 1\n}\n' "$t" > "$WK/g/$t/sce_sys/param.json"
done
MOVED="KYTY_BC5_SAVEDATA_MEMORY_FIXES=1 KYTY_BC5_SAVEDATA_DELETE_BUSY=1 KYTY_BC5_SAVEDATA_ALIASES=1 KYTY_BC5_HTTP2_FIXES=1
KYTY_BC5_PAD_OPEN_EXT=1 KYTY_BC5_JSON2_FIXES=1 KYTY_BC5_ULT_FIXES=1 KYTY_BC5_USERSERVICE_VALUES=1 KYTY_BC5_SYSTEMSERVICE_VALUES=1
KYTY_BC5_SYSTEMSERVICE_PARAMS_7_1000=1 KYTY_BC5_AUDIOOUT_CHECKS=1 KYTY_BC5_AUDIOIN_CHECKS=1 KYTY_BC5_NGS2_RACK_FIX=1
KYTY_BC5_FW_PAD=1 KYTY_BC5_LOAD_ZLIB=1 KYTY_BC5_LOAD_JPEG=1 KYTY_BC5_LOAD_IME=1 KYTY_BC5_LOAD_NPCOMMON=1
KYTY_BC5_LOAD_NPMANAGER=1 KYTY_BC5_LOAD_NPTROPHY=1 BC5_DIRECT_MEC_INDIRECT=1 BC5_DIRECT_REMEMBER_UNMAPPED=1
KYTY_BC5_APR_PARALLEL=8 BC5_DIRECT_GPU_CHECK=1 BC5_DIRECT_DMA_SNAPSHOT=4096 BC5_DIRECT_CS_PREFIX=1
BC5_DIRECT_INDIRECT_DRAWS=multi BC5_DIRECT_LAZY_RELEASE=30,eager"
G67="BC5_DIRECT_GPU_CHECK BC5_DIRECT_DMA_SNAPSHOT BC5_DIRECT_CS_PREFIX BC5_DIRECT_INDIRECT_DRAWS BC5_DIRECT_LAZY_RELEASE"
LEFT="BC5_DIRECT_DMA_SYNC BC5_DIRECT_FLAT_APERTURE BC5_DIRECT_AMM_PRT BC5_DIRECT_GPU_CHECK_PRODUCT BC5_DIRECT_SHADOW_LABELS"
KEEP=$(echo "${KEEP:-}" | tr ',' ' '); MOVED_ALL=$MOVED; MOVED=""
for p in $MOVED_ALL; do case " $KEEP " in *" ${p%%=*} "*) LEFT="$LEFT ${p%%=*}" ;; *) MOVED="$MOVED $p" ;; esac; done
for k in $KEEP; do case " $LEFT " in *" $k "*) ;; *) echo "FAIL KEEP names $k, not a moved row"; exit 1 ;; esac; done
[ -n "$KEEP" ] && echo "bake 1a: kept rows (checked as left rows): $KEEP"
DELETED="BC5_GUARD_LEARN_LOG BC5_DIRECT_SKIP_PGM BC5_GUARD_SPLIT BC5_DIRECT_ALIASES BC5_DIRECT_HOST_INDIRECT"
# the old header's values of the deleted rows (TITLE2), and the learned words that are gone (kGone0442)
DELETED_OLD="BC5_GUARD_LEARN_LOG=2 BC5_DIRECT_SKIP_PGM=0 BC5_GUARD_SPLIT=1 BC5_DIRECT_ALIASES=1 BC5_DIRECT_HOST_INDIRECT=learn:1100000000"
GONE="BC5_DIRECT_ALIASES BC5_GUARD_SPLIT BC5_GUARD_LEARN_LOG BC5_DIRECT_HOST_INDIRECT BC5_DIRECT_LEARNED BC5_DIRECT_LEARN_GUEST_ONLY"
# bake 1d: RT_OUT=<dir of mk0442.py's output> adds the ray-tracing words to the gone words (T6, T7) and runs T8 on the dir
[ -n "${RT_OUT:-}" ] && GONE="$GONE KYTY_BC5_RT KYTY_BC5_RT_BUILD_PGM"
# play-pkg.sh 47426d8e's own values for the 38 words (lines 50, 55-56, 60-64, 75, 82, 85, 88, 111-113, 124, 138, 142-143)
LAUNCHER="$MOVED BC5_DIRECT_DMA_SYNC=1 BC5_DIRECT_FLAT_APERTURE=1 BC5_GUARD_SPLIT=1 BC5_DIRECT_AMM_PRT=1 BC5_DIRECT_ALIASES=1
BC5_DIRECT_GPU_CHECK_PRODUCT=1 BC5_DIRECT_SHADOW_LABELS=1 BC5_DIRECT_HOST_INDIRECT=learn:1100000000 BC5_GUARD_LEARN_LOG=2 BC5_DIRECT_SKIP_PGM=0"
names() { for p in $1; do echo "${p%%=*}"; done; }
ALL=$( (names "$MOVED"; echo $LEFT $DELETED | tr ' ' '\n') | grep . | tr '\n' ',' | sed 's/,$//')
[ "$(echo "$ALL" | tr ',' '\n' | sort -u | wc -l)" = 38 ] || { echo "FAIL the word list is not 38 words"; exit 1; }
run() { # bin title(-|id) env... : prints NAME=value / NAME unset for the 38 words
    local bin=$1 t=$2; shift 2
    if [ "$t" = - ]; then env -i PATH=/usr/bin:/bin TG_WORDS="$ALL" "$@" "$WK/$bin"; else env -i PATH=/usr/bin:/bin TG_WORDS="$ALL" "$@" "$WK/$bin" --game "$WK/g/$t"; fi 2> /dev/null
}
val() { grep -x "$2=.*" <<< "$1" | cut -d= -f2-; }
unset_in() { grep -qx "$2 unset" <<< "$1" && echo 1 || echo 0; }
# T1
"$WK/t_new" --units > "$WK/units.txt"; rc=$?; cat "$WK/units.txt"
ok "T1 units" "$([ $rc = 0 ] && echo 1)"
# T2
for t in TITLE1B TITLE3 -; do
    o=$(run t_new "$t"); oo=$(run t_old "$t")
    for p in $MOVED; do
        ok "T2 $t: ${p%%=*}=${p#*=} (new)" "$([ "$(val "$o" "${p%%=*}")" = "${p#*=}" ] && echo 1)"
        ok "T2 $t: ${p%%=*} unset in the old header" "$(unset_in "$oo" "${p%%=*}")"
    done
    for w in $LEFT $DELETED; do ok "T2 $t: $w unset (new)" "$(unset_in "$o" "$w")"; done
done
# T3
for p in $MOVED; do
    w=${p%%=*}; o=$(run t_new TITLE1B "$w=0")
    ok "T3 $w=0 stays 0" "$([ "$(val "$o" "$w")" = 0 ] && echo 1)"
    others=1
    for q in $MOVED; do [ "${q%%=*}" = "$w" ] && continue; [ "$(val "$o" "${q%%=*}")" = "${q#*=}" ] || others=0; done
    ok "T3 $w=0 leaves the other 27 at their values" "$others"
done
offs=(); for w in $G67; do offs+=("$w=0"); done
o=$(run t_new TITLE1B "${offs[@]}")
g=1; for w in $G67; do [ "$(val "$o" "$w")" = 0 ] || g=0; done
ok "T3 G6+G7 off by five off-words" "$g"
g=1; for q in $MOVED; do case " $G67 " in *" ${q%%=*} "*) continue ;; esac; [ "$(val "$o" "${q%%=*}")" = "${q#*=}" ] || g=0; done
ok "T3 G6+G7 off leaves the other 23 on" "$g"
# T4
o=$(run t_new TITLE2); oo=$(run t_old TITLE2)
diff <(echo "$oo") <(echo "$o") > "$WK/t4-clean.diff"
d=$(grep -c '^[<>]' "$WK/t4-clean.diff")
echo "T4 second title, clean environment, old -> new (38 words):"; cat "$WK/t4-clean.diff"
want=$( (for p in $DELETED_OLD; do echo "< $p"; echo "> ${p%%=*} unset"; done) | sort)
ok "T4 clean: only the five deleted rows differ" "$([ "$(grep '^[<>]' "$WK/t4-clean.diff" | sort)" = "$want" ] && echo 1)"
read -r -a LE <<< "$(echo $LAUNCHER)"
o=$(run t_new TITLE2 "${LE[@]}"); oo=$(run t_old TITLE2 "${LE[@]}")
diff <(echo "$oo") <(echo "$o") > "$WK/t4-launcher.diff"
echo "T4 second title with play-pkg.sh's words, old -> new:"; cat "$WK/t4-launcher.diff"
want=$( (for p in BC5_GUARD_LEARN_LOG=2 BC5_GUARD_SPLIT=1 BC5_DIRECT_ALIASES=1 BC5_DIRECT_HOST_INDIRECT=learn:1100000000; do echo "< $p"; echo "> ${p%%=*} unset"; done) | sort)
ok "T4 with play-pkg.sh's words: only the four gone learned words differ (set -> unset)" "$([ "$(grep '^[<>]' "$WK/t4-launcher.diff" | sort)" = "$want" ] && echo 1)"
echo "$o" > "$WK/t4-launcher.txt"
o=$(run t_new TITLE2 BC5_DIRECT_LAZY_RELEASE=0); oo=$(run t_old TITLE2 BC5_DIRECT_LAZY_RELEASE=0)
ok "T4 LAZY_RELEASE=0: old forced 30,eager, new 0" "$([ "$(val "$oo" BC5_DIRECT_LAZY_RELEASE)" = 30,eager ] && [ "$(val "$o" BC5_DIRECT_LAZY_RELEASE)" = 0 ] && echo 1)"
o=$(run t_new TITLE1B BC5_DIRECT_LAZY_RELEASE=7); oo=$(run t_old TITLE1B BC5_DIRECT_LAZY_RELEASE=7)
ok "T4 the first title LAZY_RELEASE=7: old removed it (kTitleForced), new keeps 7" "$(unset_in "$oo" BC5_DIRECT_LAZY_RELEASE | grep -q 1 && [ "$(val "$o" BC5_DIRECT_LAZY_RELEASE)" = 7 ] && echo 1)"
# T5
o=$(run t_new TITLE2 KYTY_BC5_TITLE_DEFAULTS=0)
g=1; for p in $MOVED; do [ "$(val "$o" "${p%%=*}")" = "${p#*=}" ] || g=0; done
ok "T5 TITLE_DEFAULTS=0: the 28 moved words stay" "$g"
g=1; for w in $LEFT; do [ "$(unset_in "$o" "$w")" = 1 ] || g=0; done
ok "T5 TITLE_DEFAULTS=0: the 8 left rows go" "$g"
# T6 (tag nl442)
for w in $GONE; do
    e=$(env -i PATH=/usr/bin:/bin TG_WORDS="$w" "$w=x1" "$WK/t_new" --game "$WK/g/TITLE2" 2>&1 > "$WK/t6.out")
    ok "T6 $w=x1: unset after Apply()" "$(grep -qx "$w unset" "$WK/t6.out" && echo 1)"
    ok "T6 $w=x1: reported as ignored" "$(grep -qF "[bc5] exp 0442: $w=x1 is set, but the word is gone (nothing learned is read): ignored" <<< "$e" && echo 1)"
    o=$(env -i PATH=/usr/bin:/bin TG_WORDS="$w" "$w=x1" "$WK/t_old" --game "$WK/g/TITLE2" 2> /dev/null)
    ok "T6 $w=x1: the old header did not take it out" "$(grep -qx "$w unset" <<< "$o" || echo 1)"
done
# T7 (bake 1a, LEAN_GONE=1): the lean build carries no gone-words report
if [ "${LEAN_GONE:-0}" = 1 ]; then
    g++ -std=c++20 -O1 -Wall -Wextra -Werror -DBC5_LEAN -I "$NEW" -o "$WK/t_lean" "$SRC" || { echo "FAIL compile new lean"; exit 1; }
    for w in $GONE; do
        e=$(env -i PATH=/usr/bin:/bin TG_WORDS="$w" "$w=x1" "$WK/t_lean" --game "$WK/g/TITLE2" 2>&1 > "$WK/t7.out")
        ok "T7 lean $w=x1: no report" "$(grep -qF "[bc5] exp 0442: $w" <<< "$e" || echo 1)"
        ok "T7 lean $w=x1: left as set (no reader in lean)" "$(grep -qx "$w=x1" "$WK/t7.out" && echo 1)"
    done
    ok "T7 lean: the gone-words table is not in the lean binary" "$(strings "$WK/t_lean" | grep -qx BC5_DIRECT_LEARN_GUEST_ONLY || echo 1)"
fi
# T8 (bake 1d, RT_OUT=<dir>): exp 0273's switch is gone from the three sources; an old RayTracing line is accepted and
# ignored (the parse branch returns true before any value check, writes nothing back); nothing drops a dispatch for ray tracing
if [ -n "${RT_OUT:-}" ]; then
    for w in g_rt_on g_rt_pending g_rt_dropped SetRayTracing GetRayTracing ApplyPendingRayTracing 'getenv("KYTY_BC5_RT")' 'pgm_list("KYTY_BC5_RT_BUILD_PGM")' '"ray tracing off'; do
        ok "T8 bc5LleAgc.cpp holds no $w" "$(grep -qF "$w" "$RT_OUT/bc5LleAgc.cpp" || echo 1)"
    done
    for w in SetRayTracing GetRayTracing '"Ray tracing"' 'SaveTitleSwitch("RayTracing"'; do
        ok "T8 hostMenu.cpp holds no $w" "$(grep -qF "$w" "$RT_OUT/hostMenu.cpp" || echo 1)"
    done
    for w in m_ray_tracing SetRayTracing 'RayTracing()' '"RayTracing." + '; do
        ok "T8 hostInput.cpp holds no $w" "$(grep -qF "$w" "$RT_OUT/hostInput.cpp" || echo 1)"
    done
    br=$(awk '/EqualNoCase\(left.substr\(0, 11\), "RayTracing."\)/{f=1} f{print} f&&/^\t\t}$/{exit}' "$RT_OUT/hostInput.cpp")
    ok "T8 the RayTracing branch exists once" "$([ "$(grep -c '"RayTracing."' "$RT_OUT/hostInput.cpp")" = 1 ] && echo 1)"
    ok "T8 the RayTracing branch returns true and has no Fail or write-back" "$(grep -q "return true;" <<< "$br" && ! grep -q "Fail(\|emplace_back\|m_other_title_scales" <<< "$br" && echo 1)"
fi
echo "== test0442: $PASS passed, $FAIL failed"
[ "$FAIL" = 0 ]
