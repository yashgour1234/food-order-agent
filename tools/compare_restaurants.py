# tools/compare_restaurants.py

def compare_restaurants(restaurant_list):
    """
    Takes a list of restaurant dicts (from search_restaurants),
    filters out closed ones, scores each on a 0-1 scale using
    normalized weighted criteria, and returns them sorted best-first.

    Returns a list of the same dicts with a 'score' field added.
    """

    # ─── STEP 1: Filter to only open restaurants ───────────────────────
    # Why here, not in search? Because search gives you "restaurants that
    # match your request." Filtering closed ones is a comparison concern —
    # we can't recommend a place you can't order from right now.
    open_restaurants = [r for r in restaurant_list if r.get("is_open", False)]

    # Edge case: if nothing is open, return an empty list cleanly.
    # This prevents division-by-zero later and gives the caller a clear signal.
    if not open_restaurants:
        return []

    # ─── STEP 2: Extract raw values for each metric ────────────────────
    # We pull out the three numeric metrics we're scoring on.
    # .get() with a default handles missing fields gracefully (defensive coding).
    ratings = [r.get("rating", 0) for r in open_restaurants]
    prices = [r.get("price_for_two", 0) for r in open_restaurants]
    delivery_times = [r.get("delivery_time_minutes", 0) for r in open_restaurants]

    # ─── STEP 3: Find min/max for normalization ─────────────────────────
    # We need these to compute the 0-1 range for each metric.
    min_rating, max_rating = min(ratings), max(ratings)
    min_price, max_price = min(prices), max(prices)
    min_time, max_time = min(delivery_times), max(delivery_times)

    # ─── STEP 4: Helper — normalize a single value ──────────────────────
    # This tiny function encapsulates the normalization formula so we
    # don't repeat math everywhere. The `invert` flag handles the
    # "lower is better" case (price, delivery time).
    def normalize(value, min_val, max_val, invert=False):
        # If all restaurants have the same value for this metric
        # (e.g., all rated 4.0), the range is 0 — avoid division by zero,
        # and just give everyone a neutral 0.5 for that metric.
        if max_val == min_val:
            return 0.5
        score = (value - min_val) / (max_val - min_val)
        return (1 - score) if invert else score

    # ─── STEP 5: Parse offers into a discount percentage ─────────────────
    # Offers are stored as strings like "20% off above ₹300".
    # We extract the percentage number so it becomes comparable.
    # If no offer, the discount is 0.
    def parse_offer_discount(offers):
        if not offers:
            return 0
        for offer in offers:
            # Look for a number followed by '%' in the offer string
            import re
            match = re.search(r'(\d+)%', offer)
            if match:
                return int(match.group(1))  # Return the first % found
        return 0

    # ─── STEP 6: Score each restaurant ──────────────────────────────────
    # Weights: rating (40%), offers (25%), delivery speed (20%), price (15%)
    # These are product decisions. Change them to reflect what your users value.
    WEIGHT_RATING = 0.40
    WEIGHT_OFFER = 0.25
    WEIGHT_DELIVERY = 0.20
    WEIGHT_PRICE = 0.15

    # Pre-compute all discount values so we can normalize them too
    discounts = [parse_offer_discount(r.get("offers", [])) for r in open_restaurants]
    min_discount, max_discount = min(discounts), max(discounts)

    scored = []
    for i, restaurant in enumerate(open_restaurants):
        # Each metric is normalized to 0-1, then multiplied by its weight.
        # Higher score = better choice.

        rating_score = normalize(ratings[i], min_rating, max_rating)
        # invert=True because LOWER price is BETTER
        price_score = normalize(prices[i], min_price, max_price, invert=True)
        # invert=True because LOWER delivery time is BETTER (faster = better)
        delivery_score = normalize(delivery_times[i], min_time, max_time, invert=True)
        offer_score = normalize(discounts[i], min_discount, max_discount)

        # Weighted sum: this is your restaurant's final score
        final_score = (
            WEIGHT_RATING * rating_score +
            WEIGHT_OFFER * offer_score +
            WEIGHT_DELIVERY * delivery_score +
            WEIGHT_PRICE * price_score
        )

        # Add score to a copy of the restaurant dict.
        # We use a copy so we don't mutate the original list —
        # a good habit that prevents subtle bugs in multi-step pipelines.
        restaurant_with_score = dict(restaurant)
        restaurant_with_score["score"] = round(final_score, 4)

        # Also store the individual component scores — useful for debugging
        # and for the LLM's explanation on Day 8 (it can say "scored highest on offers")
        restaurant_with_score["score_breakdown"] = {
            "rating": round(rating_score, 3),
            "offer": round(offer_score, 3),
            "delivery": round(delivery_score, 3),
            "price": round(price_score, 3),
        }

        scored.append(restaurant_with_score)

    # ─── STEP 7: Sort by score, highest first ───────────────────────────
    # reverse=True because we want the BEST (highest score) at index 0.
    scored.sort(key=lambda r: r["score"], reverse=True)

    return scored