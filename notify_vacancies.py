"""
Tripura Job Pulse - tell the admin when an employer posts a vacancy

What it does:
  1. Looks for rows in job_submissions that have not been notified yet.
  2. Emails you one message listing all of them, with the contact number
     you need in order to ring the employer back.
  3. Marks them notified, so the next run does not repeat itself.

You promised employers a call within 24 hours. This is what makes that
promise keepable without you remembering to check the admin panel.

Environment variables (GitHub Secrets, same ones the job alerts already use):
  SUPABASE_URL
  SUPABASE_SECRET_KEY      <- secret key. Never put this in website files.
  GMAIL_USER               <- e.g. tripurajobpulse@gmail.com
  GMAIL_APP_PASSWORD       <- the 16-character App Password
  SITE_URL                 <- https://tripurajobpulse.com
  NOTIFY_TO                <- optional, defaults to GMAIL_USER
  DRY_RUN                  <- "true" to print instead of sending
"""

import os
import smtplib
import ssl
from datetime import datetime, timezone
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
NOTIFY_TO = os.environ.get("NOTIFY_TO") or GMAIL_USER
DRY_RUN = os.environ.get("DRY_RUN", "").lower() == "true"

db = create_client(SUPABASE_URL, SUPABASE_KEY)

TYPE_LABEL = {"government": "Government", "private": "Private", "remote": "Remote"}


def summary(line):
    """Write to the run summary, so the result is readable at a glance."""
    print(line)
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if path:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(line + "\n\n")


def rupees(a, b):
    fmt = lambda n: "Rs " + f"{int(n):,}"
    if a and b:
        return f"{fmt(a)} - {fmt(b)} per month"
    if a:
        return f"From {fmt(a)} per month"
    if b:
        return f"Up to {fmt(b)} per month"
    return "Not stated"


def pending():
    """Submissions nobody has been told about yet, oldest first."""
    res = (db.table("job_submissions")
             .select("*")
             .is_("notified_at", "null")
             .order("created_at", desc=False)
             .execute())
    return res.data or []


def plain_text(rows):
    out = [
        f"{len(rows)} new vacanc{'y' if len(rows) == 1 else 'ies'} posted by employers.",
        "",
        "You told them you would call within 24 hours.",
        "",
    ]
    for i, s in enumerate(rows, start=1):
        out += [
            f"{i}. {s['job_title']} - {s['company']}",
            f"   Where:         {s.get('district') or '-'} "
            f"({TYPE_LABEL.get(s.get('job_type'), s.get('job_type'))})",
            f"   Qualification: {s.get('qualification') or '-'}",
            f"   Salary:        {rupees(s.get('salary_min'), s.get('salary_max'))}",
            f"   Closes:        {s.get('last_date') or '-'}",
            f"   CALL:          {s['contact_name']} on {s['contact_phone']}",
        ]
        if s.get("contact_email"):
            out.append(f"   Email:         {s['contact_email']}")
        desc = (s.get("description") or "").strip()
        if desc:
            short = desc if len(desc) <= 300 else desc[:297].rstrip() + "..."
            out += ["   Description:"] + ["     " + ln for ln in short.splitlines()]
        out.append("")
    out += [f"Verify and publish them here: {SITE}/admin-vacancies.html", ""]
    return "\n".join(out)


