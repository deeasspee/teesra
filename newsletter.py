# newsletter.py
# Teesra — Daily email newsletter
# Pulls today's articles from Supabase and sends formatted email

import os
import resend
from dotenv import load_dotenv
from database import get_todays_articles
from datetime import date

load_dotenv()
resend.api_key = os.getenv("RESEND_API_KEY")


# ── STORY TYPE CONFIG ─────────────────────────────────────────────
TYPE_CONFIG = {
    "political": {"emoji": "🏛", "label": "Political",  "color": "#e8c84a"},
    "sports":    {"emoji": "🏏", "label": "Sports",     "color": "#7bc67e"},
    "sensitive": {"emoji": "⚠️", "label": "Sensitive",  "color": "#d45b5b"},
    "tech":      {"emoji": "⚡", "label": "Tech",        "color": "#5b9bd5"},
    "general":   {"emoji": "📰", "label": "General",    "color": "#b0aa90"},
}


# ── BUILD SINGLE STORY CARD ───────────────────────────────────────
def build_story_html(article, index):
    config = TYPE_CONFIG.get(article.get("story_type", "general"), TYPE_CONFIG["general"])
    color = config["color"]
    label = f"{config['emoji']} {config['label']}"
    is_sports = article.get("story_type") == "sports"

    # Left/right section — hide for sports
    if is_sports:
        lens_html = ""
    else:
        lens_html = f"""
        <tr>
          <td style="padding: 0 0 8px 0;">
            <table width="100%" cellpadding="0" cellspacing="0">
              <tr>
                <td width="48%" style="padding: 12px; background:#0f1218; border-left: 2px solid #5b9bd5; vertical-align:top;">
                  <p style="margin:0 0 4px 0; font-family:monospace; font-size:9px; color:#5b9bd5; letter-spacing:2px; text-transform:uppercase;">🔵 Left Lens</p>
                  <p style="margin:0; font-size:12px; color:#b0aa90; line-height:1.6;">{article.get('left_lens', '')}</p>
                </td>
                <td width="4%"></td>
                <td width="48%" style="padding: 12px; background:#180f0f; border-left: 2px solid #d45b5b; vertical-align:top;">
                  <p style="margin:0 0 4px 0; font-family:monospace; font-size:9px; color:#d45b5b; letter-spacing:2px; text-transform:uppercase;">🔴 Right Lens</p>
                  <p style="margin:0; font-size:12px; color:#b0aa90; line-height:1.6;">{article.get('right_lens', '')}</p>
                </td>
              </tr>
            </table>
          </td>
        </tr>"""

    caution_html = ""
    if article.get("caution_note"):
        caution_html = f"""
        <tr>
          <td style="padding: 8px 12px; background: rgba(212,91,91,0.08); border: 1px solid rgba(212,91,91,0.2);">
            <p style="margin:0; font-size:11px; color:#d45b5b;">⚠️ {article['caution_note']}</p>
          </td>
        </tr>"""

    return f"""
    <!-- STORY {index} -->
    <tr>
      <td style="padding: 0 0 24px 0;">
        <table width="100%" cellpadding="0" cellspacing="0" style="background:#18180f; border:1px solid #2a2a1f;">

          <!-- CARD HEADER -->
          <tr>
            <td style="padding: 20px 20px 0 20px; border-top: 3px solid {color};">
              <p style="margin:0 0 6px 0; font-family:monospace; font-size:9px; color:{color}; letter-spacing:2px; text-transform:uppercase;">{label}</p>
              <h2 style="margin:0 0 8px 0; font-family:Georgia,serif; font-size:17px; font-weight:700; color:#e8e4d4; line-height:1.3;">{article.get('headline', '')}</h2>
              <p style="margin:0 0 16px 0; font-family:monospace; font-size:10px; color:#7a7660;">
                {article.get('source', '')} · {article.get('source_bias', '')}
                {f'· <a href="{article["url"]}" style="color:#7a7660;">Read original →</a>' if article.get('url') else ''}
              </p>
            </td>
          </tr>

          <!-- FACTS -->
          <tr>
            <td style="padding: 0 20px 12px 20px;">
              <p style="margin:0 0 4px 0; font-family:monospace; font-size:9px; color:#e8c84a; letter-spacing:2px; text-transform:uppercase;">⚖️ Facts</p>
              <p style="margin:0; font-size:13px; color:#b0aa90; line-height:1.65;">{article.get('facts', '')}</p>
            </td>
          </tr>

          <!-- IMPACT -->
          <tr>
            <td style="padding: 8px 20px 12px 20px; background: rgba(232,200,74,0.03);">
              <p style="margin:0 0 4px 0; font-family:monospace; font-size:9px; color:#e8c84a; letter-spacing:2px; text-transform:uppercase;">💥 Impact</p>
              <p style="margin:0; font-size:13px; color:#e8e4d4; line-height:1.6;">{article.get('impact', '')}</p>
            </td>
          </tr>

          <!-- LEFT RIGHT LENS -->
          {lens_html}

          <!-- STREET PULSE -->
          <tr>
            <td style="padding: 8px 20px 16px 20px; border-top: 1px solid #2a2a1f;">
              <p style="margin:0 0 4px 0; font-family:monospace; font-size:9px; color:#7bc67e; letter-spacing:2px; text-transform:uppercase;">💬 Street Pulse</p>
              <p style="margin:0; font-size:12px; color:#b0aa90; line-height:1.6;">{article.get('public_pulse', '')}</p>
            </td>
          </tr>

          {caution_html}

        </table>
      </td>
    </tr>"""


