import requests
import json
import smtplib
import schedule
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime

# ============================================================
#   EDIT ONLY THIS SECTION — YOUR PERSONAL CONFIG
# ============================================================

YOUR_NAME = "Janani P"
YOUR_EMAIL = "itsjananiprasath@gmail.com"           # Gmail you want to receive results
YOUR_GMAIL = "itsjananiprasath@gmail.com"           # Gmail used to SEND (can be same)
YOUR_GMAIL_APP_PASSWORD = "yhyj cbeo fcqs sqbu"   # 16-char app password from Step 2

GEMINI_API_KEY = "AIzaSyAxxSNNR06J0Bbt-4sQ4hpbxv_Igp9t6L4"           # From aistudio.google.com

JOB_KEYWORDS = "AI engineer, Data analyst"      # What job you're looking for
JOB_LOCATION = "Bengaluru"            # Your preferred location
JOBS_PER_RUN = 5                       # How many jobs to process per day

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
#   DO NOT EDIT BELOW THIS LINE
# ============================================================

def scrape_linkedin_jobs(keywords, location, count=5):
    """Scrape jobs from LinkedIn's guest API — no account needed."""
    print(f"🔍 Scraping LinkedIn for: {keywords} in {location}")
    jobs = []
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    url = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
    params = {
        "keywords": keywords,
        "location": location,
        "start": 0,
        "count": count
    }
    
    try:
        response = requests.get(url, params=params, headers=headers, timeout=15)
        
        # Parse the HTML response to extract job info
        from html.parser import HTMLParser
        
        class JobParser(HTMLParser):
            def __init__(self):
                super().__init__()
                self.jobs = []
                self.current_job = {}
                self.capture = None
                self.depth = 0
            
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
            # Fallback: return sample jobs for testing
            print("⚠️  LinkedIn returned no results, using test data")
            jobs = [
                {
                    "title": f"{keywords} - Sample Role",
                    "company": "Sample Company",
                    "location": location,
                    "url": "https://linkedin.com/jobs",
                    "description": f"We are looking for a {keywords} to join our team. You will be responsible for product strategy, roadmap planning, and working with cross-functional teams."
                }
            ]
        
        print(f"✅ Found {len(jobs)} jobs")
        return jobs
        
    except Exception as e:
        print(f"❌ Scraping error: {e}")
        return []


def get_job_description(job_url):
    """Fetch the full job description from the job URL."""
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        response = requests.get(job_url, headers=headers, timeout=10)
        
        # Extract description text from LinkedIn job page
        text = response.text
        start = text.find("show-more-less-html__markup")
        if start != -1:
            start = text.find(">", start) + 1
            end = text.find("</div>", start)
            raw = text[start:end]
            # Strip HTML tags simply
            import re
            clean = re.sub(r'<[^>]+>', ' ', raw).strip()
            return clean[:2000]  # Limit to 2000 chars
        return "No description available"
    except:
        return "Could not fetch job description"


def tailor_resume_with_gemini(job, base_resume):
    """Use Google Gemini (free) to tailor the resume for this specific job."""
    print(f"🤖 Tailoring resume for: {job['title']} at {job['company']}")
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    
    prompt = f"""You are an expert resume writer and career coach.

JOB DETAILS:
Title: {job['title']}
Company: {job['company']}
Location: {job.get('location', 'N/A')}
Description: {job.get('description', 'Not available')}

CANDIDATE'S BASE RESUME:
{base_resume}

TASK:
Rewrite the resume to be highly tailored for THIS specific job. 

Rules:
1. Use keywords from the job description naturally
2. Reorder/reframe bullet points to match what this company values
3. Keep the same factual experience — don't invent anything
4. Add a 2-line tailored summary at the top for this specific role
5. Keep it clean and readable
6. At the end, add a section called "WHY THIS ROLE FITS" with 3 bullet points explaining why the candidate is a strong match

Output ONLY the tailored resume text. No extra commentary."""

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.7, "maxOutputTokens": 1500}
    }
    
    try:
        response = requests.post(url, json=payload, timeout=30)
        data = response.json()
        tailored = data["candidates"][0]["content"]["parts"][0]["text"]
        print(f"✅ Resume tailored successfully")
        return tailored
    except Exception as e:
        print(f"❌ Gemini error: {e}")
        return base_resume  # Fall back to original resume


