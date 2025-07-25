# Conceptual code - don't dwell on details, just show structure
import requests



def call_llm(prompt):
    url = "http://localhost:11434/api/generate"
    payload = {
        "model": "qwen2.5:7b",  # Or whatever model you chose
        "prompt": prompt,
        "stream": False
    }
    response = requests.post(url, json=payload)
    print(response.json()['response'])

def run_agent_loop():
    while True:
        user_input = input("You:").strip()
        if user_input == "quit":
            break
        elif not user_input:
            continue
        print(user_input)

        call_llm(user_input)
