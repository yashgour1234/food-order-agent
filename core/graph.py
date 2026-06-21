# core/graph.py
"""
Day 12: LangGraph state machine version of the food ordering agent.

This replaces the manual while-loop in agent_manual.py with a proper
graph of named nodes and edges. The key upgrade: interrupt() replaces
input() for the human approval step, making it resumable by Streamlit.
"""

import os
from typing import TypedDict, Optional
from dotenv import load_dotenv

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import interrupt, Command
from typing import Literal

from tools.search_restaurants import search_restaurants
from tools.compare_restaurants import compare_restaurants
from tools.recommend import generate_recommendation
from tools.place_order import place_order

load_dotenv()


# ─────────────────────────────────────────────
# 1. STATE DEFINITION
# ─────────────────────────────────────────────
class AgentState(TypedDict):
    """
    The single shared object that flows through every node in the graph.

    WHY TypedDict instead of a plain dict?
    LangGraph needs to know the shape of your state upfront so it can
    serialize/deserialize it during checkpointing (the pause-and-resume
    mechanism). TypedDict gives it that schema without requiring a heavy
    ORM or dataclass setup.

    Every node receives this state, modifies only the fields it owns,
    and returns the updated fields. LangGraph merges the returned fields
    back into the state — you never return the full state object, just
    the changed keys.
    """
    user_request: str                        # The raw user query (e.g. "Find food in CP")
    area: str                                # Extracted area for search
    cuisine: Optional[str]                   # Optional cuisine filter
    restaurants_found: list                  # Raw results from search
    ranked_restaurants: list                 # Scored + sorted results from compare
    recommendation: str                      # LLM-generated explanation text
    approved: bool                           # Human decision: True=yes, False=no
    order_result: Optional[str]              # Confirmation message after order placed


# ─────────────────────────────────────────────
# 2. NODE FUNCTIONS
# ─────────────────────────────────────────────
# Each node is just a plain Python function that:
#   - receives the current AgentState
#   - does its work
#   - returns a dict of ONLY the fields it changed
#
# LangGraph will merge those changed fields back into the full state.
# You never need to pass the entire state forward manually — the graph
# does that bookkeeping for you. This is what your manual agent_loop
# was doing by hand with state.update({...}).

def search_node(state: AgentState) -> dict:
    """
    Node 1: Search for restaurants.

    Calls your existing search_restaurants() tool directly — no LLM involved.
    This is exactly the same function from Day 5/7, just called from a
    named graph node instead of inside a while-loop.
    """
    print(f"\n[Node: search] Searching for restaurants in '{state['area']}'...")

    results = search_restaurants(
        area=state["area"],
        cuisine=state.get("cuisine")
    )

    print(f"[Node: search] Found {len(results)} restaurants.")

    # Return only the fields this node changed.
    # LangGraph merges this into the full state automatically.
    return {"restaurants_found": results}


def compare_node(state: AgentState) -> dict:
    """
    Node 2: Compare and rank restaurants.

    Calls your Day 6 scoring engine. Pure Python, no LLM.
    Receives restaurants_found from state (set by search_node).
    """
    print(f"\n[Node: compare] Scoring and ranking {len(state['restaurants_found'])} restaurants...")

    if not state["restaurants_found"]:
        # If search found nothing, pass an empty list forward.
        # The recommend_node will handle this gracefully.
        return {"ranked_restaurants": []}

    ranked = compare_restaurants(state["restaurants_found"])
    print(f"[Node: compare] Top pick: {ranked[0]['name']} (score: {ranked[0].get('score', 'N/A'):.2f})")

    return {"ranked_restaurants": ranked}


def recommend_node(state: AgentState) -> dict:
    """
    Node 3: Generate LLM recommendation.

    Calls your Day 8 generate_recommendation() with the ranked list.
    This is the only node that makes an LLM API call.
    """
    print("\n[Node: recommend] Generating LLM recommendation...")

    if not state["ranked_restaurants"]:
        return {"recommendation": "No restaurants found matching your criteria. Please try a different area or cuisine."}

    recommendation = generate_recommendation(state["ranked_restaurants"])
    print(f"[Node: recommend] Recommendation generated.")

    return {"recommendation": recommendation}


