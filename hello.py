name= "Divyendu"
project= "teesra"

print(f"Hello, {name}!")
print(f"Building {project} - news from all 3 sides of the coin")


sources = ["The Hindu", "The Indian Express", "The Times of India","Swarajya","NDTV","Scroll","BBC India"]

print (f"\nTeesra will cover {len(sources)} sources today:")

for source in sources:
    print(f"- {source}")