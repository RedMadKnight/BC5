import sys
p = sys.argv[1]
s = open(p).read()
o1 = 'sleep "$AB_SHOT_S"; el=$(( $(date +%s) - st ))'
n1 = 'if [ "$el" -ge 112 ] && [ "$el" -le 178 ]; then sleep 2; else sleep "$AB_SHOT_S"; fi; el=$(( $(date +%s) - st ))'
assert s.count(o1) == 1
s = s.replace(o1, n1)
o2 = '        gp=$!\n    fi\n'
n2 = ('        gp=$!\n    fi\n'
      '    bash "$N/sample446.sh" "$R/$t-io.txt" $((SECS + 30)) & local ip=$!  # exp 0446: per-second I/O and memory samples\n')
assert s.count(o2) == 1
s = s.replace(o2, n2)
o3 = '    [ -n "$gp" ] && { kill "$gp"'
n3 = '    kill "$ip" 2> /dev/null; wait "$ip" 2> /dev/null\n    [ -n "$gp" ] && { kill "$gp"'
assert s.count(o3) == 1
s = s.replace(o3, n3)
open(p + ".new", "w").write(s)
print("ok")
