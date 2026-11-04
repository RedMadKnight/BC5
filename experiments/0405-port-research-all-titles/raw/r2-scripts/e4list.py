# Print rank, ID and a short What for the e4-now rows of tables.md.
import re, sys
p = sys.argv[1]
for line in open(p, encoding='utf-8'):
    m = re.match(r'^\| (\d+) \| ', line)
    if not m:
        continue
    cells = [c.strip() for c in re.split(r'(?<!\\)\|', line.strip().strip('|'))]
    if not cells[8].startswith('e4-now'):
        continue
    what = re.sub(r'`', '', cells[2])
    print(cells[0] + '. ' + cells[1] + ': ' + what[:70])
