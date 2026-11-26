#!/usr/bin/env bash
# BC5 exp 0439 (tag rc439, top's order of 11-22 night): every kSoft row of the compiled header must be effective in the
# run's start-up print (bl439's "effective words" line, which lists the bake-2 rows): a row whose name is printed with
# another value, or "(unset)", fails. Catches a build whose executable applies an older table (b2fix).
#   rowcheck439.sh <play-last.log> <switch_defaults.hpp>   exit 0 = all printed rows effective
L=${1:?log}; H=${2:?header}
line=$(grep -a -m1 "effective words" "$L") || { echo "rowcheck: no effective-words line in $L"; exit 2; }
bad=0; n=0
while read -r name val; do
    got=$(echo "$line" | tr ' ' '\n' | grep -a "^$name=" | head -1 | cut -d= -f2-)
    [ -z "$got" ] && continue # not in the printed list
    n=$((n + 1))
    if [ "$got" != "$val" ]; then echo "rowcheck: $name is '$got', the header says '$val'"; bad=1; fi
done < <(awk '/inline constexpr Default kSoft\[\]/{f=1} f && /nullptr, nullptr/{exit} f' "$H" | grep -o '{"[A-Z0-9_]*", "[^"]*"}' | sed 's/{"\([^"]*\)", "\([^"]*\)"}/\1 \2/')
echo "rowcheck: $n printed kSoft rows checked, $([ $bad = 0 ] && echo all effective || echo FAILED)"
exit $bad
