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
                ┌────────────────────────────────┐  ┌────────────────────┐
                │ vector_store/chroma_ctx_db/    │  │ Ollama  (or OpenAI) │
                │ collection: mediassist_stg_ctx │  │ mistral:7b-instruct │
                │ embed: all-MiniLM-L6-v2        │  │ keep_alive=30m      │
                │ (contextual retrieval index)   │  │                     │
                └────────────────────────────────┘  └────────────────────┘
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
│   ├── retrieval/              encoder + ChromaDB searcher (path/collection aware)
│   ├── contextualize/          contextual retrieval: structural prefix + LLM blurb
│   ├── expansion/              synonyms, multi-query, hybrid BM25 (RRF)
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
├── vector_store/
│   ├── chroma_db/              Role 1 — bundled legacy 17 MB ChromaDB
│   └── chroma_ctx_db/          contextual index (bundled, ~19 MB) ← live default
├── frontend/                   Role 5 — Jesca's React UI
├── scripts/
│   ├── setup.ps1               One-shot env setup
│   ├── run.ps1                 Launch backend + frontend
│   ├── build_contextual_index.py  Build the contextual index (offline)
│   ├── eval_retrieval.py       Old-vs-new retrieval eval (hit-rate@5, MRR)
│   └── smoke_test.py           End-to-end wiring verification
├── eval/vignettes.jsonl        Clinical vignettes (retrieval ground truth)
├── docs/superpowers/           Design spec + implementation plan
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

# 5. Create your login — REQUIRED. There is no signup page; the app refuses
#    unauthenticated requests, so you must create an account before logging in.
.\.venv\Scripts\python.exe -m scripts.create_user --email you@clinic.tz --name "Your Name" --role clinician

# 6. Start backend + frontend together, then open the UI and log in
.\scripts\run.ps1
```

Open **http://localhost:5173** for the doctor UI (log in with the account from step 5).
Health check: **http://localhost:8000/api/v1/health**.

> **Retrieval index config.** `.env` is git-ignored, so it does not travel with
> a clone. Set these three keys (they are in `.env.example`) to use the
> contextual index bundled in this repo:
>
> ```bash
> CHROMA_PATH=vector_store/chroma_ctx_db
> CHROMA_COLLECTION=mediassist_stg_ctx
> USE_HYBRID=false
> ```
>
> Without them, retrieval falls back to the legacy `mediassist_stg` index and you
> won't see the contextual-retrieval improvement.

## Authentication & data

Login is real: passwords are bcrypt-hashed, sessions are signed JWTs, and the
`/diagnosis/*` and `/consultations/*` routes require a valid token. Consultations
persist in a local SQLite DB at `data/mediassist.db` (git-ignored — patient data
never leaves the device or enters git). `setup.ps1` generates a real `JWT_SECRET`
in `.env` for you. Create the first account from the repo root:

    .\.venv\Scripts\python.exe -m scripts.create_user --email admin@clinic.tz --name "Admin" --role admin

## Troubleshooting (read this if something doesn't work)

| Symptom | Cause & fix |
|---|---|
| **Diagnosis returns nothing / "no evidence"; retrieval is empty** | The retrieval pipeline needs `rank_bm25`. Re-run `pip install -r requirements.txt` (or `.\.venv\Scripts\pip.exe install rank_bm25`). It also means retrieval failed silently — check the backend window for a `Retrieval failed (...)` log line. |
| **Login fails / every request returns 401** | There is **no signup page**. Create an account first: `.\.venv\Scripts\python.exe -m scripts.create_user --email you@clinic.tz --name "You" --role clinician`, then log in with it. |
| **Health check shows `llm healthy: false` or generation hangs** | Ollama isn't running or the model isn't pulled. Run `ollama serve` in its own window and `ollama pull mistral:7b-instruct`. |
| **Evidence looks like the *old* (keyword) results** | Your `.env` is pointing at the legacy index. Set `CHROMA_PATH=vector_store/chroma_ctx_db` and `CHROMA_COLLECTION=mediassist_stg_ctx` (see `.env.example`). |

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

## Contextual retrieval

STG chunks were originally embedded as bare fragments — a chunk could be just
`"Diagnostic Criteria"` — so retrieval matched on isolated keywords and surfaced
clinically wrong evidence (e.g. a *fever, no respiratory signs* query ranked
Pneumonia first and cited its treatment line). Following Anthropic's
**contextual retrieval**, each chunk now has its `Chapter › Section` context
prepended **before embedding**, so the vector reflects what the chunk is about.

The contextual index is built into a separate ChromaDB
(`vector_store/chroma_ctx_db`, collection `mediassist_stg_ctx`) and bundled in
the repo. The clinician still sees the clean clinical text — the context prefix
is internal (stored as `raw_text` in metadata and shown as the evidence).

Measured on 16 clinical vignettes (chapter-level ground truth, top-5):

| index | hit-rate@5 | MRR |
|-------|-----------|-----|
| legacy (`mediassist_stg`)         | 62.5%      | 0.50 |
| contextual (`mediassist_stg_ctx`) | **68.75%** | **0.66** |

Hybrid BM25 fusion (the `HybridSearcher` + Reciprocal Rank Fusion) is wired in
but **off by default** (`USE_HYBRID=false`) — the eval showed it lowered ranking
quality on the STG. An LLM-blurb step for thin chunks exists but is dormant: the
shipped index is structural-only, so the gains above come from the structural
prefix alone.

```powershell
# Rebuild the contextual index (structural-only, deterministic, no LLM)
.\.venv\Scripts\python.exe -m scripts.build_contextual_index --no-llm

# Reproduce the old-vs-new eval table above
.\.venv\Scripts\python.exe -m scripts.eval_retrieval
```

> Not yet addressed: embeddings cannot represent **negation** ("no cough"), so a
> stated-negative still won't fully suppress a keyword match — that belongs in
> the `role3_llm` ranking prompt and is tracked as a follow-up.

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

# Unit tests (contextual retrieval: prefix, thin-chunk, cache, blurb, fusion)
.\.venv\Scripts\python.exe -m pytest tests/ -q     # 22 tests
```

## License

Academic capstone project — not currently licensed for commercial use.
