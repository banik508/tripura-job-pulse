"""
Tripura Job Pulse - post new jobs to Facebook and Instagram

What it does, for each job that hasn't been posted yet:
  1. Draws the job card (card_render.py - no browser needed)
  2. Uploads it to the public 'cards' bucket in Supabase Storage
  3. Posts it to the Facebook page
  4. Posts it to Instagram (which fetches the image from that public URL)
  5. Records it in social_posts, so it never goes out twice

Environment variables:
  SUPABASE_URL           https://xxxx.supabase.co
  SUPABASE_SECRET_KEY    secret key - never goes in website files
  FB_PAGE_ID             your Facebook page id
  FB_PAGE_TOKEN          the long-lived page token
  IG_USER_ID             your Instagram business account id
  SITE_URL               https://tripurajobpulse.com
  MAX_POSTS              how many jobs per run (default 2)
  DRY_RUN                "true" to render and upload but not post
  GRAPH_VERSION          Graph API version (default v23.0)
"""

import os
import time
from datetime import datetime, timezone

import requests
from supabase import create_client

from card_render import caption_for, gk_caption, render_card, render_gk_card

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SUPABASE_KEY = os.environ["SUPABASE_SECRET_KEY"]
FB_PAGE_ID = os.environ["FB_PAGE_ID"]
FB_PAGE_TOKEN = os.environ["FB_PAGE_TOKEN"]
IG_USER_ID = os.environ["IG_USER_ID"]
SITE = os.environ.get("SITE_URL", "https://tripurajobpulse.com").rstrip("/")
MAX_POSTS = int(os.environ.get("MAX_POSTS", "2"))
# General knowledge cards go out alongside the jobs. Set MAX_GK to 0 in the
# workflow to pause them without touching anything else.
MAX_GK = int(os.environ.get("MAX_GK", "1"))
DRY_RUN = os.environ.get("DRY_RUN", "false").lower() == "true"
GRAPH = f"https://graph.facebook.com/{os.environ.get('GRAPH_VERSION', 'v23.0')}"

BUCKET = "cards"
sb = create_client(SUPABASE_URL, SUPABASE_KEY)


def today_iso():
    return datetime.now(timezone.utc).date().isoformat()


def is_tripura(job):
    """Is this job in Tripura? Checked across every field that could say so,
    because the region column is not filled in on older rows."""
    blob = " ".join(str(job.get(k) or "") for k in
                    ("region", "state", "city", "location", "organisation"))
    return "tripura" in blob.lower() or "agartala" in blob.lower()


def jobs_to_post():
    """Which jobs go out today.

    The audience is in Tripura, so Tripura jobs come first and fill the slots.
    Only when there are not enough new Tripura vacancies does the rest of the
    list get a look in - better an India-wide job than an empty page that day.
    """
    posted = sb.table("social_posts").select("job_id").limit(5000).execute().data or []
    done = {r["job_id"] for r in posted}

    rows = sb.table("jobs").select(
        "id, title, organisation, job_type, region, city, state, "
        "experience, qualification, vacancies, salary, last_date, created_at"
    ).or_(
        f"last_date.gte.{today_iso()},last_date.is.null"
    ).order("created_at", desc=True).limit(200).execute().data or []

    fresh = [j for j in rows if j["id"] not in done]

    chosen = [j for j in fresh if is_tripura(j)][:MAX_POSTS]
    local = len(chosen)
    if local < MAX_POSTS:
        picked = {j["id"] for j in chosen}
        chosen += [j for j in fresh if j["id"] not in picked][:MAX_POSTS - local]

    if chosen:
        filler = len(chosen) - local
        note = f"Picked {local} Tripura job(s)"
        note += f" and {filler} from elsewhere to fill the day." if filler else "."
        summary(note)
    return chosen


def upload_card(job, image):
    """Put the card in the public bucket and return its web address."""
    path = f"{job['id']}.jpg"
    sb.storage.from_(BUCKET).upload(
        path,
        image,
        {"content-type": "image/jpeg", "upsert": "true", "cache-control": "3600"},
    )
    return f"{SUPABASE_URL}/storage/v1/object/public/{BUCKET}/{path}"


def post_to_facebook(image_url, caption):
    r = requests.post(
        f"{GRAPH}/{FB_PAGE_ID}/photos",
        data={"url": image_url, "message": caption, "access_token": FB_PAGE_TOKEN},
        timeout=90,
    )
    body = r.json()
    if r.status_code >= 400:
        raise RuntimeError(f"Facebook refused it: {body}")
    return body.get("post_id") or body.get("id")


