#!/usr/bin/env python3
"""Send the CANSLIM Visual Guide v2 with all chart examples."""

import smtplib
import json
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from email.mime.application import MIMEApplication

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

with open(os.path.join(os.path.dirname(SCRIPT_DIR), '.gmail-creds.json')) as f:
    creds = json.load(f)

with open(os.path.join(SCRIPT_DIR, 'CANSLIM_VISUAL_GUIDE.md'), 'r') as f:
    guide_text = f.read()

msg = MIMEMultipart('mixed')
msg['From'] = creds['email']
msg['To'] = 'llctechboost@gmail.com'
msg['Subject'] = '📊 CANSLIM Visual Pattern Guide v2 — Every Pattern with Real Chart Examples'

body = """Hey Rah,

Here's the updated CANSLIM Visual Guide — now with real chart screenshots for EVERY pattern type.

📎 ATTACHED FILES:
━━━━━━━━━━━━━━━━
📄 CANSLIM_VISUAL_GUIDE.md — The full guide

📸 7 CHART SCREENSHOTS:
1. GOOGL — Flat Base + Cup with Handle (current setup)
2. AMD — Ascending Base + Cup with Handle (current setup)
3. NU — Ascending Base + VCP + Cup with Handle (current, best setup)
4. NVDA Weekly — Cup with Handle + High Tight Flag (2023-2024)
5. NFLX Weekly — Cup with Handle + Flat Base + Base on Base (2023-2025)
6. META — Cup with Handle + Double Bottom (current)
7. CELH — Cup with Handle + Double Bottom (2025)

📊 EVERY PATTERN COVERED WITH REAL EXAMPLES:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Pattern                  → Example Chart           → Grade
─────────────────────────────────────────────────────────
Cup with Handle          → NFLX, META, CELH, NVDA  → B+ (multiple)
Flat Base ⭐             → NFLX, GOOGL             → A-, B+
High Tight Flag          → NVDA (2023 AI rally)    → B
Ascending Base           → AMD, NU                 → B-, B+
Double Bottom            → CELH, META              → B
VCP                      → NU (inside ascending)   → B+
Base on Base             → NFLX (triple stack)     → A-
Pocket Pivot             → Algorithmic (explained)  → N/A

Each pattern section includes:
✓ Definition & why it works
✓ Exact rules table
✓ What to look for (✅) and avoid (❌)
✓ Real chart with AI vision analysis
✓ Price levels, buy points, stops

Open the guide alongside the chart images for the full experience.

— Rara 🫠
"""

msg.attach(MIMEText(body, 'plain'))

# Attach the guide
with open(os.path.join(SCRIPT_DIR, 'CANSLIM_VISUAL_GUIDE.md'), 'rb') as f:
    att = MIMEApplication(f.read(), _subtype='markdown')
    att.add_header('Content-Disposition', 'attachment', filename='CANSLIM_VISUAL_GUIDE.md')
    msg.attach(att)

# All chart files
charts = [
    ('charts/GOOGL_20260131_2227.png', 'GOOGL — Flat Base + Cup with Handle'),
    ('charts/AMD_20260131_2228.png', 'AMD — Ascending Base'),
    ('charts/NU_20260131_2228.png', 'NU — Ascending Base + VCP + Cup with Handle'),
    ('charts/NVDA_weekly_example.jpg', 'NVDA Weekly — Cup with Handle + HTF'),
    ('charts/NFLX_weekly_example.jpg', 'NFLX Weekly — Cup with Handle + Flat Base + Base on Base'),
    ('charts/META_daily_example.jpg', 'META — Cup with Handle + Double Bottom'),
    ('charts/CELH_daily_example.jpg', 'CELH — Cup with Handle + Double Bottom'),
]

for filename, description in charts:
    filepath = os.path.join(SCRIPT_DIR, filename)
    if os.path.exists(filepath):
        ext = filename.rsplit('.', 1)[-1].lower()
        subtype = 'png' if ext == 'png' else 'jpeg'
        with open(filepath, 'rb') as f:
            img = MIMEImage(f.read(), _subtype=subtype)
            basename = os.path.basename(filename)
            img.add_header('Content-Disposition', 'attachment', filename=basename)
            img.add_header('Content-Description', description)
            msg.attach(img)
            print(f"  ✅ {basename} — {description}")
    else:
        print(f"  ❌ Missing: {filename}")

print(f"\nSending to {msg['To']}...")
with smtplib.SMTP(creds['smtp_server'], creds['smtp_port']) as server:
    server.starttls()
    server.login(creds['email'], creds['app_password'])
    server.send_message(msg)

print("✅ Email sent!")
