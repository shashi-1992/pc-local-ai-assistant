# Rebuild blueprint — recreate the whole assistant from this file

This file is a **full system spec** (architecture, data flow, folders, env, behavior). It is **not** a line-by-line copy of the codebase: you still **write or regenerate** the source files. With **only** this markdown, you rebuild by **implementing the spec** (by hand or with an AI that reads this doc).

---

## 0. If this blueprint is your only artifact

**What you have:** a map — stack, modules, HTTP routes, and logic in §6–§7.  
**What you must produce:** real files under `backend/app/` (plus `scripts/`, `.env.example`, static UI if you want it).

**Practical paths:**

1. **Ideal:** Keep a **code snapshot** (zip, drive, or repo) *and* this file. The blueprint is how you remember run order and architecture; you don’t re-type the whole app.
2. **Blueprint + coding agent:** Create folders from §4. Paste **this entire file** into the tool and ask, in order: implement `config.py` → `chroma_store.py` → `embeddings.py` → `ingestion.py` + `cli_ingest` → `rag.py` → `routers/chat.py` + `main.py`, each time citing the relevant §§. Add tools and Google routers only after RAG works.
3. **Blueprint + solo coding:** Same module order as (2); test after each step: ingest → then `uvicorn` → then `POST /v1/chat`.

**First milestone:** §7 steps 1–7 with **only** RAG chat (no `use_tools`, no Google). That proves the blueprint end-to-end; everything else is optional layers.

No git required to *build*; use whatever you like to *store* the code you produce.

**Literal copy of almost all source in one markdown:** `docs/REBUILD_SINGLE_FILE.md` (full backend app + tests + `.env.example`, `.gitignore`, `Dockerfile`, scripts, static HTML). Regenerate from the repo with `python scripts/generate_rebuild_single_file.py`.

---

## 1. What you are building

A **local / self-hosted AI assistant** that:

1. **Ingests** markdown/text under `data/knowledge/` (and optionally Confluence via CLI).
2. **Embeds** chunks with an OpenAI-compatible embedding API and stores them in **Chroma** (on-disk, `data/chroma/`).
3. **Answers** user questions via **FastAPI**: retrieve relevant chunks → build context → **chat model** returns an answer grounded on context (RAG).
4. Optionally **calls tools** (Jira, Bitbucket, internal search, Google Chat/Gmail hooks) when `use_tools` is enabled — OpenAI-style function calling through `app.services.chat_agent`.

**Design lock:** bulk knowledge = **RAG**; live actions = **tools** (see `docs/ARCHITECTURE_FROZEN.md`).

---

## 2. Architecture (one picture)

```text
                    ┌─────────────────────────────────────────┐
  Browser / Chat    │  FastAPI  app.main:app                  │
  HTTP POST         │  /v1/chat  /v1/integrations/google-chat  │
        └──────────►│  /docs  /ui/  health                    │
                    └──────┬──────────────────────────────────┘
                           │
         ┌─────────────────┼─────────────────┐
         ▼                 ▼                 ▼
   app.services.rag   chat_agent +      google_chat router
   (retrieve + LLM)   tools/registry    (webhook / card replies)
         │                 │
         ▼                 ▼
   chroma_store      handlers (Jira,
   get_collection     Bitbucket, RAG
         │            tool, Gmail, …)
         ▼
   Chroma PersistentClient → data/chroma/
         ▲
   embeddings.embed_*  ← OpenAI client (cloud or OPENAI_BASE_URL)
         ▲
   ingestion.ingest_*  ← reads data/knowledge/**/*.md|.txt
```

---

## 3. Technology stack

| Layer | Choice |
|-------|--------|
| API | **FastAPI** + **Uvicorn** |
| Settings | **pydantic-settings**, `.env` at **project root** (parent of `backend/`) |
| Vector DB | **Chroma** persistent, cosine space, collection name default `knowledge` |
| LLM | **OpenAI** Python SDK; **chat** + **embeddings**; compatible with **Ollama** via `OPENAI_BASE_URL` |
| HTTP to Atlassian / Google | **httpx**; **Google APIs** via `google-api-python-client` + OAuth where needed |
| Frontend (minimal) | Static **HTML** under `backend/app/static/` served at `/ui/` |

---

## 4. Repository layout (what each part is for)

```text
local-ai-assistant/
├── .env                    # Created by you from .env.example — never share
├── .env.example            # All tunables documented
├── data/
│   ├── knowledge/          # Your .md / .txt sources for RAG
│   └── chroma/               # Created at runtime — vector index
├── backend/
│   ├── app/
│   │   ├── main.py           # FastAPI app, mounts routers + /ui static
│   │   ├── config.py         # Settings ← env
│   │   ├── routers/          # chat, health, google_chat, demo_integration
│   │   ├── services/
│   │   │   ├── rag.py        # Core RAG: retrieve, format context, chat completion
│   │   │   ├── chroma_store.py
│   │   │   ├── embeddings.py # OpenAI embed + chat client factory
│   │   │   ├── ingestion.py  # Chunk files → embed → upsert Chroma
│   │   │   ├── query_router.py   # Adaptive RAG: skip retrieval for trivial messages
│   │   │   ├── hyde.py       # Optional HyDE expansion before retrieval
│   │   │   └── chat_agent.py # Tool loop + OpenAI tools
│   │   ├── tools/
│   │   │   ├── registry.py   # OPENAI_TOOLS schema
│   │   │   └── handlers.py   # Implementations / stubs
│   │   ├── connectors/       # Confluence, Google Chat webhook/API, Gmail, …
│   │   └── cli_*.py          # Ingest, Confluence pull, Google OAuth helpers
│   ├── requirements.txt
│   └── tests/
├── scripts/
│   ├── setup.sh              # venv + pip install
│   └── ingest_docs.sh        # runs cli_ingest
├── docs/                     # ROADMAP, INTEGRATIONS, RAG_ARCHITECTURES, …
└── web/                      # Placeholder for future React (Phase 3)
```

