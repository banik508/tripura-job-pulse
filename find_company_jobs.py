"""Collect vacancies straight from company job boards.

Only boards that were checked by hand are listed below. The survey turned up
several matches on a generic identifier that belonged to a different company
altogether - "apollo" was Apollo.io in the United States, "metropolis" was a
parking firm in Ohio - so nothing is discovered automatically. A board earns
its place here only after somebody has looked at it.

Every address is a documented public API. Nothing scrapes a website.

Jobs that are neither in India nor remote are skipped: a role in Ohio is of
no use to anyone reading this site.

  DRY_RUN=1   look and report, write nothing
"""

import concurrent.futures
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone

TIMEOUT = 60          # a 900-job board with full descriptions is slow to send
MAX_BYTES = 80_000_000
UA = "Mozilla/5.0 (compatible; TripuraJobPulse/1.0; +https://tripurajobpulse.com)"

# company, platform, board identifier, sector
# Checked individually. See the note at the top before adding to this list.
BOARDS = [
    ("Swiggy",          "smartrecruiters", "swiggy",         "Internet"),
    ("Freshworks",      "smartrecruiters", "freshworks",     "IT"),
    ("Meesho",          "lever",           "meesho",         "Internet"),
    ("InMobi",          "greenhouse",      "inmobi",         "IT"),
    ("Zeta",            "lever",           "zeta",           "Fintech"),
    ("CRED",            "lever",           "cred",           "Fintech"),
    ("Groww",           "greenhouse",      "groww",          "Fintech"),
    ("Narayana Health", "smartrecruiters", "narayanahealth", "Healthcare"),
    ("PharmaACE",       "smartrecruiters", "pharmaace",      "Pharma"),
    ("Inizio",          "greenhouse",      "inizio",         "Pharma"),
    ("Oliver Wyman",    "lever",           "oliverwyman",    "Consulting"),
    ("Protiviti",       "recruitee",       "protiviti",      "Consulting"),
    ("GitLab",          "greenhouse",      "gitlab",         "IT"),
    ("Grafana Labs",    "greenhouse",      "grafanalabs",    "IT"),
    ("Mozilla",         "greenhouse",      "mozilla",        "IT"),
    ("Elastic",         "greenhouse",      "elastic",        "IT"),
    ("Canonical",       "greenhouse",      "canonical",      "IT"),
    ("Zapier",          "ashby",           "zapier",         "IT"),
    # --- added 25 Nov 2026, from the Find readable job feeds run -------------
    # The number after each is how many of that board's jobs were in India or
    # remote when it was checked. Boards whose slug was too generic to trust
    # were deliberately left out - see the note at the bottom of this block.
    ("Paytm",           "lever",           "paytm",          "Fintech"),
    ("Stripe",          "greenhouse",      "stripe",         "Fintech"),
    ("Databricks",      "greenhouse",      "databricks",     "IT"),
    ("Twilio",          "greenhouse",      "twilio",         "IT"),
    ("Supabase",        "ashby",           "supabase",       "IT"),
    ("MongoDB",         "greenhouse",      "mongodb",        "IT"),
    ("Datadog",         "greenhouse",      "datadog",        "IT"),
    ("Temporal",        "ashby",           "temporal",       "IT"),
    ("HighRadius",      "greenhouse",      "highradius",     "Fintech"),
    ("Sarvam AI",       "ashby",           "sarvam",         "IT"),
    ("Mindtickle",      "lever",           "mindtickle",     "IT"),
    ("JFrog",           "greenhouse",      "jfrog",          "IT"),
    ("Amplitude",       "ashby",           "amplitude",      "IT"),
    ("Druva",           "greenhouse",      "druva",          "IT"),
    ("ixigo",           "smartrecruiters", "ixigo",          "Internet"),
    ("SpotDraft",       "ashby",           "spotdraft",      "IT"),
    ("Observe.AI",      "greenhouse",      "observeai",      "IT"),
    ("Intercom",        "greenhouse",      "intercom",       "IT"),
    ("Unacademy",       "smartrecruiters", "unacademy",      "Education"),
    ("Atlan",           "ashby",           "atlan",          "IT"),
    ("Vercel",          "greenhouse",      "vercel",         "IT"),
    ("Airtable",        "greenhouse",      "airtable",       "IT"),
    ("Asana",           "greenhouse",      "asana",          "IT"),
    ("Figma",           "greenhouse",      "figma",          "IT"),
    ("Cloudflare",      "greenhouse",      "cloudflare",     "IT"),
    ("Lendingkart",     "smartrecruiters", "lendingkart",    "Fintech"),
    ("Upstox",          "smartrecruiters", "upstox",         "Fintech"),
    ("Whatfix",         "smartrecruiters", "whatfix",        "IT"),
    ("Newton School",   "smartrecruiters", "newtonschool",   "Education"),
    ("Uber",            "smartrecruiters", "uber",           "Internet"),
    ("Sentry",          "ashby",           "sentry",         "IT"),
    ("Linear",          "ashby",           "linear",         "IT"),
    ("Miro",            "ashby",           "miro",           "IT"),
    ("Thoughtworks",    "ashby",           "thoughtworks",   "Consulting"),
    # Left out on purpose, because the slug is a common word and the detector
    # cannot tell one company from another by name alone. Twice before this
    # pulled in the wrong company entirely (Apollo.io, a US parking firm, and
    # Grant Thornton France). Open the board yourself before adding any:
    #   apollo, metropolis, arthur, praxis, navi, pine, porter, tiger, slice, remote
]

