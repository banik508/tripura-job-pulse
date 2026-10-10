"""
Tripura Job Pulse - daily job finder and repository

Reads Tripura job boards and news searches, works out what it can about each
vacancy, stores it, then emails you one Excel file containing the whole
repository split into tabs:

    New today
    Tripura - Government
    Tripura - Private
    Within India - Government
    Within India - Private
    Remote

Every tab uses your 15-column upload format.

Be clear about the limits. A feed gives a title, a link and a short summary.
It does not give vacancy counts, pay scales or age limits - those sit inside
PDF notifications. Those columns arrive blank, shaded yellow, for you to fill
in from the official notice.

Environment variables:
  SUPABASE_URL
  SUPABASE_SECRET_KEY
  GMAIL_USER
  GMAIL_APP_PASSWORD
  MAIL_TO              where to send it (defaults to GMAIL_USER)
  LOOKBACK_HOURS       how far back to look for new items (default 48)
  DRY_RUN              "true" to build but not email
"""

import html
import os
import re
import smtplib
import ssl
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from email.utils import formataddr
from io import BytesIO

import feedparser
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from supabase import create_client

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SUPABASE_KEY = os.environ["SUPABASE_SECRET_KEY"]
GMAIL_USER = os.environ["GMAIL_USER"]
GMAIL_PASS = os.environ["GMAIL_APP_PASSWORD"]
MAIL_TO = os.environ.get("MAIL_TO") or GMAIL_USER
LOOKBACK_HOURS = int(os.environ.get("LOOKBACK_HOURS", "48"))
DRY_RUN = os.environ.get("DRY_RUN", "false").lower() == "true"

sb = create_client(SUPABASE_URL, SUPABASE_KEY)

COLUMNS = ["Job title", "Organisation", "Job type", "City", "State",
           "Experience", "Industry", "Qualification", "Vacancies", "Salary",
           "Age limit", "Last date", "How to apply", "Apply link", "Description"]

# Columns a feed can usually fill. The rest are shaded for you to complete.
AUTO = {"Job title", "Organisation", "Job type", "City", "State",
        "Apply link", "Description"}

# Two kinds of source, treated differently.
#   "board" - a job board. Every post is meant to be a vacancy, so it only has
#             to pass the light checks. Being strict here loses real jobs.
#   "news"  - a news search. Most items are stories about jobs rather than
#             vacancies, so these face the full set of tests.
FEEDS = [
    ("board", "tripurajob.in",
     "https://www.tripurajob.in/feeds/posts/default?alt=rss"),
    ("board", "tripuracareer.in",
     "https://www.tripuracareer.in/feeds/posts/default?alt=rss"),
    ("board", "jobstripura.com",
     "https://www.jobstripura.com/feeds/posts/default?alt=rss"),
    ("board", "tripurastarnews.com",
     "https://www.tripurastarnews.com/category/job-employment/feed/"),

    ("news", "news: Tripura recruitment",
     "https://news.google.com/rss/search?q=Tripura+recruitment&hl=en-IN&gl=IN&ceid=IN:en"),
    ("news", "news: Tripura apply online",
     "https://news.google.com/rss/search?q=Tripura+vacancy+apply+online&hl=en-IN&gl=IN&ceid=IN:en"),
    ("news", "news: TPSC",
     "https://news.google.com/rss/search?q=TPSC+recruitment&hl=en-IN&gl=IN&ceid=IN:en"),
    ("news", "news: JRBT",
     "https://news.google.com/rss/search?q=JRBT+recruitment+Tripura&hl=en-IN&gl=IN&ceid=IN:en"),
    ("news", "news: Agartala vacancy",
     "https://news.google.com/rss/search?q=Agartala+job+vacancy&hl=en-IN&gl=IN&ceid=IN:en"),
    ("news", "news: walk-in",
     "https://news.google.com/rss/search?q=Tripura+walk-in+interview&hl=en-IN&gl=IN&ceid=IN:en"),
]

JOB_WORDS = re.compile(
    r"\b(recruit\w*|vacanc\w*|vacancies|hiring|appointment|apply\s+online|"
    r"walk[-\s]?in|notification|post[s]?\b|job[s]?\b|engage\w*|"
    r"empanel\w*|advertis\w*)\b", re.I)

SKIP_WORDS = re.compile(
    r"\b(result|answer\s*key|admit\s*card|cut[-\s]?off|merit\s*list|"
    r"exam\s*date|postponed|cancell?ed|scam|fraud|protest|unemployment\s+rate|"
    r"job\s*loss|laid\s*off|retrench\w*|syllabus|previous\s+year|question\s+paper)\b", re.I)

