# ui/app.py

import sys
import os
import uuid
import streamlit as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.graph import build_graph
from langgraph.types import Command

# ── Page config (must be first st.* call) ──
st.set_page_config(
    page_title="🍽️ Food Order Agent",
    page_icon="🍽️",
    layout="wide",
)

st.title("🍽️ Delhi Food Order Agent")
st.caption("Powered by Gemini + LangGraph · Human-in-the-Loop")

# ── Session state defaults ──
# Every key your app needs across re-runs lives here.
defaults = {
    "stage": "input",
    "graph": None,
    "thread_config": None,
    "restaurants": [],
    "recommendation": "",
    "error": None,
    "human_decision": None,
    "final_state": None,
    "area": "",
    "cuisine": "",
}
for key, val in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = val


def reset_state():
    for key, val in defaults.items():
        st.session_state[key] = val


# ══════════════════════════════════════════════
# STAGE 1 — INPUT
# Collect area + cuisine. Nothing expensive here.
# ══════════════════════════════════════════════
if st.session_state["stage"] == "input":
    st.subheader("Where are you ordering from?")

    col1, col2 = st.columns(2)
    with col1:
        area = st.text_input(
            "📍 Area / Locality",
            placeholder="e.g. Connaught Place, Hauz Khas, Saket",
        )
    with col2:
        cuisine = st.text_input(
            "🍛 Cuisine (optional)",
            placeholder="e.g. North Indian, Chinese, Pizza",
        )

    if st.button("🔍 Find Restaurants", type="primary", use_container_width=True):
        if not area.strip():
            st.warning("Please enter an area to search in.")
        else:
            # Store inputs so the searching stage can use them
            st.session_state["area"] = area.strip()
            st.session_state["cuisine"] = cuisine.strip() if cuisine.strip() else None
            st.session_state["stage"] = "searching"
            st.rerun()


# ══════════════════════════════════════════════
# STAGE 2 — SEARCHING
# Run the graph from START until interrupt() fires at approval_node.
# We build the initial state to match your AgentState TypedDict exactly.
# ══════════════════════════════════════════════
elif st.session_state["stage"] == "searching":
    with st.spinner("🔍 Searching restaurants, comparing options, generating recommendation..."):
        try:
            # Build graph once and store it — we need the same instance
            # to resume later with Command(resume=...).
            graph = build_graph()
            st.session_state["graph"] = graph

            # Unique thread_id per search so MemorySaver can find
            # the right checkpoint when we resume after interrupt().
            thread_config = {"configurable": {"thread_id": str(uuid.uuid4())}}
            st.session_state["thread_config"] = thread_config

            area = st.session_state["area"]
            cuisine = st.session_state["cuisine"]

            # ── Initial state matches your AgentState TypedDict exactly ──
            # This is the fix: we pass area/cuisine/user_request,
            # NOT messages — because that's what your graph expects.
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

            # stream() runs the graph and yields state after each node.
            # It will stop automatically when interrupt() fires in approval_node.
            events = list(graph.stream(
                initial_state,
                config=thread_config,
                stream_mode="values",
            ))

            # The last event is the state snapshot just before the interrupt pause.
            last_state = events[-1] if events else {}
            st.session_state["restaurants"] = last_state.get("ranked_restaurants", [])
            st.session_state["recommendation"] = last_state.get("recommendation", "")

            if not st.session_state["restaurants"]:
                st.session_state["error"] = (
                    f"No restaurants found in '{area}'. "
                    "Try a different area like 'Connaught Place' or 'Hauz Khas'."
                )
                st.session_state["stage"] = "error"
            else:
                st.session_state["stage"] = "awaiting_approval"

        except Exception as e:
            st.session_state["error"] = f"Something went wrong: {str(e)}"
            st.session_state["stage"] = "error"

    st.rerun()


