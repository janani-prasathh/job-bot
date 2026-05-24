"""
AI Job Bot — Janani P
Scrapes fresher jobs posted in last 48h via Google Jobs (JobSpy),
tailors each resume with Gemini, generates PDF, emails all attachments.

Deploy: GitHub Actions (free) — runs daily at 7 AM IST
"""

import smtplib, time, os, re, hashlib, json
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime, timezone, timedelta
from io import BytesIO

# ── try imports (installed via requirements.txt) ─────────────────────────────
try:
    import requests
except ImportError:
    raise SystemExit("Run: pip install requests")

try:
    from jobspy import scrape_jobs
except ImportError:
    raise SystemExit("Run: pip install python-jobspy")

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
    from reportlab.lib.enums import TA_CENTER
except ImportError:
    raise SystemExit("Run: pip install reportlab")

# ═══════════════════════════════════════════════════════════════════════════════
#  CONFIG  — only edit lines marked ← EDIT
#  On GitHub Actions these come from Repository Secrets (env vars)
# ═══════════════════════════════════════════════════════════════════════════════

YOUR_NAME               = os.environ.get("YOUR_NAME",            "Janani P")
YOUR_EMAIL              = os.environ.get("YOUR_EMAIL",           "janani.prasath.03@gmail.com")
YOUR_GMAIL              = os.environ.get("YOUR_GMAIL",           "janani.prasath.03@gmail.com")
YOUR_GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD",   "")   # ← EDIT or set Secret
GEMINI_API_KEY          = os.environ.get("GEMINI_API_KEY",       "")   # ← EDIT or set Secret
JOB_KEYWORDS            = os.environ.get("JOB_KEYWORDS",         "Data Analyst")
JOB_LOCATION            = os.environ.get("JOB_LOCATION",         "Bengaluru, India")
JOBS_TARGET             = 20
HOURS_OLD               = 72   # Jobs posted in last 72 hours (was 48, relaxed)

YOUR_BASE_RESUME = """
JANANI P | janani.prasath.03@gmail.com | +91-9025601507
Bengaluru, India | LinkedIn | GitHub

SUMMARY
Final-year B.E. Computer Science (Data Science) student with strong experience in AI, data analytics, and full-stack development. Skilled in building AI-powered solutions, data-driven dashboards, and scalable systems using Python, SQL, NLP, and cloud tools. Proven ability to deliver impactful projects, research contributions, and innovative solutions through internships and hackathons.

EXPERIENCE
Integration Engineer Intern | ClearTax | Jan 2026 – Apr 2026 | Bengaluru, India
- Integrated ERP systems with ClearTax SaaS products using SQL-based data validation and Retool dashboards
- Ensured accurate financial data flow and reduced reconciliation errors
- Used Agent AI and SQL queries to streamline data processing and troubleshoot integration issues
- Improved operational efficiency across multiple client accounts

Data Analyst Intern | Fidelity Investments | May 2025 – Jul 2025 | Bengaluru, India
- Conducted research on employee lifecycle and identified 100+ critical attributes
- Mapped attributes to enterprise data lake ensuring business-relevant coverage
- Built optimized SQL views in Snowflake and interactive Power BI dashboards
- Enabled HR teams to derive actionable insights from workforce data
- Developed NLP-based conversational QA interface to reduce manual reporting efforts

PROJECTS
SmartEval – Automated Answer Sheet Evaluation System
Technologies: Computer Vision, NLP, Python, OCR (Gemini)
- Built AI system to extract answers from scanned sheets and evaluate using semantic similarity
- Designed automated pipeline: text extraction → preprocessing → similarity scoring → result generation
- Created visualization interface for marks, feedback, and analytics

NyayPath
Technologies: MongoDB, Node.js, Bashini API, Solidity, JWT
- Developed digital platform for mediation services in India
- Enabled case filing, tracking, and mediator matching via web, IVR, and SMS
- Integrated multilingual support, gamification, and discussion forums

JurisSecure – Offenders Registry DApp
Technologies: Web3, Node.js, HTML, CSS, Solidity
- Built decentralized registry for secure identity verification
- Ensured tamper-proof storage of offender data using blockchain

Oil Spill Detection System
Technologies: Python, TensorFlow, Deep Learning
- Developed detection models using U-Net (ResNet-18) and DeepLabV3+ (MobileNetV3)
- Optimized accuracy and reduced false positives in SAR imagery
- Built preprocessing, training, and visualization pipeline

EDUCATION
B.E. Computer Science (Data Science) | Bangalore Institute of Technology | 2022 – 2026
CGPA: 9.04 | Bengaluru, Karnataka

SKILLS
Programming: Python, SQL (Postgres), R, MongoDB
Tools & Platforms: Google Cloud Platform, Power BI, Tableau, BigQuery, Snowflake
Libraries: Pandas, NumPy, Matplotlib, Scikit-learn
Technologies: NLP, LLMs, RAG, Blockchain, DBMS, Data Warehousing, Agile
Concepts: OOPs, Operating Systems, Git
AI Tools: OpenAI, Claude, Gemini, n8n, Make

ACHIEVEMENTS
- Published research at IEEE ICWITE 2025 on oil leak detection using SAR imagery
- Secured 1st place in Final Year Project Exhibition (Automated Answer Sheet Evaluation System)
- Winner – AI Innovation Day Hackathon (Microsoft & id8nxt)
- Selected for national-level Bhasha Bandhu Hackathon
- Top 3 in Web3 track at national-level AVENTUS hackathon

CERTIFICATIONS
Google Data Analytics Professional Certificate
AI Primer Certification – Infosys Springboard
"""

