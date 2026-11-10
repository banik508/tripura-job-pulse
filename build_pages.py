"""
Build a real, readable web page for every job, plus a sitemap.

Why this exists
---------------
job.html is a single page that fetches a job with JavaScript after checking you
are signed in. Google is never signed in and does not wait around for scripts,
so to Google the whole site looked like one page. That is why nothing ranked.

This script writes a plain HTML file per job, straight to disk, with the words
already in it. Google reads it on the first visit.

What goes on each page
----------------------
Government jobs   full details, exactly as a visitor sees them. These are free
                  for everyone anyway, and they are what people in Tripura
                  actually search for.
Private / remote  a summary only: title, organisation, where, closing date.
                  Full details and the apply link stay behind sign-in.

Google's rules say the structured data must match what a visitor can read
without signing in. So the JobPosting markup - the thing that puts a job into
the Google Jobs box - is written for government jobs only. Putting it on a
summary page would be cloaking, and sites get penalised for it.

Written to the website folder:
  job/<slug>.html   one per job
  job/index.html    a plain list, so a crawler can walk to every job
  sitemap.xml       every page, with its last-changed date
  robots.txt        points search engines at the sitemap

Run it with:  python build_pages.py
"""

import datetime as dt
import html
import json
import os
import re
import shutil
import sys
import urllib.parse

from supabase import create_client

SITE = "https://tripurajobpulse.com"
OUT = "website"
JOBDIR = os.path.join(OUT, "job")

# Pages that already exist and should be in the sitemap.
STATIC = [
    ("index.html", "1.0", "daily"),
    ("jobs.html", "0.9", "daily"),
    ("jobs-india.html", "0.8", "daily"),
    ("jobs-remote.html", "0.8", "daily"),
    ("study-material.html", "0.7", "weekly"),
    ("mock-tests.html", "0.7", "weekly"),
    ("certifications.html", "0.7", "weekly"),
    ("current-affairs.html", "0.7", "daily"),
    ("typing.html", "0.7", "monthly"),
    ("subjects.html", "0.6", "weekly"),
    ("cv.html", "0.6", "monthly"),
    ("learn.html", "0.6", "monthly"),
    ("plans.html", "0.5", "monthly"),
    ("blog.html", "0.8", "weekly"),
    ("gk.html", "0.8", "weekly"),
    ("resize.html", "0.7", "monthly"),
    ("cv-score.html", "0.7", "monthly"),
    ("salary.html", "0.7", "monthly"),
    ("privacy.html", "0.3", "yearly"),
    ("login.html", "0.3", "monthly"),
]

# A job stays online this long after its closing date, then it goes.
# Google penalises sites that keep dead vacancies in search results.
KEEP_DAYS_AFTER_CLOSE = 21


# ----------------------------------------------------------------- helpers

def slugify(text, limit=70):
    text = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    if len(text) > limit:
        text = text[:limit].rsplit("-", 1)[0]
    return text or "job"


def esc(value):
    return html.escape(str(value), quote=True) if value else ""


def safe_json(data):
    """JSON for inside a <script> tag.

    A job title is typed by hand into a spreadsheet, so one day one will
    contain an angle bracket. Left alone, '</script>' inside a title would
    close the tag early and wreck the page. Escaping the three characters
    that can start a tag keeps the JSON valid and the page intact.
    """
    text = json.dumps(data, ensure_ascii=False)
    return (text.replace("<", "\\u003C")
                .replace(">", "\\u003E")
                .replace("&", "\\u0026"))


def as_date(value):
    """Accepts a date, a datetime or a string. Returns a date or None."""
    if not value:
        return None
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    text = str(value)[:10]
    try:
        return dt.date.fromisoformat(text)
    except ValueError:
        return None


def pretty(d):
    return d.strftime("%-d %B %Y") if d else ""


def is_remote(job):
    return "remote" in {(job.get("region") or "").strip().lower(),
                        (job.get("job_type") or "").strip().lower()}


def where(job):
    # A remote job just says Remote. The company's head-office city and state
    # are not where the work happens, so printing them misleads the reader.
    if is_remote(job):
        return "Remote"
    parts = [job.get("city"), job.get("state")]
    place = ", ".join(p for p in parts if p)
    return place or job.get("location") or "Tripura"


def is_open(job):
    """Is this job public? Government jobs are free for everyone."""
    return (job.get("job_type") or "").strip().lower() == "government"


# ----------------------------------------------------------------- the page

