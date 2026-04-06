# newsletter.py
# Teesra — Daily email newsletter
# Pulls today's articles from Supabase and sends formatted email

import os
import resend
from dotenv import load_dotenv
from database import get_todays_articles, get_all_subscribers
from datetime import date
from market_data import fetch_market_data, format_market_for_email

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
def build_email_html(articles, market_data=None):
    today = date.today().strftime("%A, %d %B %Y")
    article_count = len(articles)
    # Market section — safe even if None
    market_section = ""
    if market_data:
        try:
            market_section = format_market_for_email(market_data)
        except Exception as e:
            print(f"  ⚠️ Market email section failed: {e}")
            market_section = ""
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
      <p style="margin:0;font-family:monospace;font-size:10px;color:#7a7660;letter-spacing:3px;text-transform:uppercase;">News that matters to you</p>
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

  <!-- MARKET DATA -->
  {market_section}

  <!-- STORIES -->
  {stories_html}

  <!-- SHARE + FOOTER -->
  <tr>
    <td style="padding:28px 0 0 0; border-top:1px solid #2a2a1f; text-align:center;">
      <p style="margin:0 0 6px 0; font-family:Georgia,serif; font-size:17px; font-weight:700; color:#e8e4d4;">Found this useful?</p>
      <p style="margin:0 0 18px 0; font-family:monospace; font-size:10px; color:#6a6650; letter-spacing:1.5px; text-transform:uppercase;">Share Teesra with someone who reads the news</p>
      <table cellpadding="0" cellspacing="0" style="margin:0 auto 24px auto;">
        <tr>
          <td style="padding:0 5px;">
            <a href="https://wa.me/?text=Read%20today%27s%20Teesra%20brief%20%E2%80%94%20India%27s%20news%20from%20three%20perspectives.%20https%3A%2F%2Fteesra.in%2Ffeed"
               target="_blank"
               style="display:inline-block; padding:9px 16px; background:#25D366; font-family:monospace; font-size:10px; letter-spacing:1.5px; color:#0a0a08; text-decoration:none; text-transform:uppercase; font-weight:700;">
              📲 WhatsApp
            </a>
          </td>
          <td style="padding:0 5px;">
            <a href="https://twitter.com/intent/tweet?text=Reading%20today%27s%20Teesra%20brief%20%E2%80%94%20same%20story%2C%20three%20perspectives.%20No%20spin.%20https%3A%2F%2Fteesra.in%2Ffeed"
               target="_blank"
               style="display:inline-block; padding:9px 16px; background:#1a1a1a; border:1px solid #3a3a3a; font-family:monospace; font-size:10px; letter-spacing:1.5px; color:#e8e4d4; text-decoration:none; text-transform:uppercase; font-weight:700;">
              𝕏 Twitter
            </a>
          </td>
          <td style="padding:0 5px;">
            <a href="https://teesra.in/feed"
               target="_blank"
               style="display:inline-block; padding:9px 16px; background:rgba(232,200,74,0.08); border:1px solid rgba(232,200,74,0.25); font-family:monospace; font-size:10px; letter-spacing:1.5px; color:#e8c84a; text-decoration:none; text-transform:uppercase; font-weight:700;">
              🔗 Read Online
            </a>
          </td>
        </tr>
      </table>
      <p style="margin:0 0 4px 0; font-family:Georgia,serif; font-size:15px; font-weight:900; color:#e8c84a;">Teesra</p>
      <p style="margin:0 0 10px 0; font-family:monospace; font-size:9px; color:#3a3a28; letter-spacing:2px; text-transform:uppercase;">तीसरा नज़रिया · One story, three perspectives</p>
      <p style="margin:0 0 6px 0; font-size:11px; color:#7a7660; font-style:italic;">We don't tell you what to think. We give you everything you need to think for yourself.</p>
      <p style="margin:0; font-family:monospace; font-size:9px; color:#3a3a28; letter-spacing:1px;">
        Built by Divyendu · IIM Amritsar · No ads, ever.
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

    try:
        market_data = fetch_market_data()
    except Exception as e:
        print(f"  ⚠️ Market data failed: {e}")
        market_data = None

    print(f"   Found {len(articles)} articles")

    # Build email once — with market data
    html = build_email_html(articles, market_data)
    today = date.today().strftime("%A, %d %B")

    # ── FROM ADDRESS ──────────────────────────────────────────────
    FROM_ADDRESS = "Teesra <brief@teesra.in>"

    params = {
        "from": FROM_ADDRESS,
        "to": [to_email],
        "subject": f"☀️ Teesra Brief — {today} · {len(articles)} stories ",
        "html": html
    }

    try:
        response = resend.Emails.send(params)
        print(f"✅ Newsletter sent to {to_email}")
        print(f"   Email ID: {response['id']}")
        return True
    except Exception as e:
        print(f"❌ Failed to send to {to_email}: {e}")
        return False


# ── RUN ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys

    # Allow passing email as argument or send to all subscribers
    if len(sys.argv) > 1:
        # Called with specific email: python newsletter.py test@gmail.com
        send_newsletter(sys.argv[1])
    else:
        # Send to all active subscribers
        subscribers = get_all_subscribers()

        if not subscribers:
            print("⚠️  No subscribers found. Add yourself first via the website signup.")
            test = input("Send test to this email instead: ").strip()
            if test:
                send_newsletter(test)
        else:
            print(f"\n📬 Sending to {len(subscribers)} subscribers...")
            success = 0
            for email in subscribers:
                if send_newsletter(email):
                    success += 1
            print(f"\n✅ Newsletter sent to {success}/{len(subscribers)} subscribers")