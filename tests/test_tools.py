# tests/test_tools.py
"""
Automated tests for the two deterministic tools:
  - search_restaurants  (pure filtering logic)
  - compare_restaurants (scoring + ranking logic)

WHY these two tools specifically?
  - They're deterministic: same input → same output every time.
  - LLM calls (recommend, agent loop) are NOT deterministic, so you can't
    assert an exact output. Testing those belongs to integration/eval frameworks,
    not unit tests.
  - place_order touches the filesystem; we keep it simple and test it separately
    (or mock the file write) — that's a stretch goal noted below.
"""

import pytest
from tools.search_restaurants import search_restaurants
from tools.compare_restaurants import compare_restaurants


# ─────────────────────────────────────────────
# FIXTURES
# A "fixture" is reusable test data. pytest injects it into any test
# function that declares it as a parameter. This way you write the data once.
# ─────────────────────────────────────────────

@pytest.fixture
def sample_restaurants():
    """
    A self-contained list of restaurant dicts that mirrors your JSON schema.
    Using a fixture (not the real restaurants.json) means:
      1. Tests are isolated — changes to your data file won't break tests.
      2. You control edge cases precisely (e.g., a closed restaurant, a tie).
    """
    return [
        {
            "id": "t1",
            "name": "Spice Villa",
            "area": "Connaught Place",
            "cuisine": "North Indian",
            "rating": 4.5,
            "price_for_two": 400,
            "delivery_time_minutes": 30,
            "offers": ["20% off above ₹300"],
            "is_open": True,
        },
        {
            "id": "t2",
            "name": "Dragon Wok",
            "area": "Connaught Place",
            "cuisine": "Chinese",
            "rating": 4.1,
            "price_for_two": 350,
            "delivery_time_minutes": 25,
            "offers": [],
            "is_open": True,
        },
        {
            "id": "t3",
            "name": "Pizza Paradise",
            "area": "Connaught Place",
            "cuisine": "Italian",
            "rating": 3.8,
            "price_for_two": 600,
            "delivery_time_minutes": 45,
            "offers": ["Buy 1 Get 1"],
            "is_open": True,
        },
        {
            "id": "t4",
            "name": "Closed Café",
            "area": "Connaught Place",
            "cuisine": "Café",
            "rating": 4.9,  # highest rating, but it's CLOSED
            "price_for_two": 200,
            "delivery_time_minutes": 10,
            "offers": ["50% off everything"],
            "is_open": False,  # ← the critical edge case
        },
        {
            "id": "t5",
            "name": "South Spice",
            "area": "Lajpat Nagar",  # ← different area, should NOT appear in CP search
            "cuisine": "South Indian",
            "rating": 4.7,
            "price_for_two": 300,
            "delivery_time_minutes": 20,
            "offers": [],
            "is_open": True,
        },
    ]


# ─────────────────────────────────────────────
# SEARCH TESTS
# ─────────────────────────────────────────────

class TestSearchRestaurants:
    """
    Group related tests in a class — pytest still picks them up automatically.
    Grouping makes it easy to see at a glance what scenario you're testing.
    """

    def test_returns_results_for_valid_area(self, sample_restaurants, monkeypatch):
        """
        WHAT: A valid area that has restaurants should return a non-empty list.
        WHY monkeypatch? search_restaurants loads from the real restaurants.json.
        monkeypatch.setattr temporarily replaces the file-loading call with our
        fixture data — so tests never depend on the actual file content.

        HOW monkeypatch works here:
          We replace the `json.load` inside search_restaurants... but it's
          simpler to patch at the function level. See the note below for the
          recommended approach once you see your actual implementation.
        """
        # Simpler approach: call with known data by patching the JSON load.
        # Adjust the patch target to match your actual import path in search_restaurants.py
        import json
        monkeypatch.setattr(
            "tools.search_restaurants.json.load",
            lambda f: sample_restaurants
        )
        results = search_restaurants(area="Connaught Place")
        assert len(results) > 0, "Expected results for a valid area"

    def test_filters_by_area_correctly(self, sample_restaurants, monkeypatch):
        """
        WHAT: Only restaurants in the requested area should be returned.
        WHY: The most basic correctness check — if area filtering is broken,
        every downstream step (compare, recommend) is working on wrong data.
        """
        import json
        monkeypatch.setattr("tools.search_restaurants.json.load", lambda f: sample_restaurants)

        results = search_restaurants(area="Connaught Place")
        areas_in_results = {r["area"] for r in results}

        assert areas_in_results == {"Connaught Place"}, (
            f"Got restaurants from unexpected areas: {areas_in_results}"
        )

    def test_returns_empty_list_for_unknown_area(self, sample_restaurants, monkeypatch):
        """
        WHAT: Searching an area that doesn't exist should return [] not raise an exception.
        WHY: This is the #1 crash risk in your pipeline. If search returns None or
        raises KeyError, compare_restaurants will explode with a confusing error.
        Explicitly asserting [] here protects against silent None returns.
        """
        import json
        monkeypatch.setattr("tools.search_restaurants.json.load", lambda f: sample_restaurants)

        results = search_restaurants(area="Atlantis")
        assert results == [], f"Expected empty list, got: {results}"

    def test_filters_by_cuisine_when_provided(self, sample_restaurants, monkeypatch):
        """
        WHAT: Cuisine filter (optional param) should narrow results when provided.
        WHY: Optional params are a common source of bugs — easy to implement for
        the required case and forget the optional one.
        """
        import json
        monkeypatch.setattr("tools.search_restaurants.json.load", lambda f: sample_restaurants)

        results = search_restaurants(area="Connaught Place", cuisine="Chinese")
        assert len(results) == 1
        assert results[0]["name"] == "Dragon Wok"

    def test_no_cuisine_filter_returns_all_area_results(self, sample_restaurants, monkeypatch):
        """
        WHAT: When cuisine is None/omitted, all restaurants in the area come back.
        WHY: Guards against cuisine=None accidentally filtering everything out.
        """
        import json
        monkeypatch.setattr("tools.search_restaurants.json.load", lambda f: sample_restaurants)

        results = search_restaurants(area="Connaught Place")
        # t1, t2, t3, t4 are all in Connaught Place (t4 is closed but search doesn't filter closed)
        assert len(results) == 4


