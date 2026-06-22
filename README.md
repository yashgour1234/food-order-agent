# Food Order Agent — Delhi

A Human-in-the-Loop AI food ordering agent built in Python. The agent searches Delhi restaurants, compares them across price, rating, delivery time and offers, generates a grounded recommendation using an LLM — and **cannot place an order without your explicit approval**.

Built as a 15-day learning project to understand AI agent architecture from scratch: tool calling, the ReAct loop, LangGraph state machines, and Human-in-the-Loop design.

---

## Demo

> Search → Compare → Recommend → **You Approve** → Order Confirmed

The agent will never spend your money without a human "yes." That's the entire point.

---

## What it does

Given a Delhi area and optional cuisine preference, the agent:

1. **Searches** mock restaurant data filtered by area and cuisine
2. **Compares** open restaurants using a normalized weighted score (rating, price, delivery time, offers)
3. **Recommends** the best option — the LLM explains *why*, using only the computed data (no hallucinated facts)
4. **Pauses for your approval** — shows the full comparison table and reasoning before asking
5. **Places the order** (simulated) only if you click Approve — rejection stops the pipeline cleanly
6. **Persists order history** to `data/orders.json`

---

## Architecture

```
User input (Streamlit UI)
        │
        ▼
  search_node  ──→  tools/search_restaurants.py   (filter by area/cuisine)
        │
        ▼
  compare_node ──→  tools/compare_restaurants.py  (normalize + weighted score)
        │
        ▼
  recommend_node ──→ tools/recommend.py           (LLM explains top 3)
        │
        ▼
  approval_node ──→  LangGraph interrupt()        (human sees table + reasoning)
        │
   Approve / Reject
        │
        ▼
  order_node   ──→  tools/place_order.py          (saves to data/orders.json)
```

### Two implementations preserved side-by-side

| File | Purpose |
|---|---|
| `core/agent_manual.py` | Hand-built ReAct loop  — shows what LangGraph automates |
| `core/graph.py` | LangGraph StateGraph  — used by the Streamlit UI |

Keeping both is intentional. `agent_manual.py` shows the raw mechanics; `graph.py` shows the same logic expressed as a formal state machine.

### Key architectural decisions

| Decision | Rationale |
|---|---|
| Scoring in Python, not LLM | Deterministic, fast, free, testable — LLM is reserved for natural language explanation only |
| `approved` defaults to `False` | `place_order` is structurally unreachable unless explicitly set `True` — fail-safe by design |
| `MemorySaver` checkpointer | Required for LangGraph's `interrupt()` to pause and resume across Streamlit re-runs |
| Mock JSON data | Full control over edge cases (closed restaurants, ties, no results) without external API dependencies |
| `compare_restaurants` not in LLM tool list | Gemini skips it when offered as a tool — scoring runs in Python directly, LLM only sees the results |

---

## Project structure

```
food-order-agent/
├── core/
│   ├── agent.py            # ReAct loop entry point
│   ├── agent_manual.py     # Preserved hand-built loop 
│   ├── graph.py            # LangGraph StateGraph with interrupt() 
│   ├── llm_client.py       # Gemini API client + ask_llm()
│   └── state.py            # create_initial_state()
├── tools/
│   ├── search_restaurants.py   # Filter restaurants.json by area/cuisine
│   ├── compare_restaurants.py  # Normalized weighted scoring + ranking
│   ├── recommend.py            # LLM recommendation prompt (grounded)
│   └── place_order.py          # Simulate order + persist to orders.json
├── ui/
│   └── app.py              # Streamlit HITL interface 
├── data/
│   ├── restaurants.json    # 15–20 mock Delhi restaurants
│   └── orders.json         # Persisted order history (auto-created on first order)
├── docs/
│   └── hitl_design.md      # HITL architecture design document 
├── tests/
│   └── test_tools.py       # 11 pytest tests for deterministic tools 
├── .env                    # GEMINI_API_KEY (never committed)
├── .gitignore
├── requirements.txt
└── README.md
```

---

## Setup

