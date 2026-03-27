"""Notification module — Gmail and Slack webhook support.

Sends generated content (X posts + Note article) to the user's phone
so they can copy-paste and post directly.

Configuration via environment variables:
    Gmail:  NOTIFY_GMAIL_USER, NOTIFY_GMAIL_APP_PASSWORD, NOTIFY_GMAIL_TO
    Slack:  NOTIFY_SLACK_WEBHOOK_URL
"""

from __future__ import annotations

import json
import logging
import os
import smtplib
import urllib.request
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Gmail
# ---------------------------------------------------------------------------
def send_gmail(
    *,
    subject: str,
    body: str,
    gmail_user: str | None = None,
    gmail_app_password: str | None = None,
    to_address: str | None = None,
) -> bool:
    """Send an email via Gmail SMTP. Returns True on success."""
    user = gmail_user or os.environ.get("NOTIFY_GMAIL_USER", "")
    password = gmail_app_password or os.environ.get("NOTIFY_GMAIL_APP_PASSWORD", "")
    to = to_address or os.environ.get("NOTIFY_GMAIL_TO", user)

    if not (user and password and to):
        logger.warning("Gmail 設定が不足: NOTIFY_GMAIL_USER / NOTIFY_GMAIL_APP_PASSWORD")
        return False

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = user
    msg["To"] = to

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(user, password)
            server.send_message(msg)
        logger.info("Gmail 送信完了 → %s", to)
        return True
    except Exception:
        logger.exception("Gmail 送信失敗")
        return False


# ---------------------------------------------------------------------------
# Slack
# ---------------------------------------------------------------------------
def send_slack(
    *,
    text: str,
    webhook_url: str | None = None,
) -> bool:
    """Send a message to Slack via Incoming Webhook. Returns True on success."""
    url = webhook_url or os.environ.get("NOTIFY_SLACK_WEBHOOK_URL", "")

    if not url:
        logger.warning("Slack 設定が不足: NOTIFY_SLACK_WEBHOOK_URL")
        return False

    payload = json.dumps({"text": text}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:  # noqa: S310
            if resp.status == 200:
                logger.info("Slack 送信完了")
                return True
            logger.warning("Slack 応答: %s", resp.status)
            return False
    except Exception:
        logger.exception("Slack 送信失敗")
        return False


# ---------------------------------------------------------------------------
# Format content for notification
# ---------------------------------------------------------------------------
def format_notification(unified: dict) -> tuple[str, str]:
    """Format unified output into (subject, body) for notification.

    Returns a subject line and a body that's ready to copy-paste on mobile.
    """
    theme = unified.get("theme", "不明")
    mode = unified.get("mode", "auto")
    x_posts = unified.get("x_posts", "")
    note_article = unified.get("note_article", "")

    subject = f"📝 {theme}｜コンテンツ生成完了"

    sections = [
        f"テーマ: {theme}",
        f"モード: {mode}",
        "",
        "━━━━━━━━━━━━━━━━━━━━",
        "🐦 X投稿（コピペ用）",
        "━━━━━━━━━━━━━━━━━━━━",
        "",
        x_posts,
        "",
        "━━━━━━━━━━━━━━━━━━━━",
        "📝 Note記事（コピペ用）",
        "━━━━━━━━━━━━━━━━━━━━",
        "",
        note_article,
    ]

    body = "\n".join(sections)
    return subject, body


# ---------------------------------------------------------------------------
# Unified send
# ---------------------------------------------------------------------------
def notify(unified: dict) -> bool:
    """Send notification via all configured channels.

    Returns True if at least one channel succeeded.
    """
    subject, body = format_notification(unified)

    sent = False

    # Try Gmail
    if os.environ.get("NOTIFY_GMAIL_USER"):
        if send_gmail(subject=subject, body=body):
            sent = True

    # Try Slack
    if os.environ.get("NOTIFY_SLACK_WEBHOOK_URL"):
        if send_slack(text=body):
            sent = True

    if not sent:
        logger.warning("通知チャネルが未設定です（NOTIFY_GMAIL_* または NOTIFY_SLACK_WEBHOOK_URL）")

    return sent
