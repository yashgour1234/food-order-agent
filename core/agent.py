# core/agent.py

import json
import time
from core.llm_client import client
from core.state import create_initial_state
from tools.search_restaurants import search_restaurants
from tools.compare_restaurants import compare_restaurants
from tools.recommend import generate_recommendation
from tools.place_order import place_order
from google.genai import types

MAX_ITERATIONS = 10  # Safety cap — prevents infinite loops if LLM gets confused

# ─────────────────────────────────────────────
# TOOL SCHEMAS
# These tell the LLM what tools exist and what arguments they expect.
# The LLM reads these descriptions to decide WHEN and HOW to call each tool.
# ─────────────────────────────────────────────

TOOL_SEARCH = types.FunctionDeclaration(
    name="search_restaurants",
    description=(
        "Search for open restaurants in a given area. "
        "Use this first when the user asks for food options or restaurant recommendations. "
        "Returns a list of restaurant dicts matching the area and optional cuisine filter."
    ),
    parameters_json_schema={
        "type": "object",
        "properties": {
            "area": {
                "type": "string",
                "description": "The Delhi area or neighbourhood to search in, e.g. 'Connaught Place', 'Hauz Khas'",
            },
            "cuisine": {
                "type": "string",
                "description": "Optional cuisine filter, e.g. 'North Indian', 'Chinese'. Omit to return all cuisines.",
            },
        },
        "required": ["area"],
    },
)

TOOL_COMPARE = types.FunctionDeclaration(
    name="compare_restaurants",
    description=(
        "Compare and rank a list of restaurants by a weighted score combining "
        "rating, price, delivery time, and offers. Call this AFTER search_restaurants "
        "to rank the results. Pass the full list returned by search_restaurants."
    ),
    parameters_json_schema={
        "type": "object",
        "properties": {
            "restaurants": {
                "type": "array",
                "description": "List of restaurant dicts as returned by search_restaurants.",
                "items": {"type": "object"},
            }
        },
        "required": ["restaurants"],
    },
)

TOOLS = types.Tool(function_declarations=[TOOL_SEARCH, TOOL_COMPARE])


# ─────────────────────────────────────────────
# TOOL DISPATCHER
# Maps tool name strings → actual Python functions.
# The LLM returns a name string; this is where we resolve it to real code.
# ─────────────────────────────────────────────

def dispatch_tool(name: str, args: dict) -> str:
    """
    Executes the named tool with the given arguments.
    Returns a JSON string (the LLM expects tool results as text/JSON).
    """
    print(f"\n🔧 Tool called: {name}")
    print(f"   Arguments : {json.dumps(args, ensure_ascii=False)}")

    if name == "search_restaurants":
        result = search_restaurants(
            area=args.get("area", ""),
            cuisine=args.get("cuisine"),
        )

    elif name == "compare_restaurants":
        restaurants = args.get("restaurants", [])

        # WHY this guard: the LLM sometimes returns restaurant lists as a
        # JSON string instead of a Python list (it's a text predictor, not
        # a type-safe system). We handle both cases defensively.
        if isinstance(restaurants, str):
            try:
                restaurants = json.loads(restaurants)
            except json.JSONDecodeError:
                restaurants = []

        result = compare_restaurants(restaurants)

    else:
        result = {"error": f"Unknown tool: {name}"}

    result_str = json.dumps(result, ensure_ascii=False)
    print(f"   Result    : {result_str[:200]}{'...' if len(result_str) > 200 else ''}")
    return result_str


# ─────────────────────────────────────────────
# APPROVAL GATE
# The HITL checkpoint. Physically blocks place_order from running
# without explicit human confirmation.
# ─────────────────────────────────────────────

def approval_gate(recommendation: str, ranked_restaurants: list, state: dict) -> dict:
    """
    Shows the human the comparison table + recommendation, then waits for yes/no.
    Updates and returns state with approved=True/False.

    WHY a separate function: keeps the gate logic isolated and testable.
    You can unit-test this without running the full agent loop.
    """
    print("\n" + "═" * 60)
    print("  🍽️  FOOD ORDER AGENT — APPROVAL REQUIRED")
    print("═" * 60)

    # Show comparison table for top 3
    print("\n📊 Top Restaurants (ranked by score):\n")
    for i, r in enumerate(ranked_restaurants[:3], 1):
        offers = ", ".join(r.get("offers", [])) or "No offers"
        print(f"  {i}. {r['name']} ({r['area']})")
        print(f"     Cuisine      : {r.get('cuisine', 'N/A')}")
        print(f"     Rating       : {r.get('rating', 'N/A')} ⭐")
        print(f"     Price for 2  : ₹{r.get('price_for_two', 'N/A')}")
        print(f"     Delivery     : {r.get('delivery_time_minutes', 'N/A')} min")
        print(f"     Offers       : {offers}")
        score = r.get('score')
        if score is not None:
            print(f"     Score        : {score:.3f}")
        print()

    print("💡 Recommendation:\n")
    print(f"   {recommendation}\n")
    print("═" * 60)

    # Collect human input — normalize to lowercase, handle edge cases
    while True:
        raw = input("  ➡️  Approve this order? (yes/no): ").strip().lower()

        if raw in ("yes", "y"):
            state["approved"] = True
            print("\n✅ Order approved by user.\n")
            break
        elif raw in ("no", "n"):
            state["approved"] = False
            print("\n❌ Order rejected by user.\n")
            break
        else:
            # WHY loop: don't crash on "maybe" or accidental Enter;
            # keep asking until we get a definitive answer.
            print("   Please type 'yes' or 'no'.")

    return state


