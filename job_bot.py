import requests
import smtplib
import time
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime

# ============================================================
#   CONFIG — reads from GitHub Secrets (environment variables)
#   If running locally, hardcode values between the quotes
# ============================================================

YOUR_NAME             = os.environ.get("YOUR_NAME", "Your Name")
YOUR_EMAIL            = os.environ.get("YOUR_EMAIL", "you@gmail.com")
YOUR_GMAIL            = os.environ.get("YOUR_GMAIL", "you@gmail.com")
YOUR_GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "xxxx xxxx xxxx xxxx")
GEMINI_API_KEY        = os.environ.get("GEMINI_API_KEY", "AIzaSy...")
JOB_KEYWORDS          = os.environ.get("JOB_KEYWORDS", "Product Manager")
JOB_LOCATION          = os.environ.get("JOB_LOCATION", "Bengaluru")
JOBS_PER_RUN          = 5

YOUR_BASE_RESUME = """
JANANI P | janani.prasath.03@gmail.com | +91-9025601507
Bengaluru, India | LinkedIn | GitHub
SUMMARY
Final-year B.E. Computer Science (Data Science) student with strong experience in AI, data analytics, and full-stack development. Skilled in building AI-powered solutions, data-driven dashboards, and scalable systems using Python, SQL, NLP, and cloud tools. Proven ability to deliver impactful projects, research contributions, and innovative solutions through internships and hackathons.
EXPERIENCE
Integration Engineer Intern | ClearTax | Jan 2026 – Apr 2026 | Bengaluru, India
Integrated ERP systems with ClearTax SaaS products using SQL-based data validation and Retool dashboards
Ensured accurate financial data flow and reduced reconciliation errors
Used Agent AI and SQL queries to streamline data processing and troubleshoot integration issues
Improved operational efficiency across multiple client accounts
Data Analyst Intern | Fidelity Investments | May 2025 – Jul 2025 | Bengaluru, India
Conducted research on employee lifecycle and identified 100+ critical attributes
Mapped attributes to enterprise data lake ensuring business-relevant coverage
Built optimized SQL views in Snowflake and interactive Power BI dashboards
Enabled HR teams to derive actionable insights from workforce data
Developed NLP-based conversational QA interface to reduce manual reporting efforts
PROJECTS
SmartEval – Automated Answer Sheet Evaluation System
Technologies: Computer Vision, NLP, Python, OCR (Gemini)
Built AI system to extract answers from scanned sheets and evaluate using semantic similarity
Designed automated pipeline: text extraction → preprocessing → similarity scoring → result generation
Created visualization interface for marks, feedback, and analytics
NyayPath
Technologies: MongoDB, Node.js, Bashini API, Solidity, JWT
Developed digital platform for mediation services in India
Enabled case filing, tracking, and mediator matching via web, IVR, and SMS
Integrated multilingual support, gamification, and discussion forums
JurisSecure – Offenders Registry DApp
Technologies: Web3, Node.js, HTML, CSS, Solidity
Built decentralized registry for secure identity verification
Ensured tamper-proof storage of offender data using blockchain
Oil Spill Detection System
Technologies: Python, TensorFlow, Deep Learning
Developed detection models using U-Net (ResNet-18) and DeepLabV3+ (MobileNetV3)
Optimized accuracy and reduced false positives in SAR imagery
Built preprocessing, training, and visualization pipeline
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
Published research at IEEE ICWITE 2025 on oil leak detection using SAR imagery
Secured 1st place in Final Year Project Exhibition (Automated Answer Sheet Evaluation System)
Winner – AI Innovation Day Hackathon (Microsoft & id8nxt)
Selected for national-level Bhasha Bandhu Hackathon
Top 3 in Web3 track at national-level AVENTUS hackathon
CERTIFICATIONS
Google Data Analytics Professional Certificate
AI Primer Certification – Infosys Springboard
"""

# ============================================================
#   SCRAPE LINKEDIN JOBS
# ============================================================

