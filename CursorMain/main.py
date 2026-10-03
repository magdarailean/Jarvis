from google import genai
from pathlib import Path

key_file = Path(__file__).resolve().with_name("api key.txt")

try:
    key_text = key_file.read_text(encoding="utf-8-sig").strip()
except FileNotFoundError:
    raise SystemExit(f'Create {key_file} with KEY="your-api-key".')

key_name, separator, key_value = key_text.partition("=")
api_key = key_value.strip()
if len(api_key) >= 2 and api_key[0] == api_key[-1] and api_key[0] in ('"', "'"):
    api_key = api_key[1:-1].strip()

if key_name.strip() != "KEY" or not separator or not api_key:
    raise SystemExit(f'Put a non-empty key in {key_file} using KEY="your-api-key".')

client = genai.Client(api_key=api_key)

previous_interaction_id = None

print("Gemini Chat")
print("Type 'exit' to quit.\n")

while True:
    user_message = input("You: ")

    if user_message.lower() == "exit":
        print("Goodbye!")
        break

    try:
        interaction = client.interactions.create(
            model="gemini-3.8-flash",
            input=user_message,
            previous_interaction_id=previous_interaction_id
        )

        print(f"Gemini: {interaction.output_text}\n")

        previous_interaction_id = interaction.id

    except Exception as error:
        print("Error:", error)
