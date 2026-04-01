# send_welcome.py
# Teesra — Beautiful welcome email sent immediately on subscription

import resend
import os
from dotenv import load_dotenv

load_dotenv()
resend.api_key = os.getenv("RESEND_API_KEY")

FROM_ADDRESS = "Teesra <brief@teesra.in>"


def send_welcome_email(subscriber_email: str) -> bool:

    html_content = """<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0; padding:0; background:#0a0a08; font-family:'Georgia',serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#0a0a08; padding:40px 16px;">
<tr><td align="center">
<table width="600" cellpadding="0" cellspacing="0">

  <!-- HEADER -->
  <tr>
    <td style="padding:0 0 32px 0; text-align:center; border-bottom:1px solid #2a2a1f;">
      <p style="margin:0 0 4px 0; font-family:Georgia,serif; font-size:40px; font-weight:900; color:#e8c84a; letter-spacing:-1.5px; line-height:1;">Teesra</p>
      <p style="margin:0; font-family:monospace; font-size:10px; color:#6a6650; letter-spacing:3px; text-transform:uppercase;">तीसरा नज़रिया</p>
    </td>
  </tr>

  <!-- HERO -->
  <tr>
    <td style="padding:40px 0 32px 0; text-align:center;">
      <p style="margin:0 0 14px 0; font-family:monospace; font-size:11px; color:#7bc67e; letter-spacing:2px; text-transform:uppercase;">✦ You're in</p>
      <h1 style="margin:0 0 20px 0; font-family:Georgia,serif; font-size:32px; font-weight:900; color:#e8e4d4; line-height:1.2; letter-spacing:-0.5px;">
        Welcome to India's<br><em style="color:#e8c84a; font-style:italic;">third perspective.</em>
      </h1>
      <p style="margin:0 auto; font-size:15px; color:#a8a288; line-height:1.8; max-width:460px;">
        Every morning at <strong style="color:#e8e4d4;">every morning</strong>, you'll get India's most important stories — verified facts, the left lens, the right lens, and what people on the street are actually saying. No spin. No agenda. Just everything you need to think for yourself.
      </p>
    </td>
  </tr>

  <tr><td style="border-top:1px solid #2a2a1f;"></td></tr>

  <!-- WHAT YOU GET -->
  <tr>
    <td style="padding:32px 0 28px 0;">
      <p style="margin:0 0 24px 0; font-family:monospace; font-size:10px; color:#6a6650; letter-spacing:2px; text-transform:uppercase;">What you'll get every morning</p>

      <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:14px;"><tr>
        <td width="36" style="vertical-align:top; padding-top:2px;">
          <div style="width:28px; height:28px; background:rgba(232,200,74,0.08); border-left:2px solid #e8c84a; text-align:center; line-height:28px; font-size:13px;">⚖️</div>
        </td>
        <td style="padding-left:14px; vertical-align:top;">
          <p style="margin:0 0 3px 0; font-family:monospace; font-size:10px; color:#e8c84a; letter-spacing:2px; text-transform:uppercase;">Facts</p>
          <p style="margin:0; font-size:13px; color:#a8a288; line-height:1.6;">What exactly happened — verified across 3+ sources. No spin.</p>
        </td>
      </tr></table>

      <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:14px;"><tr>
        <td width="36" style="vertical-align:top; padding-top:2px;">
          <div style="width:28px; height:28px; background:rgba(91,155,213,0.08); border-left:2px solid #5b9bd5; text-align:center; line-height:28px; font-size:13px;">🔵</div>
        </td>
        <td style="padding-left:14px; vertical-align:top;">
          <p style="margin:0 0 3px 0; font-family:monospace; font-size:10px; color:#5b9bd5; letter-spacing:2px; text-transform:uppercase;">Left Lens</p>
          <p style="margin:0; font-size:13px; color:#a8a288; line-height:1.6;">How progressive outlets frame the story — their angle, their concerns.</p>
        </td>
      </tr></table>

      <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:14px;"><tr>
        <td width="36" style="vertical-align:top; padding-top:2px;">
          <div style="width:28px; height:28px; background:rgba(212,91,91,0.08); border-left:2px solid #d45b5b; text-align:center; line-height:28px; font-size:13px;">🔴</div>
        </td>
        <td style="padding-left:14px; vertical-align:top;">
          <p style="margin:0 0 3px 0; font-family:monospace; font-size:10px; color:#d45b5b; letter-spacing:2px; text-transform:uppercase;">Right Lens</p>
          <p style="margin:0; font-size:13px; color:#a8a288; line-height:1.6;">How conservative outlets frame the same story — their priorities, their reading.</p>
        </td>
      </tr></table>

      <table width="100%" cellpadding="0" cellspacing="0"><tr>
        <td width="36" style="vertical-align:top; padding-top:2px;">
          <div style="width:28px; height:28px; background:rgba(123,198,126,0.08); border-left:2px solid #7bc67e; text-align:center; line-height:28px; font-size:13px;">💬</div>
        </td>
        <td style="padding-left:14px; vertical-align:top;">
          <p style="margin:0 0 3px 0; font-family:monospace; font-size:10px; color:#7bc67e; letter-spacing:2px; text-transform:uppercase;">Street Pulse</p>
          <p style="margin:0; font-size:13px; color:#a8a288; line-height:1.6;">What young Indians, professionals, and communities are actually saying.</p>
        </td>
      </tr></table>
    </td>
  </tr>

  <tr><td style="border-top:1px solid #2a2a1f;"></td></tr>

  <!-- CTA -->
  <tr>
    <td style="padding:32px 0; text-align:center;">
      <p style="margin:0 0 20px 0; font-size:14px; color:#a8a288; line-height:1.7;">
        Your first brief arrives <strong style="color:#e8e4d4;">tomorrow morning, fresh and ready.</strong><br>
        Until then, catch up on today's stories:
      </p>
      <a href="https://teesra.in/feed" target="_blank"
         style="display:inline-block; padding:14px 36px; background:#e8c84a; color:#0a0a08; font-family:monospace; font-size:12px; letter-spacing:2px; text-decoration:none; text-transform:uppercase; font-weight:700;">
        Read Today's Brief →
      </a>
    </td>
  </tr>

  <tr><td style="border-top:1px solid #2a2a1f;"></td></tr>

  <!-- PERSONAL NOTE -->
  <tr>
    <td style="padding:28px 0;">
      <p style="margin:0 0 12px 0; font-size:14px; color:#e8e4d4; line-height:1.8;">
        Hey — I'm Divyendu, the person who built this. Teesra is a one-person project built because I got tired of not knowing which version of the truth to believe.
      </p>
      <p style="margin:0 0 12px 0; font-size:14px; color:#a8a288; line-height:1.8;">
        If you ever have feedback — a story type you want more of, something that felt off, or just a thought — hit reply to this email or write to brief@teesra.in — I read every message.
      </p>
      <p style="margin:0; font-size:14px; color:#a8a288; line-height:1.8;">See you tomorrow morning. ☀️</p>
      <p style="margin:16px 0 0 0; font-family:Georgia,serif; font-size:16px; font-weight:700; color:#e8c84a;">— Divyendu</p>
    </td>
  </tr>

  <!-- FOOTER -->
  <tr>
    <td style="padding:20px 0 0 0; border-top:1px solid #1e1e14; text-align:center;">
      <p style="margin:0 0 4px 0; font-family:Georgia,serif; font-size:15px; font-weight:900; color:#e8c84a;">Teesra</p>
      <p style="margin:0 0 10px 0; font-family:monospace; font-size:9px; color:#3a3a28; letter-spacing:2px; text-transform:uppercase;">One story, three perspectives</p>
      <p style="margin:0; font-family:monospace; font-size:9px; color:#3a3a28; letter-spacing:1px;">
        You subscribed at teesra.in · No spam, ever.
      </p>
    </td>
  </tr>

</table>
</td></tr>
</table>
</body>
</html>"""

    params = {
        "from": FROM_ADDRESS,
        "to": [subscriber_email],
        "subject": "Welcome to Teesra — your morning brief starts tomorrow ☀️",
        "html": html_content
    }

    try:
        response = resend.Emails.send(params)
        print(f"✅ Welcome email sent to {subscriber_email} (ID: {response['id']})")
        return True
    except Exception as e:
        print(f"❌ Welcome email failed for {subscriber_email}: {e}")
        return False


# ── TEST ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    email = sys.argv[1] if len(sys.argv) > 1 else "dsp.fiem@gmail.com"
    print(f"\n🧪 Sending welcome email to {email}...\n")
    send_welcome_email(email)
