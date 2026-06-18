from core.state import create_initial_state

# Create the initial state and print it
state = create_initial_state()
print(state)

# Simulate updating one field, the way a tool would later
state["user_location"] = "Delhi"
print(state)