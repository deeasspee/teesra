# article_selector.py
# Teesra — Smart article selection
# Picks the most important stories from all fetched articles
# Logic: stories covered by MORE sources = more important

from collections import defaultdict
import re


# ── CLEAN TITLE ───────────────────────────────────────────────────
# Removes noise from titles so we can compare them
def clean_title(title: str) -> str:
    title = title.lower()
    # Remove special characters
    title = re.sub(r'[^\w\s]', '', title)
    # Remove common filler words
    stopwords = [
        'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at',
        'to', 'for', 'of', 'with', 'by', 'from', 'is', 'are',
        'was', 'were', 'has', 'have', 'had', 'says', 'said',
        'india', 'indian', 'new', 'after', 'over', 'as'
    ]
    words = [w for w in title.split() if w not in stopwords]
    return ' '.join(words)


# ── TITLE SIMILARITY ──────────────────────────────────────────────
# Checks if two titles are about the same story
def titles_similar(title1: str, title2: str, threshold: int = 3) -> bool:
    words1 = set(clean_title(title1).split())
    words2 = set(clean_title(title2).split())

    if not words1 or not words2:
        return False

    # Count common words
    common = words1.intersection(words2)
    return len(common) >= threshold


# ── GROUP ARTICLES ────────────────────────────────────────────────
# Groups articles about the same story together
def group_articles(articles: list) -> list:
    groups = []

    for article in articles:
        placed = False

        # Try to find an existing group this article belongs to
        for group in groups:
            representative = group[0]
            if titles_similar(article['title'], representative['title']):
                group.append(article)
                placed = True
                break

        # If no matching group found, start a new one
        if not placed:
            groups.append([article])

    return groups


# ── SCORE GROUP ───────────────────────────────────────────────────
# Scores a group of articles by importance
def score_group(group: list) -> dict:
    sources = list(set([a['source'] for a in group]))
    biases = list(set([a['bias'] for a in group]))

    # More sources = more important
    source_count = len(sources)

    # Bonus if covered across multiple bias types
    bias_diversity = len(biases)

    # Final score
    score = (source_count * 2) + bias_diversity

    return {
        "score":        score,
        "source_count": source_count,
        "sources":      sources,
        "biases":       biases,
        "title":        group[0]['title'],
        "articles":     group
    }


# ── SELECT TOP STORIES ────────────────────────────────────────────
# Main function — returns top N articles for the daily brief
def select_top_stories(all_articles: list, n: int = 10) -> list:
    print(f"\n🧠 Selecting top {n} stories from {len(all_articles)} articles...")

    # Separate into buckets
    ipl_articles = []
    sports_articles = []
    tech_articles = []
    other_articles = []

    for article in all_articles:
        title_lower = article['title'].lower()
        source = article['source'].lower()

        # Tech bucket — from tech sources or tech keywords
        if source in ['techcrunch', 'the verge'] or any(word in title_lower for word in [
            'ai', 'artificial intelligence', 'chatgpt', 'openai', 'google', 'apple',
            'microsoft', 'startup', 'tech', 'app', 'software', 'smartphone',
            'cybersecurity', 'data', 'robot', 'machine learning', 'chip', 'semiconductor'
        ]):
            tech_articles.append(article)

        # IPL bucket
        elif any(word in title_lower for word in [
            'ipl', 'indian premier league', 'ipl 2026'
        ]):
            ipl_articles.append(article)

        # Sports bucket
        elif any(word in title_lower for word in [
            'cricket', 'match', 'test match', 'odi', 't20',
            'football', 'hockey', 'tournament', 'player',
            'score', 'wicket', 'goal', 'trophy', 'olympic',
            'fifa', 'icc', 'squad', 'batting', 'bowling'
        ]):
            sports_articles.append(article)

        else:
            other_articles.append(article)

    print(f"   Buckets → General: {len(other_articles)} | IPL: {len(ipl_articles)} | Sports: {len(sports_articles)} | Tech: {len(tech_articles)}")

    # ── SLOT ALLOCATION ───────────────────────────────────────────
    # 7 general + 1 IPL + 1 sports + 1 tech = 10
    general_slots = n - 3

    selected = []
    bias_priority = ['center', 'center-left', 'left', 'right']

    # ── GENERAL STORIES (7 slots) ─────────────────────────────────
    groups = group_articles(other_articles)
    scored = [score_group(g) for g in groups]
    scored.sort(key=lambda x: x['score'], reverse=True)

    for story in scored[:general_slots]:
        articles = story['articles']
        best = None
        for bias in bias_priority:
            for article in articles:
                if article['bias'] == bias:
                    best = article
                    break
            if best:
                break
        if not best:
            best = articles[0]
        best['covered_by'] = story['sources']
        best['source_count'] = story['source_count']
        selected.append(best)

    # ── IPL STORY (1 slot) ────────────────────────────────────────
    if ipl_articles:
        ipl = ipl_articles[0]
        ipl['covered_by'] = [ipl['source']]
        ipl['source_count'] = 1
        ipl['is_ipl'] = True
        selected.append(ipl)
        print(f"   ✅ IPL: {ipl['title'][:60]}...")
    else:
        # No IPL today — fill with best sports story instead
        if sports_articles:
            s = sports_articles[0]
            s['covered_by'] = [s['source']]
            s['source_count'] = 1
            selected.append(s)
            print(f"   ℹ️  No IPL today — using sports: {s['title'][:60]}...")
        else:
            print(f"   ⚠️  No IPL or sports story found")

    # ── SPORTS STORY (1 slot) ─────────────────────────────────────
    # Pick a sports story that isn't IPL
    sports_added = False
    for article in sports_articles[:5]:
        # Skip if title overlaps with already selected IPL story
        already_selected_titles = [a['title'] for a in selected]
        if article['title'] not in already_selected_titles:
            article['covered_by'] = [article['source']]
            article['source_count'] = 1
            selected.append(article)
            sports_added = True
            print(f"   ✅ Sports: {article['title'][:60]}...")
            break

    if not sports_added:
        print(f"   ⚠️  No non-IPL sports story found today")

    # ── TECH STORY (1 slot) ───────────────────────────────────────
    tech_added = False
    for article in tech_articles[:5]:
        already_selected_titles = [a['title'] for a in selected]
        if article['title'] not in already_selected_titles:
            article['covered_by'] = [article['source']]
            article['source_count'] = 1
            article['is_tech'] = True
            selected.append(article)
            tech_added = True
            print(f"   ✅ Tech: {article['title'][:60]}...")
            break

    if not tech_added:
        print(f"   ⚠️  No tech story found today")

    print(f"\n✅ Final selection: {len(selected)} stories")
    print(f"   {len([a for a in selected if a.get('is_ipl')])} IPL + "
          f"{len([a for a in selected if a.get('story_type') == 'sports' and not a.get('is_ipl')])} sports + "
          f"{len([a for a in selected if a.get('is_tech')])} tech + "
          f"{len([a for a in selected if not a.get('is_ipl') and not a.get('is_tech')])} general\n")

    return selected


# ── TEST ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    from fetch_news import fetch_all_news

    articles = fetch_all_news()
    top = select_top_stories(articles, n=10)

    print("\nFinal selection:")
    for i, a in enumerate(top):
        print(f"\n{i+1}. {a['title']}")
        print(f"   Source: {a['source']} | Covered by {a['source_count']} sources")
        print(f"   Sources: {', '.join(a['covered_by'])}")