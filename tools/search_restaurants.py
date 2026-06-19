# tools/search_restaurants.py

import json
import os


def load_restaurants():
    """
    Loads the restaurant data from the JSON file.
    
    We compute the path relative to this file's location so the function
    works correctly regardless of which directory you run your script from.
    """
    # __file__ is the path of this script (search_restaurants.py)
    # We go up one level (to project root) then into data/
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_path = os.path.join(base_dir, "data", "restaurants.json")
    
    with open(data_path, "r", encoding="utf-8") as f:
        return json.load(f)


def search_restaurants(area, cuisine=None):
    """
    Searches for restaurants by area, with an optional cuisine filter.

    Args:
        area (str): The area/neighbourhood to search in (case-insensitive).
        cuisine (str, optional): The cuisine type to filter by (case-insensitive).
                                 If None, all cuisines are returned.

    Returns:
        list[dict]: A list of matching restaurant dicts. Empty list if none found.
    """
    all_restaurants = load_restaurants()
    
    # Filter by area (case-insensitive so "connaught place" works too)
    results = [
        r for r in all_restaurants
        if r["area"].lower() == area.lower()
    ]
    
    # If a cuisine was specified, apply a second filter
    if cuisine:
        results = [
            r for r in results
            if r["cuisine"].lower() == cuisine.lower()
        ]
    
    return results