import os

from dotenv import load_dotenv
from google import genai

# Load environment variables from .env
load_dotenv()

# Get API key from .env
API_KEY = os.getenv("GOOGLE_API_KEY")

if not API_KEY:
    raise ValueError("GOOGLE_API_KEY not found in .env file")

# Create Gemini client
client = genai.Client(api_key=API_KEY)


def ask_llm(system_prompt: str, user_message: str) -> str:
    """
    Sends a prompt to Gemini and returns the text response.
    """

    prompt = f"""
System:
{system_prompt}

User:
{user_message}
"""

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
    )

    return response.text