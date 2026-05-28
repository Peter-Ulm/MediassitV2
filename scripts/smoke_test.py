"""
Standalone smoke test for the MediAssist integration.

Verifies, without needing the FastAPI server running:
  1. shared.schemas imports and validates a sample response.
  2. role2_retrieval can open the bundled ChromaDB and find chunks.
  3. role3_llm.factory can build the configured provider (does NOT
     hit the model — that needs Ollama running or an OpenAI key).

Run from the repo root with the .venv active:
    python scripts/smoke_test.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Make the repo root importable so `import shared`, `import role2_retrieval`,
# `import role3_llm`, `import app` all resolve.
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "backend"))

# Force absolute chroma path so tests work no matter the cwd.
# Resolve to absolute path for whichever DB is configured (default: ctx DB).
_default_chroma_path = str(REPO_ROOT / "vector_store" / "chroma_ctx_db")
os.environ.setdefault("CHROMA_PATH", _default_chroma_path)

from role2_retrieval.utils.chroma_compat import ensure_chroma_compatibility


def check_schemas() -> None:
    from shared.schemas import DiagnosticResponse, DiagnosisItem

    sample = DiagnosticResponse(
        diagnoses=[
            DiagnosisItem(
                rank=1,
                condition="Malaria",
                probability=70,
                reasoning="Fever, chills, and travel history are classic for malaria.",
                evidence="Uncomplicated malaria presents with fever, chills, headache, and malaise.",
                source_section="Chapter 3",
            ),
            DiagnosisItem(
                rank=2,
                condition="Typhoid Fever",
                probability=30,
                reasoning="Sustained fever with headache can indicate enteric fever.",
                evidence="Typhoid fever presents with high-grade fever, headache, abdominal discomfort.",
                source_section="Chapter 5",
            ),
        ],
        follow_up_questions=["Travel history?"],
        recommended_tests=["mRDT", "Blood culture"],
        confidence_overall="medium",
    )
    assert sample.diagnoses[0].condition == "Malaria"
    print("  OK  shared.schemas validates a 2-diagnosis response")


def check_retrieval() -> None:
    import chromadb

    chroma_path = os.environ["CHROMA_PATH"]
    # Read the collection name from env so the smoke test works for both the
    # legacy bundled DB and the contextual index (go-live config).
    collection_name = os.environ.get("CHROMA_COLLECTION", "mediassist_stg_ctx")
    ensure_chroma_compatibility(chroma_path, collection_name)
    client = chromadb.PersistentClient(path=chroma_path)
    cols = client.list_collections()
    assert cols, f"No collections found at {chroma_path}"
    target = next((c for c in cols if c.name == collection_name), None)
    assert target is not None, f"Collection '{collection_name}' missing at {chroma_path}"
    n = client.get_collection(collection_name).count()
    assert n > 0, "Collection is empty"
    print(f"  OK  ChromaDB has {n} chunks in '{collection_name}'")

    # Now run the real Role 2 pipeline end-to-end (encode + search + rerank).
    # Reranking may take a moment on first run because it downloads the
    # cross-encoder weights.
    from role2_retrieval.retrieval.pipeline import retrieve

    chunks = retrieve("fever and chills in a traveler from Mwanza")
    assert chunks, "Retrieval returned no chunks"
    print(f"  OK  Role 2 returned {len(chunks)} chunks; top-score={chunks[0].score:.3f}")
    print(f"      top chunk: {chunks[0].text[:80]}...")


def check_llm_factory() -> None:
    from role3_llm.factory import get_llm_provider

    provider = get_llm_provider()
    print(
        f"  OK  Role 3 factory built provider={provider.get_provider_name()} "
        f"model={getattr(provider, 'model', 'n/a')}"
    )
    if provider.health_check():
        print("  OK  Provider reports healthy")
    else:
        print("  WARN provider.health_check()=False — model server not running?")


def main() -> int:
    print("MediAssist smoke test")
    print(f"Repo root: {REPO_ROOT}")
    print()

    print("1. shared.schemas")
    try:
        check_schemas()
    except Exception as exc:
        print(f"  FAIL {type(exc).__name__}: {exc}")
        return 1

    print()
    print("2. Role 2 retrieval (uses bundled ChromaDB)")
    try:
        check_retrieval()
    except Exception as exc:
        print(f"  FAIL {type(exc).__name__}: {exc}")
        return 1

    print()
    print("3. Role 3 LLM factory")
    try:
        check_llm_factory()
    except Exception as exc:
        print(f"  FAIL {type(exc).__name__}: {exc}")
        return 1

    print()
    print("All checks passed. The system is wired correctly end-to-end.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