def send_email(jobs_with_resumes):
    """Send all tailored applications to your email."""
    print(f"📧 Sending email with {len(jobs_with_resumes)} applications...")
    
    today = datetime.now().strftime("%B %d, %Y")
    
    # Build HTML email body
    html_body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px;">
    
    <h1 style="color: #2d5be3;">🤖 Your Daily Job Applications</h1>
    <p style="color: #666;">Generated on {today} | {len(jobs_with_resumes)} roles found for <b>{JOB_KEYWORDS}</b> in <b>{JOB_LOCATION}</b></p>
    <hr/>
    """
    
    for i, item in enumerate(jobs_with_resumes, 1):
        job = item["job"]
        resume = item["tailored_resume"]
        
        html_body += f"""
        <div style="background: #f9f9f9; border-left: 4px solid #2d5be3; padding: 20px; margin: 20px 0; border-radius: 4px;">
            <h2 style="color: #1a1a1a; margin-top: 0;">#{i} — {job['title']}</h2>
            <p><b>🏢 Company:</b> {job['company']}</p>
            <p><b>📍 Location:</b> {job.get('location', 'N/A')}</p>
            <p><b>🔗 Apply here:</b> <a href="{job.get('url', '#')}">{job.get('url', 'N/A')}</a></p>
            
            <details>
                <summary style="cursor: pointer; color: #2d5be3; font-weight: bold; margin-top: 15px;">
                    📄 Click to view your tailored resume for this role
                </summary>
                <pre style="background: white; padding: 15px; border: 1px solid #ddd; border-radius: 4px; white-space: pre-wrap; font-size: 13px; margin-top: 10px;">{resume}</pre>
            </details>
        </div>
        """
    
    html_body += """
    <hr/>
    <p style="color: #999; font-size: 12px;">Generated by your AI Job Bot 🤖 | Running 24/7 on Render.com</p>
    </body>
    </html>
    """
    
    # Send via Gmail SMTP
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"🤖 {len(jobs_with_resumes)} Tailored Applications Ready — {today}"
        msg["From"] = YOUR_GMAIL
        msg["To"] = YOUR_EMAIL
        
        msg.attach(MIMEText(html_body, "html"))
        
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(YOUR_GMAIL, YOUR_GMAIL_APP_PASSWORD)
            server.sendmail(YOUR_GMAIL, YOUR_EMAIL, msg.as_string())
        
        print(f"✅ Email sent successfully to {YOUR_EMAIL}")
        
    except Exception as e:
        print(f"❌ Email error: {e}")


def run_job_bot():
    """Main function — runs the full pipeline."""
    print(f"\n{'='*50}")
    print(f"🚀 Job Bot Starting — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*50}")
    
    # Step 1: Scrape jobs
    jobs = scrape_linkedin_jobs(JOB_KEYWORDS, JOB_LOCATION, JOBS_PER_RUN)
    
    if not jobs:
        print("No jobs found today. Will try again tomorrow.")
        return
    
    # Step 2: For each job, get description + tailor resume
    results = []
    for job in jobs:
        # Try to get full job description
        if job.get("url") and job["url"].startswith("http"):
            job["description"] = get_job_description(job["url"])
        
        # Tailor resume with Gemini
        tailored = tailor_resume_with_gemini(job, YOUR_BASE_RESUME)
        results.append({"job": job, "tailored_resume": tailored})
        
        time.sleep(2)  # Be polite to APIs
    
    # Step 3: Send email
    send_email(results)
    
    print(f"\n✅ Done! Processed {len(results)} jobs.")


# ============================================================
#   SCHEDULER — Runs every day at 7:00 AM
# ============================================================

if __name__ == "__main__":
    print("🤖 Job Bot is running...")
    print(f"   Looking for: {JOB_KEYWORDS} in {JOB_LOCATION}")
    print(f"   Will email: {YOUR_EMAIL}")
    print(f"   Scheduled: Every day at 07:00 AM")
    print()
    
    # Run once immediately on startup (for testing)
    run_job_bot()
    
    # Then schedule daily at 7am
    schedule.every().day.at("07:00").do(run_job_bot)
    
    while True:
        schedule.run_pending()
        time.sleep(60)
