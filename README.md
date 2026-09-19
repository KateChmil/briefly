# briefly

AI study spaces for students. Create a subject space, attach course files
(manual upload or import from Microsoft Teams — currently a local mock),
chat with an AI agent that interviews you about your goals, and get a
generated study plan, condensed notes, and an interactive sample test.

## Stack

- **Backend**: FastAPI + SQLAlchemy + SQLite, Anthropic Claude (`anthropic` SDK)
- **Frontend**: React + TypeScript + Vite + Tailwind CSS

## Setup

### Backend

```bash
cd backend
python -m venv .venv
.venv/Scripts/pip install -e ".[dev]"   # Windows
# source .venv/bin/activate && pip install -e ".[dev]"  # macOS/Linux
cp .env.example .env                    # add your ANTHROPIC_API_KEY
.venv/Scripts/uvicorn app.main:app --reload
```

API runs on http://localhost:8000 (docs at /docs).

### Frontend

```bash
cd frontend
npm install
npm run dev
```

App runs on http://localhost:5173 (proxies /api → :8000).

## How it works

1. **Create a space** — name a subject; the AI greets you and starts a short
   interview (goal, exam date, level, weak topics, weekly hours).
2. **Attach sources** — upload PDF/DOCX/PPTX/TXT files, or click
   "Import from Teams" to browse the mock Teams directory
   (`backend/app/mock_teams/<team>/<channel>/<file>`) and import files.
3. **Generation** — once the agent saves your profile (`save_student_profile`
   tool call), the backend generates three artifacts: a study plan, notes,
   and a sample test (interactive quiz in the UI).
4. **Tutor mode** — after setup, the chat becomes a tutor grounded in your
   sources. Artifacts can be regenerated individually.

## Teams integration

`app/services/teams_provider.py` defines a `TeamsProvider` protocol.
`MockTeamsProvider` reads a local directory; a real Microsoft Graph
implementation (Azure AD app + OAuth) can be swapped in without touching
the routers or UI.

## Tests

```bash
cd backend && .venv/Scripts/python -m pytest
cd frontend && npx vitest run && npm run build
```

Anthropic calls are mocked in tests; no API key needed to run them.

## Notes / limitations

- Single-user MVP — no auth.
- Source text is truncated to a context budget; no embeddings/RAG yet.
- Generation is synchronous (~10-30s); the UI shows a "generating" state.
