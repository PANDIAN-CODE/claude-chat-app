# Claude Chat App — Full Learning Guide

This document explains **everything** in this project: what was built, why, which
software/tools you need, the exact order to build it yourself, and a line-by-line
walkthrough of the important code. Follow it top to bottom and you can rebuild this
entire project manually, one step at a time.

Project location: `C:\Users\arunpandian.a\AIangular`
Live deployed app: https://claude-chat-frontend.onrender.com
Source code: https://github.com/PANDIAN-CODE/claude-chat-app

---

## Part 1 — What This Project Is

A full-stack AI chat application:

- **Frontend:** Angular (TypeScript) — the web page the user sees and types into
- **Backend:** FastAPI (Python) — the server that talks to the Claude API, stores data
- **AI:** Anthropic Claude API — generates the chat replies
- **Database:** SQLite + SQLAlchemy + Alembic — stores users, conversations, documents
- **Auth:** JWT (JSON Web Tokens) + bcrypt password hashing
- **RAG:** Upload PDFs, the app answers questions about them with citations
- **Deployment:** Docker containers, hosted free on Render.com
- **CI/CD:** GitHub Actions — tests run automatically on every push
- **Mobile:** PWA (Progressive Web App) — installable on Android/iOS home screen

---

## Part 2 — Software & Tools You Need

| Tool | Version used | Why | Install |
|---|---|---|---|
| Python | 3.12+ (we used 3.14) | Runs the backend | python.org or `winget install Python.Python.3.12` |
| Node.js | 22.x | Runs Angular's build tooling | nodejs.org |
| npm | 10.x (comes with Node) | Installs frontend packages | — |
| Angular CLI | 18.x | Scaffolds/builds the Angular app | `npm install -g @angular/cli` |
| Git | any recent | Version control | git-scm.com |
| VS Code | any recent | Code editor | code.visualstudio.com |
| Docker Desktop | any recent | Run containers locally (optional but recommended) | docker.com |
| A GitHub account | — | Host your code, trigger deployments | github.com |
| A Render.com account | — | Free hosting | render.com |
| An Anthropic API key | — | Lets your backend call Claude | console.anthropic.com → API Keys |

**No database server install needed** — we use SQLite, which is just a file (built
into Python). **No vector database needed** — we use scikit-learn's TF-IDF directly
on the SQL data (explained in Part 4, Step 8).

### Python packages (installed via `pip install -r requirements.txt`)

| Package | Purpose |
|---|---|
| fastapi | Web framework for the backend API |
| uvicorn | The server that actually runs FastAPI |
| anthropic | Official SDK to call the Claude API |
| python-dotenv | Loads secrets from a `.env` file |
| sqlalchemy | ORM — lets Python code talk to the database without raw SQL |
| alembic | Database migrations (versioned schema changes) |
| passlib[bcrypt] + bcrypt | Password hashing |
| python-jose[cryptography] | Creates/verifies JWT login tokens |
| email-validator | Validates email format |
| pytest + httpx | Automated testing |
| azure-monitor-opentelemetry | Optional cloud monitoring (Azure App Insights) |
| pypdf | Extracts text from uploaded PDF files |
| scikit-learn | TF-IDF text search for RAG (no heavy AI model needed) |
| python-multipart | Lets FastAPI accept file uploads |

### npm packages (installed via `npm install`)

| Package | Purpose |
|---|---|
| @angular/core, @angular/common, etc. | The Angular framework itself |
| marked | Renders Markdown (bold, code blocks, etc.) in chat replies |
| @angular/pwa (dev-only) | Adds installable-app support |

---

## Part 3 — Architecture (the big picture)

```
Your Browser
     |
     v
[Angular Frontend]  <-- nginx serves the built files, proxies /api/* to backend
     |  (fetch calls to /api/...)
     v
[FastAPI Backend]
     |-- /api/auth/*      -> register, login (JWT)
     |-- /api/chat/*      -> send messages, get streamed replies, list history
     |-- /api/documents/* -> upload/list/delete PDFs
     |
     |-- SQLite database (users, conversations, messages, documents, chunks)
     |-- Claude API (Anthropic) for generating replies
     |-- scikit-learn TF-IDF for searching uploaded PDFs
```

