article = {
    "title": "India wins ICC Cricket World Cup 2023",
    "source": "The Hindu",
    "url": "https://www.thehindu.com/sport/cricket/icc-world-cup/icc-cricket-world-cup-2023-india-vs-australia-final-in-ahmedabad-on-november-19-2023/article67550515.ece",
    "content": "India wins ICC Cricket World Cup 2023 by beating Australia in the final at Ahmedabad on November 19, 2023. The match was a thrilling encounter with both teams playing great cricket. India's victory was a well-deserved achievement and the fans were delighted with the result.",
    "bias": "centre-left",
    "summary": "India wins ICC Cricket World Cup 2023 by beating Australia in the final at Ahmedabad on November 19, 2023. The match was a thrilling encounter with both teams playing great cricket. India's victory was a well-deserved achievement and the fans were delighted with the result.",
    "date": "2023-11-19",
    "author": "The Hindu",
    "tags": ["cricket", "world cup", "india", "australia"],
    "keywords": ["cricket", "world cup", "india", "australia"]
}

print("Title:", article["title"])
print("Source:", article["source"])
print("URL:", article["url"])
print("Content:", article["content"])
print("Bias:", article["bias"])
print("Summary:", article["summary"])
print("Date:", article["date"])
print("Author:", article["author"])
print("Tags:", article["tags"])

# Dictionaries - the most important concept for Teesra
# Think of a dictionary like one row in Excel with named columns

article = {
    "title": "India wins the series against Australia",
    "source": "The Hindu",
    "url": "https://thehindu.com/example",
    "bias": "center-left",
    "summary": "India clinched the series 3-1 in Melbourne"
}

# Access any value like this
print("Title:", article["title"])
print("Source:", article["source"])
print("Bias:", article["bias"])

# A list of dictionaries = multiple rows = a table
# This is EXACTLY how Teesra will store news articles

articles = [
    {
        "title": "RBI cuts interest rates",
        "source": "Mint",
        "bias": "center"
    },
    {
        "title": "Opposition protests in Parliament",
        "source": "The Wire",
        "bias": "left"
    },
    {
        "title": "India's GDP growth beats estimates",
        "source": "Swarajya",
        "bias": "right"
    }
]

print(f"\nFetched {len(articles)} articles:")

for article in articles:
    print(f"  [{article['bias'].upper()}] {article['title']} — {article['source']}")

