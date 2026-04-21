# newsletter.py
# Teesra — Daily email newsletter
# Pulls today's articles from Supabase and sends formatted email

import os
import requests
from collections import defaultdict
from dotenv import load_dotenv
from database import get_todays_articles, get_all_subscribers
from datetime import date, datetime, timezone, timedelta
from market_data import fetch_market_data, format_market_for_email

IST = timezone(timedelta(hours=5, minutes=30))

load_dotenv()
BREVO_API_KEY = os.getenv("BREVO_API_KEY")
BREVO_SMTP_URL = "https://api.brevo.com/v3/smtp/email"


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
    config = TYPE_CONFIG.get(article.get('story_type', 'general'), TYPE_CONFIG['general'])
    color = config['color']
    label = f"{config['emoji']} {config['label']}"

    # Truncate facts to teaser length — first 2 sentences only
    facts_full = article.get('facts', '')
    sentences = facts_full.split('.')
    facts_teaser = '. '.join(sentences[:2]).strip()
    if facts_teaser and not facts_teaser.endswith('.'):
        facts_teaser += '.'
    if len(sentences) > 2:
        facts_teaser += ' <span style="color:#e8c84a;">+ more</span>'

    impact = article.get('impact', '')
    url = article.get('url', '')
    article_id = article.get('id', '')
    read_more_url = (
        f"https://teesra.in/story/{article_id}"
        if article_id
        else "https://teesra.in/feed"
    )
    source_link = f'&nbsp;&bull;&nbsp;<a href="{url}" style="color:#6a6650;">Source &#8594;</a>' if url else ''

    return f"""
    <tr>
      <td style="padding:0 0 20px 0;">
        <table width="100%" cellpadding="0" cellspacing="0"
               style="background:#141410;
                      border:1px solid #2a2a1f;
                      border-top:3px solid {color};">

          <!-- HEADER -->
          <tr>
            <td style="padding:20px 24px 14px 24px;">
              <p style="margin:0 0 8px 0;
                  font-family:monospace;
                  font-size:9px;
                  color:{color};
                  letter-spacing:2px;
                  text-transform:uppercase;
                  font-weight:700;">
                  {label}
              </p>
              <h2 style="margin:0 0 10px 0;
                  font-family:Georgia,serif;
                  font-size:20px;
                  font-weight:700;
                  color:#f0ece0;
                  line-height:1.35;">
                  {article.get('headline', '')}
              </h2>
              <p style="margin:0;
                  font-family:monospace;
                  font-size:10px;
                  color:#6a6650;">
                  {article.get('source', '')}
                  &nbsp;&bull;&nbsp;
                  {article.get('source_bias', '')}
                  {source_link}
              </p>
            </td>
          </tr>

          <!-- FACTS TEASER -->
          <tr>
            <td style="padding:0 24px 14px 24px;">
              <p style="margin:0 0 4px 0;
                  font-family:monospace;
                  font-size:9px;
                  color:#e8c84a;
                  letter-spacing:2px;
                  text-transform:uppercase;
                  font-weight:700;">
                  &#9878; Facts
              </p>
              <p style="margin:0;
                  font-size:14px;
                  color:#c0b898;
                  line-height:1.7;">
                  {facts_teaser}
              </p>
            </td>
          </tr>

          <!-- IMPACT -->
          <tr>
            <td style="padding:10px 24px 16px 24px;
                background:rgba(232,200,74,0.04);
                border-top:1px solid #2a2a1f;">
              <p style="margin:0 0 4px 0;
                  font-family:monospace;
                  font-size:9px;
                  color:#e8c84a;
                  letter-spacing:2px;
                  text-transform:uppercase;
                  font-weight:700;">
                  Impact
              </p>
              <p style="margin:0;
                  font-size:14px;
                  color:#e8e4d4;
                  line-height:1.6;
                  font-weight:500;">
                  {impact}
              </p>
            </td>
          </tr>

          <!-- READ MORE CTA -->
          <tr>
            <td style="
                padding:12px 24px;
                border-top:1px solid #2a2a1f;
                background:#0f0f0a;">
              <table cellpadding="0" cellspacing="0" width="100%">
                <tr>
                  <td>
                    <p style="margin:0;
                        font-family:monospace;
                        font-size:9px;
                        color:#5a5848;
                        letter-spacing:1px;">
                        Left &middot; Right &middot;
                        Street Pulse on website
                    </p>
                  </td>
                  <td align="right">
                    <a href="{read_more_url}"
                       style="
                        font-family:monospace;
                        font-size:10px;
                        font-weight:700;
                        color:#e8c84a;
                        text-decoration:none;
                        letter-spacing:1px;
                        border:1px solid
                            rgba(232,200,74,0.3);
                        padding:5px 12px;">
                        Full Analysis &#8594;
                    </a>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

        </table>
      </td>
    </tr>"""


