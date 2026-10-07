"""
Tripura Job Pulse - weekly job alert emails

What it does:
  1. Finds the last time alerts were sent (from the email_sends table).
  2. Picks up jobs added since then that are still open.
  3. Emails the list to every active subscriber, each with their own
     unsubscribe link.
  4. Records the send so the next run starts from the right place.

Environment variables (GitHub Secrets, or your local .env):
  SUPABASE_URL
  SUPABASE_SECRET_KEY      <- secret key. Never put this in website files.
  GMAIL_USER               <- e.g. tripurajobpulse@gmail.com
  GMAIL_APP_PASSWORD       <- the 16-character App Password, not your login password
  SITE_URL                 <- https://tripurajobpulse.com
  DRY_RUN                  <- "true" to print instead of sending (for testing)
  MAX_JOBS                 <- how many jobs to list in one email (default 12)
"""

import os
import smtplib
import ssl
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from email.utils import formataddr

from supabase import create_client

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SECRET_KEY"]
GMAIL_USER = os.environ["GMAIL_USER"]
GMAIL_PASS = os.environ["GMAIL_APP_PASSWORD"]
SITE = os.environ.get("SITE_URL", "https://tripurajobpulse.com").rstrip("/")
DRY_RUN = os.environ.get("DRY_RUN", "false").lower() == "true"
MAX_JOBS = int(os.environ.get("MAX_JOBS", "12"))

FROM_NAME = "Tripura Job Pulse"
TEAL = "#0E4F4C"
TEAL_MID = "#15706B"
MARIGOLD = "#D9A13B"
PAPER = "#F4F8F6"

sb = create_client(SUPABASE_URL, SUPABASE_KEY)


def today_iso():
    return datetime.now(timezone.utc).date().isoformat()


