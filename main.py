import json
import os
import uuid
from datetime import datetime
from typing import List, Dict, Any

from dotenv import load_dotenv
from openai import OpenAI

# --------- CONFIG ---------
TASKS_FILE = "tasks.json"
SYSTEM_PROMPT = """
You are a helpful 'concierge' AI that manages a simple task list for the user.

You MUST respond ONLY with a single JSON object and NOTHING else. No explanations.

JSON schema:
{
  "intent": "add_task" | "list_tasks" | "complete_task" | "delete_task" | "help" | "exit",
  "task_title": string or null,
  "task_due": string or null,  // natural language or date string, can be null
  "task_id": string | null     // id of an existing task, if user refers to one
}

Rules:
- If the user wants to add a new task, use intent "add_task" and fill "task_title" and optionally "task_due".
- If the user asks what they need to do, use intent "list_tasks".
- If the user says they finished something, use intent "complete_task". If they mention the exact title, do NOT guess task_id, leave task_id as null and keep the title.
- If they clearly want to delete a task, use intent "delete_task".
- For greetings, questions about what you can do, or confusion, use intent "help".
- If they want to quit, use intent "exit".
- task_title should be a short title if relevant; otherwise null.
"""

# --------- LLM CLIENT SETUP ---------

load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise RuntimeError("OPENAI_API_KEY not set in .env")

client = OpenAI(api_key=api_key)


def call_llm(user_message: str) -> Dict[str, Any]:
    """
    Send the user message to the LLM and get back a JSON object with intent, task info.
    """
    response = client.chat.completions.create(
        model="gpt-4.1-mini",  # you can change this to another model
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        temperature=0.1,
    )

    content = response.choices[0].message.content.strip()

    # Safety: try to parse JSON
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        # Fallback to a neutral result
        data = {
            "intent": "help",
            "task_title": None,
            "task_due": None,
            "task_id": None,
        }
    return data


# --------- TASK STORAGE ---------

def load_tasks() -> List[Dict[str, Any]]:
    if not os.path.exists(TASKS_FILE):
        return []
    try:
        with open(TASKS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def save_tasks(tasks: List[Dict[str, Any]]) -> None:
    with open(TASKS_FILE, "w", encoding="utf-8") as f:
        json.dump(tasks, f, indent=2)


def add_task(title: str, due: str | None) -> Dict[str, Any]:
    tasks = load_tasks()
    task = {
        "id": str(uuid.uuid4()),
        "title": title,
        "due": due,
        "status": "pending",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "completed_at": None,
    }
    tasks.append(task)
    save_tasks(tasks)
    return task


def list_tasks() -> List[Dict[str, Any]]:
    return load_tasks()


def find_matching_tasks_by_title(title: str) -> List[Dict[str, Any]]:
    """
    Simple title matching: case-insensitive 'in' search.
    """
    tasks = load_tasks()
    title_lower = title.lower()
    return [t for t in tasks if title_lower in t["title"].lower()]


def complete_task_by_id(task_id: str) -> Dict[str, Any] | None:
    tasks = load_tasks()
    found = None
    for t in tasks:
        if t["id"] == task_id:
            t["status"] = "completed"
            t["completed_at"] = datetime.now().isoformat(timespec="seconds")
            found = t
            break
    if found:
        save_tasks(tasks)
    return found


def delete_task_by_id(task_id: str) -> Dict[str, Any] | None:
    tasks = load_tasks()
    new_tasks = []
    deleted = None
    for t in tasks:
        if t["id"] == task_id:
            deleted = t
        else:
            new_tasks.append(t)
    if deleted:
        save_tasks(new_tasks)
    return deleted


# --------- HUMAN-FACING RESPONSES ---------

def print_task(task: Dict[str, Any]) -> None:
    status_icon = "✅" if task["status"] == "completed" else "⏳"
    due_str = f" | Due: {task['due']}" if task["due"] else ""
    print(f"- [{status_icon}] {task['title']} (id: {task['id'][:8]}){due_str}")


def handle_intent(parsed: Dict[str, Any]) -> bool:
    """
    Returns False if user wants to exit, else True.
    """
    intent = parsed.get("intent")
    title = parsed.get("task_title")
    due = parsed.get("task_due")
    task_id = parsed.get("task_id")

    if intent == "add_task":
        if not title:
            print("Couldn't understand the task title. Try: 'Add task: submit assignment by tomorrow'.")
            return True
        task = add_task(title, due)
        print("Task added:")
        print_task(task)
        return True

    elif intent == "list_tasks":
        tasks = list_tasks()
        if not tasks:
            print("No tasks yet. You're all clear. 🚀")
            return True
        print("Here are your tasks:")
        for t in tasks:
            print_task(t)
        return True

    elif intent == "complete_task":
        if task_id:
            # If future versions actually pass ids from LLM, we could use this
            updated = complete_task_by_id(task_id)
            if updated:
                print("Marked as completed:")
                print_task(updated)
            else:
                print("Couldn't find that task.")
            return True

        if not title:
            print("Which task did you complete? Mention some words from its title.")
            return True

        matches = find_matching_tasks_by_title(title)
        if not matches:
            print("No matching task found.")
        elif len(matches) == 1:
            updated = complete_task_by_id(matches[0]["id"])
            print("Marked as completed:")
            print_task(updated)
        else:
            print("Multiple tasks matched. Be more specific. Matching tasks:")
            for t in matches:
                print_task(t)
        return True

    elif intent == "delete_task":
        if task_id:
            deleted = delete_task_by_id(task_id)
            if deleted:
                print("Deleted task:")
                print_task(deleted)
            else:
                print("Couldn't find that task.")
            return True

        if not title:
            print("Which task do you want to delete? Mention some words from its title.")
            return True

        matches = find_matching_tasks_by_title(title)
        if not matches:
            print("No matching task found.")
        elif len(matches) == 1:
            deleted = delete_task_by_id(matches[0]["id"])
            print("Deleted task:")
            print_task(deleted)
        else:
            print("Multiple tasks matched. Be more specific. Matching tasks:")
            for t in matches:
                print_task(t)
        return True

    elif intent == "help":
        print(
            "I can help you manage simple tasks. Try things like:\n"
            "- 'Add task: finish AI assignment by tomorrow 8 pm'\n"
            "- 'What do I need to do today?'\n"
            "- 'I finished the AI assignment'\n"
            "- 'Delete the gym reminder'\n"
            "- 'exit' to quit\n"
        )
        return True

    elif intent == "exit":
        print("Exiting. Stay on top of your deliverables. 👋")
        return False

    else:
        print("I didn't quite get that. Try asking for help.")
        return True


# --------- MAIN LOOP ---------

def main():
    print("=== Simple AI Concierge Agent ===")
    print("Type 'help' to see what I can do. Type 'exit' to quit.\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting. Bye.")
            break

        if not user_input:
            continue

        # Simple fast-path exit without calling LLM
        if user_input.lower() in {"exit", "quit"}:
            print("Exiting. Bye.")
            break

        parsed = call_llm(user_input)
        keep_running = handle_intent(parsed)
        if not keep_running:
            break


if __name__ == "__main__":
    main()
