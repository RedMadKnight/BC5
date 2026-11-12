import sys
p, o = sys.argv[1], sys.argv[2]
s = open(p, encoding="utf-8").read()
a = "  astro)\n"
assert s.count(a) == 1
s = s.replace(a, "  astro | astrolog)\n")
b = "    bash -n \"$LAUNCH\" && chmod +x \"$LAUNCH\" || exit 1 ;;\n"
assert s.count(b) == 1
s = s.replace(b, "    if [ \"$KIND\" = astrolog ]; then  # the emulator's own call log, to a file (no rebuild)\n"
                 "      sed -i \"s#--printf-direction Silent#--printf-direction File --printf-output-file $R/$TAG-calls.log#\" \"$LAUNCH\"\n"
                 "      grep -q -- \"--printf-output-file $R/$TAG-calls.log\" \"$LAUNCH\" || { echo \"no call-log edit\"; exit 1; }\n"
                 "    fi\n" + b)
c = "  *) echo \"lean or astro\"; exit 1 ;;\n"
assert s.count(c) == 1
open(o, "w", encoding="utf-8", newline="\n").write(s)
print("ok")