# ── BUILD FULL EMAIL ──────────────────────────────────────────────
def build_email_html(articles, market_data=None, recipient_email="",
                     story_of_week=None):
    today = datetime.now(IST).strftime("%A, %d %B %Y")
    article_count = len(articles)

    market_section = ""
    if market_data:
        try:
            market_section = format_market_for_email(market_data)
        except Exception as e:
            print(f"  ⚠️ Market email section failed: {e}")

    sotw_section = ""
    if story_of_week:
        sotw_section = f"""
  <tr>
    <td style="padding:0 0 28px 0;">
      <table width="100%" cellpadding="0" cellspacing="0"
             style="background:#0f1a0f;border:2px solid #e8c84a;">
        <tr>
          <td style="padding:16px 24px 0 24px;">
            <p style="margin:0 0 4px 0;font-family:monospace;font-size:9px;
                color:#e8c84a;letter-spacing:3px;text-transform:uppercase;">
                &#10022; Story of the Week</p>
            <p style="margin:0 0 4px 0;font-family:monospace;font-size:9px;
                color:#7a7660;">{story_of_week.get('week_start','')} to {story_of_week.get('week_end','')}</p>
          </td>
        </tr>
        <tr>
          <td style="padding:8px 24px 20px 24px;">
            <h2 style="margin:0 0 12px 0;font-family:Georgia,serif;font-size:20px;
                font-weight:700;color:#e8e4d4;line-height:1.35;">
                {story_of_week.get('headline','')}</h2>
            <p style="margin:0 0 10px 0;font-size:13px;color:#b0aa90;line-height:1.65;">
                {story_of_week.get('summary','')}</p>
            <p style="margin:0 0 4px 0;font-family:monospace;font-size:9px;
                color:#e8c84a;letter-spacing:2px;text-transform:uppercase;">Why it matters</p>
            <p style="margin:0;font-size:13px;color:#e8e4d4;line-height:1.6;">
                {story_of_week.get('why_it_matters','')}</p>
          </td>
        </tr>
      </table>
    </td>
  </tr>
  <tr><td style="padding:0 0 28px 0;border-bottom:1px solid #2a2a1f;"></td></tr>
  <tr><td style="height:28px;"></td></tr>
"""

    stories_html = ""
    for i, article in enumerate(articles):
        stories_html += build_story_html(article, i + 1)

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<meta name="color-scheme" content="light dark">
</head>
<body style="margin:0;padding:0;
    background:#0a0a08;
    font-family:Georgia,serif;
    -webkit-font-smoothing:antialiased;">

<table width="100%" cellpadding="0" cellspacing="0"
       style="background:#0a0a08;padding:40px 16px;">
