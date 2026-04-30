# EvoCode 🤖

<div align="center">

**AI-Powered Agentic Developer Dashboard**

*Bridges the gap between client feature requests and production-ready pull requests — automatically.*

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Next.js](https://img.shields.io/badge/Next.js-14-black?style=flat-square&logo=next.js&logoColor=white)](https://nextjs.org/)
[![LangChain](https://img.shields.io/badge/LangChain-Gemini_2.5_Flash-1C3C3C?style=flat-square&logo=langchain&logoColor=white)](https://langchain.com/)
[![License](https://img.shields.io/badge/License-Demo-orange?style=flat-square)](./LICENSE)

</div>

---

## 🌟 What is EvoCode?

EvoCode is a full-stack platform that acts as an **AI Product Manager + AI Software Engineer**. Developers submit feature requests or bug reports through a dashboard, an AI planning agent generates a confidence-scored implementation plan, and — upon approval — an AI coding agent reads the codebase, writes the fix, runs tests in a sandbox, and **opens a GitHub Pull Request automatically**.

No more back-and-forth tickets. No more hallucinated code. Just request → plan → review → ship.

---

## ✨ Key Features

| Feature | Description |
|---|---|
| 🧠 **AI Planning Agent** | Gemini 2.5 Flash generates a structured implementation plan with a 0–100 Confidence Score |
| 🔒 **Dynamic Guardrails** | High-risk changes (confidence < 70) are flagged, blocking auto-execution and surfacing a strategy guide |
| 🤖 **AI Coding Agent** | LangChain agent with file-read/write tools — reads actual codebase files before writing any code |
| 🧪 **Automated Sandbox** | Runs `npm test` against generated code in an isolated subprocess before any commit |
| 🚀 **GitHub Automation** | Creates a feature branch, commits changes, and opens a Pull Request via the GitHub API |
| 📡 **Real-time Streaming** | Live agent execution logs streamed to the dashboard via Server-Sent Events (SSE) |
| 📋 **Triage Dashboard** | Lists all feature requests with full status tracking |
| 🔁 **Human-in-the-Loop** | Two-step flow: Plan → Review → Execute. You always stay in control |

---

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│                    Frontend (Next.js)                │
│  Landing Page → Sign Up → Triage Dashboard          │
│  Developer Build View (Plan Review + Execution SSE) │
└────────────────────┬────────────────────────────────┘
                     │ REST + SSE
┌────────────────────▼────────────────────────────────┐
│                 Backend (FastAPI)                    │
│                                                     │
│  POST /api/report              → Save feature req   │
│  POST /api/issues/{id}/plan    → AI Planning Agent  │
│  POST /api/issues/{id}/execute → AI Coding Agent    │
│  GET  /api/features/{id}/execute/stream → SSE logs  │
│                                                     │
│  ┌──────────────┐  ┌───────────────┐  ┌──────────┐ │
│  │ AgentOrchest.│→ │LangChain      │→ │ GitHub   │ │
│  │ (Coordinator)│  │CodeAgent+Tools│  │ Manager  │ │
│  └──────────────┘  └──────┬────────┘  └──────────┘ │
│                           │                         │
│                    ┌──────▼───────┐                 │
│                    │SandboxRunner │                 │
│                    │  (npm test)  │                 │
│                    └──────────────┘                 │
│                                                     │
│       SQLite DB: IssueReports · FixAttempts · PRs   │
└─────────────────────────────────────────────────────┘
```

### Agentic Flow (Happy Path)

```
Submit Request → [AI Plan + Confidence Score] → Developer Reviews
    → APPROVE → Coding Agent reads files → Writes fix
    → Sandbox runs npm test → Tests pass → GitHub PR created ✅
                                         → Tests fail → Retry (max 3)
```

### Guardrail Path (Assist Mode)

```
Submit Request → [AI Plan, Confidence < 70] → APPROVE button disabled
    → Strategy Guide displayed → Developer codes manually in IDE
```

---

## 🧠 How the Confidence Score Works

The AI planner (Gemini) evaluates each request and assigns a score from 0–100:

| Score | Risk Level | Blocked? | Action |
|---|---|---|---|
| **90–100** | 🟢 Low — text/CSS/label change | No | ✅ APPROVE button enabled |
| **70–89** | 🟡 Medium — component logic change | No | ✅ APPROVE button enabled |
| **< 70** | 🔴 High — multi-file / DB / API change | **Yes** | 🔒 Assist Mode: strategy guide shown |

---

## 📂 Project Structure

```
evo-code/
├── docs/
│   ├── architecture.md                    # V1 Mermaid architecture diagrams
│   └── architecture-v1-prototype.md       # V2 vision & guardrail flow diagrams
│
└── evocode-v1/
    ├── backend/                           # FastAPI Python server
    │   ├── main.py                        # All API routes & lifespan hooks
    │   ├── models.py                      # SQLAlchemy ORM models
    │   ├── database.py                    # DB engine & session factory
    │   ├── config.py                      # App configuration
    │   ├── requirements.txt               # Python dependencies
    │   ├── .env                           # ⚠️ Environment variables (gitignored)
    │   ├── simulate.py                    # Manual simulation script
    │   ├── reset_issue.py                 # Utility to reset a stuck issue
    │   ├── test_complete_flow.py          # End-to-end integration test
    │   ├── test_github.py                 # GitHub API tests
    │   ├── test_langchain.py              # LangChain agent tests
    │   ├── test_sandbox.py                # Sandbox runner tests
    │   └── utils/
    │       ├── agent_orchestrator.py      # Chains all agents together
    │       ├── code_agent_with_tools.py   # LangChain agent + file R/W tools
    │       ├── langchain_tools.py         # Custom LangChain tools (read/write file)
    │       ├── langchain_agent.py         # Simple chain (non-tool version)
    │       ├── sandbox_runner.py          # Runs npm test in subprocess
    │       ├── github_manager.py          # PyGitHub: branch, commit, PR
    │       ├── streaming_callback.py      # LangChain SSE streaming handler
    │       ├── orchestrator.py            # Alternative orchestrator (legacy)
    │       ├── initialization.py          # Startup environment checks
    │       ├── system_checks.py           # Node/npm/project validation
    │       ├── db_recovery.py             # Reset stuck features in DB
    │       ├── heartbeat.py               # DB heartbeat updater
    │       ├── process_manager.py         # Subprocess management helpers
    │       └── test_config_helper.py      # Test environment bootstrapper
    │
    ├── frontend/                          # Next.js 14 TypeScript app
    │   ├── app/
    │   │   ├── page.js                    # Landing page
    │   │   ├── layout.js                  # Root layout
    │   │   ├── globals.css                # Global styles
    │   │   ├── signup/                    # Sign-up page
    │   │   ├── developer/
    │   │   │   ├── triage/                # Triage dashboard (feature list)
    │   │   │   └── build/                 # Plan review & execution view
    │   │   ├── components/
    │   │   │   └── ui/
    │   │   │       ├── border-beam.tsx    # Animated border component
    │   │   │       └── spotlight.tsx      # Spotlight effect component
    │   │   └── lib/                       # Utility functions
    │   ├── package.json
    │   ├── tailwind.config.js
    │   └── tsconfig.json
    │
    └── test-target/                       # Sample project the AI agent fixes
        ├── src/
        │   └── checkout.js                # Target file with intentional bugs
        ├── tests/                         # Jest tests for checkout.js
        └── package.json
```

---

## 🗄️ Database Schema

| Table | Description |
|---|---|
| `issue_reports` | Every feature request / bug report submitted via the dashboard |
| `fix_attempts` | Each attempt by the coding agent (up to 3 retries on test failure) |
| `pull_requests` | Linked GitHub PR record once tests pass |

**IssueReport Status Flow:**
```
pending → planned → approved → processing → completed
                                          ↘ failed
```

---

## 🚀 Getting Started

### Prerequisites

| Requirement | Version |
|---|---|
| Python | 3.10+ |
| Node.js & npm | 18+ |
| GitHub Account | Personal Access Token with `repo` scope |
| Google Gemini API Key | [Get one here](https://aistudio.google.com/app/apikey) |

---

### 1. Clone the Repository

```bash
git clone https://github.com/Hanuaditya/evo-code.git
cd evo-code/evocode-v1
```

---

### 2. Backend Setup

```bash
cd backend
```

**Install Python dependencies:**

```bash
pip install -r requirements.txt
```

**Configure environment variables** by creating/editing the `.env` file:

```env
# ── GitHub Integration ──────────────────────────────
GITHUB_TOKEN=your_github_personal_access_token
REPO_OWNER=your_github_username
REPO_NAME=your_target_repo_name

# ── AI ──────────────────────────────────────────────
GEMINI_API_KEY=your_gemini_api_key

# ── Target Configuration ────────────────────────────
# Relative path of the file the AI agent will modify
TARGET_FILE_PATH=app/components/About.jsx

# Absolute path to the cloned target repo on disk
REPO_PATH=C:\path\to\your\target-repo

# ── Sandbox / Test Settings ─────────────────────────
TEST_TIMEOUT=30
TEST_AUTO_SETUP=true
SANDBOX_ENABLE_TESTS=true
SANDBOX_CREATE_MINIMAL_TESTS=true
```

> ⚠️ **Never commit your `.env` file.** It is already listed in `.gitignore`.

**Start the backend server:**

```bash
uvicorn main:app --reload --port 8000
```

The API will be available at **`http://localhost:8000`**.
Interactive API docs (Swagger UI) at **`http://localhost:8000/docs`**.

---

### 3. Frontend Setup

```bash
cd ../frontend
npm install
npm run dev
```

The frontend runs on **`http://localhost:3001`** (port 3001 is configured in `package.json`).

---

### 4. Test-Target Setup (for the AI Sandbox)

The `test-target/` folder is a sample Node.js project the coding agent reads and modifies. It must be set up with its own dependencies for sandbox testing to work:

```bash
cd ../test-target
npm install
```

---

## ⚡ Quick Start Checklist

```
☐  Clone repo & cd into evocode-v1/backend
☐  pip install -r requirements.txt
☐  Create .env with GITHUB_TOKEN, REPO_OWNER, REPO_NAME, GEMINI_API_KEY, REPO_PATH
☐  uvicorn main:app --reload --port 8000
☐  cd ../frontend && npm install && npm run dev
☐  cd ../test-target && npm install
☐  Open http://localhost:3001 🎉
```

---

## 🔌 API Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Health check |
| `GET` | `/health` | Detailed health status |
| `POST` | `/api/report` | Submit a new bug/feature request |
| `GET` | `/api/features` | List all feature requests |
| `GET` | `/api/features/{id}` | Get full feature details + plan |
| `POST` | `/api/issues/{id}/plan` | **Step 1:** Generate AI implementation plan |
| `POST` | `/api/issues/{id}/execute` | **Step 2:** Approve plan & start coding agent |
| `GET` | `/api/issues/{id}/status` | Poll current status of an issue |
| `GET` | `/api/features/{id}/execute/stream` | **SSE:** Stream live agent execution logs |
| `POST` | `/api/features/{id}/reset` | Reset a stuck feature to `failed` |
| `POST` | `/api/features/{id}/force-stop` | Force-stop a running feature |
| `GET` | `/api/debug/sandbox-status` | Inspect sandbox environment health |

> Full interactive docs available at `http://localhost:8000/docs` when the server is running.

---

## 🧪 Running Tests

**Backend integration tests:**

```bash
cd backend

python test_complete_flow.py   # End-to-end pipeline test
python test_github.py          # GitHub API connectivity
python test_sandbox.py         # Sandbox runner validation
python test_langchain.py       # LangChain agent smoke test
```

**Frontend linting:**

```bash
cd frontend
npm run lint
```

**Test-target unit tests (what the sandbox runs against generated code):**

```bash
cd test-target
npm test
```

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| **Frontend** | Next.js 14, React 18, TypeScript, Tailwind CSS |
| **Animations** | Framer Motion (`motion`), `@react-spring/web`, `cobe` |
| **UI Components** | Radix UI, Lucide React |
| **Backend** | Python 3.10+, FastAPI, Uvicorn |
| **AI / LLM** | LangChain, `langchain-google-genai` (Gemini 2.5 Flash) |
| **Database** | SQLite via SQLAlchemy ORM |
| **GitHub Automation** | PyGitHub |
| **Streaming** | `sse-starlette`, Server-Sent Events |
| **Sandbox** | Node.js subprocess + Jest |

---

## 📋 Environment Variables Reference

| Variable | Required | Description |
|---|---|---|
| `GITHUB_TOKEN` | ✅ | GitHub Personal Access Token (`repo` scope required) |
| `REPO_OWNER` | ✅ | GitHub username owning the target repo |
| `REPO_NAME` | ✅ | Name of the GitHub repo the agent will PR into |
| `GEMINI_API_KEY` | ✅ | Google Gemini API key |
| `TARGET_FILE_PATH` | ✅ | Relative path of the file the agent targets |
| `REPO_PATH` | ✅ | Absolute local path to the cloned target repo |
| `TEST_TIMEOUT` | ❌ | Sandbox test timeout in seconds (default: `30`) |
| `TEST_AUTO_SETUP` | ❌ | Auto-install npm deps before testing (default: `true`) |
| `SANDBOX_ENABLE_TESTS` | ❌ | Whether to run tests before committing (default: `true`) |
| `SANDBOX_CREATE_MINIMAL_TESTS` | ❌ | Create stub tests if none exist (default: `true`) |

---

## 🗺️ Roadmap

- [ ] User authentication (OAuth / magic link)
- [ ] Multi-repo support from the dashboard
- [ ] Vote-based feature request aggregation (upvote system)
- [ ] GitHub Webhook integration (auto-triage on issue creation)
- [ ] Support for Python and other language test runners
- [ ] V2 agentic architecture with parallel tool execution

---

## 🤝 Contributing

This project is currently in active development as a hackathon prototype. Feel free to open issues or pull requests if you'd like to contribute.

1. Fork the repository
2. Create a feature branch (`git checkout -b feat/your-feature`)
3. Commit your changes (`git commit -m 'feat: add your feature'`)
4. Push to the branch (`git push origin feat/your-feature`)
5. Open a Pull Request

---

## 📄 License

This project is for demonstration and hackathon purposes.

---

<div align="center">
  Built with ❤️ by <strong>Hanuaditya</strong>
</div>
