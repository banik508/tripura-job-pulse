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

import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

TIMEOUT = 20
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
]

URLS = {
    "greenhouse":      "https://boards-api.greenhouse.io/v1/boards/{s}/jobs?content=false",
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


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return json.loads(r.read(6_000_000).decode("utf-8", "replace"))
    except (urllib.error.HTTPError, urllib.error.URLError, ValueError, OSError) as e:
        print(f"    could not read: {e}")
        return None


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


# --- turning each platform's reply into the same shape ----------------------

def from_greenhouse(d):
    for j in (d or {}).get("jobs", []):
        yield (j.get("title"), (j.get("location") or {}).get("name", ""),
               j.get("absolute_url"), j.get("updated_at"))


def from_lever(d):
    for j in (d or []):
        c = j.get("categories") or {}
        yield (j.get("text"), c.get("location", ""),
               j.get("hostedUrl") or j.get("applyUrl"), None)


def from_ashby(d):
    for j in (d or {}).get("jobs", []):
        loc = j.get("location") or ""
        if j.get("isRemote") and not REMOTE.search(loc):
            loc = (loc + " Remote").strip()
        yield (j.get("title"), loc, j.get("jobUrl") or j.get("applyUrl"), j.get("publishedAt"))


def from_smartrecruiters(d):
    for j in (d or {}).get("content", []):
        loc = j.get("location") or {}
        bits = [loc.get("city"), loc.get("region"), loc.get("country")]
        text = ", ".join(b for b in bits if b)
        if loc.get("remote"):
            text += " Remote"
        url = (j.get("applyUrl") or j.get("ref") or "")
        yield (j.get("name"), text, url, j.get("releasedDate"))


def from_recruitee(d):
    for j in (d or {}).get("offers", []):
        bits = [j.get("city"), j.get("country")]
        text = ", ".join(b for b in bits if b) or (j.get("location") or "")
        yield (j.get("title"), text, j.get("careers_url") or j.get("careers_apply_url"),
               j.get("published_at"))


READERS = {"greenhouse": from_greenhouse, "lever": from_lever, "ashby": from_ashby,
           "smartrecruiters": from_smartrecruiters, "recruitee": from_recruitee}


def collect():
    rows, report = [], []
    for name, platform, slug, sector in BOARDS:
        print(f"  {name} ({platform})")
        data = get(URLS[platform].format(s=slug))
        if data is None:
            report.append((name, 0, 0, "could not read"))
            continue

        kept = total = 0
        for title, loc, url, posted in READERS[platform](data):
            total += 1
            if not title or not url:
                continue
            city, state, kind = place(loc)
            if kind == "elsewhere":
                continue
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
                "description": f"{title.strip()} at {name}."
                               + (f" Location: {loc.strip()}." if loc else ""),
                "source": f"company:{platform}:{slug}",
            })
            kept += 1
        report.append((name, total, kept, ""))
        print(f"    {kept} of {total} kept")
    return rows, report


def main():
    dry = os.environ.get("DRY_RUN") == "1"
    print(f"Reading {len(BOARDS)} company job boards"
          f"{' (dry run - nothing will be written)' if dry else ''}\n")

    rows, report = collect()

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
        for i in range(0, len(fresh), 200):
            sb.table("jobs").insert(fresh[i:i + 200]).execute()

        summary.append(f"\n**Added {len(fresh)}. "
                       f"{len(unique) - len(fresh)} were already on the site.**")
        print(f"\nAdded {len(fresh)} new jobs")

    text = "\n".join(summary)
    print("\n" + text)
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if path:
        with open(path, "a", encoding="utf-8") as f:
            f.write(text + "\n")


if __name__ == "__main__":
    main()
