"""
Add this as a temporary step in your workflow to debug what secrets GitHub sees.
It prints lengths and first/last char — never the actual value (safe to share logs).
"""
import os

secrets = {
    "YOUR_NAME":          os.environ.get("YOUR_NAME", ""),
    "YOUR_EMAIL":         os.environ.get("YOUR_EMAIL", ""),
    "YOUR_GMAIL":         os.environ.get("YOUR_GMAIL", ""),
    "GMAIL_APP_PASSWORD": os.environ.get("GMAIL_APP_PASSWORD", ""),
    "GEMINI_API_KEY":     os.environ.get("GEMINI_API_KEY", ""),
    "JOB_KEYWORDS":       os.environ.get("JOB_KEYWORDS", ""),
    "JOB_LOCATION":       os.environ.get("JOB_LOCATION", ""),
}

print("=" * 50)
print("GitHub Secrets Debug")
print("=" * 50)
all_ok = True
for name, val in secrets.items():
    stripped = val.strip()
    if not val:
        status = "MISSING ← not set in GitHub Secrets"
        all_ok = False
    elif val != stripped:
        status = f"HAS EXTRA SPACES (len={len(val)}) ← this will break auth"
        all_ok = False
    else:
        first = val[0] if val else ""
        last  = val[-1] if val else ""
        status = f"OK (len={len(val)}, starts='{first}', ends='{last}')"
    print(f"  {name:25s}: {status}")

print("=" * 50)
if all_ok:
    print("All secrets look OK — proceeding")
else:
    print("Fix the above secrets in GitHub → Settings → Secrets and variables → Actions")
    raise SystemExit(1)
