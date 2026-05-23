import requests
import smtplib
import time
import os
import re
import hashlib
import json
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime, timezone, timedelta
from html.parser import HTMLParser
from io import BytesIO

# ============================================================
#   CONFIG — Edit this section only
#   When deploying to GitHub Actions, these come from Secrets
# ============================================================

YOUR_NAME               = os.environ.get("YOUR_NAME",             "Your Name")
YOUR_EMAIL              = os.environ.get("YOUR_EMAIL",            "you@gmail.com")
YOUR_GMAIL              = os.environ.get("YOUR_GMAIL",            "you@gmail.com")
YOUR_GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD",    "xxxx xxxx xxxx xxxx")
GEMINI_API_KEY          = os.environ.get("GEMINI_API_KEY",        "AIzaSy...")
JOB_KEYWORDS            = os.environ.get("JOB_KEYWORDS",          "Software Engineer")
JOB_LOCATION            = os.environ.get("JOB_LOCATION",          "Bengaluru")
JOBS_TARGET             = 20   # Minimum jobs to collect across all sources

YOUR_BASE_RESUME = """
PASTE YOUR FULL RESUME HERE

John Doe
john@email.com | +91-XXXXXXXXXX | linkedin.com/in/johndoe | github.com/johndoe

SUMMARY
Recent Computer Science graduate with strong foundation in Python, Java, and web development.
Built 3 personal projects including a REST API and a machine learning classifier.

EDUCATION
B.Tech Computer Science | XYZ University | 2024 | CGPA: 8.5/10

PROJECTS
E-Commerce REST API | Python, FastAPI, PostgreSQL
- Built fully functional REST API with authentication and payment integration
- Deployed on AWS EC2, handles 500+ requests/minute

ML Spam Classifier | Python, scikit-learn
- Trained model on 10,000 emails achieving 97% accuracy

SKILLS
Python, Java, JavaScript, React, SQL, Git, Docker, REST APIs, Machine Learning basics

CERTIFICATIONS
AWS Cloud Practitioner | Google Data Analytics Certificate
"""

# ============================================================
#   HELPER — seen jobs dedup via hash
# ============================================================

seen_hashes = set()

def job_hash(title, company):
    key = f"{title.lower().strip()}|{company.lower().strip()}"
    return hashlib.md5(key.encode()).hexdigest()

def is_duplicate(title, company):
    h = job_hash(title, company)
    if h in seen_hashes:
        return True
    seen_hashes.add(h)
    return False

def is_fresher_role(title, description=""):
    """Filter: keep only fresher/entry-level jobs, skip experienced roles."""
    title_lower = title.lower()
    desc_lower = description.lower()

    # Must NOT have experience requirements
    exp_red_flags = [
        r'\b[2-9]\+?\s*years?\b', r'\b1[0-9]\+?\s*years?\b',
        'senior', 'lead', 'principal', 'staff engineer', 'manager',
        'director', 'vp ', 'head of', '5+ yrs', '3+ yrs', '4+ yrs',
        'minimum 2', 'minimum 3', 'at least 2', 'at least 3'
    ]
    for flag in exp_red_flags:
        if re.search(flag, title_lower) or re.search(flag, desc_lower):
            return False

    # Prefer fresher/entry-level signals (optional boost, not mandatory filter)
    fresher_signals = [
        'fresher', 'entry level', 'entry-level', 'junior', 'graduate',
        'intern', '0-1 year', '0-2 year', 'trainee', 'associate',
        'new grad', 'campus', 'recent graduate', 'no experience required'
    ]
    # If title has senior/lead explicitly, skip
    if any(w in title_lower for w in ['senior', 'lead', 'principal', 'staff']):
        return False

    return True  # Accept if no red flags found