# ══════════════════════════════════════════════
# STAGE 3 — AWAITING APPROVAL
# Graph is paused at interrupt(). Show the human:
#   1. Comparison table of all ranked candidates
#   2. LLM recommendation text
#   3. Approve / Reject buttons
# ══════════════════════════════════════════════
elif st.session_state["stage"] == "awaiting_approval":
    st.subheader("🧐 Review & Approve")

    restaurants = st.session_state["restaurants"]

    # ── Comparison table ──
    st.markdown("#### 📊 Top Candidates")
    table_rows = []
    for i, r in enumerate(restaurants[:3], start=1):
        offers_str = ", ".join(r.get("offers", [])) if r.get("offers") else "None"
        table_rows.append({
            "Rank":            f"#{i}",
            "Restaurant":      r.get("name", "—"),
            "Cuisine":         r.get("cuisine", "—"),
            "Rating ⭐":        r.get("rating", "—"),
            "Price for 2 (₹)": r.get("price_for_two", "—"),
            "Delivery (min)":  r.get("delivery_time_minutes", "—"),
            "Offers":          offers_str,
            "Score":           round(r.get("score", 0), 3),
        })

    st.dataframe(table_rows, use_container_width=True, hide_index=True)

    # ── LLM recommendation ──
    st.markdown("#### 🤖 Agent's Recommendation")
    rec = st.session_state.get("recommendation", "")
    if rec:
        st.info(rec)

    # ── Highlight the top pick ──
    top = restaurants[0]
    st.success(
        f"**Recommended: {top.get('name')}** — "
        f"{top.get('cuisine')} · "
        f"⭐ {top.get('rating')} · "
        f"₹{top.get('price_for_two')} for two · "
        f"🕐 {top.get('delivery_time_minutes')} min"
    )

    st.divider()
    st.markdown("**Do you want to place this order?**")

    col_approve, col_reject = st.columns(2)
    with col_approve:
        if st.button("✅ Approve & Order", type="primary", use_container_width=True):
            st.session_state["human_decision"] = True   # matches your graph: True = approved
            st.session_state["stage"] = "resuming"
            st.rerun()
    with col_reject:
        if st.button("❌ Reject", use_container_width=True):
            st.session_state["human_decision"] = False  # matches your graph: False = rejected
            st.session_state["stage"] = "resuming"
            st.rerun()


# ══════════════════════════════════════════════
# STAGE 4 — RESUMING
# Resume the paused graph with the human's boolean decision.
# Command(resume=True/False) is the value that becomes the
# return value of interrupt() inside approval_node.
# ══════════════════════════════════════════════
elif st.session_state["stage"] == "resuming":
    decision = st.session_state["human_decision"]
    label = "Placing your order..." if decision else "Cancelling..."

    with st.spinner(label):
        try:
            graph = st.session_state["graph"]
            thread_config = st.session_state["thread_config"]

            # Resume exactly where interrupt() paused the graph.
            # The graph loads state from MemorySaver and continues
            # from the line after interrupt() in approval_node,
            # with `decision` as the return value of interrupt().
            resume_events = list(graph.stream(
                Command(resume=decision),
                config=thread_config,
                stream_mode="values",
            ))

            final_state = resume_events[-1] if resume_events else {}
            st.session_state["final_state"] = final_state
            st.session_state["stage"] = "done"

        except Exception as e:
            st.session_state["error"] = f"Error during order processing: {str(e)}"
            st.session_state["stage"] = "error"

    st.rerun()


# ══════════════════════════════════════════════
# STAGE 5 — DONE
# ══════════════════════════════════════════════
elif st.session_state["stage"] == "done":
    final_state = st.session_state.get("final_state", {})
    decision = st.session_state.get("human_decision")
    order_result = final_state.get("order_result", "")

    if decision:
        st.balloons()
        st.success(f"🎉 Order placed successfully!")
        if order_result:
            st.markdown("#### 📋 Confirmation")
            st.code(order_result)
    else:
        st.warning(f"Order rejected. No order was placed.")
        if order_result:
            st.caption(order_result)

    st.divider()
    if st.button("🔄 Start a New Search", use_container_width=True):
        reset_state()
        st.rerun()


# ══════════════════════════════════════════════
# STAGE 6 — ERROR
# ══════════════════════════════════════════════
elif st.session_state["stage"] == "error":
    st.error(f"⚠️ {st.session_state.get('error', 'Unknown error')}")
    if st.button("🔄 Try Again", use_container_width=True):
        reset_state()
        st.rerun()