<tr><td align="center">
<table width="640" cellpadding="0" cellspacing="0"
       style="max-width:640px;width:100%;">

  <!-- MASTHEAD -->
  <tr>
    <td style="padding:0 0 32px 0;border-bottom:2px solid #e8c84a;">
      <table width="100%" cellpadding="0" cellspacing="0">
        <tr>
          <td>
            <p style="margin:0 0 4px 0;
                font-family:Georgia,serif;
                font-size:36px;
                font-weight:900;
                color:#e8c84a;
                letter-spacing:-1px;
                line-height:1;">Teesra</p>
            <p style="margin:0;
                font-family:monospace;
                font-size:10px;
                color:#5a5848;
                letter-spacing:3px;
                text-transform:uppercase;">
                &#2340;&#2368;&#2360;&#2352;&#2366; &#2344;&#2364;&#2364;&#2352;&#2367;&#2351;&#2366;
                &nbsp;&bull;&nbsp;
                The Third Perspective
            </p>
          </td>
          <td align="right" valign="bottom">
            <p style="margin:0;
                font-family:monospace;
                font-size:10px;
                color:#5a5848;
                letter-spacing:1px;">MORNING EDITION</p>
            <p style="margin:4px 0 0 0;
                font-family:Georgia,serif;
                font-size:16px;
                font-weight:700;
                color:#e8e4d4;">{today}</p>
          </td>
        </tr>
      </table>
    </td>
  </tr>

  <!-- DATE + COUNT BAR -->
  <tr>
    <td style="padding:20px 0 24px 0;">
      <p style="margin:0 0 4px 0;
          font-family:monospace;
          font-size:10px;
          color:#7a7660;
          letter-spacing:2px;
          text-transform:uppercase;">Daily Brief</p>
      <p style="margin:0 0 8px 0;
          font-family:Georgia,serif;
          font-size:13px;
          color:#7a7660;">
          {article_count} stories today
          &nbsp;&bull;&nbsp;
          Verified across 3+ sources each
          &nbsp;&bull;&nbsp;
          Facts first
      </p>
      <p style="margin:0;
          font-family:monospace;
          font-size:10px;
          color:#5a5848;">
          Read online at
          <a href="https://teesra.in/feed"
             style="color:#e8c84a;text-decoration:none;">
              teesra.in/feed
          </a>
      </p>
    </td>
  </tr>

  <!-- DIVIDER -->
  <tr><td style="padding:0 0 28px 0;border-bottom:1px solid #2a2a1f;"></td></tr>
  <tr><td style="height:28px;"></td></tr>

  {sotw_section}

  <!-- MARKET DATA -->
  {market_section}

  <!-- STORIES -->
  {stories_html}

  <!-- FOOTER -->
  <tr>
    <td style="padding:32px 0 0 0;border-top:1px solid #2a2a1f;text-align:center;">
      <p style="margin:0 0 8px 0;
          font-family:Georgia,serif;
          font-size:17px;
          font-weight:700;
          color:#e8e4d4;">Found this useful?</p>
      <p style="margin:0 0 20px 0;
          font-family:monospace;
          font-size:10px;
          color:#5a5848;
          letter-spacing:1.5px;
          text-transform:uppercase;">
          Share with someone who reads only one side
      </p>

      <table cellpadding="0" cellspacing="0" style="margin:0 auto 28px auto;">
        <tr>
          <td style="padding:0 6px;">
            <a href="https://wa.me/?text=Read%20today%27s%20Teesra%20brief%20%E2%80%94%20India%27s%20news%20from%20three%20perspectives.%20https%3A%2F%2Fteesra.in%2Ffeed"
               style="display:inline-block;
                   padding:10px 20px;
                   background:#25D366;
                   font-family:monospace;
                   font-size:11px;
                   letter-spacing:1.5px;
                   color:#0a0a08;
                   text-decoration:none;
                   text-transform:uppercase;
                   font-weight:700;
                   border-radius:4px;">
                WhatsApp
            </a>
          </td>
          <td style="padding:0 6px;">
            <a href="https://teesra.in/feed"
               style="display:inline-block;
                   padding:10px 20px;
                   background:rgba(232,200,74,0.1);
                   border:1px solid rgba(232,200,74,0.3);
                   font-family:monospace;
                   font-size:11px;
                   letter-spacing:1.5px;
                   color:#e8c84a;
                   text-decoration:none;
                   text-transform:uppercase;
                   border-radius:4px;">
                Read Online
            </a>
          </td>
        </tr>
      </table>

      <p style="margin:0 0 4px 0;
          font-family:Georgia,serif;
          font-size:16px;
          font-weight:900;
          color:#e8c84a;">Teesra</p>
      <p style="margin:0 0 12px 0;
          font-family:monospace;
          font-size:9px;
          color:#3a3a28;
          letter-spacing:2px;
          text-transform:uppercase;">No ads. No agenda. No spin.</p>
      <p style="margin:0 0 6px 0;
          font-size:11px;
          color:#5a5848;
          font-style:italic;">
          We don't tell you what to think.
          We give you what you need to think for yourself.
      </p>
      <p style="margin:0;
          font-size:11px;
          color:#4a5568;
          font-family:monospace;">
          Don't want these emails?
          <a href="https://teesra.in/unsubscribe?email={recipient_email}"
             style="color:#718096;text-decoration:underline;">Unsubscribe</a>
      </p>
    </td>
  </tr>

