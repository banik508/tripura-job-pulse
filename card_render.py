"""
Tripura Job Pulse - job card renderer (no browser needed)

Draws the same card as admin-cards.html, using Pillow instead of the
browser canvas, so a scheduled script can make the images.

  from card_render import render_card, caption_for
  png_bytes = render_card(job, "square")
"""

import io
import os
from datetime import datetime

import qrcode
from PIL import Image, ImageDraw, ImageFont

SITE = os.environ.get("SITE_URL", "https://tripurajobpulse.com").rstrip("/")
FONT_DIR = os.environ.get("FONT_DIR", "fonts")

TEAL = (14, 79, 76)
GOLD = (217, 161, 59)
PAPER = (244, 248, 246)
MUTED = (183, 207, 203)
WHITE = (255, 255, 255)

SIZES = {"square": (1080, 1080), "portrait": (1080, 1350), "story": (1080, 1920)}


# ---------------------------------------------------------------- fonts
_font_cache = {}


def sora(size, weight=700):
    key = ("sora", size, weight)
    if key not in _font_cache:
        f = ImageFont.truetype(os.path.join(FONT_DIR, "Sora.ttf"), size)
        try:
            f.set_variation_by_axes([weight])
        except Exception:
            pass
        _font_cache[key] = f
    return _font_cache[key]


def hind(size, weight=400):
    name = {400: "Regular", 500: "Medium", 600: "SemiBold", 700: "Bold"}.get(weight, "Regular")
    key = ("hind", size, name)
    if key not in _font_cache:
        _font_cache[key] = ImageFont.truetype(
            os.path.join(FONT_DIR, f"HindSiliguri-{name}.ttf"), size
        )
    return _font_cache[key]


# ---------------------------------------------------------------- helpers
def wrap(text, font, max_width, max_lines):
    """Break text into at most max_lines lines, adding an ellipsis if cut short."""
    words = str(text).split()
    if not words:
        return []
    lines, line = [], ""
    for w in words:
        test = f"{line} {w}".strip()
        if font.getlength(test) > max_width and line:
            lines.append(line)
            line = w
            if len(lines) == max_lines:
                break
        else:
            line = test
    if len(lines) < max_lines and line:
        lines.append(line)
    if len(lines) == max_lines and " ".join(words) != " ".join(lines):
        last = lines[-1]
        while font.getlength(last + "…") > max_width and len(last) > 4:
            last = last[:-1]
        lines[-1] = last + "…"
    return lines


def gradient(w, h):
    """Diagonal teal gradient, matching the canvas version."""
    stops = [(0.0, (11, 58, 56)), (0.55, TEAL), (1.0, (20, 97, 92))]
    small = Image.new("RGB", (64, 64))
    px = small.load()
    denom = 64 * 64 + 64 * 64
    for y in range(64):
        for x in range(64):
            t = (x * 64 + y * 64) / denom
            for i in range(len(stops) - 1):
                t0, c0 = stops[i]
                t1, c1 = stops[i + 1]
                if t0 <= t <= t1:
                    k = (t - t0) / (t1 - t0)
                    px[x, y] = tuple(round(c0[j] + (c1[j] - c0[j]) * k) for j in range(3))
                    break
            else:
                px[x, y] = stops[-1][1]
    return small.resize((w, h), Image.BICUBIC)


def person_figure(layer, cx, cy, scale, alpha):
    """Faint figure with a briefcase, sitting behind the content."""
    d = ImageDraw.Draw(layer)
    a = int(round(alpha * 255))
    white = WHITE + (a,)
    gold = GOLD + (a,)

    def P(x, y):
        return (cx + x * scale, cy + y * scale)

    r = 34 * scale
    hx, hy = P(0, -96)
    d.ellipse([hx - r, hy - r, hx + r, hy + r], fill=white)

    body = [P(-62, 0), P(-58, -46), P(-30, -56), P(0, -58),
            P(30, -56), P(58, -46), P(62, 0)]
    d.polygon(body, fill=white)

    x0, y0 = P(40, -24)
    x1, y1 = P(94, 16)
    d.rounded_rectangle([x0, y0, x1, y1], radius=7 * scale, fill=gold)
    d.line([P(56, -24), P(56, -34), P(78, -34), P(78, -24)],
           fill=gold, width=max(1, int(6 * scale)), joint="curve")