# News *about* jobs reads very differently from a notice.
COMMENTARY = re.compile(
    r"\b(high\s+court|supreme\s+court|affidavit|petition|plea|hearing|verdict|"
    r"listed\s+for|seeks?|slams?|alleges?|expose[sd]?|pay\s+gap|row\s+over|"
    r"demands?|criticis\w*|questions?|debate|assembly|minister\s+said|"
    r"opposition|survey|report\s+says|study|analysis|crisis|backlog)\b", re.I)

# A real notice almost always says one of these.
ANNOUNCEMENT = re.compile(
    r"(\brecruitment\b|\bnotification\b|\bapply\s+online\b|\bapply\s+before\b|"
    r"\bwalk[-\s]?in\b|\binvites?\s+application|\bapplications?\s+invited\b|"
    r"\blast\s+date\b|\bvacanc\w*\s+(?:announced|out|notified)\b|"
    r"\b\d{1,5}\+?\s+(?:post|posts|vacanc\w*)\b|"
    r"\brecruitment\s+\d{4}\b|\bhiring\s+for\b)", re.I)

RELEVANT_PLACE = re.compile(
    r"\b(tripura|agartala|udaipur|dharmanagar|kailashahar|belonia|ambassa|"
    r"khowai|sabroom|tpsc|jrbt|trbt|ttaadc|tsecl|agmc|trtc)\b", re.I)

REMOTE = re.compile(
    r"\b(work\s+from\s+home|wfh|remote\s+(?:job|work|position|role)|"
    r"fully\s+remote|home[-\s]based)\b", re.I)

ORGS = [
    ("TPSC", "Tripura Public Service Commission (TPSC)"),
    ("JRBT", "Joint Recruitment Board Tripura (JRBT)"),
    ("TRBT", "Teachers' Recruitment Board Tripura"),
    ("Tripura University", "Tripura University"),
    ("NIT Agartala", "NIT Agartala"),
    ("TSECL", "Tripura State Electricity Corporation (TSECL)"),
    ("TTAADC", "Tripura Tribal Areas Autonomous District Council"),
    ("Tripura Police", "Tripura Police"),
    ("AGMC", "Agartala Government Medical College"),
    ("TIDC", "Tripura Industrial Development Corporation"),
    ("TRTC", "Tripura Road Transport Corporation"),
    ("Tripura High Court", "Tripura High Court"),
    ("DLSA", "District Legal Services Authority"),
    ("SoFED", "SoFED, Government of Tripura"),
]

GOV_HINT = re.compile(
    r"\b(government|govt|department|ministry|commission|board|council|"
    r"corporation|directorate|municipal|nagar|panchayat|district|"
    r"tpsc|jrbt|trbt|police|university|college|hospital|railway|rrb|"
    r"bank|ssc|upsc|court|isro|drdo|ongc|aiims|icmr|nhm|bsf|crpf|army|navy|"
    r"air\s+force|psu|limited\b)\b", re.I)

TABS = [
    ("Tripura - Government", lambda r: r["region"] == "tripura" and r["gov"]),
    ("Tripura - Private", lambda r: r["region"] == "tripura" and not r["gov"]),
    ("Within India - Government", lambda r: r["region"] == "india" and r["gov"]),
    ("Within India - Private", lambda r: r["region"] == "india" and not r["gov"]),
    ("Remote", lambda r: r["region"] == "remote"),
]


# ---------------------------------------------------------------- helpers
def clean(text):
    text = html.unescape(text or "")
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def strip_publisher(title):
    return re.sub(r"\s+-\s+[^-]{2,40}$", "", title).strip()


def entry_time(entry):
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if parsed:
        return datetime(*parsed[:6], tzinfo=timezone.utc)
    return datetime.now(timezone.utc)


def guess_organisation(text):
    for needle, full in ORGS:
        if re.search(r"\b" + re.escape(needle) + r"\b", text, re.I):
            return full
    return ""


def guess_city(text):
    for city in ["Agartala", "Udaipur", "Dharmanagar", "Kailashahar",
                 "Belonia", "Ambassa", "Khowai", "Sabroom"]:
        if re.search(r"\b" + city + r"\b", text, re.I):
            return city
    return ""


def classify(blob, is_tripura):
    """Which section of the site this belongs in, and whether it's government."""
    if REMOTE.search(blob):
        region = "remote"
    elif is_tripura:
        region = "tripura"
    else:
        region = "india"
    gov = bool(guess_organisation(blob)) or bool(GOV_HINT.search(blob))
    return region, gov