def last_send_time():
    """When did we last send? Falls back to 7 days ago on the very first run."""
    rows = (
        sb.table("email_sends")
        .select("created_at")
        .order("created_at", desc=True)
        .limit(1)
        .execute()
        .data
    )
    if rows:
        return rows[0]["created_at"]
    return (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()


def new_jobs(since):
    rows = (
        sb.table("jobs")
        .select("id, title, organisation, job_type, region, city, state, last_date, created_at")
        .gte("created_at", since)
        .or_(f"last_date.gte.{today_iso()},last_date.is.null")
        .order("created_at", desc=True)
        .limit(MAX_JOBS)
        .execute()
        .data
    )
    return rows or []


def job_count_since(since):
    res = (
        sb.table("jobs")
        .select("id", count="exact")
        .gte("created_at", since)
        .or_(f"last_date.gte.{today_iso()},last_date.is.null")
        .execute()
    )
    return res.count or 0


def active_subscribers():
    rows = (
        sb.table("subscribers")
        .select("id, email, token, active")
        .eq("active", True)
        .limit(5000)
        .execute()
        .data
    )
    return [r for r in (rows or []) if r.get("email") and r.get("token")]


def place(job):
    bits = [job.get("city"), job.get("state")]
    bits = [b for b in bits if b and b.strip() and b.strip().lower() != "not specified"]
    if job.get("region") == "remote":
        return "Remote"
    return ", ".join(bits)


def pretty_date(value):
    if not value:
        return ""
    try:
        return datetime.fromisoformat(str(value)[:10]).strftime("%d %b %Y")
    except Exception:
        return str(value)[:10]


def section_name(job):
    return {"tripura": "Tripura", "india": "Within India", "remote": "Remote"}.get(
        job.get("region"), ""
    )


def build_html(jobs, total, unsub_url):
    cards = []
    for j in jobs:
        link = f"{SITE}/job.html?id={j['id']}"
        meta = " &nbsp;·&nbsp; ".join(
            x for x in [section_name(j), place(j), (j.get("job_type") or "").title()] if x
        )
        last = pretty_date(j.get("last_date"))
        last_line = (
            f'<div style="font-size:13px;color:#8A9A96;margin-top:6px;">Last date: {last}</div>'
            if last
            else ""
        )
        cards.append(
            f"""
          <tr><td style="padding:0 0 14px 0;">
            <table width="100%" cellpadding="0" cellspacing="0" style="background:#ffffff;border:1px solid #E2EBE8;border-radius:10px;">
              <tr><td style="padding:16px 18px;">
                <a href="{link}" style="font-family:Arial,Helvetica,sans-serif;font-size:17px;font-weight:bold;color:{TEAL};text-decoration:none;">{j['title']}</a>
                <div style="font-family:Arial,Helvetica,sans-serif;font-size:14px;color:#3D4A47;margin-top:4px;">{j.get('organisation') or ''}</div>
                <div style="font-family:Arial,Helvetica,sans-serif;font-size:13px;color:#6B7A77;margin-top:8px;">{meta}</div>
                {last_line}
                <div style="margin-top:12px;">
                  <a href="{link}" style="font-family:Arial,Helvetica,sans-serif;font-size:13px;font-weight:bold;color:#ffffff;background:{TEAL_MID};padding:8px 16px;border-radius:6px;text-decoration:none;display:inline-block;">View details</a>
                </div>
              </td></tr>
            </table>
          </td></tr>"""
        )

    more = ""
    if total > len(jobs):
        more = f"""
          <tr><td style="padding:4px 0 18px 0;font-family:Arial,Helvetica,sans-serif;font-size:14px;color:#3D4A47;">
            And {total - len(jobs)} more new jobs on the site.
            <a href="{SITE}/jobs.html" style="color:{TEAL};">See all jobs &rarr;</a>
          </td></tr>"""

    return f"""<!DOCTYPE html>
<html><body style="margin:0;padding:0;background:{PAPER};">
<table width="100%" cellpadding="0" cellspacing="0" style="background:{PAPER};padding:24px 12px;">
<tr><td align="center">
  <table width="100%" cellpadding="0" cellspacing="0" style="max-width:580px;">

    <tr><td style="background:{TEAL};border-radius:12px 12px 0 0;padding:22px 20px;">
      <div style="font-family:Arial,Helvetica,sans-serif;font-size:20px;font-weight:bold;color:#ffffff;">
        Tripura <span style="color:{MARIGOLD};">Job Pulse</span>
      </div>
      <div style="font-family:Arial,Helvetica,sans-serif;font-size:13px;color:#B9D5D2;margin-top:4px;">
        This week's new job openings
      </div>
    </td></tr>

    <tr><td style="background:#ffffff;padding:20px;">
      <p style="font-family:Arial,Helvetica,sans-serif;font-size:15px;color:#1C2B28;margin:0 0 18px 0;">
        Hello! Here {'is' if total == 1 else 'are'} <strong>{total}</strong> new job{'' if total == 1 else 's'} posted on Tripura Job Pulse this week.
      </p>
      <table width="100%" cellpadding="0" cellspacing="0">
        {''.join(cards)}
        {more}
      </table>
      <table width="100%" cellpadding="0" cellspacing="0" style="margin-top:6px;">
        <tr><td align="center" style="padding:10px 0;">
          <a href="{SITE}/jobs.html" style="font-family:Arial,Helvetica,sans-serif;font-size:14px;font-weight:bold;color:{TEAL};text-decoration:none;border:1px solid {TEAL};padding:10px 20px;border-radius:6px;display:inline-block;">Browse all jobs</a>
        </td></tr>
      </table>
    </td></tr>

    <tr><td style="background:#ffffff;border-top:1px solid #E2EBE8;border-radius:0 0 12px 12px;padding:16px 20px;">
      <p style="font-family:Arial,Helvetica,sans-serif;font-size:12px;color:#8A9A96;margin:0;line-height:1.6;">
        You are getting this because you subscribed to job alerts on
        <a href="{SITE}" style="color:{TEAL};">tripurajobpulse.com</a>.<br>
        <a href="{unsub_url}" style="color:#8A9A96;">Unsubscribe</a>
      </p>
    </td></tr>

  </table>
</td></tr>
</table>
</body></html>"""


def build_text(jobs, total, unsub_url):
    lines = [
        "TRIPURA JOB PULSE - this week's new jobs",
        "",
        f"{total} new job{'' if total == 1 else 's'} were posted this week.",
        "",
    ]
    for j in jobs:
        lines.append(f"* {j['title']}")
        if j.get("organisation"):
            lines.append(f"  {j['organisation']}")
        meta = " | ".join(
            x for x in [section_name(j), place(j), (j.get("job_type") or "").title()] if x
        )
        if meta:
            lines.append(f"  {meta}")
        if j.get("last_date"):
            lines.append(f"  Last date: {pretty_date(j['last_date'])}")
        lines.append(f"  {SITE}/job.html?id={j['id']}")
        lines.append("")
    if total > len(jobs):
        lines.append(f"And {total - len(jobs)} more on the site.")
        lines.append("")
    lines += [
        f"All jobs: {SITE}/jobs.html",
        "",
        "---",
        "You subscribed to job alerts on tripurajobpulse.com.",
        f"Unsubscribe: {unsub_url}",
    ]
    return "\n".join(lines)


def main():
    since = last_send_time()
    print(f"Looking for jobs added since {since}")

    jobs = new_jobs(since)
    if not jobs:
        print("No new jobs this week. Nothing sent, nothing recorded.")
        return

    total = job_count_since(since)
    subs = active_subscribers()
    print(f"{total} new jobs, showing {len(jobs)}. {len(subs)} active subscribers.")

    if not subs:
        print("No subscribers yet. Nothing sent.")
        return

    subject = (
        f"{total} new job{'' if total == 1 else 's'} in Tripura and beyond - "
        f"{datetime.now(timezone.utc).strftime('%d %b')}"
    )

    if DRY_RUN:
        print("\n--- DRY RUN: nothing will be emailed ---")
        print("Subject:", subject)
        print(build_text(jobs, total, f"{SITE}/unsubscribe.html?token=SAMPLE"))
        print("Would email:", ", ".join(s["email"] for s in subs))
        return

    sent, failed = 0, 0
    context = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
        server.login(GMAIL_USER, GMAIL_PASS)
        for s in subs:
            unsub = f"{SITE}/unsubscribe.html?token={s['token']}"
            msg = EmailMessage()
            msg["Subject"] = subject
            msg["From"] = formataddr((FROM_NAME, GMAIL_USER))
            msg["To"] = s["email"]
            msg["List-Unsubscribe"] = f"<{unsub}>"
            msg.set_content(build_text(jobs, total, unsub))
            msg.add_alternative(build_html(jobs, total, unsub), subtype="html")
            try:
                server.send_message(msg)
                sent += 1
                sb.table("subscribers").update(
                    {"last_sent_at": datetime.now(timezone.utc).isoformat()}
                ).eq("id", s["id"]).execute()
            except Exception as err:
                failed += 1
                print(f"  ! could not send to {s['email']}: {err}")

    sb.table("email_sends").insert(
        {
            "kind": "job_alert",
            "job_count": total,
            "sent_to": sent,
            "failed": failed,
        }
    ).execute()

    print(f"Done. Sent {sent}, failed {failed}.")


if __name__ == "__main__":
    main()