def approval_node(state: AgentState) -> Command[Literal["order_node", "reject_node"]]:
    """
    Node 4: Human approval gate — the most important node today.

    THIS IS THE KEY DIFFERENCE FROM DAY 10.

    In agent_manual.py, you used:
        answer = input("Approve this order? (yes/no): ")

    That blocks the entire Python process. Works fine in a terminal,
    but completely breaks in Streamlit (which re-runs the script on
    every button click — you can't block mid-rerun waiting for input).

    interrupt() solves this differently:
        1. It serializes the ENTIRE current state to the checkpointer (MemorySaver).
        2. It raises a special exception that STOPS graph execution cleanly.
        3. Your calling code catches this, shows the UI, waits for the human.
        4. When the human clicks Approve/Reject, you call graph.invoke() again
           with Command(resume=True/False) — LangGraph loads the saved state
           and picks up exactly here, at this line, with the human's answer.

    The value passed to interrupt() is what gets surfaced to the caller
    (your test script today, Streamlit tomorrow) — it's the "payload" the
    human needs to see to make their decision.
    """
    print("\n[Node: approval] Pausing for human approval...")

    # Build the payload the human will see.
    # interrupt() sends this to the caller and freezes here.
    top = state["ranked_restaurants"][0] if state["ranked_restaurants"] else {}

    human_decision = interrupt({
        "recommendation": state["recommendation"],
        "top_restaurant": top.get("name", "Unknown"),
        "top_score": round(top.get("score", 0), 2),
        "cuisine": top.get("cuisine", "N/A"),
        "rating": top.get("rating", "N/A"),
        "price_for_two": top.get("price_for_two", "N/A"),
        "delivery_time_minutes": top.get("delivery_time_minutes", "N/A"),
        "prompt": "Do you approve this order? (True=yes / False=no)",
    })

    # human_decision is whatever the caller passed via Command(resume=...).
    # It will be True (approved) or False (rejected).

    if human_decision:
        print("[Node: approval] Human APPROVED the order.")
        return Command(
            goto="order_node",
            update={"approved": True}
        )
    else:
        print("[Node: approval] Human REJECTED the order.")
        return Command(
            goto="reject_node",
            update={"approved": False}
        )


def order_node(state: AgentState) -> dict:
    """
    Node 5a: Place the order (only reachable if human approved).

    Calls your Day 11 place_order() tool.
    The approved=True check in approval_node's routing makes it
    structurally impossible to reach this node without approval.
    """
    print("\n[Node: order] Placing order...")

    restaurant = state["ranked_restaurants"][0]
    result = place_order(restaurant, state)

    return {"order_result": result}


def reject_node(state: AgentState) -> dict:
    """
    Node 5b: Handle rejection cleanly.

    The human said no. We record that and end gracefully.
    No order is placed. No side effects.
    """
    print("\n[Node: reject] Order rejected by user. No order placed.")
    return {"order_result": "Order was not placed. You rejected the recommendation."}


# ─────────────────────────────────────────────
# 3. BUILD THE GRAPH
# ─────────────────────────────────────────────
def build_graph():
    """
    Assembles the StateGraph and returns a compiled, runnable graph.

    WHY a function instead of module-level code?
    So Streamlit (Day 13) can call build_graph() once and store the
    compiled graph in st.session_state, rather than rebuilding it on
    every script rerun.
    """

    builder = StateGraph(AgentState)

    # Add nodes — each string name becomes a node identifier in the graph.
    builder.add_node("search_node", search_node)
    builder.add_node("compare_node", compare_node)
    builder.add_node("recommend_node", recommend_node)
    builder.add_node("approval_node", approval_node)
    builder.add_node("order_node", order_node)
    builder.add_node("reject_node", reject_node)

    # Add edges — these define the sequence.
    # START → search → compare → recommend → approval
    # approval branches via Command(goto=...) — no add_edge needed for that.
    # Both order_node and reject_node lead to END.
    builder.add_edge(START, "search_node")
    builder.add_edge("search_node", "compare_node")
    builder.add_edge("compare_node", "recommend_node")
    builder.add_edge("recommend_node", "approval_node")
    builder.add_edge("order_node", END)
    builder.add_edge("reject_node", END)

    # The checkpointer is MANDATORY for interrupt() to work.
    # WHY: when interrupt() fires, LangGraph needs somewhere to save
    # the full state so it can be restored when the human responds.
    # MemorySaver stores it in RAM — perfect for development.
    # (Day 14+ could swap to SqliteSaver for persistence across restarts.)
    checkpointer = MemorySaver()

    return builder.compile(checkpointer=checkpointer)