def within_48_hours(date_str):
    """Returns True if date_str is within the last 48 hours. Flexible parser."""
    if not date_str:
        return True  # Unknown date — include it
    date_str = date_str.lower().strip()
    now = datetime.now(timezone.utc)

    # Relative: "2 hours ago", "1 day ago", "just now", "today"
    if 'just now' in date_str or 'today' in date_str or 'hour' in date_str or 'minute' in date_str:
        return True
    if '1 day ago' in date_str or 'yesterday' in date_str:
        return True
    if '2 days ago' in date_str:
        return True
    # If says "3 days ago" or more — skip
    match = re.search(r'(\d+)\s*days?\s*ago', date_str)
    if match and int(match.group(1)) > 2:
        return False
    # Absolute date
    for fmt in ('%Y-%m-%dT%H:%M:%S', '%Y-%m-%d', '%B %d, %Y', '%b %d, %Y'):
        try:
            dt = datetime.strptime(date_str[:19], fmt).replace(tzinfo=timezone.utc)
            return (now - dt) <= timedelta(hours=48)
        except:
            pass
    return True  # Can't parse — include


# ============================================================
#   SOURCE 1 — LinkedIn
# ============================================================

def scrape_linkedin(keywords, location, count=10):
    print("  [LinkedIn] Scraping...")
    jobs = []
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

    # Try multiple start offsets to get more results
    for start in [0, 10, 20]:
        if len(jobs) >= count:
            break
        try:
            url = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
            params = {
                "keywords": f"{keywords} fresher entry level",
                "location": location,
                "f_TPR": "r172800",   # Posted in last 48 hours (172800 seconds)
                "f_E": "1,2",         # Experience level: Internship(1), Entry(2)
                "start": start
            }
            resp = requests.get(url, params=params, headers=headers, timeout=15)

            class LIParser(HTMLParser):
                def __init__(self):
                    super().__init__()
                    self.jobs = []
                    self.current = {}
                    self.capture = None
                def handle_starttag(self, tag, attrs):
                    d = dict(attrs)
                    cls = d.get("class", "")
                    if tag == "div" and "base-card" in cls:
                        self.current = {}
                    if tag == "h3" and "base-search-card__title" in cls:
                        self.capture = "title"
                    if tag == "h4" and "base-search-card__subtitle" in cls:
                        self.capture = "company"
                    if tag == "span" and "job-search-card__location" in cls:
                        self.capture = "location"
                    if tag == "time":
                        self.current["date"] = d.get("datetime", "")
                    if tag == "a" and "base-card__full-link" in cls:
                        self.current["url"] = d.get("href", "")
                def handle_data(self, data):
                    if self.capture and data.strip():
                        self.current[self.capture] = data.strip()
                        if self.capture == "location":
                            self.jobs.append(self.current.copy())
                        self.capture = None

            p = LIParser()
            p.feed(resp.text)
            for j in p.jobs:
                if not j.get("title") or not j.get("company"):
                    continue
                if is_duplicate(j["title"], j["company"]):
                    continue
                if not within_48_hours(j.get("date", "")):
                    continue
                if not is_fresher_role(j["title"]):
                    continue
                j["source"] = "LinkedIn"
                jobs.append(j)
            time.sleep(1)
        except Exception as e:
            print(f"  [LinkedIn] Error: {e}")

    print(f"  [LinkedIn] Got {len(jobs)} jobs")
    return jobs


# ============================================================
#   SOURCE 2 — Indeed (via RSS feed — no scraping needed)
# ============================================================

