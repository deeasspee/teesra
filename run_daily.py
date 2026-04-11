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
        print(f"\n📊 PIPELINE DIAGNOSTIC:")
        print(f"   Stage 1 — RSS fetch:       {len(all_articles)} articles")

        TARGET = 20
        clear_todays_articles()
        # Select 40 candidates so 15-20 survive Claude's quality filters
        top_articles = select_top_stories(all_articles, n=40)
        print(f"   Stage 2 — After scoring:   {len(top_articles)} candidates selected")

        print(f"\n🧠 Analyzing up to {len(top_articles)} articles (target: {TARGET})...\n")
        results = []
        failed_analysis = 0

        STOPWORDS = {'a','an','the','in','on','at','to','of','for','is','are',
                     'was','were','has','have','had','and','or','but','with','from','by','after'}

        def headlines_similar(h1, h2):
            """Return True if two Claude-rewritten headlines cover the same story."""
            w1 = set(h1.lower().split()) - STOPWORDS
            w2 = set(h2.lower().split()) - STOPWORDS
            if not w1 or not w2:
                return False
            overlap = len(w1 & w2)
            return overlap / min(len(w1), len(w2)) >= 0.6

        for i, article in enumerate(top_articles):
            if len(results) >= TARGET:
                print(f"  ✅ Target of {TARGET} reached — stopping early")
                break
            print(f"  [{i+1}/{len(top_articles)}] {article['title'][:60]}...")
            analysis = analyze_article(article)
            if analysis:
                new_headline = analysis.get('headline', '')
                # Skip if same story already saved in this run
                existing = [r.get('headline', '') for r in results]
                if any(headlines_similar(new_headline, h) for h in existing):
                    print(f"  🔁 Duplicate story — skipping: {new_headline[:55]}...")
                    continue
                save_article(analysis)
                results.append(analysis)
            else:
                failed_analysis += 1
                print(f"  ⚠️  Claude rejected or failed — running total: {failed_analysis} rejected")

        print(f"\n📊 PIPELINE SUMMARY:")
        print(f"   Stage 1 — RSS fetch:       {len(all_articles)} articles")
        print(f"   Stage 2 — After scoring:   {len(top_articles)} candidates")
        print(f"   Stage 3 — Claude analysis: {len(results)} passed, {failed_analysis} rejected")
        print(f"   Stage 4 — Saved to DB:     {len(results)} articles")
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