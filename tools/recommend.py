# tools/recommend.py

import os
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


def generate_recommendation(ranked_restaurants: list) -> str:
    """
    Takes the top-ranked restaurants (already scored by compare_restaurants),
    and asks the LLM to explain WHY the top pick is the best choice.
    
    The LLM is given only the data we pass — it cannot invent new facts.
    Returns a plain-English recommendation string.
    """

    if not ranked_restaurants:
        return "No restaurants found to recommend."

    # Take the top 3 (or fewer if less exist)
    top_picks = ranked_restaurants[:3]

    # --- Build a tight, grounded prompt ---
    # We format the restaurant data ourselves so the LLM sees clean, structured text.
    # This reduces hallucination risk compared to dumping raw JSON at it.
    restaurant_summaries = []
    for i, r in enumerate(top_picks):
        rank = i + 1
        offers_text = ", ".join(r.get("offers", [])) if r.get("offers") else "No current offers"
        summary = (
            f"Rank #{rank}: {r['name']}\n"
            f"  - Score: {r.get('score', 'N/A'):.2f}\n"
            f"  - Cuisine: {r['cuisine']}\n"
            f"  - Rating: {r['rating']}/5\n"
            f"  - Price for two: ₹{r['price_for_two']}\n"
            f"  - Delivery time: {r['delivery_time_minutes']} minutes\n"
            f"  - Offers: {offers_text}"
        )
        restaurant_summaries.append(summary)

    restaurants_block = "\n\n".join(restaurant_summaries)

    system_prompt = """You are a food-ordering assistant helping a user pick the best restaurant.
You will be given a ranked list of restaurants with their scores and details.
The rankings have already been computed by a scoring algorithm — do NOT re-rank or recalculate.
Your ONLY job is to write a clear, friendly recommendation explaining why Rank #1 is the top pick.

STRICT RULES:
- Only reference facts explicitly provided in the data below. Do NOT invent prices, ratings, offers, or delivery times.
- Do NOT mention any restaurant not in the provided list.
- Keep your response to 3-4 sentences maximum.
- Be specific: mention actual numbers (rating, price, delivery time) from the data to justify the choice.
- End with one sentence acknowledging the runner-up as a solid alternative."""

    user_message = f"""Here are the top-ranked restaurants based on our scoring algorithm:

{restaurants_block}

Please write a recommendation explaining why Rank #1 is the best choice for the user today."""

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=user_message,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=0.2,   # Low temperature = consistent, factual explanation (not creative)
        ),
    )

    return response.text