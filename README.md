# MediAssist

An AI-powered Clinical Decision Support System (CDSS) for Tanzanian healthcare
facilities. Final-year capstone project at the University of Dar es Salaam.

MediAssist receives patient symptoms, retrieves relevant **Tanzania Standard
Treatment Guidelines (STG)** passages from a local vector database, and
produces a ranked differential diagnosis as structured JSON. The system is
**offline-first** — patient data never leaves the device — using a local LLM
(via Ollama) as the production model and OpenAI's `gpt-4o-mini` as the
development model.

## Team

| Role | Owner                       | Component                                          |
|------|-----------------------------|----------------------------------------------------|
| 1    | Athuman Rajab Athuman       | Knowledge Engineering & Vector Database            |
| 2    | Willard Willbroad Karugaba  | Retrieval Engine & Prompt Engineering              |
| 3    | Peter Sadick Ulomi          | LLM Integration & AI Reasoning                     |
| 4    | Benson Godfrey Lyezia       | Backend API & System Integration                   |
| 5    | Jesca John Kessy            | Frontend Engineer & Dual-Mode Interface            |

## Architecture (runtime)

```
                ┌──────────────────────────────────────────────┐
                │  Frontend (React + Vite + Tailwind)          │
                │  - VITE_API_BASE_URL → live backend          │
                │  - MSW mocks only when no backend configured │
                └─────────────────────┬────────────────────────┘
                                      │  POST /api/v1/diagnosis/generate
                                      ▼
                ┌──────────────────────────────────────────────┐
                │  Backend (FastAPI, uvicorn)                  │
                │  app/services/diagnose.py  ── one call ──────┤
                │     │                                        │
                │     ├─► role2_retrieval.retrieve()           │
                │     │     ChromaDB + cross-encoder rerank    │
                │     │                                        │
                │     └─► role3_llm.run_mediassist_pipeline()  │
                │            Query Planner → Provider →        │
                │            Gatekeeper → Auditor →            │
                │            Calibrator → Strategist           │
                └─────────────────────┬────────────────────────┘
                                      ▼
                ┌────────────────────────────┐  ┌────────────────────┐
                │ vector_store/chroma_db/    │  │ Ollama  (or OpenAI) │
                │ collection: mediassist_stg │  │ mistral:7b-instruct │
                │ embed: all-MiniLM-L6-v2    │  │ keep_alive=30m      │
                └────────────────────────────┘  └────────────────────┘
```

## Repository layout

```
mediassist/
├── backend/                    Role 4 — FastAPI integration layer
│   └── app/
│       ├── main.py             App factory + startup warmup
│       ├── api/routes/         /health, /diagnosis/{retrieve,generate}
│       ├── core/               config, logger
│       ├── schemas/api.py      Public request/response models
│       └── services/diagnose.py  Retrieval → LLM wire
│
├── role2_retrieval/            Role 2 — Willard's retrieval pipeline
│   ├── retrieval/              encoder + ChromaDB searcher
│   ├── expansion/              synonyms + multi-query
│   ├── reranking/              cross-encoder
│   └── utils/                  config, logger
│
├── role3_llm/                  Role 3 — Peter's LLM reasoning pipeline
│   ├── main.py                 run_mediassist_pipeline()
│   ├── factory.py              env-driven provider selection (cached)
│   ├── providers/
│   │   ├── ollama_provider.py  Native ollama-python, JSON mode, keep_alive
│   │   └── openai_provider.py  gpt-4o-mini default, JSON mode
│   ├── parser.py               LLM output → DiagnosticResponse
│   ├── calibration.py          probability normalisation
│   ├── token_counter.py        context-window guard
│   └── validation/             Gatekeeper, Auditor, Strategist
│
├── shared/schemas.py           Pydantic contract used by all roles
├── vector_store/chroma_db/     Role 1 — bundled prebuilt 17 MB ChromaDB
├── frontend/                   Role 5 — Jesca's React UI
├── scripts/
│   ├── setup.ps1               One-shot env setup
│   ├── run.ps1                 Launch backend + frontend
│   └── smoke_test.py           End-to-end wiring verification
├── requirements.txt
├── .env.example
└── README.md
```

## Quick start (Windows / PowerShell)

```powershell
# 1. Make sure Ollama is running (https://ollama.com)
ollama serve            # in its own window — usually starts on install

# 2. From this repo root, run setup once
cd mediassist
.\scripts\setup.ps1     # creates .venv, installs python + npm deps, pulls mistral

# 3. (Optional) For OpenAI mode, edit .env and set OPENAI_API_KEY, LLM_PROVIDER=openai

# 4. Verify the wiring (no LLM call yet — just retrieval + factory)
.\.venv\Scripts\python.exe scripts\smoke_test.py

# 5. Start backend + frontend together
.\scripts\run.ps1
```

Open **http://localhost:5173** for the doctor UI.
Health check: **http://localhost:8000/api/v1/health**.

## Switching models

The point of the provider abstraction is that this is a one-line change.

```bash
# .env
LLM_PROVIDER=ollama
OLLAMA_MODEL=mistral:7b-instruct        # default — already pulled
# Faster alternative (after `ollama pull llama3.2:3b`):
# OLLAMA_MODEL=llama3.2:3b
# Higher quality with OpenAI:
# LLM_PROVIDER=openai
# OPENAI_MODEL=gpt-4o-mini              # or gpt-4o for the premium tier
```

## Why the prototype was slow

The original `LlamaProvider` reused OpenAI's HTTP client against Ollama's
`/v1` shim, with no `keep_alive`, no native JSON mode, and a health check
before every request. On a typical FYP laptop that meant a 5–15 s cold-start
on every call plus an extra HTTP round-trip.

The new [role3_llm/providers/ollama_provider.py](role3_llm/providers/ollama_provider.py)
fixes this by:

* using Ollama's native `/api/chat` endpoint via `ollama-python`,
* enabling **server-side JSON mode** (`format="json"`) — eliminates a whole
  class of parser failures,
* passing **`keep_alive="30m"`** so the model stays resident,
* exposing **`warmup()`** which the FastAPI startup hook calls so the first
  doctor request is fast,
* removing the per-request `health_check()` (health is checked once at
  startup, and `generate()` failures already fall back gracefully).

For demos on a 4 GB-VRAM laptop, `llama3.2:3b` is roughly 3× faster than the
default mistral:7b-instruct and still produces good JSON-grounded answers.

## API surface

| Method | Path                          | Purpose                                  |
|--------|-------------------------------|------------------------------------------|
| GET    | `/api/v1/health`              | Status of LLM, ChromaDB, uptime          |
| POST   | `/api/v1/diagnosis/retrieve`  | STG chunks for given symptoms            |
| POST   | `/api/v1/diagnosis/generate`  | Full pipeline → ranked diagnosis         |

Example request:

```bash
curl -X POST http://localhost:8000/api/v1/diagnosis/generate \
  -H "Content-Type: application/json" \
  -d '{
    "symptoms": "fever, chills, headache, recent travel from Mwanza",
    "patientMeta": {"age": 34, "sex": "male"}
  }'
```

## Testing

```powershell
# Wiring smoke test (no LLM call required)
.\.venv\Scripts\python.exe scripts\smoke_test.py

# Backend pytest (when tests/ is populated)
.\.venv\Scripts\python.exe -m pytest
```

## License

Academic capstone project — not currently licensed for commercial use.