STYLE = """
  .wrap { max-width: 760px; margin: 0 auto; padding: 32px 20px 72px; }
  .back { display:inline-block; color:var(--teal); margin-bottom:18px; text-decoration:none; }
  .back:hover { text-decoration:underline; }
  h1 { font-family:Sora,sans-serif; font-size:30px; line-height:1.25; color:var(--teal-deep); }
  .org { font-size:19px; margin-top:8px; color:var(--muted); }
  .tags { margin-top:16px; display:flex; gap:8px; flex-wrap:wrap; }
  .tag { font-size:14px; background:var(--teal-soft); color:var(--teal-deep);
         padding:5px 12px; border-radius:999px; }
  dl.details { margin-top:30px; border-top:1px solid var(--line); }
  dl.details > div { display:grid; grid-template-columns:190px 1fr; gap:16px;
                     padding:14px 0; border-bottom:1px solid var(--line); }
  dl.details dt { font-weight:600; color:var(--muted); }
  dl.details dd { margin:0; white-space:pre-line; }
  .buttons { margin-top:30px; display:flex; gap:12px; flex-wrap:wrap; }
  a.btn { text-decoration:none; display:inline-block; }
  .btn.outline { background:#fff; color:var(--teal); border:1px solid var(--teal); }
  .btn.outline:hover { background:var(--teal-soft); }
  .gate { margin-top:30px; background:#fff; border:1px solid var(--line);
          border-radius:12px; padding:26px; }
  .gate h2 { font-family:Sora,sans-serif; font-size:20px; color:var(--teal-deep); }
  .gate p { margin-top:8px; color:var(--muted); }
  .closed { margin-top:24px; background:#FBF1E3; border:1px solid #E8D5B0;
            color:#6B4E1E; padding:12px 16px; border-radius:8px; font-size:15px; }
  .foot { margin-top:48px; padding-top:20px; border-top:1px solid var(--line);
          font-size:15px; color:var(--muted); }
  .foot a { color:var(--teal); }
  @media (max-width:560px) { dl.details > div { grid-template-columns:1fr; gap:2px; }
                             h1 { font-size:25px; } }
"""


def summary_line(job):
    """The sentence Google shows under the blue link."""
    bits = [job.get("title")]
    if job.get("organisation"):
        bits.append("at " + job["organisation"])
    bits.append("in " + where(job))
    tail = []
    if job.get("vacancies"):
        tail.append(f"{job['vacancies']} vacancies")
    if job.get("qualification"):
        tail.append(str(job["qualification"]))
    close = as_date(job.get("last_date"))
    if close:
        tail.append("apply by " + pretty(close))
    line = " ".join(b for b in bits if b)
    if tail:
        joined = ", ".join(tail)
        # Capitalise the first letter only. .capitalize() would lower the rest
        # and turn "B.E. in Civil Engineering" into "b.e. in civil engineering".
        line += ". " + joined[:1].upper() + joined[1:] + "."
    return re.sub(r"\s+", " ", line).strip()[:300]


def page_title(title, org):
    """Google shows roughly 60 characters. Cut whole words, never mid-word,
    and drop the organisation rather than leave it half-written."""
    suffix = " | Tripura Job Pulse"
    room = 65 - len(suffix)
    if org and len(title) + 3 + len(org) <= room:
        return f"{title} — {org}{suffix}"
    if len(title) <= room:
        return title + suffix
    cut = title[:room]
    if " " in cut:
        cut = cut.rsplit(" ", 1)[0]
    return cut.rstrip(" ,-–—") + "…" + suffix


def job_posting_jsonld(job, url):
    """Google Jobs markup. Only for pages where a visitor reads everything."""
    posted = as_date(job.get("created_at")) or dt.date.today()
    close = as_date(job.get("last_date"))

    description = (job.get("description") or "").strip()
    if len(description) < 60:
        # Google wants a real description. Build one from the fields we have.
        lines = []
        for label, key in [("Organisation", "organisation"), ("Qualification", "qualification"),
                           ("Experience", "experience"), ("Vacancies", "vacancies"),
                           ("Salary", "salary"), ("Age limit", "age_limit"),
                           ("How to apply", "how_to_apply")]:
            if job.get(key):
                lines.append(f"{label}: {job[key]}")
        description = (description + "\n" + "\n".join(lines)).strip()
    if len(description) < 30:
        return None  # Not enough to mark up honestly.

    data = {
        "@context": "https://schema.org/",
        "@type": "JobPosting",
        "title": job.get("title"),
        "description": "<p>" + html.escape(description).replace("\n", "<br>") + "</p>",
        "datePosted": posted.isoformat(),
        "hiringOrganization": {
            "@type": "Organization",
            "name": job.get("organisation") or "Government of Tripura",
        },
        "jobLocation": {
            "@type": "Place",
            "address": {
                "@type": "PostalAddress",
                "addressLocality": job.get("city") or "Agartala",
                "addressRegion": job.get("state") or "Tripura",
                "addressCountry": "IN",
            },
        },
        "directApply": False,
        "url": url,
    }
    if is_remote(job):
        # Google's own flag for work-from-home roles
        data["jobLocationType"] = "TELECOMMUTE"
        data["applicantLocationRequirements"] = {"@type": "Country", "name": "India"}
    if close:
        data["validThrough"] = close.isoformat() + "T23:59:59+05:30"
    if job.get("vacancies"):
        try:
            data["totalJobOpenings"] = int(re.sub(r"\D", "", str(job["vacancies"])) or 0) or None
        except ValueError:
            pass
        data = {k: v for k, v in data.items() if v is not None}
    return data


