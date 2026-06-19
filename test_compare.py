# test_compare.py
# Run this from your project root with your venv active:
#   python3 test_compare.py

from tools.search_restaurants import search_restaurants
from tools.compare_restaurants import compare_restaurants

print("=" * 60)
print("TEST: Searching for restaurants in Connaught Place...")
print("=" * 60)

# Step 1: get restaurants (same as Day 5)
results = search_restaurants(area="Connaught Place")

if not results:
    print("No restaurants found — check your data/restaurants.json has 'Connaught Place' entries.")
else:
    print(f"Found {len(results)} restaurant(s). Now comparing...\n")

    # Step 2: pass them to compare — this is the new Day 6 logic
    ranked = compare_restaurants(results)

    if not ranked:
        print("All found restaurants are currently closed.")
    else:
        print(f"RANKED RESULTS (best first):\n")
        for i, r in enumerate(ranked, start=1):
            print(f"  #{i}: {r['name']}")
            print(f"       Score:    {r['score']}")
            print(f"       Rating:   {r['rating']}  |  Price: ₹{r['price_for_two']}  |  Delivery: {r['delivery_time_minutes']} min")
            print(f"       Offers:   {r.get('offers', [])}")
            print(f"       Breakdown: {r['score_breakdown']}")
            print()

print("=" * 60)
print("TEST: Edge case — empty list input")
print("=" * 60)
empty_result = compare_restaurants([])
print(f"compare_restaurants([]) returned: {empty_result}  (expected: [])\n")

print("=" * 60)
print("TEST: Edge case — all restaurants are closed")
print("=" * 60)
all_closed = [
    {"name": "Closed Place", "rating": 4.5, "price_for_two": 300,
     "delivery_time_minutes": 25, "offers": [], "is_open": False}
]
closed_result = compare_restaurants(all_closed)
print(f"compare_restaurants(all_closed) returned: {closed_result}  (expected: [])\n")