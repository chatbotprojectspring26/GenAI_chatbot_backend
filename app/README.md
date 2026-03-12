# GenAI Chatbot Backend

FastAPI backend for the GenAI Research Chatbot Platform, built for A/B testing experiments with Prolific participants.

**Stack:** FastAPI · MongoDB (Motor async driver) · OpenAI LLM (gpt-4o-mini) · Pydantic v2

---

## 📁 File Reference

### `app/config.py`
**Purpose:** Central settings loaded from `.env` via `pydantic-settings`.

| Setting | Default | Description |
|---|---|---|
| `MONGODB_URI` | `mongodb://localhost:27017` | MongoDB connection string |
| `MONGODB_DB_NAME` | `chatbot_research` | Database name |
| `OPENAI_API_KEY` | *(set in .env)* | OpenAI API key |
| `OPENAI_MODEL` | `gpt-4o-mini` | LLM model name |
| `OPENAI_TEMPERATURE` | `0.3` | Default sampling temperature |
| `OPENAI_MAX_TOKENS` | `512` | Max output tokens |
| `MEMORY_WINDOW` | `20` | Chat history turns sent to LLM |
| `CORS_ORIGINS` | `http://localhost:3000,http://127.0.0.1:3000` | Comma-separated allowed origins |
| `QUALTRICS_POST_BASE_URL` | – | Post-survey redirect base URL |

**DB used:** None (settings only)  
**Frontend:** Sets CORS to allow requests from the React dev server

---

### `app/db.py`
**Purpose:** MongoDB Motor async client lifecycle — connect, create indexes, disconnect.

| Function | Description |
|---|---|
| `init_db()` | Opens Motor client, creates all collection indexes |
| `close_db()` | Cleanly closes the Motor client on shutdown |
| `get_db()` | FastAPI dependency — returns the Motor database handle per request |
| `get_database()` | Internal helper returning the db handle |

**DB collections indexed:**
- `participants` — unique `(pid, study_id)` compound index
- `conditions` — `(experiment_id, is_active)` index
- `chat_sessions` — indexes on `participant_id`, `status`, `experiment_id`
- `messages` — compound `(chat_session_id, turn_index)` + `prompt_hash`
- `events` — `chat_session_id`, `created_at`

**Frontend:** Not directly called — runs at server startup/shutdown via `lifespan`

---

### `app/models.py`
**Purpose:** Pydantic document models for each MongoDB collection. No SQL tables.

| Class | MongoDB Collection | Key Fields |
|---|---|---|
| `Experiment` | `experiments` | `name`, `status`, `created_at` |
| `Condition` | `conditions` | `experiment_id`, `name`, `system_prompt`, `llm_model`, `temperature`, `is_active` |
| `Participant` | `participants` | `pid`, `study_id`, `assigned_condition_id` |
| `ChatSession` | `chat_sessions` | `id` (UUID), `participant_id`, `condition_id`, `status`, `turn_count` |
| `Message` | `messages` | `chat_session_id`, `turn_index`, `role`, `text`, `prompt_hash`, token counts |
| `Event` | `events` | `event_type`, `severity`, `description`, `chat_session_id` |

**DB used:** Defines the shape of all documents stored in MongoDB  
**Frontend:** Never sent directly — data is serialized via `schemas.py` response models

---

### `app/schemas.py`
**Purpose:** Pydantic request/response models for the API layer (no DB coupling).

| Schema | Type | Used by |
|---|---|---|
| `SessionStartRequest` | Request | `POST /session/start` |
| `SessionStartResponse` | Response | `POST /session/start` |
| `ChatRequest` | Request | `POST /chat` |
| `ChatResponse` | Response | `POST /chat` |
| `FinalChatRequest` | Request | `POST /chat/final` |
| `FinalChatResponse` | Response | `POST /chat/final` |
| `SessionEndRequest` | Request | `POST /session/end` |
| `SessionEndResponse` | Response | `POST /session/end` |
| `ExportQuery` | Request | `GET /admin/export` |

**DB used:** None directly — shapes data coming from / going to the frontend  
**Frontend:** Every request body and response from the React chatbot UI maps to one of these

---

### `app/services.py`
**Purpose:** Business logic layer — all async, talks directly to MongoDB via Motor. Routers call these functions; they never touch HTTP.