def html(rows):
    def esc(t):
        return (str(t or "")
                .replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))

    blocks = []
    for s in rows:
        desc = (s.get("description") or "").strip()
        if len(desc) > 300:
            desc = desc[:297].rstrip() + "..."
        blocks.append(f"""
        <tr><td style="padding:0 0 18px">
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
                 style="border:1px solid #DDE8E5;border-radius:12px;border-left:4px solid #D9A13B">
            <tr><td style="padding:16px 18px">
              <div style="font:600 17px/1.3 Segoe UI,Arial,sans-serif;color:#0E4F4C">{esc(s['job_title'])}</div>
              <div style="font:400 15px/1.5 Segoe UI,Arial,sans-serif;color:#5C7572;margin-top:2px">{esc(s['company'])}</div>
              <table role="presentation" cellpadding="0" cellspacing="0"
                     style="font:400 14px/1.7 Segoe UI,Arial,sans-serif;color:#10302E;margin-top:12px">
                <tr><td style="color:#5C7572;padding-right:14px">Where</td><td>{esc(s.get('district') or '-')}
                    &middot; {esc(TYPE_LABEL.get(s.get('job_type'), s.get('job_type')))}</td></tr>
                <tr><td style="color:#5C7572;padding-right:14px">Qualification</td><td>{esc(s.get('qualification') or '-')}</td></tr>
                <tr><td style="color:#5C7572;padding-right:14px">Salary</td><td>{esc(rupees(s.get('salary_min'), s.get('salary_max')))}</td></tr>
                <tr><td style="color:#5C7572;padding-right:14px">Closes</td><td>{esc(s.get('last_date') or '-')}</td></tr>
                <tr><td style="color:#5C7572;padding-right:14px"><b>Call</b></td>
                    <td><b>{esc(s['contact_name'])}</b> &nbsp;
                        <a href="tel:{esc(s['contact_phone'])}"
                           style="color:#15706B;font-weight:600">{esc(s['contact_phone'])}</a>
                        {('&nbsp; &middot; &nbsp;<a href="mailto:' + esc(s['contact_email']) + '" style="color:#15706B">' + esc(s['contact_email']) + '</a>') if s.get('contact_email') else ''}
                    </td></tr>
              </table>
              {('<div style="font:400 14px/1.6 Segoe UI,Arial,sans-serif;color:#5C7572;margin-top:12px;white-space:pre-line">' + esc(desc) + '</div>') if desc else ''}
            </td></tr>
          </table>
        </td></tr>""")

    n = len(rows)
    return f"""<!doctype html><html><body style="margin:0;background:#F4F8F6;padding:24px 12px">
  <table role="presentation" align="center" width="100%" cellpadding="0" cellspacing="0" style="max-width:620px">
    <tr><td style="font:700 20px/1.3 Segoe UI,Arial,sans-serif;color:#0E4F4C;padding-bottom:4px">
      {n} new vacanc{'y' if n == 1 else 'ies'} from employers</td></tr>
    <tr><td style="font:400 15px/1.6 Segoe UI,Arial,sans-serif;color:#5C7572;padding-bottom:20px">
      You told them you would call within 24 hours.</td></tr>
    {''.join(blocks)}
    <tr><td style="padding-top:4px">
      <a href="{SITE}/admin-vacancies.html"
         style="display:inline-block;background:#D9A13B;color:#3A2A06;text-decoration:none;
                font:600 15px Segoe UI,Arial,sans-serif;padding:12px 22px;border-radius:9px">
        Verify and publish</a></td></tr>
    <tr><td style="font:400 13px/1.6 Segoe UI,Arial,sans-serif;color:#8AA09D;padding-top:22px">
      Sent by Tripura Job Pulse because a vacancy was submitted on your site.</td></tr>
  </table></body></html>"""


def send(rows):
    n = len(rows)
    msg = EmailMessage()
    msg["Subject"] = (f"{n} new vacanc{'y' if n == 1 else 'ies'} to verify - "
                      f"{datetime.now(timezone.utc).strftime('%d %b')}")
    msg["From"] = formataddr(("Tripura Job Pulse", GMAIL_USER))
    msg["To"] = NOTIFY_TO
    msg.set_content(plain_text(rows))
    msg.add_alternative(html(rows), subtype="html")

    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ssl.create_default_context()) as smtp:
        smtp.login(GMAIL_USER, GMAIL_PASS)
        smtp.send_message(msg)


def mark_notified(rows):
    stamp = datetime.now(timezone.utc).isoformat()
    for s in rows:
        db.table("job_submissions").update({"notified_at": stamp}).eq("id", s["id"]).execute()


def main():
    summary("## Result")
    summary("**Mode: PRACTICE - no email will be sent.**" if DRY_RUN
            else "**Mode: SENDING FOR REAL.**")

    rows = pending()
    if not rows:
        summary("No new vacancy submissions. Nothing sent.")
        return

    summary(f"{len(rows)} submission(s) waiting:")
    for s in rows:
        summary(f"- **{s['job_title']}** at {s['company']} "
                f"({s.get('district') or '-'}) - call {s['contact_name']} on {s['contact_phone']}")

    if DRY_RUN:
        summary("Nothing was sent and nothing was marked - this was a practice run.")
        print("\n--- DRY RUN, the email would read: ---\n")
        print(plain_text(rows))
        return

    send(rows)
    mark_notified(rows)
    summary(f"Emailed {NOTIFY_TO} and marked {len(rows)} submission(s) as notified.")


if __name__ == "__main__":
    main()