def logo(layer, x, y, s=1.0):
    """Briefcase mark used beside the wordmark."""
    d = ImageDraw.Draw(layer)
    paper = PAPER + (255,)

    def P(px, py):
        return (x + px * s, y + py * s)

    d.rounded_rectangle([P(0, 14), P(64, 54)], radius=7 * s, fill=paper)
    d.line([P(22, 14), P(22, 6), P(42, 6), P(42, 14)],
           fill=paper, width=max(1, int(6 * s)), joint="curve")
    d.line([P(10, 34), P(24, 34), P(30, 24), P(38, 44), P(44, 34), P(56, 34)],
           fill=GOLD + (255,), width=max(1, int(5 * s)), joint="curve")


def qr_image(text, size):
    q = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, border=0)
    q.add_data(text)
    q.make(fit=True)
    n = q.modules_count
    pad = 14
    cell = max(1, int((size - pad * 2) / n))
    inner = cell * n

    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, size - 1, size - 1], radius=16, fill=WHITE + (255,))
    off = (size - inner) // 2
    for r in range(n):
        for c in range(n):
            if q.modules[r][c]:
                d.rectangle(
                    [off + c * cell, off + r * cell,
                     off + c * cell + cell - 1, off + r * cell + cell - 1],
                    fill=TEAL + (255,),
                )
    return img


def pretty_date(value):
    if not value:
        return ""
    try:
        return datetime.fromisoformat(str(value)[:10]).strftime("%-d %B %Y")
    except Exception:
        try:
            return datetime.fromisoformat(str(value)[:10]).strftime("%d %B %Y")
        except Exception:
            return str(value)[:10]


def card_from_job(job):
    def ok(v):
        return v and str(v).strip().lower() != "not specified"

    place = ", ".join(x for x in [job.get("city"), job.get("state")] if x)
    rows = [(l, v) for l, v in [
        ("Location", place),
        ("Experience", job.get("experience")),
        ("Qualification", job.get("qualification")),
        ("Vacancies", job.get("vacancies")),
        ("Salary", job.get("salary")),
    ] if ok(v)]

    pills = []
    jt = (job.get("job_type") or "").strip()
    if jt:
        pills.append(jt[:1].upper() + jt[1:] + " job")
    if job.get("region") == "remote":
        pills.append("Work from home")
    elif job.get("region") == "india":
        pills.append("Within India")

    return {
        "id": job["id"],
        "title": job.get("title") or "",
        "org": job.get("organisation") or "",
        "pills": pills,
        "rows": rows,
        "date_line": pretty_date(job.get("last_date")),
        "cta": "Scan to apply",
    }


