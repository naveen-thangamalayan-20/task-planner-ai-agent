import requests
import json
import os
import time # For simulating a brief pause

# --- Configuration ---
OLLAMA_API_URL = "http://localhost:11434/api/chat"
OLLAMA_MODEL = "qwen" # Ensure you have 'qwen' model pulled in Ollama
TASK_FILE = "tasks.json" # File to store long-term task memory

# --- Memory Components ---
# Long-term memory: Stores the actual tasks
# Format: [{"id": 1, "description": "Buy groceries", "status": "pending"}, ...]
tasks = []

# Short-term memory: Stores recent conversation history for context
# Limited to remember last few turns to manage token limits
conversation_history = [
    {"role": "system", "content": """
    You are a Conversational Task Manager AI. Your primary goal is to help the user manage their tasks.
    You understand commands to add tasks, list tasks, mark tasks as complete, query specific tasks, or clear all tasks.
    You must always respond in a structured JSON format.

    Here's the expected JSON structure:
    {
        "intent": "add_task" | "list_tasks" | "complete_task" | "query_task" | "clear_tasks" | "unknown",
        "task_description": "string or null for list/clear/unknown intents",
        "response_message": "string (a helpful, concise message to the user)"
    }

    - If the user asks to add a task, set 'intent' to 'add_task' and extract 'task_description'.
    - If the user asks to list tasks, set 'intent' to 'list_tasks'.
    - If the user asks to complete a task, set 'intent' to 'complete_task' and extract 'task_description'.
    - If the user asks about a specific task, set 'intent' to 'query_task' and extract 'task_description'.
    - If the user asks to clear all tasks, set 'intent' to 'clear_tasks'.
    - If you don't understand, set 'intent' to 'unknown'.

    Be concise in 'response_message'. Do NOT include code examples or elaborate on your internal process in 'response_message'.
    """}
]
MAX_CONVERSATION_HISTORY = 5 # Number of recent user/assistant turns to keep


# --- Utility Functions for Memory Management ---

def load_tasks():
    """Loads tasks from a JSON file (long-term memory)."""
    global tasks
    if os.path.exists(TASK_FILE):
        try:
            with open(TASK_FILE, 'r') as f:
                tasks = json.load(f)
            print(f"Agent: Loaded {len(tasks)} tasks from {TASK_FILE}.")
        except json.JSONDecodeError:
            print(f"Agent: Error reading {TASK_FILE}. Starting with empty tasks.")
            tasks = []
    else:
        print("Agent: No existing task file found. Starting with empty tasks.")

def save_tasks():
    """Saves tasks to a JSON file (long-term memory)."""
    with open(TASK_FILE, 'w') as f:
        json.dump(tasks, f, indent=4)
    # print(f"Agent: Tasks saved to {TASK_FILE}.")

def get_next_task_id():
    """Generates a unique ID for new tasks."""
    return max([t['id'] for t in tasks] + [0]) + 1

def add_to_conversation_history(role, content):
    """Adds a message to the conversational memory."""
    conversation_history.append({"role": role, "content": content})
    # Keep history within limits (excluding the system prompt)
    if len(conversation_history) > MAX_CONVERSATION_HISTORY + 1: # +1 for system message
        conversation_history.pop(1) # Remove oldest user/assistant pair (after system prompt)

# --- Reasoning Phase: Interact with Ollama (Qwen) ---

def get_llm_response(prompt_messages):
    """Sends messages to Ollama and returns the parsed JSON response."""
    try:
        response = requests.post(OLLAMA_API_URL,
                                 json={"model": OLLAMA_MODEL, "messages": prompt_messages, "stream": False, "format": "json"},
                                 timeout=120) # Increased timeout for local LLM
        response.raise_for_status() # Raise an exception for HTTP errors
        llm_output = response.json()['message']['content']
        # Qwen might sometimes include extra text outside JSON, try to parse
        try:
            # Find the first and last curly brace to isolate the JSON
            json_start = llm_output.find('{')
            json_end = llm_output.rfind('}')
            if json_start != -1 and json_end != -1 and json_end > json_start:
                json_string = llm_output[json_start : json_end + 1]
                return json.loads(json_string)
            else:
                raise ValueError("No valid JSON found in LLM response.")
        except json.JSONDecodeError as e:
            print(f"Agent (Error Parsing LLM JSON): {e}")
            print(f"Raw LLM output: {llm_output}")
            return {"intent": "unknown", "response_message": "I had trouble understanding your command format."}
    except requests.exceptions.ConnectionError:
        print("Agent: Error: Could not connect to Ollama server. Is 'ollama serve' running?")
        return {"intent": "exit", "response_message": "Ollama server not reachable. Exiting."}
    except requests.exceptions.RequestException as e:
        print(f"Agent: An error occurred during Ollama request: {e}")
        return {"intent": "unknown", "response_message": "An error occurred with my brain. Please try again."}
    except Exception as e:
        print(f"Agent: An unexpected error occurred: {e}")
        return {"intent": "unknown", "response_message": "Something went wrong internally."}

