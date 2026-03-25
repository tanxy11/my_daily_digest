"""Send the digest via email."""

from __future__ import annotations

import json
import logging
import os
import re
import socket
import smtplib
import urllib.error
import urllib.request
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

logger = logging.getLogger(__name__)


class IPv4FirstSMTP(smtplib.SMTP):
    """SMTP client that prefers IPv4 and surfaces connection attempts clearly."""

    def _get_socket(self, host: str, port: int, timeout: float):
        return _create_smtp_socket(host, port, timeout)


def _create_smtp_socket(host: str, port: int, timeout: float) -> socket.socket:
    infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    infos.sort(key=lambda item: 0 if item[0] == socket.AF_INET else 1)

    attempts: list[str] = []
    for family, socktype, proto, _, sockaddr in infos:
        sock = socket.socket(family, socktype, proto)
        sock.settimeout(timeout)
        try:
            sock.connect(sockaddr)
            logger.info("Connected to SMTP endpoint %s", sockaddr)
            return sock
        except OSError as exc:
            attempts.append(f"{sockaddr}: {exc}")
            sock.close()

    details = "; ".join(attempts) if attempts else "no addresses resolved"
    raise OSError(
        "Unable to reach SMTP server "
        f"{host}:{port}. Attempts: {details}. "
        "If this host runs on a cloud VPS, outbound SMTP may be blocked by the provider."
    )


def send_email(subject: str, html_body: str, config: dict[str, Any]) -> None:
    """Send an HTML email using Resend when configured, otherwise SMTP."""
    resend_api_key = os.environ.get("RESEND_API_KEY")
    if resend_api_key:
        _send_via_resend(subject, html_body, config, resend_api_key)
        return

    _send_via_smtp(subject, html_body, config)


def _send_via_resend(
    subject: str,
    html_body: str,
    config: dict[str, Any],
    api_key: str,
) -> None:
    delivery = config["delivery"]
    to_address = delivery["to_address"]
    configured_from = delivery["from_address"]
    from_address = (
        os.environ.get("RESEND_FROM_ADDRESS")
        or _resend_from_address(configured_from)
    )

    payload = {
        "from": from_address,
        "to": [to_address],
        "subject": subject,
        "html": html_body,
        "text": _plain_text_fallback(subject, html_body),
        "reply_to": configured_from,
    }
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        "https://api.resend.com/emails",
        data=data,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "my_daily_digest/1.0",
        },
        method="POST",
    )

    logger.info("Sending digest to %s via Resend API", to_address)

    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            "Resend API rejected the email. "
            f"Sender used: {from_address}. Response: {details}"
        ) from exc
    except urllib.error.URLError as exc:
        raise RuntimeError("Unable to reach the Resend API over HTTPS") from exc

    logger.info("Digest sent successfully via Resend: %s", body)


def _resend_from_address(configured_from: str) -> str:
    if "@" in configured_from and not configured_from.endswith("@gmail.com"):
        return configured_from
    return "Daily Digest <onboarding@resend.dev>"


def _plain_text_fallback(subject: str, html_body: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html_body)
    text = re.sub(r"\s+", " ", text).strip()
    return f"{subject}\n\n{text}"


def _send_via_smtp(subject: str, html_body: str, config: dict[str, Any]) -> None:
    """Send an HTML email using SMTP config from the config dict."""
    delivery = config["delivery"]
    smtp_cfg = delivery["smtp"]
    timeout = float(smtp_cfg.get("timeout_seconds", 15))

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

    with IPv4FirstSMTP(smtp_cfg["host"], smtp_cfg["port"], timeout=timeout) as server:
        server.starttls()
        server.login(smtp_cfg["username"], smtp_cfg["password"])
        server.sendmail(
            delivery["from_address"],
            delivery["to_address"],
            msg.as_string(),
        )

    logger.info("Digest sent successfully")