def scrape_linkedin_jobs(keywords, location, count=5):
    print(f"Scraping LinkedIn for: {keywords} in {location}")
    jobs = []
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    url = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
    params = {"keywords": keywords, "location": location, "start": 0}

    try:
        response = requests.get(url, params=params, headers=headers, timeout=15)
        from html.parser import HTMLParser

        class JobParser(HTMLParser):
            def __init__(self):
                super().__init__()
                self.jobs = []
                self.current_job = {}
                self.capture = None

            def handle_starttag(self, tag, attrs):
                attrs_dict = dict(attrs)
                if tag == "div" and "base-card" in attrs_dict.get("class", ""):
                    self.current_job = {}
                if tag == "h3" and "base-search-card__title" in attrs_dict.get("class", ""):
                    self.capture = "title"
                if tag == "h4" and "base-search-card__subtitle" in attrs_dict.get("class", ""):
                    self.capture = "company"
                if tag == "span" and "job-search-card__location" in attrs_dict.get("class", ""):
                    self.capture = "location"
                if tag == "a" and "base-card__full-link" in attrs_dict.get("class", ""):
                    self.current_job["url"] = attrs_dict.get("href", "")

            def handle_data(self, data):
                if self.capture and data.strip():
                    self.current_job[self.capture] = data.strip()
                    if self.capture == "location" and self.current_job.get("title"):
                        self.jobs.append(self.current_job.copy())
                    self.capture = None

        parser = JobParser()
        parser.feed(response.text)
        jobs = parser.jobs[:count]

        if not jobs:
            print("LinkedIn returned no results, using fallback test data")
            jobs = [{"title": keywords, "company": "Test Company", "location": location,
                     "url": "https://linkedin.com/jobs",
                     "description": f"Looking for a {keywords} to join our growing team."}]

        print(f"Found {len(jobs)} jobs")
        return jobs

    except Exception as e:
        print(f"Scraping error: {e}")
        return []


# ============================================================
#   TAILOR RESUME WITH GEMINI (FREE)
# ============================================================

def tailor_resume_with_gemini(job, base_resume):
    print(f"Tailoring resume for: {job['title']} at {job['company']}")

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"

    prompt = f"""You are an expert resume writer.

JOB:
Title: {job['title']}
Company: {job['company']}
Location: {job.get('location', 'N/A')}
Description: {job.get('description', 'Not provided')}

CANDIDATE RESUME:
{base_resume}

Rewrite the resume tailored for this specific job. Use keywords from the job description.
Keep all facts true — do not invent anything. Add a 2-line tailored summary at the top.
At the end, add "WHY THIS ROLE FITS" with 3 bullet points.
Output ONLY the resume text, nothing else."""

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.7, "maxOutputTokens": 1500}
    }

    try:
        response = requests.post(url, json=payload, timeout=30)
        data = response.json()
        tailored = data["candidates"][0]["content"]["parts"][0]["text"]
        print("Resume tailored successfully")
        return tailored
    except Exception as e:
        print(f"Gemini error: {e}")
        return base_resume


# ============================================================
#   SEND EMAIL
# ============================================================

def send_email(jobs_with_resumes):
    print(f"Sending email with {len(jobs_with_resumes)} applications...")
    today = datetime.now().strftime("%B %d, %Y")

    html_body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px;">
    <h1 style="color: #2d5be3;">Your Daily Job Applications</h1>
    <p style="color: #666;">{today} | {len(jobs_with_resumes)} roles for <b>{JOB_KEYWORDS}</b> in <b>{JOB_LOCATION}</b></p>
    <hr/>
    """

    for i, item in enumerate(jobs_with_resumes, 1):
        job = item["job"]
        resume = item["tailored_resume"]
        html_body += f"""
        <div style="background:#f9f9f9; border-left:4px solid #2d5be3; padding:20px; margin:20px 0; border-radius:4px;">
            <h2 style="margin-top:0;">#{i} — {job['title']}</h2>
            <p><b>Company:</b> {job['company']}</p>
            <p><b>Location:</b> {job.get('location','N/A')}</p>
            <p><b>Apply:</b> <a href="{job.get('url','#')}">{job.get('url','N/A')}</a></p>
            <details>
                <summary style="cursor:pointer; color:#2d5be3; font-weight:bold;">Click to view tailored resume</summary>
                <pre style="background:white; padding:15px; border:1px solid #ddd; white-space:pre-wrap; font-size:13px;">{resume}</pre>
            </details>
        </div>
        """

    html_body += "<hr/><p style='color:#999; font-size:12px;'>Your AI Job Bot</p></body></html>"

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"{len(jobs_with_resumes)} Tailored Applications Ready — {today}"
        msg["From"] = YOUR_GMAIL
        msg["To"] = YOUR_EMAIL
        msg.attach(MIMEText(html_body, "html"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(YOUR_GMAIL, YOUR_GMAIL_APP_PASSWORD)
            server.sendmail(YOUR_GMAIL, YOUR_EMAIL, msg.as_string())

        print(f"Email sent to {YOUR_EMAIL}")
    except Exception as e:
        print(f"Email error: {e}")


# ============================================================
#   MAIN
# ============================================================

def run_job_bot():
    print(f"\n{'='*50}")
    print(f"Job Bot Starting — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*50}")

    jobs = scrape_linkedin_jobs(JOB_KEYWORDS, JOB_LOCATION, JOBS_PER_RUN)
    if not jobs:
        print("No jobs found today.")
        return

    results = []
    for job in jobs:
        tailored = tailor_resume_with_gemini(job, YOUR_BASE_RESUME)
        results.append({"job": job, "tailored_resume": tailored})
        time.sleep(2)

    send_email(results)
    print(f"\nDone! Processed {len(results)} jobs.")


if __name__ == "__main__":
    run_job_bot()