Search the codebase for **`PHASE_`** comments to see what is fully implemented vs stubbed.

---

## 5. Configuration model (env → `app.config.settings`)

- **Project root** is two levels above `backend/app/config.py`. `.env` lives there.
- Important fields (names in env are **SCREAMING_SNAKE** of these):

| Logical setting | Role |
|-----------------|------|
| `openai_api_key` / `openai_base_url` | Embeddings + chat; base URL enables local LLM |
| `embedding_model` / `chat_model` | Model IDs |
| `chroma_persist_dir` / `knowledge_dir` | Defaults `data/chroma`, `data/knowledge` |
| `retrieve_top_k`, `retrieve_max_distance` | Retrieval size + optional cosine distance cutoff |
| `adaptive_rag_enabled`, `rag_hyde_enabled` | Skip trivial queries; HyDE retrieval |
| `jira_*`, `bitbucket_*`, `confluence_*` | Phase 2 Atlassian |
| `google_chat_*`, `gmail_*` | Google Chat webhook/API, Gmail |

Full list and comments: **`.env.example`**.

---

## 6. Core runtime flows

### 6.1 RAG chat (`POST /v1/chat`, `use_tools: false`)

1. `routers/chat.py` → `rag.answer_query_with_trace(message)`.
2. If no OpenAI client possible → return `trace_mode=config` with instructions.
3. If adaptive RAG says “no retrieve” → direct chat with `SYSTEM_DIRECT`, `trace_mode=direct`.
4. If Chroma count is 0 → `index_empty` message.
5. Optional: HyDE rewrites query for embedding (`hyde.expand_query_for_retrieval`).
6. `embed_query` → Chroma `query` with top-k, optional distance filter.
7. If no chunks → `no_match` path (still uses LLM to answer helpfully).
8. Else build context string from chunks → `chat.completions.create` with `SYSTEM_PROMPT` → `trace_mode=retrieved` + `sources`.

### 6.2 Agent chat (`use_tools: true`)

1. `chat_agent.answer_with_tools_with_trace` → OpenAI tools from `tools/registry.py` → handler dispatch in `tools/handlers.py` (Jira, Bitbucket, `search_internal_knowledge`, etc.).

### 6.3 Ingestion

1. Walk `knowledge_dir` for `.md` / `.txt`.
2. Chunk text (see `ingestion.py`), `embed_texts`, `collection.upsert` with ids + metadata `source`, `path`.

Entrypoint: **`python -m app.cli_ingest`** from `backend/` with venv active (or `scripts/ingest_docs.sh`).

---

## 7. Step-by-step: rebuild from nothing

1. Create folder `local-ai-assistant/` with subtree **`backend/app/`** as above (or copy the project tree).
2. Place **`requirements.txt`** and install:  
   `cd backend && python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`
3. Add **`.env.example`** at repo root; copy to **`.env`** and set at minimum **`OPENAI_API_KEY`** or **`OPENAI_BASE_URL`** (+ models if not default).
4. Create **`data/knowledge/`** and add at least one **`.md`** file for testing.
5. Run ingest:  
   `cd backend && source .venv/bin/activate && python -m app.cli_ingest`
6. Run API:  
   `uvicorn app.main:app --reload --host 127.0.0.1 --port 8000`
7. Verify: **`http://127.0.0.1:8000/docs`**, **`POST /v1/chat`**, **`http://127.0.0.1:8000/ui/`**
8. Add routers only after `main.py` pattern: `include_router`, prefix, tags.
9. Extend RAG: touch **`rag.py`**, **`ingestion.py`**, **`chroma_store.py`**, **`embeddings.py`** — not `main.py` logic-heavy.

---

## 8. Optional features (same blueprint, extra wiring)

| Feature | Where to look |
|---------|----------------|
| Confluence pull | `app.cli_confluence`, `connectors/`, then ingest |
| Google Chat (HTTP app) | `routers/google_chat.py`, `docs/GOOGLE_CHAT.md` |
| Gmail | `docs/GMAIL.md`, `cli_gmail.py`, tools |
| Jira / Bitbucket tools | `.env` + `tools/handlers.py` |
| Docker | `Dockerfile` at repo root |

---

## 9. Deeper reference (optional reading)

| Topic | File |
|-------|------|
| Roadmap / phases | `docs/ROADMAP.md` |
| Folder tree | `docs/STRUCTURE.md` |
| RAG vs tools | `docs/ARCHITECTURE_FROZEN.md` |
| RAG patterns | `docs/RAG_ARCHITECTURES.md` |
| Keys & local LLM | `docs/GET_API_KEYS.md`, `docs/LOCAL_LLM.md` |
| Integrations | `docs/INTEGRATIONS.md` |

---

## 10. Sanity checklist after a rebuild

- [ ] `GET /` returns JSON with links to `/docs` and `/ui/`.
- [ ] Ingest runs without error; Chroma directory populated.
- [ ] `POST /v1/chat` returns `trace_mode=retrieved` when docs match the question.
- [ ] With empty index, response explains ingest path (`index_empty`).

Keep this file in **`docs/REBUILD_BLUEPRINT.md`** so you can open **one** document and recreate the system later without hunting the repo.
