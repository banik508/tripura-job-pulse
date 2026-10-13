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


def where(job):
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

    tags = [t for t in [
        (job.get("job_type") or "").title() or None,
        where(job),
        f"Closes {pretty(close)}" if close else None,
    ] if t]
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
            ("Location", where(job)),
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
            ("Location", where(job)),
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


def render_sitemap(entries):
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
    with open(os.path.join(OUT, "sitemap.xml"), "w", encoding="utf-8") as f:
        f.write(render_sitemap(entries))
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
