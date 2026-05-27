"""
AI Job Bot — Janani P
Scrapes fresher jobs posted in last 72h, generates one base resume PDF,
emails all job links + the PDF. No AI tailoring — 100% reliable.
"""

import smtplib, time, os, re, hashlib, ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime, timezone
from io import BytesIO

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
#  CONFIG
# ═══════════════════════════════════════════════════════════════════════════════

YOUR_NAME               = os.environ.get("YOUR_NAME",            "Janani P")
YOUR_EMAIL              = os.environ.get("YOUR_EMAIL",           "itsjananiprasath@gmail.com")
YOUR_GMAIL              = os.environ.get("YOUR_GMAIL",           "itsjananiprasath@gmail.com")
YOUR_GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD",   "")
JOB_KEYWORDS            = os.environ.get("JOB_KEYWORDS",         "AI Engineer").strip()
JOB_LOCATION            = os.environ.get("JOB_LOCATION",         "Bengaluru, India").strip()
JOBS_TARGET             = 20
HOURS_OLD               = 72

YOUR_BASE_RESUME = """JANANI P
janani.prasath.03@gmail.com | +91-9025601507 | Bengaluru, India | LinkedIn | GitHub

SUMMARY
Final-year B.E. Computer Science (Data Science) student with strong experience in AI,
data analytics, and full-stack development. Skilled in building AI-powered solutions,
data-driven dashboards, and scalable systems using Python, SQL, NLP, and cloud tools.

EXPERIENCE

Integration Engineer Intern | ClearTax | Jan 2026 - Apr 2026 | Bengaluru
- Integrated ERP systems with ClearTax SaaS using SQL-based data validation and Retool dashboards
- Used Agent AI and SQL queries to streamline data processing and troubleshoot integration issues
- Improved operational efficiency across multiple client accounts

Data Analyst Intern | Fidelity Investments | May 2025 - Jul 2025 | Bengaluru
- Identified 100+ critical employee lifecycle attributes mapped to enterprise data lake
- Built optimized SQL views in Snowflake and interactive Power BI dashboards
- Developed NLP-based conversational QA interface to reduce manual reporting efforts

PROJECTS

SmartEval - Automated Answer Sheet Evaluation System
Technologies: Computer Vision, NLP, Python, OCR (Gemini)
- Built AI system to extract and evaluate answers using semantic similarity
- Designed pipeline: text extraction, preprocessing, similarity scoring, result generation
- 1st place in Final Year Project Exhibition

NyayPath - Digital Mediation Platform
Technologies: MongoDB, Node.js, Solidity, JWT
- Developed platform for mediation services enabling case filing and mediator matching
- Integrated multilingual support, IVR, SMS, and discussion forums

JurisSecure - Offenders Registry DApp
Technologies: Web3, Node.js, Solidity
- Built decentralized registry for secure tamper-proof identity verification

Oil Spill Detection System
Technologies: Python, TensorFlow, Deep Learning
- Developed U-Net (ResNet-18) and DeepLabV3+ (MobileNetV3) detection models
- Published research at IEEE ICWITE 2025

EDUCATION
B.E. Computer Science (Data Science) | Bangalore Institute of Technology | 2022-2026
CGPA: 9.04 | Bengaluru, Karnataka

SKILLS
Programming  : Python, SQL (Postgres), R, MongoDB
Platforms    : Google Cloud, Power BI, Tableau, BigQuery, Snowflake
Libraries    : Pandas, NumPy, Matplotlib, Scikit-learn
Technologies : NLP, LLMs, RAG, Blockchain, Data Warehousing, Agile
AI Tools     : OpenAI, Claude, Gemini, n8n, Make

ACHIEVEMENTS
- Published at IEEE ICWITE 2025 — Oil Leak Detection using SAR Imagery
- Winner — AI Innovation Day Hackathon (Microsoft & id8nxt)
- Top 3 — Web3 track, national-level AVENTUS Hackathon
- Selected — National-level Bhasha Bandhu Hackathon

CERTIFICATIONS
- Google Data Analytics Professional Certificate
- AI Primer Certification — Infosys Springboard
"""

# ═══════════════════════════════════════════════════════════════════════════════
#  DEDUP + FILTER
# ═══════════════════════════════════════════════════════════════════════════════

_seen = set()

def is_duplicate(title, company):
    h = hashlib.md5(f"{str(title).lower().strip()}|{str(company).lower().strip()}".encode()).hexdigest()
    if h in _seen: return True
    _seen.add(h)
    return False

SENIORITY = re.compile(r'\b(senior|lead|principal|staff|manager|director|head|vp)\b', re.IGNORECASE)