def render(job, slug):
    url = f"{SITE}/job/{slug}.html"
    open_job = is_open(job)
    close = as_date(job.get("last_date"))
    expired = bool(close and close < dt.date.today())

    title = job.get("title") or "Job vacancy"
    org = job.get("organisation") or ""
    head_title = page_title(title, org)
    desc = summary_line(job)

    head = [
        '<!DOCTYPE html>', '<html lang="en">', '<head>',
        '<meta charset="UTF-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        f'<title>{esc(head_title)}</title>',
        f'<meta name="description" content="{esc(desc)}">',
        f'<link rel="canonical" href="{url}">',
    ]
    if expired:
        # Dead vacancy: stays readable for anyone holding the link, out of search.
        head.append('<meta name="robots" content="noindex, follow">')

    head += [
        f'<meta property="og:title" content="{esc(title)}">',
        f'<meta property="og:description" content="{esc(desc)}">',
        f'<meta property="og:url" content="{url}">',
        '<meta property="og:type" content="article">',
        '<meta property="og:site_name" content="Tripura Job Pulse">',
        '<meta name="twitter:card" content="summary">',
        '<link rel="preconnect" href="https://fonts.googleapis.com">',
        '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>',
        '<link href="https://fonts.googleapis.com/css2?family=Sora:wght@600;700'
        '&family=Hind+Siliguri:wght@400;500;600&display=swap" rel="stylesheet">',
        '<link rel="stylesheet" href="../style.css">',
        '<link rel="icon" href="../favicon.ico">',
        f'<style>{STYLE}</style>',
    ]

    if open_job and not expired:
        ld = job_posting_jsonld(job, url)
        if ld:
            head.append('<script type="application/ld+json">'
                        + safe_json(ld) + '</script>')

    head += ['</head>', '<body>']

    body = [
        '<header class="site-header"><div class="inner">',
        '<a class="brand" href="../index.html">Tripura <span>Job Pulse</span></a>',
        '<a class="header-link" href="../jobs.html">All jobs</a>',
        '</div></header>',
        '<main class="wrap">',
        '<a class="back" href="../jobs.html">&larr; Back to all jobs</a>',
        f'<h1>{esc(title)}</h1>',
    ]
    if org:
        body.append(f'<p class="org">{esc(org)}</p>')

    # A remote job's type and its location are both the word "Remote",
    # so show it once rather than three times across the page.
    tags, seen = [], set()
    for t in [(job.get("job_type") or "").title() or None,
              where(job),
              f"Closes {pretty(close)}" if close else None]:
        if t and t.lower() not in seen:
            seen.add(t.lower())
            tags.append(t)
    body.append('<div class="tags">' + "".join(
        f'<span class="tag">{esc(t)}</span>' for t in tags) + '</div>')

    if expired:
        body.append('<p class="closed">This vacancy has closed. '
                    'It is kept here for reference. '
                    '<a href="../jobs.html">See jobs open now</a>.</p>')

    # ---- what the visitor can read
    if open_job:
        rows = [
            ("Job type", (job.get("job_type") or "").title()),
            (None if is_remote(job) else "Location", None if is_remote(job) else where(job)),
            ("Experience", job.get("experience")),
            ("Industry", job.get("industry")),
            ("Qualification", job.get("qualification")),
            ("Vacancies", job.get("vacancies")),
            ("Salary", job.get("salary")),
            ("Age limit", job.get("age_limit")),
            ("Last date to apply", pretty(close)),
            ("How to apply", job.get("how_to_apply")),
            ("About the job", job.get("description")),
        ]
    else:
        rows = [
            ("Job type", (job.get("job_type") or "").title()),
            (None if is_remote(job) else "Location", None if is_remote(job) else where(job)),
            ("Qualification", job.get("qualification")),
            ("Last date to apply", pretty(close)),
        ]

    rows = [(k, v) for k, v in rows if v]
    body.append('<dl class="details">')
    for label, value in rows:
        body.append(f'<div><dt>{esc(label)}</dt><dd>{esc(value)}</dd></div>')
    body.append('</dl>')

    # ---- what they do next
    link = (job.get("apply_link") or "").strip()
    if open_job:
        body.append('<div class="buttons">')
        if re.match(r"^https?://", link, re.I):
            body.append(f'<a class="btn" href="{esc(link)}" target="_blank" '
                        f'rel="noopener noreferrer">Apply on official site</a>')
        elif re.match(r"^mailto:", link, re.I):
            body.append(f'<a class="btn" href="{esc(link)}">Email your application</a>')
        body.append(f'<a class="btn outline" href="../cv.html?job={esc(job["id"])}">'
                    f'Build a CV for this job</a>')
        body.append('</div>')
    else:
        body += [
            '<section class="gate">',
            '<h2>Sign in to see the full details</h2>',
            '<p>This is a private or remote vacancy. Create a free account to see '
            'the salary, the full description and the link to apply. '
            'Government jobs are always free and fully open.</p>',
            '<div class="buttons">',
            f'<a class="btn" href="../login.html?next={esc("job.html?id=" + str(job["id"]))}">'
            f'Sign in or create an account</a>',
            '<a class="btn outline" href="../jobs.html">See free government jobs</a>',
            '</div></section>',
        ]

    body += [
        '<p class="foot">Found on <a href="../index.html">Tripura Job Pulse</a> — '
        'every Tripura job, and the preparation to win it. '
        'Always check the official notification before applying.</p>',
        '</main>', '</body>', '</html>',
    ]

    return "\n".join(head + body)


