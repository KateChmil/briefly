# briefly

AI study planner for students. Create a subject, bring in your course materials
(upload files, import from Microsoft Teams — currently a local mock — or pull in
your Canvas/Outlook calendar), chat with an AI agent about your goals, and get:

- a **dated study plan** you can tick off, shown on a **calendar** next to your classes and exams
- condensed **notes**, an interactive **sample test** and **flashcards**
- a **tutor chat** grounded in your materials that re-plans when your situation changes

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

### Demo data (no API key needed)

```bash
cd backend
python -m scripts.seed_demo --reset   # two subjects with plans, notes, tests, flashcards and a calendar
```

Use it to develop the UI, or as a fallback if Wi-Fi or the API fails during a live demo.

## How it works

1. **Create a subject** — the AI greets you and interviews you (goal, exam date,
   level, weak topics, weekly hours). It saves your answers with a tool call.
2. **Attach materials** — upload PDF/DOCX/PPTX/TXT (drag & drop), or browse the mock Teams
   directory (`backend/app/mock_teams/<team>/<channel>/<file>`).
3. **Generation runs in the background** — the plan, notes, test and flashcards are generated
   in parallel and appear one by one. The plan, test and flashcards come back as validated,
   structured data (forced tool calls, retried once if malformed). If something fails the
   space is *not* marked ready; a message in the chat explains and **Generate** retries it.
4. **Calendar** — plan sessions, exams and classes in a month view. Add events by hand, import an
   `.ics` file or a live feed URL (Canvas → Calendar → *Calendar Feed*; Outlook and Google offer
   the same), and export your plan as `.ics` for your phone calendar.
5. **Tutor mode** — answers use the most relevant excerpts of your materials (keyword retrieval
   over the whole text, not just the beginning). Tell it "I only have 4 hours a week now" and it
   updates your profile and rebuilds the plan (ticked sessions are kept).

## Teams and Canvas

`app/services/teams_provider.py` defines a `TeamsProvider` protocol; `MockTeamsProvider` reads a
local directory. A real Microsoft Graph provider (Azure AD app + OAuth) can be swapped in without
touching the routers or UI. Canvas and Outlook schedules work today through calendar feeds
(`app/services/ics.py`), which need no OAuth.

## Deploying

The frontend is a static Vite build and deploys to **Vercel** as-is (`frontend/vercel.json`):

1. Import the repo in Vercel and set the **root directory** to `frontend`.
2. Set `VITE_API_URL` to your backend's public URL (no trailing slash).
3. On the backend set `CORS_ORIGINS` to your Vercel URL.

The **backend should run on a normal server** (Render, Railway, Fly.io…), not Vercel's
serverless functions: it keeps SQLite/uploaded files on disk and finishes generation in a
background thread after responding, both of which serverless platforms discard. For a hackathon
demo, running both locally (or the seeded demo data) is the safest option.

## Tests

```bash
cd backend && .venv/Scripts/python -m pytest
cd frontend && npx tsc -b && npx vitest run && npm run build
```

Anthropic calls are mocked in tests; no API key needed to run them.

## Limitations

- Single-user MVP — no auth.
- Recurring calendar events support daily/weekly rules only.
- No embeddings: retrieval is keyword-based, which is enough for course notes.
- Study plans depend on the AI; always skim them before relying on them.
