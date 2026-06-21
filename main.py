# main.py

from core.state import create_initial_state
from core.agent import run_agent


def main():
    print("\n" + "═" * 60)
    print("  🍽️  Delhi Food Order Agent")
    print("═" * 60)
    print("  I'll search restaurants, compare them, and recommend")
    print("  the best option — but you approve before I order.\n")

    # Collect user preferences
    area = input("  📍 Your area in Delhi (e.g. Connaught Place): ").strip()
    if not area:
        area = "Connaught Place"  # sensible default for testing

    cuisine = input("  🍛 Cuisine preference (press Enter to skip): ").strip()

    # Build natural language request for the agent
    if cuisine:
        user_request = (
            f"Find me a good {cuisine} restaurant for delivery in {area}, Delhi. "
            f"Compare them and recommend the best option."
        )
    else:
        user_request = (
            f"Find me a good restaurant for delivery in {area}, Delhi. "
            f"Compare all options and recommend the best one."
        )

    # Create fresh state and run the full agent pipeline
    state = create_initial_state()
    final_state = run_agent(user_request, state)

    # Summary
    print("\n" + "═" * 60)
    print("  Session Summary")
    print("═" * 60)
    print(f"  Order placed : {final_state.get('order_placed', False)}")
    if final_state.get("order_id"):
        print(f"  Order ID     : {final_state['order_id']}")
    print("═" * 60 + "\n")


if __name__ == "__main__":
    main()