#!/usr/bin/env python3
"""Send the CANSLIM Visual Guide via email with chart attachments."""

import smtplib
import json
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from email.mime.application import MIMEApplication

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Load credentials
with open(os.path.join(os.path.dirname(SCRIPT_DIR), '.gmail-creds.json')) as f:
    creds = json.load(f)

# Read the guide
with open(os.path.join(SCRIPT_DIR, 'CANSLIM_VISUAL_GUIDE.md'), 'r') as f:
    guide_text = f.read()

# Build email
msg = MIMEMultipart('mixed')
msg['From'] = creds['email']
msg['To'] = 'llctechboost@gmail.com'
msg['Subject'] = '📊 CANSLIM Visual Pattern Guide — Complete Reference with Real Chart Examples'

# Email body (summary + note about attachments)
body = """Hey Rah,

Here's your complete CANSLIM Visual Pattern Guide with AI vision analysis of real charts.

📎 Attached:
• CANSLIM_VISUAL_GUIDE.md — The full guide (33K words, every pattern with rules + real examples)
• GOOGL chart — Flat Base + Cup with Handle example (Grade: B+)
• AMD chart — Ascending Base + Cup with Handle example (Grade: B-)
• NU chart — Ascending Base + Cup with Handle + VCP example (Grade: B+)

Quick Summary of Current Setups:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• GOOGL (9/12, RS 85) — Beautiful flat base but ⚠️ earnings Feb 4. WAIT.
• AMD (8/12, RS 91) — Strong ascending base but ⚠️ earnings Feb 3. WAIT.
• NU (7/12, RS 70) — Cleanest setup. No earnings risk. 👀 WATCH for $19.02 breakout.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

The guide covers all 7 patterns with:
✓ What each pattern looks like (visual description)
✓ Exact rules (range, duration, volume requirements)
✓ Buy signals and stop loss placement
✓ Common mistakes to avoid
✓ Real chart examples with AI vision breakdown
✓ The full 7-layer system stack explained
✓ Position sizing and risk management tables
✓ Decision flowchart for trade entry

Market context: S&P at 6,939 with 8 distribution days = CAUTION mode.
Only take highest-conviction setups with tight risk management right now.

— Rara 🫠
"""

msg.attach(MIMEText(body, 'plain'))

# Attach the guide as a file
with open(os.path.join(SCRIPT_DIR, 'CANSLIM_VISUAL_GUIDE.md'), 'rb') as f:
    attachment = MIMEApplication(f.read(), _subtype='markdown')
    attachment.add_header('Content-Disposition', 'attachment', filename='CANSLIM_VISUAL_GUIDE.md')
    msg.attach(attachment)

# Attach chart images
charts = [
    ('GOOGL_20260131_2227.png', 'GOOGL — Flat Base + Cup with Handle'),
    ('AMD_20260131_2228.png', 'AMD — Ascending Base + Cup with Handle'),
    ('NU_20260131_2228.png', 'NU — Ascending Base + Cup w Handle + VCP'),
]

for filename, description in charts:
    filepath = os.path.join(SCRIPT_DIR, 'charts', filename)
    if os.path.exists(filepath):
        with open(filepath, 'rb') as f:
            img = MIMEImage(f.read(), _subtype='png')
            img.add_header('Content-Disposition', 'attachment', filename=filename)
            img.add_header('Content-Description', description)
            msg.attach(img)
            print(f"  ✅ Attached: {filename}")
    else:
        print(f"  ❌ Missing: {filename}")

# Send
print(f"\nSending to {msg['To']}...")
with smtplib.SMTP(creds['smtp_server'], creds['smtp_port']) as server:
    server.starttls()
    server.login(creds['email'], creds['app_password'])
    server.send_message(msg)

print("✅ Email sent successfully!")
