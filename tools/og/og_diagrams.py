# Simple drawio-style illustrations for posts that have no diagram of their own.
# Each function takes the panel size in pixels and returns an RGB image of that size.
from PIL import Image, ImageDraw, ImageFont

BOLD = "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf"
REG = "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf"
MONO = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"

# drawio default palette: (fill, stroke)
BLUE = ((218, 232, 252), (108, 142, 191))
GREEN = ((213, 232, 212), (130, 179, 102))
YELLOW = ((255, 242, 204), (214, 182, 86))
RED = ((248, 206, 204), (184, 84, 80))
PURPLE = ((225, 213, 231), (150, 115, 166))
GREY = ((245, 245, 245), (102, 102, 102))
INK = (40, 40, 40)
SOFT = (110, 110, 110)


class Canvas:
    """Coordinates are in a 1000 x (1000*h/w) unit space, so layouts do not depend on the panel size."""

    def __init__(self, w, h):
        self.im = Image.new("RGB", (w, h), (255, 255, 255))
        self.d = ImageDraw.Draw(self.im)
        self.k = w / 1000
        self.H = h / self.k

    def s(self, v):
        return int(v * self.k)

    def font(self, size, kind=REG):
        return ImageFont.truetype(kind, self.s(size))

    def box(self, x, y, w, h, style, lines, size=22, kind=BOLD, radius=10, dashed=False):
        fill, stroke = style
        xy = [self.s(x), self.s(y), self.s(x + w), self.s(y + h)]
        if dashed:
            self.d.rounded_rectangle(xy, self.s(radius), fill=fill)
            self.dashed_rect(x, y, w, h, stroke)
        else:
            self.d.rounded_rectangle(xy, self.s(radius), fill=fill, outline=stroke, width=max(2, self.s(2)))
        if isinstance(lines, str):
            lines = [lines]
        self.text_block(x + w / 2, y + h / 2, lines, size, kind)

    def text_block(self, cx, cy, lines, size, kind=BOLD, color=INK):
        f = self.font(size, kind)
        lh = size * 1.3
        top = cy - lh * len(lines) / 2
        for i, l in enumerate(lines):
            if isinstance(l, tuple):
                l, lf, lc = l
                f2 = self.font(size, lf)
            else:
                f2, lc = f, color
            self.d.text((self.s(cx), self.s(top + lh * i + lh / 2)), l, font=f2, fill=lc, anchor="mm")

    def text(self, x, y, t, size, kind=REG, color=INK, anchor="lm"):
        self.d.text((self.s(x), self.s(y)), t, font=self.font(size, kind), fill=color, anchor=anchor)

    def dashed_rect(self, x, y, w, h, color, dash=12):
        for (x1, y1, x2, y2) in [(x, y, x + w, y), (x, y + h, x + w, y + h), (x, y, x, y + h), (x + w, y, x + w, y + h)]:
            self.dashed_line(x1, y1, x2, y2, color, dash)

    def dashed_line(self, x1, y1, x2, y2, color, dash=12, width=2):
        import math
        L = math.hypot(x2 - x1, y2 - y1)
        n = int(L / dash)
        for i in range(0, n, 2):
            a, b = i / n, min((i + 1) / n, 1)
            self.d.line([self.s(x1 + (x2 - x1) * a), self.s(y1 + (y2 - y1) * a),
                         self.s(x1 + (x2 - x1) * b), self.s(y1 + (y2 - y1) * b)], fill=color, width=self.s(width))

    def arrow(self, x1, y1, x2, y2, color=SOFT, width=3):
        import math
        self.d.line([self.s(x1), self.s(y1), self.s(x2), self.s(y2)], fill=color, width=self.s(width))
        a = math.atan2(y2 - y1, x2 - x1)
        L = 14
        p = [(x2, y2), (x2 - L * math.cos(a - 0.4), y2 - L * math.sin(a - 0.4)),
             (x2 - L * math.cos(a + 0.4), y2 - L * math.sin(a + 0.4))]
        self.d.polygon([(self.s(px), self.s(py)) for px, py in p], fill=color)