# ----------------------------------------------------------------- the index

def render_index(entries):
    rows = "\n".join(
        f'<li><a href="{esc(slug)}.html">{esc(job.get("title"))}</a>'
        f'{" — " + esc(job.get("organisation")) if job.get("organisation") else ""}</li>'
        for slug, job in entries
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>All job vacancies | Tripura Job Pulse</title>
<meta name="description" content="Every government, private and remote vacancy listed on Tripura Job Pulse.">
<link rel="canonical" href="{SITE}/job/index.html">
<link rel="stylesheet" href="../style.css">
<style>
  .wrap {{ max-width:860px; margin:0 auto; padding:32px 20px 72px; }}
  h1 {{ font-family:Sora,sans-serif; color:var(--teal-deep); }}
  ul {{ margin-top:24px; line-height:2; }}
  a {{ color:var(--teal); }}
</style>
</head>
<body>
<header class="site-header"><div class="inner">
<a class="brand" href="../index.html">Tripura <span>Job Pulse</span></a>
<a class="header-link" href="../jobs.html">All jobs</a>
</div></header>
<main class="wrap">
<h1>Every vacancy on Tripura Job Pulse</h1>
<p class="lead">{len(entries)} vacancies. Government jobs are free to read in full.</p>
<ul>
{rows}
</ul>
</main>
</body>
</html>
"""


def render_sitemap(entries, posts=()):
    today = dt.date.today().isoformat()
    out = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']

    for path, priority, freq in STATIC:
        out += [f'  <url><loc>{SITE}/{path}</loc>',
                f'    <lastmod>{today}</lastmod>',
                f'    <changefreq>{freq}</changefreq>',
                f'    <priority>{priority}</priority></url>']

    out += [f'  <url><loc>{SITE}/job/index.html</loc>',
            f'    <lastmod>{today}</lastmod>'
            f'<changefreq>daily</changefreq><priority>0.7</priority></url>']

    for slug, job in entries:
        close = as_date(job.get("last_date"))
        if close and close < dt.date.today():
            continue  # closed: kept on the site, kept out of search
        changed = as_date(job.get("updated_at")) or as_date(job.get("created_at")) or dt.date.today()
        out += [f'  <url><loc>{SITE}/job/{slug}.html</loc>',
                f'    <lastmod>{changed.isoformat()}</lastmod>',
                f'    <changefreq>weekly</changefreq>',
                f'    <priority>{"0.8" if is_open(job) else "0.6"}</priority></url>']

    for p in posts:
        changed = post_date(p)
        out += [f'  <url><loc>{SITE}/blog/{p["slug"]}.html</loc>',
                f'    <lastmod>{changed.isoformat()}</lastmod>',
                f'    <changefreq>monthly</changefreq>',
                f'    <priority>0.7</priority></url>']

    out.append('</urlset>')
    return "\n".join(out)


ROBOTS = f"""User-agent: *
Allow: /

# Nothing useful behind these for a search engine
Disallow: /admin
Disallow: /admin-*.html
Disallow: /profile.html
Disallow: /verify.html
Disallow: /result.html

Sitemap: {SITE}/sitemap.xml
"""



# ===========================================================================
#  The blog
#
#  Posts are written in the admin panel and stored in Supabase. This turns
#  each published one into a real HTML page.
#
#  Why static rather than loading the post with JavaScript: when a link is
#  shared on LinkedIn, Facebook or WhatsApp, those sites fetch the page with
#  a crawler that does not run JavaScript. A page that fills itself in after
#  loading shares as a blank card with no title and no picture. The tags have
#  to be in the HTML as it leaves the server, so the page is built here.
# ===========================================================================

BLOGDIR = os.path.join(OUT, "blog")


def md_inline(text):
    """Bold, italic, links and inline code, applied to already-escaped text."""
    # links first, so the text inside them is not mangled by the rules below
    text = re.sub(r"\[([^\]]+)\]\((https?://[^\s)]+)\)",
                  r'<a href="\2" target="_blank" rel="noopener">\1</a>', text)
    # A post lives at /blog/<slug>.html, so a link written as "cv.html" would
    # resolve to /blog/cv.html and 404. Relative links get sent up one level.
    text = re.sub(r"\[([^\]]+)\]\((?!https?://|#|/|\.\./|mailto:)([^\s)]+)\)",
                  r'<a href="../\2">\1</a>', text)
    text = re.sub(r"\[([^\]]+)\]\((#|/|\.\./|mailto:)([^\s)]*)\)", r'<a href="\2\3">\1</a>', text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"<em>\1</em>", text)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    return text


def md_to_html(src):
    """A deliberately small subset of Markdown.

    Everything is HTML-escaped before any formatting is applied, so a stray
    < or an pasted tag in a post can never become live markup on the page.
    Anything not recognised below is shown as an ordinary paragraph.
    """
    lines = (src or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")
    out, para, list_type = [], [], None

    def close_para():
        if para:
            out.append("<p>" + md_inline(" ".join(para)) + "</p>")
            para.clear()

    def close_list():
        nonlocal list_type
        if list_type:
            out.append("</ul>" if list_type == "ul" else "</ol>")
            list_type = None

    for raw in lines:
        line = raw.rstrip()
        stripped = line.strip()

        if not stripped:
            close_para(); close_list()
            continue

        esc_line = esc(stripped)

        # picture on its own line
        m = re.match(r"^!\[([^\]]*)\]\(([^\s)]+)\)$", stripped)
        if m:
            close_para(); close_list()
            out.append(f'<figure><img src="{esc(m.group(2))}" alt="{esc(m.group(1))}" loading="lazy">'
                       + (f"<figcaption>{esc(m.group(1))}</figcaption>" if m.group(1) else "")
                       + "</figure>")
            continue

        if re.match(r"^-{3,}$", stripped):
            close_para(); close_list()
            out.append("<hr>")
            continue

        m = re.match(r"^(#{2,4})\s+(.*)$", esc_line)
        if m:
            close_para(); close_list()
            level = len(m.group(1))
            out.append(f"<h{level}>{md_inline(m.group(2))}</h{level}>")
            continue

        m = re.match(r"^&gt;\s?(.*)$", esc_line)      # "> quote", already escaped
        if m:
            close_para(); close_list()
            out.append(f"<blockquote>{md_inline(m.group(1))}</blockquote>")
            continue

        m = re.match(r"^[-*]\s+(.*)$", esc_line)
        if m:
            close_para()
            if list_type != "ul":
                close_list(); out.append("<ul>"); list_type = "ul"
            out.append(f"<li>{md_inline(m.group(1))}</li>")
            continue

        m = re.match(r"^\d+[.)]\s+(.*)$", esc_line)
        if m:
            close_para()
            if list_type != "ol":
                close_list(); out.append("<ol>"); list_type = "ol"
            out.append(f"<li>{md_inline(m.group(1))}</li>")
            continue

        close_list()
        para.append(esc_line)

    close_para(); close_list()
    return "\n".join(out)


def reading_time(body):
    words = len(re.findall(r"\S+", body or ""))
    return max(1, round(words / 200))


def post_date(post):
    value = post.get("published_at") or post.get("created_at")
    d = as_date(value)
    return d or dt.date.today()


def share_row(url, title):
    """Share buttons. Each one is a plain link, so they work without scripts."""
    q_url = urllib.parse.quote(url, safe="")
    q_title = urllib.parse.quote(title, safe="")
    targets = [
        ("LinkedIn", f"https://www.linkedin.com/sharing/share-offsite/?url={q_url}"),
        ("Facebook", f"https://www.facebook.com/sharer/sharer.php?u={q_url}"),
        ("WhatsApp", f"https://api.whatsapp.com/send?text={q_title}%20{q_url}"),
        ("X", f"https://twitter.com/intent/tweet?text={q_title}&url={q_url}"),
    ]
    links = "".join(
        f'<a class="share-btn" href="{esc(href)}" target="_blank" rel="noopener">{name}</a>'
        for name, href in targets
    )
    return ('<div class="share"><span class="share-label">Share this</span>'
            + links
            + f'<button class="share-btn copy" type="button" data-url="{esc(url)}">Copy link</button>'
            + "</div>")


BLOG_CSS = """
  .post { max-width: 760px; margin: 0 auto; padding: 30px 20px 80px; }
  .post .kicker { font-size: 14px; color: var(--muted); display: flex; gap: 10px;
                  flex-wrap: wrap; align-items: center; }
  .post .kicker a { color: var(--teal); }
  .post h1 { font-family: Sora, sans-serif; font-size: 36px; line-height: 1.18;
             color: var(--teal-deep); margin-top: 10px; }
  @media (max-width: 620px) { .post h1 { font-size: 27px; } }
  .post .standfirst { font-size: 19px; line-height: 1.6; color: var(--muted); margin-top: 14px; }
  .post .cover { width: 100%; border-radius: 14px; margin-top: 24px; display: block; }
  .post .tags { display: flex; gap: 7px; flex-wrap: wrap; margin-top: 16px; }
  .post .tags span { font-size: 13px; font-weight: 600; background: var(--teal-soft);
                     color: var(--teal-deep); padding: 3px 11px; border-radius: 99px; }
  .body { margin-top: 30px; font-size: 18px; line-height: 1.75; color: var(--ink); }
  .body > * + * { margin-top: 18px; }
  .body h2 { font-family: Sora, sans-serif; font-size: 25px; color: var(--teal-deep); margin-top: 38px; }
  .body h3 { font-family: Sora, sans-serif; font-size: 20px; color: var(--ink); margin-top: 28px; }
  .body h4 { font-family: Sora, sans-serif; font-size: 17px; color: var(--ink); margin-top: 22px; }
  .body ul, .body ol { padding-left: 24px; }
  .body li + li { margin-top: 8px; }
  .body a { color: var(--teal); }
  .body code { background: var(--teal-soft); color: var(--teal-deep); padding: 1px 6px;
               border-radius: 5px; font-size: .92em; }
  .body blockquote { border-left: 4px solid var(--marigold); padding: 4px 0 4px 18px;
                     color: var(--muted); font-style: italic; }
  .body figure { margin: 26px 0; }
  .body figure img { width: 100%; border-radius: 12px; display: block; }
  .body figcaption { font-size: 14px; color: var(--muted); margin-top: 8px; text-align: center; }
  .body hr { border: 0; border-top: 1px solid var(--line); margin: 32px 0; }
  .share { display: flex; gap: 8px; flex-wrap: wrap; align-items: center;
           margin-top: 44px; padding-top: 22px; border-top: 1px solid var(--line); }
  .share-label { font-size: 14px; font-weight: 600; color: var(--muted); margin-right: 4px; }
  .share-btn { font: inherit; font-size: 14px; font-weight: 600; padding: 8px 15px;
               border-radius: 8px; border: 1px solid var(--line); background: #fff;
               color: var(--teal-deep); text-decoration: none; cursor: pointer; }
  .share-btn:hover { background: var(--teal-soft); border-color: var(--teal); }
  .backlink { display: inline-block; margin-top: 34px; color: var(--teal); font-weight: 600; }
"""

COPY_SCRIPT = """
<script>
  document.querySelectorAll(".share-btn.copy").forEach(function (b) {
    b.addEventListener("click", function () {
      var url = b.dataset.url;
      var done = function () { b.textContent = "Link copied"; setTimeout(function () { b.textContent = "Copy link"; }, 2000); };
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(url).then(done, function () { window.prompt("Copy this link", url); });
      } else { window.prompt("Copy this link", url); }
    });
  });
