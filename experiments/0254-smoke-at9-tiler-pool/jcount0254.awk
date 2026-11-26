# BC5 experiment 0254: one pass over a GPU journal (gc/direct.log) with exp 0226's ab0226.py counts: cpu-wait GIVEN UP,
# two rings NOT served, hold tail ... GIVEN UP, TIMEOUT (not hold tail lines), the hold lines and the last
# "hold tail: N holds" summary; exp 0195's "cs prefix" lines (F254) with the first one; and patch_0195's alias_learn
# guard acting ("aliases: fault ...: no guest memory at ..., not learned") with the first one.
# usage: awk -f jcount0254.awk <direct.log>
/^cpu-wait / && /GIVEN UP/ {cg++} /^two rings/ && /NOT served/ {ns++}
/^hold tail: the wait on / && /GIVEN UP/ {hg++} /TIMEOUT/ && !/^hold tail/ {to++}
/^hold tail: the game thread.s chain is held/ {hl++} /^hold tail: [0-9]+ holds;/ {sum = $0}
/^cs prefix \(exp 0195\)/ {cp++; if (cp == 1) cf = $0}
/^aliases: fault / && /no guest memory at .*not learned/ {al++; if (al == 1) af = $0}
END {printf "journal: cpu-wait GIVEN UP %d, two rings NOT served %d, hold tail GIVEN UP %d, TIMEOUT %d, hold lines %d, cs prefix lines %d, alias not-learned lines %d\n", cg, ns, hg, to, hl, cp, al
print "journal last summary: " (sum == "" ? "none" : sum)
print "journal first cs prefix: " (cf == "" ? "none" : substr(cf, 1, 300))
print "journal first alias not learned: " (af == "" ? "none" : substr(af, 1, 300))}
