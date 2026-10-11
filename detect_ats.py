"""
Work out which hiring platform each company uses.

This is a one-off survey, not part of the daily job. It visits each company's
careers page and looks for the fingerprint of a known hiring platform, then
prints a table. Once we know who runs on what, we only build readers for the
platforms that publish an open listings feed.

Why it matters:
  Greenhouse, Lever, SmartRecruiters, Ashby, Workable, Recruitee
      publish an open jobs feed on purpose, for job boards to use. Clean.
  Workday, SuccessFactors, Taleo, iCIMS, Phenom, Eightfold
      have an internal feed their own page calls, but no published API and
      terms that generally forbid automated access. Your call, not mine.
  Custom
      bespoke portal. Readable only by driving a browser, and it breaks
      whenever they redesign.

Run it with:  python detect_ats.py
"""

import concurrent.futures
import os
import re
import sys

import requests

TIMEOUT = 20
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (compatible; TripuraJobPulse/1.0; "
                   "+https://tripurajobpulse.com)"),
    "Accept": "text/html,application/xhtml+xml",
}

# Fingerprint -> (platform, how open it is)
SIGNS = [
    (r"boards\.greenhouse\.io|job-boards\.greenhouse\.io|greenhouse\.io/embed",
     "Greenhouse", "open"),
    (r"jobs\.lever\.co|api\.lever\.co", "Lever", "open"),
    (r"smartrecruiters\.com", "SmartRecruiters", "open"),
    (r"ashbyhq\.com", "Ashby", "open"),
    (r"apply\.workable\.com|workable\.com/api", "Workable", "open"),
    (r"\.recruitee\.com", "Recruitee", "open"),
    (r"teamtailor\.com", "Teamtailor", "open"),

    (r"myworkdayjobs\.com|workday\.com", "Workday", "closed"),
    (r"successfactors\.com|sapsf\.com|jobs\.sap\.com", "SuccessFactors", "closed"),
    (r"taleo\.net", "Taleo", "closed"),
    (r"icims\.com", "iCIMS", "closed"),
    (r"phenompeople\.com|phenom\.com", "Phenom", "closed"),
    (r"eightfold\.ai", "Eightfold", "closed"),
    (r"oraclecloud\.com/hcmUI|/hcmUI/CandidateExperience", "Oracle HCM", "closed"),
    (r"brassring\.com", "BrassRing", "closed"),
    (r"peoplestrong|darwinbox", "Darwinbox/PeopleStrong", "closed"),
]

# Where a careers page usually lives
PATHS = ["/careers", "/en/careers", "/careers/", "/jobs", "/en/about-us/careers",
         "/about/careers", "/company/careers", "/careers/jobs", "/en-in/careers",
         "/in/careers", "/career"]


def load(path):
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "|" not in line:
                continue
            name, domain = [p.strip() for p in line.split("|", 1)]
            out.append((name, domain))
    return out


def fetch(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True)
        if r.status_code < 400:
            return r.url, r.text[:400000]
    except Exception:
        pass
    return None, ""


def identify(text, final_url):
    blob = (text or "") + " " + (final_url or "")
    for pattern, platform, openness in SIGNS:
        if re.search(pattern, blob, re.I):
            return platform, openness
    return None, None


def check(entry):
    name, domain = entry
    tried = []

    for path in PATHS:
        url = f"https://{domain}{path}"
        final, text = fetch(url)
        if not text:
            continue
        tried.append(path)
        platform, openness = identify(text, final)
        if platform:
            return name, domain, platform, openness, final

        # Careers pages often link out to the real board rather than embed it
        for m in re.finditer(r'href=["\']([^"\']{10,200})["\']', text):
            href = m.group(1)
            platform, openness = identify(href, href)
            if platform:
                return name, domain, platform, openness, href

    # Fall back to the home page
    final, text = fetch(f"https://{domain}")
    if text:
        platform, openness = identify(text, final)
        if platform:
            return name, domain, platform, openness, final

    return name, domain, "unknown / custom", "unclear", ", ".join(tried) or "no page reached"


def summary(line):
    print(line)
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if path:
        with open(path, "a", encoding="utf-8") as f:
            f.write(line + "\n")


def main():
    companies = load(sys.argv[1] if len(sys.argv) > 1 else "companies.txt")
    print(f"Checking {len(companies)} companies...\n")

    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        for r in pool.map(check, companies):
            results.append(r)
            print(f"  {r[2]:<24} {r[0]}")

    order = {"open": 0, "closed": 1, "unclear": 2}
    results.sort(key=lambda r: (order.get(r[3], 3), r[2], r[0]))

    summary("## Hiring platform by company\n")
    summary("| Company | Platform | Can we read it? |")
    summary("| --- | --- | --- |")
    label = {"open": "Yes - open feed",
             "closed": "Technically, but not permitted",
             "unclear": "No - custom site"}
    for name, domain, platform, openness, _ in results:
        summary(f"| {name} | {platform} | {label.get(openness, '?')} |")

    counts = {}
    for _, _, platform, openness, _ in results:
        counts[openness] = counts.get(openness, 0) + 1
    summary("")
    summary(f"**Open feeds: {counts.get('open', 0)} · "
            f"Restricted: {counts.get('closed', 0)} · "
            f"Custom: {counts.get('unclear', 0)}**")

    with open("ats-results.csv", "w", encoding="utf-8") as f:
        f.write("company,domain,platform,openness,evidence\n")
        for row in results:
            f.write(",".join('"' + str(c).replace('"', "'") + '"' for c in row) + "\n")
    print("\nSaved ats-results.csv")


if __name__ == "__main__":
    main()
