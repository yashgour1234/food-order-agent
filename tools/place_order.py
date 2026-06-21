# tools/place_order.py

import json
import os
import uuid
from datetime import datetime


def place_order(restaurant: dict, state: dict) -> dict:
    """
    Simulates placing a food order.
    
    WHY MOCK: We don't have a real payment/restaurant API, but we want to
    validate the FULL pipeline including the final step. Saving to a JSON
    file gives us a real, inspectable side-effect — not just a print statement.
    
    Returns a result dict so the agent can relay a confirmation to the user.
    """

    # Safety check — belt AND suspenders. Even if agent.py already gates this,
    # place_order itself refuses to run without approval. Two layers of protection.
    if not state.get("approved", False):
        return {
            "success": False,
            "message": "Order rejected: human approval was not granted.",
            "order_id": None,
        }

    # Build the order record
    order_id = f"ORD-{uuid.uuid4().hex[:8].upper()}"  # e.g. ORD-3F9A1C2B
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    order_record = {
        "order_id": order_id,
        "timestamp": timestamp,
        "restaurant_id": restaurant.get("id"),
        "restaurant_name": restaurant.get("name"),
        "area": restaurant.get("area"),
        "cuisine": restaurant.get("cuisine"),
        "price_for_two": restaurant.get("price_for_two"),
        "delivery_time_minutes": restaurant.get("delivery_time_minutes"),
        "status": "confirmed",
    }

    # Persist to data/orders.json — append to existing list, or create file fresh
    orders_path = os.path.join("data", "orders.json")

    # WHY this pattern: json.load on an empty/missing file crashes.
    # We always try to read existing orders; if anything goes wrong, start fresh.
    try:
        with open(orders_path, "r") as f:
            existing_orders = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        existing_orders = []

    existing_orders.append(order_record)

    with open(orders_path, "w") as f:
        json.dump(existing_orders, f, indent=2)

    print(f"\n✅ Order placed successfully!")
    print(f"   Order ID  : {order_id}")
    print(f"   Restaurant: {restaurant.get('name')} ({restaurant.get('area')})")
    print(f"   Cuisine   : {restaurant.get('cuisine')}")
    print(f"   Est. Time : {restaurant.get('delivery_time_minutes')} minutes")
    print(f"   Timestamp : {timestamp}")
    print(f"   Saved to  : {orders_path}\n")

    return {
        "success": True,
        "message": f"Order {order_id} placed successfully at {restaurant.get('name')}.",
        "order_id": order_id,
        "order_record": order_record,
    }