# ---------------------------------------------------------------- the card
def render_card(job, size="square"):
    card = card_from_job(job)
    W, H = SIZES[size]
    M, CX = 80, W // 2

    img = gradient(W, H).convert("RGBA")
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)

    # soft rings
    faint = (255, 255, 255, 15)
    d.ellipse([W + 80 - 280, H * 0.16 - 280, W + 80 + 280, H * 0.16 + 280],
              outline=faint, width=64)
    d.ellipse([-110 - 240, H * 0.86 - 240, -110 + 240, H * 0.86 + 240],
              outline=faint, width=64)

    d.rectangle([0, 0, 17, H], fill=GOLD + (255,))
    person_figure(layer, W - 190, H - 150, 1.25 if H > 1200 else 1.05, 0.11)

    # header
    head_y = M + 10
    logo(layer, CX - 150, head_y - 10, 1.0)
    d.text((CX - 62, head_y + 18), "TRIPURA", font=sora(34, 700),
           fill=WHITE + (255,), anchor="ls")
    d.text((CX - 62, head_y + 56), "JOB PULSE", font=sora(34, 700),
           fill=GOLD + (255,), anchor="ls")
    d.line([(M, head_y + 96), (W - M, head_y + 96)], fill=(255, 255, 255, 46), width=2)

    # pills
    y = head_y + 156
    pf = hind(27, 600)
    widths = [pf.getlength(p) + 44 for p in card["pills"]]
    total = sum(widths) + 14 * max(0, len(widths) - 1)
    px = CX - total / 2
    for i, text in enumerate(card["pills"]):
        bg = GOLD + (255,) if i == 0 else (255, 255, 255, 41)
        fg = (58, 42, 6, 255) if i == 0 else WHITE + (255,)
        d.rounded_rectangle([px, y, px + widths[i], y + 50], radius=25, fill=bg)
        d.text((px + widths[i] / 2, y + 34), text, font=pf, fill=fg, anchor="ms")
        px += widths[i] + 14

    # title - shrinks a step when it needs all three lines, to leave room below
    y += 122
    tsize = 74 if H > 1200 else 64
    tf = sora(tsize, 700)
    title_lines = wrap(card["title"], tf, W - M * 2, 3)
    if len(title_lines) >= 3:
        tsize = int(tsize * 0.86)
        tf = sora(tsize, 700)
        title_lines = wrap(card["title"], tf, W - M * 2, 3)
    for line in title_lines:
        d.text((CX, y), line, font=tf, fill=WHITE + (255,), anchor="ms")
        y += int(tsize * 1.2)

    # organisation
    if card["org"]:
        y += 6
        of = hind(40, 500)
        for line in wrap(card["org"], of, W - M * 2, 2):
            d.text((CX, y), line, font=of, fill=MUTED + (255,), anchor="ms")
            y += 52

    qr_size = 210
    qr_y = H - M - qr_size - 52
    band_h = 100
    band_y = qr_y - band_h - 96

    # details - the block is squeezed to fit the space left above the date band,
    # and only trimmed when even the tightest spacing will not do
    y += 34
    rows = list(card["rows"])
    room = band_y - 34 - y
    if rows:
        scale = 1.0
        while rows:
            scale = min(1.0, room / (len(rows) * 92)) if room > 0 else 0
            if scale >= 0.62:
                break
            rows.pop()
        scale = max(0.62, min(1.0, scale)) if rows else 1.0

        gap = int(92 * scale)
        lf = hind(max(19, int(25 * scale)), 600)
        vf = hind(max(28, int(37 * scale)), 500)
        voff = int(46 * scale)
        for label, value in rows:
            if label:
                d.text((CX, y), label.upper(), font=lf,
                       fill=(255, 255, 255, 140), anchor="ms")
            shown = wrap(value, vf, W - M * 2, 1)
            if shown:
                d.text((CX, y + (voff if label else 10)), shown[0], font=vf,
                       fill=WHITE + (255,), anchor="ms")
            y += gap if label else int(54 * scale)

    # last date band
    if card["date_line"]:
        bw = min(W - M * 2, 680)
        d.rounded_rectangle([CX - bw / 2, band_y, CX + bw / 2, band_y + band_h],
                            radius=16, fill=(217, 161, 59, 46))
        d.text((CX, band_y + 38), "LAST DATE TO APPLY", font=hind(26, 600),
               fill=GOLD + (255,), anchor="ms")
        df = sora(40, 700)
        d.text((CX, band_y + 82), wrap(card["date_line"], df, bw - 60, 1)[0],
               font=df, fill=WHITE + (255,), anchor="ms")

    # QR and footer
    d.text((CX, qr_y - 34), "Full details and how to apply at", font=hind(30, 500),
           fill=(255, 255, 255, 191), anchor="ms")

    link = f"{SITE}/job.html?id={card['id']}"
    layer.alpha_composite(qr_image(link, qr_size), (int(CX - qr_size / 2), int(qr_y)))

    d.text((CX, qr_y + qr_size + 38), card["cta"], font=hind(26, 600),
           fill=GOLD + (255,), anchor="ms")
    d.text((CX, H - 34), "tripurajobpulse.com", font=sora(36, 700),
           fill=WHITE + (255,), anchor="ms")

    out = Image.alpha_composite(img, layer).convert("RGB")
    buf = io.BytesIO()
    out.save(buf, format="JPEG", quality=92, optimize=True)
    return buf.getvalue()


# ---------------------------------------------------------------- caption
def caption_for(job):
    def ok(v):
        return v and str(v).strip().lower() != "not specified"

    place = ", ".join(x for x in [job.get("city"), job.get("state")] if x)
    lines = [job["title"] + (f" — {job['organisation']}" if job.get("organisation") else ""), ""]
    if place:
        lines.append("Location: " + place)
    if ok(job.get("vacancies")):
        lines.append("Vacancies: " + str(job["vacancies"]))
    if ok(job.get("qualification")):
        lines.append("Qualification: " + str(job["qualification"]))
    if ok(job.get("experience")):
        lines.append("Experience: " + str(job["experience"]))
    if ok(job.get("salary")):
        lines.append("Salary: " + str(job["salary"]))
    if job.get("last_date"):
        lines.append("Last date: " + pretty_date(job["last_date"]))

    lines += [
        "",
        "Full details and the official apply link are on our website:",
        f"{SITE}/job.html?id={job['id']}",
        "",
        "Government jobs are free to view for everyone. New vacancies added every day.",
        "",
    ]

    tags = ["#TripuraJobs", "#JobsInTripura", "#Tripura", "#Agartala",
            "#TripuraJobPulse", "#SarkariNaukri"]
    if job.get("job_type") == "government":
        tags += ["#GovtJobs", "#TPSC"]
    if job.get("region") == "remote":
        tags += ["#WorkFromHome", "#RemoteJobs"]
    if job.get("region") == "india":
        tags.append("#JobsInIndia")
    lines.append(" ".join(tags))
    return "\n".join(lines)
