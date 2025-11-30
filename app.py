import json
import os
import uuid
from datetime import datetime
from typing import List, Dict, Any

import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI

# ---------------- CONFIG ----------------

TASKS_FILE = "tasks.json"
SYSTEM_PROMPT = """
You are a helpful 'concierge' AI that manages a simple task list for the user.

You MUST respond ONLY with a single JSON object and NOTHING else. No explanations.

JSON schema:
{
  "intent": "add_task" | "list_tasks" | "complete_task" | "delete_task" | "help" | "exit",
  "task_title": string or null,
  "task_due": string or null,
  "task_id": string or null
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

# ---------------- LLM SETUP ----------------

load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")

if not api_key:
    st.error("OPENAI_API_KEY not found. Please set it in a .env file.")
    st.stop()

client = OpenAI(api_key=api_key)


def call_llm(user_message: str) -> Dict[str, Any]:
    """
    Send the user message to the LLM and get back a JSON object with intent, task info.
    """
    response = client.chat.completions.create(
        model="gpt-4.1-mini",  # adjust model if needed
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        temperature=0.1,
    )

    content = response.choices[0].message.content.strip()

    # Try parse JSON
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        data = {
            "intent": "help",
            "task_title": None,
            "task_due": None,
            "task_id": None,
        }
    return data


# ---------------- TASK STORAGE ----------------

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


# ---------------- UI HELPERS ----------------

def format_task_text(task: Dict[str, Any]) -> str:
    status_icon = "✅" if task["status"] == "completed" else "⏳"
    due_str = f" | Due: {task['due']}" if task["due"] else ""
    return f"{status_icon} {task['title']} ({task['id'][:8]}){due_str}"


def task_status_badge(task: Dict[str, Any]) -> str:
    if task["status"] == "completed":
        return '<span class="badge done">Done</span>'
    return '<span class="badge pending">Pending</span>'


def render_task_card(task: Dict[str, Any]) -> None:
    icon = "✅" if task["status"] == "completed" else "🧩"
    due_html = f"<div class='task-due'>Due: {task['due']}</div>" if task["due"] else ""
    html = f"""
    <div class="task-card">
        <div class="task-header">
            <span class="task-icon">{icon}</span>
            <span class="task-title">{task['title']}</span>
        </div>
        <div class="task-meta">
            {due_html}
            <div class="task-id">ID: {task['id'][:8]}</div>
            {task_status_badge(task)}
        </div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


def handle_intent(parsed: Dict[str, Any]) -> str:
    """
    Handle the parsed intent and return a natural language response string.
    """
    intent = parsed.get("intent")
    title = parsed.get("task_title")
    due = parsed.get("task_due")
    task_id = parsed.get("task_id")

    if intent == "exit":
        return "I can’t close the app, but you can close the tab. You’re good to go for now. 🧭"

    if intent == "add_task":
        if not title:
            return "I couldn't understand the task title. Try something like: `Add task: submit assignment by tomorrow`."
        task = add_task(title, due)
        return "Task added:\n" + format_task_text(task)

    if intent == "list_tasks":
        tasks = list_tasks()
        if not tasks:
            return "You have no tasks yet. You’re all clear. 🚀"
        lines = ["Here are your tasks:"]
        for t in tasks:
            lines.append("- " + format_task_text(t))
        return "\n".join(lines)

    if intent == "complete_task":
        if task_id:
            updated = complete_task_by_id(task_id)
            if updated:
                return "Marked as completed:\n" + format_task_text(updated)
            else:
                return "I couldn't find that task."

        if not title:
            return "Which task did you complete? Mention some words from its title."

        matches = find_matching_tasks_by_title(title)
        if not matches:
            return "No matching task found."
        if len(matches) == 1:
            updated = complete_task_by_id(matches[0]["id"])
            return "Marked as completed:\n" + format_task_text(updated)
        else:
            lines = ["Multiple tasks matched. Please be more specific. Matching tasks:"]
            for t in matches:
                lines.append("- " + format_task_text(t))
            return "\n".join(lines)

    if intent == "delete_task":
        if task_id:
            deleted = delete_task_by_id(task_id)
            if deleted:
                return "Deleted task:\n" + format_task_text(deleted)
            else:
                return "I couldn't find that task."

        if not title:
            return "Which task do you want to delete? Mention some words from its title."

        matches = find_matching_tasks_by_title(title)
        if not matches:
            return "No matching task found."
        if len(matches) == 1:
            deleted = delete_task_by_id(matches[0]["id"])
            return "Deleted task:\n" + format_task_text(deleted)
        else:
            lines = ["Multiple tasks matched. Please be more specific. Matching tasks:"]
            for t in matches:
                lines.append("- " + format_task_text(t))
            return "\n".join(lines)

    if intent == "help":
        return (
            "I can help you manage simple tasks. Try things like:\n"
            "- `Add task: finish AI assignment by tomorrow 8 pm`\n"
            "- `What do I need to do today?`\n"
            "- `I finished the AI assignment`\n"
            "- `Delete the gym reminder`\n"
        )

    return "I didn't quite get that. Try asking for `help`."


# ---------------- STREAMLIT APP ----------------

st.set_page_config(page_title="Concierge Agent", page_icon="🧭", layout="wide")