# ─────────────────────────────────────────────
# MAIN AGENT LOOP
# ─────────────────────────────────────────────

def run_agent(user_request: str, state: dict = None) -> dict:
    """
    Runs the full ReAct agent loop for a food ordering request.

    Flow:
      1. LLM decides to call search_restaurants
      2. LLM decides to call compare_restaurants on the results
      3. We call generate_recommendation on the ranked list (not LLM-driven tool call)
      4. Approval gate pauses for human input
      5. If approved → place_order; if rejected → stop cleanly

    Returns the final state dict.
    """
    if state is None:
        state = create_initial_state()

    print(f"\n🚀 Agent started")
    print(f"   Request: {user_request}\n")

    # Build conversation history — start with the user's request
    conversation: list[types.Content] = [
        types.Content(
            role="user",
            parts=[types.Part.from_text(text=user_request)],
        )
    ]

    system_prompt = (
        "You are a food ordering assistant for Delhi, India. "
        "When the user asks for restaurant recommendations, ALWAYS: "
        "1. Call search_restaurants to find options in their area. "
        "2. Call compare_restaurants on the results to rank them. "
        "After both tool calls complete, say 'DONE' and nothing else — "
        "the recommendation will be generated separately."
    )

    ranked_restaurants = []
    iterations = 0

    # ── ReAct Loop ──
    while iterations < MAX_ITERATIONS:
        iterations += 1
        print(f"── Iteration {iterations} ──")

        # Retry logic for transient Gemini 503 errors (from Day 8)
        for attempt in range(3):
            try:
                response = client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=conversation,
                    config=types.GenerateContentConfig(
                        system_instruction=system_prompt,
                        tools=[TOOLS],
                        automatic_function_calling=types.AutomaticFunctionCallingConfig(
                            disable=True
                        ),
                        temperature=0.2,
                    ),
                )
                break  # success — exit retry loop
            except Exception as e:
                if attempt == 2:
                    raise
                wait = 2 ** attempt
                print(f"   ⚠️  API error ({e}), retrying in {wait}s...")
                time.sleep(wait)

        candidate = response.candidates[0]
        model_content = candidate.content  # may be None in transitional states

        # Check if the LLM wants to call a tool
        function_calls = response.function_calls  # list or None

        if function_calls:
            # Guard: model_content can be None on some Gemini responses.
            # Only append to history if it's a real Content object.
            if model_content is not None:
                conversation.append(model_content)

            # Execute each requested tool and collect responses
            tool_response_parts = []
            for fc in function_calls:
                tool_result_str = dispatch_tool(fc.name, dict(fc.args))

                # If this was compare_restaurants, capture the ranked list
                # so we can pass it to generate_recommendation and place_order
                if fc.name == "compare_restaurants":
                    try:
                        ranked_restaurants = json.loads(tool_result_str)
                        state["comparison_result"] = ranked_restaurants
                    except json.JSONDecodeError:
                        ranked_restaurants = []

                tool_response_parts.append(
                    types.Part.from_function_response(
                        name=fc.name,
                        response={"result": tool_result_str},
                    )
                )

            # Append tool results back into conversation history
            conversation.append(
                types.Content(role="tool", parts=tool_response_parts)
            )

        else:
            # No tool call requested. But Gemini can return function_calls=[]
            # AND candidate.content=None during tool-use transitions — this is
            # NOT a final answer, just an empty transitional response. Guard it.
            if candidate.content is None:
                print(f"   ⚠️  Empty response (no tool call, no content). Continuing...")
                continue

            # Content exists — extract text parts
            final_text = ""
            for part in candidate.content.parts:
                if hasattr(part, "text") and part.text:
                    final_text += part.text

            if not final_text.strip():
                # Content object present but no actual text — also transitional
                print(f"   ⚠️  No text in response parts. Continuing...")
                continue

            # We have real text — this is the LLM's final answer, exit the loop
            print(f"\n   LLM final text: {final_text[:100]}")
            state["raw_answer"] = final_text
            break

    else:
        # Exited loop via iteration limit, not via break
        print(f"⚠️  Agent hit MAX_ITERATIONS ({MAX_ITERATIONS}). Stopping.")
        state["raw_answer"] = "Agent could not complete the request within iteration limit."
        return state

    # ── Post-loop: Recommendation + Approval + Order ──

    if not ranked_restaurants:
        print("\n⚠️  No restaurants were ranked. Cannot proceed.")
        state["raw_answer"] = "No restaurants found matching your request."
        return state

    # Step 1: Generate LLM recommendation (grounded in scored data)
    print("\n💬 Generating recommendation...")
    recommendation_text = generate_recommendation(ranked_restaurants)
    state["recommendation"] = recommendation_text

    # Step 2: Human approval gate
    state = approval_gate(recommendation_text, ranked_restaurants, state)

    # Step 3: Place order — ONLY if approved
    if state["approved"]:
        top_restaurant = ranked_restaurants[0]
        order_result = place_order(top_restaurant, state)
        state["order_placed"] = order_result["success"]
        state["order_id"] = order_result.get("order_id")
    else:
        print("Order was not placed. Feel free to run again with different preferences!")
        state["order_placed"] = False

    return state