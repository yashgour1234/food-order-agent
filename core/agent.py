# core/agent.py

import json
from google import genai
from google.genai import types
from core.state import create_initial_state
from tools.search_restaurants import search_restaurants
from tools.compare_restaurants import compare_restaurants
from tools.recommend import generate_recommendation

import os
from dotenv import load_dotenv

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

MAX_ITERATIONS = 10

# ─────────────────────────────────────────────
# TOOL SCHEMAS
# ─────────────────────────────────────────────

search_tool = types.FunctionDeclaration(
    name="search_restaurants",
    description="Search for open restaurants in a given area, optionally filtered by cuisine type.",
    parameters_json_schema={
        "type": "object",
        "properties": {
            "area": {
                "type": "string",
                "description": "The area or neighbourhood to search in, e.g. 'Connaught Place'"
            },
            "cuisine": {
                "type": "string",
                "description": "Optional cuisine filter, e.g. 'North Indian', 'Chinese'"
            }
        },
        "required": ["area"]
    }
)

# compare_tool declaration kept for reference but NOT given to the LLM
compare_tool = types.FunctionDeclaration(
    name="compare_restaurants",
    description="Score and rank a list of restaurants based on rating, price, delivery time, and offers.",
    parameters_json_schema={
        "type": "object",
        "properties": {
            "restaurants": {
                "type": "array",
                "items": {"type": "object"},
                "description": "List of restaurant dicts to compare"
            }
        },
        "required": ["restaurants"]
    }
)

# CHANGE 1: only search_tool goes to the LLM
tools = types.Tool(function_declarations=[search_tool])


# ─────────────────────────────────────────────
# TOOL DISPATCHER
# ─────────────────────────────────────────────

def dispatch_tool(name: str, args: dict) -> str:
    if name == "search_restaurants":
        result = search_restaurants(**args)
        return json.dumps(result)
    elif name == "compare_restaurants":
        restaurants = args.get("restaurants", [])
        if isinstance(restaurants, str):
            restaurants = json.loads(restaurants)
        result = compare_restaurants(restaurants)
        return json.dumps(result)
    else:
        return json.dumps({"error": f"Unknown tool: {name}"})


# ─────────────────────────────────────────────
# APPROVAL GATE
# ─────────────────────────────────────────────

def approval_gate(state: dict) -> dict:
    print("\n" + "=" * 60)
    print("🍽️  FOOD AGENT RECOMMENDATION")
    print("=" * 60)

    comparison = state.get("comparison_result", [])
    if comparison:
        print("\n📊 TOP RESTAURANTS (ranked by score):\n")
        print(f"  {'Rank':<5} {'Name':<25} {'Rating':<8} {'Price/2':<10} {'Delivery':<12} {'Score':<8}")
        print(f"  {'-'*5} {'-'*25} {'-'*8} {'-'*10} {'-'*12} {'-'*8}")
        for i, r in enumerate(comparison[:3], 1):
            score = r.get("score", 0)
            print(
                f"  {i:<5} "
                f"{r.get('name', 'N/A'):<25} "
                f"{r.get('rating', 'N/A'):<8} "
                f"₹{r.get('price_for_two', 'N/A'):<9} "
                f"{r.get('delivery_time_minutes', 'N/A')} min{'':<6} "
                f"{score:.3f}"
            )
    else:
        print("\n(No comparison data available)")

    recommendation = state.get("recommendation", {})
    rec_text = recommendation.get("recommendation", "") if isinstance(recommendation, dict) else str(recommendation)

    print(f"\n🤖 AGENT RECOMMENDATION:\n")
    print(f"  {rec_text}")
    print("\n" + "=" * 60)

    while True:
        raw = input("\n✅  Approve this order? (yes/no): ").strip().lower()
        if raw in ("yes", "y"):
            state["approved"] = True
            print("\n✔  Order approved. Proceeding...")
            break
        elif raw in ("no", "n"):
            state["approved"] = False
            print("\n✘  Order rejected. No order will be placed.")
            break
        else:
            print(f"  ⚠️  Please type 'yes' or 'no' (you typed: '{raw}')")

    return state