# ═══════════════════════════════════════════════════════════════════════════════
#  SCRAPE
# ═══════════════════════════════════════════════════════════════════════════════

def scrape_all_jobs(keywords, location, target):
    print(f"\n--- Scraping: '{keywords}' in '{location}' ---")
    all_jobs = []

    variants = [
        f"{keywords} fresher",
        f"{keywords} entry level",
        f"junior {keywords}",
        f"{keywords} trainee",
        f"{keywords} 0 years experience",
        f"{keywords}",
        f"{keywords} graduate",
    ]

    for term in variants:
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
                verbose=0,
            )
            if df is None or len(df) == 0:
                print(f"    No results")
                continue

            print(f"    Raw: {len(df)}")
            added = 0
            for _, row in df.iterrows():
                title   = str(row.get("title", "") or "")
                company = str(row.get("company", "") or "Unknown")
                loc     = str(row.get("location", "") or location)
                url     = str(row.get("job_url", "") or "")
                date    = row.get("date_posted")
                source  = str(row.get("site", "") or "").capitalize()

                if not title or not company: continue
                if is_duplicate(title, company): continue
                if SENIORITY.search(title): continue

                all_jobs.append({
                    "title":   title,
                    "company": company,
                    "location": loc,
                    "url":     url,
                    "date":    str(date) if date else "Recent",
                    "source":  source,
                })
                added += 1

            print(f"    After filter: +{added} (total: {len(all_jobs)})")
            time.sleep(2)

        except Exception as e:
            print(f"    Error: {e}")
            time.sleep(3)

    print(f"\nTotal jobs collected: {len(all_jobs)}")
    return all_jobs[:target]

# ═══════════════════════════════════════════════════════════════════════════════
#  GENERATE BASE RESUME PDF
# ═══════════════════════════════════════════════════════════════════════════════

def make_resume_pdf():
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=14*mm, rightMargin=14*mm,
        topMargin=10*mm, bottomMargin=10*mm
    )

    name_style = ParagraphStyle("Name", fontSize=15, fontName="Helvetica-Bold",
                                 alignment=TA_CENTER, textColor=colors.HexColor("#1a3c6e"), spaceAfter=2)
    sub_style  = ParagraphStyle("Sub", fontSize=8, fontName="Helvetica",
                                 alignment=TA_CENTER, textColor=colors.grey, spaceAfter=5)
    head_style = ParagraphStyle("Head", fontSize=10, fontName="Helvetica-Bold",
                                 textColor=colors.HexColor("#1a3c6e"), spaceBefore=7, spaceAfter=2)
    body_style = ParagraphStyle("Body", fontSize=8.5, fontName="Helvetica", leading=13, spaceAfter=1)

    story = []
    story.append(Paragraph(YOUR_NAME, name_style))
    story.append(Paragraph(f"Generated {datetime.now().strftime('%d %b %Y')}", sub_style))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#1a3c6e")))
    story.append(Spacer(1, 3))

    SECTION_HEADERS = {"SUMMARY","EXPERIENCE","PROJECTS","EDUCATION","SKILLS","ACHIEVEMENTS","CERTIFICATIONS"}

    def safe(t): return t.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")

    for line in YOUR_BASE_RESUME.strip().split("\n"):
        line = line.strip()
        if not line:
            story.append(Spacer(1, 2))
            continue
        if any(line.upper().startswith(h) for h in SECTION_HEADERS):
            story.append(HRFlowable(width="100%", thickness=0.4, color=colors.lightgrey))
            story.append(Paragraph(line.upper(), head_style))
        elif line.startswith(("- ", "• ")):
            story.append(Paragraph(f"&nbsp;&nbsp;&nbsp;{safe(line)}", body_style))
        else:
            story.append(Paragraph(safe(line), body_style))

    doc.build(story)
    return buffer.getvalue()

# ═══════════════════════════════════════════════════════════════════════════════
#  SEND EMAIL
# ═══════════════════════════════════════════════════════════════════════════════