Locally: frontend runs on `localhost:4200`, backend on `localhost:8000`.
In production: both run as separate Docker containers on Render, with nginx
proxying frontend-to-backend calls over HTTPS.

---

## Part 4 — Build It Yourself: Step-by-Step Order

This is the **exact sequence** we followed. Do them in this order.

### Step 1 — Scaffold the backend

```
mkdir backend
cd backend
python -m venv venv
venv\Scripts\activate
```

Create `requirements.txt`:
```
fastapi
uvicorn[standard]
anthropic
python-dotenv
```

```
pip install -r requirements.txt
```

Create `.env` (your secrets — never commit this file):
```
ANTHROPIC_API_KEY=your_api_key_here
CLAUDE_MODEL=claude-sonnet-5-5
```

Create `main.py` — the simplest possible version: one endpoint that takes a
message and returns Claude's reply (non-streaming, no auth, no database):
```python
import os
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import anthropic

load_dotenv()
app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:4200"],
                    allow_methods=["POST"], allow_headers=["*"])

client = anthropic.Anthropic()

class ChatRequest(BaseModel):
    message: str

@app.post("/api/chat")
def chat(req: ChatRequest):
    result = client.messages.create(
        model="claude-sonnet-5-5", max_tokens=500,
        messages=[{"role": "user", "content": req.message}],
    )
    return {"answer": result.content[0].text}
```

Run it: `uvicorn main:app --reload --port 8000`

**What you just learned:** FastAPI routing, Pydantic request validation, calling
the Anthropic SDK, CORS (why browsers block cross-origin requests without it).

### Step 2 — Scaffold the frontend

```
ng new frontend --routing=false --style=css
cd frontend
```

Add `provideHttpClient()` to `app.config.ts` so Angular can make HTTP calls.

Create a `ChatComponent` with: an input box, a send button, a list of messages,
and a call to `http.post('http://localhost:8000/api/chat', {message})`.

Run it: `ng serve`. Open `localhost:4200`.

**What you learned:** Angular standalone components, signals (`signal()`),
two-way binding (`[(ngModel)]`), HttpClient.

### Step 3 — Mock mode (develop without paying for API calls)

In `main.py`, check if `ANTHROPIC_API_KEY` is empty/placeholder. If so, skip the
real API call and return a canned response instead. This lets you build the UI
without needing real credits.

**What you learned:** environment-based feature flags, graceful degradation.

### Step 4 — Streaming responses

Real chat apps show text appearing word-by-word, not all at once. Changes:

- Backend: use `client.messages.stream(...)` instead of `.create()`, and return
  a `StreamingResponse` that yields text chunks as they arrive from Claude.
- Frontend: use `fetch()` (not HttpClient, which buffers the whole response) with
  `response.body.getReader()` to read chunks as they arrive and append them to
  the UI live.

**What you learned:** HTTP streaming, Python generators (`yield`), the
`ReadableStream` Web API.

### Step 5 — Conversation history

The AI needs to see prior messages to have a real conversation. Changed the
frontend to send `{conversation_id, message}` instead of resending the whole
history every time — the **backend** now owns history, loading it from the
database before calling Claude.

**What you learned:** stateless HTTP + stateful conversations, the tradeoff of
client-side vs server-side state.

### Step 6 — Better UI

Added: Markdown rendering (the `marked` library), a blinking cursor while
streaming, a Stop button (`AbortController`), and Retry-on-error.

**What you learned:** third-party npm libraries, the `AbortController` API,
Angular's `@if`/`@for` control-flow syntax.

### Step 7 — Database, authentication, persistence

This is the big one. New backend structure:

```
backend/
  database.py       <- SQLAlchemy engine/session setup
  models.py         <- table definitions (User, Conversation, Message)
  schemas.py        <- Pydantic request/response shapes
  auth.py           <- password hashing, JWT create/verify
  routers/
    auth_router.py  <- /api/auth/register, /login
    chat_router.py  <- /api/chat/* (now requires login)
  services/
    claude_service.py  <- the Claude-calling logic, extracted out
  alembic/          <- database migration history
  tests/            <- automated tests
```

