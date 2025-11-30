🧭 Concierge Agent — AI Task Automation Assistant

A lightweight AI-powered concierge that automates daily tasks through natural language.
Built with Streamlit + OpenAI. Handles your reminders, to-dos, completions, and quick task queries — all from a smart chat interface.

✨ Features
Capability	Description
🧠 Intent Parsing	Understands everyday language using LLM
📝 Task Management	Add, list, complete & delete tasks
🗂️ Task Board UI	Clean sidebar with cards, badges & icons
🎨 Custom Dark Theme	Polished design with gradients and shadows
📦 Local Storage	Tasks saved persistently (JSON DB)
💡 Smart Prompts	Suggestive hints to guide new users
🛠 Tech Stack

Python

Streamlit (Chat UI + Sidebar Task Board)

OpenAI API (Intent Interpretation)

dotenv (Secret key handling)

JSON data storage

🚀 Run Locally
Clone the repo
git clone https://github.com/<your-user>/concierge-agent.git
cd concierge-agent

Create venv & Install dependencies
python -m venv venv
.\venv\Scripts\activate   # Windows
# or
source venv/bin/activate # Mac/Linux

pip install -r requirements.txt

Add .env file
OPENAI_API_KEY=your_key_here

Run the app
python -m streamlit run app.py


🎯 App opens at: http://localhost:8501

📌 Project Structure
concierge-agent/
│─ app.py
│─ tasks.json        # created automatically
│─ .env              
│─ requirements.txt
└─ README.md



👤 Author

Mustaqeem Shaikh
AI & Data Engineering Enthusiast

📍 Pune, India
