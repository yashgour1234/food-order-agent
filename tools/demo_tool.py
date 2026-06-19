from datetime import datetime

def get_current_time():
    """Returns the current time as a formatted string."""
    now = datetime.now()
    formatted = now.strftime("%H:%M:%S on %A, %B %d, %Y")
    print(f"[TOOL EXECUTED] get_current_time() was called → {formatted}")
    return formatted