Commands used:
```
pip install sqlalchemy alembic passlib[bcrypt] bcrypt==4.0.1 python-jose[cryptography] email-validator pytest httpx
alembic init alembic
# edit alembic/env.py to point at our models
alembic revision --autogenerate -m "initial tables"
alembic upgrade head
```

Key concepts, explained:

- **`database.py`** creates one `engine` (the DB connection) and a `SessionLocal`
  factory. `get_db()` is a FastAPI "dependency" — it opens a session, hands it to
  your endpoint function, then always closes it afterward (the `finally` block).

- **`models.py`** — each `class(Base)` becomes a real SQL table. `relationship()`
  tells SQLAlchemy how tables connect (a User `has many` Conversations).
  `cascade="all, delete-orphan"` means deleting a User also deletes their data.

- **`auth.py`**:
  - `hash_password()` — never store plain-text passwords; bcrypt makes a one-way
    scrambled version you can check against but never reverse.
  - `create_access_token()` — packs `{"sub": user_id, "exp": expiry}` into a
    signed JWT string using your `JWT_SECRET`. Anyone with the secret can verify
    it wasn't tampered with, but can't forge a new one without the secret.
  - `get_current_user()` — a dependency that reads the `Authorization: Bearer
    <token>` header, verifies it, and looks up the User row. Any endpoint that
    takes `user: models.User = Depends(get_current_user)` is now protected.

- **`routers/auth_router.py`**:
  - `/register` — check email isn't taken, hash the password, save the User.
  - `/login` — look up the user by email, verify the password, issue a JWT.

- **`routers/chat_router.py`** — now every endpoint requires
  `Depends(get_current_user)`. The `/stream` endpoint:
  1. Finds or creates a Conversation (scoped to that user — can't see others').
  2. Saves the incoming user Message to the DB.
  3. Loads the full message history for that conversation.
  4. Streams Claude's reply, and in a `finally` block (so it runs even if the
     client disconnects early), saves the assistant's full reply to the DB.

- **Alembic migrations** — instead of manually running `CREATE TABLE` SQL, you
  change your Python `models.py`, run `alembic revision --autogenerate`, and it
  writes the SQL diff for you into a timestamped file in `alembic/versions/`.
  `alembic upgrade head` applies all pending migrations. This gives you a
  version-controlled history of every database schema change.

- **`tests/`** — `conftest.py` sets up a throwaway test database so tests never
  touch your real data. Each test function gets a fresh `client` (a fake HTTP
  client that calls your FastAPI app directly, no real network needed).

Frontend changes: added `auth.service.ts` (login/register/logout, stores the JWT
in `localStorage`), `login.component.ts` (the sign-in form), and updated
`chat.component.ts` to attach `Authorization: Bearer <token>` to every request.

**What you learned:** relational databases, foreign keys, password hashing, JWT
authentication, database migrations, automated testing with fixtures.

### Step 8 — RAG (Retrieval-Augmented Generation)

Goal: let users upload PDFs and ask questions about them.

```
pip install pypdf scikit-learn python-multipart
```

New files:

