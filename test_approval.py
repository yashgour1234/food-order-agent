# test_approval.py
# Run this to test BOTH paths: approve and reject.
# Expected:
#   - "yes" → prints stub order confirmation, state["order_placed"] == True
#   - "no"  → stops cleanly,               state["order_placed"] == False

from core.agent import run_agent

if __name__ == "__main__":
    print("=" * 60)
    print("DAY 10 — Approval Gate Test")
    print("=" * 60)
    print("When prompted, try typing:")
    print("  'yes' → should reach the stub order step")
    print("  'no'  → should stop cleanly")
    print("  'maybe' → should re-prompt (input validation)")
    print("=" * 60 + "\n")

    final_state = run_agent(
        "Find me a good restaurant for delivery in Connaught Place"
    )

    print("\n── Final State ──")
    print(f"  approved:     {final_state['approved']}")
    print(f"  order_placed: {final_state['order_placed']}")

    # Quick self-check
    if final_state["approved"] and not final_state["order_placed"]:
        print("\n❌ BUG: Approved but order not placed — check _stub_place_order wiring")
    elif not final_state["approved"] and final_state["order_placed"]:
        print("\n❌ BUG: Order placed without approval — CRITICAL, fix immediately")
    else:
        print("\n✅ Gate behaviour is consistent with approval state")