</script>
"""


def render_post(post):
    slug = post["slug"]
    url = f"{SITE}/blog/{slug}.html"
    title = post.get("title") or "Post"
    excerpt = (post.get("excerpt") or "").strip()
    desc = excerpt or f"{title} — Tripura Job Pulse"
    cover = (post.get("cover_url") or "").strip()
    cover_alt = (post.get("cover_alt") or title).strip()
    d = post_date(post)
    mins = reading_time(post.get("body"))
    tags = [t for t in (post.get("tags") or []) if t]

    head = [
        "<!DOCTYPE html>", '<html lang="en">', "<head>",
        '<meta charset="UTF-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        f"<title>{esc(title)} | Tripura Job Pulse</title>",
        f'<meta name="description" content="{esc(desc)}">',
        f'<link rel="canonical" href="{url}">',
        f'<meta property="og:title" content="{esc(title)}">',
        f'<meta property="og:description" content="{esc(desc)}">',
        f'<meta property="og:url" content="{url}">',
        '<meta property="og:type" content="article">',
        '<meta property="og:site_name" content="Tripura Job Pulse">',
        f'<meta property="article:published_time" content="{d.isoformat()}">',
    ]
    if cover:
        head += [
            f'<meta property="og:image" content="{esc(cover)}">',
            f'<meta property="og:image:alt" content="{esc(cover_alt)}">',
            '<meta name="twitter:card" content="summary_large_image">',
        ]
    else:
        head.append('<meta name="twitter:card" content="summary">')
    head += [
        f'<meta name="twitter:title" content="{esc(title)}">',
        f'<meta name="twitter:description" content="{esc(desc)}">',
        '<link rel="preconnect" href="https://fonts.googleapis.com">',
        '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>',
        '<link href="https://fonts.googleapis.com/css2?family=Sora:wght@600;700'
        '&family=Hind+Siliguri:wght@400;500;600&display=swap" rel="stylesheet">',
        '<link rel="stylesheet" href="../style.css">',
        '<link rel="stylesheet" href="../tjp-header.css">',
        f"<style>{BLOG_CSS}</style>",
        "</head>", "<body>",
        '<div id="tjp-header"></div>',
    ]

    jsonld = {
        "@context": "https://schema.org",
        "@type": "BlogPosting",
        "headline": title,
        "description": desc,
        "datePublished": d.isoformat(),
        "author": {"@type": "Organization", "name": post.get("author") or "Tripura Job Pulse"},
        "publisher": {"@type": "Organization", "name": "Tripura Job Pulse"},
        "mainEntityOfPage": url,
    }
    if cover:
        jsonld["image"] = cover

    body = [
        '<main class="post">',
        '<p class="kicker"><a href="../blog.html">Blog</a><span>·</span>'
        f"<span>{pretty(d)}</span><span>·</span><span>{mins} min read</span></p>",
        f"<h1>{esc(title)}</h1>",
    ]
    if excerpt:
        body.append(f'<p class="standfirst">{esc(excerpt)}</p>')
    if cover:
        body.append(f'<img class="cover" src="{esc(cover)}" alt="{esc(cover_alt)}">')
    if tags:
        body.append('<div class="tags">'
                    + "".join(f"<span>{esc(t)}</span>" for t in tags)
                    + "</div>")
    body += [
        f'<div class="body">{md_to_html(post.get("body"))}</div>',
        share_row(url, title),
        '<a class="backlink" href="../blog.html">&larr; All posts</a>',
        "</main>",
        '<div id="tjp-footer"></div>',
        f'<script type="application/ld+json">{safe_json(jsonld)}</script>',
        '<script src="../config.js"></script>',
        '<script src="../tjp-header.js"></script>',
        COPY_SCRIPT,
        "</body>", "</html>",
    ]
    return "\n".join(head + body)


BLOG_INDEX_CSS = """
  .bwrap { max-width: 940px; margin: 0 auto; padding: 30px 20px 80px; }
  .bwrap h1 { font-family: Sora, sans-serif; font-size: 34px; color: var(--teal-deep); }
  .bwrap .lead { font-size: 18px; color: var(--muted); margin-top: 10px; max-width: 620px; }
  .plist { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
           gap: 20px; margin-top: 32px; }
  .pcard { background: #fff; border: 1px solid var(--line); border-radius: 14px;
           overflow: hidden; display: flex; flex-direction: column; text-decoration: none;
           transition: border-color .15s, box-shadow .15s; }
  .pcard:hover { border-color: var(--teal); box-shadow: 0 4px 16px rgba(14,79,76,.10); }
  .pcard .thumb { aspect-ratio: 16 / 9; background: var(--teal-soft); display: block;
                  width: 100%; object-fit: cover; }
  .pcard .ph { aspect-ratio: 16 / 9; background: linear-gradient(135deg, #0E4F4C, #15706B);
               display: flex; align-items: center; justify-content: center; color: #9FD8D1;
               font-family: Sora, sans-serif; font-size: 15px; letter-spacing: .04em; }
  .pcard .inner { padding: 16px 18px 18px; display: flex; flex-direction: column; flex: 1; }
  .pcard h2 { font-family: Sora, sans-serif; font-size: 18px; line-height: 1.32;
              color: var(--teal-deep); }
  .pcard p { font-size: 15px; color: var(--muted); margin-top: 8px; flex: 1; line-height: 1.55; }
  .pcard .meta { font-size: 13px; color: #8AA09D; margin-top: 14px; }
  .empty-note { background: #fff; border: 1px dashed var(--line); border-radius: 14px;
                padding: 40px 24px; text-align: center; color: var(--muted); margin-top: 30px; }
"""


def render_blog_index(posts):
    cards = []
    for p in posts:
        d = post_date(p)
        cover = (p.get("cover_url") or "").strip()
        thumb = (f'<img class="thumb" src="{esc(cover)}" alt="{esc(p.get("cover_alt") or "")}" loading="lazy">'
                 if cover else '<div class="ph">TRIPURA JOB PULSE</div>')
        cards.append(
            f'<a class="pcard" href="blog/{esc(p["slug"])}.html">{thumb}<div class="inner">'
            f'<h2>{esc(p.get("title") or "")}</h2>'
            f'<p>{esc((p.get("excerpt") or "")[:180])}</p>'
            f'<div class="meta">{pretty(d)} · {reading_time(p.get("body"))} min read</div>'
            "</div></a>"
        )

    body = ('<div class="plist">' + "".join(cards) + "</div>") if cards else (
        '<div class="empty-note">No posts yet. The first one is on its way.</div>')

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Blog | Tripura Job Pulse</title>
<meta name="description" content="Guides, explainers and advice on finding work in Tripura and preparing for recruitment examinations.">
<link rel="canonical" href="{SITE}/blog.html">
<meta property="og:title" content="Tripura Job Pulse blog">
<meta property="og:description" content="Guides, explainers and advice on finding work in Tripura and preparing for recruitment examinations.">
<meta property="og:url" content="{SITE}/blog.html">
<meta property="og:type" content="website">
<meta property="og:site_name" content="Tripura Job Pulse">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Sora:wght@600;700&family=Hind+Siliguri:wght@400;500;600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="style.css">
<link rel="stylesheet" href="tjp-header.css">
<style>{BLOG_INDEX_CSS}</style>
</head>
<body>
<div id="tjp-header"></div>
<main class="bwrap">
<h1>Blog</h1>
<p class="lead">Guides and explainers on finding work in Tripura, preparing for recruitment
examinations, and getting the paperwork right.</p>
{body}
</main>
<div id="tjp-footer"></div>
<script src="config.js"></script>
<script src="tjp-header.js"></script>
</body>
</html>
"""


def build_blog(sb):
    """Write website/blog.html and one page per published post. Returns the posts."""
    posts = []
    try:
        posts = (sb.table("blog_posts")
                   .select("*")
                   .eq("status", "published")
                   .order("published_at", desc=True)
                   .execute().data) or []
    except Exception as exc:
        # The table may not exist yet. Carry on and write an empty blog, so a
        # missing table cannot take the job pages down with it - and so the
        # workflow still finds website/blog to commit.
        summary(f"Blog: no posts read ({exc}).")

    if os.path.isdir(BLOGDIR):
        shutil.rmtree(BLOGDIR)
    os.makedirs(BLOGDIR, exist_ok=True)

    written = 0
    for p in posts:
        if not p.get("slug"):
            continue
        with open(os.path.join(BLOGDIR, p["slug"] + ".html"), "w", encoding="utf-8") as f:
            f.write(render_post(p))
        written += 1

    with open(os.path.join(OUT, "blog.html"), "w", encoding="utf-8") as f:
        f.write(render_blog_index(posts))

    summary(f"Blog: {written} published post(s).")
    return posts


# ----------------------------------------------------------------- main

def summary(line):
    print(line)
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if path:
        with open(path, "a", encoding="utf-8") as f:
            f.write(line + "\n")


def main():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SECRET_KEY")
    if not url or not key:
        sys.exit("SUPABASE_URL and SUPABASE_SECRET_KEY must be set.")

    sb = create_client(url, key)
    jobs = sb.table("jobs").select("*").execute().data or []
    print(f"Read {len(jobs)} jobs from the database.")

    cutoff = dt.date.today() - dt.timedelta(days=KEEP_DAYS_AFTER_CLOSE)
    entries, dropped = [], 0
    seen = set()

    for job in jobs:
        close = as_date(job.get("last_date"))
        if close and close < cutoff:
            dropped += 1
            continue

        base = slugify(f"{job.get('title')} {job.get('organisation') or ''}")
        slug = f"{base}-{str(job['id'])[:8]}"
        if slug in seen:
            continue
        seen.add(slug)
        entries.append((slug, job))

    # Rebuild the folder from scratch so vacancies we dropped really disappear.
    if os.path.isdir(JOBDIR):
        shutil.rmtree(JOBDIR)
    os.makedirs(JOBDIR, exist_ok=True)

    for slug, job in entries:
        with open(os.path.join(JOBDIR, slug + ".html"), "w", encoding="utf-8") as f:
            f.write(render(job, slug))

    entries.sort(key=lambda e: (not is_open(e[1]), e[1].get("title") or ""))

    with open(os.path.join(JOBDIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(render_index(entries))
    posts = build_blog(sb)

    with open(os.path.join(OUT, "sitemap.xml"), "w", encoding="utf-8") as f:
        f.write(render_sitemap(entries, posts))
    with open(os.path.join(OUT, "robots.txt"), "w", encoding="utf-8") as f:
        f.write(ROBOTS)

    gov = sum(1 for _, j in entries if is_open(j))
    live = sum(1 for _, j in entries
               if not (as_date(j.get("last_date")) and as_date(j["last_date"]) < dt.date.today()))

    summary("## Job pages built\n")
    summary("| | |")
    summary("| --- | --- |")
    summary(f"| Pages written | {len(entries)} |")
    summary(f"| Government — full details, in Google Jobs | {gov} |")
    summary(f"| Private & remote — summary, sign-in for the rest | {len(entries) - gov} |")
    summary(f"| Still open, so listed in the sitemap | {live} |")
    summary(f"| Closed too long ago, removed | {dropped} |")
    summary("")
    summary(f"Sitemap: {SITE}/sitemap.xml")


if __name__ == "__main__":
    main()