- **`models.py`** additions — `Document` (one row per uploaded file) and
  `DocumentChunk` (one row per ~800-character slice of that file's text).

- **`services/rag_service.py`**:
  - `extract_text_from_pdf()` — uses `pypdf` to pull raw text out of a PDF.
  - `chunk_text()` — splits long text into overlapping ~800-character pieces
    (overlap means less chance of cutting an important sentence in half between
    two chunks).
  - `retrieve_relevant_chunks()` — **this is the "R" in RAG**. Given the user's
    question, it:
    1. Loads all of that user's chunks from the database.
    2. Uses `TfidfVectorizer` to convert every chunk + the question into number
       vectors, weighting words by how rare/important they are (TF-IDF = Term
       Frequency × Inverse Document Frequency).
    3. Computes `cosine_similarity` between the question vector and every chunk
       vector — a score from 0 (unrelated) to 1 (identical wording).
    4. Returns the top 4 highest-scoring chunks (if any score high enough).
  - `build_rag_system_prompt()` — wraps those chunks in an instruction telling
    Claude "use this if relevant, and cite the filename."

  **Why TF-IDF instead of real AI embeddings?** Real semantic search uses a
  neural network to understand *meaning*, not just matching words. But that
  model needs ~100-500MB of RAM to run. Render's free tier only gives you
  512MB total — loading such a model would crash the whole app. TF-IDF is pure
  math (keyword matching with smart weighting), needs almost no memory, and is
  "good enough" for a learning project. The tradeoff: it won't find a chunk
  about "yearly leave" if you ask about "vacation days" (different words, same
  meaning) — real embeddings would catch that.

- **`routers/documents_router.py`** — upload (validates it's a PDF, extracts +
  chunks + saves text), list, and delete endpoints. All scoped to the logged-in
  user via `get_current_user`.

- **`chat_router.py`** changes — before calling Claude, it now calls
  `retrieve_relevant_chunks()`, appends the result to the system prompt, and
  returns which documents were used via an `X-Citations` response header (JSON),
  since you can't easily mix "extra metadata" into a streaming text response any
  other way.

Frontend: `documents.service.ts` (upload/list/delete via `fetch` with
`FormData` for the file), and `chat.component.ts` reads the `X-Citations`
header after each reply and shows "Sources: file.pdf" under the message.

**What you learned:** text chunking strategies, TF-IDF and cosine similarity
(classic information retrieval, pre-dates neural embeddings), the RAG pattern
(retrieve → augment the prompt → generate), HTTP multipart file uploads,
memory-constrained engineering tradeoffs.

### Step 9 — Docker

- **`backend/Dockerfile`** — starts from a `python:3.12-slim` base image,
  installs `requirements.txt`, copies your code, and on startup runs
  `alembic upgrade head` (so the database schema is always current) then starts
  `uvicorn`.
- **`frontend/Dockerfile`** — a **multi-stage build**: stage 1 uses a `node`
  image to run `ng build` (producing static HTML/JS/CSS); stage 2 copies just
  those built files into a tiny `nginx` image. This keeps the final image small
  (no Node.js runtime needed to just serve static files).
- **`frontend/nginx.conf.template`** — tells nginx to serve the Angular files
  for normal requests, but forward anything starting with `/api/` to the
  backend container. `proxy_buffering off` is critical — without it, nginx
  would wait for the *entire* streamed response before forwarding any of it,
  breaking the live-typing effect.
- **`docker-compose.yml`** — defines both containers and how they network
  together (`backend` and `frontend` can reach each other by service name).

Run locally: `docker compose up --build`, open `localhost:8080`.

**What you learned:** containers vs. VMs (conceptually), multi-stage Docker
builds, reverse proxies, why streaming breaks if a reverse proxy buffers.

### Step 10 — CI/CD (GitHub Actions)

**`.github/workflows/ci.yml`** — on every `git push`, a cloud machine
automatically: installs Python deps and runs `pytest`, installs npm deps and
runs `ng build`, and builds both Docker images — catching broken code before
it reaches production.

**What you learned:** continuous integration, YAML config, why automated tests
matter (they ran your 15 tests on every single push in this project, catching
the bcrypt-version bug and the test-isolation bug long before deployment).

### Step 11 — Cloud deployment (Render)

1. Push code to a GitHub repo (`git init`, `git add`, `git commit`, `git push`).
2. On render.com: **New → Web Service**, connect the repo, set Root Directory
   to `backend`, add environment variables (`ANTHROPIC_API_KEY`,
   `CLAUDE_MODEL`, `JWT_SECRET`, `DATABASE_URL=sqlite:///./app.db` — note: no
   `/data/` prefix, since Render's free tier has no persistent disk, just the
   container's own writable folder).
3. Repeat for the frontend, Root Directory `frontend`, with one env var:
   `BACKEND_URL=https://<your-backend-url>.onrender.com`.
4. Render builds the Dockerfiles automatically and gives you public URLs.

We also wrote `infra/main.bicep` (Azure Container Apps + Key Vault + App
Insights) as an alternative path, documented in `docs/AZURE_DEPLOYMENT.md`, for
when you have Azure admin access.

**What you learned:** the difference between local Docker and cloud container
hosting, environment variables for secrets (never hardcode API keys),
free-tier constraints (sleep after idle, no persistent disk, 512MB RAM).

### Step 12 — Agentic AI (tool use / agent loop)

Up to Step 8, the backend **always** searched uploaded PDFs before every reply,
whether the question needed it or not. That's RAG, but it's not agentic — the
app decided to search, not the AI. This step changes that.

```python
# services/claude_service.py
SEARCH_DOCUMENTS_TOOL = {
    "name": "search_documents",
    "description": "Search the user's uploaded PDFs...",
    "input_schema": {"type": "object",
                      "properties": {"query": {"type": "string"}},
                      "required": ["query"]},
}
```

This is a **tool definition** — not code Claude runs, just a description of a
capability it's allowed to request. The loop:

1. Send the conversation + `tools=[SEARCH_DOCUMENTS_TOOL]` to Claude.
2. If `response.stop_reason == "tool_use"` — Claude decided it needs to search.
   Read the `query` it generated, actually run `retrieve_relevant_chunks()`
   (the same TF-IDF search from Step 8), and send the results back as a
   `tool_result` message.
3. Claude sees the results and either answers, or calls the tool again
   (capped at `MAX_AGENT_ITERATIONS = 3` so a confused model can't loop forever).
4. Once `stop_reason != "tool_use"`, that's the final answer.

This is the **agent loop** pattern underlying every AI agent framework
(LangGraph, Claude Agent SDK, AutoGPT, etc.) at its core: give the model tools,
let it reason about which to use, execute what it asks for, feed the result
back, repeat until done. We implemented the loop by hand here (no framework)
specifically so you can see every step of it.

**Why this matters over Step 8's approach:** ask "What's the capital of
France?" and the old version would waste a search on your PDFs for no reason.
The agentic version lets Claude recognize that's general knowledge and skip
the tool entirely — more accurate, and cheaper (fewer tokens spent on
irrelevant document text).

**What you learned:** tool/function-calling schemas (JSON Schema), the
reason → act → observe loop, why agent loops need an iteration cap, and the
difference between "the app always does X" and "the AI decides whether to
do X."

### Step 13 — Two topics deliberately *not* implemented

**Fine-tuning** — training a custom version of a model on your own data.
Not implemented here because Anthropic doesn't offer customer fine-tuning for
Claude the way some other providers do for their models — you can't retrain
Claude's weights yourself via the API. The nearest equivalent available to you
is what this whole project already does: steering behavior with a good system
prompt and RAG, which covers the vast majority of real use cases anyway.

**Local/open-source models (e.g., via Ollama)** — running a model like Llama
or Mistral on your own machine instead of calling a cloud API. Not implemented
because it's a different architecture, not an addition to this one: it would
mean replacing the Anthropic SDK calls entirely, downloading multi-gigabyte
model weight files, and accepting noticeably lower answer quality than Claude
— which defeats the point of a project specifically about building a *Claude*
chat app. Worth trying as a **separate, standalone exercise** if you want to
compare a local model's quality/speed/cost tradeoffs against calling Claude.

### Step 14 — PWA (installable mobile app)

```
ng add @angular/pwa
```

This auto-generates a `manifest.webmanifest` (app name/icon/colors) and a
service worker (`ngsw-worker.js`) that caches the app so it can be "installed"
from the browser (Chrome: menu → "Add to Home screen").

**Important gotcha you hit:** the service worker aggressively caches the app,
so after deploying an update, you must hard-refresh (Ctrl+Shift+R) to see
changes — this is the #1 PWA debugging surprise.

**What you learned:** service workers, the install-to-home-screen flow, cache
invalidation (one of the two hardest problems in computer science, as the
joke goes).

---

## Part 5 — Topics Covered vs. Your Curriculum List

Mapped against the 11-topic roadmap you shared earlier:

| # | Topic | Covered here? |
|---|---|---|
| 1 | LLM fundamentals (tokens, context, temperature) | Partially — used in practice, not explicitly taught |
| 2 | Prompt engineering (system prompts, structured output) | ✅ System prompts, RAG prompt construction |
| 3 | LLM API integration (streaming, history, errors, retry) | ✅ Fully covered |
| 3 | Token counting, rate limits, cost tracking | ❌ Not covered |
| 3 | Prompt caching, batch APIs | ❌ Not covered |
| 4 | RAG — embeddings, chunking, vector DBs | ✅ Chunking + retrieval done; ❌ real embeddings/vector DB (used TF-IDF instead) |
| 4 | Hybrid search, re-ranking, citations | ✅ Citations done; ❌ hybrid/re-ranking |
| 5 | Tool use / function calling | ✅ Covered (Step 12 — `search_documents` tool) |
| 6 | Agentic AI (agent loops, MCP, multi-agent) | ✅ Agent loop covered (Step 12); ❌ MCP and multi-agent not covered |
| 7 | Multimodal (image/PDF/audio input) | Partially — PDF text extraction only, no image/vision |
| 8 | Evaluation (test sets, LLM-as-judge) | ❌ Not covered |
| 9 | Safety/guardrails (prompt injection, PII) | ❌ Not covered (worth noting: your RAG prompt has no injection defense yet) |
| 10 | LLMOps (logging/tracing, cost monitoring) | Partially — Application Insights wired in, but not LLM-specific tracing |
| 10 | Deployment | ✅ Fully covered (Docker, CI/CD, cloud hosting) |
| 11 | Fine-tuning / local models | ❌ Deliberately skipped — see Step 13 for why |

**Angular-specific AI topics not yet covered** (relevant to your "next project"
suggestion of Angular + RAG):
- Real vector embeddings + a proper vector DB (pgvector, Chroma, Azure AI Search)
- Server-Sent Events (SSE) as an alternative to raw streaming (more standard,
  built-in reconnection)
- Angular signals + RxJS interop for more complex async state
- File drag-and-drop upload UX (we only did a plain file input)
- Multi-document conversations with per-document toggle (which PDFs to search)
- Showing retrieval scores/confidence in the UI
- Rate-limiting the chat endpoint (currently unlimited requests per user)
- Tool use: letting Claude call your own `/api/documents` search function
  directly instead of always injecting all top-k chunks

---

## Part 6 — Quick Command Reference

```bash
# Backend — run locally
cd backend
venv\Scripts\activate
alembic upgrade head
uvicorn main:app --reload --port 8000

# Frontend — run locally
cd frontend
ng serve --port 4200

# Run backend tests
cd backend
pytest -v

# Docker — run everything together
docker compose up --build

# Deploy — just push
git add -A
git commit -m "your message"
git push origin main
# Render auto-deploys both services on push
```

---

## Suggested Order to Re-Build This Yourself

1. Step 1–2 (basic chat, no streaming, no auth) — get comfortable with FastAPI + Angular talking to each other
2. Step 4 (streaming) — understand generators and ReadableStream
3. Step 7 (auth + database) — the biggest conceptual jump; take your time here
4. Step 5–6 (history + UI polish) — quick wins once auth works
5. Step 8 (RAG) — the AI-specific part; read Part 4 Step 8's "why TF-IDF" section
   carefully before building
6. Step 12 (agent loop / tool use) — once RAG works, this is a natural next
   step: same search function, but let Claude decide when to call it
7. Step 9–11 (Docker, CI/CD, deploy) — infrastructure; can be skipped at first
   and added later once the app works locally
8. Step 14 (PWA) — purely cosmetic, do it last

Good luck — build it once by following this guide, then try rebuilding it a
second time from memory, only checking this doc when stuck. That's the fastest
way to actually retain it.
