import sys
p = sys.argv[1]
s = open(p).read()
o = '    bash "$N/sample446.sh" "$R/$t-io.txt" $((SECS + 30)) & local ip=$!  # exp 0446: per-second I/O and memory samples\n'
n = o + ('    local lp="" w2=() w\n'
         '    for w in "${words[@]}"; do case "$w" in X446_LOAD=*) bash "$N/load446.sh" "${w#X446_LOAD=}" 40 $((SECS - 40)) "$R/$t-load.txt" & lp=$! ;; *) w2+=("$w") ;; esac; done\n'
         '    words=("${w2[@]}")  # exp 0446: X446_LOAD=reader|writer|both starts a background disk load at t40\n')
assert s.count(o) == 1
s = s.replace(o, n)
o2 = '    kill "$ip" 2> /dev/null; wait "$ip" 2> /dev/null\n'
n2 = o2 + '    [ -n "$lp" ] && wait "$lp" 2> /dev/null\n'
assert s.count(o2) == 1
s = s.replace(o2, n2)
open(p + ".new", "w").write(s)
print("ok")