# ─────────────────────────────────────────────
# STUB ORDER STEP
# ─────────────────────────────────────────────

# CHANGE 3: fixed — added order_placed flag and return statement
def _stub_place_order(state: dict) -> dict:
    comparison = state.get("comparison_result") or []
    top = comparison[0] if comparison else {}
    name = top.get("name", "Unknown")
    print(f"\n🎉  [STUB] Order would be placed at: {name}")
    print("    (Real implementation coming in Day 11)")
    state["order_placed"] = True
    return state


# ─────────────────────────────────────────────
# MAIN AGENT LOOP
# ─────────────────────────────────────────────

def run_agent(user_request: str) -> dict:
    state = create_initial_state()
    conversation = []

    system_prompt = (
        "You are a food ordering assistant for Delhi. "
        "You have one tool: search_restaurants. "
        "Call it to find restaurants in the requested area, then summarise what you found for the user."
    )

    conversation.append(
        types.Content(role="user", parts=[types.Part.from_text(text=user_request)])
    )

    print(f"\n🔍 Agent starting for: '{user_request}'")

    for iteration in range(MAX_ITERATIONS):
        print(f"\n[Iteration {iteration + 1}/{MAX_ITERATIONS}]")

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=conversation,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                tools=[tools],
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
                temperature=0.2,
            ),
        )

        if response.function_calls:
            conversation.append(response.candidates[0].content)

            tool_response_parts = []
            for fc in response.function_calls:
                print(f"  → Tool call: {fc.name}({json.dumps(fc.args, ensure_ascii=False)[:80]}...)")
                result_str = dispatch_tool(fc.name, fc.args)
                print(f"  ← Result: {result_str[:120]}...")

                # CHANGE 2: auto-compare runs here in Python, not via LLM tool call
                if fc.name == "search_restaurants":
                    found = json.loads(result_str)
                    state["restaurants_found"] = found

                    if found:
                        print(f"  → Auto-running compare_restaurants on {len(found)} results...")
                        ranked = compare_restaurants(found)
                        state["comparison_result"] = ranked
                        top_names = [r["name"] for r in ranked[:3]]
                        print(f"  ← Ranked. Top 3: {top_names}")

                        result_str = (
                            f"Found {len(found)} restaurants. After scoring, top picks are: "
                            + ", ".join(
                                f"{r['name']} (score: {r.get('score', 0):.3f})"
                                for r in ranked[:3]
                            )
                            + ". Please summarise this for the user."
                        )
                    else:
                        state["comparison_result"] = []
                        result_str = "No open restaurants found in that area."

                tool_response_parts.append(
                    types.Part.from_function_response(
                        name=fc.name,
                        response={"result": result_str}
                    )
                )

            conversation.append(
                types.Content(role="tool", parts=tool_response_parts)
            )

        else:
            final_text = response.text

            # CHANGE 4: guard against None/empty response
            if not final_text:
                print("  ⚠️  Empty response — nudging model to summarise...")
                conversation.append(
                    types.Content(
                        role="user",
                        parts=[types.Part.from_text(
                            text="Please summarise the restaurant comparison results for the user."
                        )]
                    )
                )
                continue

            print(f"\n💬 Agent final answer:\n{final_text}")

            if state.get("comparison_result"):
                print("\n⚙️  Generating recommendation...")
                state["recommendation"] = generate_recommendation(state["comparison_result"])

            state = approval_gate(state)

            if state["approved"]:
                state = _stub_place_order(state)
            else:
                print("\n  Agent stopped. No order placed.")

            return state

    print(f"\n⚠️  Max iterations ({MAX_ITERATIONS}) reached without a final answer.")
    return state