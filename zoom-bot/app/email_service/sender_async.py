# email_service/sender_async.py
import os
import aioboto3
from email import encoders
from dotenv import load_dotenv
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from app.logging_config import setup_logger
from email.mime.multipart import MIMEMultipart
from jinja2 import Environment, FileSystemLoader
from app.services.summarizer import detect_language

logger = setup_logger(__name__)

load_dotenv()

ROOT_EMAIL = os.getenv("SES_SOURCE_EMAIL")
template_env = Environment(loader=FileSystemLoader("email_service/templates"))


async def send_email_with_attachment(
        recipient_email: str,
        subject: str,
        body: str,
        body_html: str,
        attachment_text: str,
        attachment_filename: str = "summary.txt"
):
    logger.info(f"📧 Preparing to send email with attachment to {recipient_email}")

    try:
        msg = MIMEMultipart("mixed")
        msg["Subject"] = subject
        msg["From"] = ROOT_EMAIL
        msg["To"] = recipient_email

        # Body (plain + HTML)
        msg_body = MIMEMultipart("alternative")
        msg_body.attach(MIMEText(body, "plain"))
        msg_body.attach(MIMEText(body_html, "html"))
        msg.attach(msg_body)

        # Attachment
        part = MIMEBase("application", "octet-stream")
        part.set_payload(attachment_text.encode("utf-8"))
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", f'attachment; filename="{attachment_filename}"')
        msg.attach(part)

        # Send via SES
        session = aioboto3.Session()
        async with session.client("ses", region_name="eu-central-1") as ses:
            response = await ses.send_raw_email(
                Source=ROOT_EMAIL,
                Destinations=[recipient_email],
                RawMessage={"Data": msg.as_string()}
            )
            logger.info(f"📎 Email with attachment sent to {recipient_email}")
            return response

    except Exception:
        logger.exception("❌ Failed to send email with attachment")
        raise


def get_email_heading(meeting_id: str, summary: str) -> str:
    try:
        lang = detect_language(summary)
        if lang == "bg":
            return f"📋 Zoom meeting summary: {meeting_id}"
        else:
            return f"📋 Summary of your Zoom meeting: {meeting_id}"
    except Exception:
        logger.exception("❌ Error detecting summary language")
        return f"📋 Meeting Summary: {meeting_id}"


def render_summary_email(meeting_id: str, summary: str) -> str:
    try:
        heading = get_email_heading(meeting_id, summary)
        template = template_env.get_template("summary_email_template.html")
        return template.render(
            meeting_id=meeting_id,
            summary=summary.replace("\n", "<br>"),
            heading=heading
        )
    except Exception:
        logger.exception("❌ Failed to render HTML email template")
        return f"<p>{summary.replace(chr(10), '<br>')}</p>"


async def send_email_async(recipient_email: str, subject: str, body: str, body_html: str = None):
    logger.info(f"📨 Sending simple email to {recipient_email}")
    try:
        session = aioboto3.Session()
        async with session.client("ses", region_name="eu-central-1") as ses:
            response = await ses.send_email(
                Source=ROOT_EMAIL,
                Destination={"ToAddresses": [recipient_email]},
                Message={
                    "Subject": {"Data": subject},
                    "Body": {
                        "Text": {"Data": body},
                        "Html": {"Data": body_html or body}
                    }
                }
            )
            logger.info(f"📨 Email sent to {recipient_email}")
            return response
    except Exception:
        logger.exception("❌ Failed to send email")
        raise