# ═══════════════════════════════════════════════════════════════════════════════
#  DEDUP HELPER
# ═══════════════════════════════════════════════════════════════════════════════

_seen = set()

def is_duplicate(title, company):
    h = hashlib.md5(f"{str(title).lower().strip()}|{str(company).lower().strip()}".encode()).hexdigest()
    if h in _seen:
        return True
    _seen.add(h)
    return False

# ═══════════════════════════════════════════════════════════════════════════════
#  FRESHER FILTER
# ═══════════════════════════════════════════════════════════════════════════════

EXPERIENCE_RED_FLAGS = re.compile(
    r'\b([2-9]|\d{2})\+?\s*years?\b'
    r'|senior|lead\b|principal|staff engineer|manager|director|head of|vp\b'
    r'|minimum [2-9]|at least [2-9]|[3-9]\+\s*yrs',
    re.IGNORECASE
)
SENIORITY_IN_TITLE = re.compile(r'\b(senior|lead|principal|staff|manager|director|head)\b', re.IGNORECASE)

def is_fresher_role(title, description=""):
    if SENIORITY_IN_TITLE.search(str(title)):
        return False
    if EXPERIENCE_RED_FLAGS.search(str(description)):
        return False
    return True

# ═══════════════════════════════════════════════════════════════════════════════
#  SCRAPE — uses JobSpy which routes through Google Jobs (no IP blocking)
# ═══════════════════════════════════════════════════════════════════════════════

