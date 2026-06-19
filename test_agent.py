from core.state import create_initial_state
from core.agent import run_agent

# Create a fresh state
state = create_initial_state()

# Set the user's location in state
state["user_location"] = "Connaught Place"

# Run the agent
updated_state = run_agent(
    user_request="Find me a good restaurant for delivery in Connaught Place",
    state=state
)

# Show what ended up in state after the agent ran
print("\n--- Final State ---")
print(f"Recommendation stored: {updated_state['recommendation'] is not None}")
print(f"Order placed: {updated_state['order_placed']}")