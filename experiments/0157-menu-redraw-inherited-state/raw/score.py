import sys, glob, re
from PIL import Image
fs = sorted(glob.glob("shots%s/s*.png" % sys.argv[1]), key=lambda f:int(re.findall(r"s(\d+)\.png",f)[0]))
flag = []
for f in fs:
    im = Image.open(f).convert("RGB"); w,h = im.size
    box = im.convert("HSV").crop((0, int(h*0.08), int(w*0.55), int(h*0.70))).resize((440,248))
    px = list(box.getdata()); col = 100.0*sum(1 for H,S,V in px if S>80 and V>50)/len(px)
    if col > 1.0: flag.append((f.split("/")[1], round(col,2)))
print(sys.argv[1], "flagged", len(flag), "of", len(fs), flag)