# ---------------------------------------------------------------- collecting
def known_urls():
    rows = sb.table("job_leads").select("source_url").limit(20000).execute().data or []
    return {r["source_url"] for r in rows}


def collect():
    cutoff = datetime.now(timezone.utc) - timedelta(hours=LOOKBACK_HOURS)
    seen_urls = known_urls()
    seen_titles = set()
    found = []
    tally = []

    for kind, label, url in FEEDS:
        kept_here = 0
        why = {"already have": 0, "duplicate": 0, "too old": 0, "not a job": 0,
               "skipped word": 0, "commentary": 0, "no notice wording": 0,
               "not Tripura": 0}
        try:
            feed = feedparser.parse(url)
        except Exception as err:
            tally.append((label, "could not be read", 0, 0, why))
            print(f"  ! {label}: {err}")
            continue

        total_here = len(feed.entries)
        for e in feed.entries:
            link = e.get("link", "")
            raw_title = clean(e.get("title", ""))
            if not link or not raw_title:
                continue
            if link in seen_urls:
                why["already have"] += 1
                continue

            title = strip_publisher(raw_title)
            key = re.sub(r"[^a-z0-9]", "", title.lower())
            if key in seen_titles:
                why["duplicate"] += 1
                continue

            snippet = clean(e.get("summary") or e.get("description") or "")[:800]
            blob = f"{title} {snippet}"

            if not JOB_WORDS.search(blob):
                why["not a job"] += 1
                continue
            if SKIP_WORDS.search(title):
                why["skipped word"] += 1
                continue
            if kind == "news":
                if COMMENTARY.search(title):
                    why["commentary"] += 1
                    continue
                if not ANNOUNCEMENT.search(blob):
                    why["no notice wording"] += 1
                    continue

            is_tripura = bool(RELEVANT_PLACE.search(blob))
            # Job boards legitimately carry national vacancies, which feed the
            # "Jobs within India" section. A Tripura news search returning
            # another state is a misfire, so that still gets dropped.
            if kind == "news" and not is_tripura:
                why["not Tripura"] += 1
                continue
            if entry_time(e) < cutoff:
                why["too old"] += 1
                continue

            region, gov = classify(blob, is_tripura)
            src = e.get("source", {})
            found.append({
                "source_url": link,
                "title": title,
                "organisation": guess_organisation(blob),
                "source_name": (src.get("title") if isinstance(src, dict) else "") or label,
                "job_type": "Government" if gov else "Private",
                "city": guess_city(blob),
                "state": "Tripura" if is_tripura else "",
                "region": region,
                "apply_link": link,
                "description": snippet,
            })
            seen_urls.add(link)
            seen_titles.add(key)
            kept_here += 1

        tally.append((label, "ok" if total_here else "empty",
                      total_here, kept_here, why))

    return found, tally


def store(items):
    if items:
        sb.table("job_leads").upsert(
            items, on_conflict="source_url", ignore_duplicates=True
        ).execute()


def repository():
    """Everything collected and not yet marked as uploaded."""
    rows = (sb.table("job_leads")
            .select("*")
            .eq("uploaded", False)
            .order("found_at", desc=True)
            .limit(3000)
            .execute().data) or []
    for r in rows:
        r["gov"] = (r.get("job_type") or "").lower() == "government"
        r["region"] = r.get("region") or "india"
    return rows


# ---------------------------------------------------------------- the workbook
def to_row(r):
    return {
        "Job title": r.get("title") or "",
        "Organisation": r.get("organisation") or r.get("source_name") or "",
        "Job type": r.get("job_type") or "",
        "City": r.get("city") or "",
        "State": r.get("state") or "",
        "Experience": "", "Industry": "", "Qualification": "", "Vacancies": "",
        "Salary": "", "Age limit": "", "Last date": "", "How to apply": "",
        "Apply link": r.get("apply_link") or r.get("source_url") or "",
        "Description": r.get("description") or "",
    }


HEAD_FILL = PatternFill("solid", fgColor="0E4F4C")
TODO_FILL = PatternFill("solid", fgColor="FDF3D7")
HEAD_FONT = Font(color="FFFFFF", bold=True, size=11)
WIDTHS = {"Job title": 44, "Organisation": 30, "Job type": 13, "City": 14,
          "State": 12, "Experience": 18, "Industry": 18, "Qualification": 26,
          "Vacancies": 11, "Salary": 14, "Age limit": 16, "Last date": 13,
          "How to apply": 24, "Apply link": 40, "Description": 60}