def scrape_indeed(keywords, location, count=10):
    print("  [Indeed] Scraping via RSS...")
    jobs = []
    try:
        # Indeed public RSS — no API key needed
        query = f"{keywords} fresher entry level"
        url = f"https://www.indeed.com/rss?q={requests.utils.quote(query)}&l={requests.utils.quote(location)}&fromage=2&sort=date"
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=15)

        # Parse RSS XML
        items = re.findall(r'<item>(.*?)</item>', resp.text, re.DOTALL)
        for item in items[:count]:
            title  = re.search(r'<title><!\[CDATA\[(.*?)\]\]>', item)
            comp   = re.search(r'<source[^>]*>(.*?)</source>', item)
            loc    = re.search(r'<location>(.*?)</location>', item)
            link   = re.search(r'<link>(.*?)</link>', item)
            date   = re.search(r'<pubDate>(.*?)</pubDate>', item)
            desc   = re.search(r'<description><!\[CDATA\[(.*?)\]\]>', item, re.DOTALL)

            title_text = title.group(1).strip() if title else keywords
            company    = comp.group(1).strip()  if comp  else "Unknown"
            loc_text   = loc.group(1).strip()   if loc   else location
            link_text  = link.group(1).strip()  if link  else ""
            date_text  = date.group(1).strip()  if date  else ""
            desc_text  = re.sub(r'<[^>]+>', ' ', desc.group(1)) if desc else ""

            if is_duplicate(title_text, company):
                continue
            if not within_48_hours(date_text):
                continue
            if not is_fresher_role(title_text, desc_text):
                continue

            jobs.append({
                "title": title_text,
                "company": company,
                "location": loc_text,
                "url": link_text,
                "description": desc_text[:500],
                "date": date_text,
                "source": "Indeed"
            })
    except Exception as e:
        print(f"  [Indeed] Error: {e}")

    print(f"  [Indeed] Got {len(jobs)} jobs")
    return jobs


# ============================================================
#   SOURCE 3 — Wellfound (AngelList) via public search
# ============================================================

def scrape_wellfound(keywords, location, count=10):
    print("  [Wellfound] Scraping...")
    jobs = []
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml"
        }
        query = f"{keywords} entry level"
        url = f"https://wellfound.com/jobs?q={requests.utils.quote(query)}&l={requests.utils.quote(location)}"
        resp = requests.get(url, headers=headers, timeout=15)

        # Extract job cards from Wellfound HTML
        # Wellfound renders some data in JSON inside script tags
        json_match = re.search(r'"jobListings"\s*:\s*(\[.*?\])\s*[,}]', resp.text, re.DOTALL)
        if json_match:
            try:
                listings = json.loads(json_match.group(1))
                for j in listings[:count]:
                    title   = j.get("title", "")
                    company = j.get("startup", {}).get("name", "Unknown")
                    loc     = j.get("locationNames", [location])[0] if j.get("locationNames") else location
                    link    = "https://wellfound.com" + j.get("slug", "")
                    date    = j.get("createdAt", "")

                    if is_duplicate(title, company):
                        continue
                    if not within_48_hours(date):
                        continue
                    if not is_fresher_role(title):
                        continue

                    jobs.append({
                        "title": title,
                        "company": company,
                        "location": loc,
                        "url": link,
                        "date": date,
                        "source": "Wellfound"
                    })
            except:
                pass

        # Fallback: regex extract from HTML
        if not jobs:
            titles   = re.findall(r'"title":"([^"]+)"', resp.text)
            companies = re.findall(r'"name":"([^"]+)"', resp.text)
            for i, title in enumerate(titles[:count]):
                company = companies[i] if i < len(companies) else "Startup"
                if is_duplicate(title, company):
                    continue
                if not is_fresher_role(title):
                    continue
                jobs.append({
                    "title": title,
                    "company": company,
                    "location": location,
                    "url": "https://wellfound.com/jobs",
                    "source": "Wellfound"
                })
    except Exception as e:
        print(f"  [Wellfound] Error: {e}")

    print(f"  [Wellfound] Got {len(jobs)} jobs")
    return jobs


# ============================================================
#   SOURCE 4 — RemoteOK (great for remote/fresher jobs)
# ============================================================

