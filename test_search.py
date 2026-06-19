# test_search.py
# Run from project root: python3 test_search.py

from tools.search_restaurants import search_restaurants


def test_area_only():
    print("\n--- Test 1: Area only (Connaught Place) ---")
    results = search_restaurants(area="Connaught Place")
    print(f"Found {len(results)} restaurants:")
    for r in results:
        status = "OPEN" if r["is_open"] else "CLOSED"
        print(f"  [{status}] {r['name']} | {r['cuisine']} | ₹{r['price_for_two']} for two | Rating: {r['rating']}")


def test_area_and_cuisine():
    print("\n--- Test 2: Area + cuisine filter (Lajpat Nagar, Chinese) ---")
    results = search_restaurants(area="Lajpat Nagar", cuisine="Chinese")
    print(f"Found {len(results)} restaurants:")
    for r in results:
        print(f"  {r['name']} | Rating: {r['rating']}")


def test_case_insensitive():
    print("\n--- Test 3: Case-insensitive search (lowercase area) ---")
    results = search_restaurants(area="karol bagh")
    print(f"Found {len(results)} restaurants (should be > 0):")
    for r in results:
        print(f"  {r['name']}")


def test_no_results():
    print("\n--- Test 4: Area that doesn't exist (should return empty list, not crash) ---")
    results = search_restaurants(area="Atlantis")
    print(f"Found {len(results)} restaurants (expected: 0)")
    assert results == [], f"Expected empty list, got: {results}"
    print("  Correctly returned empty list — no crash!")


def test_cuisine_no_results():
    print("\n--- Test 5: Area exists but cuisine doesn't match (should return empty list) ---")
    results = search_restaurants(area="Karol Bagh", cuisine="Ethiopian")
    print(f"Found {len(results)} restaurants (expected: 0)")
    assert results == [], f"Expected empty list, got: {results}"
    print("  Correctly returned empty list — no crash!")


if __name__ == "__main__":
    test_area_only()
    test_area_and_cuisine()
    test_case_insensitive()
    test_no_results()
    test_cuisine_no_results()
    print("\nAll tests passed!")