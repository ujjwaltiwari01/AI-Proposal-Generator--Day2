<div align="center">

<h1>🚀 AI Proposal Generator</h1>

<p>
  <img src="https://img.shields.io/badge/Framework-Streamlit-ff4b4b?logo=streamlit&logoColor=white" />
  <img src="https://img.shields.io/badge/AI-LangChain-blue?logo=OpenAI&logoColor=white" />
  <img src="https://img.shields.io/badge/Model-OpenAI%20GPT-brightgreen" />
  <img src="https://img.shields.io/badge/Exports-PDF%20%7C%20DOCX%20%7C%20HTML-purple" />
</p>

<p>
  <a href="#-quick-start" style="text-decoration:none">
    <img src="https://img.shields.io/badge/▶️%20Run%20Locally-000?style=for-the-badge" />
  </a>
  <a href="#-features" style="text-decoration:none">
    <img src="https://img.shields.io/badge/✨%20Features-222?style=for-the-badge" />
  </a>
  <a href="#-screenshots" style="text-decoration:none">
    <img src="https://img.shields.io/badge/🖼️%20Screenshots-444?style=for-the-badge" />
  </a>
</p>

</div>

---

> Ever spent hours writing client proposals — only to realize they all sound the same?
>
> Imagine this: you just finished a client call, dropped a few notes, uploaded their logo and transcript… and boom — in seconds, an AI generates a ready‑to‑send business proposal, perfectly tailored to their goals, tone, and budget. No templates. No copy‑paste. Just pure personalization.
>
> Day 2 of our “30 Days, 30 AI Agents” — meet your new proposal co‑pilot.

---

## 🌈 What is this?
- An AI agent that crafts client proposals that feel truly yours.
- Give it: company name, client name, project title, timeline, goals, tone.
- Add optional transcripts, assets, or notes — it blends everything into your brand voice (formal, friendly, founder‑style — you choose).
- One click. No writer’s block. No wasted hours.
- Open source. Remix it for your clients.

## ✨ Features
- Streamlit UI with super-simple sidebar inputs
- 12-section proposal with per‑section regeneration and inline editing
- Quality checker with grade + suggestions
- Exports: PDF, DOCX, HTML
- Copy to Google Docs with styling
- Local drafts under `data/` with versioning
- Privacy Mode to avoid saving transcripts

---

## 🧒 Setup So Easy A 5‑Year‑Old Can Do It

> Little helper: Ask an adult to install Python. Then follow the pictures and type the lines exactly!

### 1) Get the tools
- Install Python 3.11 or newer: https://www.python.org/downloads/
- Optional (for fancy PDFs): Install wkhtmltopdf: https://wkhtmltopdf.org/downloads.html

### 2) Open the project folder
- On Windows, open PowerShell and run:

```powershell
cd "d:\30 days 30 agent\day 2 proposal generator fina\ai-proposal-agent"
```

### 3) Make a tiny sandbox (virtual env)
```powershell
python -m venv .venv
.venv\Scripts\activate
```

### 4) Add the magic (install packages)
```powershell
pip install -r requirements.txt
```

### 5) Tell the app your AI key
- Copy this file: `.streamlit/secrets.toml.example` → `.streamlit/secrets.toml`
- Open `.streamlit/secrets.toml` and put your key like this:

```toml
OPENAI_API_KEY = "sk-your-key-here"
# Optional
# OPENAI_ORG_ID = "org_..."
# OPENAI_PROJECT = "proj_..."
```

### 6) Press the big GO button (run the app)
```powershell
streamlit run app.py
```
- If that doesn’t work, try:
```powershell
python -m streamlit run app.py
```
- Then open the link it shows (usually http://localhost:8501)

---

## 🧭 How to Use
1. Fill the left sidebar: Company, Client, Project Title, Goals, Budget, Timeline, Tone.
2. Paste transcript or upload text/doc files (optional). Upload logo (optional).
3. Click “Generate Proposal”.
4. Edit any section inline. Regenerate a single section if you want.
5. Export as PDF / DOCX / HTML or copy to Google Docs.
6. Save Draft to keep a version in `data/`.

> Tip: Timeline must be at least 3 characters (e.g., "6 weeks").

---



---

## 🧰 Troubleshooting
- “Generate Proposal” button greyed out
  - Make sure the left sidebar fields are filled: project title, goals, budget, timeline (≥3 chars).
- “No API key / auth error”
  - Check `.streamlit/secrets.toml` for `OPENAI_API_KEY`, or use the override field in the app sidebar.
- PDF looks plain
  - Install wkhtmltopdf and make it visible to the app. On Windows you can do:
  ```powershell
  setx WKHTMLTOPDF_PATH "C:\\Program Files\\wkhtmltopdf\\bin\\wkhtmltopdf.exe"
  ```
  Then restart the terminal and the app.
- Port 8501 already used
  - Streamlit will offer a new port automatically.

---

## 🧪 Quick Test
```bash
pytest tests/
```

---

## 🧱 Tech Stack
- Streamlit UI
- LangChain + OpenAI (ChatOpenAI) for generation
- ReportLab and/or wkhtmltopdf for PDFs
- python-docx for DOCX

---

## 🛠️ Customize
- Prompts live in `prompts/`
- Validation rules in `validators.py`
- Export helpers in `ai_proposal_agent/utils.py`

---

## 🌟 Why we built this
> “This is just Day 2.”

We wanted a real, usable agent that saves hours — not a toy demo. If it helps you ship proposals faster, give it a ⭐ and share what you build.

---

<div align="center">

<a href="#-quick-start" style="text-decoration:none;margin:8px;">
  <img src="https://img.shields.io/badge/🚀%20I%27m%20Ready%20—%20Let%27s%20Go!-0b3d91?style=for-the-badge&labelColor=101010" />
</a>

</div>