</table>
</td></tr>
</table>
</body>
</html>"""


# ── SELECT NEWSLETTER ARTICLES ────────────────────────────────────
def select_newsletter_articles(articles: list, target: int = 15) -> list:
    """
    Pick 12-15 articles with topic diversity for the newsletter.
    Score is not stored in Supabase, so use type-based caps.
    Max: political=3, general=3, sports=2, tech=2, international=2, sensitive=1.
    """
    type_caps = {
        "political":     3,
        "general":       3,
        "sports":        2,
        "tech":          2,
        "international": 2,
        "sensitive":     1,
    }
    type_counts = defaultdict(int)
    selected = []

    for article in articles:
        if len(selected) >= target:
            break
        t = article.get("story_type", "general")
        cap = type_caps.get(t, 2)
        if type_counts[t] < cap:
            selected.append(article)
            type_counts[t] += 1

    # If still under 12, top up without caps
    if len(selected) < 12:
        used_ids = {id(a) for a in selected}
        for article in articles:
            if len(selected) >= target:
                break
            if id(article) not in used_ids:
                selected.append(article)

    return selected


# ── DUPLICATE SEND PREVENTION ─────────────────────────────────────
def already_sent_today() -> bool:
    """Check if newsletter already sent today"""
    try:
        from database import get_client
        IST_check = timezone(timedelta(hours=5, minutes=30))
        today = str(datetime.now(IST_check).date())
        client = get_client()
        result = client.table('newsletter_log')\
            .select('id')\
            .eq('sent_date', today)\
            .execute()
        return len(result.data) > 0
    except Exception as e:
        print(f"  ⚠️ Log check failed: {e}")
        return False


def mark_newsletter_sent():
    """Record newsletter was sent today"""
    try:
        from database import get_client
        IST_mark = timezone(timedelta(hours=5, minutes=30))
        now_ist = datetime.now(IST_mark)
        client = get_client()
        client.table('newsletter_log').insert({
            'sent_date': str(now_ist.date()),
            'sent_at': now_ist.isoformat()
        }).execute()
        print("  ✅ Newsletter send logged")
    except Exception as e:
        print(f"  ⚠️ Could not log send: {e}")


# ── SEND NEWSLETTER ───────────────────────────────────────────────
def send_newsletter(to_email: str):
    print(f"\n📧 Building today's Teesra newsletter...")

    # Prevent duplicate sends
    if already_sent_today():
        print("⚠️ Newsletter already sent today — skipping to prevent duplicates")
        return False

    all_articles = get_todays_articles()

    if not all_articles:
        print("❌ No articles found for today. Run analyze_article.py first.")
        return False

    # Select top 12-15 with topic diversity for email
    articles = select_newsletter_articles(all_articles, target=15)
    print(f"   Found {len(all_articles)} articles total — sending top {len(articles)} in newsletter")

    try:
        from market_data import fetch_market_data, fetch_commodity_data
        market_data = fetch_market_data()
        commodity_data = fetch_commodity_data()
        if commodity_data and market_data:
            market_data.update(commodity_data)
    except Exception as e:
        print(f"  ⚠️ Market data failed: {e}")
        market_data = None

    # Detect Sunday IST — add Story of the Week
    ist_now = datetime.now(IST)
    is_sunday = ist_now.weekday() == 6
    today_str = ist_now.strftime("%A, %d %B")

    story_of_week = None
    if is_sunday:
        try:
            from story_of_week import get_latest_story_of_week
            story_of_week = get_latest_story_of_week()
            if story_of_week:
                print(f"  📅 Sunday edition — adding Story of the Week")
        except Exception as e:
            print(f"  ⚠️ Story of week failed: {e}")

    # Build email with optional story of week
    html = build_email_html(articles, market_data,
                            recipient_email=to_email,
                            story_of_week=story_of_week)

    if is_sunday:
        subject = f"☀️ Teesra Sunday Brief — {today_str} · Week in Review"
    else:
        subject = f"☀️ Teesra Brief — {today_str} · {len(articles)} stories"

    # ── FROM ADDRESS ──────────────────────────────────────────────
    FROM_ADDRESS = "Teesra <brief@teesra.in>"

    payload = {
        "sender": {
            "name": "Teesra",
            "email": "brief@teesra.in"
        },
        "to": [{"email": to_email}],
        "subject": subject,
        "htmlContent": html
    }

    try:
        response = requests.post(
            BREVO_SMTP_URL,
            headers={
                "api-key": BREVO_API_KEY,
                "Content-Type": "application/json"
            },
            json=payload,
            timeout=15
        )
        if response.status_code == 201:
            data = response.json()
            print(f"✅ Newsletter sent to {to_email}")
            print(f"   Message ID: {data.get('messageId', 'n/a')}")
            return True
        else:
            print(f"❌ Brevo error {response.status_code}: {response.text}")
            return False
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