def compute_cost(w, h):
    c = Canvas(w, h)
    H = c.H
    x0, x1, yb, yt = 90, 960, H - 45, 20
    # break-even around 55% utilization, as stated in the post (~50-60%)
    bx = x0 + (x1 - x0) * 0.55
    c.d.rectangle([c.s(x0), c.s(yt), c.s(bx), c.s(yb)], fill=(236, 243, 253))
    c.d.rectangle([c.s(bx), c.s(yt), c.s(x1), c.s(yb)], fill=(234, 245, 233))
    c.arrow(x0, yb, x1 + 20, yb, INK, 3)
    c.arrow(x0, yb, x0, yt - 10, INK, 3)
    c.text((x0 + x1) / 2, yb + 22, "sustained utilization", 19, REG, SOFT, "mm")
    c.d.text((c.s(x0 - 40), c.s((yt + yb) / 2)), "cost", font=c.font(19), fill=SOFT, anchor="mm")
    own_y = yb - (yb - yt) * 0.55
    c.d.line([c.s(x0), c.s(own_y), c.s(x1), c.s(own_y)], fill=GREEN[1], width=c.s(5))
    c.d.line([c.s(x0), c.s(yb), c.s(x1), c.s(yt)], fill=BLUE[1], width=c.s(5))
    c.dashed_line(bx, yt, bx, yb, RED[1], 10, 3)
    c.text(x0 + 15, yt + 22, "rent wins", 24, BOLD, BLUE[1])
    c.text(x1 - 15, yb - 22, "own wins", 24, BOLD, GREEN[1], "rm")
    c.text(x0 + 15, own_y - 20, "own: capex + power + people", 19, BOLD, GREEN[1])
    c.text(780, yt + 15, "rent: pay per hour", 19, BOLD, BLUE[1], "rm")
    c.text(bx + 12, yb - 48, "break-even", 19, BOLD, RED[1])
    c.text(bx + 12, yb - 24, "~50-60%", 19, REG, RED[1])
    return c.im


def release_notes(w, h):
    c = Canvas(w, h)
    H = c.H
    dx, dy, dw, dh = 40, 20, 400, H - 40
    c.d.rounded_rectangle([c.s(dx), c.s(dy), c.s(dx + dw), c.s(dy + dh)], c.s(10), fill=(252, 252, 252),
                          outline=GREY[1], width=c.s(2))
    c.d.rectangle([c.s(dx), c.s(dy), c.s(dx + dw), c.s(dy + 55)], fill=BLUE[0])
    c.text(dx + 20, dy + 28, "Release 1.21.0", 24, BOLD)
    items = [("Features", GREEN[1]), ("Bug fixes", BLUE[1]), ("Breaking changes", RED[1]),
             ("Deployment notes", YELLOW[1]), ("Compatibility", PURPLE[1])]
    step = (dh - 75) / len(items)
    for i, (t, col) in enumerate(items):
        y = dy + 70 + step * i + step / 2
        c.d.ellipse([c.s(dx + 22), c.s(y - 8), c.s(dx + 38), c.s(y + 8)], fill=col)
        c.text(dx + 52, y, t, 21, BOLD)
        c.d.line([c.s(dx + 250), c.s(y), c.s(dx + dw - 25), c.s(y)], fill=(215, 215, 215), width=c.s(6))
    readers = [("Developers", BLUE), ("QA", YELLOW), ("Support", GREEN), ("Product", PURPLE), ("Clients", RED)]
    bh = min(52, (H - 40) / 5 - 10)
    gap = (H - 40 - bh * 5) / 4
    for i, (t, st) in enumerate(readers):
        y = 20 + i * (bh + gap)
        c.box(720, y, 230, bh, st, t, 21)
        c.arrow(dx + dw + 10, H / 2, 712, y + bh / 2)
    return c.im


