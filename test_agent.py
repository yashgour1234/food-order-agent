# test_agent.py

from core.agent import run_agent

if __name__ == "__main__":
    result = run_agent("Find me a good restaurant for delivery in Connaught Place")

    print("\n" + "="*60)
    print("FINAL RESULTS SUMMARY")
    print("="*60)

    print(f"\nRestaurants ranked: {len(result['ranked_restaurants'])}")
    if result['ranked_restaurants']:
        print("\nTop 3 picks:")
        for i, r in enumerate(result['ranked_restaurants'][:3]):
            print(f"  {i+1}. {r['name']} (score: {r.get('score', 'N/A'):.2f})")

    print(f"\n--- RECOMMENDATION ---")
    print(result['recommendation'])