def scrape_all_jobs(keywords, location, target):
    """
    Uses python-jobspy which aggregates from multiple sources.
    Google Jobs and Indeed work reliably from any IP including GitHub Actions.
    LinkedIn may be blocked — that's OK, Google Jobs covers it indirectly.
    """
    print(f"\n--- Scraping jobs: '{keywords}' in '{location}' ---")
    all_jobs = []

    # Search terms: fresher-specific first, then broader fallbacks
    search_variants = [
        f"{keywords} fresher",
        f"{keywords} entry level",
        f"junior {keywords}",
        f"{keywords} trainee",
        f"{keywords} 0 years experience",
        f"{keywords}",               # broad fallback — no fresher filter in query
        f"{keywords} graduate",
    ]

    for term in search_variants:
        if len(all_jobs) >= target * 2:
            break
        try:
            print(f"  Searching: '{term}'")
            df = scrape_jobs(
                site_name=["indeed", "linkedin", "google", "glassdoor", "zip_recruiter"],
                search_term=term,
                location=location,
                results_wanted=15,
                hours_old=HOURS_OLD,
                country_indeed="India",
                linkedin_fetch_description=True,
                verbose=0,
            )

            if df is None or len(df) == 0:
                print(f"    No results")
                continue

            print(f"    Raw results: {len(df)}")
            count_added = 0

            for _, row in df.iterrows():
                title   = str(row.get("title", "") or "")
                company = str(row.get("company", "") or "Unknown")
                loc     = str(row.get("location", "") or location)
                url     = str(row.get("job_url", "") or "")
                desc    = str(row.get("description", "") or "")
                date    = row.get("date_posted")
                source  = str(row.get("site", "") or "JobSpy")

                # Filters
                if not title or not company:
                    continue
                if is_duplicate(title, company):
                    continue
                # Only apply fresher filter on title — description filter was too aggressive
                if SENIORITY_IN_TITLE.search(title):
                    continue

                all_jobs.append({
                    "title":       title,
                    "company":     company,
                    "location":    loc,
                    "url":         url,
                    "description": desc[:3000],
                    "date":        str(date) if date else "Recent",
                    "source":      source.capitalize(),
                })
                count_added += 1

            print(f"    After filters: +{count_added} (total so far: {len(all_jobs)})")
            time.sleep(2)

        except Exception as e:
            print(f"    Error on '{term}': {e}")
            time.sleep(3)

    print(f"\nTotal unique fresher jobs collected: {len(all_jobs)}")
    return all_jobs[:target]


# ═══════════════════════════════════════════════════════════════════════════════
#  GEMINI RESUME TAILORING
# ═══════════════════════════════════════════════════════════════════════════════

def similarity_ratio(a, b):
    w1, w2 = set(a.lower().split()), set(b.lower().split())
    if not w1 or not w2:
        return 1.0
    return len(w1 & w2) / max(len(w1), len(w2))


def call_gemini(prompt, temperature=0.8):
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    )
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": temperature, "maxOutputTokens": 2000},
    }
    resp = requests.post(url, json=payload, timeout=45)
    data = resp.json()
    if "error" in data:
        raise ValueError(f"Gemini error: {data['error'].get('message', data['error'])}")
    return data["candidates"][0]["content"]["parts"][0]["text"].strip()


def tailor_resume(job, base_resume):
    title   = job["title"]
    company = job["company"]
    jd      = job.get("description", "")

    if not jd or len(jd) < 60:
        jd = f"Role: {title} at {company} in {job.get('location','')}. Looking for a {title} to join the team."

    print(f"  [{job['source']}] {title} @ {company} | JD: {len(jd)} chars")

    prompt = f"""You are a professional resume writer. Rewrite the candidate's resume to be SPECIFICALLY tailored for this ONE job.

=== JOB POSTING ===
Title: {title}
Company: {company}
Location: {job.get('location', '')}
Description:
{jd[:2500]}

=== CANDIDATE RESUME ===
{base_resume}

=== INSTRUCTIONS ===
You MUST produce a resume that is noticeably different from the input for THIS specific job.

Required changes (all mandatory):
1. OBJECTIVE (first section): 2-3 sentences. MUST explicitly name "{title}" and "{company}". Must reference a specific requirement from the JD above.
2. Extract the 5 most important keywords/skills from the JD. Use each one naturally in at least one bullet point.
3. Reorder SKILLS section — put JD-relevant skills first.
4. In PROJECTS, reframe the most relevant project's bullet points to echo the JD language.
5. Final section "WHY I FIT {company.upper()}": 3 bullet points each directly addressing a specific JD requirement with evidence from the resume.

Formatting rules:
- Section headers in ALL CAPS
- Bullet points start with -
- No markdown, no backticks, no preamble text
- Output ONLY the resume — start directly with "JANANI P"
"""

    try:
        result = call_gemini(prompt, temperature=0.85)
        # Strip any accidental markdown fences
        result = re.sub(r"^```[a-z]*\n?", "", result, flags=re.MULTILINE).replace("```", "").strip()

        # Similarity check — if too similar, retry harder
        sim = similarity_ratio(base_resume, result)
        if sim > 0.90:
            print(f"    Similarity {sim:.0%} too high — retrying")
            prompt += f"\n\nWARNING: Previous attempt was {sim:.0%} identical to input. You MUST rewrite more aggressively. The OBJECTIVE and WHY I FIT sections must be completely new text specific to {company}."
            result = call_gemini(prompt, temperature=0.95)
            result = re.sub(r"^```[a-z]*\n?", "", result, flags=re.MULTILINE).replace("```", "").strip()

        final_sim = similarity_ratio(base_resume, result)
        print(f"    Done — similarity to base: {final_sim:.0%}, length: {len(result)} chars")
        return result

    except Exception as e:
        print(f"    Gemini failed: {e}")
        return None