| Function | DB Operation | Description |
|---|---|---|
| `get_or_create_participant()` | `participants.find_one_and_update` (upsert) | Idempotent participant lookup by `(pid, study_id)` |
| `_pick_random_condition()` | `conditions.aggregate` `$sample` | Random A/B assignment from active conditions |
| `get_condition()` | `conditions.find_one` | Fetch condition by ObjectId |
| `create_chat_session()` | `chat_sessions.insert_one`, `participants.update_one` | Creates session; assigns condition (stable per PID) |
| `get_chat_session()` | `chat_sessions.find_one` | Validates session exists and is active |
| `end_chat_session()` | `chat_sessions.find_one_and_update` | Sets `status=completed`, records `ended_at` |
| `handle_chat_turn()` | `messages.find`, `messages.insert_many`, `chat_sessions.update_one` | Full turn: load history → call OpenAI → persist messages |
| `_get_next_turn_index()` | `messages.find` + sort | Returns next sequential turn number |
| `build_qualtrics_redirect()` | None | Builds Qualtrics post-survey URL with PID + session params |
| `log_event()` | `events.insert_one` | Audit log for session lifecycle events |

**DB collections used:** `participants`, `conditions`, `chat_sessions`, `messages`, `events`  
**Frontend:** Called indirectly through routers. Frontend never calls services directly.

---

### `app/llm_client.py`
**Purpose:** OpenAI API wrapper. Calls the OpenAI SDK using `AsyncOpenAI`.

| Function | Description |
|---|---|
| `generate_completion()` | Sync OpenAI call — converts role/content list → completions.create, returns `(text, usage_dict)` |
| `generate_completion_async()` | Async OpenAI call via `AsyncOpenAI` client directly. |

**DB used:** None  
**Frontend:** Called by `services.handle_chat_turn()`. The assistant reply travels back to the frontend as `ChatResponse.assistant_message`.

**OpenAI model:** `gpt-4o-mini` (configurable via `OPENAI_MODEL`)

---

### `app/routers_session.py`
**Purpose:** Session lifecycle endpoints — creates, views, and ends chat sessions.

| Endpoint | Method | Description | DB Collections |
|---|---|---|---|
| `/session/start` | POST | Create participant + assign condition + open session | `participants`, `conditions`, `chat_sessions`, `events` |
| `/session/end` | POST | Mark session completed, return Qualtrics redirect URL | `chat_sessions`, `participants`, `events` |
| `/session/view/{id}` | GET | Return raw session doc + all messages | `chat_sessions`, `messages` |
| `/session/active` | GET | List all sessions with `status=active` | `chat_sessions` |

**Frontend calls:**
- `POST /session/start` on page load (receives `chat_session_id` and `condition_name`)
- `POST /session/end` or uses `/chat/final` when participant finishes

---

### `app/routers_chat.py`
**Purpose:** Conversation turn endpoints — sends user messages to OpenAI and returns replies.

| Endpoint | Method | Description | DB Collections |
|---|---|---|---|
| `/chat` | POST | One conversation turn: log + LLM call + persist | `chat_sessions`, `conditions`, `messages` |
| `/chat/final` | POST | Last turn + ends session + returns Qualtrics redirect | `chat_sessions`, `conditions`, `messages`, `participants`, `events` |

**Frontend calls:** Every "Send" button press calls `POST /chat`. The final message uses `POST /chat/final`.

---

### `app/routers_admin.py`
**Purpose:** Admin/research export endpoints — no auth (add if deploying publicly).

| Endpoint | Method | Description | DB Collections |
|---|---|---|---|
| `/admin/sessions` | GET | List sessions, filter by `experiment_id` / `condition_id` | `chat_sessions` |
| `/admin/export?table=messages&format=csv` | GET | Export participants / sessions / messages as CSV or JSON | `participants`, `chat_sessions`, `messages` |

**Frontend:** Research dashboard or direct API calls for data export

---

### `app/routers_health.py`
**Purpose:** Simple liveness probe.

| Endpoint | Method | Description |
|---|---|---|
| `/health` | GET | Returns `{"status": "ok"}` |

**DB used:** None  
**Frontend:** Load balancer / deployment health check

---

### `app/logging_system.py`
**Purpose:** In-memory console logger for real-time session debugging during development.

| Class/Function | Description |
|---|---|
| `SessionLogger` | Tracks live sessions in a dict; prints emoji-formatted events to console |
| `get_session_logger()` | Returns the process-wide singleton logger |

> **Note:** This logs only within a single server process. Persistent audit events are stored in the MongoDB `events` collection via `services.log_event()`.

**DB used:** None directly (reads are done in routers if needed)  
**Frontend:** No interaction — console output only

---

### `app/main.py`
**Purpose:** FastAPI app factory — wires together routers, CORS, and the MongoDB lifespan.

| Component | Description |
|---|---|
| `lifespan()` | Async context manager: calls `init_db()` on startup, `close_db()` on shutdown |
| `create_app()` | Builds the FastAPI instance, registers middleware and routers |

**DB used:** Triggers `init_db()` on server start  
**Frontend:** CORS configured here — must include the React app origin (`http://localhost:3000` or production URL)