def scrape_remoteok(keywords, count=10):
    print("  [RemoteOK] Scraping via API...")
    jobs = []
    try:
        url = "https://remoteok.com/api"
        headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
        resp = requests.get(url, headers=headers, timeout=15)
        data = resp.json()

        keyword_lower = keywords.lower()
        for item in data:
            if not isinstance(item, dict) or not item.get("position"):
                continue
            title   = item.get("position", "")
            company = item.get("company", "Unknown")
            tags    = " ".join(item.get("tags", []))
            desc    = item.get("description", "")
            date    = item.get("date", "")
            link    = item.get("url", "https://remoteok.com")

            # Filter by keyword relevance
            if keyword_lower not in title.lower() and keyword_lower not in tags.lower():
                continue
            if is_duplicate(title, company):
                continue
            if not within_48_hours(date):
                continue
            if not is_fresher_role(title, desc):
                continue

            jobs.append({
                "title": title,
                "company": company,
                "location": "Remote",
                "url": link,
                "description": re.sub(r'<[^>]+>', ' ', desc)[:500],
                "date": date,
                "source": "RemoteOK"
            })
            if len(jobs) >= count:
                break
    except Exception as e:
        print(f"  [RemoteOK] Error: {e}")

    print(f"  [RemoteOK] Got {len(jobs)} jobs")
    return jobs


# ============================================================
#   SOURCE 5 — Adzuna (has a free API tier)
# ============================================================

def scrape_adzuna(keywords, location, count=10):
    """Adzuna free API — register at developer.adzuna.com for free keys."""
    print("  [Adzuna] Skipping (add ADZUNA_APP_ID + ADZUNA_API_KEY env vars to enable)")
    # To enable: register free at developer.adzuna.com, add secrets, uncomment below
    #
    # app_id  = os.environ.get("ADZUNA_APP_ID", "")
    # api_key = os.environ.get("ADZUNA_API_KEY", "")
    # if not app_id or not api_key:
    #     return []
    # url = f"https://api.adzuna.com/v1/api/jobs/in/search/1"
    # params = {"app_id": app_id, "app_key": api_key, "what": keywords,
    #           "where": location, "max_days_old": 2, "results_per_page": count,
    #           "title_only": keywords}
    # resp = requests.get(url, params=params, timeout=15).json()
    # for j in resp.get("results", []):
    #     ... parse and append
    return []


# ============================================================
#   TAILOR RESUME WITH GEMINI
# ============================================================

def tailor_resume_with_gemini(job, base_resume):
    print(f"  Tailoring for: {job['title']} @ {job['company']}")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"

    prompt = f"""You are an expert resume writer helping a fresher land their first job.

JOB DETAILS:
Title: {job['title']}
Company: {job['company']}
Location: {job.get('location', 'N/A')}
Source: {job.get('source', 'N/A')}
Description: {job.get('description', 'Not provided')}

CANDIDATE BASE RESUME:
{base_resume}

TASK: Rewrite the resume specifically for this job. Rules:
1. Write a 2-line tailored OBJECTIVE at the top for this exact role
2. Use keywords from the job description naturally in bullet points
3. Emphasize skills/projects most relevant to this role
4. NEVER invent facts — only reframe existing content
5. Keep it clean, ATS-friendly, under 1 page worth of text
6. At the end add a "WHY I'M A STRONG FIT" section with 3 bullet points
7. Format with clear sections: OBJECTIVE, EDUCATION, PROJECTS, SKILLS, CERTIFICATIONS

Output ONLY the resume text. No commentary, no markdown, no backticks."""

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.6, "maxOutputTokens": 1500}
    }
    try:
        resp = requests.post(url, json=payload, timeout=30)
        data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        print(f"  Gemini error: {e}")
        return base_resume


# ============================================================
#   GENERATE PDF with ReportLab
# ============================================================

