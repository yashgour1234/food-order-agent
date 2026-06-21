# test_graph.py
"""
Day 12 test: Run the LangGraph version of the agent.

This should produce identical observable behavior to running main.py
(your Day 11 manual agent), just with a different internal architecture.

Expected trace:
  [Node: search]   → finds restaurants
  [Node: compare]  → scores and ranks them
  [Node: recommend] → LLM writes recommendation
  [Node: approval] → pauses, shows you the recommendation
  You type yes/no
  [Node: order] or [Node: reject] → order placed or skipped
"""

from core.graph import run_graph

if __name__ == "__main__":
    # Test with a known area from your restaurants.json
    # Change "Connaught Place" to an area you know has restaurants in your data
    run_graph(area="Connaught Place", cuisine=None)