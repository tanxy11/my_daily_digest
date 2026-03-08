"""Send the digest via email."""

from __future__ import annotations

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

logger = logging.getLogger(__name__)


def send_email(subject: str, html_body: str, config: dict[str, Any]) -> None:
    """Send an HTML email using SMTP config from the config dict."""
    delivery = config["delivery"]
    smtp_cfg = delivery["smtp"]

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = delivery["from_address"]
    msg["To"] = delivery["to_address"]

    # Plain text fallback
    plain = f"{subject}\n\nView this email in an HTML-capable client."
    msg.attach(MIMEText(plain, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    logger.info("Sending digest to %s via %s:%s",
                delivery["to_address"], smtp_cfg["host"], smtp_cfg["port"])

    with smtplib.SMTP(smtp_cfg["host"], smtp_cfg["port"]) as server:
        server.starttls()
        server.login(smtp_cfg["username"], smtp_cfg["password"])
        server.sendmail(
            delivery["from_address"],
            delivery["to_address"],
            msg.as_string(),
        )

    logger.info("Digest sent successfully")
