#!/usr/bin/env python3
"""
Alert System - Multi-channel notifications for high-conviction signals
Telegram, Email, and alert log
"""
import json
import smtplib
import argparse
from email.mime.text import MIMEText
from datetime import datetime
from colorama import Fore, Style, init

init(autoreset=True)

SIGNALS_FILE = 'signals_latest.json'
ALERTS_FILE = 'alerts.json'

# Email config (from TOOLS.md)
SMTP_SERVER = 'smtp.gmail.com'
SMTP_PORT = 587
FROM_EMAIL = 'rara3bot@gmail.com'
TO_EMAIL = 'llctechboost@gmail.com'
APP_PASSWORD = 'vjuj dobj bpri rqfy'

def load_signals():
    """Load latest signals."""
    try:
        with open(SIGNALS_FILE, 'r') as f:
            return json.load(f)
    except:
        return {'hot': [], 'strong': [], 'watch': []}

def load_alerts():
    """Load alert history."""
    try:
        with open(ALERTS_FILE, 'r') as f:
            return json.load(f)
    except:
        return []

def save_alert(alert):
    """Save alert to history."""
    alerts = load_alerts()
    alerts.append(alert)
    
    # Keep last 100
    alerts = alerts[-100:]
    
    with open(ALERTS_FILE, 'w') as f:
        json.dump(alerts, f, indent=2)

def send_email(subject, body):
    """Send email alert."""
    try:
        msg = MIMEText(body)
        msg['Subject'] = subject
        msg['From'] = FROM_EMAIL
        msg['To'] = TO_EMAIL
        
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(FROM_EMAIL, APP_PASSWORD)
        server.send_message(msg)
        server.quit()
        
        return True
    except Exception as e:
        print(f"{Fore.RED}✗ Email failed: {e}{Style.RESET_ALL}")
        return False

def format_alert(signal):
    """Format signal as alert message."""
    emoji = "🔥" if signal['conviction'] >= 95 else "🟢" if signal['conviction'] >= 85 else "🟡"
    level = "HOT" if signal['conviction'] >= 95 else "STRONG" if signal['conviction'] >= 85 else "WATCH"
    
    msg = f"{emoji} {level} SIGNAL: {signal['ticker']}\n\n"
    msg += f"Conviction: {signal['conviction']}/100\n"
    msg += f"Pattern: {signal['pattern']} (Score: {signal['stock_score']}/100)\n"
    msg += f"Price: ${signal['price']:.2f}\n"
    
    if signal.get('buy_point'):
        msg += f"Buy Point: ${signal['buy_point']:.2f}\n"
    if signal.get('stop'):
        msg += f"Stop: ${signal['stop']:.2f}\n"
    
    if signal['has_flow']:
        msg += f"\nOptions Flow: {signal['flow_bias']}\n"
        msg += f"Premium: ${signal['premium_flow']:,.0f}\n"
    
    msg += f"\nReasons:\n"
    for reason in signal['reasons']:
        msg += f"• {reason}\n"
    
    msg += f"\nTime: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    
    return msg

def send_alerts(min_conviction=95, email=True, console=True):
    """Send alerts for signals above threshold."""
    signals_data = load_signals()
    
    # Filter by conviction
    hot = signals_data.get('hot', [])
    strong = signals_data.get('strong', [])
    
    to_alert = []
    
    if min_conviction >= 95:
        to_alert = hot
    elif min_conviction >= 85:
        to_alert = hot + strong
    else:
        to_alert = hot + strong + signals_data.get('watch', [])
    
    to_alert = [s for s in to_alert if s['conviction'] >= min_conviction]
    
    if not to_alert:
        if console:
            print(f"\n{Fore.YELLOW}No signals above {min_conviction}/100 conviction.{Style.RESET_ALL}\n")
        return
    
    if console:
        print(f"\n{Fore.CYAN}{'='*60}")
        print(f"{Fore.CYAN}{Style.BRIGHT}📢 SENDING ALERTS")
        print(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}\n")
    
    sent_count = 0
    
    for signal in to_alert:
        alert_msg = format_alert(signal)
        
        # Console output
        if console:
            print(alert_msg)
            print(f"{Fore.CYAN}{'─'*60}{Style.RESET_ALL}\n")
        
        # Email
        if email:
            subject = f"🔥 Trade Alert: {signal['ticker']} ({signal['conviction']}/100)"
            success = send_email(subject, alert_msg)
            if success:
                sent_count += 1
        
        # Save to history
        save_alert({
            'timestamp': datetime.now().isoformat(),
            'ticker': signal['ticker'],
            'conviction': signal['conviction'],
            'pattern': signal['pattern'],
            'price': signal['price'],
            'message': alert_msg
        })
    
    if console:
        print(f"{Fore.GREEN}✓ Sent {sent_count} alert{'s' if sent_count != 1 else ''}{Style.RESET_ALL}\n")

def list_alerts(limit=10):
    """Show recent alerts."""
    alerts = load_alerts()
    
    if not alerts:
        print(f"\n{Fore.YELLOW}No alerts in history.{Style.RESET_ALL}\n")
        return
    
    print(f"\n{Fore.CYAN}{'='*60}")
    print(f"{Fore.CYAN}{Style.BRIGHT}📋 RECENT ALERTS")
    print(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}\n")
    
    for alert in alerts[-limit:]:
        print(f"{Fore.WHITE}{alert['timestamp'][:16]}{Style.RESET_ALL} | "
              f"{Fore.CYAN}{alert['ticker']:<6}{Style.RESET_ALL} | "
              f"{alert['conviction']}/100 | {alert['pattern']}")
    
    print()

def main():
    parser = argparse.ArgumentParser(description='Alert System')
    parser.add_argument('--min-conviction', type=int, default=95, help='Minimum conviction to alert')
    parser.add_argument('--no-email', action='store_true', help='Skip email')
    parser.add_argument('--list', action='store_true', help='Show recent alerts')
    parser.add_argument('--limit', type=int, default=10, help='Limit for --list')
    
    args = parser.parse_args()
    
    if args.list:
        list_alerts(args.limit)
    else:
        send_alerts(
            min_conviction=args.min_conviction,
            email=not args.no_email,
            console=True
        )

if __name__ == '__main__':
    main()