**Prerequisites:** Python 3.10+, a free [Google AI Studio](https://aistudio.google.com) API key (no credit card required)

```bash
# 1. Clone the repo
git clone https://github.com/YOUR_USERNAME/food-order-agent.git
cd food-order-agent

# 2. Create and activate virtual environment
python -m venv venv

# Windows:
venv\Scripts\activate
# Mac/Linux:
# source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Create a .env file in the project root and add your key:
# GEMINI_API_KEY=your_key_here

# 5. Run the Streamlit UI
streamlit run ui/app.py
```

---

## Usage

1. Open the Streamlit app — it auto-opens at `http://localhost:8501`
2. Enter a Delhi area: `Connaught Place`, `Lajpat Nagar`, `Saket`, etc.
3. Optionally specify a cuisine: `North Indian`, `Chinese`, `South Indian`, etc.
4. Click **Find Restaurants**
5. Review the comparison table and LLM recommendation
6. Click **Approve & Order** or **Reject**
7. If approved, a confirmation appears and `data/orders.json` gets a new entry

**To run tests:**
```bash
pytest tests/ -v
```

Expected: 11 tests, all passing, in under 1 second.

---

## Requirements mapped to implementation

| Original requirement | Where it's implemented |
|---|---|
| Find restaurants by area/cuisine | `tools/search_restaurants.py` → `search_restaurants()` |
| Compare by price | `tools/compare_restaurants.py` — price penalty in weighted score |
| Compare by offers | `tools/compare_restaurants.py` — offer discount extracted and scored |
| Compare by rating | `tools/compare_restaurants.py` — rating carries the highest weight (0.4) |
| Compare by delivery time | `tools/compare_restaurants.py` — delivery time penalty in score |
| Recommend best option | `tools/recommend.py` — LLM explains top 3 using only computed data |
| Ask for approval | `core/graph.py` → `approval_node` using LangGraph `interrupt()` |
| Place order only after approval | `tools/place_order.py` — double-guarded by `state["approved"] == True` |

---

## How the scoring works

`compare_restaurants` ranks restaurants using a normalized weighted score so that different units (minutes, rupees, stars) are comparable:

```
score = (rating_norm × 0.4)
      + (offer_discount_norm × 0.3)
      - (delivery_time_norm × 0.2)
      - (price_norm × 0.1)
```

Each metric is normalized to 0–1 across the candidate list before weighting. Closed restaurants are excluded before scoring — a closed restaurant can never win regardless of its raw rating.

The LLM sees only the top 3 scored results and explains the winner in plain English. It never recalculates the ranking itself.

---

## How the HITL gate works

```
state["approved"] starts as False
          │
          ▼
  approval_node (LangGraph interrupt)
  → agent pauses, renders comparison table + recommendation in Streamlit
  → waits for human button click
          │
     ┌────┴────┐
   Approve    Reject
     │           │
     ▼           ▼
state["approved"]  pipeline
  set to True      stops, no
     │             order saved
     ▼
  order_node
  place_order() runs
```

There is no code path where `place_order()` executes with `approved == False`. This is enforced both by the LangGraph edge condition and by an explicit check inside `place_order()` itself (defense-in-depth).

---

## Known limitations

- **Mock data only** — `data/restaurants.json` contains ~15–20 hand-crafted Delhi restaurants. No real Zomato, Swiggy, or Google Places integration.
- **Exact area string matching** — "nearby" means the area field matches exactly. Searching `"CP"` will not match `"Connaught Place"`.
- **No conversational memory** — each session starts fresh. Follow-ups like "show me cheaper options" require starting a new search.
- **Single user only** — no authentication, no concurrent session handling. JSON file storage is not safe for multiple simultaneous users.
- **Simulated ordering** — `place_order` saves a local record but does not contact any real restaurant or payment system.
- **Gemini 503 errors** — transient API overload errors can occur; re-running the search usually resolves them.

---

## What's next 

- **Real data** — replace `restaurants.json` with Google Places API for genuine nearby restaurant discovery using GPS coordinates
- **Conversational memory** — handle follow-ups like "show me faster options" without restarting the pipeline
- **Structured observability** — add LangSmith tracing or custom structured logs to debug agent decisions after the fact
- **Deployment** — host on Streamlit Community Cloud so others can use it without local setup

---

## Tech stack

| Layer | Choice | Why |
|---|---|---|
| Language | Python 3.10 | Universal agent framework support |
| LLM | Google Gemini `gemini-2.5-flash` via `google-genai` | Free tier, strong tool-calling support |
| Agent orchestration | LangGraph (`StateGraph`, `interrupt()`, `MemorySaver`) | First-class HITL support via `interrupt()` |
| UI | Streamlit | Pure Python, approval buttons in ~15 lines |
| Testing | pytest | Deterministic tool logic only — no LLM calls in tests |
| Storage | JSON files | No database needed for single-user MVP |

---

## What I learned

This project was built day-by-day to understand *why* each piece of agent architecture exists, not just *how* to use it:

- **Tool calling** is the mechanism that turns a chatbot into an agent — the LLM requests functions, your code runs them
- **The ReAct loop** (reason + act) is the pattern nearly all agent frameworks automate — building it by hand first made LangGraph obvious
- **Deterministic logic belongs in Python** — scoring and filtering are fast, free, testable; LLM is reserved for language tasks only
- **HITL is an architecture decision, not a feature** — the approval gate is designed so bypassing it requires changing multiple files, not just one
- **`MemorySaver` is not optional** for `interrupt()` — LangGraph's pause/resume depends on checkpointing state between Streamlit re-runs

---
