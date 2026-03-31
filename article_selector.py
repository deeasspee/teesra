# article_selector.py
# Teesra — Smart article selection
# Picks the most meaningful stories for young Indians (18-30)
# Philosophy: importance > coverage count, diversity > repetition

from collections import defaultdict
import re


# ── CLEAN TITLE ───────────────────────────────────────────────────
def clean_title(title: str) -> str:
    title = title.lower()
    title = re.sub(r'[^\w\s]', '', title)
    stopwords = [
        'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at',
        'to', 'for', 'of', 'with', 'by', 'from', 'is', 'are',
        'was', 'were', 'has', 'have', 'had', 'says', 'said',
        'india', 'indian', 'new', 'after', 'over', 'as', 'his',
        'her', 'their', 'its', 'into', 'about', 'up', 'down'
    ]
    words = [w for w in title.split() if w not in stopwords]
    return ' '.join(words)


# ── TITLE SIMILARITY ──────────────────────────────────────────────
def titles_similar(title1: str, title2: str, threshold: int = 2) -> bool:
    words1 = set(clean_title(title1).split())
    words2 = set(clean_title(title2).split())
    if not words1 or not words2:
        return False
    return len(words1.intersection(words2)) >= threshold


# ── GROUP ARTICLES ────────────────────────────────────────────────
def group_articles(articles: list) -> list:
    groups = []
    for article in articles:
        placed = False
        for group in groups:
            if titles_similar(article['title'], group[0]['title']):
                group.append(article)
                placed = True
                break
        if not placed:
            groups.append([article])
    return groups


# ── DETECT TOPIC ──────────────────────────────────────────────────
def detect_topic(title: str, source: str) -> str:
    t = title.lower()

    if any(w in t for w in ['ipl', 'indian premier league', 'ipl 2026', 'ipl 2025']):
        return 'ipl'

    if source in ['TechCrunch', 'The Verge'] or any(w in t for w in [
        'artificial intelligence', 'ai ', ' ai,', 'chatgpt', 'openai', 'apple ',
        'microsoft', 'cybersecurity', 'robot', 'machine learning', 'chip ',
        'semiconductor', 'meta ', 'samsung', 'iphone', 'google ', 'fintech',
        'crypto ', 'blockchain', 'deepfake', 'data breach', 'cybercrime',
        'elon musk', 'tesla', 'spacex', 'ev startup', 'tech startup'
    ]):
        return 'tech'

    if any(w in t for w in [
        'cricket', 'test match', 'odi ', 't20 ', 'football', 'hockey',
        'tournament', 'wicket', 'goal', 'trophy', 'olympic', 'fifa',
        'icc ', 'batting', 'bowling', 'athlete', 'sport', 'coach ',
        'stadium', 'grand slam', 'formula 1', 'f1 ', 'badminton', 'kabaddi'
    ]):
        return 'sports'

    if source in ['BBC World', 'Reuters'] or any(w in t for w in [
        'ceasefire', 'nato', 'united nations', 'g20 ', 'brics',
        'imf ', 'world bank', 'us president', 'white house', 'trump ',
        'xi jinping', 'putin ', 'europe ', 'middle east', 'africa ',
        'global summit', 'trade war', 'tariff', 'world economy'
    ]):
        return 'international'

    if any(w in t for w in [
        'rbi ', 'sensex', 'nifty', 'rupee', 'union budget', 'gst ', 'income tax',
        'inflation', 'gdp ', 'interest rate', 'sebi ', 'ipo ', 'stock market',
        'recession', 'emi ', 'loan ', 'bank rate', 'fuel price', 'petrol price',
        'trade deficit', 'export', 'fdi ', 'forex', 'fiscal'
    ]):
        return 'economy'

    if any(w in t for w in [
        'parliament', 'lok sabha', 'rajya sabha', 'election', 'modi ',
        'rahul gandhi', 'bjp ', 'congress ', 'aap ', 'chief minister', 'cm ',
        'mla ', 'governor ', 'cabinet ', 'minister ', 'policy ', 'bill passed',
        'supreme court', 'high court verdict', 'cbi ', ' ed ', 'constitution',
        'government ', 'govt '
    ]):
        return 'politics'

    return 'general'


