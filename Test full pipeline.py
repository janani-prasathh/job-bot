"""
Run this on GitHub Actions manually as a separate test.
It tests each component independently and shows exactly where the failure is.
Add it to your repo and run: python test_full_pipeline.py
"""
import os, smtplib, ssl, requests
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

YOUR_GMAIL          = os.environ.get("YOUR_GMAIL", "")
YOUR_EMAIL          = os.environ.get("YOUR_EMAIL", "")
GMAIL_APP_PASSWORD  = os.environ.get("GMAIL_APP_PASSWORD", "")
GEMINI_API_KEY      = os.environ.get("GEMINI_API_KEY", "")
JOB_KEYWORDS        = os.environ.get("JOB_KEYWORDS", "Data Analyst")
JOB_LOCATION        = os.environ.get("JOB_LOCATION", "Bengaluru")

print("\n" + "="*55)
print("FULL PIPELINE TEST")
print("="*55)

# ── TEST 1: JobSpy scraping ───────────────────────────────
print("\n[TEST 1] Job Scraping")
try:
    from jobspy import scrape_jobs
    df = scrape_jobs(
        site_name=["indeed", "google"],
        search_term=f"{JOB_KEYWORDS} fresher",
        location=JOB_LOCATION,
        results_wanted=3,
        hours_old=72,
        country_indeed="India",
        verbose=0,
    )
    print(f"  ✅ Scraping works — found {len(df)} jobs")
    if len(df) > 0:
        print(f"  Sample: {df.iloc[0]['title']} @ {df.iloc[0]['company']}")
    else:
        print("  ⚠️  0 jobs found — try broadening keywords or increasing hours_old")
except Exception as e:
    print(f"  ❌ Scraping failed: {e}")

# ── TEST 2: Gemini API ────────────────────────────────────
print("\n[TEST 2] Gemini API")
try:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    payload = {"contents": [{"parts": [{"text": "Say HELLO in one word"}]}]}
    resp = requests.post(url, json=payload, timeout=15)
    data = resp.json()
    if "error" in data:
        print(f"  ❌ Gemini error: {data['error'].get('message')}")
    else:
        reply = data["candidates"][0]["content"]["parts"][0]["text"]
        print(f"  ✅ Gemini works — replied: {reply.strip()}")
except Exception as e:
    print(f"  ❌ Gemini failed: {e}")

# ── TEST 3: Email port 465 ────────────────────────────────
print("\n[TEST 3] Gmail SMTP — port 465")
try:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Job Bot — GitHub Actions Test Email"
    msg["From"]    = YOUR_GMAIL
    msg["To"]      = YOUR_EMAIL
    msg.attach(MIMEText("<h2>✅ GitHub Actions email works!</h2><p>The job bot pipeline is healthy.</p>", "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
        s.login(YOUR_GMAIL, GMAIL_APP_PASSWORD)
        s.sendmail(YOUR_GMAIL, YOUR_EMAIL, msg.as_string())
    print(f"  ✅ Email sent to {YOUR_EMAIL} — check inbox now")
except smtplib.SMTPAuthenticationError as e:
    print(f"  ❌ Auth failed: {e}")
    print("     → App password wrong or 2FA not enabled")
except Exception as e:
    print(f"  ❌ Port 465 failed: {type(e).__name__}: {e}")
    # Try port 587
    print("\n[TEST 3b] Gmail SMTP — port 587 fallback")
    try:
        ctx = ssl.create_default_context()
        with smtplib.SMTP("smtp.gmail.com", 587) as s:
            s.ehlo()
            s.starttls(context=ctx)
            s.ehlo()
            s.login(YOUR_GMAIL, GMAIL_APP_PASSWORD)
            s.sendmail(YOUR_GMAIL, YOUR_EMAIL, msg.as_string())
        print(f"  ✅ Port 587 works — email sent to {YOUR_EMAIL}")
    except Exception as e2:
        print(f"  ❌ Port 587 also failed: {type(e2).__name__}: {e2}")
        print("     → GitHub Actions may be blocking outbound SMTP")
        print("     → Switch to SendGrid or Gmail API (see below)")

print("\n" + "="*55)
print("TEST COMPLETE — check results above")
print("="*55 + "\n")