# ═══════════════════════════════════════════════════════════════════════════════
#  PDF GENERATION
# ═══════════════════════════════════════════════════════════════════════════════

def make_pdf(resume_text, job):
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=14*mm, rightMargin=14*mm,
        topMargin=10*mm, bottomMargin=10*mm
    )

    name_style = ParagraphStyle("Name", fontSize=15, fontName="Helvetica-Bold",
                                 alignment=TA_CENTER, textColor=colors.HexColor("#1a3c6e"),
                                 spaceAfter=2)
    sub_style  = ParagraphStyle("Sub", fontSize=8, fontName="Helvetica",
                                 alignment=TA_CENTER, textColor=colors.grey, spaceAfter=5)
    head_style = ParagraphStyle("Head", fontSize=10, fontName="Helvetica-Bold",
                                 textColor=colors.HexColor("#1a3c6e"), spaceBefore=7, spaceAfter=2)
    body_style = ParagraphStyle("Body", fontSize=8.5, fontName="Helvetica",
                                 leading=13, spaceAfter=1)

    story = []

    # Header block
    story.append(Paragraph(YOUR_NAME, name_style))
    story.append(Paragraph(
        f"Tailored for: <b>{job['title']}</b> at <b>{job['company']}</b> "
        f"| Source: {job['source']} | {job.get('date','Recent')}",
        sub_style
    ))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#1a3c6e")))
    story.append(Spacer(1, 3))

    SECTION_HEADERS = {
        "OBJECTIVE", "SUMMARY", "EXPERIENCE", "EDUCATION",
        "PROJECTS", "SKILLS", "ACHIEVEMENTS", "CERTIFICATIONS",
        "WHY I FIT"
    }

    def safe(text):
        return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    for line in resume_text.strip().split("\n"):
        line = line.strip()
        if not line:
            story.append(Spacer(1, 2))
            continue

        upper = line.upper()
        is_section = any(upper.startswith(h) for h in SECTION_HEADERS)

        if is_section:
            story.append(HRFlowable(width="100%", thickness=0.4, color=colors.lightgrey))
            story.append(Paragraph(line.upper(), head_style))
        elif line.startswith(("- ", "• ")):
            story.append(Paragraph(f"&nbsp;&nbsp;&nbsp;{safe(line)}", body_style))
        else:
            story.append(Paragraph(safe(line), body_style))

    story.append(Spacer(1, 5))
    story.append(HRFlowable(width="100%", thickness=0.4, color=colors.lightgrey))
    story.append(Paragraph(
        f"Apply: <a href='{job.get('url','')}'>{job.get('url','N/A')[:80]}</a> "
        f"| Generated {datetime.now().strftime('%d %b %Y')}",
        sub_style
    ))

    doc.build(story)
    return buffer.getvalue()


# ═══════════════════════════════════════════════════════════════════════════════
#  EMAIL
# ═══════════════════════════════════════════════════════════════════════════════