def generate_resume_pdf(resume_text, job):
    """Convert resume plain text to a clean PDF. Returns bytes."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
    from reportlab.lib.enums import TA_LEFT, TA_CENTER

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=15*mm, rightMargin=15*mm,
        topMargin=12*mm, bottomMargin=12*mm
    )

    # Styles
    styles = getSampleStyleSheet()
    heading_style = ParagraphStyle(
        'SectionHead', fontSize=10, fontName='Helvetica-Bold',
        textColor=colors.HexColor('#1a3c6e'), spaceBefore=8, spaceAfter=2
    )
    normal_style = ParagraphStyle(
        'Body', fontSize=9, fontName='Helvetica',
        leading=13, spaceAfter=2
    )
    title_style = ParagraphStyle(
        'Title', fontSize=14, fontName='Helvetica-Bold',
        alignment=TA_CENTER, spaceAfter=4,
        textColor=colors.HexColor('#1a3c6e')
    )
    subtitle_style = ParagraphStyle(
        'Sub', fontSize=8, fontName='Helvetica',
        alignment=TA_CENTER, spaceAfter=6, textColor=colors.grey
    )

    story = []

    # Header
    story.append(Paragraph(YOUR_NAME, title_style))
    story.append(Paragraph(
        f"Tailored for: {job['title']} at {job['company']} ({job.get('source','')})",
        subtitle_style
    ))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#1a3c6e')))
    story.append(Spacer(1, 4))

    # Parse resume text into sections
    section_keywords = ['OBJECTIVE', 'SUMMARY', 'EDUCATION', 'EXPERIENCE',
                        'PROJECTS', 'SKILLS', 'CERTIFICATIONS', 'WHY I']

    lines = resume_text.strip().split('\n')
    for line in lines:
        line = line.strip()
        if not line:
            story.append(Spacer(1, 3))
            continue

        # Detect section headers
        is_header = any(line.upper().startswith(kw) for kw in section_keywords)
        if is_header:
            story.append(HRFlowable(width="100%", thickness=0.5, color=colors.lightgrey))
            story.append(Paragraph(line.upper(), heading_style))
        elif line.startswith('-') or line.startswith('•'):
            # Bullet point — indent
            safe_line = line.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            story.append(Paragraph(f"&nbsp;&nbsp;&nbsp;{safe_line}", normal_style))
        else:
            safe_line = line.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            story.append(Paragraph(safe_line, normal_style))

    # Footer
    story.append(Spacer(1, 6))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.lightgrey))
    story.append(Paragraph(
        f"Generated {datetime.now().strftime('%B %d, %Y')} | Apply at: {job.get('url', 'N/A')}",
        subtitle_style
    ))

    doc.build(story)
    return buffer.getvalue()


# ============================================================
#   SEND EMAIL WITH PDF ATTACHMENTS
# ============================================================

def send_email(jobs_with_resumes):
    print(f"\nSending email with {len(jobs_with_resumes)} applications...")
    today = datetime.now().strftime("%B %d, %Y")

    # Count by source
    sources = {}
    for item in jobs_with_resumes:
        src = item["job"].get("source", "Other")
        sources[src] = sources.get(src, 0) + 1
    source_summary = " | ".join([f"{v} from {k}" for k, v in sources.items()])

    # HTML email body
    html_body = f"""
<html>
<body style="font-family:Arial,sans-serif; max-width:750px; margin:0 auto; padding:20px; color:#1a1a1a;">
<div style="background:#1a3c6e; padding:20px; border-radius:8px; margin-bottom:20px;">
  <h1 style="color:white; margin:0;">Your Daily Job Applications</h1>
  <p style="color:#aac4f0; margin:8px 0 0;">{today} &nbsp;|&nbsp; {len(jobs_with_resumes)} roles found &nbsp;|&nbsp; {source_summary}</p>
</div>
"""
    for i, item in enumerate(jobs_with_resumes, 1):
        job = item["job"]
        safe_title = job['title'].replace('&','&amp;')
        safe_co    = job['company'].replace('&','&amp;')
        src_color  = {"LinkedIn":"#0077b5","Indeed":"#003a9b","Wellfound":"#fb6404",
                      "RemoteOK":"#09c372"}.get(job.get("source",""), "#555")
        html_body += f"""
<div style="border:1px solid #e0e0e0; border-radius:6px; padding:16px; margin:12px 0;">
  <div style="display:flex; justify-content:space-between; align-items:center;">
    <h2 style="margin:0; font-size:15px;">#{i} &mdash; {safe_title}</h2>
    <span style="background:{src_color}; color:white; padding:2px 8px; border-radius:12px; font-size:11px;">{job.get('source','')}</span>
  </div>
  <p style="margin:6px 0; color:#555;">
    <b>Company:</b> {safe_co} &nbsp;&nbsp;
    <b>Location:</b> {job.get('location','N/A')} &nbsp;&nbsp;
    <b>Posted:</b> {job.get('date','Recent')}
  </p>
  <p style="margin:4px 0;">
    <a href="{job.get('url','#')}" style="color:#1a3c6e; font-weight:bold;">Apply Now &rarr;</a>
  </p>
  <p style="margin:6px 0; font-size:12px; color:#888;">PDF resume attached as: Resume_{i}_{job['title'][:20].replace(' ','_')}.pdf</p>