# Custom CSS for styling
st.markdown(
    """
    <style>
    .stApp {
        background: radial-gradient(circle at top left, #0f172a 0, #020617 40%, #020617 100%);
        color: #e5e7eb;
        font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    .main-header {
        padding: 0.75rem 1rem 0.5rem 1rem;
        border-radius: 1rem;
        background: linear-gradient(135deg, #0ea5e9, #6366f1);
        color: white;
        box-shadow: 0 18px 45px rgba(15, 23, 42, 0.7);
        margin-bottom: 0.75rem;
    }
    .main-header h1 {
        margin: 0;
        font-size: 1.7rem;
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }
    .main-header p {
        margin: 0.2rem 0 0 0;
        opacity: 0.95;
        font-size: 0.9rem;
    }
    .task-card {
        border-radius: 0.8rem;
        padding: 0.6rem 0.8rem;
        margin-bottom: 0.5rem;
        background: rgba(15, 23, 42, 0.85);
        border: 1px solid rgba(148, 163, 184, 0.35);
        box-shadow: 0 6px 16px rgba(15, 23, 42, 0.5);
    }
    .task-header {
        display: flex;
        align-items: center;
        gap: 0.4rem;
        margin-bottom: 0.2rem;
    }
    .task-icon {
        font-size: 1.1rem;
    }
    .task-title {
        font-weight: 600;
        font-size: 0.9rem;
        color: #e5e7eb;
    }
    .task-meta {
        display: flex;
        flex-direction: column;
        gap: 0.15rem;
        font-size: 0.75rem;
        color: #9ca3af;
    }
    .task-due {
        color: #e5e7eb;
    }
    .task-id {
        opacity: 0.8;
        font-family: "JetBrains Mono", ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
    }
    .badge {
        display: inline-block;
        padding: 0.1rem 0.35rem;
        border-radius: 999px;
        font-size: 0.65rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.04em;
        margin-top: 0.1rem;
        width: fit-content;
    }
    .badge.pending {
        background: rgba(253, 224, 71, 0.15);
        color: #facc15;
        border: 1px solid rgba(250, 204, 21, 0.6);
    }
    .badge.done {
        background: rgba(34, 197, 94, 0.12);
        color: #4ade80;
        border: 1px solid rgba(52, 211, 153, 0.7);
    }
    .sidebar-block {
        padding: 0.5rem 0.25rem 0.5rem 0.25rem;
    }
    .hint-box {
        border-radius: 0.75rem;
        border: 1px dashed rgba(148, 163, 184, 0.7);
        padding: 0.6rem 0.8rem;
        font-size: 0.8rem;
        margin-top: 0.4rem;
        background: rgba(15, 23, 42, 0.7);
    }
    .hint-box code {
        font-size: 0.75rem;
    }
    .chat-container {
        background: rgba(15, 23, 42, 0.85);
        border-radius: 1rem;
        padding: 0.75rem 0.9rem 0.9rem 0.9rem;
        box-shadow: 0 16px 50px rgba(15, 23, 42, 0.85);
        border: 1px solid rgba(148, 163, 184, 0.4);
        margin-top: 0.5rem;
    }
    .stChatMessage {
        font-size: 0.9rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# Layout: wide with two columns
left_col, right_col = st.columns([2.2, 1])

with left_col:
    # Header
    st.markdown(
        """
        <div class="main-header">
            <h1>🧭 Concierge Agent</h1>
            <p>Your lightweight AI ops partner for day-to-day task execution.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("<div class='chat-container'>", unsafe_allow_html=True)

    # Initialize chat history
    if "messages" not in st.session_state:
        st.session_state["messages"] = []

    # Render chat history
    for msg in st.session_state["messages"]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Chat input
    user_input = st.chat_input("Type a request, e.g., 'Add task: revise ML notes by tonight'")

    if user_input:
        # Add user message
        st.session_state["messages"].append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        parsed = call_llm(user_input)
        reply = handle_intent(parsed)

        # Add assistant message
        st.session_state["messages"].append({"role": "assistant", "content": reply})
        with st.chat_message("assistant"):
            st.markdown(reply)

    st.markdown("</div>", unsafe_allow_html=True)

with right_col:
    st.markdown("### 📋 Task Board")

    tasks = list_tasks()
    pending = sum(1 for t in tasks if t["status"] == "pending")
    done = sum(1 for t in tasks if t["status"] == "completed")

    # Small KPIs
    kpi1, kpi2 = st.columns(2)
    kpi1.metric("Open Items", pending)
    kpi2.metric("Closed Items", done)

    st.markdown("<div class='sidebar-block'>", unsafe_allow_html=True)

    if not tasks:
        st.write("No tasks yet. Add something and I’ll track it for you.")
    else:
        for t in tasks:
            render_task_card(t)

    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown(
        """
        <div class="hint-box">
        <strong>Quick prompts</strong><br><br>
        <code>Add task: finish AI assignment by tomorrow 8pm</code><br>
        <code>What are my tasks?</code><br>
        <code>I finished AI assignment</code><br>
        <code>Delete the gym reminder</code>
        </div>
        """,
        unsafe_allow_html=True,
    )
    # ---------------- FOOTER ----------------
st.markdown(
    """
    <hr style="margin-top: 2.5rem; border: 0.5px solid rgba(148, 163, 184, 0.4);" />
    <div style="text-align: center; padding: 0.4rem; color: #9ca3af; font-size: 0.8rem;">
        Built by <strong style="color:#0ea5e9; text-shadow:0 0 6px rgba(14,165,233,0.8);">
    Mustaqeem Shaikh
</strong>
</div>
    """,
    unsafe_allow_html=True
)