# ── BUILD FULL EMAIL ──────────────────────────────────────────────
def build_email_html(articles):
    today = date.today().strftime("%A, %d %B %Y")
    article_count = len(articles)

    # Build all story cards
    stories_html = ""
    for i, article in enumerate(articles):
        stories_html += build_story_html(article, i + 1)

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"></head>
<body style="margin:0;padding:0;background:#0a0a08;font-family:'Georgia',serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#0a0a08;padding:32px 16px;">
<tr><td align="center">
<table width="600" cellpadding="0" cellspacing="0">

  <!-- HEADER -->
  <tr>
    <td style="padding:0 0 24px 0; border-bottom:1px solid #2a2a1f; margin-bottom:24px;">
      <p style="margin:0 0 2px 0;font-family:Georgia,serif;font-size:32px;font-weight:900;color:#e8c84a;letter-spacing:-1px;">Teesra</p>
      <p style="margin:0;font-family:monospace;font-size:10px;color:#7a7660;letter-spacing:3px;text-transform:uppercase;">तीसरा नज़रिया · Ek khabar, teen nazariye</p>
    </td>
  </tr>

  <!-- DATE BAR -->
  <tr>
    <td style="padding:20px 0;">
      <p style="margin:0 0 4px 0;font-family:monospace;font-size:10px;color:#7a7660;letter-spacing:2px;text-transform:uppercase;">Morning Brief</p>
      <p style="margin:0;font-family:Georgia,serif;font-size:22px;font-weight:700;color:#e8e4d4;">{today}</p>
      <p style="margin:8px 0 0 0;font-size:13px;color:#7a7660;">{article_count} stories · verified across multiple sources · facts first</p>
    </td>
  </tr>

  <!-- DIVIDER -->
  <tr><td style="padding:0 0 24px 0;border-bottom:1px solid #2a2a1f;"></td></tr>
  <tr><td style="height:24px;"></td></tr>

  <!-- STORIES -->
  {stories_html}

  <!-- FOOTER -->
  <tr>
    <td style="padding:24px 0 0 0;border-top:1px solid #2a2a1f;">
      <p style="margin:0 0 4px 0;font-family:Georgia,serif;font-size:16px;font-weight:700;color:#e8c84a;">Teesra</p>
      <p style="margin:0 0 12px 0;font-size:11px;color:#7a7660;font-style:italic;">We don't tell you what to think. We give you everything you need to think for yourself.</p>
      <p style="margin:0;font-family:monospace;font-size:10px;color:#7a7660;letter-spacing:1px;">
        Built by Divyendu · IIM Amritsar · 
        You're on the Teesra waitlist. No spam, ever.
      </p>
    </td>
  </tr>

</table>
</td></tr>
</table>
</body>
</html>"""


# ── SEND NEWSLETTER ───────────────────────────────────────────────
def send_newsletter(to_email: str):
    print(f"\n📧 Building today's Teesra newsletter...")

    articles = get_todays_articles()

    if not articles:
        print("❌ No articles found for today. Run analyze_article.py first.")
        return False

    print(f"   Found {len(articles)} articles")

    html = build_email_html(articles)
    today = date.today().strftime("%A, %d %B")

    params = {
        "from": "Teesra <onboarding@resend.dev>",
        "to": [to_email],
        "subject": f"☀️ Teesra Brief — {today} · {len(articles)} stories",
        "html": html
    }

    try:
        response = resend.Emails.send(params)
        print(f"✅ Newsletter sent to {to_email}")
        print(f"   Email ID: {response['id']}")
        return True
    except Exception as e:
        print(f"❌ Failed to send: {e}")
        return False


# ── RUN ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    email = input("Send newsletter to: ")
    send_newsletter(email)