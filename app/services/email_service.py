import smtplib
import os
import threading
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from itsdangerous import URLSafeTimedSerializer

# Allow cleaner import from app context
def init_email_service(app):
    global serializer, BASE_URL, SMTP_EMAIL, SMTP_PASSWORD, SMTP_SERVER, SMTP_PORT
    serializer = URLSafeTimedSerializer(app.secret_key)
    BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:5000")
    SMTP_EMAIL = os.getenv("SMTP_EMAIL")
    SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
    SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    SMTP_PORT = int(os.getenv("SMTP_PORT", 587))

def send_approval_email(year, code, attachments=None):
    if not (SMTP_EMAIL and SMTP_PASSWORD):
        print("[EMAIL WARNING] SMTP credentials not set. Email skipped.")
        return

    subject = f"GATE Calculator: New Submission {code} ({year})"
    body = f"""
    <h2>New Submission for Review</h2>
    <p>A new paper has been uploaded to the staging area.</p>
    <ul>
        <li><strong>Paper Code:</strong> {code}</li>
        <li><strong>Year:</strong> {year}</li>
    </ul>
    <p>
        Please log in to the admin dashboard to review and approve this submission.
    </p>
    <p>
        <a href="{BASE_URL}/dashboard" style="background:#3b82f6; color:white; padding:10px 20px; text-decoration:none; border-radius:5px;">
            Go to Admin Dashboard
        </a>
    </p>
    """
    
    print(f"\n[EMAIL DEBUG] To Admin ({SMTP_EMAIL}):\nSubject: {subject}\n")
    
    try:
        msg = MIMEMultipart()
        msg['From'] = f"GATE Calculator <{SMTP_EMAIL}>"
        msg['To'] = SMTP_EMAIL
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'html'))
        
        # Attach files if provided
        # attachments: list of {'name': str, 'data': bytes}
        if attachments:
            for item in attachments:
                try:
                    name = item.get('name')
                    data = item.get('data')
                    if name and data:
                        part = MIMEApplication(data, Name=name)
                        part['Content-Disposition'] = f'attachment; filename="{name}"'
                        msg.attach(part)
                except Exception as ex:
                    print(f"[EMAIL ERROR] Failed to attach {item.get('name')}: {ex}")
        
        # Force IPv4 Resolution to avoid "Network is unreachable" on cloud envs
        target_host = SMTP_SERVER
        import socket
        try:
            # Get first IPv4 address
            addr_info = socket.getaddrinfo(SMTP_SERVER, SMTP_PORT, socket.AF_INET)
            target_host = addr_info[0][4][0]
            print(f"[EMAIL DEBUG] Resolved {SMTP_SERVER} to {target_host} (IPv4)")
        except Exception as e:
            print(f"[EMAIL WARNING] IPv4 resolution failed: {e}. Using hostname.")

        print(f"[EMAIL DEBUG] Connecting to SMTP Server: {target_host}:{SMTP_PORT}...", flush=True)
        with smtplib.SMTP(target_host, SMTP_PORT) as server:
            # Fix for SSL: server._host must match the certificate domain, not the IP
            if target_host != SMTP_SERVER:
                server._host = SMTP_SERVER
            
            server.starttls()
            print("[EMAIL DEBUG] Logging in...", flush=True)
            server.login(SMTP_EMAIL, SMTP_PASSWORD)
            print("[EMAIL DEBUG] Sending message...", flush=True)
            server.send_message(msg)
        print("[EMAIL] Sent successfully.", flush=True)
    except Exception as e:
        print(f"[EMAIL ERROR] Failed to send: {e}", flush=True)

def send_approval_email_async(year, code, attachments=None):
    # Wrapper for threading
    thread = threading.Thread(target=send_approval_email, args=(year, code, attachments))
    thread.start()
