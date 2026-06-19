import os
from dotenv import load_dotenv
from google import genai
from google.genai import types

from tools.search_restaurants import search_restaurants
from tools.compare_restaurants import compare_restaurants

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# ─────────────────────────────────────────────
# TOOL DEFINITIONS (what we describe to the LLM)
# ─────────────────────────────────────────────

TOOL_DEFINITIONS = types.Tool(
    function_declarations=[
        types.FunctionDeclaration(
            name="search_restaurants",
            description=(
                "Search for open restaurants in a given area. "
                "Call this first when the user asks for restaurant recommendations. "
                "Returns a list of restaurant dicts with fields: id, name, area, cuisine, "
                "rating, price_for_two, delivery_time_minutes, offers, is_open."
            ),
            parameters_json_schema={
                "type": "object",
                "properties": {
                    "area": {
                        "type": "string",
                        "description": "The area or neighbourhood to search in, e.g. 'Connaught Place'",
                    },
                    "cuisine": {
                        "type": "string",
                        "description": "Optional cuisine filter, e.g. 'North Indian'. Omit to return all cuisines.",
                    },
                },
                "required": ["area"],
            },
        ),
        types.FunctionDeclaration(
            name="compare_restaurants",
            description=(
                "Score and rank a list of restaurants using a weighted formula that balances "
                "rating, price, delivery time, and offers. Call this after search_restaurants "
                "to rank the results. Returns the same list sorted best-first, with a 'score' "
                "field added to each restaurant."
            ),
            parameters_json_schema={
                "type": "object",
                "properties": {
                    "restaurants": {
                        "type": "array",
                        "description": "The list of restaurant dicts returned by search_restaurants.",
                        "items": {"type": "object"},
                    }
                },
                "required": ["restaurants"],
            },
        ),
    ]
)

# ─────────────────────────────────────────────
# TOOL EXECUTOR (maps name → actual Python function)
# ─────────────────────────────────────────────

def execute_tool(name: str, args: dict) -> str:
    """
    Runs the actual Python function for a tool call the LLM requested.
    Always returns a string — the LLM can only read text.
    """
    print(f"\n  [Tool called] → {name}({args})")

    if name == "search_restaurants":
        result = search_restaurants(**args)
        print(f"  [Tool result] → {len(result)} restaurants found")
        return str(result)

    elif name == "compare_restaurants":
        result = compare_restaurants(args["restaurants"])
        print(f"  [Tool result] → Ranked {len(result)} restaurants")
        return str(result)

    else:
        return f"Error: unknown tool '{name}'"


# ─────────────────────────────────────────────
# THE AGENT LOOP
# ─────────────────────────────────────────────

def run_agent(user_request: str, state: dict) -> dict:
    """
    The ReAct agent loop.

    Sends the user request to the LLM with tool descriptions.
    If the LLM requests a tool call, we execute it and send the result back.
    We repeat until the LLM returns a plain text answer (no more tool calls).

    Returns the updated state dict.
    """
    MAX_ITERATIONS = 10

    system_prompt = (
        "You are a helpful food-ordering assistant. "
        "When a user asks for restaurant recommendations, always search first, "
        "then compare the results, then give a clear final recommendation. "
        "Use the available tools in the right order. "
        "Only give a final text answer once you have searched AND compared."
    )

    # conversation history — this is the list we keep appending to
    conversation: list[types.Content] = [
        types.Content(
            role="user",
            parts=[types.Part.from_text(text=user_request)]
        )
    ]

    print(f"\n{'='*60}")
    print(f"Agent started. Request: '{user_request}'")
    print(f"{'='*60}")

    for iteration in range(1, MAX_ITERATIONS + 1):
        print(f"\n--- Iteration {iteration} ---")

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=conversation,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                tools=[TOOL_DEFINITIONS],
                automatic_function_calling=types.AutomaticFunctionCallingConfig(
                    disable=True   # we handle the loop ourselves
                ),
            ),
        )

        # Check what the model returned
        # Case 1: The model wants to call a tool
        if response.function_calls:
            # Append the model's response (its tool request) to the conversation
            conversation.append(response.candidates[0].content)

            # Execute every tool the model requested (usually one at a time)
            tool_response_parts = []
            for fn_call in response.function_calls:
                tool_result = execute_tool(fn_call.name, dict(fn_call.args))

                tool_response_parts.append(
                    types.Part.from_function_response(
                        name=fn_call.name,
                        response={"result": tool_result},
                    )
                )

            # Append all tool results back to the conversation as a single "tool" message
            conversation.append(
                types.Content(role="tool", parts=tool_response_parts)
            )

        # Case 2: The model returned a plain text final answer — loop ends
        elif response.text:
            print(f"\n{'='*60}")
            print("Agent final answer:")
            print(response.text)
            print(f"{'='*60}")

            state["recommendation"] = response.text
            return state

        # Case 3: Unexpected — neither tool call nor text (shouldn't happen normally)
        else:
            print("  [Warning] Model returned neither tool call nor text. Stopping.")
            break

    # If we exit the loop without a final answer, we hit the iteration limit
    print(f"\n[Agent stopped] Hit the {MAX_ITERATIONS}-iteration limit without a final answer.")
    state["recommendation"] = "I wasn't able to complete the search in time. Please try again."
    return state