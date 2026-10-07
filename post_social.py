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

from card_render import caption_for, render_card

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
DRY_RUN = os.environ.get("DRY_RUN", "false").lower() == "true"
GRAPH = f"https://graph.facebook.com/{os.environ.get('GRAPH_VERSION', 'v23.0')}"

BUCKET = "cards"
sb = create_client(SUPABASE_URL, SUPABASE_KEY)


def today_iso():
    return datetime.now(timezone.utc).date().isoformat()


def jobs_to_post():
    """Newest open jobs that haven't been posted to either platform yet."""
    posted = sb.table("social_posts").select("job_id").limit(5000).execute().data or []
    done = {r["job_id"] for r in posted}

    rows = sb.table("jobs").select(
        "id, title, organisation, job_type, region, city, state, "
        "experience, qualification, vacancies, salary, last_date, created_at"
    ).or_(
        f"last_date.gte.{today_iso()},last_date.is.null"
    ).order("created_at", desc=True).limit(200).execute().data or []

    fresh = [j for j in rows if j["id"] not in done]
    return fresh[:MAX_POSTS]


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


def record(job_id, platform, post_id, image_url):
    sb.table("social_posts").insert({
        "job_id": job_id,
        "platform": platform,
        "post_id": str(post_id) if post_id else None,
        "image_url": image_url,
    }).execute()


def main():
    jobs = jobs_to_post()
    if not jobs:
        print("Nothing new to post.")
        return

    print(f"{len(jobs)} job(s) to post.")
    for job in jobs:
        print(f"\n--- {job['title']}")
        image = render_card(job, "portrait")
        print(f"    card drawn, {len(image) // 1024} KB")

        url = upload_card(job, image)
        print(f"    uploaded: {url}")

        text = caption_for(job)

        if DRY_RUN:
            print("    DRY RUN - not posting. Caption would be:")
            print("    " + text.replace("\n", "\n    "))
            continue

        try:
            fb_id = post_to_facebook(url, text)
            record(job["id"], "facebook", fb_id, url)
            print(f"    Facebook: posted ({fb_id})")
        except Exception as err:
            print(f"    Facebook failed: {err}")

        try:
            ig_id = post_to_instagram(url, text)
            record(job["id"], "instagram", ig_id, url)
            print(f"    Instagram: posted ({ig_id})")
        except Exception as err:
            print(f"    Instagram failed: {err}")

    print("\nDone.")


if __name__ == "__main__":
    main()