# ── SCORE GROUP ───────────────────────────────────────────────────
def score_group(group: list) -> dict:
    sources      = list(set([a['source'] for a in group]))
    biases       = list(set([a['bias']   for a in group]))
    title_lower  = group[0]['title'].lower()
    source_count = len(sources)

    # Source count capped — coverage is a signal not the whole story
    score = min(source_count * 3, 20) + len(biases)

    # ── National impact: affects large number of Indians ──────────
    national_impact = [
        'parliament', 'supreme court', 'rbi ', 'union budget', 'election',
        'inflation', 'gdp ', 'policy ', 'law ', 'bill passed', 'modi ',
        'cabinet ', 'government ', 'rupee', 'income tax', 'gst ',
        'employment', 'jobs', 'sebi ', 'interest rate', 'fuel price',
        'reservation', 'constitution', 'court verdict', 'cbi ', ' ed '
    ]
    for kw in national_impact:
        if kw in title_lower:
            score += 25
            break

    # ── Youth relevance ───────────────────────────────────────────
    youth_relevant = [
        'startup', 'unicorn', 'funding', 'ipo ', 'layoff', 'hiring',
        'ai ', 'artificial intelligence', 'chatgpt', 'climate',
        'education ', 'neet ', 'upsc ', 'iit ', 'iim ', 'scholarship',
        'mental health', 'housing price', 'rent ', 'emi ',
        'electric vehicle', 'ev ', 'renewable', 'upi ', 'fintech',
        'deepfake', 'data privacy', 'internship'
    ]
    for kw in youth_relevant:
        if kw in title_lower:
            score += 15
            break

    # ── India-connected international stories ────────────────────
    india_impact_intl = [
        'india ', 'pakistan', 'china ', 'border ', 'trade deal',
        'sanctions', 'oil price', 'dollar ', 'imf ', 'climate summit',
        'g20 ', 'brics', 'indian diaspora', 'visa'
    ]
    for kw in india_impact_intl:
        if kw in title_lower:
            score += 10
            break

    # ── Penalty: repetitive geopolitics (unless major development) ─
    repetitive_conflict = [
        'gaza ', 'west asia', 'israel ', 'hamas', 'ukraine ',
        'ceasefire talks', 'airstrike', 'missiles fired', 'shelling'
    ]
    new_development = [
        'ceasefire', 'deal ', 'ended', 'agreement', 'breakthrough',
        'nuclear', 'escalat', 'invasion'
    ]
    if any(kw in title_lower for kw in repetitive_conflict):
        if not any(kw in title_lower for kw in new_development):
            score -= 20

    # ── Penalty: petty one-off crime ─────────────────────────────
    # Block individual crimes unless they have systemic context
    petty_crime = [
        'drugged husband', 'killed husband', 'killed wife', 'stabbed ',
        'body found', 'missing person', 'honour killing', 'lover',
        'allegedly killed', 'murder accused', 'alleged murder',
        'killed over', 'skips birthday', 'birthday cake',
        'domestic dispute', 'quarrel', 'eve teasing'
    ]
    systemic_context = [
        'politician', 'minister', 'mla ', 'mp ', 'judge ', 'police officer',
        'pattern', 'nationwide', 'widespread', 'crackdown',
        'gang ', 'organised', 'terror', 'naxal', 'serial'
    ]
    if any(kw in title_lower for kw in petty_crime):
        if not any(kw in title_lower for kw in systemic_context):
            score -= 35

    # ── Penalty: celebrity/trivial ────────────────────────────────
    trivial = [
        'birthday party', 'birthday cake', 'birthday celebration',
        'wedding ', 'divorce ', 'breakup', 'dating ', 'affair ',
        'viral video', 'trolled', 'outfit', 'hairstyle', 'red carpet',
        'award night', 'baby shower', 'photoshoot', 'skips birthday'
    ]
    for kw in trivial:
        if kw in title_lower:
            score -= 25
            break

    # ── Penalty: hyper-local ──────────────────────────────────────
    hyperlocal = [
        'municipal ', 'ward ', 'panchayat', 'locality ', 'pothole',
        'water supply', 'power cut', 'district court', 'admit card',
        'school holiday', 'college exam date', 'result class'
    ]
    for kw in hyperlocal:
        if kw in title_lower:
            score -= 20
            break

    return {
        "score":        score,
        "source_count": source_count,
        "sources":      sources,
        "biases":       biases,
        "title":        group[0]['title'],
        "topic":        detect_topic(group[0]['title'], group[0].get('source', '')),
        "articles":     group
    }


# ── PICK BEST ARTICLE FROM GROUP ─────────────────────────────────
def pick_best_article(articles: list) -> dict:
    bias_priority = ['center', 'center-left', 'left', 'right']
    for bias in bias_priority:
        for a in articles:
            if a['bias'] == bias:
                return a
    return articles[0]


