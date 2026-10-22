# Synthetic test data for the media: gamelist + pictures for some .mra files.
# Usage: python3 tools/fe/testdata/mkmedia.py <frontier folder>   (e.g. a copy of tools/fe/sd/frontier)
# On the MiSTer: tar -C <folder> -cf - gamelists media | mssh "tar -C /media/fat/frontier -xf -" then F5.
import sys, os, random
from PIL import Image, ImageDraw, ImageFont
out = sys.argv[1]
games = ["1942 (Revision B)", "1943 Kai Midway Kaisen (Japan)", "1943 The Battle of Midway (Euro)",
         "1941 Counter Attack (World 900227)", "1944 The Loop Master (Europe 000620)", "19XX The War Against Destiny (Europe 960104)",
         "Bubble Bobble", "Donkey Kong (US set 1)"]
font = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
for d in ["gamelists/arcade", "media/arcade/snap", "media/arcade/box", "media/arcade/marquee", "media/folders/snap"]:
    os.makedirs(os.path.join(out, d), exist_ok=True)
random.seed(1)
xml = ['<?xml version="1.0"?>', '<gameList>']
for i, g in enumerate(games):
    c = (random.randint(40, 200), random.randint(40, 200), random.randint(40, 200))
    im = Image.new("RGB", (448 if i % 2 else 320, 336 if i % 2 else 240), c)
    dr = ImageDraw.Draw(im)
    for k in range(0, im.width, 16): dr.line([(k, 0), (k, im.height)], fill=(c[0]//2, c[1]//2, c[2]//2))
    dr.text((10, 10), "SNAP\n" + g, fill="white", font=ImageFont.truetype(font, 20))
    im.save(os.path.join(out, "media/arcade/snap", g + (".jpg" if i % 2 else ".png")), quality=85)
    if i % 3 != 2:
        b = Image.new("RGBA", (300, 420), (0, 0, 0, 0))
        dr = ImageDraw.Draw(b)
        dr.rounded_rectangle([0, 0, 299, 419], 18, fill=(c[2], c[0], c[1], 255), outline="white", width=4)
        dr.text((20, 40), "BOX\n" + g[:12], fill="white", font=ImageFont.truetype(font, 28))
        b.save(os.path.join(out, "media/arcade/box", g + ".png"))
    desc = ("Test description for %s. The player flies a plane &amp; must survive waves "
            "of enemies, collecting power-ups. Long text to check the automatic line wrap and the cut "
            "with the dots when there is no more space in the area." % g)
    xml.append('  <game>\n    <path>./%s.mra</path>\n    <name>%s</name>\n    <desc>%s</desc>\n'
               '    <releasedate>19%02d0101T000000</releasedate>\n    <developer>Capcom</developer>\n'
               '    <publisher>Capcom</publisher>\n    <genre>Shoot\'em up / Verticale</genre>\n    <players>1-2</players>\n'
               '    <rating>0.%d</rating>\n  </game>' % (g.replace("&", "&amp;"), g.split(" (")[0], desc, 84 + i, 4 + i))
xml.append('</gameList>')
open(os.path.join(out, "gamelists/arcade/gamelist.xml"), "w").write("\n".join(xml) + "\n")
im = Image.new("RGB", (640, 360), (30, 60, 120)); ImageDraw.Draw(im).text((20, 150), "ARCADE CATEGORY", fill="white", font=ImageFont.truetype(font, 40))
im.save(os.path.join(out, "media/folders/snap/Arcade.png"))
print("ok", out)