# --- Action Phase: Modify and Display Tasks ---

def perform_action(parsed_intent):
    """Executes actions based on the LLM's parsed intent."""
    global tasks
    intent = parsed_intent.get("intent")
    task_description = parsed_intent.get("task_description")
    response_message = parsed_intent.get("response_message", "Okay.") # Default response message

    if intent == "add_task":
        if task_description:
            new_task = {"id": get_next_task_id(), "description": task_description, "status": "pending"}
            tasks.append(new_task)
            save_tasks()
            return response_message
        else:
            return "Agent: I need a description to add a task."

    elif intent == "list_tasks":
        if not tasks:
            return "Agent: Your task list is empty!"
        else:
            task_list_str = "Agent: Here are your tasks:\n"
            pending_tasks = [t for t in tasks if t['status'] == 'pending']
            completed_tasks = [t for t in tasks if t['status'] == 'completed']

            if pending_tasks:
                task_list_str += "  --- Pending ---\n"
                for task in pending_tasks:
                    task_list_str += f"  - [ ] {task['description']} (ID: {task['id']})\n"
            if completed_tasks:
                task_list_str += "  --- Completed ---\n"
                for task in completed_tasks:
                    task_list_str += f"  - [x] {task['description']} (ID: {task['id']})\n"
            return task_list_str.strip()

    elif intent == "complete_task":
        if task_description:
            # Try to find by full description first
            found = False
            for task in tasks:
                if task['description'].lower() == task_description.lower() and task['status'] == 'pending':
                    task['status'] = 'completed'
                    found = True
                    break
            # If not found by description, try by ID if description looks like an ID
            if not found and task_description.isdigit():
                task_id = int(task_description)
                for task in tasks:
                    if task['id'] == task_id and task['status'] == 'pending':
                        task['status'] = 'completed'
                        found = True
                        task_description = task['description'] # Use actual description for message
                        break

            if found:
                save_tasks()
                return f"Agent: Marked '{task_description}' as complete."
            else:
                return f"Agent: Could not find pending task '{task_description}'."
        else:
            return "Agent: Please specify which task to complete."

    elif intent == "query_task":
        if task_description:
            found_tasks = [
                t for t in tasks
                if task_description.lower() in t['description'].lower()
            ]
            if found_tasks:
                response = f"Agent: I found these tasks related to '{task_description}':\n"
                for task in found_tasks:
                    status_marker = "[x]" if task['status'] == 'completed' else "[ ]"
                    response += f"  - {status_marker} {task['description']} (ID: {task['id']})\n"
                return response.strip()
            else:
                return f"Agent: I couldn't find any tasks related to '{task_description}'."
        else:
            return "Agent: What task are you asking about?"

    elif intent == "clear_tasks":
        confirm = input("Agent: Are you sure you want to clear ALL tasks? (yes/no): ").lower().strip()
        if confirm == 'yes':
            tasks = []
            save_tasks()
            return "Agent: All tasks cleared."
        else:
            return "Agent: Task clearing cancelled."

    elif intent == "unknown":
        return response_message # LLM provides a default message for unknown intent
    else:
        return "Agent: I'm not sure how to handle that command."

# --- Main Agent Loop ---

def run_agent():
    """Main loop for the Conversational Task Manager agent."""
    load_tasks() # Load long-term memory at startup

    print("--- Conversational Task Manager Agent (Qwen via Ollama) ---")
    print("Type your commands (e.g., 'Add buy groceries', 'List tasks', 'Complete buy groceries', 'Quit').")
    print("-" * 60)

    while True:
        # 1. Perception
        user_input = input("You: ").strip()
        if user_input.lower() == 'quit':
            print("Agent: Goodbye!")
            save_tasks() # Save tasks before exiting
            break
        elif not user_input:
            continue # Ignore empty input

        # Add user input to conversational history
        add_to_conversation_history("user", user_input)

        # 2. Reasoning (using Ollama's Qwen model)
        # Pass the current conversational history to the LLM for context
        # This is where short-term memory is leveraged
        llm_response_json = get_llm_response(conversation_history)

        if llm_response_json.get("intent") == "exit": # Handle Ollama connection error exit
            print(llm_response_json.get("response_message"))
            break

        # 3. Action (based on LLM's parsed intent)
        agent_response = perform_action(llm_response_json)

        # Add agent's response to conversational history (for future turns)
        # Only add content that is meant for the user, not internal debugging info
        add_to_conversation_history("assistant", agent_response)

        # Print the agent's final response to the user
        print(agent_response)
        print("-" * 60) # Separator for readability

# --- Run the Agent ---
if __name__ == "__main__":
    run_agent()