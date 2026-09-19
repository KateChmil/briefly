---
agent: devin-local
session: oasis-swordfish
created: 2026-09-19T09:12:49Z
---
# Briefly — Student Study-Space Web App (MVP)

Build a FastAPI + React app where students create subject spaces, attach sources via manual upload or a mocked Microsoft Teams provider, get interviewed by a Claude chat agent, and receive a generated study plan, notes, and a sample test.

## Summary

Greenfield project (empty repo at `C:\PythonGOIT\briefly`). Build "Briefly": a web app where a student creates a **subject space**, attaches study materials (manual file upload or a mock Microsoft Teams source behind a provider interface), gets interviewed by a Claude-powered chat agent (exam date, goals, level, schedule), and receives generated **study plan**, **notes**, and an **interactive sample test**. Stack: FastAPI + SQLAlchemy + SQLite backend, React + TypeScript (Vite + Tailwind) frontend, Anthropic API via `anthropic` SDK.

## Architecture

```
briefly/
  backend/
    pyproject.toml            # deps: fastapi, uvicorn, sqlalchemy, anthropic,
                              # pydantic-settings, python-multipart,
                              # pypdf, python-docx, python-pptx, pytest, httpx
    .env.example              # ANTHROPIC_API_KEY, ANTHROPIC_MODEL
    app/
      main.py                 # app factory, CORS, router registration
      config.py               # pydantic-settings (api keys, db url, storage dir)
      db.py                   # engine, session, Base
      models.py               # ORM models (below)
      schemas.py              # Pydantic request/response DTOs
      routers/
        spaces.py             # CRUD subject spaces
        sources.py            # manual upload + list/delete sources
        teams.py              # browse mock teams/channels/files, import file
        chat.py               # POST message -> agent reply
        artifacts.py          # list/get artifacts, POST regenerate
      services/
        llm.py                # Anthropic client wrapper (env-configured model)
        extract.py            # text extraction: pdf/docx/pptx/txt -> plain text
        teams_provider.py     # TeamsProvider protocol + MockTeamsProvider
        agent.py              # interview agent: system prompt + tool use
        generation.py         # build context from sources -> generate artifacts
      storage/                # uploaded/imported files on disk
      mock_teams/             # fixture files (sample pdf/txt/docx per channel)
    tests/
      test_spaces.py
      test_sources_extract.py
      test_agent.py           # mocked Anthropic client
      test_artifacts.py
      test_teams.py
  frontend/
    package.json              # vite, react, react-dom, typescript, tailwindcss,
                              # react-router-dom, react-markdown, vitest
    index.html, vite.config.ts, tailwind.config.js, tsconfig.json
    src/
      main.tsx, App.tsx       # router
      api/client.ts           # typed fetch wrappers for backend API
      types.ts                # shared TS types mirroring schemas
      pages/
        SpacesPage.tsx        # list spaces + create-new dialog
        SpacePage.tsx         # 3-pane layout: sources | chat | artifacts
      components/
        ChatPanel.tsx         # message list + input
        SourceList.tsx        # attached sources, upload button, Teams picker
        TeamsPicker.tsx       # modal browsing mock teams/channels/files
        ArtifactTabs.tsx      # Plan / Notes / Sample test tabs
        QuizView.tsx          # interactive rendering of sample test JSON
      components/ui/          # small primitives (button, card, spinner)
    src/__tests__/            # minimal vitest component tests
```

## Data model (SQLite via SQLAlchemy)

- **SubjectSpace**: `id`, `name`, `status` (`interviewing` | `generating` | `ready`), `profile_json` (exam date, goal, level, weekly hours, weak topics — filled by agent), `created_at`
- **Source**: `id`, `space_id`, `origin` (`upload` | `teams`), `filename`, `mime_type`, `storage_path`, `extracted_text`, `teams_ref` (nullable JSON: team/channel/file ids)
- **ChatMessage**: `id`, `space_id`, `role` (`user` | `assistant`), `content`, `created_at`
- **Artifact**: `id`, `space_id`, `kind` (`study_plan` | `notes` | `sample_test`), `format` (`markdown` | `json`), `content`, `version`, `created_at`

## Backend design

