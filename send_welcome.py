# send_welcome.py
# Teesra — sends welcome email when someone subscribes

import resend
import os
from dotenv import load_dotenv

load_dotenv()

resend.api_key = os.getenv("RESEND_API_KEY")

def send_welcome_email(subscriber_email):

    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8">
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="margin:0; padding:0; background:#0a0a08; font-family: 'Georgia', serif;">

      <table width="100%" cellpadding="0" cellspacing="0" style="background:#0a0a08; padding: 40px 20px;">
        <tr>
          <td align="center">
            <table width="560" cellpadding="0" cellspacing="0" style="background:#11110e; border: 1px solid #2a2a1f;">

              <!-- HEADER -->
              <tr>
                <td style="padding: 36px 40px 28px; border-bottom: 1px solid #2a2a1f;">
                  <p style="margin:0 0 4px 0; font-family: 'Georgia', serif; font-size: 28px; font-weight: 900; color: #e8c84a; letter-spacing: -0.5px;">Teesra</p>
                  <p style="margin:0; font-size: 11px; color: #7a7660; letter-spacing: 3px; text-transform: uppercase; font-family: monospace;">तीसरा नज़रिया</p>
                </td>
              </tr>

              <!-- BODY -->
              <tr>
                <td style="padding: 36px 40px;">
                  <p style="margin: 0 0 20px 0; font-size: 22px; font-weight: 700; color: #e8e4d4; line-height: 1.3;">
                    You're on the list. ☀️
                  </p>
                  <p style="margin: 0 0 16px 0; font-size: 15px; color: #b0aa90; line-height: 1.7;">
                    Thank you for signing up for <strong style="color: #e8e4d4;">Teesra</strong> — India's morning brief that gives you every story from all three sides.
                  </p>
                  <p style="margin: 0 0 28px 0; font-size: 15px; color: #b0aa90; line-height: 1.7;">
                    When we go live, you'll get a clean, AI-powered brief in your inbox every morning by <strong style="color: #e8c84a;">7:30 AM</strong> — facts first, left lens, right lens, and what people on the street are saying.
                  </p>

                  <!-- THREE SIDES PREVIEW -->
                  <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom: 28px;">
                    <tr>
                      <td style="padding: 16px; background: #0a0a08; border-left: 3px solid #e8c84a; margin-bottom: 8px; display: block;">
                        <p style="margin:0 0 4px 0; font-size: 10px; color: #e8c84a; letter-spacing: 2px; text-transform: uppercase; font-family: monospace;">⚖️ Facts</p>
                        <p style="margin:0; font-size: 13px; color: #b0aa90; line-height: 1.5;">What exactly happened — verified across 3+ sources, no spin.</p>
                      </td>
                    </tr>
                    <tr><td style="height: 8px;"></td></tr>
                    <tr>
                      <td style="padding: 16px; background: #0a0a08; border-left: 3px solid #5b9bd5;">
                        <p style="margin:0 0 4px 0; font-size: 10px; color: #5b9bd5; letter-spacing: 2px; text-transform: uppercase; font-family: monospace;">🔵 Left Lens</p>
                        <p style="margin:0; font-size: 13px; color: #b0aa90; line-height: 1.5;">How progressive outlets are framing the story.</p>
                      </td>
                    </tr>
                    <tr><td style="height: 8px;"></td></tr>
                    <tr>
                      <td style="padding: 16px; background: #0a0a08; border-left: 3px solid #d45b5b;">
                        <p style="margin:0 0 4px 0; font-size: 10px; color: #d45b5b; letter-spacing: 2px; text-transform: uppercase; font-family: monospace;">🔴 Right Lens</p>
                        <p style="margin:0; font-size: 13px; color: #b0aa90; line-height: 1.5;">How conservative outlets are framing the same story.</p>
                      </td>
                    </tr>
                  </table>

                  <p style="margin: 0 0 28px 0; font-size: 14px; color: #7a7660; line-height: 1.6; font-style: italic;">
                    "We don't tell you what to think. We give you everything you need to think for yourself."
                  </p>

                  <!-- CTA -->
                  <table cellpadding="0" cellspacing="0">
                    <tr>
                      <td style="background: #e8c84a; padding: 12px 28px;">
                        <a href="https://teesra.news" style="color: #0a0a08; font-size: 13px; font-weight: 600; text-decoration: none; font-family: sans-serif; letter-spacing: 0.3px;">Visit teesra.news →</a>
                      </td>
                    </tr>
                  </table>
                </td>
              </tr>

              <!-- FOOTER -->
              <tr>
                <td style="padding: 24px 40px; border-top: 1px solid #2a2a1f;">
                  <p style="margin:0 0 4px 0; font-size: 11px; color: #7a7660; font-family: monospace; letter-spacing: 1px;">
                    Built by Divyendu · IIM Amritsar
                  </p>
                  <p style="margin:0; font-size: 11px; color: #7a7660;">
                    You're receiving this because you signed up at teesra.news. No spam, ever.
                  </p>
                </td>
              </tr>

            </table>
          </td>
        </tr>
      </table>

    </body>
    </html>
    """

    params = {
        "from": "Teesra <onboarding@resend.dev>",
        "to": [subscriber_email],
        "subject": "☀️ You're on the Teesra waitlist",
        "html": html_content
    }

    try:
        response = resend.Emails.send(params)
        print(f"✅ Welcome email sent to {subscriber_email}")
        print(f"   Email ID: {response['id']}")
        return True
    except Exception as e:
        print(f"❌ Failed to send email: {e}")
        return False


# Test it — send to yourself
if __name__ == "__main__":
    test_email = input("Enter your email to test: ")
    send_welcome_email(test_email)