def write_sheet(ws, rows):
    ws.append(COLUMNS)
    for i, name in enumerate(COLUMNS, start=1):
        c = ws.cell(row=1, column=i)
        c.fill = HEAD_FILL
        c.font = HEAD_FONT
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    for r in rows:
        ws.append([r[c] for c in COLUMNS])

    for i, name in enumerate(COLUMNS, start=1):
        ws.column_dimensions[get_column_letter(i)].width = WIDTHS.get(name, 18)
        if name in AUTO:
            continue
        for row in range(2, len(rows) + 2):
            ws.cell(row=row, column=i).fill = TODO_FILL

    ws.freeze_panes = "A2"
    for row in ws.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = Alignment(vertical="top", wrap_text=True)


def build_excel(new_items, store_rows, found_on):
    wb = Workbook()

    ws = wb.active
    ws.title = "New today"
    write_sheet(ws, [to_row(r) for r in new_items])

    counts = {}
    for name, test in TABS:
        picked = [r for r in store_rows if test(r)]
        counts[name] = len(picked)
        write_sheet(wb.create_sheet(name[:31]), [to_row(r) for r in picked])

    notes = wb.create_sheet("Read me")
    for line in [
        ["Tripura Job Pulse - job repository, built " + found_on],
        [],
        ["New today holds what arrived in the latest run."],
        ["The other tabs hold everything collected so far, by section."],
        [],
        ["White columns were filled in automatically."],
        ["Yellow columns could not be worked out from a feed - open the Apply"],
        ["link, read the official notice, and fill them in."],
        [],
        ["The Apply link points at wherever the notice was found, often a job"],
        ["board rather than the official site. Replace it with the official"],
        ["application link before you upload."],
        [],
        ["Check every row against the official notification. Job boards and"],
        ["news sites get details wrong, and some items are not real vacancies."],
        [],
        ["Rows stay in the repository until they are marked as uploaded in the"],
        ["job_leads table."],
        [],
        ["Counts:"],
    ] + [[f"   {k}: {v}"] for k, v in counts.items()]:
        notes.append(line)
    notes.column_dimensions["A"].width = 95

    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue(), counts


# ---------------------------------------------------------------- sending
def send(xlsx, new_count, counts, found_on):
    subject = (f"{new_count} new job{'' if new_count == 1 else 's'} - "
               f"Tripura Job Pulse repository {found_on}")
    lines = [
        f"{new_count} new job notice{'' if new_count == 1 else 's'} today.",
        "",
        "The attached file is the whole repository, in your upload format:",
        "",
    ] + [f"  {k}: {v}" for k, v in counts.items()] + [
        "",
        "White columns are filled in; yellow ones need you to open the link and",
        "read the official notice. Check each row before uploading.",
        "",
        "Tripura Job Pulse",
    ]

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = formataddr(("Tripura Job Pulse", GMAIL_USER))
    msg["To"] = MAIL_TO
    msg.set_content("\n".join(lines))
    msg.add_attachment(
        xlsx,
        maintype="application",
        subtype="vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=f"tripura-job-repository-{found_on}.xlsx",
    )

    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ssl.create_default_context()) as s:
        s.login(GMAIL_USER, GMAIL_PASS)
        s.send_message(msg)


def summary(line):
    print(line)
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if path:
        with open(path, "a", encoding="utf-8") as f:
            f.write(line + "\n\n")


def main():
    found_on = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d")
    new_items, tally = collect()

    summary("## Result")
    lines = ["| Source | In feed | Kept | Why the rest were dropped |",
             "| --- | ---: | ---: | --- |"]
    for label, state, total, kept, why in tally:
        shown = total if state == "ok" else state
        reasons = ", ".join(f"{k} {v}" for k, v in why.items() if v) or "—"
        lines.append(f"| {label} | {shown} | {kept} | {reasons} |")
    summary("\n".join(lines))

    if not DRY_RUN:
        store(new_items)

    rows = repository()
    if DRY_RUN:
        # The new ones aren't saved yet, so add them for an accurate preview
        existing = {r.get("source_url") for r in rows}
        for n in new_items:
            if n["source_url"] not in existing:
                r = dict(n)
                r["gov"] = r["job_type"] == "Government"
                rows.append(r)

    xlsx, counts = build_excel(new_items, rows, found_on)

    summary(f"**{len(new_items)} new**, {len(rows)} in the repository.")
    summary("\n".join([f"- {k}: {v}" for k, v in counts.items()]))
    for r in new_items[:25]:
        summary(f"  - {r['title']}")

    if DRY_RUN:
        summary("**Practice run - nothing emailed, nothing saved.**")
        return

    send(xlsx, len(new_items), counts, found_on)
    summary(f"**Emailed to {MAIL_TO}.**")


if __name__ == "__main__":
    main()