def keycloak_migration(w, h):
    c = Canvas(w, h)
    H = c.H
    c.box(30, 20, 290, H - 40, GREY,
          ["migration scripts", ("in git", REG, SOFT), "",
           ("001_realm.sh", MONO, INK), ("002_clients.sh", MONO, INK), ("003_roles.sh", MONO, INK),
           ("004_groups.sh", MONO, INK)], 20)
    c.box(390, H / 2 - 45, 180, 90, YELLOW, [("kcadm.sh", MONO, INK), ("CI / CD", REG, SOFT)], 22)
    c.arrow(322, H / 2, 385, H / 2)
    envs = [("dev", BLUE), ("staging", PURPLE), ("prod", GREEN)]
    bh = (H - 40 - 2 * 14) / 3
    for i, (e, st) in enumerate(envs):
        y = 20 + i * (bh + 14)
        c.box(650, y, 320, bh, st, [e, ("realm · clients · roles", REG, SOFT)], 22)
        c.arrow(572, H / 2, 645, y + bh / 2)
    return c.im


def jinja(w, h):
    c = Canvas(w, h)
    H = c.H
    bh = (H - 40 - 16) / 2
    c.box(20, 20, 330, bh, YELLOW, ["template", ("image: {{ image }}", MONO, INK), ("replicas: {{ n }}", MONO, INK)], 20)
    c.box(20, 20 + bh + 16, 330, bh, BLUE, ["values.yaml", ("image: api:1.4", MONO, INK), ("n: 3", MONO, INK)], 20)
    c.box(420, H / 2 - 50, 160, 100, PURPLE, ["Jinja", ("render", REG, SOFT)], 26)
    c.arrow(352, 20 + bh / 2, 415, H / 2 - 20)
    c.arrow(352, 20 + bh * 1.5 + 16, 415, H / 2 + 20)
    outs = ["dev.yaml", "staging.yaml", "prod.yaml", "..."]
    oh = (H - 40 - 3 * 12) / 4
    for i, o in enumerate(outs):
        y = 20 + i * (oh + 12)
        c.box(660, y, 310, oh, GREEN if o != "..." else GREY, [(o, MONO, INK)], 20)
        c.arrow(582, H / 2, 655, y + oh / 2)
    return c.im


def tesseract_docker(w, h):
    c = Canvas(w, h)
    H = c.H
    c.box(15, 15, 970, H - 30, ((240, 247, 255), (29, 99, 237)), [], dashed=True)
    c.text(35, 40, "docker container", 20, BOLD, (29, 99, 237))
    top, bot = 70, H - 35
    bh = bot - top
    c.box(40, top, 270, bh, YELLOW, ["ground truth", ("sample_001.png", MONO, INK), ("sample_001.gt.txt", MONO, INK),
                                     ("...", MONO, SOFT)], 20)
    c.box(380, top, 250, bh, PURPLE, [("lstmtraining", MONO, INK), ("fine-tune from", REG, SOFT),
                                      ("eng.traineddata", MONO, SOFT)], 20)
    c.box(700, top, 260, bh, GREEN, ["custom model", ("custom.traineddata", MONO, INK)], 20)
    c.arrow(312, top + bh / 2, 375, top + bh / 2)
    c.arrow(632, top + bh / 2, 695, top + bh / 2)
    return c.im


def tesseract_ocr(w, h):
    c = Canvas(w, h)
    H = c.H
    rh = (H - 40 - 20) / 2
    c.box(20, H / 2 - 60, 250, 120, GREY, [("INVOICE No. 817", MONO, INK), ("scanned line", REG, SOFT)], 20)
    rows = [("generic model", BLUE, "lNV0ICE N0. 8I7", RED), ("fine-tuned on your data", PURPLE, "INVOICE No. 817", GREEN)]
    for i, (m, st, out, ost) in enumerate(rows):
        y = 20 + i * (rh + 20)
        c.box(350, y, 290, rh, st, m, 21)
        c.box(710, y, 270, rh, ost, [(out, MONO, INK)], 21)
        c.arrow(272, H / 2, 345, y + rh / 2)
        c.arrow(642, y + rh / 2, 705, y + rh / 2)
    return c.im


DIAGRAMS = {
    "compute-cost-calculation-buy-vs-rent": compute_cost,
    "how-to-write-release-notes": release_notes,
    "keycloak-migration-scripts": keycloak_migration,
    "templating-with-jinja": jinja,
    "tesseract-docker-fine-tuning": tesseract_docker,
    "tesseract-fine-tuning-ocr": tesseract_ocr,
}