# ─────────────────────────────────────────────
# COMPARE TESTS
# ─────────────────────────────────────────────

class TestCompareRestaurants:

    def test_returns_sorted_list(self, sample_restaurants):
        """
        WHAT: Output should be a list sorted by score, highest first.
        WHY: The entire value of compare_restaurants is this ordering.
        If it's unsorted, the "best" recommendation is random.
        """
        # Only pass open restaurants (search_restaurants returns all, 
        # compare filters closed — but we test compare in isolation here)
        open_restaurants = [r for r in sample_restaurants if r["is_open"] and r["area"] == "Connaught Place"]
        results = compare_restaurants(open_restaurants)

        scores = [r["score"] for r in results]
        assert scores == sorted(scores, reverse=True), (
            f"Results not sorted by score descending: {scores}"
        )

    def test_excludes_closed_restaurants(self, sample_restaurants):
        """
        WHAT: A restaurant with is_open=False should never appear in results.
        WHY: This is a correctness invariant — 'Closed Café' has the highest
        raw rating (4.9) in our fixture. If closed filtering is broken, it
        would incorrectly win every time. This test catches exactly that bug.
        """
        results = compare_restaurants(sample_restaurants)
        result_names = [r["name"] for r in results]

        assert "Closed Café" not in result_names, (
            "Closed restaurant appeared in comparison results — filtering is broken"
        )

    def test_score_field_is_attached(self, sample_restaurants):
        """
        WHAT: Each result dict should have a 'score' key added by compare_restaurants.
        WHY: The Streamlit UI and recommendation prompt rely on r["score"] existing.
        If it's missing, you get a KeyError deep in the pipeline with no clear message.
        """
        open_restaurants = [r for r in sample_restaurants if r["is_open"]]
        results = compare_restaurants(open_restaurants)

        for r in results:
            assert "score" in r, f"Restaurant '{r['name']}' missing 'score' field"
            assert isinstance(r["score"], (int, float)), (
                f"Score for '{r['name']}' is not a number: {r['score']}"
            )

    def test_empty_input_returns_empty_list(self):
        """
        WHAT: compare_restaurants([]) should return [] without crashing.
        WHY: If search finds nothing, compare receives []. Any crash here
        would hide the real "no restaurants found" message with a confusing error.
        """
        results = compare_restaurants([])
        assert results == [], f"Expected [], got: {results}"

    def test_all_closed_returns_empty_list(self, sample_restaurants):
        """
        WHAT: If every restaurant in the input is closed, output should be [].
        WHY: Edge case — a valid area where every restaurant happens to be closed
        right now. The agent must handle this gracefully.
        """
        all_closed = [dict(r, is_open=False) for r in sample_restaurants]
        results = compare_restaurants(all_closed)
        assert results == [], "All-closed input should produce empty output"

    def test_single_restaurant_still_works(self, sample_restaurants):
        """
        WHAT: A list with just one open restaurant should return a list with one scored result.
        WHY: Normalization math (dividing by range) can produce division-by-zero
        when max == min (i.e., only one restaurant, so all values are equal).
        This is a real, common bug in scoring implementations.
        """
        single = [sample_restaurants[0]]  # Spice Villa, is_open=True
        results = compare_restaurants(single)

        assert len(results) == 1
        assert "score" in results[0]