# core/agent.py

import os
import json
from dotenv import load_dotenv
from google import genai
from google.genai import types

from tools.search_restaurants import search_restaurants
from tools.compare_restaurants import compare_restaurants
from tools.recommend import generate_recommendation  # NEW import

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

MAX_ITERATIONS = 10

# --- Tool schemas (unchanged from Day 7) ---
search_tool_declaration = types.FunctionDeclaration(
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
                "description": "Optional cuisine type to filter by, e.g. 'North Indian', 'Chinese'"
            }
        },
        "required": ["area"]
    }
)

compare_tool_declaration = types.FunctionDeclaration(
    name="compare_restaurants",
    description="Compare and rank a list of restaurants by a weighted score combining rating, price, delivery time, and offers.",
    parameters_json_schema={
        "type": "object",
        "properties": {
            "restaurant_list": {
                "type": "string",
                "description": "A JSON string containing the list of restaurant dicts to compare."
            }
        },
        "required": ["restaurant_list"]
    }
)

gemini_tools = types.Tool(
    function_declarations=[search_tool_declaration, compare_tool_declaration]
)


def run_agent(user_request: str) -> dict:
    """
    Runs the ReAct agent loop for the given user request.
    
    Returns a dict with:
      - 'ranked_restaurants': the scored + sorted list from compare_restaurants
      - 'recommendation': the LLM's plain-English explanation (NEW in Day 8)
      - 'raw_answer': the LLM's final text from the tool loop
    """

    system_prompt = """You are a helpful food-ordering assistant for Delhi, India.

When the user asks for restaurant recommendations:
1. ALWAYS call search_restaurants first to find available options.
2. ALWAYS call compare_restaurants next with the results to rank them.
3. After both tools have run, give a brief summary of what you found.

You have access to restaurants in these areas: Connaught Place, Lajpat Nagar, Karol Bagh.
Never guess restaurant details — always use the tools to get real data."""

    conversation_history = [
        types.Content(
            role="user",
            parts=[types.Part.from_text(text=user_request)]
        )
    ]

    ranked_restaurants = []
    iteration = 0

    print(f"\n{'='*60}")
    print(f"AGENT STARTING | Request: {user_request}")
    print(f"{'='*60}")

    while iteration < MAX_ITERATIONS:
        iteration += 1
        print(f"\n--- Iteration {iteration} ---")

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=conversation_history,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                tools=[gemini_tools],
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
                temperature=0.2,
            ),
        )

        # Check if the model wants to call a tool
        if response.function_calls:
            model_turn_content = response.candidates[0].content
            conversation_history.append(model_turn_content)

            tool_response_parts = []

            for function_call in response.function_calls:
                tool_name = function_call.name
                tool_args = dict(function_call.args)
                print(f"  [TOOL CALL] {tool_name}({tool_args})")

                # --- Execute the right tool ---
                if tool_name == "search_restaurants":
                    result = search_restaurants(
                        area=tool_args.get("area", ""),
                        cuisine=tool_args.get("cuisine", None)
                    )
                    print(f"  [TOOL RESULT] Found {len(result)} restaurants")

                elif tool_name == "compare_restaurants":
                    # Defensive: handle if Gemini passes a JSON string instead of a list
                    raw = tool_args.get("restaurant_list", "[]")
                    if isinstance(raw, str):
                        try:
                            restaurant_list = json.loads(raw)
                        except json.JSONDecodeError:
                            restaurant_list = []
                    else:
                        restaurant_list = raw

                    result = compare_restaurants(restaurant_list)
                    ranked_restaurants = result  # Save for recommendation step
                    print(f"  [TOOL RESULT] Ranked {len(result)} restaurants. Top: {result[0]['name'] if result else 'none'}")

                else:
                    result = {"error": f"Unknown tool: {tool_name}"}
                    print(f"  [TOOL ERROR] {result}")

                tool_response_parts.append(
                    types.Part.from_function_response(
                        name=tool_name,
                        response={"result": json.dumps(result, ensure_ascii=False)}
                    )
                )

            # Append all tool results as a single 'tool' role message
            conversation_history.append(
                types.Content(role="tool", parts=tool_response_parts)
            )

        else:
            # No tool call = LLM gave a final text answer → loop ends
            final_text = response.text
            print(f"\n[AGENT FINAL TEXT]\n{final_text}")

            # --- Day 8 addition: generate grounded recommendation ---
            recommendation = ""
            if ranked_restaurants:
                print("\n[GENERATING RECOMMENDATION...]")
                recommendation = generate_recommendation(ranked_restaurants)
                print(f"\n[RECOMMENDATION]\n{recommendation}")
            else:
                recommendation = "No restaurants were ranked — cannot generate a recommendation."
                print(f"\n[RECOMMENDATION] {recommendation}")

            print(f"\n{'='*60}")
            print("AGENT FINISHED")
            print(f"{'='*60}\n")

            return {
                "ranked_restaurants": ranked_restaurants,
                "recommendation": recommendation,
                "raw_answer": final_text,
            }

    # Safety: max iterations reached
    print("[WARNING] Max iterations reached without a final answer.")
    return {
        "ranked_restaurants": ranked_restaurants,
        "recommendation": "Agent hit iteration limit — no recommendation generated.",
        "raw_answer": "",
    }