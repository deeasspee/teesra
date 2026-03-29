# test_send.py
# Sends today's already-analyzed brief to one or all subscribers.
# Does NOT re-fetch RSS or re-call Claude API — uses what's already in Supabase.
# Run: python test_send.py

from newsletter import send_newsletter
from database import get_all_subscribers, get_todays_articles

articles = get_todays_articles()
print(f"📰 Articles in Supabase today: {len(articles)}")

if not articles:
    print("❌ No articles found. Run python run_daily.py first to analyze today's stories.")
    exit()

subscribers = get_all_subscribers()
print(f"👥 Active subscribers: {len(subscribers)}")

# ── CHANGE THIS to control who gets the test email ────────────────
# Option A: Send only to yourself (safe while domain isn't verified)
TEST_ONLY_TO = "dsp.fiem@gmail.com"

# Option B: Send to all subscribers (uncomment after domain is verified)
# TEST_ONLY_TO = None
# ─────────────────────────────────────────────────────────────────

if TEST_ONLY_TO:
    print(f"\n🧪 Test mode — sending only to {TEST_ONLY_TO}")
    send_newsletter(TEST_ONLY_TO)
else:
    print(f"\n📬 Sending to all {len(subscribers)} subscribers...")
    success = 0
    for sub in subscribers:
        if send_newsletter(sub['email'] if isinstance(sub, dict) else sub):
            success += 1
    print(f"\n✅ Sent {success}/{len(subscribers)}")
