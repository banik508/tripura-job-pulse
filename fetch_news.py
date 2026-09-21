"""
Tripura Job Pulse - current affairs collector (no AI version)

Reads RSS feeds, sorts stories into tripura / india / international,
skips junk and duplicates, and saves them to Supabase as drafts.

Needs a .env file in the same folder with:
  SUPABASE_URL=https://yourproject.supabase.co
  SUPABASE_SECRET_KEY=your_secret_key
"""

import html
import os
import re
from datetime import datetime, timedelta, timezone

import feedparser
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SECRET_KEY"]

TABLE = "current_affairs"
LOOKBACK_HOURS = 36          # how far back to look in each feed
MAX_PER_SECTION = 20         # most items to save per section per run

# Feeds for each section. Add or remove lines freely.
FEEDS = {
    "tripura": [
        "https://news.google.com/rss/search?q=Tripura&hl=en-IN&gl=IN&ceid=IN:en",
        "https://news.google.com/rss/search?q=Agartala&hl=en-IN&gl=IN&ceid=IN:en",
    ],
    "india": [
        "https://news.google.com/rss/headlines/section/topic/NATION?hl=en-IN&gl=IN&ceid=IN:en",
        "https://news.google.com/rss/search?q=cabinet+approves+OR+government+scheme+India&hl=en-IN&gl=IN&ceid=IN:en",
    ],
    "international": [
        "https://news.google.com/rss/headlines/section/topic/WORLD?hl=en-IN&gl=IN&ceid=IN:en",
    ],
}

# Headlines containing any of these words are skipped as not exam-useful.
SKIP_WORDS = [
    "murder", "rape", "arrested", "molest", "suicide", "accident", "road mishap",
    "actress", "actor", "bollywood", "box office", "movie", "film review",
    "horoscope", "astrology", "recipe", "viral video", "trolled", "slams",
    "sensex", "nifty", "stock tips", "ipo listing", "betting", "match preview",
]


def clean(text):
    """Remove HTML tags and extra spaces from feed text."""
    text = html.unescape(text or "")
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def normalise_title(title):
    """Strip the ' - Publisher' that Google News adds, for duplicate checking."""
    title = re.sub(r"\s+-\s+[^-]+$", "", title)
    return re.sub(r"[^a-z0-9]", "", title.lower())


def entry_time(entry):
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if parsed:
        return datetime(*parsed[:6], tzinfo=timezone.utc)
    return datetime.now(timezone.utc)


def is_junk(title):
    lowered = title.lower()
    return any(word in lowered for word in SKIP_WORDS)


def already_saved(supabase):
    """Links and titles saved in the last few days, so we don't repeat them."""
    since = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()
    rows = (
        supabase.table(TABLE)
        .select("source_url,title")
        .gte("created_at", since)
        .limit(2000)
        .execute()
        .data
    )
    return ({r["source_url"] for r in rows},
            {normalise_title(r["title"]) for r in rows})


def collect(section, seen_urls, seen_titles):
    cutoff = datetime.now(timezone.utc) - timedelta(hours=LOOKBACK_HOURS)
    found = []

    for feed_url in FEEDS[section]:
        feed = feedparser.parse(feed_url)
        for e in feed.entries:
            link = e.get("link", "")
            title = clean(e.get("title", ""))
            if not link or not title:
                continue

            key = normalise_title(title)
            if link in seen_urls or key in seen_titles:
                continue
            if is_junk(title):
                continue
            if entry_time(e) < cutoff:
                continue

            source = e.get("source", {})
            snippet = clean(e.get("summary", ""))
            # Google News often repeats the headline in the snippet; drop it if so
            if normalise_title(snippet)[:40] == key[:40]:
                snippet = ""

            found.append({
                "section": section,
                "title": re.sub(r"\s+-\s+[^-]+$", "", title),
                "summary": snippet[:500] or None,
                "source_name": source.get("title") if isinstance(source, dict) else None,
                "source_url": link,
                "published_at": entry_time(e).isoformat(),
                "status": "draft",
            })
            seen_urls.add(link)
            seen_titles.add(key)

    found.sort(key=lambda x: x["published_at"], reverse=True)
    return found[:MAX_PER_SECTION]


def main():
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    seen_urls, seen_titles = already_saved(supabase)
    total = 0

    for section in FEEDS:
        rows = collect(section, seen_urls, seen_titles)
        if rows:
            supabase.table(TABLE).upsert(
                rows, on_conflict="source_url", ignore_duplicates=True
            ).execute()
        print(f"{section}: saved {len(rows)} new items")
        total += len(rows)

    print(f"Finished. {total} items saved as drafts.")


if __name__ == "__main__":
    main()
