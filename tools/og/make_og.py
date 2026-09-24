import re, glob, os
from PIL import Image, ImageDraw, ImageFont
from og_diagrams import DIAGRAMS

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BLOG = f"{ROOT}/themes/aafu/content/blog"
IMG = f"{ROOT}/themes/aafu/static/images"
OUT = f"{IMG}/og"
os.makedirs(OUT, exist_ok=True)

W, H = 1200, 630
BG, FG, MUTED, ACCENT = (37, 38, 39), (240, 240, 240), (160, 160, 165), (94, 196, 182)
BOLD = "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf"
REG = "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf"

# Main image per post: first diagram in the body, overridden where a later one reads better as a thumbnail.
OVERRIDE = {
    "numa-the-performance-bug-that-never-throws": "numa-uma-vs-numa.png",
    "content-piracy-by-authorized-users": "antipiracy-the-lock-works.png",
    "anti-piracy-designing-after-authorization": "antipiracy-signal-stack.png",
}

def wrap(draw, text, font, width):
    lines, cur = [], ""
    for w in text.split():
        t = (cur + " " + w).strip()
        if draw.textlength(t, font=font) <= width:
            cur = t
        else:
            lines.append(cur); cur = w
    lines.append(cur)
    return lines

def fit_title(draw, title, width, sizes, max_lines):
    for s in sizes:
        f = ImageFont.truetype(BOLD, s)
        lines = wrap(draw, title, f, width)
        if len(lines) <= max_lines:
            return f, lines
    return f, lines[:max_lines]

def card(slug, title, image, out):
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    pad = 60
    d.rectangle([0, 0, 12, H], fill=ACCENT)
    small = ImageFont.truetype(REG, 24)
    d.text((pad, 40), "nenadlazic.github.io", font=small, fill=ACCENT)
    if image:
        f, lines = fit_title(d, title, W - 2 * pad, [50, 44, 40, 36], 2)
    else:
        f, lines = fit_title(d, title, W - 2 * pad, [72, 64, 56, 50], 3)
    y = 90 if image else 150
    lh = int(f.size * 1.22)
    for l in lines:
        d.text((pad, y), l, font=f, fill=FG); y += lh
    footer_y = H - 60
    d.text((pad, footer_y), "Nenad Lazić  ·  Software Architect", font=small, fill=MUTED)
    if image:
        top, bottom = y + 20, footer_y - 25
        box_w, box_h = W - 2 * pad, bottom - top
        if callable(image):
            # render at 2x and downscale, for anti-aliased lines and text
            src = image((box_w - 30) * 2, (box_h - 30) * 2).convert("RGBA")
        else:
            src = Image.open(f"{IMG}/{image}")
            src.seek(0)
            src = src.convert("RGBA")
        panel = Image.new("RGB", (box_w, box_h), (255, 255, 255))
        s = min((box_w - 30) / src.width, (box_h - 30) / src.height)
        src = src.resize((int(src.width * s), int(src.height * s)), Image.LANCZOS)
        panel.paste(src, ((box_w - src.width) // 2, (box_h - src.height) // 2), src)
        mask = Image.new("L", panel.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, box_w, box_h], 14, fill=255)
        im.paste(panel, (pad, top), mask)
    im.save(out, optimize=True)

rows = []
for p in sorted(glob.glob(f"{BLOG}/*.md")):
    slug = os.path.basename(p)[:-3]
    if slug == "_index":
        continue
    txt = open(p, encoding="utf-8").read()
    if re.search(r"^draft:\s*true", txt, re.M):
        continue
    title = re.search(r'^title:\s*"(.*)"', txt, re.M).group(1)
    imgs = [i for i in re.findall(r"!\[[^\]]*\]\(/images/([^)]+)\)", txt) if os.path.exists(f"{IMG}/{i}")]
    image = OVERRIDE.get(slug) or (imgs[0] if imgs else None) or DIAGRAMS.get(slug)
    card(slug, title, image, f"{OUT}/{slug}.png")
    rows.append((slug, title, image if isinstance(image, str) or image is None else "generated diagram"))

card("default", "Software architecture, media systems and the failure modes nobody logs", None, f"{IMG}/default-preview.png")
rows.append(("../default-preview", "(default - home page, blog list)", None))

os.makedirs(f"{ROOT}/out", exist_ok=True)
with open(f"{ROOT}/out/og-preview.html", "w", encoding="utf-8") as h:
    h.write("<!doctype html><meta charset=utf-8><title>OG preview</title><body style='background:#eee;font-family:sans-serif;padding:20px'>")
    for slug, title, image in rows:
        h.write(f"<h3>{slug}</h3><p>source image: {image or 'none (title only)'}</p>"
                f"<img src='../themes/aafu/static/images/og/{slug}.png' width=600 style='border:1px solid #ccc'><hr>")
for r in rows: print(r)
