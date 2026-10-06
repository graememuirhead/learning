"""Welcome email via SendGrid."""
from __future__ import annotations

import logging
from typing import Optional

from config.settings import Settings

logger = logging.getLogger(__name__)


def send_welcome_email(
    name: str,
    email: str,
    member_number: str,
    expiry_date: str,
    apple_pass_url: Optional[str],
    google_save_url: Optional[str],
) -> bool:
    """Send a welcome email with wallet pass links. Returns True on success."""
    if not Settings.SENDGRID_API_KEY:
        logger.warning("SENDGRID_API_KEY not set — skipping welcome email to %s", email)
        return False
    try:
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import Mail

        message = Mail(
            from_email=Settings.FROM_EMAIL,
            to_emails=email,
            subject="Welcome to Rye Tri Club – Your Membership Card",
            html_content=_build_html(name, member_number, expiry_date, apple_pass_url, google_save_url),
        )
        response = SendGridAPIClient(Settings.SENDGRID_API_KEY).send(message)
        logger.info("Welcome email sent to %s status=%d", email, response.status_code)
        return response.status_code in (200, 202)
    except Exception:
        logger.exception("Failed to send welcome email to %s", email)
        return False


def _build_html(
    name: str,
    member_number: str,
    expiry_date: str,
    apple_pass_url: Optional[str],
    google_save_url: Optional[str],
) -> str:
    first_name = name.split()[0] if name else name

    apple_btn = ""
    if apple_pass_url:
        apple_btn = f"""
            <tr><td align="center" style="padding:8px 0;">
              <a href="{apple_pass_url}"
                 style="display:inline-block;background:#000000;color:#ffffff;
                        font-family:-apple-system,BlinkMacSystemFont,sans-serif;
                        font-size:16px;font-weight:600;padding:14px 32px;
                        border-radius:8px;text-decoration:none;letter-spacing:0.3px;">
                Add to Apple Wallet
              </a>
            </td></tr>"""

    google_btn = ""
    if google_save_url:
        google_btn = f"""
            <tr><td align="center" style="padding:8px 0;">
              <a href="{google_save_url}"
                 style="display:inline-block;background:#1a73e8;color:#ffffff;
                        font-family:sans-serif;font-size:16px;font-weight:600;
                        padding:14px 32px;border-radius:8px;text-decoration:none;">
                Add to Google Wallet
              </a>
            </td></tr>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<body style="margin:0;padding:0;background:#f0f2f5;font-family:Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f0f2f5;padding:40px 0;">
  <tr><td align="center">
    <table width="580" cellpadding="0" cellspacing="0"
           style="background:#ffffff;border-radius:10px;overflow:hidden;
                  max-width:580px;box-shadow:0 2px 8px rgba(0,0,0,0.08);">

      <!-- Header -->
      <tr>
        <td style="background:#0a2463;padding:36px 32px;text-align:center;">
          <h1 style="color:#ffffff;margin:0;font-size:26px;font-weight:700;
                     letter-spacing:1px;">RYE TRI CLUB</h1>
          <p style="color:#8fa8d8;margin:6px 0 0;font-size:14px;
                    letter-spacing:2px;text-transform:uppercase;">Membership Card</p>
        </td>
      </tr>

      <!-- Body -->
      <tr>
        <td style="padding:36px 32px;">
          <p style="font-size:18px;color:#111;margin:0 0 12px;font-weight:600;">
            Hi {first_name},
          </p>
          <p style="color:#555;line-height:1.7;margin:0 0 28px;font-size:15px;">
            Welcome to Rye Tri Club! Your membership is now active.
            Add your digital membership card to your phone wallet — it gives you
            quick access at events and automatically reminds you when it's time to renew.
          </p>

          <!-- Member details card -->
          <table width="100%" cellpadding="0" cellspacing="0"
                 style="background:#f7f9fc;border-radius:8px;border:1px solid #e4e9f0;
                        margin-bottom:32px;">
            <tr>
              <td style="padding:20px 24px;">
                <table width="100%" cellpadding="0" cellspacing="0">
                  <tr>
                    <td style="padding:6px 0;width:50%;">
                      <span style="color:#888;font-size:11px;text-transform:uppercase;
                                   letter-spacing:1px;">Member</span><br>
                      <strong style="color:#0a2463;font-size:15px;">{name}</strong>
                    </td>
                    <td style="padding:6px 0;width:50%;">
                      <span style="color:#888;font-size:11px;text-transform:uppercase;
                                   letter-spacing:1px;">Member #</span><br>
                      <strong style="color:#0a2463;font-size:15px;">{member_number}</strong>
                    </td>
                  </tr>
                  <tr>
                    <td style="padding:6px 0;" colspan="2">
                      <span style="color:#888;font-size:11px;text-transform:uppercase;
                                   letter-spacing:1px;">Valid Through</span><br>
                      <strong style="color:#0a2463;font-size:15px;">{expiry_date}</strong>
                    </td>
                  </tr>
                </table>
              </td>
            </tr>
          </table>

          <!-- Wallet buttons -->
          <p style="color:#555;font-size:14px;text-align:center;margin:0 0 16px;">
            Tap a button on your phone to add your card:
          </p>
          <table width="100%" cellpadding="0" cellspacing="0">
            {apple_btn}
            {google_btn}
          </table>
        </td>
      </tr>

      <!-- Footer -->
      <tr>
        <td style="background:#f7f9fc;padding:24px 32px;text-align:center;
                   border-top:1px solid #e4e9f0;">
          <p style="color:#999;font-size:12px;margin:0 0 4px;">
            Questions? Email us at
            <a href="mailto:membership@ryetriclub.com"
               style="color:#0a2463;text-decoration:none;">membership@ryetriclub.com</a>
            or visit <a href="https://www.ryetri.org" style="color:#0a2463;">www.ryetri.org</a>
          </p>
          <p style="color:#bbb;font-size:11px;margin:6px 0 0;">
            This membership card is personal and non-transferable.
          </p>
        </td>
      </tr>

    </table>
  </td></tr>
</table>
</body>
</html>"""
