from google.genai import types
from core.llm_client import client   # reusing the client from Day 3
from tools.demo_tool import get_current_time

# ── Step 1: Describe our tool to Gemini ──────────────────────────────────────
# This is NOT calling the function. It's writing a menu of what functions
# are available so Gemini knows it can request one.

function_declaration = types.FunctionDeclaration(
    name="get_current_time",
    description="Returns the current local time as a formatted string. "
                "Call this whenever the user asks what time it is.",
    parameters_json_schema={
        "type": "object",
        "properties": {}   # no parameters needed for this function
    },
)

tool = types.Tool(function_declarations=[function_declaration])

# ── Step 2: Send the user's message + the tool menu to Gemini ────────────────
user_prompt_content = types.Content(
    role="user",
    parts=[types.Part.from_text(text="What time is it right now?")],
)

print("=" * 60)
print("STEP 1: Sending user message + tool description to Gemini...")
print("=" * 60)

first_response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents=[user_prompt_content],
    config=types.GenerateContentConfig(
        tools=[tool],
        # Disabling automatic function calling so WE handle the round-trip
        # manually. This is the whole point of today's lesson.
        automatic_function_calling=types.AutomaticFunctionCallingConfig(
            disable=True
        ),
    ),
)

# ── Step 3: Read what Gemini is requesting ───────────────────────────────────
# Gemini doesn't give a text answer yet — it asks us to call a function.
# Let's inspect that request.

function_call_part = first_response.function_calls[0]
function_call_content = first_response.candidates[0].content  # we'll need this later

print(f"\nGemini requested tool call: '{function_call_part.name}'")
print(f"With arguments: {function_call_part.args}")

# ── Step 4: WE actually run the Python function ──────────────────────────────
# Note: we're choosing which function to call based on the name Gemini
# requested. In a real agent with many tools, this would be an if/elif
# or a dict lookup.

print("\nSTEP 2: Executing the function ourselves...")
print("-" * 40)

if function_call_part.name == "get_current_time":
    result = get_current_time()   # ← THIS is where the function actually runs
else:
    result = "Error: unknown function requested"

print(f"Function returned: {result}")
print("-" * 40)

# ── Step 5: Send the result back to Gemini ───────────────────────────────────
# We package the result in a special "tool" role message and send the full
# conversation history back (original user message + Gemini's tool request
# + our function result).

function_response_content = types.Content(
    role="tool",      # Must be "tool" — not "user" — for Gemini
    parts=[
        types.Part.from_function_response(
            name=function_call_part.name,
            response={"result": result},
        )
    ],
)

print("\nSTEP 3: Sending function result back to Gemini...")
print("=" * 60)

final_response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents=[
        user_prompt_content,       # original user message
        function_call_content,     # Gemini's tool request
        function_response_content, # our function's result
    ],
    config=types.GenerateContentConfig(tools=[tool]),
)

print("\nGemini's final answer:")
print(final_response.text)