# ─────────────────────────────────────────────
# 4. CONVENIENCE RUNNER (for terminal testing)
# ─────────────────────────────────────────────
def run_graph(area: str, cuisine: str = None):
    """
    Runs the graph end-to-end in a terminal with a real human prompt.

    This is the CLI equivalent of what Streamlit will do on Day 13 —
    it just uses print() and input() instead of buttons and st.dataframe().

    The thread_id is what LangGraph uses to identify this specific
    conversation's saved state. If you run again with the same thread_id,
    LangGraph would load the previous checkpoint — so we generate a
    unique one per run using a timestamp.
    """
    import time

    graph = build_graph()

    # Each run gets a unique thread_id so states don't bleed across runs.
    thread_id = f"food-order-{int(time.time())}"
    config = {"configurable": {"thread_id": thread_id}}

    initial_state = {
        "user_request": f"Find {cuisine or 'any'} food in {area}",
        "area": area,
        "cuisine": cuisine,
        "restaurants_found": [],
        "ranked_restaurants": [],
        "recommendation": "",
        "approved": False,
        "order_result": None,
    }

    print(f"\n{'='*50}")
    print(f"Starting food order agent for: {area} / {cuisine or 'any cuisine'}")
    print(f"Thread ID: {thread_id}")
    print(f"{'='*50}")

    # ── PHASE 1: Run until interrupt ──
    # graph.invoke() runs all nodes until it hits interrupt() in approval_node.
    # At that point it returns a GraphInterrupt — we catch it to show the user
    # what they're approving.
    result = graph.invoke(initial_state, config)

    # If we got here without an interrupt (e.g. no restaurants found),
    # the graph ran to END already — just print the result.
    if result.get("order_result") and "No restaurants" in result.get("recommendation", ""):
        print(f"\nResult: {result['order_result']}")
        return result

    # ── Show the interrupt payload to the human ──
    # LangGraph stores interrupt data in the graph state's __interrupt__ key,
    # but the simplest way to get it for a CLI is to check the state snapshot.
    state_snapshot = graph.get_state(config)

    if state_snapshot.tasks:
        # There's a pending interrupt — show the approval prompt
        interrupt_data = state_snapshot.tasks[0].interrupts[0].value

        print(f"\n{'─'*50}")
        print("APPROVAL REQUIRED")
        print(f"{'─'*50}")
        print(f"Recommendation: {interrupt_data['recommendation']}")
        print(f"\nTop Restaurant: {interrupt_data['top_restaurant']}")
        print(f"  Cuisine:       {interrupt_data['cuisine']}")
        print(f"  Rating:        {interrupt_data['rating']}")
        print(f"  Price for 2:   ₹{interrupt_data['price_for_two']}")
        print(f"  Delivery:      {interrupt_data['delivery_time_minutes']} mins")
        print(f"  Score:         {interrupt_data['top_score']}")
        print(f"{'─'*50}")

        # Get human input
        while True:
            answer = input("\nApprove this order? (yes/no): ").strip().lower()
            if answer in ("yes", "y"):
                human_approved = True
                break
            elif answer in ("no", "n"):
                human_approved = False
                break
            else:
                print("Please type 'yes' or 'no'.")

        # ── PHASE 2: Resume the graph with the human's decision ──
        # Command(resume=...) is how you "inject" the human's answer
        # back into the interrupt() call inside approval_node.
        # The graph loads the saved state from MemorySaver and continues
        # from exactly the line after interrupt() — with human_approved
        # as the return value of interrupt().
        final_result = graph.invoke(
            Command(resume=human_approved),
            config
        )

        print(f"\n{'='*50}")
        print(f"Final result: {final_result.get('order_result', 'No result')}")
        print(f"{'='*50}")
        return final_result

    else:
        # Graph finished without interrupting (edge case: empty results)
        print(f"\nResult: {result.get('order_result', 'No result')}")
        return result