---

## 🗄️ MongoDB Collections

| Collection | Primary Key | Purpose |
|---|---|---|
| `experiments` | ObjectId | Experiment registry |
| `conditions` | ObjectId | A/B arms per experiment |
| `participants` | ObjectId | Prolific participant registry |
| `chat_sessions` | UUID string | One session per participant visit |
| `messages` | ObjectId | Every chat turn (user + assistant) |
| `events` | ObjectId | Session lifecycle audit log |

---

## 🚂 Deploying to Railway

### Prerequisites
- [Railway account](https://railway.app) (free tier works)
- MongoDB Atlas free cluster (Railway does not provide managed MongoDB)
- Your OpenAI API key

### 1. Set up MongoDB Atlas (if you don't have one)
1. Go to [cloud.mongodb.com](https://cloud.mongodb.com) → **New Project** → **Build a Cluster** (free M0 tier)
2. Create a database user (username + password — use these in your `MONGODB_URI`)
3. **Network Access → IP Allowlist:**
   - **Local dev**: Add each developer's current IP individually (Atlas shows your current IP with "Add Current IP Address")
   - **Railway production (free tier)**: Railway does not provide static IPs on the free plan, so you must either:
     - *(Option A — simple)* Add `0.0.0.0/0` to allow all IPs ⚠️ less secure but straightforward
     - *(Option B — recommended)* Upgrade to [Railway Pro](https://railway.app/pricing) and use their static egress IPs, then add those specific IPs to Atlas
4. Click **Connect** → **Drivers** → copy the `mongodb+srv://...` connection string

### 2. Create a Railway project
1. Go to [railway.app](https://railway.app) → **New Project** → **Deploy from GitHub repo**
2. Select your GitHub repo (`chatbot_design_2026_FULL` or similar)
3. ⚠️ **Important**: Railway will detect the repo root. Since the backend is in a subdirectory, go to your service → **Settings** → **Root Directory** → set it to the backend folder (`backend` or `GenAI_chatbot_backend`).

### 3. Add environment variables
In Railway → your service → **Variables** tab, add:

| Variable | Value |
|---|---|
| `MONGODB_URI` | `mongodb+srv://user:pass@cluster.mongodb.net/...` |
| `MONGODB_DB_NAME` | `chatbot_research` |
| `OPENAI_API_KEY` | your OpenAI API key (`sk-proj-...`) |
| `OPENAI_MODEL` | `gpt-4o-mini` |
| `CORS_ORIGINS` | `https://your-react-frontend.vercel.app,http://localhost:3000` |
| `QUALTRICS_POST_BASE_URL` | your Qualtrics survey URL |

> All variables are in `.env.example` — use it as a reference.

### 4. Generate a public domain
Railway → your service → **Settings** → **Networking** → **Generate Domain**

### 5. Verify deployment
```bash
curl https://<your-service>.railway.app/health
# Expected: {"status": "ok"}
```
Then open `https://<your-service>.railway.app/docs` to confirm the Swagger UI loads.

---

## 🚀 Running Locally

### 1. Prerequisites
- Python 3.11+
- MongoDB running locally (`mongod`) or MongoDB Atlas URI
- React Frontend running locally

### 2. Install dependencies
```bash
cd GenAI_chatbot_backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
```

### 3. Create `.env`
```env
MONGODB_URI=mongodb://localhost:27017
MONGODB_DB_NAME=chatbot_research
OPENAI_API_KEY=sk-proj-...
OPENAI_MODEL=gpt-4o-mini
CORS_ORIGINS=http://localhost:3000
QUALTRICS_POST_BASE_URL=https://binghamton.qualtrics.com/jfe/form/SV_XXXX
```

### 4. Start the server
```bash
uvicorn app.main:app --reload --port 8000
```

### 5. Seed a condition (MongoDB shell or Compass)
```js
db.conditions.insertOne({
  experiment_id: "<your_experiment_oid>",
  name: "control",
  system_prompt: "You are a helpful assistant.",
  llm_model: "gpt-4o-mini",
  temperature: 0.3,
  max_tokens: 512,
  is_active: true,
  created_at: new Date(),
  updated_at: new Date()
})
```

---

## 🔗 Frontend ↔ Backend Flow

```
React Frontend
      │
      ├── POST /session/start  ──→ Returns chat_session_id + condition_name
      │
      ├── POST /chat            ──→ Returns assistant_message (each turn)
      │                              (stores user + assistant in messages collection)
      │
      └── POST /chat/final      ──→ Returns assistant_message + qualtrics redirect_url
                                     (marks session complete)
```

---

*Author: Kush Gandhi — GenAI Research Platform*