def _send_no_jobs_email():
    """Send a simple notification when no jobs are found so you know the bot ran."""
    today = datetime.now().strftime("%B %d, %Y")
    html = f"""<html><body style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:20px;">
<div style="background:#1a3c6e;padding:20px;border-radius:8px;">
  <h2 style="color:white;margin:0;">Job Bot Ran — No New Jobs Today</h2>
  <p style="color:#aac4f0;margin:8px 0 0;">{today}</p>
</div>
<div style="padding:20px;border:1px solid #e0e0e0;border-radius:8px;margin-top:16px;">
  <p>The bot ran successfully but found <b>0 jobs</b> matching your filters:</p>
  <ul>
    <li>Keywords: <b>{JOB_KEYWORDS}</b></li>
    <li>Location: <b>{JOB_LOCATION}</b></li>
    <li>Posted in last: <b>{HOURS_OLD} hours</b></li>
    <li>Level: <b>Fresher / Entry-level only</b></li>
  </ul>
  <p>This can happen on days when few new jobs are posted. Try again tomorrow.</p>
  <p>To get more results, update <b>JOB_KEYWORDS</b> in GitHub Secrets to a broader term like <b>analyst</b> or <b>engineer</b>.</p>
</div>
</body></html>"""
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"Job Bot: No jobs found today — {today}"
        msg["From"]    = YOUR_GMAIL
        msg["To"]      = YOUR_EMAIL
        msg.attach(MIMEText(html, "html"))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
            s.login(YOUR_GMAIL, YOUR_GMAIL_APP_PASSWORD)
            s.sendmail(YOUR_GMAIL, YOUR_EMAIL, msg.as_string())
        print(f"  Notification email sent to {YOUR_EMAIL}")
    except Exception as e:
        print(f"  Could not send notification email: {e}")


def send_email(results):
    today = datetime.now().strftime("%B %d, %Y")
    n = len(results)
    sources = {}
    for item in results:
        s = item["job"].get("source", "Other")
        sources[s] = sources.get(s, 0) + 1
    src_line = " | ".join(f"{v} from {k}" for k, v in sources.items())

    html = f"""<html><body style="font-family:Arial,sans-serif;max-width:750px;margin:0 auto;padding:20px;">
<div style="background:#1a3c6e;padding:20px;border-radius:8px;margin-bottom:20px;">
  <h1 style="color:white;margin:0;">Your Daily Job Applications</h1>
  <p style="color:#aac4f0;margin:8px 0 0;">{today}&nbsp;|&nbsp;{n} roles&nbsp;|&nbsp;{src_line}</p>
</div>
"""
    SOURCE_COLORS = {"Indeed":"#003a9b","Linkedin":"#0077b5","Google":"#ea4335",
                     "Glassdoor":"#0caa41","Zip_recruiter":"#4a90d9"}

    for i, item in enumerate(results, 1):
        j = item["job"]
        c = SOURCE_COLORS.get(j.get("source",""), "#555")
        t = j["title"].replace("&","&amp;")
        co = j["company"].replace("&","&amp;")
        fname = f"Resume_{i}_{j['title'][:18].replace(' ','_').replace('/','')}.pdf"
        html += f"""
<div style="border:1px solid #e0e0e0;border-radius:6px;padding:14px;margin:10px 0;">
  <div style="display:flex;justify-content:space-between;align-items:flex-start;">
    <h2 style="margin:0;font-size:14px;">#{i} &mdash; {t}</h2>
    <span style="background:{c};color:white;padding:2px 8px;border-radius:12px;font-size:11px;white-space:nowrap;">{j.get('source','')}</span>
  </div>
  <p style="margin:5px 0;color:#555;font-size:13px;"><b>{co}</b> &nbsp;·&nbsp; {j.get('location','N/A')} &nbsp;·&nbsp; {j.get('date','Recent')}</p>
  <p style="margin:4px 0;font-size:13px;"><a href="{j.get('url','#')}" style="color:#1a3c6e;font-weight:bold;">Apply Now →</a></p>
  <p style="margin:4px 0;font-size:11px;color:#888;">📎 Tailored PDF attached: {fname}</p>
</div>"""

    html += "<hr/><p style='color:#aaa;font-size:11px;'>AI Job Bot · GitHub Actions (free)</p></body></html>"

    msg = MIMEMultipart("mixed")
    msg["Subject"] = f"🤖 Job Bot: {n} Tailored Applications — {today}"
    msg["From"]    = YOUR_GMAIL
    msg["To"]      = YOUR_EMAIL
    msg.attach(MIMEText(html, "html"))

    for i, item in enumerate(results, 1):
        j = item["job"]
        print(f"  Generating PDF {i}/{n}: {j['title'][:45]}")
        pdf = make_pdf(item["tailored_resume"], j)
        fname = f"Resume_{i}_{j['title'][:18].replace(' ','_').replace('/','')}.pdf"
        part = MIMEBase("application", "octet-stream")
        part.set_payload(pdf)
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", f'attachment; filename="{fname}"')
        msg.attach(part)

    sent = False

    # Try port 465 (SSL) first
    try:
        print("  Trying SMTP port 465 (SSL)...")
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
            s.login(YOUR_GMAIL, YOUR_GMAIL_APP_PASSWORD)
            s.sendmail(YOUR_GMAIL, YOUR_EMAIL, msg.as_string())
        sent = True
        print(f"  Email sent via port 465 to {YOUR_EMAIL} ({n} PDF attachments)")
    except smtplib.SMTPAuthenticationError as e:
        print(f"  Port 465 auth failed: {e}")
        print("  Gmail auth checklist:")
        print("  1. 2-Step Verification ON? myaccount.google.com > Security")
        print("  2. Using App Password (not regular Gmail password)?")
        print("     myaccount.google.com > Security > search App passwords")
        print("  3. App password must be exactly 16 chars")
        print("  4. GitHub Secret GMAIL_APP_PASSWORD set correctly?")
        raise
    except Exception as e:
        print(f"  Port 465 failed ({type(e).__name__}: {e}), trying port 587...")
        try:
            import ssl as _ssl
            ctx = _ssl.create_default_context()
            with smtplib.SMTP("smtp.gmail.com", 587) as s:
                s.ehlo()
                s.starttls(context=ctx)
                s.ehlo()
                s.login(YOUR_GMAIL, YOUR_GMAIL_APP_PASSWORD)
                s.sendmail(YOUR_GMAIL, YOUR_EMAIL, msg.as_string())
            sent = True
            print(f"  Email sent via port 587 to {YOUR_EMAIL} ({n} PDF attachments)")
        except Exception as e2:
            print(f"  Port 587 also failed: {e2}")
            raise

    if not sent:
        raise RuntimeError("Email could not be sent")


