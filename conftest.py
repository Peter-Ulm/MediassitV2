# conftest.py
"""Ensure the repo root is importable in tests (role2_retrieval, role3_llm, shared)."""
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
