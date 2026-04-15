# run_daily.py
# Teesra — Daily pipeline runner
# Modes:
#   pipeline   — fetch, analyze, save to Supabase (runs at midnight IST)
#   newsletter — send newsletter from today's saved articles (runs at 7 AM IST)
#   full       — pipeline + newsletter (for manual local testing)

import sys
from datetime import datetime


def run_pipeline():
    """Full fetch + analyze + save pipeline. Does NOT send newsletter."""
    print(f"\n🚀 TEESRA DAILY PIPELINE — FETCH & ANALYZE")
    from datetime import timezone, timedelta
    IST = timezone(timedelta(hours=5, minutes=30))
    ist_now = datetime.now(IST)
    print(f"   UTC Time:  {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   IST Time:  {ist_now.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   IST Date:  {ist_now.date()} (articles will be saved with this date)")
    print("=" * 50)

    # ── STEP 1: FETCH + ANALYZE ───────────────────────────────────
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
        print(f"\n✅ Pipeline done — {len(results)} articles saved\n")

    except Exception as e:
        print(f"❌ Pipeline failed: {e}")
        sys.exit(1)

    print("\n" + "=" * 50)
    print("✅ Teesra fetch & analyze complete!")
    print("=" * 50 + "\n")


def run_newsletter():
    """Send newsletter only — articles must already exist in Supabase
    from today's pipeline run."""
    print(f"\n📧 TEESRA NEWSLETTER SEND")
    from datetime import timezone, timedelta
    IST = timezone(timedelta(hours=5, minutes=30))
    ist_now = datetime.now(IST)
    print(f"   UTC Time:  {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   IST Time:  {ist_now.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   IST Date:  {ist_now.date()} (fetching articles for this date)")
    print("=" * 50)

    from newsletter import send_newsletter
    from database import get_all_subscribers, get_todays_articles

    # Safety check — confirm today's articles exist
    articles = get_todays_articles()
    if not articles:
        print("❌ No articles found for today.")
        print("   Pipeline may not have run yet.")
        print("   Newsletter send aborted.")
        return False

    print(f"  ✅ Found {len(articles)} articles for today")

    subscribers = get_all_subscribers()
    if not subscribers:
        print("  ⚠️  No active subscribers found")
        return False

    print(f"  📬 Sending to {len(subscribers)} subscribers...")
    success = 0
    failed = 0
    for sub in subscribers:
        email = sub['email'] if isinstance(sub, dict) else sub
        if send_newsletter(email):
            success += 1
        else:
            failed += 1

    print(f"\n  ✅ Newsletter sent: {success}/{len(subscribers)}")
    if failed > 0:
        print(f"  ❌ Failed: {failed}")

    print("\n" + "=" * 50)
    print("✅ Teesra newsletter send complete!")
    print("=" * 50 + "\n")
    return success > 0


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "full"

    if mode == "pipeline":
        run_pipeline()
    elif mode == "newsletter":
        run_newsletter()
    elif mode == "full":
        # Keep full mode for manual testing
        run_pipeline()
        run_newsletter()
    else:
        print(f"Unknown mode: {mode}")
        print("Usage: python run_daily.py [pipeline|newsletter|full]")
        sys.exit(1)