# ═══════════════════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def run():
    print("=" * 60)
    print(f"Job Bot  |  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"Target   :  {JOB_KEYWORDS} in {JOB_LOCATION}")
    print(f"Filters  :  Last {HOURS_OLD}h | Fresher/Entry-level | Dedup on")
    print("=" * 60)

    # Guard: secrets must be set
    if not GEMINI_API_KEY:
        raise SystemExit("ERROR: GEMINI_API_KEY is not set. Add it as a GitHub Secret.")
    if not YOUR_GMAIL_APP_PASSWORD:
        raise SystemExit("ERROR: GMAIL_APP_PASSWORD is not set. Add it as a GitHub Secret.")

    # 1. Scrape
    jobs = scrape_all_jobs(JOB_KEYWORDS, JOB_LOCATION, JOBS_TARGET)

    if not jobs:
        print("\nNo jobs found after all filters.")
        print("Sending notification email so you know the bot ran.")
        # Send a notification email so you always get something
        _send_no_jobs_email()
        return

    print(f"\nFound {len(jobs)} jobs. Proceeding to tailor resumes.")

    # 2. Tailor resumes
    print("\n--- Tailoring resumes with Gemini ---")
    results = []
    failed  = 0
    for i, job in enumerate(jobs, 1):
        print(f"[{i}/{len(jobs)}]", end=" ")
        tailored = tailor_resume(job, YOUR_BASE_RESUME)
        if tailored:
            results.append({"job": job, "tailored_resume": tailored})
        else:
            failed += 1
        time.sleep(1.5)   # Gemini free tier: 15 req/min

    print(f"\nTailoring complete: {len(results)} succeeded, {failed} failed")

    if not results:
        print("All tailoring failed — not sending email.")
        return

    # 3. Send email with PDFs
    print("\n--- Generating PDFs and sending email ---")
    send_email(results)

    print(f"\n✓ Done — {len(results)} tailored PDF resumes sent to {YOUR_EMAIL}")
    print("=" * 60)


if __name__ == "__main__":
    run()