def send_email(jobs, resume_pdf):
    today = datetime.now().strftime("%B %d, %Y")
    n = len(jobs)

    # Count by source
    sources = {}
    for j in jobs:
        s = j.get("source","Other")
        sources[s] = sources.get(s, 0) + 1
    src_line = " | ".join(f"{v} from {k}" for k, v in sources.items())

    SOURCE_COLORS = {
        "Indeed":"#003a9b", "Linkedin":"#0077b5", "Google":"#ea4335",
        "Glassdoor":"#0caa41", "Zip_recruiter":"#4a90d9"
    }

    # Build HTML
    html = f"""<html><body style="font-family:Arial,sans-serif;max-width:750px;margin:0 auto;padding:20px;">
<div style="background:#1a3c6e;padding:20px;border-radius:8px;margin-bottom:20px;">
  <h1 style="color:white;margin:0;">Your Daily Job Listings</h1>
  <p style="color:#aac4f0;margin:8px 0 0;">{today} &nbsp;|&nbsp; {n} jobs found &nbsp;|&nbsp; {src_line}</p>
</div>
<p style="color:#555;">Your resume is attached as a PDF. For each job below, click Apply, upload the PDF, and customise your cover letter if needed.</p>
<hr/>
"""
    for i, j in enumerate(jobs, 1):
        t  = j["title"].replace("&","&amp;")
        co = j["company"].replace("&","&amp;")
        c  = SOURCE_COLORS.get(j.get("source",""), "#555")
        html += f"""
<div style="border:1px solid #e0e0e0;border-radius:6px;padding:14px;margin:10px 0;">
  <div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:6px;">
    <h2 style="margin:0;font-size:14px;">#{i} &mdash; {t}</h2>
    <span style="background:{c};color:white;padding:2px 10px;border-radius:12px;font-size:11px;">{j.get('source','')}</span>
  </div>
  <p style="margin:6px 0;color:#444;font-size:13px;">
    <b>{co}</b> &nbsp;·&nbsp; {j.get('location','N/A')} &nbsp;·&nbsp; Posted: {j.get('date','Recent')}
  </p>
  <a href="{j.get('url','#')}" style="display:inline-block;background:#1a3c6e;color:white;padding:6px 16px;border-radius:4px;text-decoration:none;font-size:13px;margin-top:4px;">Apply Now →</a>
</div>"""

    html += """
<hr style="margin-top:30px;"/>
<p style="color:#aaa;font-size:11px;">AI Job Bot · Runs daily at 7 AM IST · GitHub Actions (free)</p>
</body></html>"""

    # Build email
    msg = MIMEMultipart("mixed")
    msg["Subject"] = f"Job Bot: {n} Fresh Jobs for You — {today}"
    msg["From"]    = YOUR_GMAIL
    msg["To"]      = YOUR_EMAIL
    msg.attach(MIMEText(html, "html"))

    # Attach resume PDF
    part = MIMEBase("application", "octet-stream")
    part.set_payload(resume_pdf)
    encoders.encode_base64(part)
    part.add_header("Content-Disposition", f'attachment; filename="Janani_P_Resume.pdf"')
    msg.attach(part)

    # Send — try port 465, fallback to 587
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
            s.login(YOUR_GMAIL, YOUR_GMAIL_APP_PASSWORD)
            s.sendmail(YOUR_GMAIL, YOUR_EMAIL, msg.as_string())
        print(f"  Email sent via port 465 to {YOUR_EMAIL}")
    except Exception as e:
        print(f"  Port 465 failed ({e}), trying 587...")
        ctx = ssl.create_default_context()
        with smtplib.SMTP("smtp.gmail.com", 587) as s:
            s.ehlo(); s.starttls(context=ctx); s.ehlo()
            s.login(YOUR_GMAIL, YOUR_GMAIL_APP_PASSWORD)
            s.sendmail(YOUR_GMAIL, YOUR_EMAIL, msg.as_string())
        print(f"  Email sent via port 587 to {YOUR_EMAIL}")

# ═══════════════════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def run():
    print("=" * 60)
    print(f"Job Bot  |  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"Target   :  {JOB_KEYWORDS} in {JOB_LOCATION}")
    print(f"Mode     :  Job links + base resume PDF (no AI tailoring)")
    print("=" * 60)

    if not YOUR_GMAIL_APP_PASSWORD:
        raise SystemExit("ERROR: GMAIL_APP_PASSWORD secret not set.")

    # Scrape
    jobs = scrape_all_jobs(JOB_KEYWORDS, JOB_LOCATION, JOBS_TARGET)

    if not jobs:
        print("No jobs found. Not sending email.")
        return

    print(f"\nFound {len(jobs)} jobs.")

    # Generate single resume PDF
    print("Generating resume PDF...")
    resume_pdf = make_resume_pdf()
    print(f"  PDF generated ({len(resume_pdf)} bytes)")

    # Send email
    print("\n--- Sending email ---")
    send_email(jobs, resume_pdf)

    print(f"\nDone — {len(jobs)} job links + resume PDF sent to {YOUR_EMAIL}")
    print("=" * 60)

if __name__ == "__main__":
    run()
