# run_daily.py
# Teesra — Full daily pipeline
# Runs automatically every morning via GitHub Actions
# Order: fetch → analyze → send newsletter

import sys
from datetime import datetime

def run():
    print(f"\n🌅 Teesra Daily Pipeline Starting...")
    print(f"   Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # ── STEP 1: FETCH + ANALYZE ───────────────────────────────────
    print("=" * 50)
    print("STEP 1 — Fetching and analyzing news")
    print("=" * 50)

    try:
        from fetch_news import fetch_all_news
        from article_selector import select_top_stories
        from analyze_article import analyze_article, display_analysis
        from database import save_article, clear_todays_articles

        print("📡 Fetching live articles...")
        all_articles = fetch_all_news()

        TARGET = 20
        clear_todays_articles()
        # Select 30 candidates so ~20 survive Claude's quality filters
        top_articles = select_top_stories(all_articles, n=30)

        print(f"\n🧠 Analyzing up to {len(top_articles)} articles (target: {TARGET})...\n")
        results = []

        for i, article in enumerate(top_articles):
            if len(results) >= TARGET:
                print(f"  ✅ Target of {TARGET} reached — stopping early")
                break
            print(f"  [{i+1}/{len(top_articles)}] {article['title'][:60]}...")
            analysis = analyze_article(article)
            if analysis:
                save_article(analysis)
                results.append(analysis)

        print(f"\n✅ Step 1 done — {len(results)} articles saved\n")

    except Exception as e:
        print(f"❌ Step 1 failed: {e}")
        sys.exit(1)

    # ── STEP 2: SEND NEWSLETTER ───────────────────────────────────
    print("=" * 50)
    print("STEP 2 — Sending newsletter")
    print("=" * 50)

    try:
        from newsletter import send_newsletter
        from database import get_all_subscribers

        subscribers = get_all_subscribers()

        if not subscribers:
            print("⚠️  No subscribers yet — skipping newsletter")
        else:
            print(f"📬 Sending to {len(subscribers)} subscribers...")
            success = 0
            for sub in subscribers:
                email = sub['email'] if isinstance(sub, dict) else sub
                if send_newsletter(email):
                    success += 1
            print(f"✅ Sent to {success}/{len(subscribers)} subscribers")

    except Exception as e:
        print(f"❌ Step 2 failed: {e}")
        sys.exit(1)

    print("\n" + "=" * 50)
    print("✅ Teesra daily pipeline complete!")
    print("=" * 50 + "\n")

if __name__ == "__main__":
    run()