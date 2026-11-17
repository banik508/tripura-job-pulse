"""Ask the hiring platforms directly which companies have a readable job feed.

The earlier survey fetched each company's careers page and guessed from the
HTML. 62 of 169 refused the request outright - TCS, Infosys, HDFC Bank,
AstraZeneca, Flipkart - so the answer came back "custom site" for firms that
plainly have a careers page. The result undercounted badly.

This asks the other end instead. Greenhouse, Lever, Ashby, SmartRecruiters,
Workable and Recruitee all publish a documented JSON endpoint per employer.
If a company has a board, the endpoint answers with its jobs. That is the
exact question we need answered, and it gives us the identifier needed to
collect from them afterwards.

Nothing here scrapes a website. Every address below is a public API meant to
be called by programs.

Run it from the Actions tab. Output: feed-results.csv
"""

import concurrent.futures
import csv
import json
import os
import re
import sys
import urllib.error
import urllib.request

TIMEOUT = 12
WORKERS = 8
UA = "Mozilla/5.0 (compatible; TripuraJobPulse/1.0; +https://tripurajobpulse.com)"


# Each entry: name, URL pattern, and how to count jobs in the reply.
def _count_greenhouse(d):  return len(d.get("jobs", []))
def _count_lever(d):       return len(d) if isinstance(d, list) else 0
def _count_ashby(d):       return len(d.get("jobs", []))
def _count_smart(d):       return int(d.get("totalFound") or len(d.get("content", [])))
def _count_workable(d):    return len(d.get("jobs", []))
def _count_recruitee(d):   return len(d.get("offers", []))

PLATFORMS = [
    ("Greenhouse",     "https://boards-api.greenhouse.io/v1/boards/{s}/jobs",        _count_greenhouse),
    ("Lever",          "https://api.lever.co/v0/postings/{s}?mode=json",             _count_lever),
    ("Ashby",          "https://api.ashbyhq.com/posting-api/job-board/{s}",          _count_ashby),
    ("SmartRecruiters","https://api.smartrecruiters.com/v1/companies/{s}/postings",  _count_smart),
    ("Workable",       "https://apply.workable.com/api/v1/widget/accounts/{s}",      _count_workable),
    ("Recruitee",      "https://{s}.recruitee.com/api/offers/",                      _count_recruitee),
]

INDIA = re.compile(r"\b(india|bangalore|bengaluru|hyderabad|mumbai|pune|chennai|"
                   r"delhi|gurgaon|gurugram|noida|kolkata|ahmedabad|kochi|"
                   r"coimbatore|indore|jaipur|remote)\b", re.I)


def slugs(name, domain):
    """The identifiers a company is most likely to use on a job board."""
    base = domain.split(".")[0]
    plain = re.sub(r"[^a-z0-9]", "", name.lower())
    hyphen = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    first = re.sub(r"[^a-z0-9]", "", name.lower().split()[0])
    # Short or generic identifiers match somebody else's job board, and we
    # would file their vacancies under this company's name. "dr" for Dr Lal
    # PathLabs, "au" for AU Small Finance Bank. Not worth the risk.
    GENERIC = {"the", "new", "dr", "au", "india", "indian", "national",
               "first", "global", "tata", "max", "city", "south", "united"}
    out = []
    for s in (base, plain, hyphen, first):
        if not s or len(s) < 4 or s in GENERIC or s in out:
            continue
        out.append(s)
    return out[:4]


def get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            if r.status != 200:
                return None
            body = r.read(3_000_000)
        return json.loads(body.decode("utf-8", "replace"))
    except (urllib.error.HTTPError, urllib.error.URLError, ValueError, OSError):
        return None


def india_share(platform, data):
    """Roughly how many of the jobs look Indian. Useful, not exact - every
    platform words its location field differently."""
    try:
        if platform == "Greenhouse":
            items = [j.get("location", {}).get("name", "") for j in data.get("jobs", [])]
        elif platform == "Lever":
            items = [j.get("categories", {}).get("location", "") for j in data]
        elif platform == "Ashby":
            items = [j.get("location", "") for j in data.get("jobs", [])]
        elif platform == "SmartRecruiters":
            items = [json.dumps(j.get("location", {})) for j in data.get("content", [])]
        elif platform == "Workable":
            items = [j.get("location", "") if isinstance(j.get("location"), str)
                     else json.dumps(j.get("location", {})) for j in data.get("jobs", [])]
        else:
            items = [json.dumps(j.get("locations", [])) for j in data.get("offers", [])]
        return sum(1 for s in items if INDIA.search(s or ""))
    except Exception:
        return 0


def check(entry):
    name, domain = entry
    for slug in slugs(name, domain):
        for platform, pattern, counter in PLATFORMS:
            data = get_json(pattern.format(s=slug))
            if data is None:
                continue
            try:
                n = counter(data)
            except Exception:
                continue
            if n > 0:
                return (name, domain, platform, slug, n, india_share(platform, data))
    return (name, domain, "", "", 0, 0)


def load(path):
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "|" not in line:
                continue
            n, d = [p.strip() for p in line.split("|", 1)]
            out.append((n, d))
    return out


def summary(line):
    print(line)
    p = os.environ.get("GITHUB_STEP_SUMMARY")
    if p:
        with open(p, "a", encoding="utf-8") as f:
            f.write(line + "\n")


def main():
    companies = load(sys.argv[1] if len(sys.argv) > 1 else "companies.txt")
    print(f"Asking the job platforms about {len(companies)} companies...\n")

    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as pool:
        for r in pool.map(check, companies):
            results.append(r)
            if r[2]:
                print(f"  FOUND  {r[0]:<34} {r[2]:<16} {r[4]} jobs ({r[5]} in India)")

    hits = [r for r in results if r[2]]
    hits.sort(key=lambda r: -r[5])

    summary("## Companies with a readable job feed\n")
    if hits:
        summary("| Company | Platform | Identifier | Jobs | Look Indian |")
        summary("| --- | --- | --- | --- | --- |")
        for n, d, p, s, c, i in hits:
            summary(f"| {n} | {p} | `{s}` | {c} | {i} |")
    else:
        summary("_None found._")

    total_jobs = sum(r[4] for r in hits)
    total_india = sum(r[5] for r in hits)
    summary("")
    summary(f"**{len(hits)} of {len(results)} companies have an open feed — "
            f"{total_jobs} jobs in total, {total_india} of them in India or remote.**")
    summary("")
    summary("Companies with no feed are not listed. They are not missing: they "
            "simply run their hiring somewhere we cannot read, and belong in "
            "the aggregator instead.")

    with open("feed-results.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["company", "domain", "platform", "slug", "jobs", "india_jobs"])
        w.writerows(results)
    print(f"\nSaved feed-results.csv — {len(hits)} with feeds, {total_jobs} jobs")


if __name__ == "__main__":
    main()