URLS = {
    "greenhouse":      "https://boards-api.greenhouse.io/v1/boards/{s}/jobs?content=true",
    "lever":           "https://api.lever.co/v0/postings/{s}?mode=json",
    "ashby":           "https://api.ashbyhq.com/posting-api/job-board/{s}",
    "smartrecruiters": "https://api.smartrecruiters.com/v1/companies/{s}/postings?limit=100",
    "recruitee":       "https://{s}.recruitee.com/api/offers/",
}

# A blank state means Tripura in this database, so every row must carry a
# real one. Getting this wrong puts Bengaluru jobs in the Tripura list.
CITY_STATE = {
    "bengaluru": "Karnataka", "bangalore": "Karnataka", "mysuru": "Karnataka",
    "mumbai": "Maharashtra", "pune": "Maharashtra", "nagpur": "Maharashtra",
    "navi mumbai": "Maharashtra", "thane": "Maharashtra",
    "hyderabad": "Telangana", "secunderabad": "Telangana",
    "chennai": "Tamil Nadu", "coimbatore": "Tamil Nadu", "madurai": "Tamil Nadu",
    "delhi": "Delhi", "new delhi": "Delhi",
    "gurgaon": "Haryana", "gurugram": "Haryana", "faridabad": "Haryana",
    "noida": "Uttar Pradesh", "ghaziabad": "Uttar Pradesh", "lucknow": "Uttar Pradesh",
    "kolkata": "West Bengal", "howrah": "West Bengal",
    "ahmedabad": "Gujarat", "surat": "Gujarat", "vadodara": "Gujarat", "gandhinagar": "Gujarat",
    "jaipur": "Rajasthan", "indore": "Madhya Pradesh", "bhopal": "Madhya Pradesh",
    "kochi": "Kerala", "cochin": "Kerala", "thiruvananthapuram": "Kerala",
    "chandigarh": "Chandigarh", "bhubaneswar": "Odisha", "patna": "Bihar",
    "guwahati": "Assam", "agartala": "Tripura", "shillong": "Meghalaya",
    "visakhapatnam": "Andhra Pradesh", "vijayawada": "Andhra Pradesh",
}

REMOTE = re.compile(r"\b(remote|work from home|wfh|anywhere|distributed|home[- ]based)\b", re.I)
INDIA = re.compile(r"\bindia\b", re.I)

# "Remote" often means remote within one region. A role marked EMEA or
# Americas is closed to someone sitting in Tripura, and listing it wastes
# the reader's time. Keep it only if nothing rules India out.
SHUT_OUT = re.compile(r"\b(emea|americas|latam|north america|south america|"
                      r"united states|usa|u\.s\.|canada|mexico|brazil|"
                      r"united kingdom|uk only|europe|european|germany|france|"
                      r"spain|poland|australia|japan|singapore only)\b", re.I)
LET_IN = re.compile(r"\b(india|apac|asia|asia[- ]pacific|worldwide|global|"
                    r"anywhere|any location|all locations)\b", re.I)