def post_to_instagram(image_url, caption):
    # Step one: hand Instagram the image address and wait for it to fetch it
    r = requests.post(
        f"{GRAPH}/{IG_USER_ID}/media",
        data={"image_url": image_url, "caption": caption, "access_token": FB_PAGE_TOKEN},
        timeout=90,
    )
    body = r.json()
    if r.status_code >= 400:
        raise RuntimeError(f"Instagram refused the image: {body}")
    container = body["id"]

    for _ in range(20):
        s = requests.get(
            f"{GRAPH}/{container}",
            params={"fields": "status_code,status", "access_token": FB_PAGE_TOKEN},
            timeout=60,
        ).json()
        state = s.get("status_code")
        if state == "FINISHED":
            break
        if state == "ERROR":
            raise RuntimeError(f"Instagram couldn't process the image: {s}")
        time.sleep(3)

    # Step two: publish it
    r = requests.post(
        f"{GRAPH}/{IG_USER_ID}/media_publish",
        data={"creation_id": container, "access_token": FB_PAGE_TOKEN},
        timeout=90,
    )
    body = r.json()
    if r.status_code >= 400:
        raise RuntimeError(f"Instagram refused to publish: {body}")
    return body["id"]


def gk_to_post():
    """Which general knowledge cards go out this run.

    Anything already posted is skipped, so the bank is worked through rather
    than the same few items going round again. Oldest first, so items you
    wrote weeks ago are not stranded behind everything added since.
    """
    if MAX_GK < 1:
        return []

    posted = sb.table("gk_posts").select("gk_id").limit(5000).execute().data or []
    done = {r["gk_id"] for r in posted}

    rows = sb.table("gk_items").select("*").eq(
        "status", "published"
    ).order("created_at", desc=False).limit(500).execute().data or []

    fresh = [g for g in rows if g["id"] not in done]
    if not fresh:
        summary("General knowledge: every published item has already been posted.")
        return []

    return fresh[:MAX_GK]


def upload_gk_card(item, image):
    path = f"gk-{item['id']}.jpg"
    sb.storage.from_(BUCKET).upload(
        path,
        image,
        {"content-type": "image/jpeg", "upsert": "true", "cache-control": "3600"},
    )
    return f"{SUPABASE_URL}/storage/v1/object/public/{BUCKET}/{path}"


def record_gk(gk_id, platform, post_id, image_url):
    sb.table("gk_posts").insert({
        "gk_id": gk_id,
        "platform": platform,
        "post_id": str(post_id) if post_id else None,
        "image_url": image_url,
    }).execute()


def post_gk():
    """One general knowledge card per run, after the job."""
    items = gk_to_post()
    for item in items:
        label = (item.get("question") or "")[:60]
        print(f"\n--- GK: {label}")
        image = render_gk_card(item, "portrait")
        print(f"    card drawn, {len(image) // 1024} KB")

        url = upload_gk_card(item, image)
        print(f"    uploaded: {url}")
        text = gk_caption(item)

        if DRY_RUN:
            summary(f"- Practice run for GK **{label}** - card made, nothing posted.")
            print("    Caption would be:")
            print("    " + text.replace("\n", "\n    "))
            continue

        try:
            fb_id = post_to_facebook(url, text)
            record_gk(item["id"], "facebook", fb_id, url)
            summary(f"- Facebook: **posted** GK - {label}")
        except Exception as err:
            summary(f"- Facebook: **FAILED** on GK - {err}")

        try:
            ig_id = post_to_instagram(url, text)
            record_gk(item["id"], "instagram", ig_id, url)
            summary(f"- Instagram: **posted** GK - {label}")
        except Exception as err:
            summary(f"- Instagram: **FAILED** on GK - {err}")


def record(job_id, platform, post_id, image_url):
    sb.table("social_posts").insert({
        "job_id": job_id,
        "platform": platform,
        "post_id": str(post_id) if post_id else None,
        "image_url": image_url,
    }).execute()


def summary(line):
    """Also show the result at the top of the GitHub run page, so there is
    no need to dig through the log."""
    print(line)
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if path:
        with open(path, "a", encoding="utf-8") as f:
            f.write(line + "\n\n")


def main():
    summary("## Result")
    summary("**Mode: PRACTICE — nothing will be posted.**" if DRY_RUN
            else "**Mode: POSTING FOR REAL.**")

    jobs = jobs_to_post()
    if not jobs:
        summary("No new job to post — every open job has already been posted.")

    print(f"{len(jobs)} job(s) to post.")
    for job in jobs:
        print(f"\n--- {job['title']}")
        image = render_card(job, "portrait")
        print(f"    card drawn, {len(image) // 1024} KB")

        url = upload_card(job, image)
        print(f"    uploaded: {url}")

        text = caption_for(job)

        if DRY_RUN:
            summary(f"- Practice run for **{job['title']}** — card made, nothing posted.")
            print("    Caption would be:")
            print("    " + text.replace("\n", "\n    "))
            continue

        try:
            fb_id = post_to_facebook(url, text)
            record(job["id"], "facebook", fb_id, url)
            summary(f"- Facebook: **posted** — {job['title']}")
        except Exception as err:
            summary(f"- Facebook: **FAILED** — {err}")

        try:
            ig_id = post_to_instagram(url, text)
            record(job["id"], "instagram", ig_id, url)
            summary(f"- Instagram: **posted** — {job['title']}")
        except Exception as err:
            summary(f"- Instagram: **FAILED** — {err}")

    # The general knowledge card goes out whether or not there was a job,
    # so a day with no new vacancy is not a silent day on the page.
    try:
        post_gk()
    except Exception as err:
        summary(f"- General knowledge: **FAILED** - {err}")

    print("\nDone.")


if __name__ == "__main__":
    main()
