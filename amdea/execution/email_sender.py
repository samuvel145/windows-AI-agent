import smtplib
import ssl
import pathlib
import re
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders
from amdea.security.keystore import get_smtp_config
from amdea.controller.safety import check_path_allowed

class SMTPConfigError(Exception): pass
class EmailSendError(Exception): pass

EMAIL_REGEX = re.compile(r'^[^@]+@[^@]+\.[^@]+$')

def validate_email_address(address: str) -> bool:
    """Returns True/False based on RFC 5322 regex."""
    return bool(EMAIL_REGEX.match(address))

def send_email(
    to: list[str], subject: str, body: str,
    attachments: list[str] = [], cc: list[str] = []
) -> None:
    """Sends an email via SMTP with optional attachments."""
    try:
        config = get_smtp_config()
    except Exception as e:
        raise SMTPConfigError(f"Failed to retrieve SMTP config: {e}")
    
    # Validate addresses
    for addr in to + cc:
        if not validate_email_address(addr):
            raise ValueError(f"Invalid email address: {addr}")

    msg = MIMEMultipart("mixed")
    msg["From"] = config["sender"]
    msg["To"] = ", ".join(to)
    msg["Cc"] = ", ".join(cc)
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain", "utf-8"))

    for att_path in attachments:
        check, reason = check_path_allowed(att_path)
        if not check:
            raise PermissionError(f"Attachment blocked: {reason}")
            
        path = pathlib.Path(att_path).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(f"Attachment not found: {att_path}")
            
        with open(path, "rb") as f:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(f.read())
            encoders.encode_base64(part)
            part.add_header("Content-Disposition", f'attachment; filename="{path.name}"')
            msg.attach(part)

    try:
        ctx = ssl.create_default_context()
        with smtplib.SMTP_SSL(config["host"], int(config["port"]), context=ctx) as server:
            server.login(config["user"], config["password"])
            server.sendmail(config["sender"], to + cc, msg.as_string())
    except smtplib.SMTPException as e:
        raise EmailSendError(f"SMTP error while sending email: {str(e)}")

def draft_email_to_file(to, subject, body, attachments, draft_dir: str) -> str:
    """For demo/safe mode: writes email details as a text file to draft_dir."""
    dest = pathlib.Path(draft_dir).expanduser().resolve()
    dest.mkdir(parents=True, exist_ok=True)
    
    safe_subject = re.sub(r'[^\w\-_\. ]', '_', subject)[:50]
    file_path = dest / f"draft_{safe_subject}.txt"
    
    content = [
        f"To: {', '.join(to)}",
        f"Cc: {', '.join(cc) if 'cc' in locals() else ''}",
        f"Subject: {subject}",
        f"Attachments: {', '.join(attachments)}",
        "\n" + "="*30 + "\n",
        body
    ]
    file_path.write_text("\n".join(content), encoding="utf-8")
    return str(file_path)
