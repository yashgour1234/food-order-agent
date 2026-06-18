from core.llm_client import ask_llm

response = ask_llm(
    system_prompt="You are a helpful food-ordering assistant.",
    user_message="What should I consider when picking a restaurant for delivery?"
)

print(response)