def get(url, tries=3):
    """One failed call should not cost a whole company's listings. CRED's
    board answered the survey and refused the next run an hour later.

    The read limit used to be 6 MB, which silently decapitated the biggest
    boards: the reply arrived, got cut in half, and json.loads then failed
    with a parse error that said nothing about size. Stripe, Databricks,
    Cloudflare and Elastic were all lost that way. The limit is now high
    enough for any real board, and if one ever does exceed it the message
    says so in words instead of looking like a broken feed."""
    last = None
    for attempt in range(tries):
        got = 0
        req = urllib.request.Request(
            url, headers={"User-Agent": UA, "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                raw = r.read(MAX_BYTES + 1)
            got = len(raw)
            if got > MAX_BYTES:
                raise ValueError(f"reply larger than {MAX_BYTES // 1_000_000} MB")
            return json.loads(raw.decode("utf-8", "replace"))
        except (urllib.error.HTTPError, urllib.error.URLError,
                ValueError, OSError) as e:
            last = f"{type(e).__name__}: {e}" + (f" ({got:,} bytes read)" if got else "")
            if attempt + 1 < tries:
                time.sleep(2 * (attempt + 1))
    print(f"    could not read after {tries} tries: {last}")
    return None


def fetch_board(platform, slug):
    """SmartRecruiters answers at most 100 postings at a time. Asking once
    quietly lost about half of Swiggy's jobs, so this walks the pages. The
    other platforms return everything in one reply."""
    if platform == "greenhouse":
        # Descriptions make these replies large. If the full one cannot be
        # had, take the listings without descriptions rather than losing the
        # company altogether - a job with a thin description still reaches
        # people, and the next run's backfill fills it in.
        board = get(URLS[platform].format(s=slug))
        if board is None:
            print("    retrying without descriptions")
            board = get(URLS[platform].format(s=slug).replace("content=true", "content=false"))
            if board is not None:
                print(f"    read {len(board.get('jobs') or [])} jobs, descriptions to follow next run")
        return board

    if platform != "smartrecruiters":
        return get(URLS[platform].format(s=slug))

    content, offset = [], 0
    while True:
        page = get("https://api.smartrecruiters.com/v1/companies/"
                   f"{slug}/postings?limit=100&offset={offset}")
        if not page:
            break
        items = page.get("content") or []
        content.extend(items)
        total = int(page.get("totalFound") or 0)
        offset += len(items)
        if not items or offset >= total or offset > 2000:
            break
    return {"content": content, "totalFound": len(content)}


def place(text):
    """Work out city and state from a location string. Returns (city, state,
    kind) where kind is 'india', 'remote' or 'elsewhere'."""
    s = (text or "").strip()
    low = s.lower()

    for city, state in CITY_STATE.items():
        if re.search(r"\b" + re.escape(city) + r"\b", low):
            return city.title(), state, "india"

    if INDIA.search(low):
        first = re.split(r"[,/|]", s)[0].strip()
        city = "" if INDIA.search(first) else first[:40]
        return city, "India", "india"

    if REMOTE.search(low):
        if SHUT_OUT.search(low) and not LET_IN.search(low):
            return "", "", "elsewhere"
        return "", "Remote", "remote"

    return "", "", "elsewhere"



def to_text(raw, limit=4000):
    """Job descriptions arrive as HTML, and as HTML that has been escaped
    once or twice. Turn it into plain text that reads properly on the page,
    keeping paragraph and bullet breaks and nothing else."""
    if not raw:
        return ""
    s = str(raw)
    # Greenhouse escapes its HTML; some boards escape it twice.
    for _ in range(2):
        if "&lt;" in s or "&amp;" in s:
            s = html.unescape(s)
    s = re.sub(r"(?is)<(script|style).*?</\1>", " ", s)
    s = re.sub(r"(?i)<li[^>]*>", "\n• ", s)
    s = re.sub(r"(?i)<br\s*/?>", "\n", s)
    s = re.sub(r"(?i)</(p|div|ul|ol|h[1-6]|tr)>", "\n\n", s)
    s = re.sub(r"<[^>]+>", " ", s)
    s = html.unescape(s)
    s = s.replace("\xa0", " ")
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r" *\n *", "\n", s)
    s = re.sub(r"\n{3,}", "\n\n", s).strip()
    if len(s) > limit:
        cut = s.rfind("\n", 0, limit)
        s = (s[:cut] if cut > limit * 0.6 else s[:limit]).rstrip() + "…"
    return s


def lever_text(j):
    bits = [j.get("descriptionPlain") or j.get("description") or ""]
    for section in (j.get("lists") or []):
        if section.get("text"):
            bits.append("\n" + section["text"])
        bits.append(section.get("content") or "")
    bits.append(j.get("additionalPlain") or j.get("additional") or "")
    return "\n\n".join(b for b in bits if b)


def smart_text(detail):
    """SmartRecruiters keeps the words in a separate call, in named sections."""
    sections = ((detail or {}).get("jobAd") or {}).get("sections") or {}
    order = ["jobDescription", "qualifications", "additionalInformation", "companyDescription"]
    out = []
    for key in order:
        sec = sections.get(key) or {}
        title, text = sec.get("title"), sec.get("text")
        if text:
            out.append((title + "\n" if title else "") + text)
    return "\n\n".join(out)


def recruitee_text(j):
    return "\n\n".join(b for b in [j.get("description"), j.get("requirements")] if b)


# --- turning each platform's reply into the same shape ----------------------

def from_greenhouse(d):
    for j in (d or {}).get("jobs", []):
        yield (j.get("title"), (j.get("location") or {}).get("name", ""),
               j.get("absolute_url"), j.get("updated_at"), to_text(j.get("content")))


def from_lever(d):
    for j in (d or []):
        c = j.get("categories") or {}
        yield (j.get("text"), c.get("location", ""),
               j.get("hostedUrl") or j.get("applyUrl"), None, to_text(lever_text(j)))


def from_ashby(d):
    for j in (d or {}).get("jobs", []):
        loc = j.get("location") or ""
        if j.get("isRemote") and not REMOTE.search(loc):
            loc = (loc + " Remote").strip()
        yield (j.get("title"), loc, j.get("jobUrl") or j.get("applyUrl"), j.get("publishedAt"),
               to_text(j.get("descriptionPlain") or j.get("descriptionHtml")))


def from_smartrecruiters(d):
    for j in (d or {}).get("content", []):
        loc = j.get("location") or {}
        bits = [loc.get("city"), loc.get("region"), loc.get("country")]
        text = ", ".join(b for b in bits if b)
        if loc.get("remote"):
            text += " Remote"
        url = (j.get("applyUrl") or j.get("ref") or "")
        # the words come from a second call, made later only for the jobs kept
        yield (j.get("name"), text, url, j.get("releasedDate"), "@smart:" + str(j.get("id") or ""))


def from_recruitee(d):
    for j in (d or {}).get("offers", []):
        bits = [j.get("city"), j.get("country")]
        text = ", ".join(b for b in bits if b) or (j.get("location") or "")
        yield (j.get("title"), text, j.get("careers_url") or j.get("careers_apply_url"),
               j.get("published_at"), to_text(recruitee_text(j)))


READERS = {"greenhouse": from_greenhouse, "lever": from_lever, "ashby": from_ashby,
           "smartrecruiters": from_smartrecruiters, "recruitee": from_recruitee}


def collect():
    rows, report = [], []
    read_ok = set()          # sources we genuinely read this time
    for name, platform, slug, sector in BOARDS:
        print(f"  {name} ({platform})")
        data = fetch_board(platform, slug)
        if data is None:
            # Deliberately NOT added to read_ok. A board that timed out
            # tells us nothing about which of its jobs are still open, and
            # treating silence as "all closed" would wipe a company's
            # listings over one bad minute.
            report.append((name, 0, 0, "could not read"))
            continue

        kept = total = 0
        pending_smart = []
        for title, loc, url, posted, text in READERS[platform](data):
            total += 1
            if not title or not url:
                continue
            city, state, kind = place(loc)
            if kind == "elsewhere":
                continue
            if isinstance(text, str) and text.startswith("@smart:"):
                pending_smart.append((len(rows), slug, text[7:]))
                text = ""
            rows.append({
                "title": title.strip()[:200],
                "organisation": name,
                "job_type": "remote" if kind == "remote" else "private",
                "city": city or None,
                "state": state,
                "industry": sector,
                "location": (loc or "").strip()[:120] or None,
                "apply_link": url,
                "how_to_apply": f"Apply on the {name} careers site.",
                # The board's own words where we have them. The one-line
                # version is only a fallback: a page that says nothing is
                # no use to a reader and is treated as thin by search engines.
                "description": text or (f"{title.strip()} at {name}."
                                        + (f" Location: {loc.strip()}." if loc else "")),
                "source": f"company:{platform}:{slug}",
            })
            kept += 1
        # SmartRecruiters keeps the description behind a second call, so it is
        # fetched only for the jobs we are actually keeping.
        if pending_smart:
            print(f"    fetching {len(pending_smart)} descriptions")
            with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
                texts = list(pool.map(
                    lambda item: smart_text(get(
                        f"https://api.smartrecruiters.com/v1/companies/{item[1]}/postings/{item[2]}")),
                    pending_smart))
            for (idx, _, _), body in zip(pending_smart, texts):
                clean = to_text(body)
                if clean:
                    rows[idx]["description"] = clean

        report.append((name, total, kept, ""))
        # A board that answered but listed nothing at all is suspicious
        # rather than informative, so it does not license closing either.
        if total > 0:
            read_ok.add(f"company:{platform}:{slug}")
        print(f"    {kept} of {total} kept")
    return rows, report, read_ok


def jobs_key(title, organisation):
    """How the database decides two rows are the same job."""
    return ((title or "").strip().lower(),
            (organisation or "").strip().lower())


def unique_title(row, taken):
    """A title this company does not already have. Returns None if even the
    city does not make it distinct - better to drop one listing than to lose
    a whole batch."""
    base = row["title"]
    for candidate in (base,
                      f"{base} — {row['city']}" if row.get("city") else None,
                      f"{base} — {row['state']}" if row.get("state") else None,
                      f"{base} — {row['location']}" if row.get("location") else None):
        if candidate and jobs_key(candidate, row["organisation"]) not in taken:
            return candidate[:200]
    return None


def backfill(sb, live_rows):
    """Give jobs already on the site the description we now have for them.

    Only touches rows this collector created, only where what we have is
    materially better than what is there, and never overwrites something
    longer than our own. A job somebody edited by hand keeps its text.
    """
    have = {r["apply_link"]: r["description"] for r in live_rows
            if r.get("description") and len(r["description"]) > 200}
    if not have:
        return 0

    held, start = [], 0
    while True:
        got = sb.table("jobs").select("id,apply_link,description") \
                .like("source", "company:%").range(start, start + 999).execute().data or []
        held.extend(got)
        if len(got) < 1000:
            break
        start += 1000

    done = 0
    for row in held:
        better = have.get(row.get("apply_link"))
        if not better:
            continue
        current = row.get("description") or ""
        # Replace only the thin placeholder, or something clearly shorter.
        if len(current) >= len(better):
            continue
        sb.table("jobs").update({"description": better}).eq("id", row["id"]).execute()
        done += 1
    if done:
        print(f"  filled in {done} descriptions")
    return done


def tidy(sb, live_rows, read_ok):
    """Close jobs the companies have taken down, and reopen any that came back.

    Collected jobs carry no closing date, so without this they sit on the
    site for ever and people apply for posts that were filled months ago.

    Only sources in read_ok are touched. If a board failed to answer, its
    jobs are left exactly as they are - the alternative is wiping a
    company's listings because of one timeout.
    """
    if not read_ok:
        return 0, 0

    live_links = {r["apply_link"] for r in live_rows}
    yesterday = date.today() - timedelta(days=1)

    held = []
    start = 0
    while True:
        got = sb.table("jobs").select("id,apply_link,source,last_date") \
                .like("source", "company:%").range(start, start + 999).execute().data or []
        held.extend(got)
        if len(got) < 1000:
            break
        start += 1000

    to_close, to_open = [], []
    for row in held:
        if row.get("source") not in read_ok:
            continue
        on_board = row.get("apply_link") in live_links
        if not on_board and row.get("last_date") is None:
            to_close.append(row["id"])
        elif on_board and row.get("last_date") is not None:
            to_open.append(row["id"])

    for i in range(0, len(to_close), 100):
        sb.table("jobs").update({"last_date": yesterday.isoformat()}) \
          .in_("id", to_close[i:i + 100]).execute()
    for i in range(0, len(to_open), 100):
        sb.table("jobs").update({"last_date": None}) \
          .in_("id", to_open[i:i + 100]).execute()

    print(f"  closed {len(to_close)}, reopened {len(to_open)}")
    return len(to_close), len(to_open)


def main():
    dry = os.environ.get("DRY_RUN") == "1"
    print(f"Reading {len(BOARDS)} company job boards"
          f"{' (dry run - nothing will be written)' if dry else ''}\n")

    rows, report, read_ok = collect()

    # One board can list the same role twice; and a job already on the site
    # must not be added again.
    seen, unique = set(), []
    for r in rows:
        if r["apply_link"] in seen:
            continue
        seen.add(r["apply_link"])
        unique.append(r)

    summary = ["## Company job boards\n",
               "| Company | Found | Kept |", "| --- | --- | --- |"]
    for name, total, kept, err in report:
        summary.append(f"| {name} | {err or total} | {kept} |")
    summary.append("")
    summary.append(f"**{len(unique)} jobs in India or remote, from {len(BOARDS)} boards.**")

    india = sum(1 for r in unique if r["job_type"] == "private")
    summary.append(f"{india} in India, {len(unique) - india} remote.")

    if dry:
        summary.append("\n_Dry run - nothing was written._")
        for r in unique[:15]:
            summary.append(f"- {r['title']} — {r['organisation']} — "
                           f"{r['city'] or ''} {r['state']}")
    else:
        from supabase import create_client
        sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SECRET_KEY"])

        existing = set()
        start = 0
        while True:
            got = sb.table("jobs").select("apply_link").not_.is_("apply_link", "null") \
                    .range(start, start + 999).execute().data or []
            existing |= {g["apply_link"] for g in got if g.get("apply_link")}
            if len(got) < 1000:
                break
            start += 1000

        fresh = [r for r in unique if r["apply_link"] not in existing]

        # The table allows one row per title + organisation. A company often
        # advertises the same role in several cities, so the title has to say
        # which city, or the second one is refused and takes the whole batch
        # down with it.
        taken = set()
        start = 0
        while True:
            got = sb.table("jobs").select("title,organisation") \
                    .range(start, start + 999).execute().data or []
            taken |= {jobs_key(g.get("title"), g.get("organisation")) for g in got}
            if len(got) < 1000:
                break
            start += 1000

        ready, skipped = [], 0
        for r in fresh:
            title = unique_title(r, taken)
            if title is None:
                skipped += 1
                continue
            r["title"] = title
            taken.add(jobs_key(title, r["organisation"]))
            ready.append(r)

        added, refused = 0, 0
        for i in range(0, len(ready), 100):
            batch = ready[i:i + 100]
            try:
                sb.table("jobs").insert(batch).execute()
                added += len(batch)
            except Exception as e:
                # One awkward row must not cost the other ninety-nine.
                print(f"    batch refused ({e}); inserting one at a time")
                for row in batch:
                    try:
                        sb.table("jobs").insert(row).execute()
                        added += 1
                    except Exception:
                        refused += 1
        fresh = ready

        # The 625 jobs already on the site were saved with a one-line
        # description, because the earlier version threw the real text away.
        # Fill those in now rather than leaving a thousand thin pages behind.
        filled = backfill(sb, unique)

        closed, reopened = tidy(sb, unique, read_ok)

        summary.append(f"\n**Added {added}. "
                       f"{len(unique) - len(fresh)} were already on the site.**")
        if skipped or refused:
            summary.append(f"{skipped + refused} skipped as the same role "
                           f"already listed for that company.")
        if filled:
            summary.append(f"Replaced the one-line description on {filled} jobs "
                           f"already on the site with the company's own wording.")
        if closed or reopened:
            summary.append(f"Closed {closed} that the companies have taken down"
                           + (f", reopened {reopened} that came back." if reopened else "."))
        skipped = [n for n, _, _, err in report if err]
        if skipped:
            summary.append(f"Left alone: {', '.join(skipped)} — the board could not "
                           f"be read, so its jobs were neither closed nor changed.")
        print(f"\nAdded {len(fresh)} new jobs")

    text = "\n".join(summary)
    print("\n" + text)
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if path:
        with open(path, "a", encoding="utf-8") as f:
            f.write(text + "\n")


if __name__ == "__main__":
    main()