</div>"""

    html_body += """
<hr style="margin-top:30px;"/>
<p style="color:#aaa; font-size:11px;">Generated by your AI Job Bot | Ran on GitHub Actions (free)</p>
</body></html>"""

    try:
        msg = MIMEMultipart("mixed")
        msg["Subject"] = f"Job Bot: {len(jobs_with_resumes)} Tailored Applications — {today}"
        msg["From"]    = YOUR_GMAIL
        msg["To"]      = YOUR_EMAIL
        msg.attach(MIMEText(html_body, "html"))

        # Attach each resume as PDF
        for i, item in enumerate(jobs_with_resumes, 1):
            job = item["job"]
            print(f"  Generating PDF {i}/{len(jobs_with_resumes)}: {job['title'][:40]}")
            pdf_bytes = generate_resume_pdf(item["tailored_resume"], job)
            filename  = f"Resume_{i}_{job['title'][:20].replace(' ','_').replace('/','')}.pdf"

            part = MIMEBase("application", "octet-stream")
            part.set_payload(pdf_bytes)
            encoders.encode_base64(part)
            part.add_header("Content-Disposition", f'attachment; filename="{filename}"')
            msg.attach(part)

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(YOUR_GMAIL, YOUR_GMAIL_APP_PASSWORD)
            server.sendmail(YOUR_GMAIL, YOUR_EMAIL, msg.as_string())

        print(f"Email sent to {YOUR_EMAIL} with {len(jobs_with_resumes)} PDF attachments")

    except Exception as e:
        print(f"Email error: {e}")
        raise


# ============================================================
#   MAIN PIPELINE
# ============================================================

def run_job_bot():
    print(f"\n{'='*55}")
    print(f"Job Bot Starting — {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"Target: {JOB_KEYWORDS} | {JOB_LOCATION} | Min {JOBS_TARGET} jobs")
    print(f"{'='*55}\n")

    all_jobs = []

    # Scrape all sources
    print("--- Collecting jobs from all sources ---")
    all_jobs += scrape_linkedin(JOB_KEYWORDS, JOB_LOCATION, 10)
    all_jobs += scrape_indeed(JOB_KEYWORDS, JOB_LOCATION, 10)
    all_jobs += scrape_wellfound(JOB_KEYWORDS, JOB_LOCATION, 8)
    all_jobs += scrape_remoteok(JOB_KEYWORDS, 8)
    all_jobs += scrape_adzuna(JOB_KEYWORDS, JOB_LOCATION, 5)

    print(f"\nTotal collected: {len(all_jobs)} jobs (after dedup + fresher filter + 48h filter)")

    if not all_jobs:
        print("No jobs found. Will retry tomorrow.")
        return

    # Limit to target count
    jobs_to_process = all_jobs[:JOBS_TARGET]
    print(f"Processing {len(jobs_to_process)} jobs...\n")

    # Tailor resumes
    print("--- Tailoring resumes with Gemini ---")
    results = []
    for i, job in enumerate(jobs_to_process, 1):
        print(f"[{i}/{len(jobs_to_process)}]", end=" ")
        tailored = tailor_resume_with_gemini(job, YOUR_BASE_RESUME)
        results.append({"job": job, "tailored_resume": tailored})
        time.sleep(1.5)  # Rate limit Gemini free tier

    # Send email with PDF attachments
    print("\n--- Sending email ---")
    send_email(results)

    print(f"\nDone! {len(results)} tailored PDF resumes sent to {YOUR_EMAIL}")
    print("="*55)


if __name__ == "__main__":
    run_job_bot()