1. **Spaces API** — `POST /spaces` (create, status=`interviewing`), `GET /spaces`, `GET /spaces/{id}`, `DELETE /spaces/{id}`.
2. **Sources API** — `POST /spaces/{id}/sources` (multipart upload) → save to `storage/`, extract text via `extract.py`, store `extracted_text`. `GET`/`DELETE` sources.
3. **Teams (mock)** — `TeamsProvider` protocol with `list_teams()`, `list_channels(team_id)`, `list_files(channel_id)`, `get_file(file_id)`. `MockTeamsProvider` reads `mock_teams/` fixture dir (e.g. "Biology 101" team → "Lectures" channel → sample `.pdf`/`.txt`/`.docx`). Endpoints: `GET /teams/teams`, `GET /teams/{id}/channels`, `GET /teams/channels/{id}/files`, `POST /spaces/{id}/sources/teams` (import → copy file, extract text, `origin=teams`). Interface keeps a future `GraphTeamsProvider` a drop-in swap.
4. **Chat agent** (`agent.py`) — `POST /spaces/{id}/chat` {message}:
   - Persists user message, loads space + history + source summaries.
   - **Interviewing state**: system prompt instructs Claude to ask 1–2 questions at a time about exam date, goals, current level, weak topics, weekly study hours. Agent has a `save_student_profile` tool (Anthropic tool use) — when Claude has enough info it calls the tool with the profile JSON; backend saves `profile_json` and flips status to `generating`.
   - After the tool call, backend kicks off generation (synchronous for MVP — generation takes ~seconds) and returns the assistant's reply plus a `profile_completed` flag so the UI can refresh artifacts.
   - **Ready state**: agent becomes a study tutor — answers questions grounded in `extracted_text` of sources (truncated to a token budget), can point at artifacts.
5. **Generation** (`generation.py`) — builds a context bundle (profile + extracted source text, truncated/sampled per source) and makes 3 Claude calls:
   - `study_plan` → markdown, day/week schedule sized to exam date + weekly hours
   - `notes` → condensed markdown notes of key concepts
   - `sample_test` → **JSON** `{title, questions: [{type: mcq|short, question, choices?, answer, explanation}]}` for interactive rendering
   - Each stored as an `Artifact` with `version` incremented on regenerate. `POST /spaces/{id}/artifacts/{kind}/regenerate`.
6. **Config** — `pydantic-settings`: `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL` (env-overridable), `DATABASE_URL` (default sqlite), `STORAGE_DIR`.

## Frontend design

- **SpacesPage**: grid of space cards (name, status, source count), "+ New subject space" dialog.
- **SpacePage** (3 columns):
  - **Left – Sources**: list of attached sources (icon per type, origin badge `teams`/`upload`), upload button, "Import from Teams" opens `TeamsPicker` modal (teams → channels → files drill-down, multi-select import).
  - **Center – Chat**: conversational interview, then tutor chat. While `generating`, show progress note. Non-streaming POST (MVP); message list auto-scrolls.
  - **Right – Artifacts**: tabs **Study plan** / **Notes** (rendered markdown via `react-markdown`) / **Sample test** (`QuizView`: MCQ selection + short-answer inputs, "check answers" reveals explanations + score). Regenerate button per tab.
- Styling: Tailwind; small `ui/` primitives, no component library dependency.

## Implementation order

1. Backend scaffold: config, db, models, health check — verify `uvicorn` runs.
2. Text extraction + sources upload; tests for extract.
3. Mock Teams provider + browse/import endpoints + fixture files; tests.
4. Chat endpoint + interview agent (tool use for `save_student_profile`); unit tests with mocked Anthropic client.
5. Generation service + artifacts endpoints; tests.
6. Frontend scaffold (Vite + Tailwind + router + typed API client).
7. SpacesPage + SpacePage layout; chat panel wired to API.
8. Source list + upload + TeamsPicker.
9. Artifact tabs + QuizView + regenerate.
10. `.env.example`, README-style run notes inside plan output; full test run (pytest + vitest + tsc).

## Verification

- `cd backend && pytest` — all unit tests pass (Anthropic client mocked).
- `cd backend && uvicorn app.main:app` — manual smoke: create space → chat interview → upload + Teams-import sources → artifacts generated.
- `cd frontend && npx tsc --noEmit && npm run build && npx vitest run`.
- Manual end-to-end in browser (`npm run dev` + uvicorn): full UX flow.

## Risks / considerations

- **ANTHROPIC_API_KEY** required at runtime; tests mock the SDK. `.env.example` provided; key is never committed.
- **Token limits**: source text truncated per-source with a total budget; large PDFs get head+tail sampling. Noted as a known MVP limitation (no embeddings/RAG yet).
- **Generation latency**: synchronous (~10–30 s for 3 artifacts) with a `generating` status + UI spinner; can move to background tasks later.
- **Teams provider is fake** by design; `TeamsProvider` protocol + `teams_ref` field keep real Graph API integration a clean swap later (needs Azure AD app + OAuth — out of scope now).
- **No auth**: single-user MVP; schema is per-space so multi-user can be added later.
