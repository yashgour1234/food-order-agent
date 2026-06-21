# Human-in-the-Loop (HITL) Design Document

**Project:** food-order-agent
**Day:** 9 of 15-Day Bootcamp

---

## 1. Tool Classification Table

| Tool | Classification | Reason |
|---|---|---|
| `search_restaurants` | ✅ Auto-run | Read-only operation. Reversible, no external side-effects. Running it 10 times changes nothing in the world. |
| `compare_restaurants` | ✅ Auto-run | Pure Python computation. No API calls, no data mutation. 100% deterministic and free. |
| `generate_recommendation` | ✅ Auto-run | LLM call that produces text only. No real-world consequence — it explains, it does not act. |
| `place_order` | 🛑 Requires human approval | **Irreversible.** Money moves, the restaurant begins preparing food. Cannot be recalled once submitted. |

**Decision rule applied:** a tool is auto-run if it is (a) reversible AND (b) has no real-world consequence beyond producing data. The moment a tool causes an irreversible real-world effect, it must be gated behind explicit human confirmation.

---

## 2. Approval Flow (Step by Step)

```
[Agent completes recommendation]
        │
        ▼
[Display to human]
  - Comparison table: top 3 restaurants with scores, prices, delivery time, offers
  - LLM recommendation text (2–3 sentences explaining the winner)
  - Ranked list showing all candidates considered
        │
        ▼
[Prompt: "Do you approve this order? (yes/no)"]
        │
   ┌────┴─────┐
  yes         no
   │           │
   ▼           ▼
[place_order] [Stop + inform user]
  - Save to    "Order cancelled. You can
    orders.json  restart with new preferences."
  - Print
    confirmation
```

**What the human sees before deciding:**
1. Restaurant name, cuisine, area
2. Price for two (₹)
3. Estimated delivery time (minutes)
4. Active offers (if any)
5. The computed score and score breakdown
6. The LLM's written recommendation with reasoning

The human must never be asked to approve a bare restaurant name. Full context is non-negotiable for an informed decision.

---

## 3. Rejection Handling

**MVP decision (Day 9–11):** On rejection, the agent prints a cancellation message and stops. The user must re-run `main.py` with new preferences.

**Rationale:** Implementing a "re-rank remaining candidates" flow adds stateful complexity that is better handled by LangGraph's `interrupt()`/resume model introduced on Day 12. Doing it in plain Python first would require passing mutable state across the rejection branch — premature complexity for an MVP.

**Post-MVP (Day 12+):** After LangGraph is introduced, the rejection branch will:
1. Ask the user if they want to see the next-best option
2. If yes: re-present the #2 ranked restaurant with the same approval gate
3. If no: ask for entirely new preferences (area, cuisine) and restart the agent loop

---

## 4. Edge Cases Considered

| Scenario | Handling |
|---|---|
| User types "YES", "Yes", "y" | Normalize to lowercase before comparison — all map to approval |
| User types "NO", "No", "n" | Normalize to lowercase — all map to rejection |
| User types garbage ("maybe", "idk", "") | Re-prompt once: "Please enter 'yes' or 'no'." If still invalid, treat as rejection (safe default) |
| No restaurants found by search | Agent returns early before reaching the approval gate — user sees "No restaurants found in [area]" |
| All restaurants are closed | `compare_restaurants` filters them out; if list becomes empty, agent returns early before the gate |
| Double-approval (button clicked twice) | In CLI: `input()` blocks until one response, physically impossible. In Streamlit (Day 13): guard with `st.session_state["approved"]` boolean check — only process approval if not already set |
| Timeout / no response | Not applicable for CLI `input()` — it blocks indefinitely. For production web UI: treat no response within N seconds as rejection (safe default). Not implemented in MVP. |

---

## 5. The Safety Invariant

**The single most important guarantee this design must enforce:**

> There is no code path in the system through which `place_order()` can be called with `state["approved"] == False`.

This will be verified on Day 10 by:
1. Reading `core/agent.py` and tracing every possible execution path
2. Confirming `place_order()` is only reachable through the `if state["approved"]:` branch
3. Testing: running the agent end-to-end and typing "no" — confirming `data/orders.json` receives no new entry

**Default state:** `state["approved"]` initialises to `False` in `create_initial_state()` (Day 2). It is only ever set to `True` by explicit user input of "yes" at the approval gate. This is intentional — fail-safe by default.

---

## 6. What This Document Enables

Day 10's implementation will be near-mechanical from this document:
- One function `approval_gate(recommendation, state)` handles display + input + state update
- One `if state["approved"]:` guard in `core/agent.py` routes to `place_order` or early exit
- Input normalisation handles the "YES/Yes/y" variants noted above
- The rejection message is pre-decided: no ambiguity about what to print

Day 12 will extend this with LangGraph's `interrupt()`, which solves the same problem (pausing for human input) but in a way that survives Streamlit's full-script-rerun model.