# ── SELECT TOP STORIES ────────────────────────────────────────────
def select_top_stories(all_articles: list, n: int = 15) -> list:
    print(f"\n🧠 Selecting top {n} stories from {len(all_articles)} articles...")

    # Step 1: Group + score
    groups = group_articles(all_articles)
    scored = [score_group(g) for g in groups]
    scored.sort(key=lambda x: x['score'], reverse=True)
    print(f"   Grouped into {len(scored)} unique stories")

    # Step 2: Topic slot limits — flexible, prevents domination
    topic_max = {
        'politics':      5,
        'general':       4,
        'economy':       3,
        'international': 2,
        'tech':          2,
        'sports':        2,
        'ipl':           1,
    }
    # Minimum guaranteed slots
    topic_min = {
        'international': 1,
        'tech':          1,
        'sports':        1,
    }
    topic_counts   = defaultdict(int)
    conflict_used  = set()   # one story per conflict zone
    selected       = []
    selected_titles = set()

    # Step 3: First pass — fill by score with topic caps
    for story in scored:
        if len(selected) >= n:
            break

        topic      = story['topic']
        title_lower = story['title'].lower()

        # Block very negative scores
        if story['score'] < -10:
            print(f"   ⛔ Blocked (score {story['score']:+d}): {story['title'][:60]}")
            continue

        # Topic cap
        if topic_counts[topic] >= topic_max.get(topic, 4):
            continue

        # One story per conflict zone
        conflict_zone = None
        for zone in ['gaza', 'ukraine', 'myanmar', 'taiwan', 'sudan']:
            if zone in title_lower:
                conflict_zone = zone
                break
        if conflict_zone:
            if conflict_zone in conflict_used:
                print(f"   ⛔ Conflict repeat: {story['title'][:60]}")
                continue
            conflict_used.add(conflict_zone)

        # Pick best source from group
        best = pick_best_article(story['articles'])
        best['covered_by']   = story['sources']
        best['source_count'] = story['source_count']
        if topic == 'ipl':           best['is_ipl'] = True
        if topic == 'tech':          best['is_tech'] = True
        if topic == 'international': best['is_international'] = True

        selected.append(best)
        selected_titles.add(story['title'])
        topic_counts[topic] += 1
        print(f"   ✅ [{topic.upper():13}] {story['score']:+3d} | {story['title'][:55]}...")

    # Step 4: Guarantee minimums — force one in if topic missing
    for topic, min_count in topic_min.items():
        if topic_counts[topic] < min_count:
            print(f"   ⚠️  {topic} minimum not met — forcing fallback...")
            for story in scored:
                if story['topic'] == topic and story['title'] not in selected_titles:
                    best = pick_best_article(story['articles'])
                    best['covered_by']   = story['sources']
                    best['source_count'] = story['source_count']
                    if topic == 'tech':          best['is_tech'] = True
                    if topic == 'international': best['is_international'] = True
                    selected.append(best)
                    selected_titles.add(story['title'])
                    topic_counts[topic] += 1
                    print(f"   ➕ Forced [{topic.upper()}]: {story['title'][:55]}...")
                    break

    # Step 5: Reorder — India/politics/economy first, sports/IPL last
    def sort_order(a):
        t = a.get('_topic_cache') or detect_topic(a.get('title',''), a.get('source',''))
        if a.get('is_ipl'):           return 6
        if t == 'sports':             return 5
        if a.get('is_tech'):          return 4
        if a.get('is_international'): return 3
        if t == 'economy':            return 2
        return 1

    selected.sort(key=sort_order)

    # Summary
    counts = defaultdict(int)
    for a in selected:
        t = detect_topic(a.get('title',''), a.get('source',''))
        if a.get('is_ipl'): t = 'ipl'
        counts[t] += 1

    print(f"\n✅ Final selection: {len(selected)} stories")
    for t, c in sorted(counts.items()):
        print(f"   {t:14}: {c}")
    print()

    return selected


# ── TEST ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    from fetch_news import fetch_all_news
    articles = fetch_all_news()
    top = select_top_stories(articles, n=15)
    print("\nFinal selection:")
    for i, a in enumerate(top):
        t = detect_topic(a.get('title',''), a.get('source',''))
        print(f"\n{i+1}. [{t.upper()}] {a['title']}")
        print(f"   Source: {a['source']} | {a['source_count']} sources: {', '.join(a['covered_by'])}")
